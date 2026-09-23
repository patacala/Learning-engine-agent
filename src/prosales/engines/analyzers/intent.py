import json
import logging
from typing import Any

from prosales.core.enums import Intent
from prosales.core.interfaces.engine import BaseDetector
from prosales.core.models.analysis import IntentResult
from prosales.infrastructure.llm.provider import LLMMessage, LLMProvider

logger = logging.getLogger(__name__)

INTENT_PROMPT = """Analyze the user message and classify the intent.
Return JSON with: {{"intent": "<intent>", "confidence": <0-1>, "sub_intent": "<optional>"}}

Valid intents: greeting, inquiry, comparison, objection, negotiation, scheduling, farewell, complaint, follow_up, unknown

User message: {message}

Context (last messages):
{context}"""


class IntentDetector(BaseDetector):
    def __init__(self, llm: LLMProvider, model: str = "gpt-4o-mini"):
        self.llm = llm
        self.model = model

    async def detect(self, text: str, context: dict[str, Any] | None = None) -> IntentResult:
        ctx_str = ""
        if context and context.get("recent_messages"):
            ctx_str = "\n".join(
                f"{m.role}: {m.content}" for m in context["recent_messages"][-3:]
            )

        try:
            result = await self.llm.complete_json(
                messages=[
                    LLMMessage(role="system", content="You are an intent classifier."),
                    LLMMessage(
                        role="user",
                        content=INTENT_PROMPT.format(message=text, context=ctx_str),
                    ),
                ],
                model=self.model,
            )
            return IntentResult(
                intent=Intent(result.get("intent", "unknown")),
                confidence=float(result.get("confidence", 0.5)),
                sub_intent=result.get("sub_intent"),
            )
        except Exception:
            logger.exception("Intent detection failed")
            return IntentResult()
