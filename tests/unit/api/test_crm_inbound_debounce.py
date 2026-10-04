"""CRM inbound debounce: rapid messages for one conversation coalesce into a
single pipeline run on the combined text; a message arriving within the window
cancels the pending run and restarts it."""

import asyncio
from uuid import uuid4

import pytest

import prosales.api.v1.endpoints.crm_inbound as ci
from prosales.config import settings


class FakeCache:
    """In-memory stand-in for RedisCache's list_push / list_drain."""

    def __init__(self):
        self.lists: dict[str, list[str]] = {}

    async def list_push(self, key, value, ttl=300):
        self.lists.setdefault(key, []).append(value)

    async def list_drain(self, key):
        return self.lists.pop(key, [])


@pytest.fixture
def fast_window(monkeypatch):
    monkeypatch.setattr(settings, "crm_debounce_seconds", 0.05)


@pytest.fixture
def captured_runs(monkeypatch):
    runs = []

    async def fake_run(message, client_id, conversation_id, agent_context,
                       organization_id, extra_context=None, contact_id=None):
        runs.append(message)

    monkeypatch.setattr(ci, "_run_pipeline_and_reply", fake_run)
    return runs


@pytest.mark.asyncio
async def test_single_message_runs_after_window(fast_window, captured_runs, monkeypatch):
    cache = FakeCache()
    monkeypatch.setattr(ci, "get_redis_cache", lambda: cache)
    conv = uuid4()
    await cache.list_push(ci._buffer_key(conv), "hola")

    await ci._debounce_and_run(conv, uuid4(), object(), uuid4(), None, "c1")

    assert captured_runs == ["hola"]


@pytest.mark.asyncio
async def test_three_rapid_messages_coalesce_into_one_run(fast_window, captured_runs, monkeypatch):
    cache = FakeCache()
    monkeypatch.setattr(ci, "get_redis_cache", lambda: cache)
    conv = uuid4()
    key = str(conv)

    # Simulate three inbound webhooks in quick succession: each buffers and
    # (re)arms, cancelling the previous pending task.
    for text in ["quiero", "un audi", "a5"]:
        await cache.list_push(ci._buffer_key(conv), text)
        existing = ci._debounce_tasks.get(key)
        if existing and not existing.done():
            existing.cancel()
        ci._debounce_tasks[key] = asyncio.create_task(
            ci._debounce_and_run(conv, uuid4(), object(), uuid4(), None, "c1")
        )

    # Let the surviving task's window elapse.
    await asyncio.sleep(0.15)

    assert captured_runs == ["quiero\nun audi\na5"]  # one run, combined in order


@pytest.mark.asyncio
async def test_cancelled_task_does_not_run(fast_window, captured_runs, monkeypatch):
    cache = FakeCache()
    monkeypatch.setattr(ci, "get_redis_cache", lambda: cache)
    conv = uuid4()
    await cache.list_push(ci._buffer_key(conv), "msg")

    task = asyncio.create_task(
        ci._debounce_and_run(conv, uuid4(), object(), uuid4(), None, "c1")
    )
    await asyncio.sleep(0)  # let it reach the sleep
    task.cancel()
    await asyncio.sleep(0.1)

    assert captured_runs == []
    # Buffer untouched — the next task will drain it.
    assert cache.lists[ci._buffer_key(conv)] == ["msg"]
