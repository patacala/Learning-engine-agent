"""SQLAlchemy model for per-contact qualification (evolves across conversations)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class ContactQualificationModel(Base):
    __tablename__ = "contact_qualifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    temperature: Mapped[str] = mapped_column(String(10), default="cold")
    status: Mapped[str] = mapped_column(String(20), default="unqualified")
    readiness: Mapped[float] = mapped_column(Float, default=0.0)
    bant: Mapped[dict] = mapped_column(JSONB, default=dict)
    signals: Mapped[dict] = mapped_column(JSONB, default=dict)  # {signal: count}
    facts: Mapped[dict] = mapped_column(JSONB, default=dict)
    suggested_transition: Mapped[str] = mapped_column(String(20), default="hold")
    last_conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
