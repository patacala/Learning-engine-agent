"""Tests for ContactQualificationEngine — deterministic, accumulating."""

from prosales.core.enums import ConversationStage, Intent, Sentiment, UrgencyLevel
from prosales.core.models.analysis import (
    AnalysisResult,
    ContactSignalResult,
    IntentResult,
    SentimentResult,
    StageResult,
    UrgencyResult,
)
from prosales.engines.contact_qualification.engine import ContactQualificationEngine
from prosales.engines.contact_qualification.models import ContactQualification


def _a(intent, sentiment, stage, signals=None, facts=None, buying=0.0, urgency=UrgencyLevel.LOW):
    return AnalysisResult(
        intent=IntentResult(intent=intent, confidence=0.9),
        sentiment=SentimentResult(sentiment=sentiment, score=0.6),
        stage=StageResult(stage=stage),
        urgency=UrgencyResult(level=urgency),
        contact_signals=ContactSignalResult(
            signals=signals or [], facts=facts or {}, buying_intent=buying
        ),
    )


ENGINE = ContactQualificationEngine()


def test_interest_is_warm_qualifying():
    q = ENGINE.qualify(
        ContactQualification(),
        _a(Intent.INQUIRY, Sentiment.POSITIVE, ConversationStage.DISCOVERY,
           signals=["positive_interest"], facts={"product_interest": "Q4"}, buying=0.4),
    )
    assert q.temperature == "warm"
    assert q.status == "qualifying"


def test_full_bant_scheduled_is_hot_qualified_advance():
    q = ENGINE.qualify(
        ContactQualification(),
        _a(Intent.SCHEDULING, Sentiment.POSITIVE, ConversationStage.CLOSING,
           signals=["appointment_requested", "budget_confirmed", "decision_maker"],
           facts={"timeline": "este mes"}, buying=0.85),
        conversation_outcome="scheduled",
    )
    assert q.temperature == "hot"
    assert q.status == "qualified"
    assert all(q.bant.values())
    assert q.suggested_transition == "advance"


def test_not_interested_is_lost_and_cold():
    q = ENGINE.qualify(
        ContactQualification(),
        _a(Intent.FAREWELL, Sentiment.NEGATIVE, ConversationStage.OBJECTION_HANDLING,
           signals=["not_interested"], buying=0.1),
    )
    assert q.temperature == "cold"
    assert q.suggested_transition == "lost"


def test_signals_accumulate_across_turns():
    q1 = ENGINE.qualify(
        ContactQualification(),
        _a(Intent.INQUIRY, Sentiment.NEUTRAL, ConversationStage.DISCOVERY, signals=["positive_interest"]),
    )
    q2 = ENGINE.qualify(
        q1,
        _a(Intent.SCHEDULING, Sentiment.POSITIVE, ConversationStage.CLOSING, signals=["budget_confirmed"]),
    )
    # both turns' signals present; appointment_requested derived from scheduling intent
    assert "positive_interest" in q2.signals
    assert "budget_confirmed" in q2.signals
    assert "appointment_requested" in q2.signals


def test_facts_merge_and_survive():
    q1 = ENGINE.qualify(ContactQualification(), _a(Intent.INQUIRY, Sentiment.NEUTRAL,
                        ConversationStage.DISCOVERY, facts={"product_interest": "Q4"}))
    q2 = ENGINE.qualify(q1, _a(Intent.NEGOTIATION, Sentiment.POSITIVE,
                        ConversationStage.NEGOTIATION, facts={"budget": "50k"}))
    assert q2.facts == {"product_interest": "Q4", "budget": "50k"}


def test_to_public_shape():
    q = ContactQualification(signals={"positive_interest": 2, "budget_confirmed": 1})
    pub = q.to_public()
    assert pub["signals"] == ["budget_confirmed", "positive_interest"]  # sorted list
    assert set(pub) == {"temperature", "status", "readiness", "bant", "signals", "facts", "suggested_transition"}
