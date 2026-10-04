"""ContactSignalDetector — universal (funnel-agnostic) lead signals + facts.

Per-turn LLM detector (mirrors IntentDetector). Emits abstract sales signals and
structured facts that Cognition can hand to any CRM; the CRM maps them to its
own funnel. Cognition never knows the CRM's funnel stages.
"""

import logging
from typing import Any

from prosales.core.interfaces.engine import BaseDetector
from prosales.core.models.analysis import ContactSignalResult
from prosales.infrastructure.llm.provider import LLMMessage, LLMProvider

logger = logging.getLogger(__name__)

# Universal sales signals (no funnel-stage names — those live in the CRM).
VALID_SIGNALS = {
    "positive_interest",
    "appointment_requested",
    "ready_to_buy",
    "budget_confirmed",
    "decision_maker",
    "asked_for_quote",
    "price_objection",
    "comparing_competitors",
    "needs_more_info",
    "wants_followup",
    "not_interested",
}

_DEFAULT_FACTS_INSTRUCTION = (
    'Hechos (facts): objeto con datos concretos si aparecen, ej: '
    '{"product_interest": "...", "budget": "...", "timeline": "...", '
    '"decision_role": "...", "location": "..."}. Omite lo que no se mencione.'
)


def build_facts_instruction(schema) -> str:
    """Build the 'which facts to extract' instruction from a QualificationSchema.

    Without a schema, falls back to the generic example. With one, the LLM is
    told to extract exactly the configured keys (so each agent/industry captures
    its own fields, and service_needed/product_interest stay distinct). Safe to
    inject via str.format — substituted values keep their braces literally.
    """
    if not schema:
        return _DEFAULT_FACTS_INSTRUCTION
    try:
        fields = schema.enabled_fields()
    except AttributeError:
        return _DEFAULT_FACTS_INSTRUCTION
    if not fields:
        return _DEFAULT_FACTS_INSTRUCTION
    lines = []
    for f in fields:
        desc = f"{f.key} ({f.label}"
        if f.type == "enum" and f.options:
            desc += f"; uno de: {', '.join(f.options)}"
        elif f.type:
            desc += f"; {f.type}"
        desc += ")"
        lines.append(desc)
    return (
        "Hechos (facts): extraé SOLO estos campos si el cliente los menciona "
        "(omití lo que no diga), usando estas keys EXACTAS:\n- " + "\n- ".join(lines)
    )


SIGNAL_PROMPT = """Eres un calificador de leads. Del mensaje del cliente detecta SEÑALES universales de venta y HECHOS estructurados. No inventes.

Señales válidas (usa solo estas): positive_interest, appointment_requested, ready_to_buy, budget_confirmed, decision_maker, asked_for_quote, price_objection, comparing_competitors, needs_more_info, wants_followup, not_interested

{facts_instruction}

buying_intent: 0.0-1.0 (qué tan cerca de comprar suena).

Mensaje del cliente: {message}

Contexto (últimos mensajes):
{context}

Responde SOLO JSON: {{"signals": ["..."], "facts": {{}}, "buying_intent": 0.0}}"""


class ContactSignalDetector(BaseDetector):
    def __init__(self, llm: LLMProvider, model: str = "gpt-4o-mini"):
        self.llm = llm
        self.model = model

    async def detect(self, text: str, context: dict[str, Any] | None = None) -> ContactSignalResult:
        ctx_str = ""
        if context and context.get("recent_messages"):
            ctx_str = "\n".join(f"{m.role}: {m.content}" for m in context["recent_messages"][-3:])

        facts_instruction = build_facts_instruction(
            context.get("qualification_schema") if context else None
        )
        try:
            result = await self.llm.complete_json(
                messages=[
                    LLMMessage(role="system", content="You extract universal sales lead signals."),
                    LLMMessage(
                        role="user",
                        content=SIGNAL_PROMPT.format(
                            message=text, context=ctx_str, facts_instruction=facts_instruction
                        ),
                    ),
                ],
                model=self.model,
            )
            raw_signals = result.get("signals", [])
            signals = [s for s in raw_signals if s in VALID_SIGNALS] if isinstance(raw_signals, list) else []
            facts = result.get("facts", {})
            if not isinstance(facts, dict):
                facts = {}
            buying = float(result.get("buying_intent", 0.0) or 0.0)
            return ContactSignalResult(
                signals=signals, facts=facts, buying_intent=max(0.0, min(1.0, buying))
            )
        except Exception:
            logger.exception("Contact signal detection failed")
            return ContactSignalResult()
