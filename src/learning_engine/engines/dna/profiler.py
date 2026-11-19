"""DNAProfiler — build a behavioral fingerprint of a whole conversation.

Objective metrics (talk ratio, question/objection counts, turn length) are
computed deterministically from the evidence turns. The six subjective scores
(trust/curiosity/empathy/urgency/storytelling/pressure) come from an LLM when
available; otherwise they default to neutral 0.5, keeping the profiler usable
without API access.
"""

import logging

from learning_engine.engines.dna.models import ConversationDNA
from learning_engine.engines.evidence.models import EvidenceSource
from learning_engine.infrastructure.llm.provider import LLMMessage, LLMProvider

logger = logging.getLogger(__name__)

_OBJECTION_KEYWORDS = (
    "precio", "caro", "costoso", "no sé", "no se", "duda", "pensar", "pensarlo",
    "comparar", "competencia", "no estoy seguro", "más tarde", "mas tarde", "presupuesto",
)

_SCORE_KEYS = (
    "trust_score", "curiosity_score", "empathy_score",
    "urgency_score", "storytelling_score", "pressure_score",
)

_SYSTEM_PROMPT = """Eres un analista de conversaciones de ventas. Evalúa la conversación y devuelve SOLO un JSON con seis puntajes de 0.0 a 1.0 que describen el comportamiento global:
- trust_score: cuánta confianza se construyó
- curiosity_score: cuánta curiosidad genuina mostró el agente (preguntas, interés)
- empathy_score: cuánta empatía/validación emocional hubo
- urgency_score: cuánta urgencia comercial se imprimió
- storytelling_score: cuánto se usaron historias/ejemplos/analogías
- pressure_score: cuánta presión comercial se ejerció
Además "objections_resolved": entero, cuántas objeciones del cliente quedaron resueltas.

Responde SOLO JSON: {"trust_score":0.0,"curiosity_score":0.0,"empathy_score":0.0,"urgency_score":0.0,"storytelling_score":0.0,"pressure_score":0.0,"objections_resolved":0}"""


def _word_count(text: str) -> int:
    return len(text.split())


class DNAProfiler:
    def __init__(self, llm_provider: LLMProvider | None = None):
        self.llm = llm_provider

    async def profile(self, source: EvidenceSource) -> ConversationDNA:
        turns = source.turns
        dna = ConversationDNA(
            evidence_source_id=source.id,
            conversation_id=source.conversation_id,
            agent_version_id=source.agent_version_id,
            organization_id=source.organization_id,
            outcome=source.outcome,
        )
        if not turns:
            return dna

        agent_turns = [t for t in turns if t.speaker == "agent"]
        client_turns = [t for t in turns if t.speaker == "client"]

        agent_words = sum(_word_count(t.text) for t in agent_turns)
        total_words = sum(_word_count(t.text) for t in turns) or 1

        dna.question_count = sum(t.text.count("?") for t in agent_turns)
        dna.objection_count = sum(
            1 for t in client_turns if any(k in t.text.lower() for k in _OBJECTION_KEYWORDS)
        )
        dna.avg_turn_length = round(total_words / len(turns), 2)
        dna.talk_ratio = round(agent_words / total_words, 4)
        dna.conversational_balance = round(1.0 - abs(dna.talk_ratio - 0.5) * 2, 4)

        scores = await self._subjective_scores(source)
        for k in _SCORE_KEYS:
            setattr(dna, k, float(scores.get(k, 0.5)))
        dna.objections_resolved = min(
            int(scores.get("objections_resolved", 0)), dna.objection_count
        )
        return dna

    async def _subjective_scores(self, source: EvidenceSource) -> dict:
        if self.llm is None:
            return {k: 0.5 for k in _SCORE_KEYS}
        numbered = "\n".join(
            f"{('Agente' if t.speaker == 'agent' else 'Cliente')}: {t.text}" for t in source.turns
        )
        try:
            return await self.llm.complete_json(
                messages=[
                    LLMMessage(role="system", content=_SYSTEM_PROMPT),
                    LLMMessage(role="user", content=numbered),
                ],
                temperature=0.2,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("DNA subjective scoring failed, using neutral: %s", e)
            return {k: 0.5 for k in _SCORE_KEYS}
