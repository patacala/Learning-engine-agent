"""Provisioning endpoints — CRM super-admin operations on tenants.

Protected by PROVISIONING_SECRET. Only 2 endpoints — minimal surface.
"""

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from prosales.api.v1.dependencies import get_db_session, get_redis_cache, verify_provisioning_secret
from prosales.api.v1.schemas.management import OrganizationResponse, ProvisionOrganizationRequest
from prosales.infrastructure.agent.resolver import invalidate_agent_context
from prosales.infrastructure.agent.templates import ORG_CAPABILITY_PRESETS, create_organization
from prosales.infrastructure.cache.redis import RedisCache
from prosales.infrastructure.database.models_agent import OrganizationModel

router = APIRouter(
    prefix="/provisioning",
    tags=["provisioning"],
    dependencies=[Depends(verify_provisioning_secret)],
)


def _org_response(org: OrganizationModel) -> OrganizationResponse:
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        api_key=org.api_key,
        capabilities=org.capabilities or [],
        is_active=org.is_active,
    )


@router.put("/organizations/{slug}")
async def provision_organization(
    slug: str,
    body: ProvisionOrganizationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> OrganizationResponse:
    """Idempotent upsert organization by slug. CRM can call multiple times safely."""
    stmt = select(OrganizationModel).where(OrganizationModel.slug == slug)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        # Update
        existing.name = body.name
        if body.capabilities_preset in ORG_CAPABILITY_PRESETS:
            existing.capabilities = ORG_CAPABILITY_PRESETS[body.capabilities_preset]
        existing.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return _org_response(existing)

    # Create
    org = await create_organization(
        session,
        name=body.name,
        slug=slug,
        api_key=body.api_key,
        capabilities_preset=body.capabilities_preset,
    )
    return _org_response(org)


@router.post("/organizations/{org_id}/regenerate-key")
async def regenerate_api_key(
    org_id: str,
    session: AsyncSession = Depends(get_db_session),
    cache: RedisCache = Depends(get_redis_cache),
) -> OrganizationResponse:
    """Regenerate API key for an organization and invalidate cache."""
    from uuid import UUID

    stmt = select(OrganizationModel).where(OrganizationModel.id == UUID(org_id))
    result = await session.execute(stmt)
    org = result.scalar_one_or_none()

    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    old_key = org.api_key
    new_key = f"sk-{org.slug}-{secrets.token_hex(12)}"
    org.api_key = new_key
    org.api_key_prefix = new_key[:8]
    org.updated_at = datetime.now(timezone.utc)
    await session.flush()

    # Invalidate old key cache
    await invalidate_agent_context(cache, old_key)

    return _org_response(org)
