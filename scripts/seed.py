"""First-run seed — idempotent, safe to re-run.

Populates the strategy catalog (`agent_strategies` + `agent_tactics`) for every
PUBLISHED agent version. Run this ONCE after the first organization/agent has
been provisioned (a fresh DB has no agent versions yet, so it seeds nothing
until then). Re-running only fills gaps — existing strategies are skipped.

Usage:
    python -m scripts.seed              # strategies only (production default)
    python -m scripts.seed --knowledge  # + demo vehicle catalog (NON-idempotent)

In Docker/Coolify (one-off, from the API image):
    docker compose -f docker-compose.prod.yml run --rm seed
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from prosales.config import settings
from scripts.seed_strategies import seed_strategies


async def _run(with_knowledge: bool) -> None:
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as session:
            counts = await seed_strategies(session)
            print(
                f"[seed] strategies: {counts['added']} added, "
                f"{counts['skipped']} skipped, {counts['versions']} version(s) processed."
            )
            if counts["versions"] == 0:
                print(
                    "[seed] No published agent versions yet — provision an "
                    "organization first, then re-run this seed."
                )
    finally:
        await engine.dispose()

    if with_knowledge:
        # Demo data (Toyota/Honda catalog). NOT idempotent — re-running duplicates.
        from scripts.seed_knowledge import main as seed_knowledge_main

        print("[seed] indexing demo knowledge base...")
        await seed_knowledge_main()


def main() -> None:
    parser = argparse.ArgumentParser(description="ProSales first-run seed.")
    parser.add_argument(
        "--knowledge",
        action="store_true",
        help="Also index the demo vehicle catalog (non-idempotent demo data).",
    )
    args = parser.parse_args()
    asyncio.run(_run(with_knowledge=args.knowledge))


if __name__ == "__main__":
    main()
