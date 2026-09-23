"""Concurrency load test for the chat pipeline.

Fires N concurrent turns at ``POST /conversation/message`` and reports
throughput, latency percentiles and error rate. If a DATABASE_URL is available
it samples ``pg_stat_activity`` before / during / after the run to verify the
short-session refactor: active connections should return to baseline afterwards
(no connection held for the whole request/LLM).

Usage:
    .venv/bin/python scripts/loadtest_chat.py \
        --base-url http://localhost:8000 \
        --api-key <ORG_API_KEY> \
        --concurrency 50 --requests 200

Notes:
- This drives the REAL pipeline (LLM calls cost money). Keep --requests modest.
- --api-key is optional; without it the pipeline runs with hardcoded defaults.
"""

import argparse
import asyncio
import os
import statistics
import time
from uuid import uuid4

import httpx

try:
    import asyncpg  # optional; only for pg_stat_activity sampling
except Exception:  # pragma: no cover
    asyncpg = None


MESSAGES = [
    "Hola, quería información sobre sus servicios",
    "¿Cuánto cuesta el plan mensual?",
    "Me parece un poco caro la verdad",
    "¿Tienen alguna promoción disponible?",
    "Perfecto, ¿cómo agendo una cita?",
]


async def _sample_active_connections(dsn: str) -> int | None:
    if not asyncpg:
        return None
    try:
        conn = await asyncpg.connect(dsn)
        try:
            val = await conn.fetchval(
                "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
            )
            return int(val)
        finally:
            await conn.close()
    except Exception as e:  # pragma: no cover
        print(f"  (pg_stat_activity sample failed: {e})")
        return None


async def _one_turn(client: httpx.AsyncClient, url: str, headers: dict) -> tuple[float, int]:
    payload = {
        "client_id": f"loadtest-{uuid4()}",
        "message": MESSAGES[int(time.time() * 1000) % len(MESSAGES)],
    }
    t0 = time.perf_counter()
    try:
        r = await client.post(url, json=payload, headers=headers, timeout=120.0)
        return (time.perf_counter() - t0), r.status_code
    except Exception:
        return (time.perf_counter() - t0), 0


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--api-key", default=os.getenv("LOADTEST_API_KEY"))
    ap.add_argument("--concurrency", type=int, default=25)
    ap.add_argument("--requests", type=int, default=100)
    ap.add_argument("--dsn", default=os.getenv("DATABASE_URL", "").replace("+asyncpg", ""))
    args = ap.parse_args()

    url = f"{args.base_url}/api/v1/conversation/message"
    headers = {"X-API-Key": args.api_key} if args.api_key else {}
    sem = asyncio.Semaphore(args.concurrency)

    dsn = args.dsn or None
    baseline = await _sample_active_connections(dsn) if dsn else None
    if baseline is not None:
        print(f"Baseline active DB connections: {baseline}")

    latencies: list[float] = []
    statuses: list[int] = []
    peak_conns = baseline or 0

    async with httpx.AsyncClient() as client:
        async def _worker():
            nonlocal peak_conns
            async with sem:
                dur, code = await _one_turn(client, url, headers)
                latencies.append(dur)
                statuses.append(code)

        # Sample connections mid-run in the background.
        stop = asyncio.Event()

        async def _monitor():
            nonlocal peak_conns
            while not stop.is_set() and dsn:
                n = await _sample_active_connections(dsn)
                if n is not None:
                    peak_conns = max(peak_conns, n)
                await asyncio.sleep(0.25)

        mon = asyncio.create_task(_monitor())
        wall0 = time.perf_counter()
        await asyncio.gather(*[_worker() for _ in range(args.requests)])
        wall = time.perf_counter() - wall0
        stop.set()
        await mon

    ok = sum(1 for s in statuses if s == 200)
    errors = len(statuses) - ok
    latencies.sort()

    def _pct(p: float) -> float:
        if not latencies:
            return 0.0
        idx = min(len(latencies) - 1, int(len(latencies) * p))
        return latencies[idx]

    print("\n=== Load test results ===")
    print(f"Requests:        {len(statuses)} (concurrency={args.concurrency})")
    print(f"Wall time:       {wall:.2f}s")
    print(f"Throughput:      {len(statuses) / wall:.1f} req/s")
    print(f"Success / error: {ok} / {errors}")
    if latencies:
        print(f"Latency mean:    {statistics.mean(latencies):.2f}s")
        print(f"Latency p50:     {_pct(0.50):.2f}s")
        print(f"Latency p95:     {_pct(0.95):.2f}s")
        print(f"Latency p99:     {_pct(0.99):.2f}s")

    if dsn:
        after = await _sample_active_connections(dsn)
        print(f"\nActive DB connections — baseline={baseline} peak={peak_conns} after={after}")
        if after is not None and baseline is not None and after <= baseline + 1:
            print("OK: connections returned to baseline (no leak).")
        elif after is not None:
            print("WARN: active connections did not return to baseline — investigate leaks.")


if __name__ == "__main__":
    asyncio.run(main())
