"""SQLAlchemy models for agent-centric architecture."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .models import Base


class OrganizationModel(Base):
    """Lightweight tenant for data isolation. Business details live in the CRM."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    api_key_prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    capabilities: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # IANA tz name (e.g. "America/New_York") — grounds "current date/time" in
    # prompts to where this dealership actually is, instead of a fixed guess.
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York")
    # CRM integration (POST /crm/inbound callback): base URL + API key to call
    # back the CRM's /ai/tools/execute (e.g. tool="send_message"), and the
    # automation-agent id that call is attributed to on the CRM side.
    crm_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    crm_api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    crm_agent_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    agents: Mapped[list["OrganizationAgentModel"]] = relationship(back_populates="organization")


class AgentModel(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False, default="sales")
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    versions: Mapped[list["AgentVersionModel"]] = relationship(back_populates="agent")


class AgentVersionModel(Base):
    __tablename__ = "agent_versions"
    __table_args__ = (UniqueConstraint("agent_id", "version_number"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    capabilities: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    agent: Mapped["AgentModel"] = relationship(back_populates="versions")
    identity: Mapped["AgentIdentityModel | None"] = relationship(back_populates="agent_version", uselist=False)
    personality: Mapped["AgentPersonalityModel | None"] = relationship(back_populates="agent_version", uselist=False)
    rules: Mapped[list["AgentRuleModel"]] = relationship(back_populates="agent_version")
    strategies: Mapped[list["AgentStrategyModel"]] = relationship(back_populates="agent_version")
    prompt_templates: Mapped[list["AgentPromptTemplateModel"]] = relationship(back_populates="agent_version")
    voice: Mapped["AgentVoiceModel | None"] = relationship(back_populates="agent_version", uselist=False)
    assignments: Mapped[list["OrganizationAgentModel"]] = relationship(back_populates="agent_version")


class AgentIdentityModel(Base):
    __tablename__ = "agent_identity"
    __table_args__ = (UniqueConstraint("agent_version_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_versions.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    communication_style: Mapped[str] = mapped_column(Text, default="")
    compliance_notes: Mapped[str] = mapped_column(Text, default="")
    principles: Mapped[list] = mapped_column(JSONB, default=list)
    beliefs: Mapped[list] = mapped_column(JSONB, default=list)
    values_list: Mapped[list] = mapped_column(JSONB, default=list)
    words_never_use: Mapped[list] = mapped_column(JSONB, default=list)
    words_prefer: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    agent_version: Mapped["AgentVersionModel"] = relationship(back_populates="identity")


class AgentPersonalityModel(Base):
    __tablename__ = "agent_personality"
    __table_args__ = (UniqueConstraint("agent_version_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_versions.id", ondelete="CASCADE"), nullable=False)
    brand_traits: Mapped[list] = mapped_column(JSONB, default=list)
    brand_tone: Mapped[str] = mapped_column(String(255), default="Profesional y cercano")
    brand_instructions: Mapped[list] = mapped_column(JSONB, default=list)
    voice_traits: Mapped[list] = mapped_column(JSONB, default=list)
    voice_tone: Mapped[str] = mapped_column(String(255), default="Natural y conversacional")
    voice_instructions: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    agent_version: Mapped["AgentVersionModel"] = relationship(back_populates="personality")


class AgentRuleModel(Base):
    __tablename__ = "agent_rules"
    __table_args__ = (UniqueConstraint("agent_version_id", "rule_id", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_versions.id", ondelete="CASCADE"), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    action_params: Mapped[dict] = mapped_column(JSONB, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    agent_version: Mapped["AgentVersionModel"] = relationship(back_populates="rules")


class AgentStrategyModel(Base):
    __tablename__ = "agent_strategies"
    __table_args__ = (UniqueConstraint("agent_version_id", "strategy_type"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_versions.id", ondelete="CASCADE"), nullable=False)
    strategy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    triggers: Mapped[list] = mapped_column(JSONB, default=list)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    agent_version: Mapped["AgentVersionModel"] = relationship(back_populates="strategies")
    tactics: Mapped[list["AgentTacticModel"]] = relationship(back_populates="strategy", order_by="AgentTacticModel.position")


class AgentTacticModel(Base):
    __tablename__ = "agent_tactics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_strategies.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_instruction: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    strategy: Mapped["AgentStrategyModel"] = relationship(back_populates="tactics")


class AgentPromptTemplateModel(Base):
    __tablename__ = "agent_prompt_templates"
    __table_args__ = (UniqueConstraint("agent_version_id", "component", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_versions.id", ondelete="CASCADE"), nullable=False)
    component: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    agent_version: Mapped["AgentVersionModel"] = relationship(back_populates="prompt_templates")


class AgentVoiceModel(Base):
    __tablename__ = "agent_voice"
    __table_args__ = (UniqueConstraint("agent_version_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_versions.id", ondelete="CASCADE"), nullable=False)
    backchannels_es: Mapped[list] = mapped_column(JSONB, default=lambda: ["claro", "entiendo"])
    backchannels_en: Mapped[list] = mapped_column(JSONB, default=lambda: ["I see", "sure"])
    backchannel_probability: Mapped[float] = mapped_column(Float, default=0.3)
    enable_ssml: Mapped[bool] = mapped_column(Boolean, default=True)
    style_adaptations: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    agent_version: Mapped["AgentVersionModel"] = relationship(back_populates="voice")


class OrganizationAgentModel(Base):
    __tablename__ = "organization_agents"
    __table_args__ = (UniqueConstraint("organization_id", "agent_version_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    agent_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_versions.id", ondelete="CASCADE"), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization: Mapped["OrganizationModel"] = relationship(back_populates="agents")
    agent_version: Mapped["AgentVersionModel"] = relationship(back_populates="assignments")
