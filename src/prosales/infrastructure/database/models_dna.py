"""SQLAlchemy model for Conversation DNA.

A high-level behavioral fingerprint of a whole conversation, enabling similarity
search ("show similar conversations that converted") and comparison.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base

# Compact numeric feature vector used for cosine similarity between conversations.
DNA_DIM = 12


class ConversationDNAModel(Base):
    __tablename__ = "conversation_dna"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evidence_source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    agent_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    # High-level behavioral scores (0-1)
    trust_score: Mapped[float] = mapped_column(Float, default=0.0)
    curiosity_score: Mapped[float] = mapped_column(Float, default=0.0)
    empathy_score: Mapped[float] = mapped_column(Float, default=0.0)
    urgency_score: Mapped[float] = mapped_column(Float, default=0.0)
    storytelling_score: Mapped[float] = mapped_column(Float, default=0.0)
    pressure_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Objective counts / ratios
    question_count: Mapped[int] = mapped_column(Integer, default=0)
    objection_count: Mapped[int] = mapped_column(Integer, default=0)
    objections_resolved: Mapped[int] = mapped_column(Integer, default=0)
    avg_turn_length: Mapped[float] = mapped_column(Float, default=0.0)
    talk_ratio: Mapped[float] = mapped_column(Float, default=0.0)  # agent words / total words
    conversational_balance: Mapped[float] = mapped_column(Float, default=0.0)

    dna_vector = mapped_column(Vector(DNA_DIM), nullable=True)
    outcome: Mapped[str] = mapped_column(String(50), default="pending", index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
