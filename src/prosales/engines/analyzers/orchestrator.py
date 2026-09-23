import asyncio
import logging
from typing import Any

from prosales.core.interfaces.engine import BaseEngine
from prosales.core.models.analysis import AnalysisResult
from prosales.engines.analyzers.contact_signals import ContactSignalDetector
from prosales.engines.analyzers.intent import IntentDetector
from prosales.engines.analyzers.language import LanguageDetector
from prosales.engines.analyzers.sentiment import SentimentDetector
from prosales.engines.analyzers.stage import ConversationStageDetector
from prosales.engines.analyzers.urgency import UrgencyDetector

logger = logging.getLogger(__name__)


class AnalyzerOrchestrator(BaseEngine):
    """Runs all detectors in parallel and aggregates results."""

    def __init__(
        self,
        intent: IntentDetector,
        sentiment: SentimentDetector,
        language: LanguageDetector,
        urgency: UrgencyDetector | None = None,
        stage: ConversationStageDetector | None = None,
        contact_signals: ContactSignalDetector | None = None,
    ):
        self.intent = intent
        self.sentiment = sentiment
        self.language = language
        self.urgency = urgency or UrgencyDetector()
        self.stage = stage
        self.contact_signals = contact_signals

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        text = state["current_message"]
        context = {}
        if state.get("context"):
            context["recent_messages"] = state["context"].recent_messages

        # Run all detectors in parallel
        tasks = [
            self.intent.detect(text, context),
            self.sentiment.detect(text, context),
            self.language.detect(text, context),
            self.urgency.detect(text, context),
        ]

        # Optional detectors (Phase 2)
        if self.stage:
            tasks.append(self.stage.detect(text, context))
        if self.contact_signals:
            tasks.append(self.contact_signals.detect(text, context))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        analysis = AnalysisResult()

        # Map results by position
        detectors = ["intent", "sentiment", "language", "urgency"]
        if self.stage:
            detectors.append("stage")
        if self.contact_signals:
            detectors.append("contact_signals")

        for name, result in zip(detectors, results):
            if isinstance(result, Exception):
                logger.error("Detector %s failed: %s", name, result)
                continue
            setattr(analysis, name, result)

        return {"analysis": analysis}
