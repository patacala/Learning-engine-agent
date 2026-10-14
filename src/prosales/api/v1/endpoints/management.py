"""Management endpoints — org-scoped CRUD for agents, versions, config, knowledge, outbound.

All endpoints require Bearer org_api_key → resolves OrganizationModel → scopes to that org.
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from prosales.api.v1.dependencies import (
    current_db_session,
    get_authenticated_org,
    get_redis_cache,
)
from prosales.api.v1.schemas.management import (
    AgentResponse,
    AssignAgentRequest,
    AssignmentResponse,
    BriefRequest,
    BriefResponse,
    CreateAgentRequest,
    CreateVersionRequest,
    CrmIntegrationRequest,
    IdentityPayload,
    IndexDocumentRequest,
    KnowledgeDocumentResponse,
    OutboundCallRequest,
    OutboundCallResponse,
    OutcomeUpdateRequest,
    PersonalityPayload,
    RulePayload,
    StrategyPayload,
    UpdateAgentRequest,
    UpdateVersionRequest,
    VersionResponse,
    VoiceConfigPayload,
)
from prosales.api.v1.endpoints.episode import _propagate_outcome_to_clusters
from prosales.channels.voice.outbound import OutboundCallService
from prosales.config import settings
from prosales.core.models.qualification_schema import QualificationField, default_schema
from prosales.di.container import create_llm_provider
from prosales.engines.knowledge.indexer import index_document
from prosales.services.live_learning import approve_moves_for_conversation, run_live_learning
from prosales.services.brief_extractor import (
    BriefExtractor,
    merge_identity,
    merge_personality,
    merge_rules,
    merge_strategies,
)
from prosales.infrastructure.agent.resolver import invalidate_agent_context, invalidate_agent_version_cache
from prosales.infrastructure.agent.templates import assign_agent_to_org, create_agent_from_template
from prosales.infrastructure.cache.redis import RedisCache
from prosales.infrastructure.database.connection import async_session_factory
from prosales.infrastructure.database.models import ConversationModel, KnowledgeDocumentModel
from prosales.infrastructure.database.repositories.episodic import SQLEpisodicRepository
from prosales.infrastructure.database.models_agent import (
    AgentIdentityModel,
    AgentModel,
    AgentPersonalityModel,
    AgentQualificationSchemaModel,
    AgentRuleModel,
    AgentStrategyModel,
    AgentTacticModel,
    AgentVersionModel,
    AgentVoiceModel,
    OrganizationAgentModel,
    OrganizationModel,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/management", tags=["management"])


# --- Helpers ---

async def _get_session_from_org(_org: OrganizationModel) -> AsyncSession:
    """Async session of the current request. inspect(org).session is the sync
    Session and raises MissingGreenlet as soon as a query runs."""
    return current_db_session()


async def _verify_agent_belongs_to_org(session: AsyncSession, agent_id: uuid.UUID, org_id: uuid.UUID) -> AgentModel:
    """Verify agent is assigned to org via organization_agents."""
    stmt = (
        select(AgentModel)
        .join(AgentVersionModel, AgentVersionModel.agent_id == AgentModel.id)
        .join(OrganizationAgentModel, OrganizationAgentModel.agent_version_id == AgentVersionModel.id)
        .where(
            AgentModel.id == agent_id,
            OrganizationAgentModel.organization_id == org_id,
        )
    )
    result = await session.execute(stmt)
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found in this organization")
    return agent


async def _verify_version_belongs_to_org(session: AsyncSession, version_id: uuid.UUID, org_id: uuid.UUID) -> AgentVersionModel:
    """Verify version belongs to an agent assigned to this org."""
    stmt = (
        select(AgentVersionModel)
        .join(OrganizationAgentModel, OrganizationAgentModel.agent_version_id == AgentVersionModel.id)
        .where(
            AgentVersionModel.id == version_id,
            OrganizationAgentModel.organization_id == org_id,
        )
    )
    result = await session.execute(stmt)
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found in this organization")
    return version


# --- Config persist helpers (shared by the PUT handlers and from-brief) ---
# Each is bulk-replace: delete the version's existing rows, insert from payload.

async def _persist_identity(session: AsyncSession, version_id: uuid.UUID, body: IdentityPayload) -> None:
    await session.execute(
        delete(AgentIdentityModel).where(AgentIdentityModel.agent_version_id == version_id)
    )
    session.add(AgentIdentityModel(
        agent_version_id=version_id,
        name=body.name,
        description=body.description,
        communication_style=body.communication_style,
        compliance_notes=body.compliance_notes,
        principles=body.principles,
        beliefs=body.beliefs,
        values_list=body.values,
        words_never_use=body.words_never_use,
        words_prefer=body.words_prefer,
    ))
    await session.flush()


async def _persist_personality(session: AsyncSession, version_id: uuid.UUID, body: PersonalityPayload) -> None:
    await session.execute(
        delete(AgentPersonalityModel).where(AgentPersonalityModel.agent_version_id == version_id)
    )
    session.add(AgentPersonalityModel(
        agent_version_id=version_id,
        brand_traits=body.brand_traits,
        brand_tone=body.brand_tone,
        brand_instructions=body.brand_instructions,
        voice_traits=body.voice_traits,
        voice_tone=body.voice_tone,
        voice_instructions=body.voice_instructions,
    ))
    await session.flush()


async def _persist_rules(session: AsyncSession, version_id: uuid.UUID, body: list[RulePayload]) -> None:
    await session.execute(
        delete(AgentRuleModel).where(AgentRuleModel.agent_version_id == version_id)
    )
    for rule in body:
        session.add(AgentRuleModel(
            agent_version_id=version_id,
            rule_id=rule.rule_id,
            intent=rule.intent,
            sentiment=rule.sentiment,
            urgency=rule.urgency,
            action_type=rule.action_type,
            action_params=rule.action_params,
            priority=rule.priority,
        ))
    await session.flush()


async def _persist_strategies(session: AsyncSession, version_id: uuid.UUID, body: list[StrategyPayload]) -> None:
    # Delete existing (tactics first, then strategies).
    existing_ids = (
        select(AgentStrategyModel.id).where(AgentStrategyModel.agent_version_id == version_id)
    )
    await session.execute(delete(AgentTacticModel).where(AgentTacticModel.strategy_id.in_(existing_ids)))
    await session.execute(delete(AgentStrategyModel).where(AgentStrategyModel.agent_version_id == version_id))

    for strat in body:
        new_strat = AgentStrategyModel(
            agent_version_id=version_id,
            strategy_type=strat.strategy_type,
            name=strat.name,
            description=strat.description,
            triggers=strat.triggers,
            priority=strat.priority,
            cooldown_seconds=strat.cooldown_seconds,
        )
        session.add(new_strat)
        await session.flush()
        for tactic in strat.tactics:
            session.add(AgentTacticModel(
                strategy_id=new_strat.id,
                name=tactic.name,
                prompt_instruction=tactic.prompt_instruction,
                position=tactic.position,
            ))
    await session.flush()


async def _persist_qualification(
    session: AsyncSession, version_id: uuid.UUID, fields: list[QualificationField]
) -> None:
    await session.execute(
        delete(AgentQualificationSchemaModel).where(
            AgentQualificationSchemaModel.agent_version_id == version_id
        )
    )
    session.add(AgentQualificationSchemaModel(
        agent_version_id=version_id,
        fields=[f.model_dump() for f in fields],
    ))
    await session.flush()


# --- Config readers (ORM → payloads) for additive brief merge ---
# Return None/[] when absent so the brief merge treats a not-yet-seeded version
# as "no base" (merge == brief alone), keeping agents created without a template
# working exactly as before.

async def _read_identity_payload(session: AsyncSession, version_id: uuid.UUID) -> IdentityPayload | None:
    row = (await session.execute(
        select(AgentIdentityModel).where(AgentIdentityModel.agent_version_id == version_id)
    )).scalar_one_or_none()
    if row is None:
        return None
    return IdentityPayload(
        name=row.name, description=row.description,
        communication_style=row.communication_style, compliance_notes=row.compliance_notes,
        principles=row.principles or [], beliefs=row.beliefs or [], values=row.values_list or [],
        words_never_use=row.words_never_use or [], words_prefer=row.words_prefer or [],
    )


async def _read_personality_payload(session: AsyncSession, version_id: uuid.UUID) -> PersonalityPayload | None:
    row = (await session.execute(
        select(AgentPersonalityModel).where(AgentPersonalityModel.agent_version_id == version_id)
    )).scalar_one_or_none()
    if row is None:
        return None
    return PersonalityPayload(
        brand_traits=row.brand_traits or [], brand_tone=row.brand_tone,
        brand_instructions=row.brand_instructions or [], voice_traits=row.voice_traits or [],
        voice_tone=row.voice_tone, voice_instructions=row.voice_instructions or [],
    )


async def _read_rules_payload(session: AsyncSession, version_id: uuid.UUID) -> list[RulePayload]:
    rows = (await session.execute(
        select(AgentRuleModel).where(AgentRuleModel.agent_version_id == version_id)
    )).scalars().all()
    return [
        RulePayload(
            rule_id=r.rule_id, intent=r.intent, sentiment=r.sentiment, urgency=r.urgency,
            action_type=r.action_type, action_params=r.action_params or {}, priority=r.priority,
        )
        for r in rows
    ]


async def _read_strategies_payload(session: AsyncSession, version_id: uuid.UUID) -> list[StrategyPayload]:
    rows = (await session.execute(
        select(AgentStrategyModel)
        .options(selectinload(AgentStrategyModel.tactics))
        .where(AgentStrategyModel.agent_version_id == version_id)
    )).scalars().all()
    return [
        StrategyPayload(
            strategy_type=s.strategy_type, name=s.name, description=s.description or "",
            triggers=s.triggers or [], priority=s.priority, cooldown_seconds=s.cooldown_seconds,
            tactics=[
                {"name": t.name, "prompt_instruction": t.prompt_instruction, "position": t.position}
                for t in s.tactics
            ],
        )
        for s in rows
    ]


def _agent_response(agent: AgentModel, latest_version: AgentVersionModel | None = None) -> AgentResponse:
    return AgentResponse(
        id=agent.id,
        name=agent.name,
        slug=agent.slug,
        agent_type=agent.agent_type,
        description=agent.description or "",
        is_active=agent.is_active,
        latest_version_id=latest_version.id if latest_version else None,
        latest_version_number=latest_version.version_number if latest_version else None,
    )


def _version_response(version: AgentVersionModel) -> VersionResponse:
    return VersionResponse(
        id=version.id,
        agent_id=version.agent_id,
        version_number=version.version_number,
        is_published=version.is_published,
        capabilities=version.capabilities or [],
    )


# ==================== CRM INTEGRATION ====================

@router.put("/organization/crm-integration")
async def set_crm_integration(
    body: CrmIntegrationRequest,
    org: OrganizationModel = Depends(get_authenticated_org),
) -> CrmIntegrationRequest:
    """Set the credentials this org's agent uses to call back the CRM's
    send_message tool after replying (see crm_inbound.py). Without this,
    /crm/inbound processes messages but silently can't deliver the reply —
    see crm-integration-2026-09 memory for how this gap was found.
    """
    session = await _get_session_from_org(org)
    org.crm_base_url = body.crm_base_url
    org.crm_api_key = body.crm_api_key
    org.crm_agent_id = body.crm_agent_id
    await session.flush()
    return body


# ==================== AGENTS ====================

@router.post("/agents")
async def create_agent(
    body: CreateAgentRequest,
    org: OrganizationModel = Depends(get_authenticated_org),
) -> AgentResponse:
    """Create agent from template + assign to org."""
    session = await _get_session_from_org(org)
    agent, version = await create_agent_from_template(
        session, name=body.name, slug=body.slug, agent_type=body.agent_type,
    )
    await assign_agent_to_org(session, org.id, version.id, is_primary=False)
    return _agent_response(agent, version)


@router.get("/agents")
async def list_agents(
    org: OrganizationModel = Depends(get_authenticated_org),
) -> list[AgentResponse]:
    """List agents assigned to this org."""
    session = await _get_session_from_org(org)
    stmt = (
        select(AgentModel, AgentVersionModel)
        .join(AgentVersionModel, AgentVersionModel.agent_id == AgentModel.id)
        .join(OrganizationAgentModel, OrganizationAgentModel.agent_version_id == AgentVersionModel.id)
        .where(OrganizationAgentModel.organization_id == org.id)
        .order_by(AgentModel.name)
    )
    result = await session.execute(stmt)
    rows = result.all()

    # Group by agent, pick latest version
    agents_map: dict[uuid.UUID, tuple[AgentModel, AgentVersionModel]] = {}
    for agent, version in rows:
        existing = agents_map.get(agent.id)
        if existing is None or version.version_number > existing[1].version_number:
            agents_map[agent.id] = (agent, version)

    return [_agent_response(a, v) for a, v in agents_map.values()]


@router.get("/agents/{agent_id}")
async def get_agent(
    agent_id: uuid.UUID,
    org: OrganizationModel = Depends(get_authenticated_org),
) -> AgentResponse:
    """Get agent detail with latest version."""
    session = await _get_session_from_org(org)
    agent = await _verify_agent_belongs_to_org(session, agent_id, org.id)

    stmt = (
        select(AgentVersionModel)
        .where(AgentVersionModel.agent_id == agent_id)
        .order_by(AgentVersionModel.version_number.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    latest = result.scalar_one_or_none()
    return _agent_response(agent, latest)


@router.patch("/agents/{agent_id}")
async def update_agent(
    agent_id: uuid.UUID,
    body: UpdateAgentRequest,
    org: OrganizationModel = Depends(get_authenticated_org),
) -> AgentResponse:
    """Partial update of agent fields."""
    session = await _get_session_from_org(org)
    agent = await _verify_agent_belongs_to_org(session, agent_id, org.id)

    # Re-fetch the actual agent object (the join may return a different instance)
    stmt = select(AgentModel).where(AgentModel.id == agent_id)
    result = await session.execute(stmt)
    agent = result.scalar_one()

    if body.name is not None:
        agent.name = body.name
    if body.description is not None:
        agent.description = body.description
    if body.is_active is not None:
        agent.is_active = body.is_active
    agent.updated_at = datetime.now(timezone.utc)
    await session.flush()

    stmt = (
        select(AgentVersionModel)
        .where(AgentVersionModel.agent_id == agent_id)
        .order_by(AgentVersionModel.version_number.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    latest = result.scalar_one_or_none()
    return _agent_response(agent, latest)


# ==================== VERSIONS ====================

@router.post("/agents/{agent_id}/versions")
async def create_version(
    agent_id: uuid.UUID,
    body: CreateVersionRequest,
    org: OrganizationModel = Depends(get_authenticated_org),
    cache: RedisCache = Depends(get_redis_cache),
) -> VersionResponse:
    """Create new version as deep copy of latest. New version is unpublished."""
    session = await _get_session_from_org(org)
    await _verify_agent_belongs_to_org(session, agent_id, org.id)

    # Find latest version
    stmt = (
        select(AgentVersionModel)
        .where(AgentVersionModel.agent_id == agent_id)
        .order_by(AgentVersionModel.version_number.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    latest = result.scalar_one_or_none()

    new_number = (latest.version_number + 1) if latest else 1
    new_version = AgentVersionModel(
        id=uuid.uuid4(),
        agent_id=agent_id,
        version_number=new_number,
        is_published=False,
        capabilities=body.capabilities if body.capabilities is not None else (latest.capabilities if latest else []),
    )
    session.add(new_version)
    await session.flush()

    # Deep copy config from latest version
    if latest:
        await _deep_copy_version_config(session, latest.id, new_version.id)

    return _version_response(new_version)


async def _deep_copy_version_config(session: AsyncSession, src_id: uuid.UUID, dst_id: uuid.UUID) -> None:
    """Copy identity, personality, rules, strategies+tactics, voice from src to dst version."""
    # Identity
    stmt = select(AgentIdentityModel).where(AgentIdentityModel.agent_version_id == src_id)
    result = await session.execute(stmt)
    src_identity = result.scalar_one_or_none()
    if src_identity:
        session.add(AgentIdentityModel(
            agent_version_id=dst_id,
            name=src_identity.name,
            description=src_identity.description,
            communication_style=src_identity.communication_style,
            compliance_notes=src_identity.compliance_notes,
            principles=src_identity.principles,
            beliefs=src_identity.beliefs,
            values_list=src_identity.values_list,
            words_never_use=src_identity.words_never_use,
            words_prefer=src_identity.words_prefer,
        ))

    # Personality
    stmt = select(AgentPersonalityModel).where(AgentPersonalityModel.agent_version_id == src_id)
    result = await session.execute(stmt)
    src_personality = result.scalar_one_or_none()
    if src_personality:
        session.add(AgentPersonalityModel(
            agent_version_id=dst_id,
            brand_traits=src_personality.brand_traits,
            brand_tone=src_personality.brand_tone,
            brand_instructions=src_personality.brand_instructions,
            voice_traits=src_personality.voice_traits,
            voice_tone=src_personality.voice_tone,
            voice_instructions=src_personality.voice_instructions,
        ))

    # Rules
    stmt = select(AgentRuleModel).where(AgentRuleModel.agent_version_id == src_id)
    result = await session.execute(stmt)
    for rule in result.scalars().all():
        session.add(AgentRuleModel(
            agent_version_id=dst_id,
            rule_id=rule.rule_id,
            intent=rule.intent,
            sentiment=rule.sentiment,
            urgency=rule.urgency,
            action_type=rule.action_type,
            action_params=rule.action_params,
            priority=rule.priority,
        ))

    # Strategies + tactics
    stmt = (
        select(AgentStrategyModel)
        .options(selectinload(AgentStrategyModel.tactics))
        .where(AgentStrategyModel.agent_version_id == src_id)
    )
    result = await session.execute(stmt)
    for strat in result.scalars().all():
        new_strat = AgentStrategyModel(
            agent_version_id=dst_id,
            strategy_type=strat.strategy_type,
            name=strat.name,
            description=strat.description,
            triggers=strat.triggers,
            priority=strat.priority,
            cooldown_seconds=strat.cooldown_seconds,
        )
        session.add(new_strat)
        await session.flush()
        for tactic in strat.tactics:
            session.add(AgentTacticModel(
                strategy_id=new_strat.id,
                name=tactic.name,
                prompt_instruction=tactic.prompt_instruction,
                position=tactic.position,
            ))

    # Voice
    stmt = select(AgentVoiceModel).where(AgentVoiceModel.agent_version_id == src_id)
    result = await session.execute(stmt)
    src_voice = result.scalar_one_or_none()
    if src_voice:
        session.add(AgentVoiceModel(
            agent_version_id=dst_id,
            backchannels_es=src_voice.backchannels_es,
            backchannels_en=src_voice.backchannels_en,
            backchannel_probability=src_voice.backchannel_probability,
            enable_ssml=src_voice.enable_ssml,
            style_adaptations=src_voice.style_adaptations,
        ))

    await session.flush()


@router.patch("/versions/{version_id}")
async def update_version(
    version_id: uuid.UUID,
    body: UpdateVersionRequest,
    org: OrganizationModel = Depends(get_authenticated_org),
    cache: RedisCache = Depends(get_redis_cache),
) -> VersionResponse:
    """Publish/unpublish a version, update capabilities."""
    session = await _get_session_from_org(org)
    version = await _verify_version_belongs_to_org(session, version_id, org.id)

    # Re-fetch for mutation
    stmt = select(AgentVersionModel).where(AgentVersionModel.id == version_id)
    result = await session.execute(stmt)
    version = result.scalar_one()

    if body.is_published is not None:
        version.is_published = body.is_published
    if body.capabilities is not None:
        version.capabilities = body.capabilities
    await session.flush()

    await invalidate_agent_version_cache(cache, version_id)
    return _version_response(version)


# ==================== CONFIG PER VERSION ====================

# --- Identity ---

@router.get("/versions/{version_id}/identity")
async def get_identity(
    version_id: uuid.UUID,
    org: OrganizationModel = Depends(get_authenticated_org),
) -> IdentityPayload:
    session = await _get_session_from_org(org)
    await _verify_version_belongs_to_org(session, version_id, org.id)

    stmt = select(AgentIdentityModel).where(AgentIdentityModel.agent_version_id == version_id)
    result = await session.execute(stmt)
    identity = result.scalar_one_or_none()
    if identity is None:
        raise HTTPException(status_code=404, detail="Identity not found")

    return IdentityPayload(
        name=identity.name,
        description=identity.description,
        communication_style=identity.communication_style,
        compliance_notes=identity.compliance_notes,
        principles=identity.principles or [],
        beliefs=identity.beliefs or [],
        values=identity.values_list or [],
        words_never_use=identity.words_never_use or [],
        words_prefer=identity.words_prefer or [],
    )


@router.put("/versions/{version_id}/identity")
async def put_identity(
    version_id: uuid.UUID,
    body: IdentityPayload,
    org: OrganizationModel = Depends(get_authenticated_org),
    cache: RedisCache = Depends(get_redis_cache),
) -> IdentityPayload:
    session = await _get_session_from_org(org)
    await _verify_version_belongs_to_org(session, version_id, org.id)
    await _persist_identity(session, version_id, body)
    await invalidate_agent_version_cache(cache, version_id)
    return body


# --- Brief → full config (identity + personality + rules + strategies) ---

@router.post("/versions/{version_id}/from-brief")
async def configure_from_brief(
    version_id: uuid.UUID,
    body: BriefRequest,
    org: OrganizationModel = Depends(get_authenticated_org),
    cache: RedisCache = Depends(get_redis_cache),
) -> BriefResponse:
    """Enrich the agent's config from a plain-language brief, so a non-technical
    user never hand-edits strategy_type/cooldown/tactics.

    ADDITIVE: the brief merges ON TOP of the existing (type-template-seeded)
    config — list fields are unioned, scalars (name/tone/style) are kept from the
    template — so a weak brief ("an agent that answers calls") never degrades the
    agent. The per-section PUT endpoints remain the way to override any field.
    Returns the MERGED config for a read-only summary in the CRM."""
    session = await _get_session_from_org(org)
    version = await _verify_version_belongs_to_org(session, version_id, org.id)

    extractor = BriefExtractor(create_llm_provider())
    generated = await extractor.extract(body.brief)

    # Merge onto the current config (if any) so the template baseline survives.
    base_identity = await _read_identity_payload(session, version_id)
    base_personality = await _read_personality_payload(session, version_id)
    base_rules = await _read_rules_payload(session, version_id)
    base_strategies = await _read_strategies_payload(session, version_id)

    merged = BriefResponse(
        identity=merge_identity(base_identity, generated.identity) if base_identity else generated.identity,
        personality=merge_personality(base_personality, generated.personality) if base_personality else generated.personality,
        rules=merge_rules(base_rules, generated.rules),
        strategies=merge_strategies(base_strategies, generated.strategies),
    )

    await _persist_identity(session, version_id, merged.identity)
    await _persist_personality(session, version_id, merged.personality)
    await _persist_rules(session, version_id, merged.rules)
    await _persist_strategies(session, version_id, merged.strategies)
    # Seed a default qualification schema so the Qualification tab is pre-filled;
    # the user refines it there. (Only when one isn't configured yet.)
    existing_qual = (
        await session.execute(
            select(AgentQualificationSchemaModel.id).where(
                AgentQualificationSchemaModel.agent_version_id == version_id
            )
        )
    ).scalar_one_or_none()
    if existing_qual is None:
        await _persist_qualification(session, version_id, default_schema().fields)
    version.brief = body.brief  # keep the source for re-generation/editing
    await session.flush()

    await invalidate_agent_version_cache(cache, version_id)
    return merged


# --- Qualification schema (what the agent captures from a lead) ---

@router.get("/versions/{version_id}/qualification")
async def get_qualification(
    version_id: uuid.UUID,
    org: OrganizationModel = Depends(get_authenticated_org),
) -> list[QualificationField]:
    session = await _get_session_from_org(org)
    await _verify_version_belongs_to_org(session, version_id, org.id)

    stmt = select(AgentQualificationSchemaModel).where(
        AgentQualificationSchemaModel.agent_version_id == version_id
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None or not row.fields:
        # No custom schema yet → return the default so the UI shows a starting point.
        return default_schema().fields
    return [QualificationField(**f) for f in row.fields]


@router.put("/versions/{version_id}/qualification")
async def put_qualification(
    version_id: uuid.UUID,
    body: list[QualificationField],
    org: OrganizationModel = Depends(get_authenticated_org),
    cache: RedisCache = Depends(get_redis_cache),
) -> list[QualificationField]:
    session = await _get_session_from_org(org)
    await _verify_version_belongs_to_org(session, version_id, org.id)
    await _persist_qualification(session, version_id, body)
    await invalidate_agent_version_cache(cache, version_id)
    return body


# --- Personality ---

@router.get("/versions/{version_id}/personality")
async def get_personality(
    version_id: uuid.UUID,
    org: OrganizationModel = Depends(get_authenticated_org),
) -> PersonalityPayload:
    session = await _get_session_from_org(org)
    await _verify_version_belongs_to_org(session, version_id, org.id)

    stmt = select(AgentPersonalityModel).where(AgentPersonalityModel.agent_version_id == version_id)
    result = await session.execute(stmt)
    personality = result.scalar_one_or_none()
    if personality is None:
        raise HTTPException(status_code=404, detail="Personality not found")

    return PersonalityPayload(
        brand_traits=personality.brand_traits or [],
        brand_tone=personality.brand_tone,
        brand_instructions=personality.brand_instructions or [],
        voice_traits=personality.voice_traits or [],
        voice_tone=personality.voice_tone,
        voice_instructions=personality.voice_instructions or [],
    )


@router.put("/versions/{version_id}/personality")
async def put_personality(
    version_id: uuid.UUID,
    body: PersonalityPayload,
    org: OrganizationModel = Depends(get_authenticated_org),
    cache: RedisCache = Depends(get_redis_cache),
) -> PersonalityPayload:
    session = await _get_session_from_org(org)
    await _verify_version_belongs_to_org(session, version_id, org.id)
    await _persist_personality(session, version_id, body)
    await invalidate_agent_version_cache(cache, version_id)
    return body


# --- Rules (bulk replace) ---

@router.get("/versions/{version_id}/rules")
async def get_rules(
    version_id: uuid.UUID,
    org: OrganizationModel = Depends(get_authenticated_org),
) -> list[RulePayload]:
    session = await _get_session_from_org(org)
    await _verify_version_belongs_to_org(session, version_id, org.id)

    stmt = select(AgentRuleModel).where(AgentRuleModel.agent_version_id == version_id)
    result = await session.execute(stmt)
    return [
        RulePayload(
            rule_id=r.rule_id,
            intent=r.intent,
            sentiment=r.sentiment,
            urgency=r.urgency,
            action_type=r.action_type,
            action_params=r.action_params or {},
            priority=r.priority,
        )
        for r in result.scalars().all()
    ]


@router.put("/versions/{version_id}/rules")
async def put_rules(
    version_id: uuid.UUID,
    body: list[RulePayload],
    org: OrganizationModel = Depends(get_authenticated_org),
    cache: RedisCache = Depends(get_redis_cache),
) -> list[RulePayload]:
    session = await _get_session_from_org(org)
    await _verify_version_belongs_to_org(session, version_id, org.id)
    await _persist_rules(session, version_id, body)
    await invalidate_agent_version_cache(cache, version_id)
    return body


# --- Strategies (bulk replace, tactics cascade) ---

@router.get("/versions/{version_id}/strategies")
async def get_strategies(
    version_id: uuid.UUID,
    org: OrganizationModel = Depends(get_authenticated_org),
) -> list[StrategyPayload]:
    session = await _get_session_from_org(org)
    await _verify_version_belongs_to_org(session, version_id, org.id)

    stmt = (
        select(AgentStrategyModel)
        .options(selectinload(AgentStrategyModel.tactics))
        .where(AgentStrategyModel.agent_version_id == version_id)
    )
    result = await session.execute(stmt)
    return [
        StrategyPayload(
            strategy_type=s.strategy_type,
            name=s.name,
            description=s.description or "",
            triggers=s.triggers or [],
            priority=s.priority,
            cooldown_seconds=s.cooldown_seconds,
            tactics=[
                {"name": t.name, "prompt_instruction": t.prompt_instruction, "position": t.position}
                for t in s.tactics
            ],
        )
        for s in result.scalars().all()
    ]


@router.put("/versions/{version_id}/strategies")
async def put_strategies(
    version_id: uuid.UUID,
    body: list[StrategyPayload],
    org: OrganizationModel = Depends(get_authenticated_org),
    cache: RedisCache = Depends(get_redis_cache),
) -> list[StrategyPayload]:
    session = await _get_session_from_org(org)
    await _verify_version_belongs_to_org(session, version_id, org.id)
    await _persist_strategies(session, version_id, body)
    await invalidate_agent_version_cache(cache, version_id)
    return body


# --- Voice ---

@router.get("/versions/{version_id}/voice")
async def get_voice(
    version_id: uuid.UUID,
    org: OrganizationModel = Depends(get_authenticated_org),
) -> VoiceConfigPayload:
    session = await _get_session_from_org(org)
    await _verify_version_belongs_to_org(session, version_id, org.id)

    stmt = select(AgentVoiceModel).where(AgentVoiceModel.agent_version_id == version_id)
    result = await session.execute(stmt)
    voice = result.scalar_one_or_none()
    if voice is None:
        raise HTTPException(status_code=404, detail="Voice config not found")

    return VoiceConfigPayload(
        backchannels_es=voice.backchannels_es or [],
        backchannels_en=voice.backchannels_en or [],
        backchannel_probability=voice.backchannel_probability,
        enable_ssml=voice.enable_ssml,
    )


@router.put("/versions/{version_id}/voice")
async def put_voice(
    version_id: uuid.UUID,
    body: VoiceConfigPayload,
    org: OrganizationModel = Depends(get_authenticated_org),
    cache: RedisCache = Depends(get_redis_cache),
) -> VoiceConfigPayload:
    session = await _get_session_from_org(org)
    await _verify_version_belongs_to_org(session, version_id, org.id)

    await session.execute(
        delete(AgentVoiceModel).where(AgentVoiceModel.agent_version_id == version_id)
    )
    session.add(AgentVoiceModel(
        agent_version_id=version_id,
        backchannels_es=body.backchannels_es,
        backchannels_en=body.backchannels_en,
        backchannel_probability=body.backchannel_probability,
        enable_ssml=body.enable_ssml,
    ))
    await session.flush()
    await invalidate_agent_version_cache(cache, version_id)
    return body


# ==================== ASSIGNMENTS ====================

@router.post("/agents/{agent_id}/assign")
async def assign_agent(
    agent_id: uuid.UUID,
    body: AssignAgentRequest,
    org: OrganizationModel = Depends(get_authenticated_org),
) -> AssignmentResponse:
    """Assign an agent version to this org."""
    session = await _get_session_from_org(org)

    # Verify version belongs to this agent
    stmt = select(AgentVersionModel).where(
        AgentVersionModel.id == body.agent_version_id,
        AgentVersionModel.agent_id == agent_id,
    )
    result = await session.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Version not found for this agent")

    assignment = await assign_agent_to_org(session, org.id, body.agent_version_id, body.is_primary)
    return AssignmentResponse(
        id=assignment.id,
        organization_id=org.id,
        agent_version_id=body.agent_version_id,
        is_primary=assignment.is_primary,
        is_active=assignment.is_active,
    )


@router.delete("/assignments/{assignment_id}", status_code=204)
async def unassign_agent(
    assignment_id: uuid.UUID,
    org: OrganizationModel = Depends(get_authenticated_org),
    cache: RedisCache = Depends(get_redis_cache),
):
    """Remove an agent assignment from this org."""
    session = await _get_session_from_org(org)
    stmt = select(OrganizationAgentModel).where(
        OrganizationAgentModel.id == assignment_id,
        OrganizationAgentModel.organization_id == org.id,
    )
    result = await session.execute(stmt)
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")

    await session.delete(assignment)
    await session.flush()

    # The org-level agent context cache is keyed by plaintext API key (only
    # available transiently on the request, since only the hash is stored).
    # Without this, a removed assignment keeps serving the old agent for up
    # to CACHE_TTL.
    auth_api_key = getattr(org, "_auth_api_key", None)
    if auth_api_key:
        await invalidate_agent_context(cache, auth_api_key)


# ==================== KNOWLEDGE ====================

@router.post("/knowledge")
async def index_knowledge(
    body: IndexDocumentRequest,
    org: OrganizationModel = Depends(get_authenticated_org),
) -> KnowledgeDocumentResponse:
    """Index a knowledge document scoped to this org."""
    # Auth already read the org. Commit that transaction before contextual
    # retrieval: a long file holds the request open for the LLM calls, and an
    # idle-in-transaction timeout kills only that one entry.
    request_session = await _get_session_from_org(org)
    await request_session.commit()

    doc = await index_document(
        title=body.title,
        content=body.content,
        category=body.category,
        organization_id=org.id,
        metadata=body.metadata,
    )
    return KnowledgeDocumentResponse(
        id=doc.id,
        title=doc.title,
        category=doc.category,
        created_at=str(doc.created_at) if doc.created_at else None,
    )


@router.get("/knowledge")
async def list_knowledge(
    category: str | None = None,
    org: OrganizationModel = Depends(get_authenticated_org),
) -> list[KnowledgeDocumentResponse]:
    """List knowledge documents for this org."""
    session = await _get_session_from_org(org)
    stmt = select(KnowledgeDocumentModel).where(
        KnowledgeDocumentModel.organization_id == org.id
    )
    if category:
        stmt = stmt.where(KnowledgeDocumentModel.category == category)

    result = await session.execute(stmt)
    return [
        KnowledgeDocumentResponse(
            id=doc.id,
            title=doc.title,
            category=doc.category,
            created_at=str(doc.created_at) if doc.created_at else None,
        )
        for doc in result.scalars().all()
    ]


@router.delete("/knowledge/{doc_id}", status_code=204)
async def delete_knowledge(
    doc_id: uuid.UUID,
    org: OrganizationModel = Depends(get_authenticated_org),
):
    """Delete a knowledge document (must belong to this org)."""
    session = await _get_session_from_org(org)
    stmt = select(KnowledgeDocumentModel).where(
        KnowledgeDocumentModel.id == doc_id,
        KnowledgeDocumentModel.organization_id == org.id,
    )
    result = await session.execute(stmt)
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    await session.delete(doc)
    await session.flush()


# ==================== CONVERSATIONS (verified outcome) ====================

@router.post("/conversations/{conversation_id}/outcome")
async def report_conversation_outcome(
    conversation_id: uuid.UUID,
    body: OutcomeUpdateRequest,
    org: OrganizationModel = Depends(get_authenticated_org),
) -> dict:
    """Record a CRM-verified outcome (e.g. a completed payment) and feed it to
    the learning loop as real ground truth.

    The CRM reaches this under /management (Bearer org key); the internal-token
    episode endpoint is unreachable with that credential, and it also 404s when
    no Episode row exists (CRM fast-ACK conversations have none).
    """
    session = await _get_session_from_org(org)

    conversation = await session.get(ConversationModel, conversation_id)
    if conversation is None or conversation.organization_id != org.id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Persist + COMMIT the outcome first: run_live_learning opens its OWN
    # session (async_session_factory) and only sees the new value once it's
    # committed — same mid-handler commit pattern as the /knowledge endpoint.
    conversation.outcome = body.outcome
    conversation.updated_at = datetime.utcnow()
    await session.commit()

    if conversation.learned_at is None:
        # Not learned yet → extract + score moves with the verified outcome.
        await run_live_learning(conversation_id)
    else:
        # Already learned (likely at terminal with an inferred outcome) →
        # re-score the existing moves/clusters with the verified outcome.
        async with async_session_factory() as learn_session:
            async with learn_session.begin():
                await _propagate_outcome_to_clusters(learn_session, conversation_id, body.outcome)

    # Ground truth from the CRM: approve this conversation's moves so they
    # cluster and become retrievable plays (this is what closes the learning
    # loop — without it, moves stay pending forever and proven_plays is empty).
    async with async_session_factory() as approve_session:
        async with approve_session.begin():
            await approve_moves_for_conversation(approve_session, conversation_id)

    # Best-effort: if an Episode exists, mirror the outcome onto it too. CRM
    # fast-ACK conversations usually have none, so a miss is expected — never 404.
    try:
        await SQLEpisodicRepository(session).update_feedback(
            conversation_id, body.outcome, body.outcome_notes
        )
    except Exception as e:  # noqa: BLE001 — episode mirror is non-essential
        logger.warning("Episode feedback mirror failed (non-fatal): %s", e)

    return {"status": "ok", "outcome": body.outcome}


# ==================== OUTBOUND CALLS ====================

@router.post("/outbound-calls")
async def create_outbound_call(
    body: OutboundCallRequest,
    org: OrganizationModel = Depends(get_authenticated_org),
) -> OutboundCallResponse:
    """Initiate an outbound call via Retell. Metadata carries only IDs, never secrets."""
    if not settings.retell_api_key:
        raise HTTPException(status_code=400, detail="Voice provider not configured")

    session = await _get_session_from_org(org)
    await _verify_version_belongs_to_org(session, body.agent_version_id, org.id)

    service = OutboundCallService()
    data = await service.initiate(
        to_number=body.to_number,
        from_number=body.from_number,
        organization_id=str(org.id),
        agent_version_id=str(body.agent_version_id),
        extra_metadata=body.metadata,
    )

    return OutboundCallResponse(
        call_id=data.get("call_id", data.get("id", "")),
        status=data.get("status", "initiated"),
    )
