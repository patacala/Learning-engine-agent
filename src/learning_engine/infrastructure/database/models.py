import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ClientModel(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    memories: Mapped[list["ClientMemoryModel"]] = relationship(back_populates="client")
    conversations: Mapped[list["ConversationModel"]] = relationship(back_populates="client")


class ClientMemoryModel(Base):
    __tablename__ = "client_memories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    key: Mapped[str] = mapped_column(String(255))
    value: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source: Mapped[str] = mapped_column(String(50), default="conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    client: Mapped["ClientModel"] = relationship(back_populates="memories")


class ConversationModel(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    agent_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    stage: Mapped[str] = mapped_column(String(50), default="opening")
    language: Mapped[str] = mapped_column(String(10), default="es")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Channel this conversation flows through: "chat" (default), "voice", "roleplay".
    channel: Mapped[str] = mapped_column(String(20), default="chat", index=True)
    # Roleplay training only: the trainer's scenario prompt + who Cognition plays.
    scenario: Mapped[str | None] = mapped_column(Text, nullable=True)
    roleplay_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "agent" | "client"
    # Cognition-inferred outcome (not the CRM). See engines/qualification.
    outcome: Mapped[str] = mapped_column(String(50), default="open", index=True)
    outcome_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    # Roleplay training only: scenario-flavored outcome (see RoleplaySubOutcome),
    # mapped to the terminal `outcome` above so the learning pipeline is untouched.
    sub_outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)
    learned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    client: Mapped["ClientModel"] = relationship(back_populates="conversations")
    messages: Mapped[list["MessageModel"]] = relationship(back_populates="conversation")


class MessageModel(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(10), default="es")
    turn_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    conversation: Mapped["ConversationModel"] = relationship(back_populates="messages")


class KnowledgeDocumentModel(Base):
    """Source document: title/category/full original content/metadata, for
    display and re-chunking. Does NOT carry an embedding itself — retrieval
    happens at the KnowledgeChunkModel level (see engines/knowledge/chunker.py)."""

    __tablename__ = "knowledge_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100))
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    chunks: Mapped[list["KnowledgeChunkModel"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )


class KnowledgeChunkModel(Base):
    """One retrieval unit: a small, structure-aware slice of a
    KnowledgeDocumentModel's content, contextualized (Anthropic's Contextual
    Retrieval) and embedded individually. See engines/knowledge/chunker.py
    and engines/knowledge/contextualizer.py."""

    __tablename__ = "knowledge_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True
    )
    # Denormalized from the parent document at insert time so retrieval can
    # filter by org without a join on the hot path (matches the
    # organization_id-on-every-tenant-row convention used elsewhere).
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding = mapped_column(Vector(1536), nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped["KnowledgeDocumentModel"] = relationship(back_populates="chunks")


class EventModel(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class StrategyExecutionModel(Base):
    __tablename__ = "strategy_executions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    strategy_type: Mapped[str] = mapped_column(String(50))
    tactic_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    result: Mapped[str | None] = mapped_column(String(50), nullable=True)
    effectiveness: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PersonalityConfigModel(Base):
    __tablename__ = "personality_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_name: Mapped[str] = mapped_column(String(100), index=True)
    channel: Mapped[str] = mapped_column(String(50), default="voice")
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EpisodicMemoryModel(Base):
    __tablename__ = "episodic_memories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"), unique=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)

    # Temporal
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    message_count: Mapped[int] = mapped_column(Integer, default=0)

    # Observable facts
    dominant_intent: Mapped[str] = mapped_column(String(50), default="")
    dominant_sentiment: Mapped[str] = mapped_column(String(50), default="")
    sentiment_shifts: Mapped[int] = mapped_column(Integer, default=0)
    final_stage: Mapped[str] = mapped_column(String(50), default="")
    objections_detected: Mapped[list] = mapped_column(JSONB, default=list)
    strategies_used: Mapped[list] = mapped_column(JSONB, default=list)
    urgency_signals: Mapped[list] = mapped_column(JSONB, default=list)
    risk_signals: Mapped[list] = mapped_column(JSONB, default=list)

    # CRM feedback
    outcome: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    outcome_notes: Mapped[str] = mapped_column(Text, default="")

    # Embedding for future similarity search
    embedding = mapped_column(Vector(1536), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
