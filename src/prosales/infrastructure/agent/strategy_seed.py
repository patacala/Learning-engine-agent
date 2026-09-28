"""Strategy catalog seeding — idempotent, fills agent_strategies from STRATEGY_CATALOG.

Shared by scripts/seed_strategies.py (CLI) and the provisioning bootstrap
endpoint/script — keep the logic here, not duplicated in either caller.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from prosales.engines.strategy.catalog import STRATEGY_CATALOG
from prosales.infrastructure.database.models_agent import (
    AgentStrategyModel,
    AgentTacticModel,
    AgentVersionModel,
)


async def seed_strategies(session: AsyncSession) -> dict[str, int]:
    """Insert missing strategies for all published agent versions. Returns counts."""
    result = await session.execute(
        select(AgentVersionModel).where(AgentVersionModel.is_published.is_(True))
    )
    versions = result.scalars().all()

    total_added = 0
    total_skipped = 0

    for version in versions:
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
