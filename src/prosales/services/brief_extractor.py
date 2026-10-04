"""Turn a plain-language business brief into full agent config.

A non-technical user pastes a brief in the CRM; this extractor (one LLM call)
produces Identity / Personality / Rules / Strategies payloads that the existing
Management API persists. The LLM is constrained to the real closed vocabularies
(StrategyType, Intent) so it can't invent strategy_types the engine wouldn't
recognize — anything off-list is dropped during validation.
"""

import json
import logging

from prosales.api.v1.schemas.management import (
    BriefResponse,
    IdentityPayload,
    PersonalityPayload,
    RulePayload,
    StrategyPayload,
    TacticPayload,
)
from prosales.core.enums import Intent, StrategyType
from prosales.infrastructure.llm.provider import LLMMessage, LLMProvider

logger = logging.getLogger(__name__)

_VALID_STRATEGY_TYPES = {s.value for s in StrategyType}
_VALID_INTENTS = {i.value for i in Intent}

_SYSTEM_PROMPT = """You configure an AI sales/support agent from a business brief.

Return ONLY a JSON object with these exact top-level keys:
  "identity", "personality", "rules", "strategies".

identity: {{
  "name": str, "description": str,
  "communication_style": one of ["consultive","direct","empathetic","assertive"],
  "principles": [str], "beliefs": [str], "values": [str],
  "words_never_use": [str], "words_prefer": [str]
}}
personality: {{
  "brand_traits": [str], "brand_tone": str, "brand_instructions": [str],
  "voice_traits": [str], "voice_tone": str, "voice_instructions": [str]
}}
rules: [{{ "rule_id": str, "intent": one of {intents} or null,
  "action_type": str, "priority": int }}]
strategies: [{{ "strategy_type": one of {strategy_types},
  "name": str, "description": str,
  "triggers": [{{"intent": one of {intents}}}],
  "tactics": [{{"name": str, "prompt_instruction": str}}] }}]

Rules:
- strategy_type MUST be from the list above. Do not invent new ones.
- Write everything in the language the brief is written in (match the brief).
- Keep it concise but complete: 2-5 strategies, 3-6 rules.
- prompt_instruction must be an actionable instruction to the agent."""


class BriefExtractor:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def extract(self, brief: str) -> BriefResponse:
        system = _SYSTEM_PROMPT.format(
            intents=sorted(_VALID_INTENTS), strategy_types=sorted(_VALID_STRATEGY_TYPES)
        )
        messages = [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=f"Business brief:\n{brief}"),
        ]
        raw = await self.llm.complete_json(messages)
        return self._validate(raw)

    def _validate(self, raw: dict) -> BriefResponse:
        """Coerce the LLM output into the typed payloads, dropping anything that
        would be invalid (unknown strategy_type, unknown intent trigger) rather
        than persisting junk the engine can't use."""
        identity = IdentityPayload(**(raw.get("identity") or {"name": "Assistant"}))
        personality = PersonalityPayload(**(raw.get("personality") or {}))

        rules = []
        for i, r in enumerate(raw.get("rules") or []):
            intent = r.get("intent")
            if intent is not None and intent not in _VALID_INTENTS:
                intent = None  # keep the rule but drop an unrecognized intent filter
            if not r.get("action_type"):
                continue
            rules.append(
                RulePayload(
                    rule_id=r.get("rule_id") or f"brief_rule_{i}",
                    intent=intent,
                    sentiment=r.get("sentiment"),
                    urgency=r.get("urgency"),
                    action_type=r["action_type"],
                    action_params=r.get("action_params") or {},
                    priority=int(r.get("priority", 5)),
                )
            )

        strategies = []
        for s in raw.get("strategies") or []:
            stype = s.get("strategy_type")
            if stype not in _VALID_STRATEGY_TYPES:
                logger.info("Brief extractor dropped unknown strategy_type: %r", stype)
                continue
            triggers = [
                {"intent": t["intent"]}
                for t in (s.get("triggers") or [])
                if isinstance(t, dict) and t.get("intent") in _VALID_INTENTS
            ]
            tactics = [
                TacticPayload(
                    name=t.get("name") or f"tactic_{j}",
                    prompt_instruction=t.get("prompt_instruction", ""),
                    position=j,
                )
                for j, t in enumerate(s.get("tactics") or [])
                if t.get("prompt_instruction")
            ]
            strategies.append(
                StrategyPayload(
                    strategy_type=stype,
                    name=s.get("name") or stype,
                    description=s.get("description", ""),
                    triggers=triggers,
                    priority=int(s.get("priority", 5)),
                    cooldown_seconds=int(s.get("cooldown_seconds", 0)),
                    tactics=tactics,
                )
            )

        return BriefResponse(
            identity=identity, personality=personality, rules=rules, strategies=strategies
        )
