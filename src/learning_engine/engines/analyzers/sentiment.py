import logging
from typing import Any

from learning_engine.core.enums import Sentiment
from learning_engine.core.interfaces.engine import BaseDetector
from learning_engine.core.models.analysis import SentimentResult
from learning_engine.infrastructure.llm.provider import LLMMessage, LLMProvider

logger = logging.getLogger(__name__)

SENTIMENT_PROMPT = """Evaluate the CUSTOMER's sentiment toward the conversation
and the purchase, reading the message IN THE CONTEXT of the previous messages —
not just the isolated emotional charge of the phrase. A customer who asks
questions, shares data, or shows active interest is positive (very_positive on
clear enthusiasm); neutral ONLY when there is no sign of disposition;
negative/very_negative on rejection, annoyance, or disinterest.

Return JSON: {{"sentiment": "<sentiment>", "score": <-1 to 1>, "emotions": ["<emotion1>"]}}

Valid sentiments: very_positive, positive, neutral, negative, very_negative

Previous messages:
{context}

Message: {message}"""


def _format_context(context: dict[str, Any] | None) -> str:
    if context and context.get("recent_messages"):
        return "\n".join(f"{m.role}: {m.content}" for m in context["recent_messages"][-5:])
    return "(none)"


class SentimentDetector(BaseDetector):
    def __init__(self, llm: LLMProvider, model: str = "gpt-4o-mini"):
        self.llm = llm
        self.model = model

    async def detect(self, text: str, context: dict[str, Any] | None = None) -> SentimentResult:
        try:
            result = await self.llm.complete_json(
                messages=[
                    LLMMessage(role="system", content="You are a sentiment analyzer."),
                    LLMMessage(
                        role="user",
                        content=SENTIMENT_PROMPT.format(
                            message=text, context=_format_context(context)
                        ),
                    ),
                ],
                model=self.model,
            )
            return SentimentResult(
                sentiment=Sentiment(result.get("sentiment", "neutral")),
                score=float(result.get("score", 0.0)),
                emotions=result.get("emotions", []),
            )
        except Exception:
            logger.exception("Sentiment detection failed")
            return SentimentResult()
