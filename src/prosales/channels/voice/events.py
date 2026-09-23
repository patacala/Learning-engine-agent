"""Internal voice call events for CRM notification."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CallStartedEvent(BaseModel):
    """Emitted when a voice call begins."""

    session_id: str
    conversation_id: UUID
    client_id: UUID
    organization_id: UUID | None = None
    from_number: str | None = None
    to_number: str | None = None
    provider_type: str = ""
    started_at: datetime


class CallEndedEvent(BaseModel):
    """Emitted when a voice call ends — includes summary for CRM."""

    session_id: str
    conversation_id: UUID
    client_id: UUID
    organization_id: UUID | None = None
    duration_seconds: int = 0
    turn_count: int = 0
    disconnect_reason: str = "normal"
    ended_at: datetime
    summary: dict = {}
