"""SQLAlchemy model for Learning sessions (a grouping of ingests).

Replaces the old training_sessions table. Each session groups the evidence
sources / moves extracted from one or more transcript/audio ingests.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class LearningSessionModel(Base):
    __tablename__ = "learning_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    source_label: Mapped[str] = mapped_column(String(255), default="")
    transcript: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(50), default="text")  # text | audio
    status: Mapped[str] = mapped_column(String(50), default="processing")  # processing | completed | draft
    moves_extracted: Mapped[int] = mapped_column(Integer, default=0)
    moves_approved: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
