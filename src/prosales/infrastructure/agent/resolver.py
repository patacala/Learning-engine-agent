"""Agent context resolver: API key → Organization → Agent → AgentContext."""

import hashlib
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from prosales.core.models.agent import AgentContext
from prosales.infrastructure.cache.redis import RedisCache
from prosales.infrastructure.database.models_agent import (
    AgentModel,
    AgentVersionModel,
    OrganizationAgentModel,
    OrganizationModel,
)

# Note: OrganizationModel is a lightweight tenant (name, api_key, capabilities).
# Business context (industry, products, etc.) comes from the CRM at request time.

CACHE_TTL = 300  # 5 minutes


async def invalidate_agent_context(cache: RedisCache, api_key: str) -> None:
    """Invalidate cached agent context for an API key."""
    digest = hashlib.sha256(api_key.encode()).hexdigest()[:16]
    await cache.delete(f"agent_ctx:apikey:{digest}")


async def invalidate_agent_version_cache(cache: RedisCache, agent_version_id: UUID) -> None:
    """Invalidate cached data for an agent version (provider caches)."""
    key = f"agent_version:{agent_version_id}"
    await cache.delete(key)


async def resolve_agent_version_for_org(
    session: AsyncSession, organization_id: UUID
) -> UUID | None:
    """The org's primary active agent version (no API key needed).

    Fallback for live conversations that didn't persist agent_version_id.
    """
    stmt = (
        select(OrganizationAgentModel.agent_version_id)
        .where(
            OrganizationAgentModel.organization_id == organization_id,
            OrganizationAgentModel.is_active.is_(True),
            OrganizationAgentModel.is_primary.is_(True),
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def resolve_published_version(
    session: AsyncSession,
    agent_version_id: UUID,
) -> AgentContext | None:
    """Resolve a published Cognition agent by version id — no org or API key.

    Training, roleplay, and the agent catalog treat agents as product-owned.
    ``organization_id`` stays None so conversations are not tenant-scoped.
    """
    version = (
        await session.execute(
            select(AgentVersionModel).where(
                AgentVersionModel.id == agent_version_id,
                AgentVersionModel.is_published.is_(True),
            )
        )
    ).scalar_one_or_none()
    if version is None:
        return None

    agent = (
        await session.execute(
            select(AgentModel).where(
                AgentModel.id == version.agent_id,
                AgentModel.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if agent is None:
        return None

    return AgentContext(
        organization_id=None,
        organization_name="Cognition",
        org_capabilities=["knowledge", "voice"],
        agent_id=agent.id,
        agent_version_id=version.id,
        agent_name=agent.name,
        agent_type=agent.agent_type,
        agent_capabilities=version.capabilities or [],
    )


async def resolve_by_ids(
    session: AsyncSession,
    organization_id: UUID,
    agent_version_id: UUID,
) -> AgentContext | None:
    """Resolve AgentContext from IDs directly (for outbound calls — no api_key needed)."""
    # Load organization
    stmt = select(OrganizationModel).where(
        OrganizationModel.id == organization_id,
        OrganizationModel.is_active.is_(True),
    )
    result = await session.execute(stmt)
    org = result.scalar_one_or_none()
    if org is None:
        return None

    # Load version
    stmt = select(AgentVersionModel).where(
        AgentVersionModel.id == agent_version_id,
        AgentVersionModel.is_published.is_(True),
    )
    result = await session.execute(stmt)
    version = result.scalar_one_or_none()
    if version is None:
        return None

    # Load agent
    stmt = select(AgentModel).where(AgentModel.id == version.agent_id)
    result = await session.execute(stmt)
    agent = result.scalar_one_or_none()
    if agent is None:
        return None

    return AgentContext(
        organization_id=org.id,
        organization_name=org.name,
        org_capabilities=org.capabilities or [],
        agent_id=agent.id,
        agent_version_id=version.id,
        agent_name=agent.name,
        agent_type=agent.agent_type,
        agent_capabilities=version.capabilities or [],
    )


class AgentContextResolver:
    def __init__(self, session: AsyncSession, cache: RedisCache | None = None):
        self.session = session
        self.cache = cache

    def _cache_key(self, api_key: str) -> str:
        digest = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        return f"agent_ctx:apikey:{digest}"

    async def resolve(self, api_key: str) -> AgentContext | None:
        # 1. Cache check
        if self.cache:
            cache_key = self._cache_key(api_key)
            cached = await self.cache.get(cache_key)
            if cached:
                return AgentContext(**cached)

        # 2. Find organization by API key
        prefix = api_key[:8]
        stmt = (
            select(OrganizationModel)
            .where(
                OrganizationModel.api_key_prefix == prefix,
                OrganizationModel.api_key == api_key,
                OrganizationModel.is_active.is_(True),
            )
        )
        result = await self.session.execute(stmt)
        org = result.scalar_one_or_none()

        if org is None:
            return None

        # 3. Find primary active agent assignment
        stmt = (
            select(OrganizationAgentModel)
            .where(
                OrganizationAgentModel.organization_id == org.id,
                OrganizationAgentModel.is_active.is_(True),
                OrganizationAgentModel.is_primary.is_(True),
            )
        )
        result = await self.session.execute(stmt)
        assignment = result.scalar_one_or_none()

        if assignment is None:
            return None

        # 4. Load agent version
        stmt = (
            select(AgentVersionModel)
            .where(
                AgentVersionModel.id == assignment.agent_version_id,
                AgentVersionModel.is_published.is_(True),
            )
        )
        result = await self.session.execute(stmt)
        version = result.scalar_one_or_none()

        if version is None:
            return None

        # 5. Load agent
        stmt = select(AgentModel).where(AgentModel.id == version.agent_id)
        result = await self.session.execute(stmt)
        agent = result.scalar_one_or_none()

        if agent is None:
            return None

        # 6. Build context
        ctx = AgentContext(
            organization_id=org.id,
            organization_name=org.name,
            org_capabilities=org.capabilities or [],
            agent_id=agent.id,
            agent_version_id=version.id,
            agent_name=agent.name,
            agent_type=agent.agent_type,
            agent_capabilities=version.capabilities or [],
        )

        # 7. Cache
        if self.cache:
            await self.cache.set(cache_key, ctx.model_dump(mode="json"), ttl=CACHE_TTL)

        return ctx
