from pydantic import BaseModel, Field

from prosales.core.enums import (
    ConversationStage,
    Intent,
    Language,
    RiskLevel,
    Sentiment,
    UrgencyLevel,
)


class IntentResult(BaseModel):
    intent: Intent = Intent.UNKNOWN
    confidence: float = 0.0
    sub_intent: str | None = None


class SentimentResult(BaseModel):
    sentiment: Sentiment = Sentiment.NEUTRAL
    score: float = 0.0
    emotions: list[str] = Field(default_factory=list)


class LanguageResult(BaseModel):
    language: Language = Language.ES
    confidence: float = 1.0


class UrgencyResult(BaseModel):
    level: UrgencyLevel = UrgencyLevel.LOW
    signals: list[str] = Field(default_factory=list)


class StageResult(BaseModel):
    stage: ConversationStage = ConversationStage.OPENING
    confidence: float = 0.0


class RiskResult(BaseModel):
    level: RiskLevel = RiskLevel.LOW
    factors: list[str] = Field(default_factory=list)


class ContactSignalResult(BaseModel):
    """Universal (funnel-agnostic) contact/lead signals detected this turn."""

    signals: list[str] = Field(default_factory=list)
    facts: dict = Field(default_factory=dict)
    buying_intent: float = 0.0


class AnalysisResult(BaseModel):
    """Aggregated result from all detectors."""

    intent: IntentResult = Field(default_factory=IntentResult)
    sentiment: SentimentResult = Field(default_factory=SentimentResult)
    language: LanguageResult = Field(default_factory=LanguageResult)
    urgency: UrgencyResult = Field(default_factory=UrgencyResult)
    stage: StageResult = Field(default_factory=StageResult)
    risk: RiskResult = Field(default_factory=RiskResult)
    contact_signals: ContactSignalResult = Field(default_factory=ContactSignalResult)
