"""Backfill works_when on existing approved moves + their clusters.

The extractor guardrail added to engines/moves/extractor.py only affects moves
extracted from here on — it can't retroactively fix moves already in the DB.
Without works_when, a move can never be preferred by PatternRetriever's
client_state boost (engines/knowledge/pattern_retriever.py), even when its
content is a great topical match for the current message.

For every APPROVED move with no works_when tag but a known client_state_before,
sets conditions = {"works_when": [client_state_before]} — the same
deterministic derivation the extractor now does at ingest time, applied
retroactively. Then recomputes each affected cluster's condition_profile from
its member moves, using the exact same merge logic PatternClusterer uses on
approval (engines/performance/clusterer.py:_merge_conditions), so aggregates
stay consistent with how they'd look if these moves had been tagged correctly
from the start.

Idempotent: only touches moves that are missing works_when.

Usage:
    python -m scripts.backfill_move_conditions [--agent <agent_version_id>] [--dry-run]
"""

import argparse
import asyncio
import sys
from collections import defaultdict
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from prosales.engines.performance.clusterer import _merge_conditions
from prosales.infrastructure.database.connection import async_session_factory
from prosales.infrastructure.database.models_moves import ConversationMoveModel
from prosales.infrastructure.database.models_performance import PatternClusterModel


def _has_works_when(conditions: dict | None) -> bool:
    return bool((conditions or {}).get("works_when"))


async def backfill(agent_version_id: UUID | None, dry_run: bool) -> None:
    async with async_session_factory() as session:
        stmt = select(ConversationMoveModel).where(ConversationMoveModel.status == "approved")
        if agent_version_id:
            stmt = stmt.where(ConversationMoveModel.agent_version_id == agent_version_id)
        moves = (await session.execute(stmt)).scalars().all()

        tagged = 0
        touched_clusters: set[UUID] = set()
        for m in moves:
            if _has_works_when(m.conditions) or not m.client_state_before:
                continue
            new_conditions = dict(m.conditions or {})
            new_conditions["works_when"] = [m.client_state_before]
            print(
                f"  move {m.id} [{m.move_kind}]: conditions={m.conditions!r} "
                f"-> works_when=[{m.client_state_before!r}]"
            )
            if not dry_run:
                m.conditions = new_conditions
                tagged += 1
                if m.cluster_id:
                    touched_clusters.add(m.cluster_id)

        print(f"\n{'Would tag' if dry_run else 'Tagged'} {tagged if not dry_run else '(dry-run, see above)'} move(s).")

        if dry_run or not touched_clusters:
            if dry_run:
                print("(dry-run — no cluster recompute; re-run without --dry-run to apply)")
            return

        await session.flush()

        # Recompute each affected cluster's condition_profile from ALL its member
        # moves (not just the ones just tagged) — matches PatternClusterer's own
        # incremental aggregation, applied here in one pass.
        for cluster_id in touched_clusters:
            cluster = await session.get(PatternClusterModel, cluster_id)
            if cluster is None:
                continue
            member_moves = (
                await session.execute(
                    select(ConversationMoveModel).where(ConversationMoveModel.cluster_id == cluster_id)
                )
            ).scalars().all()
            profile = dict(cluster.condition_profile or {})
            # Rebuild works_when counts from scratch to avoid double-counting
            # across repeated runs (idempotent), keeping any other keys (e.g. "seed").
            profile.pop("works_when", None)
            for mv in member_moves:
                profile = _merge_conditions(profile, mv.conditions or {})
            print(f"  cluster {cluster_id} [{cluster.move_kind}]: condition_profile -> {profile}")
            cluster.condition_profile = profile

        await session.commit()
        print(f"\nRecomputed condition_profile for {len(touched_clusters)} cluster(s).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--agent", help="limit to one agent_version_id (default: all agents)")
    parser.add_argument("--dry-run", action="store_true", help="print what would change, don't write")
    args = parser.parse_args()
    asyncio.run(backfill(UUID(args.agent) if args.agent else None, args.dry_run))


if __name__ == "__main__":
    main()
