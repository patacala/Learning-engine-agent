"""ExpressionExtractor — capture the exact words of great (and bad) sellers.

The LLM points at agent turns and classifies them as winning or anti
expressions; code extracts the verbatim phrase from the real turn text. If the
LLM's quote is a genuine substring of the turn we keep that slice; otherwise we
fall back to the whole turn, so the stored phrase is always real.
"""

import logging

from learning_engine.engines.evidence.models import EvidenceSource
from learning_engine.engines.expressions.models import Expression, ExpressionCandidate
from learning_engine.infrastructure.llm.provider import LLMMessage, LLMProvider

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Eres un analista experto en ventas centrado en el LENGUAJE. Recibes una conversación numerada por turnos.

Identifica las EXPRESIONES del agente que tienen valor reutilizable:
- "winning": frases exactas que generan confianza / avanzan la venta (ej: "Tiene todo el sentido que hagas esa pregunta", "Muchos clientes comenzaron con esa misma preocupación").
- "anti": frases que restan confianza o generan rechazo (ej: "Créame", "No se preocupe", "Es el mejor precio").

Por cada expresión devuelve:
- turn_index: índice del turno del AGENTE donde aparece
- polarity: "winning" o "anti"
- goal: para qué sirve la frase (validar, reencuadrar, cerrar, generar urgencia...)
- stage: etapa de la conversación (apertura, descubrimiento, propuesta, objecion, cierre)
- quote: la frase exacta, copiada literalmente del turno (sin cambiar ni una palabra)

Responde SOLO con JSON válido:
{
  "expressions": [
    {"turn_index": 3, "polarity": "winning", "goal": "validar la preocupación", "stage": "objecion", "quote": "Tiene todo el sentido que hagas esa pregunta"}
  ]
}"""


def _extract_verbatim(turn_text: str, quote: str) -> str:
    """Return the exact slice of turn_text matching quote, else the full turn."""
    q = quote.strip()
    if not q:
        return turn_text.strip()
    idx = turn_text.lower().find(q.lower())
    if idx >= 0:
        return turn_text[idx : idx + len(q)].strip()
    return turn_text.strip()


class ExpressionExtractor:
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider

    async def extract(self, source: EvidenceSource, base_score: float = 0.0) -> list[Expression]:
        if not source.turns:
            return []

        messages = self._build_prompt(source)
        try:
            result = await self.llm.complete_json(messages=messages, temperature=0.2)
        except Exception as e:  # noqa: BLE001
            logger.error("Expression extraction failed: %s", e)
            return []

        return self._anchor(source, result, base_score)

    def _build_prompt(self, source: EvidenceSource) -> list[LLMMessage]:
        numbered = "\n".join(
            f"[{t.turn_index}] {('Agente' if t.speaker == 'agent' else 'Cliente')}: {t.text}"
            for t in source.turns
        )
        return [
            LLMMessage(role="system", content=_SYSTEM_PROMPT),
            LLMMessage(role="user", content=f"Conversación:\n{numbered}"),
        ]

    def _anchor(self, source: EvidenceSource, result: dict, base_score: float) -> list[Expression]:
        raw = result.get("expressions", [])
        if not isinstance(raw, list):
            return []

        conv_ref = str(source.conversation_id or source.id or "")
        agent_ref = str(source.agent_version_id or "")
        out: list[Expression] = []
        for item in raw:
            try:
                cand = ExpressionCandidate(**item)
            except Exception as e:  # noqa: BLE001
                logger.warning("Skipping invalid expression: %s — %s", item, e)
                continue

            turn = source.turn_at(cand.turn_index)
            if turn is None or turn.speaker != "agent":
                continue
            phrase = _extract_verbatim(turn.text, cand.quote)
            if not phrase:
                continue

            out.append(
                Expression(
                    agent_version_id=source.agent_version_id,
                    organization_id=source.organization_id,
                    exact_phrase=phrase,
                    polarity=cand.polarity if cand.polarity in ("winning", "anti") else "winning",
                    goal=cand.goal,
                    stage=cand.stage,
                    score=base_score,
                    contexts=[cand.stage] if cand.stage else [],
                    conversation_ids=[conv_ref] if conv_ref else [],
                    agent_ids=[agent_ref] if agent_ref else [],
                )
            )
        return out
