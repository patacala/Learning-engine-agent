"""Tests for QualificationEngine — Cognition infers the conversation outcome."""

from learning_engine.core.enums import ConversationStage, Intent, Outcome, Sentiment
from learning_engine.core.models.analysis import (
    AnalysisResult,
    IntentResult,
    SentimentResult,
    StageResult,
)
from learning_engine.engines.qualification.engine import QualificationEngine


def _analysis(intent, sentiment, stage, ic=0.9, ss=0.6):
    return AnalysisResult(
        intent=IntentResult(intent=intent, confidence=ic),
        sentiment=SentimentResult(sentiment=sentiment, score=ss),
        stage=StageResult(stage=stage),
    )


def test_scheduling_positive_is_scheduled():
    r = QualificationEngine().qualify(
        _analysis(Intent.SCHEDULING, Sentiment.POSITIVE, ConversationStage.CLOSING)
    )
    assert r.outcome == Outcome.SCHEDULED and r.is_terminal


def test_complaint_negative_is_lost():
    r = QualificationEngine().qualify(
        _analysis(Intent.COMPLAINT, Sentiment.VERY_NEGATIVE, ConversationStage.OBJECTION_HANDLING)
    )
    assert r.outcome == Outcome.LOST and r.is_terminal


def test_farewell_neutral_is_abandoned():
    r = QualificationEngine().qualify(
        _analysis(Intent.FAREWELL, Sentiment.NEUTRAL, ConversationStage.DISCOVERY)
    )
    assert r.outcome == Outcome.ABANDONED and r.is_terminal


def test_inquiry_is_open_non_terminal():
    r = QualificationEngine().qualify(
        _analysis(Intent.INQUIRY, Sentiment.NEUTRAL, ConversationStage.DISCOVERY)
    )
    assert r.outcome == Outcome.OPEN and not r.is_terminal


def test_terminal_is_sticky_not_downgraded():
    # A scheduled conversation that keeps chatting stays scheduled.
    r = QualificationEngine().qualify(
        _analysis(Intent.INQUIRY, Sentiment.NEUTRAL, ConversationStage.DISCOVERY),
        prior_outcome="scheduled",
    )
    assert r.outcome == Outcome.SCHEDULED


def test_new_terminal_overrides_prior():
    # scheduled → then explicit rejection → lost.
    r = QualificationEngine().qualify(
        _analysis(Intent.FAREWELL, Sentiment.VERY_NEGATIVE, ConversationStage.NEGOTIATION),
        prior_outcome="scheduled",
    )
    assert r.outcome == Outcome.LOST


def test_terminal_confidence_floored():
    r = QualificationEngine().qualify(
        _analysis(Intent.SCHEDULING, Sentiment.POSITIVE, ConversationStage.CLOSING, ic=0.0, ss=0.0)
    )
    assert r.confidence >= 0.5
