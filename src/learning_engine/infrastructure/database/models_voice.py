"""Voice call DB models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from learning_engine.infrastructure.database.models import Base


class VoiceCallModel(Base):
    __tablename__ = "voice_calls"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[str] = mapped_column(
        String(255), unique=True, index=True
    )
    provider_type: Mapped[str] = mapped_column(String(50), index=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    from_number: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    to_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    direction: Mapped[str] = mapped_column(String(20), default="inbound")
    status: Mapped[str] = mapped_column(String(20), default="active")
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    duration_seconds: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    disconnect_reason: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, default=dict
    )
