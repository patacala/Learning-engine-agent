"""UnifiedAnalyzer — fuses the 4 LLM-backed detectors (intent, sentiment, stage,
contact_signals) into a single ``complete_json`` call.

Fase 4.2 of the improvement plan: measured live (2026-09-23) that the 4
detectors, run in parallel via ``asyncio.gather`` in ``AnalyzerOrchestrator``,
account for ~57% of a turn's total latency (~2.7s of ~4.5s) — bounded by
whichever of the 4 gpt-4o-mini calls is slowest, plus the per-call network/
model overhead paid 4 times over. One combined call trades that for a single
round-trip, at ~75% fewer analyzer tokens.

Trade-off, stated explicitly rather than hidden: today, if ONE detector's LLM
call fails, only that detector falls back to its default — the other 3 still
succeed. Here, if the single call fails (network/rate-limit), all 4 sections
fall back to their defaults together. A malformed/missing individual section
in an otherwise-successful response still falls back per-section, same as
today's per-detector behavior.

Feature-flagged via ``settings.use_unified_analyzer`` (see graph.py) so this
can be turned off without a redeploy if eval quality regresses — see
tests/evals/.
"""

import logging
from typing import Any

from learning_engine.core.enums import ConversationStage, Intent, Sentiment
from learning_engine.core.models.analysis import (
    ContactSignalResult,
    IntentResult,
    SentimentResult,
    StageResult,
)
from learning_engine.engines.analyzers.contact_signals import VALID_SIGNALS, build_facts_instruction
from learning_engine.infrastructure.llm.provider import LLMMessage, LLMProvider

logger = logging.getLogger(__name__)

UNIFIED_PROMPT = """Mensaje del cliente: {message}

Conversación / contexto (últimos mensajes):
{context}

Analizá el mensaje de arriba en 4 dimensiones independientes y devolvé SOLO JSON
con esta forma exacta (las 4 secciones, siempre):

{{
  "intent": {{"intent": "<intent>", "confidence": <0-1>, "sub_intent": "<opcional o null>"}},
  "sentiment": {{"sentiment": "<sentiment>", "score": <-1 a 1>, "emotions": ["<emocion>"]}},
  "stage": {{"stage": "<stage>", "confidence": <0-1>}},
  "contact_signals": {{"signals": ["..."], "facts": {{}}, "buying_intent": <0-1>}}
}}

--- intent ---
Clasificá la intención PRINCIPAL del mensaje — qué es lo que el cliente está
haciendo ahora, no de qué habla en general.
Intents válidos: greeting, inquiry, comparison, objection, negotiation, scheduling, farewell, complaint, follow_up, unknown
- scheduling: el cliente propone, pide o confirma un día/hora/lugar concreto para
  encontrarse o ver el producto (ej. "¿puedo pasar el sábado?", "nos vemos mañana").
  Prevalece sobre "inquiry" cuando hay una fecha/momento concreto de por medio,
  aunque el mensaje también incluya una pregunta.
- inquiry: pregunta o pedido de información general, sin proponer un momento concreto
  para encontrarse.

--- sentiment ---
Evaluá el sentimiento del CLIENTE hacia la conversación y la compra, leyendo el
mensaje EN EL CONTEXTO de los mensajes anteriores — no solo la carga emocional de
la frase aislada. Un cliente que pregunta, da datos o muestra interés activo es
positive (very_positive si hay entusiasmo claro); neutral SOLO cuando no hay
ninguna señal de disposición; negative/very_negative ante rechazo, molestia o
desinterés.
Sentiments válidos: very_positive, positive, neutral, negative, very_negative

--- stage ---
Determiná la etapa de venta actual según la conversación.
Stages válidos: opening, discovery, presentation, objection_handling, negotiation, closing, post_sale

--- contact_signals ---
Sos un calificador de leads. Detectá SEÑALES universales de venta y HECHOS estructurados. No inventes.
Señales válidas (usa solo estas): positive_interest, appointment_requested, ready_to_buy, budget_confirmed, decision_maker, asked_for_quote, price_objection, comparing_competitors, needs_more_info, wants_followup, not_interested
{facts_instruction}
buying_intent: 0.0-1.0 (qué tan cerca de comprar suena)."""


def _parse_intent(data: dict) -> IntentResult:
    try:
        return IntentResult(
            intent=Intent(data.get("intent", "unknown")),
            confidence=float(data.get("confidence", 0.5)),
            sub_intent=data.get("sub_intent"),
        )
    except Exception:
        logger.exception("UnifiedAnalyzer: intent section malformed, using default")
        return IntentResult()


def _parse_sentiment(data: dict) -> SentimentResult:
    try:
        return SentimentResult(
            sentiment=Sentiment(data.get("sentiment", "neutral")),
            score=float(data.get("score", 0.0)),
            emotions=data.get("emotions", []),
        )
    except Exception:
        logger.exception("UnifiedAnalyzer: sentiment section malformed, using default")
        return SentimentResult()


def _parse_stage(data: dict) -> StageResult:
    try:
        return StageResult(
            stage=ConversationStage(data.get("stage", "opening")),
            confidence=float(data.get("confidence", 0.5)),
        )
    except Exception:
        logger.exception("UnifiedAnalyzer: stage section malformed, using default")
        return StageResult()


def _parse_contact_signals(data: dict) -> ContactSignalResult:
    try:
        raw_signals = data.get("signals", [])
        signals = [s for s in raw_signals if s in VALID_SIGNALS] if isinstance(raw_signals, list) else []
        facts = data.get("facts", {})
        if not isinstance(facts, dict):
            facts = {}
        buying = float(data.get("buying_intent", 0.0) or 0.0)
        return ContactSignalResult(signals=signals, facts=facts, buying_intent=max(0.0, min(1.0, buying)))
    except Exception:
        logger.exception("UnifiedAnalyzer: contact_signals section malformed, using default")
        return ContactSignalResult()


class UnifiedAnalyzer:
    """One LLM call producing intent + sentiment + stage + contact_signals."""

    def __init__(self, llm: LLMProvider, model: str = "gpt-4o-mini"):
        self.llm = llm
        self.model = model

    async def detect(
        self, text: str, context: dict[str, Any] | None = None
    ) -> tuple[IntentResult, SentimentResult, StageResult, ContactSignalResult]:
        ctx_str = ""
        if context and context.get("recent_messages"):
            ctx_str = "\n".join(f"{m.role}: {m.content}" for m in context["recent_messages"][-5:])

        facts_instruction = build_facts_instruction(
            context.get("qualification_schema") if context else None
        )
        try:
            result = await self.llm.complete_json(
                messages=[
                    LLMMessage(
                        role="system",
                        content="Sos un analizador de conversaciones de ventas. Respondés solo JSON.",
                    ),
                    LLMMessage(
                        role="user",
                        content=UNIFIED_PROMPT.format(
                            message=text, context=ctx_str, facts_instruction=facts_instruction
                        ),
                    ),
                ],
                model=self.model,
            )
        except Exception:
            logger.exception("UnifiedAnalyzer call failed — all 4 sections fall back to default")
            return IntentResult(), SentimentResult(), StageResult(), ContactSignalResult()

        return (
            _parse_intent(result.get("intent", {}) or {}),
            _parse_sentiment(result.get("sentiment", {}) or {}),
            _parse_stage(result.get("stage", {}) or {}),
            _parse_contact_signals(result.get("contact_signals", {}) or {}),
        )
