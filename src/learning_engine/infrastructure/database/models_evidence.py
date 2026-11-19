"""SQLAlchemy models for the Evidence layer (source of truth).

Evidence is immutable: exact turns of a conversation, with speaker, index and
timestamp. Everything the learning engine derives (moves, expressions, clusters)
anchors back to these rows.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class EvidenceSourceModel(Base):
    __tablename__ = "evidence_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # expert_transcript | live_conversation | playground
    source_type: Mapped[str] = mapped_column(String(30), default="expert_transcript")
    agent_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    # converted | lost | scheduled | abandoned | pending
    outcome: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    outcome_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EvidenceTurnModel(Base):
    __tablename__ = "evidence_turns"
    __table_args__ = (UniqueConstraint("evidence_source_id", "turn_index", name="uq_evidence_turn"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evidence_source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(String(20))  # agent | client
    text: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
