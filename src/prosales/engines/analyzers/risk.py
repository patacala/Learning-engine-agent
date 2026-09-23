from typing import Any

from prosales.core.enums import RiskLevel, Sentiment
from prosales.core.interfaces.engine import BaseDetector
from prosales.core.models.analysis import RiskResult

RISK_KEYWORDS = ["competencia", "caro", "otro", "mejor oferta", "competitor", "expensive", "too much", "no me convence", "no estoy seguro"]


class RiskDetector(BaseDetector):
    async def detect(self, text: str, context: dict[str, Any] | None = None) -> RiskResult:
        text_lower = text.lower()
        factors = []

        for keyword in RISK_KEYWORDS:
            if keyword in text_lower:
                factors.append(keyword)

        # Check sentiment from context
        if context and context.get("sentiment"):
            if context["sentiment"] in (Sentiment.NEGATIVE, Sentiment.VERY_NEGATIVE):
                factors.append("negative_sentiment")

        if len(factors) >= 3:
            level = RiskLevel.HIGH
        elif len(factors) >= 1:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        return RiskResult(level=level, factors=factors)
