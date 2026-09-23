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

SIGNAL_PROMPT = """Eres un calificador de leads. Del mensaje del cliente detecta SEÑALES universales de venta y HECHOS estructurados. No inventes.

Señales válidas (usa solo estas): positive_interest, appointment_requested, ready_to_buy, budget_confirmed, decision_maker, asked_for_quote, price_objection, comparing_competitors, needs_more_info, wants_followup, not_interested

Hechos (facts): objeto con datos concretos si aparecen, ej: {{"product_interest": "...", "budget": "...", "timeline": "...", "decision_role": "...", "location": "..."}}. Omite lo que no se mencione.

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

        try:
            result = await self.llm.complete_json(
                messages=[
                    LLMMessage(role="system", content="You extract universal sales lead signals."),
                    LLMMessage(
                        role="user",
                        content=SIGNAL_PROMPT.format(message=text, context=ctx_str),
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
