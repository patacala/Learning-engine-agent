"""StyleProfiler — reconstruct an agent's personality and linguistic style.

Objective traits (question ratio, response length, microexpressions, first-person
use, negativity) are computed deterministically over the agent's turns. The
subjective traits (empathy, formality, technical level, analogies, humor,
emotional validation, sales pressure, confidence) come from an LLM when
available; otherwise they stay at 0.0 (unknown) and only the deterministic
signals drive the prompt block.
"""

import logging
import re
from collections import Counter

from learning_engine.engines.evidence.models import EvidenceSource
from learning_engine.engines.identity_learning.models import AgentStyleProfile
from learning_engine.infrastructure.llm.provider import LLMMessage, LLMProvider

logger = logging.getLogger(__name__)

# Curated Spanish sales microexpressions to look for, plus generic leading tokens.
_CANDIDATE_MICRO = [
    "excelente", "perfecto", "claro", "entiendo", "tiene sentido", "por supuesto",
    "genial", "buenísimo", "de acuerdo", "me encanta", "correcto", "así es",
    "exacto", "totalmente", "sin problema", "con gusto", "estupendo",
]
_FIRST_PERSON = re.compile(r"\b(yo|me|mi|mis|nosotros|nuestro|nuestra)\b", re.IGNORECASE)
_NEGATIVE = re.compile(r"\b(no|nunca|nada|imposible|jamás|jamas|tampoco)\b", re.IGNORECASE)

_SUBJECTIVE_KEYS = (
    "empathy_level", "formality", "technical_level", "analogy_use",
    "example_use", "humor_use", "emotional_validation_freq",
    "sales_pressure", "confidence_level",
)

_SYSTEM_PROMPT = """Eres un analista del ESTILO de un vendedor. Recibes varios turnos de un mismo agente de ventas. Evalúa su estilo y devuelve SOLO un JSON con valores 0.0-1.0:
- empathy_level, formality, technical_level, analogy_use, example_use, humor_use, emotional_validation_freq, sales_pressure, confidence_level

Responde SOLO JSON con esas nueve claves."""


class StyleProfiler:
    def __init__(self, llm_provider: LLMProvider | None = None):
        self.llm = llm_provider

    async def profile(self, sources: list[EvidenceSource]) -> AgentStyleProfile:
        agent_turns = [t for s in sources for t in s.turns if t.speaker == "agent"]
        profile = AgentStyleProfile(computed_from_n_conversations=len(sources))
        if sources:
            profile.agent_version_id = sources[0].agent_version_id
            profile.organization_id = sources[0].organization_id
        if not agent_turns:
            return profile

        n = len(agent_turns)
        texts = [t.text for t in agent_turns]
        lowered = [t.lower() for t in texts]

        profile.question_ratio = round(sum(1 for t in texts if "?" in t) / n, 4)
        profile.avg_response_length = round(sum(len(t.split()) for t in texts) / n, 2)

        first_person = sum(1 for t in texts if _FIRST_PERSON.search(t)) / n
        negativity = sum(1 for t in texts if _NEGATIVE.search(t)) / n
        formal = sum(1 for t in lowered if "usted" in t) / n
        profile.linguistic_style = {
            "first_person": round(first_person, 4),
            "avoids_negative_words": round(1.0 - negativity, 4),
            "uses_usted": round(formal, 4),
        }
        profile.microexpressions = self._microexpressions(lowered, texts, n)

        subjective = await self._subjective(agent_turns)
        for k in _SUBJECTIVE_KEYS:
            if k in subjective:
                setattr(profile, k, float(subjective[k]))
        # If the LLM didn't run, seed formality from the deterministic usted-ratio.
        if not subjective and formal:
            profile.formality = round(min(1.0, formal * 2), 4)
        return profile

    def _microexpressions(self, lowered: list[str], texts: list[str], n: int) -> list[dict]:
        counter: Counter[str] = Counter()
        # Curated multi/single-word expressions anywhere in a turn.
        for low in lowered:
            for cand in _CANDIDATE_MICRO:
                if cand in low:
                    counter[cand] += 1
        result = []
        for phrase, count in counter.most_common(8):
            freq = round(count / n, 4)
            if freq >= 0.1:  # appears in at least 10% of the agent's turns
                result.append({"phrase": phrase.capitalize(), "frequency": freq})
        return result

    async def _subjective(self, agent_turns) -> dict:
        if self.llm is None:
            return {}
        sample = "\n".join(f"- {t.text}" for t in agent_turns[:40])
        try:
            data = await self.llm.complete_json(
                messages=[
                    LLMMessage(role="system", content=_SYSTEM_PROMPT),
                    LLMMessage(role="user", content=f"Turnos del agente:\n{sample}"),
                ],
                temperature=0.2,
            )
            return {k: data[k] for k in _SUBJECTIVE_KEYS if k in data}
        except Exception as e:  # noqa: BLE001
            logger.warning("Style subjective analysis failed: %s", e)
            return {}
