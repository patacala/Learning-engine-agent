"""Response schemas for the timeline API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from prosales.core.types import JSON


class TimelineEntry(BaseModel):
    timestamp: datetime
    event_type: str
    summary: str  # "Intent: Price Objection (0.92)"
    details: JSON = Field(default_factory=dict)
    duration_ms: float | None = None


class TimelineResponse(BaseModel):
    conversation_id: UUID
    entries: list[TimelineEntry] = Field(default_factory=list)
    total_duration_ms: float = 0
    total_tokens: int = 0
    pipeline_version: str = ""
    model_used: str = ""
