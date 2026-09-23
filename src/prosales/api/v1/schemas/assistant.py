"""Schemas for the neutral assistant channel."""

from uuid import UUID

from pydantic import BaseModel, Field


class AssistantMessageRequest(BaseModel):
    session_id: UUID | None = Field(
        None, description="Existing session to continue; null starts a new session"
    )
    text: str = Field(..., min_length=1, description="What the user just said")


class AssistantMessageResponse(BaseModel):
    session_id: UUID
    reply: str
