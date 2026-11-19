import asyncio
import logging
from typing import Any

from learning_engine.core.interfaces.engine import BaseEngine
from learning_engine.core.models.analysis import AnalysisResult
from learning_engine.engines.analyzers.contact_signals import ContactSignalDetector
from learning_engine.engines.analyzers.intent import IntentDetector
from learning_engine.engines.analyzers.language import LanguageDetector
from learning_engine.engines.analyzers.sentiment import SentimentDetector
from learning_engine.engines.analyzers.stage import ConversationStageDetector
from learning_engine.engines.analyzers.unified import UnifiedAnalyzer
from learning_engine.engines.analyzers.urgency import UrgencyDetector

logger = logging.getLogger(__name__)


class AnalyzerOrchestrator(BaseEngine):
    """Runs all detectors in parallel and aggregates results.

    ``unified``, when given, replaces the 4 separate intent/sentiment/stage/
    contact_signals LLM calls with a single ``UnifiedAnalyzer`` call (Fase
    4.2) — ``language``/``urgency`` are rule-based and always run standalone
    regardless. When ``unified`` is None, behavior is identical to before
    (4 independent calls) — kept so the individual detectors/their tests stay
    valid and this is trivially reversible via ``settings.use_unified_analyzer``
    (see pipeline/graph.py).
    """

    def __init__(
        self,
        intent: IntentDetector,
        sentiment: SentimentDetector,
        language: LanguageDetector,
        urgency: UrgencyDetector | None = None,
        stage: ConversationStageDetector | None = None,
        contact_signals: ContactSignalDetector | None = None,
        unified: UnifiedAnalyzer | None = None,
    ):
        self.intent = intent
        self.sentiment = sentiment
        self.language = language
        self.urgency = urgency or UrgencyDetector()
        self.stage = stage
        self.contact_signals = contact_signals
        self.unified = unified

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        text = state["current_message"]
        context = {}
        if state.get("context"):
            context["recent_messages"] = state["context"].recent_messages
        # Schema-aware extraction: the contact-signal detector extracts exactly
        # the agent's configured qualification fields (see build_facts_instruction).
        if state.get("qualification_schema") is not None:
            context["qualification_schema"] = state["qualification_schema"]

        analysis = AnalysisResult()

        if self.unified:
            unified_task = self.unified.detect(text, context)
            language_result, urgency_result, unified_result = await asyncio.gather(
                self.language.detect(text, context),
                self.urgency.detect(text, context),
                unified_task,
                return_exceptions=True,
            )
            if isinstance(unified_result, Exception):
                logger.error("UnifiedAnalyzer failed: %s", unified_result)
            else:
                analysis.intent, analysis.sentiment, analysis.stage, analysis.contact_signals = unified_result

            for name, result in (("language", language_result), ("urgency", urgency_result)):
                if isinstance(result, Exception):
                    logger.error("Detector %s failed: %s", name, result)
                    continue
                setattr(analysis, name, result)

            return {"analysis": analysis}

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
