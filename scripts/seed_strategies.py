"""Seed strategies — idempotent script to populate agent_strategies from expanded catalog.

For each published agent_version, inserts strategies from STRATEGY_CATALOG
that don't already exist in DB.

Usage:
    python -m scripts.seed_strategies
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from prosales.config import settings
from prosales.engines.strategy.catalog import STRATEGY_CATALOG
from prosales.infrastructure.database.models_agent import (
    AgentStrategyModel,
    AgentTacticModel,
    AgentVersionModel,
)


async def seed_strategies(session: AsyncSession) -> dict[str, int]:
    """Insert missing strategies for all published agent versions. Returns counts."""
    # Get all published versions
    result = await session.execute(
        select(AgentVersionModel).where(AgentVersionModel.is_published.is_(True))
    )
    versions = result.scalars().all()

    total_added = 0
    total_skipped = 0

    for version in versions:
        # Get existing strategy types for this version
        existing_result = await session.execute(
            select(AgentStrategyModel.strategy_type).where(
                AgentStrategyModel.agent_version_id == version.id
            )
        )
        existing_types = {row[0] for row in existing_result}

        for strategy_type, strategy in STRATEGY_CATALOG.items():
            if strategy_type.value in existing_types:
                total_skipped += 1
                continue

            # Insert strategy
            strat_model = AgentStrategyModel(
                agent_version_id=version.id,
                strategy_type=strategy_type.value,
                name=strategy.name,
                description=strategy.description,
                triggers=[],
                priority=5,
                cooldown_seconds=0,
            )
            session.add(strat_model)
            await session.flush()

            # Insert tactics
            for i, tactic in enumerate(strategy.tactics):
                tactic_model = AgentTacticModel(
                    strategy_id=strat_model.id,
                    name=tactic.name,
                    prompt_instruction=tactic.prompt_instruction,
                    position=i,
                )
                session.add(tactic_model)

            total_added += 1

    await session.commit()
    return {"added": total_added, "skipped": total_skipped, "versions": len(versions)}


async def main():
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        counts = await seed_strategies(session)
        print(f"Seed complete: {counts['added']} strategies added, "
              f"{counts['skipped']} skipped, "
              f"{counts['versions']} versions processed.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
