"""SQLAlchemy model for Conversation Moves.

A move is a complete conversational action that may span several consecutive
turns (validate -> ask -> reframe). It stores the verbatim excerpt (the memory),
the client-state transition it produced, and the conditions under which it works.
Moves are the human-approvable proposals of the new learning pipeline.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class ConversationMoveModel(Base):
    __tablename__ = "conversation_moves"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evidence_source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    agent_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    # Anchor into evidence_turns (provenance)
    start_turn_index: Mapped[int] = mapped_column(Integer, default=0)
    end_turn_index: Mapped[int] = mapped_column(Integer, default=0)

    move_kind: Mapped[str] = mapped_column(String(50), index=True)  # objection_handling, discovery, closing...
    goal: Mapped[str] = mapped_column(Text, default="")
    client_state_before: Mapped[str] = mapped_column(String(50), default="")
    client_state_after: Mapped[str] = mapped_column(String(50), default="")
    transcript_excerpt: Mapped[str] = mapped_column(Text)  # verbatim multi-turn text
    polarity: Mapped[str] = mapped_column(String(10), default="positive")  # positive | negative

    outcome_label: Mapped[str] = mapped_column(String(50), default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    human_rating: Mapped[float | None] = mapped_column(Float, nullable=True)

    # works_when / fails_when -> {client_state, stage, objection_type, product_type, prior_trust}
    conditions: Mapped[dict] = mapped_column(JSONB, default=dict)

    embedding = mapped_column(Vector(1536), nullable=True)
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)  # pending | approved | rejected

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
