"""Schemas for CRM Management API — provisioning, agents, versions, config, knowledge, outbound."""

from uuid import UUID

from pydantic import BaseModel, Field


# --- Provisioning ---

class ProvisionOrganizationRequest(BaseModel):
    name: str
    capabilities_preset: str = "full"
    api_key: str | None = None


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    # Returned only on create/regenerate. Existing org responses never expose
    # plaintext API keys because only hashes are stored at rest.
    api_key: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    is_active: bool = True


class CrmIntegrationRequest(BaseModel):
    """Credentials this org's agent needs to call back the CRM's
    POST /ai/tools/execute (tool="send_message") once its pipeline finishes —
    see api/v1/endpoints/crm_inbound.py. Without these, /crm/inbound accepts
    the message, runs the pipeline, and silently skips the reply callback.
    """

    crm_base_url: str
    crm_api_key: str
    crm_agent_id: str


class BootstrapTenantRequest(BaseModel):
    """Full first-tenant setup — org + primary agent + strategy catalog.

    Used by POST /provisioning/bootstrap, the HTTP equivalent of
    scripts/bootstrap_tenant.py for environments without shell/SSH access
    (e.g. a Coolify deploy before the console is available).
    """

    name: str
    slug: str
    agent_type: str = "sales"
    capabilities_preset: str = "full"
    api_key: str | None = None
    strategy_topup: bool = True


class BootstrapTenantResponse(BaseModel):
    org_id: UUID
    slug: str
    agent_version_id: UUID
    api_key: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    created_org: bool
    created_agent: bool
    strategy_topup: dict | None = None


# --- Agents ---

class CreateAgentRequest(BaseModel):
    name: str
    slug: str
    agent_type: str = "sales"


class UpdateAgentRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class AgentResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    agent_type: str
    description: str = ""
    is_active: bool = True
    latest_version_id: UUID | None = None
    latest_version_number: int | None = None


# --- Versions ---

class CreateVersionRequest(BaseModel):
    capabilities: list[str] | None = None


class UpdateVersionRequest(BaseModel):
    is_published: bool | None = None
    capabilities: list[str] | None = None


class VersionResponse(BaseModel):
    id: UUID
    agent_id: UUID
    version_number: int
    is_published: bool
    capabilities: list[str] = Field(default_factory=list)


# --- Config payloads ---

class IdentityPayload(BaseModel):
    name: str
    description: str = ""
    communication_style: str = "consultive"
    compliance_notes: str = ""
    principles: list[str] = Field(default_factory=list)
    beliefs: list[str] = Field(default_factory=list)
    values: list[str] = Field(default_factory=list)
    words_never_use: list[str] = Field(default_factory=list)
    words_prefer: list[str] = Field(default_factory=list)


class PersonalityPayload(BaseModel):
    brand_traits: list[str] = Field(default_factory=list)
    brand_tone: str = "Professional and approachable"
    brand_instructions: list[str] = Field(default_factory=list)
    voice_traits: list[str] = Field(default_factory=list)
    voice_tone: str = "Natural and conversational"
    voice_instructions: list[str] = Field(default_factory=list)


class RulePayload(BaseModel):
    rule_id: str
    intent: str | None = None
    sentiment: str | None = None
    urgency: str | None = None
    action_type: str
    action_params: dict = Field(default_factory=dict)
    priority: int = 5


class TacticPayload(BaseModel):
    name: str
    prompt_instruction: str
    position: int = 0


class StrategyPayload(BaseModel):
    strategy_type: str
    name: str
    description: str = ""
    triggers: list[dict] = Field(default_factory=list)
    priority: int = 5
    cooldown_seconds: int = 0
    tactics: list[TacticPayload] = Field(default_factory=list)


class VoiceConfigPayload(BaseModel):
    backchannels_es: list[str] = Field(default_factory=lambda: ["claro", "entiendo"])
    backchannels_en: list[str] = Field(default_factory=lambda: ["I see", "sure"])
    backchannel_probability: float = 0.3
    enable_ssml: bool = True


# --- Brief → config ---

class BriefRequest(BaseModel):
    """A plain-language description of the business/agent that the extractor
    turns into the full config. The CRM collects this instead of making a
    non-technical user hand-edit strategy_type/cooldown/tactics."""

    brief: str


class BriefResponse(BaseModel):
    """What the brief was transformed into — persisted AND returned so the CRM
    can show a human-readable, read-only summary (and still allow editing the
    underlying payloads via the existing PUT endpoints)."""

    identity: IdentityPayload
    personality: PersonalityPayload
    rules: list[RulePayload] = Field(default_factory=list)
    strategies: list[StrategyPayload] = Field(default_factory=list)


# --- Assignments ---

class AssignAgentRequest(BaseModel):
    agent_version_id: UUID
    is_primary: bool = True


class AssignmentResponse(BaseModel):
    id: UUID
    organization_id: UUID
    agent_version_id: UUID
    is_primary: bool
    is_active: bool


# --- Knowledge ---

class IndexDocumentRequest(BaseModel):
    title: str
    content: str
    category: str
    metadata: dict | None = None


class KnowledgeDocumentResponse(BaseModel):
    id: UUID
    title: str
    category: str
    created_at: str | None = None


# --- Verified outcome (CRM → learning loop) ---

class OutcomeUpdateRequest(BaseModel):
    """A verified outcome pushed by the CRM (e.g. a completed payment) so the
    learning loop re-scores the conversation's moves with real ground truth
    instead of only Cognition's inferred outcome."""

    outcome: str
    outcome_notes: str = ""


# --- Outbound ---

class OutboundCallRequest(BaseModel):
    agent_version_id: UUID
    to_number: str
    from_number: str
    metadata: dict | None = None


class OutboundCallResponse(BaseModel):
    call_id: str
    status: str
