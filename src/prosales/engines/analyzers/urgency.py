import re
from typing import Any

from prosales.core.enums import UrgencyLevel
from prosales.core.interfaces.engine import BaseDetector
from prosales.core.models.analysis import UrgencyResult

URGENCY_SIGNALS = {
    "high": ["urgente", "ya", "ahora", "hoy", "inmediato", "urgent", "now", "today", "asap", "rápido"],
    "medium": ["pronto", "esta semana", "soon", "this week", "cuando pueda"],
}


class UrgencyDetector(BaseDetector):
    async def detect(self, text: str, context: dict[str, Any] | None = None) -> UrgencyResult:
        text_lower = text.lower()
        signals = []

        for word in URGENCY_SIGNALS["high"]:
            if word in text_lower:
                signals.append(word)

        if signals:
            return UrgencyResult(level=UrgencyLevel.HIGH, signals=signals)

        for word in URGENCY_SIGNALS["medium"]:
            if word in text_lower:
                signals.append(word)

        if signals:
            return UrgencyResult(level=UrgencyLevel.MEDIUM, signals=signals)

        return UrgencyResult(level=UrgencyLevel.LOW)
