import logging
from typing import Any

from prosales.core.enums import Sentiment
from prosales.core.interfaces.engine import BaseDetector
from prosales.core.models.analysis import SentimentResult
from prosales.infrastructure.llm.provider import LLMMessage, LLMProvider

logger = logging.getLogger(__name__)

SENTIMENT_PROMPT = """Analyze the sentiment of this message.
Return JSON: {{"sentiment": "<sentiment>", "score": <-1 to 1>, "emotions": ["<emotion1>"]}}

Valid sentiments: very_positive, positive, neutral, negative, very_negative

Message: {message}"""


class SentimentDetector(BaseDetector):
    def __init__(self, llm: LLMProvider, model: str = "gpt-4o-mini"):
        self.llm = llm
        self.model = model

    async def detect(self, text: str, context: dict[str, Any] | None = None) -> SentimentResult:
        try:
            result = await self.llm.complete_json(
                messages=[
                    LLMMessage(role="system", content="You are a sentiment analyzer."),
                    LLMMessage(role="user", content=SENTIMENT_PROMPT.format(message=text)),
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
