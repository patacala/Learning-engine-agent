"""InsightGenerator — conclusions grounded ONLY on aggregated cluster stats.

The LLM never sees raw transcripts here; it reads success rates and occurrence
counts across clusters and produces conclusions plus an actionable behavior_rule
that can be injected into the agent's prompt. Insights below a minimum sample
size are not generated, so a single conversation can never become an "insight".
"""

import logging

from learning_engine.engines.insights.models import Insight
from learning_engine.infrastructure.database.models_performance import PatternClusterModel
from learning_engine.infrastructure.llm.provider import LLMMessage, LLMProvider

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Eres un analista de performance de ventas. Recibes ESTADÍSTICAS AGREGADAS de patrones de conversación (clusters), no transcripciones. Cada cluster trae: id, tipo de movimiento, polaridad, tasa de éxito, veces observado, score promedio y una frase representativa.

Tu tarea: generar INSIGHTS accionables basados SOLO en estos números. Compara clusters, identifica qué comportamientos correlacionan con mayor éxito y cuáles con fracaso.

Por cada insight devuelve:
- insight_text: la conclusión en lenguaje natural (ej: "Validar la preocupación del cliente antes de hablar de precio se asocia con mayor tasa de cierre").
- behavior_rule: una directiva imperativa breve para el agente (ej: "Valida la preocupación del cliente antes de mencionar el precio").
- supporting_cluster_ids: lista de ids de cluster (de los provistos) que sustentan el insight.

No inventes datos ni cites frases que no estén en los clusters. Si la evidencia es débil, genera menos insights.

Responde SOLO JSON:
{"insights": [{"insight_text": "...", "behavior_rule": "...", "supporting_cluster_ids": ["..."]}]}"""


class InsightGenerator:
    def __init__(self, llm_provider: LLMProvider | None = None, min_occurrences: int = 2):
        self.llm = llm_provider
        self.min_occurrences = min_occurrences

    def _eligible(self, clusters: list[PatternClusterModel]) -> list[PatternClusterModel]:
        return [c for c in clusters if c.occurrence_count >= self.min_occurrences]

    async def generate(self, clusters: list[PatternClusterModel]) -> list[Insight]:
        eligible = self._eligible(clusters)
        if len(eligible) < 2 or self.llm is None:
            # Not enough accumulated evidence to draw conclusions.
            return []

        by_id = {str(c.id): c for c in eligible}
        payload = "\n".join(
            f"- id={c.id} kind={c.move_kind} polarity={c.polarity} "
            f"success={c.success_rate:.0%} seen={c.occurrence_count} avg_score={c.avg_score:.2f} "
            f'phrase="{(c.canonical_excerpt or "")[:80]}"'
            for c in eligible
        )
        try:
            result = await self.llm.complete_json(
                messages=[
                    LLMMessage(role="system", content=_SYSTEM_PROMPT),
                    LLMMessage(role="user", content=f"Clusters:\n{payload}"),
                ],
                temperature=0.3,
            )
        except Exception as e:  # noqa: BLE001
            logger.error("Insight generation failed: %s", e)
            return []

        return self._parse(result, by_id)

    def _parse(self, result: dict, by_id: dict[str, PatternClusterModel]) -> list[Insight]:
        raw = result.get("insights", [])
        if not isinstance(raw, list):
            return []
        insights: list[Insight] = []
        total_samples = sum(c.occurrence_count for c in by_id.values())
        for item in raw:
            text = (item.get("insight_text") or "").strip()
            if not text:
                continue
            # Keep only cluster ids that were actually provided (grounding guard).
            support = [cid for cid in item.get("supporting_cluster_ids", []) if cid in by_id]
            kinds = sorted({by_id[cid].move_kind for cid in support})
            # Confidence scales with how much evidence backs the insight.
            backed = sum(by_id[cid].occurrence_count for cid in support)
            confidence = round(min(1.0, backed / max(total_samples, 1)), 3) if support else 0.3
            insights.append(
                Insight(
                    insight_text=text,
                    behavior_rule=(item.get("behavior_rule") or "").strip(),
                    supporting_cluster_ids=support,
                    pattern_kinds=kinds,
                    confidence=confidence,
                    sample_size=backed,
                )
            )
        return insights
