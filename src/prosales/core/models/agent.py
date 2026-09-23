"""Agent domain models."""

from uuid import UUID

from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    """Lightweight execution context that travels in pipeline state.

    Separates Organization (what to sell) from Agent (how to sell).
    Training/roleplay agents are Cognition-owned: ``organization_id`` is None.
    """

    organization_id: UUID | None = None
    organization_name: str = ""
    org_capabilities: list[str] = Field(default_factory=list)

    agent_id: UUID
    agent_version_id: UUID
    agent_name: str
    agent_type: str = "sales"  # sales, support, receptionist, customer_success
    agent_capabilities: list[str] = Field(default_factory=list)

    def has_capability(self, cap: str) -> bool:
        """Check if capability exists in either org or agent."""
        return cap in self.org_capabilities or cap in self.agent_capabilities

    def has_org_capability(self, cap: str) -> bool:
        """Check organization-level capability (knowledge, inventory, etc.)."""
        return cap in self.org_capabilities

    def has_agent_capability(self, cap: str) -> bool:
        """Check agent-level capability (voice, negotiation, etc.)."""
        return cap in self.agent_capabilities


class AgentIdentityConfig(BaseModel):
    """Identity config loaded by IdentityProvider."""

    name: str = ""
    description: str = ""
    communication_style: str = ""
    compliance_notes: str = ""


class AgentPersonalityConfig(BaseModel):
    """Personality config loaded by PersonalityProvider."""

    brand_traits: list[str] = Field(default_factory=list)
    brand_tone: str = "Profesional y cercano"
    brand_instructions: list[str] = Field(default_factory=list)
    voice_traits: list[str] = Field(default_factory=list)
    voice_tone: str = "Natural y conversacional"
    voice_instructions: list[str] = Field(default_factory=list)


class AgentRule(BaseModel):
    """A single agent rule."""

    rule_id: str
    version: int = 1
    intent: str | None = None
    sentiment: str | None = None
    urgency: str | None = None
    action_type: str
    action_params: dict = Field(default_factory=dict)
    priority: int = 5


class AgentStrategyTactic(BaseModel):
    """A tactic within a strategy."""

    name: str
    prompt_instruction: str
    position: int = 0


class AgentStrategy(BaseModel):
    """An agent strategy with its tactics."""

    strategy_type: str
    name: str
    description: str = ""
    triggers: list[dict] = Field(default_factory=list)
    priority: int = 5
    cooldown_seconds: int = 0
    tactics: list[AgentStrategyTactic] = Field(default_factory=list)


class AgentVoiceConfig(BaseModel):
    """Voice config loaded by VoiceProvider."""

    backchannels_es: list[str] = Field(default_factory=lambda: ["claro", "entiendo"])
    backchannels_en: list[str] = Field(default_factory=lambda: ["I see", "sure"])
    backchannel_probability: float = 0.3
    enable_ssml: bool = True
    style_adaptations: dict = Field(default_factory=dict)
