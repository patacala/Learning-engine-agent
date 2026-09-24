"""LLMCallTracker: real HTTP-attempt ground truth for a pipeline node,
including across concurrent coroutines (analyze runs its 4→1 detectors via
asyncio.gather) — contextvars must propagate into child tasks correctly for
this to attribute attempts to the right node at all."""

import asyncio

import httpx
import pytest

from prosales.infrastructure.llm.observability import EVENT_HOOKS, LLMCallTracker


def _client() -> httpx.AsyncClient:
    """httpx.AsyncClient wired to the real event hooks, with a MockTransport
    so no actual network call happens — same technique used to unit-test
    httpx-based code without extra mocking dependencies."""
    transport = httpx.MockTransport(lambda request: httpx.Response(200))
    return httpx.AsyncClient(transport=transport, event_hooks=EVENT_HOOKS)


@pytest.mark.asyncio
async def test_tracker_records_single_attempt():
    async with _client() as client:
        with LLMCallTracker("test_node") as tracker:
            await client.get("https://example.test/ping")

    assert tracker.http_attempts == 1
    assert tracker.http_retry_count == 0
    assert tracker.attempts[0].status_code == 200
    assert tracker.http_max_elapsed_ms is not None


@pytest.mark.asyncio
async def test_tracker_counts_concurrent_calls_from_gather():
    """Mirrors AnalyzerOrchestrator: several detector calls fired via
    asyncio.gather inside one node — all must land on the same tracker."""
    async with _client() as client:
        with LLMCallTracker("analyze") as tracker:
            await asyncio.gather(
                client.get("https://example.test/a"),
                client.get("https://example.test/b"),
                client.get("https://example.test/c"),
            )

    assert tracker.http_attempts == 3
    assert tracker.http_retry_count == 2


@pytest.mark.asyncio
async def test_calls_outside_any_tracker_are_ignored():
    async with _client() as client:
        await client.get("https://example.test/untracked")  # no tracker active — must not raise


@pytest.mark.asyncio
async def test_two_sibling_trackers_dont_leak_into_each_other():
    """Sequential nodes (not nested) must not see each other's attempts —
    regression guard for the ContextVar reset in __exit__."""
    async with _client() as client:
        with LLMCallTracker("node_a") as tracker_a:
            await client.get("https://example.test/x")

        with LLMCallTracker("node_b") as tracker_b:
            await client.get("https://example.test/y")

    assert tracker_a.http_attempts == 1
    assert tracker_b.http_attempts == 1
