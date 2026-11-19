"""Aggregate real per-node latency + HTTP-attempt ground truth from
`pipeline.completed` events (populated by pipeline/nodes.py's
LLMCallTracker, infrastructure/llm/observability.py) — built 2026-09-24
because every prior latency finding in this project was a one-off manual
script. This is the tool to actually answer, from real traffic, "is a slow
node slow because of one slow API round-trip, or because of silent SDK
retries" — instead of assuming either.

Usage:
    python -m scripts.latency_diagnostics --last 50
    python -m scripts.latency_diagnostics --since-minutes 30
"""

import argparse
import asyncio
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text  # noqa: E402

from learning_engine.infrastructure.database.connection import async_session_factory  # noqa: E402


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    idx = min(len(values) - 1, int(len(values) * p))
    return values[idx]


async def run(last: int | None, since_minutes: int | None) -> None:
    where = "event_type = 'pipeline.completed'"
    params: dict = {}
    if since_minutes:
        where += " AND timestamp >= NOW() - (:mins || ' minutes')::interval"
        params["mins"] = since_minutes

    limit_sql = "LIMIT :limit" if last else ""
    if last:
        params["limit"] = last

    async with async_session_factory() as session:
        rows = (
            await session.execute(
                text(f"SELECT data FROM events WHERE {where} ORDER BY timestamp DESC {limit_sql}"),
                params,
            )
        ).fetchall()

    if not rows:
        print("No pipeline.completed events found for that window.")
        return

    per_node: dict[str, list[dict]] = defaultdict(list)
    for (data,) in rows:
        for node in data.get("nodes", []):
            per_node[node["node_id"]].append(node)

    print(f"{len(rows)} turns analyzed\n")
    header = f"{'node':<16} {'n':>4} {'p50ms':>8} {'p95ms':>8} {'max_ms':>8} {'attempts':>9} {'retries':>8} {'retry%':>7}"
    print(header)
    print("-" * len(header))

    for node_id, traces in sorted(per_node.items(), key=lambda kv: -statistics.median(t["duration_ms"] for t in kv[1])):
        durations = [t["duration_ms"] for t in traces]
        attempts = [t.get("http_attempts", 0) for t in traces]
        retries = [t.get("http_retry_count", 0) for t in traces]
        turns_with_retry = sum(1 for r in retries if r > 0)
        retry_pct = 100 * turns_with_retry / len(traces)
        print(
            f"{node_id:<16} {len(traces):>4} {_pct(durations, 0.5):>8.0f} {_pct(durations, 0.95):>8.0f} "
            f"{max(durations):>8.0f} {sum(attempts)/len(attempts):>9.2f} {sum(retries)/len(retries):>8.2f} {retry_pct:>6.0f}%"
        )

    total_retried_turns = sum(
        1 for (data,) in rows if any(n.get("http_retry_count", 0) > 0 for n in data.get("nodes", []))
    )
    print(f"\nturns with AT LEAST ONE retry anywhere: {total_retried_turns}/{len(rows)} "
          f"({100*total_retried_turns/len(rows):.0f}%)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--last", type=int, default=50, help="analyze the last N turns (default 50)")
    parser.add_argument("--since-minutes", type=int, default=None, help="instead: all turns in the last N minutes")
    args = parser.parse_args()
    asyncio.run(run(args.last, args.since_minutes))


if __name__ == "__main__":
    main()
