"""SQLAlchemy models for the Performance & Expression layers.

- ExpressionModel: exact reusable phrases (winning) or phrases to avoid (anti),
  aggregated by similarity with a measured success rate.
- PatternClusterModel: groups of similar moves that COMPETE within the same
  (move_kind, context); retrieval prefers the highest success_rate.
- AgentStyleProfileModel: the learned personality / linguistic style of an agent.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class ExpressionModel(Base):
    __tablename__ = "expressions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    exact_phrase: Mapped[str] = mapped_column(Text)
    normalized_phrase: Mapped[str] = mapped_column(String(500), index=True)  # lowered, for dedup
    polarity: Mapped[str] = mapped_column(String(10), default="winning")  # winning | anti
    goal: Mapped[str] = mapped_column(Text, default="")
    contexts: Mapped[list] = mapped_column(JSONB, default=list)
    stage: Mapped[str] = mapped_column(String(50), default="")

    times_used: Mapped[int] = mapped_column(Integer, default=1)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_score: Mapped[float] = mapped_column(Float, default=0.0)
    conversation_ids: Mapped[list] = mapped_column(JSONB, default=list)
    agent_ids: Mapped[list] = mapped_column(JSONB, default=list)

    embedding = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PatternClusterModel(Base):
    __tablename__ = "pattern_clusters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    move_kind: Mapped[str] = mapped_column(String(50), index=True)
    polarity: Mapped[str] = mapped_column(String(10), default="positive")
    canonical_excerpt: Mapped[str] = mapped_column(Text, default="")
    centroid = mapped_column(Vector(1536), nullable=True)

    occurrence_count: Mapped[int] = mapped_column(Integer, default=0)
    positive_count: Mapped[int] = mapped_column(Integer, default=0)
    negative_count: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_score: Mapped[float] = mapped_column(Float, default=0.0)

    # aggregated works_when profile: {dimension: {value: count}}
    condition_profile: Mapped[dict] = mapped_column(JSONB, default=dict)
    rank: Mapped[int] = mapped_column(Integer, default=0)  # competitive position within move_kind

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AgentStyleProfileModel(Base):
    __tablename__ = "agent_style_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    # Inferred style attributes (0-1 unless noted)
    empathy_level: Mapped[float] = mapped_column(Float, default=0.0)
    question_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    formality: Mapped[float] = mapped_column(Float, default=0.0)
    avg_response_length: Mapped[float] = mapped_column(Float, default=0.0)  # words
    technical_level: Mapped[float] = mapped_column(Float, default=0.0)
    analogy_use: Mapped[float] = mapped_column(Float, default=0.0)
    example_use: Mapped[float] = mapped_column(Float, default=0.0)
    humor_use: Mapped[float] = mapped_column(Float, default=0.0)
    emotional_validation_freq: Mapped[float] = mapped_column(Float, default=0.0)
    sales_pressure: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_level: Mapped[float] = mapped_column(Float, default=0.0)

    microexpressions: Mapped[list] = mapped_column(JSONB, default=list)  # [{phrase, frequency}]
    linguistic_style: Mapped[dict] = mapped_column(JSONB, default=dict)

    computed_from_n_conversations: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
