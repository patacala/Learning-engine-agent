"""QualificationEngine — Cognition infers the conversation outcome per turn.

Deterministic (no LLM): reads the current AnalysisResult (intent/stage/sentiment)
plus the prior outcome and returns the current best qualification. It never
downgrades a terminal outcome back to OPEN (a scheduled conversation that keeps
chatting stays scheduled), but a stronger/different terminal overrides.
"""

from prosales.core.enums import ConversationStage, Intent, Outcome, Sentiment
from prosales.core.models.analysis import AnalysisResult
from prosales.engines.qualification.models import QualificationResult

_NEGATIVE = {Sentiment.NEGATIVE, Sentiment.VERY_NEGATIVE}
_POSITIVE = {Sentiment.POSITIVE, Sentiment.VERY_POSITIVE}


class QualificationEngine:
    def qualify(self, analysis: AnalysisResult, prior_outcome: str = "open") -> QualificationResult:
        intent = analysis.intent.intent
        sentiment = analysis.sentiment.sentiment
        stage = analysis.stage.stage
        neg = sentiment in _NEGATIVE
        pos = sentiment in _POSITIVE

        outcome = Outcome.OPEN
        reason = "in progress"

        if intent == Intent.COMPLAINT and neg:
            outcome, reason = Outcome.LOST, "complaint with negative sentiment"
        elif intent == Intent.FAREWELL and neg:
            outcome, reason = Outcome.LOST, "negative farewell"
        elif intent == Intent.SCHEDULING and not neg:
            outcome, reason = Outcome.SCHEDULED, "scheduling agreed"
        elif stage in {ConversationStage.CLOSING, ConversationStage.POST_SALE} and pos:
            outcome, reason = Outcome.SCHEDULED, "positive close"
        elif intent == Intent.FAREWELL and not pos:
            outcome, reason = Outcome.ABANDONED, "farewell without commitment"
        elif pos and stage in {ConversationStage.PRESENTATION, ConversationStage.NEGOTIATION}:
            outcome, reason = Outcome.RESOLVED, "progressing positively"

        # Never downgrade a terminal outcome to OPEN; a new terminal overrides.
        prior = self._coerce(prior_outcome)
        if outcome == Outcome.OPEN and prior.is_terminal():
            outcome, reason = prior, "sticky terminal (" + prior.value + ")"

        confidence = self._confidence(analysis, outcome)
        return QualificationResult(
            outcome=outcome,
            confidence=round(confidence, 3),
            is_terminal=outcome.is_terminal(),
            reason=reason,
        )

    @staticmethod
    def _coerce(value: str) -> Outcome:
        try:
            return Outcome(value)
        except ValueError:
            return Outcome.OPEN

    @staticmethod
    def _confidence(analysis: AnalysisResult, outcome: Outcome) -> float:
        if outcome == Outcome.OPEN:
            return 0.3
        # Intent-driven outcomes trust the intent confidence; stage-driven trust
        # the sentiment strength. Blend both, floored so a terminal isn't zero.
        intent_c = analysis.intent.confidence
        sentiment_strength = min(1.0, abs(analysis.sentiment.score))
        return max(0.5, min(1.0, 0.5 * intent_c + 0.5 * sentiment_strength + 0.3))
