import hmac
import logging
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

logger = logging.getLogger(__name__)

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


async def require_agent_context(
    session: AsyncSession,
    x_api_key: str | None,
) -> AgentContext:
    """Like ``get_agent_context`` but the key is MANDATORY.

    Tenant-facing endpoints (conversation, contact) must never run without an
    organization: an unscoped run would create NULL-org data and search the
    knowledge base without a tenant filter.
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    ctx = await get_agent_context(session, x_api_key)
    assert ctx is not None  # get_agent_context raises 401 on invalid keys
    return ctx


def _internal_token_ok(token: str | None) -> bool:
    """Constant-time check of the internal API token.

    When INTERNAL_API_TOKEN is unset, internal endpoints are open ONLY in
    development (local UI/tests); any other APP_ENV rejects every request so a
    misconfigured production deploy fails closed for callers, not open.
    """
    if not settings.internal_api_token:
        if settings.app_env == "development":
            return True
        logger.error(
            "INTERNAL_API_TOKEN is not set and APP_ENV=%s — rejecting internal API access",
            settings.app_env,
        )
        return False
    return token is not None and hmac.compare_digest(token, settings.internal_api_token)


async def verify_internal_token(
    x_internal_token: str | None = Header(None),
) -> None:
    """Gate for internal/training endpoints (learning, testing, agents, timeline)."""
    if not _internal_token_ok(x_internal_token):
        raise HTTPException(status_code=401, detail="Invalid or missing internal token")


async def verify_internal_or_api_key(
    x_internal_token: str | None = Header(None),
    x_api_key: str | None = Header(None),
) -> None:
    """Gate for endpoints used by BOTH the internal UI and the CRM.

    Accepts the internal token (UI) or a valid, active organization API key
    (CRM calls e.g. /conversation/{id}/close and /feedback).
    """
    if _internal_token_ok(x_internal_token):
        return
    if x_api_key:
        async with async_session_factory() as session:
            stmt = select(OrganizationModel.id).where(
                OrganizationModel.api_key_prefix == x_api_key[:8],
                OrganizationModel.api_key == x_api_key,
                OrganizationModel.is_active.is_(True),
            )
            if (await session.execute(stmt)).scalar_one_or_none() is not None:
                return
    raise HTTPException(status_code=401, detail="Invalid or missing credentials")


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
