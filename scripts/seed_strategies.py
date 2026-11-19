"""Seed strategies — idempotent CLI wrapper to populate agent_strategies from
the expanded catalog. The actual logic lives in
learning_engine.infrastructure.agent.strategy_seed (shared with the provisioning
bootstrap endpoint), so it isn't duplicated here.

Usage:
    python -m scripts.seed_strategies
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from learning_engine.config import settings
from learning_engine.infrastructure.agent.strategy_seed import seed_strategies


async def main():
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        counts = await seed_strategies(session)
        await session.commit()
        print(f"Seed complete: {counts['added']} strategies added, "
              f"{counts['skipped']} skipped, "
              f"{counts['versions']} versions processed.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
