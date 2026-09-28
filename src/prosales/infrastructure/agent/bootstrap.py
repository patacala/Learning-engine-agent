"""Bootstrap the FIRST working tenant — idempotent, safe to re-run.

A fresh DB has no organization/agent, so the pipeline can't resolve an
``agent_context`` for any API key. This wires a complete, working tenant:

  1. Organization (tenant, by slug)               -> create_organization
  2. Agent + published version 1 (from template)  -> create_agent_from_template
  3. Primary org<->agent assignment               -> assign_agent_to_org
  4. Strategy catalog top-up (full 30-catalog)     -> seed_strategies

Shared by scripts/bootstrap_tenant.py (CLI, needs shell/SSH access) and the
POST /provisioning/bootstrap endpoint (HTTP, needs only PROVISIONING_SECRET)
so the two never drift.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from prosales.infrastructure.agent.strategy_seed import seed_strategies
from prosales.infrastructure.agent.templates import (
    assign_agent_to_org,
    create_agent_from_template,
    create_organization,
)
from prosales.infrastructure.database.models_agent import (
    OrganizationAgentModel,
    OrganizationModel,
)


async def bootstrap_tenant(
    session: AsyncSession,
    *,
    name: str,
    slug: str,
    agent_type: str = "sales",
    capabilities_preset: str = "full",
    api_key: str | None = None,
    strategy_topup: bool = True,
) -> dict:
    """Create (or reuse) an organization, its primary agent, and the strategy catalog.

    Does NOT commit — callers own the transaction (endpoints via
    get_db_session's session.begin(), the CLI script explicitly).
    """
    # 1. Organization (reuse by slug if it already exists).
    org = (
        await session.execute(select(OrganizationModel).where(OrganizationModel.slug == slug))
    ).scalar_one_or_none()
    if org is None:
        org = await create_organization(
            session,
            name=name,
            slug=slug,
            api_key=api_key,
            capabilities_preset=capabilities_preset,
        )
        created_org = True
    else:
        created_org = False

    # 2+3. Agent + assignment — only if the org has no primary active agent yet.
    existing_primary = (
        await session.execute(
            select(OrganizationAgentModel).where(
                OrganizationAgentModel.organization_id == org.id,
                OrganizationAgentModel.is_primary.is_(True),
                OrganizationAgentModel.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()

    if existing_primary is None:
        _, version = await create_agent_from_template(
            session,
            name=f"{name} Agent",
            slug=f"{slug}-agent",
            agent_type=agent_type,
        )
        await assign_agent_to_org(session, org.id, version.id, is_primary=True)
        created_agent = True
        agent_version_id = version.id
    else:
        created_agent = False
        agent_version_id = existing_primary.agent_version_id

    # 4. Fill the strategy catalog to the full set for every published version.
    topup = None
    if strategy_topup:
        topup = await seed_strategies(session)

    return {
        "org_id": str(org.id),
        "slug": org.slug,
        "agent_version_id": str(agent_version_id),
        "api_key": getattr(org, "_plain_api_key", api_key if created_org and api_key else None),
        "capabilities": org.capabilities or [],
        "created_org": created_org,
        "created_agent": created_agent,
        "strategy_topup": topup,
    }
