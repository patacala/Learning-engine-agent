from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ClientMemory(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    client_id: UUID
    key: str
    value: str
    confidence: float = 1.0
    source: str = "conversation"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Client(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    external_id: str | None = None
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    memories: list[ClientMemory] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
