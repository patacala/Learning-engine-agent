"""Backfill embeddings for existing insights (published behavior_rules).

Run once after migration 016 (insight_embedding). Rules with no embedding are
never filtered out by relevance in ``SQLInsightsRepository.behavior_rules`` —
they rank last and can lose the retrieval cap, but until this runs they can
also never be scoped, so this is what actually makes the relevance filter
matter for pre-existing rules.

Idempotent: only touches rows where ``embedding IS NULL``.

Usage:
    python -m scripts.backfill_insight_embeddings
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from learning_engine.infrastructure.database.connection import async_session_factory
from learning_engine.infrastructure.database.models_insights import InsightModel
from learning_engine.infrastructure.vector_store.pgvector import PGVectorStore


async def backfill() -> int:
    async with async_session_factory() as session:
        rows = (
            await session.execute(
                select(InsightModel).where(
                    InsightModel.embedding.is_(None),
                    InsightModel.behavior_rule != "",
                )
            )
        ).scalars().all()

        if not rows:
            print("Nothing to backfill.")
            return 0

        store = PGVectorStore(session)
        for row in rows:
            row.embedding = await store.embed(row.behavior_rule[:2000])
        await session.commit()
        print(f"Backfilled {len(rows)} insight(s).")
        return len(rows)


if __name__ == "__main__":
    asyncio.run(backfill())
