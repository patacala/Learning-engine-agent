from typing import AsyncGenerator

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from prosales.config import settings
from prosales.core.models.agent import AgentContext
from prosales.infrastructure.cache.redis import RedisCache
from prosales.infrastructure.database.connection import async_session_factory
from prosales.infrastructure.agent.resolver import AgentContextResolver
from prosales.infrastructure.database.models_agent import OrganizationModel

# Shared cache instance (initialized on first use)
_redis_cache: RedisCache | None = None


def get_redis_cache() -> RedisCache:
    global _redis_cache
    if _redis_cache is None:
        _redis_cache = RedisCache()
    return _redis_cache


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        async with session.begin():
            yield session


async def get_agent_context(
    session: AsyncSession,
    x_api_key: str | None = Header(None),
) -> AgentContext | None:
    """Resolve agent context from X-API-Key header. Returns None if no key provided."""
    if not x_api_key:
        return None

    cache = get_redis_cache()
    resolver = AgentContextResolver(session, cache)
    ctx = await resolver.resolve(x_api_key)
    if ctx is None:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    return ctx


async def verify_provisioning_secret(
    authorization: str = Header(...),
) -> None:
    """Validate provisioning secret from Authorization header."""
    token = authorization.removeprefix("Bearer ").strip()
    if not settings.provisioning_secret or token != settings.provisioning_secret:
        raise HTTPException(status_code=401, detail="Invalid provisioning secret")


async def get_authenticated_org(
    session: AsyncSession = Depends(get_db_session),
    authorization: str = Header(...),
) -> OrganizationModel:
    """Resolve org from Bearer API key. All management ops scoped to this org."""
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing API key")

    prefix = token[:8]
    stmt = select(OrganizationModel).where(
        OrganizationModel.api_key_prefix == prefix,
        OrganizationModel.api_key == token,
        OrganizationModel.is_active.is_(True),
    )
    result = await session.execute(stmt)
    org = result.scalar_one_or_none()

    if org is None:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    return org
