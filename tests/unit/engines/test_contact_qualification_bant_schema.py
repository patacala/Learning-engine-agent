"""BANT scoring is schema-driven: each org's own fields (tagged with a
bant_dimension) feed BANT, with a per-dimension fallback to the legacy hardcoded
keys when no schema/field is set."""

from learning_engine.core.enums import ConversationStage, Intent, Sentiment, UrgencyLevel
from learning_engine.core.models.analysis import (
    AnalysisResult,
    ContactSignalResult,
    IntentResult,
    SentimentResult,
    StageResult,
    UrgencyResult,
)
from learning_engine.core.models.qualification_schema import (
    QualificationField,
    QualificationSchema,
    default_schema,
)
from learning_engine.engines.contact_qualification.engine import ContactQualificationEngine
from learning_engine.engines.contact_qualification.models import ContactQualification


def _a(facts=None, signals=None, intent=Intent.INQUIRY, urgency=UrgencyLevel.LOW):
    return AnalysisResult(
        intent=IntentResult(intent=intent, confidence=0.9),
        sentiment=SentimentResult(sentiment=Sentiment.NEUTRAL, score=0.5),
        stage=StageResult(stage=ConversationStage.DISCOVERY),
        urgency=UrgencyResult(level=urgency),
        contact_signals=ContactSignalResult(signals=signals or [], facts=facts or {}, buying_intent=0.0),
    )


ENGINE = ContactQualificationEngine()


def test_custom_field_feeds_its_bant_dimension():
    # An org names its authority field however it wants; tagging it drives BANT.
    schema = QualificationSchema(fields=[
        QualificationField(key="quien_decide", label="Who decides", bant_dimension="authority"),
    ])
    q = ENGINE.qualify(
        ContactQualification(),
        _a(facts={"quien_decide": "el gerente"}),  # no "decision_maker" signal
        schema=schema,
    )
    assert q.bant["authority"] is True


def test_untagged_schema_field_does_not_feed_bant():
    schema = QualificationSchema(fields=[
        QualificationField(key="favorite_color", label="Color"),  # no bant_dimension
    ])
    q = ENGINE.qualify(ContactQualification(), _a(facts={"favorite_color": "blue"}), schema=schema)
    assert q.bant["authority"] is False
    assert q.bant["budget"] is False


def test_default_schema_reads_its_tagged_keys():
    # Default schema tags has_budget→budget; capturing it flips budget even
    # though the legacy hardcoded key was "budget".
    schema = default_schema()
    q = ENGINE.qualify(ContactQualification(), _a(facts={"has_budget": True}), schema=schema)
    assert q.bant["budget"] is True


def test_no_schema_falls_back_to_legacy_keys():
    # schema=None → legacy behavior: budget reads facts["budget"], not has_budget.
    legacy_hit = ENGINE.qualify(ContactQualification(), _a(facts={"budget": "50k"}))
    assert legacy_hit.bant["budget"] is True

    legacy_miss = ENGINE.qualify(ContactQualification(), _a(facts={"has_budget": True}))
    assert legacy_miss.bant["budget"] is False  # legacy never read has_budget


def test_universal_signals_still_feed_bant_regardless_of_schema():
    # The signal heuristics are funnel-agnostic and stay, with or without schema.
    schema = QualificationSchema(fields=[])
    q = ENGINE.qualify(
        ContactQualification(),
        _a(signals=["budget_confirmed", "decision_maker"]),
        schema=schema,
    )
    assert q.bant["budget"] is True
    assert q.bant["authority"] is True
