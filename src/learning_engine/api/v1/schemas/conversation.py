from uuid import UUID

from pydantic import BaseModel, Field


class MessageRequest(BaseModel):
    message: str
    client_id: str  # external client ID
    conversation_id: UUID | None = None  # None = new conversation


class MessageResponse(BaseModel):
    conversation_id: UUID
    response: str
    voice_ssml: str | None = None
    analysis: dict = Field(default_factory=dict)
    route: str = ""
    contact_qualification: dict = Field(default_factory=dict)
