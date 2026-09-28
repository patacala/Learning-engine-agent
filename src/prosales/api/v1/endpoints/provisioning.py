"""Provisioning endpoints — CRM super-admin operations on tenants.

Protected by PROVISIONING_SECRET. Only 2 endpoints — minimal surface.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from prosales.api.v1.dependencies import get_db_session, verify_provisioning_secret
from prosales.api.v1.schemas.management import (
    BootstrapTenantRequest,
    BootstrapTenantResponse,
    OrganizationResponse,
    ProvisionOrganizationRequest,
)
from prosales.infrastructure.agent.bootstrap import bootstrap_tenant
from prosales.infrastructure.agent.templates import ORG_CAPABILITY_PRESETS, create_organization
from prosales.infrastructure.database.models_agent import OrganizationModel
from prosales.infrastructure.security.api_keys import api_key_prefix, generate_api_key, hash_api_key

router = APIRouter(
    prefix="/provisioning",
    tags=["provisioning"],
    dependencies=[Depends(verify_provisioning_secret)],
)


def _org_response(org: OrganizationModel, api_key: str | None = None) -> OrganizationResponse:
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        api_key=api_key,
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
        existing.updated_at = datetime.utcnow()
        await session.flush()
        return _org_response(existing)

    # Create
    clear_api_key = body.api_key or generate_api_key(slug)
    org = await create_organization(
        session,
        name=body.name,
        slug=slug,
        api_key=clear_api_key,
        capabilities_preset=body.capabilities_preset,
    )
    return _org_response(org, api_key=clear_api_key)


@router.post("/bootstrap")
async def bootstrap(
    body: BootstrapTenantRequest,
    session: AsyncSession = Depends(get_db_session),
) -> BootstrapTenantResponse:
    """HTTP equivalent of scripts/bootstrap_tenant.py — org + primary agent +
    strategy catalog top-up, idempotent by slug. For environments where a
    shell/SSH one-off (the `bootstrap` compose profile) isn't reachable.
    """
    result = await bootstrap_tenant(
        session,
        name=body.name,
        slug=body.slug,
        agent_type=body.agent_type,
        capabilities_preset=body.capabilities_preset,
        api_key=body.api_key,
        strategy_topup=body.strategy_topup,
    )
    return BootstrapTenantResponse(**result)


@router.post("/organizations/{org_id}/regenerate-key")
async def regenerate_api_key(
    org_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> OrganizationResponse:
    """Regenerate API key for an organization."""
    from uuid import UUID

    stmt = select(OrganizationModel).where(OrganizationModel.id == UUID(org_id))
    result = await session.execute(stmt)
    org = result.scalar_one_or_none()

    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    new_key = generate_api_key(org.slug)
    org.api_key_hash = hash_api_key(new_key)
    org.api_key_prefix = api_key_prefix(new_key)
    org.updated_at = datetime.utcnow()
    await session.flush()

    return _org_response(org, api_key=new_key)
