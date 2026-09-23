"""Bootstrap the FIRST working tenant — idempotent, safe to re-run.

A fresh DB has no organization/agent, so the pipeline can't resolve an
``agent_context`` for any API key. This script wires a complete, working tenant:

  1. Organization (tenant, by slug)               -> create_organization
  2. Agent + published version 1 (from template)  -> create_agent_from_template
  3. Primary org<->agent assignment               -> assign_agent_to_org
  4. Strategy catalog top-up (full 30-catalog)     -> seed_strategies

It then prints the org's API key when a key is created/provided.

Idempotency: reuses the org by slug; if the org already has a primary active
agent, it skips creation; existing plaintext keys are not recoverable. Re-running only fills
gaps.

Usage (local):
    python -m scripts.bootstrap_tenant --name "Acme" --slug acme

Usage (Docker/Coolify one-off, from the API image):
    docker compose -f docker-compose.prod.yml run --rm \
        -e BOOTSTRAP_ORG_NAME="Acme" -e BOOTSTRAP_ORG_SLUG=acme bootstrap
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from prosales.config import settings
from prosales.infrastructure.agent.templates import (
    AGENT_TEMPLATES,
    ORG_CAPABILITY_PRESETS,
    assign_agent_to_org,
    create_agent_from_template,
    create_organization,
)
from prosales.infrastructure.database.models_agent import (
    OrganizationAgentModel,
    OrganizationModel,
)
from scripts.seed_strategies import seed_strategies


async def _bootstrap(
    session: AsyncSession,
    *,
    name: str,
    slug: str,
    agent_type: str,
    capabilities_preset: str,
    api_key: str | None,
    strategy_topup: bool,
) -> dict:
    # 1. Organization (reuse by slug if it already exists).
    org = (
        await session.execute(
            select(OrganizationModel).where(OrganizationModel.slug == slug)
        )
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
    else:
        created_agent = False

    # 4. Fill the strategy catalog to the full set for every published version.
    topup = None
    if strategy_topup:
        topup = await seed_strategies(session)  # commits internally

    await session.commit()
    return {
        "org_id": str(org.id),
        "slug": org.slug,
        "api_key": getattr(org, "_plain_api_key", api_key if created_org and api_key else None),
        "capabilities": org.capabilities or [],
        "created_org": created_org,
        "created_agent": created_agent,
        "strategy_topup": topup,
    }


async def _run(args: argparse.Namespace) -> None:
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with async_session() as session:
            result = await _bootstrap(
                session,
                name=args.name,
                slug=args.slug,
                agent_type=args.agent_type,
                capabilities_preset=args.capabilities,
                api_key=args.api_key,
                strategy_topup=not args.no_strategy_topup,
            )
    finally:
        await engine.dispose()

    print("\n=== Tenant bootstrap complete ===")
    print(f"  Organization : {result['slug']}  (id={result['org_id']})")
    print(f"  Org created  : {result['created_org']}   Agent created: {result['created_agent']}")
    print(f"  Capabilities : {', '.join(result['capabilities']) or '(none)'}")
    if result["strategy_topup"] is not None:
        t = result["strategy_topup"]
        print(f"  Strategies   : +{t['added']} added, {t['skipped']} already present "
              f"({t['versions']} version(s))")
    if result["api_key"]:
        print("\n  >>> API KEY (use as X-API-Key header):")
        print(f"      {result['api_key']}\n")
    else:
        print("\n  >>> API KEY: existing org reused; plaintext key is not stored.")
        print("      Regenerate it via /api/v1/provisioning/organizations/{org_id}/regenerate-key if needed.\n")


def main() -> None:
    p = argparse.ArgumentParser(description="Bootstrap the first working ProSales tenant.")
    p.add_argument("--name", default=os.getenv("BOOTSTRAP_ORG_NAME", "Default Org"))
    p.add_argument("--slug", default=os.getenv("BOOTSTRAP_ORG_SLUG", "default"))
    p.add_argument(
        "--agent-type",
        default=os.getenv("BOOTSTRAP_AGENT_TYPE", "sales"),
        choices=sorted(AGENT_TEMPLATES.keys()),
    )
    p.add_argument(
        "--capabilities",
        default=os.getenv("BOOTSTRAP_CAPABILITIES", "full"),
        choices=sorted(ORG_CAPABILITY_PRESETS.keys()),
    )
    p.add_argument("--api-key", default=os.getenv("BOOTSTRAP_API_KEY") or None,
                   help="Fixed API key (default: auto-generated sk-<slug>-<random>).")
    p.add_argument("--no-strategy-topup", action="store_true",
                   help="Skip filling the full strategy catalog.")
    asyncio.run(_run(p.parse_args()))


if __name__ == "__main__":
    main()
