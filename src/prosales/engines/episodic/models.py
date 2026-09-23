"""Episodic Memory DTOs — facts only, no interpretation."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Episode(BaseModel):
    """Structured record of a completed conversation. Facts only, no interpretation."""

    id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID
    client_id: UUID
    organization_id: UUID | None = None

    # Temporal
    started_at: datetime | None = None
    closed_at: datetime | None = None
    duration_seconds: float = 0.0
    message_count: int = 0

    # Observable facts from events
    dominant_intent: str = ""
    dominant_sentiment: str = ""
    sentiment_shifts: int = 0
    final_stage: str = ""
    objections_detected: list[str] = Field(default_factory=list)
    strategies_used: list[str] = Field(default_factory=list)
    urgency_signals: list[str] = Field(default_factory=list)
    risk_signals: list[str] = Field(default_factory=list)

    # CRM feedback (updated later)
    outcome: str = "pending"
    outcome_notes: str = ""


class EpisodeSummary(BaseModel):
    """Compact episode view for pipeline context."""

    conversation_id: UUID
    dominant_intent: str = ""
    dominant_sentiment: str = ""
    objections_detected: list[str] = Field(default_factory=list)
    strategies_used: list[str] = Field(default_factory=list)
    outcome: str = "pending"
    closed_at: datetime | None = None


class EpisodeFeedback(BaseModel):
    """Schema for PATCH endpoint — CRM updates outcome."""

    outcome: str
    outcome_notes: str = ""
