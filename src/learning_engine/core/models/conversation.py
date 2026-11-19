from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from learning_engine.core.enums import ConversationStage, Language, MessageRole


class Message(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID
    role: MessageRole
    content: str
    language: Language = Language.ES
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Conversation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    client_id: UUID
    stage: ConversationStage = ConversationStage.OPENING
    language: Language = Language.ES
    messages: list[Message] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
