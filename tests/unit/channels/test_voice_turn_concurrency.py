"""Tests for VoiceAdapter's turn concurrency/cancellation layer.

These target dispatch_turn/_run_turn/cancel_active_turn in isolation from
the cognitive pipeline (already covered by test_voice_adapter.py): chunk
producers are plain async generators standing in for on_user_speech/
on_call_opening, since the concurrency mechanism itself is provider- and
pipeline-agnostic.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from learning_engine.channels.voice.adapter import VoiceAdapter
from learning_engine.channels.voice.providers.base import VoiceChunk
from learning_engine.channels.voice.session import VoiceSessionManager


class FakeRedisCache:
    async def get(self, key):
        return None

    async def set(self, key, value, ttl: int = 3600):
        pass

    async def delete(self, key):
        pass


class FakeWebSocket:
    def __init__(self):
        self.sent: list[dict] = []

    async def send_json(self, msg: dict) -> None:
        self.sent.append(msg)


async def _format_response(chunk: VoiceChunk, response_id=None) -> dict:
    return {
        "content": chunk.content,
        "response_id": response_id,
        "content_complete": chunk.end_of_turn,
    }


def _make_adapter() -> VoiceAdapter:
    manager = VoiceSessionManager(FakeRedisCache())
    return VoiceAdapter(
        provider=MagicMock(),
        session_manager=manager,
        session_factory=MagicMock(),
        cache=None,
    )


async def _slow_turn(started: asyncio.Event, release: asyncio.Event, label: str):
    """Yields once, then blocks on `release` before yielding the final chunk —
    stands in for a turn still mid-generation when a new one arrives."""
    yield VoiceChunk(content=f"{label}-1", end_of_turn=False)
    started.set()
    await release.wait()
    yield VoiceChunk(content=f"{label}-2", end_of_turn=True)


async def _instant_turn(label: str):
    yield VoiceChunk(content=f"{label}-1", end_of_turn=True)


@pytest.mark.asyncio
async def test_interruption_cancels_previous_turn_mid_generation():
    """A new response_required must cancel a turn still generating, and its
    stale chunks must never reach the WebSocket."""
    adapter = _make_adapter()
    ws = FakeWebSocket()
    started = asyncio.Event()
    release = asyncio.Event()

    adapter.dispatch_turn(
        "call-1", _slow_turn(started, release, "old"), ws, 1, _format_response
    )
    await started.wait()

    adapter.dispatch_turn(
        "call-1", _instant_turn("new"), ws, 2, _format_response
    )
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    release.set()
    await asyncio.sleep(0.01)

    contents = [m["content"] for m in ws.sent]
    assert "old-2" not in contents, "a superseded turn's chunk must never be sent"
    assert "new-1" in contents


@pytest.mark.asyncio
async def test_interruption_just_before_send_drops_stale_chunk():
    """Even if task.cancel() hasn't propagated yet, the turn_id gate checked
    right before each send must drop a chunk from an already-superseded
    turn — this is the race the pure cancel() path can't fully cover."""
    adapter = _make_adapter()
    ws = FakeWebSocket()

    async def almost_done_turn():
        yield VoiceChunk(content="first", end_of_turn=False)
        # Simulate another turn having been dispatched concurrently right
        # after this chunk was produced but before the next one is sent.
        adapter._active_turn_id += 1
        yield VoiceChunk(content="final", end_of_turn=True)

    adapter.dispatch_turn("call-1", almost_done_turn(), ws, 1, _format_response)
    await asyncio.sleep(0.01)

    contents = [m["content"] for m in ws.sent]
    assert contents == ["first"]


@pytest.mark.asyncio
async def test_consecutive_turns_both_complete_without_interruption():
    """Two turns that don't overlap must both be delivered in full — normal,
    non-interrupted behavior stays unchanged."""
    adapter = _make_adapter()
    ws = FakeWebSocket()

    adapter.dispatch_turn("call-1", _instant_turn("one"), ws, 1, _format_response)
    await adapter._active_task

    adapter.dispatch_turn("call-1", _instant_turn("two"), ws, 2, _format_response)
    await adapter._active_task

    contents = [m["content"] for m in ws.sent]
    assert contents == ["one-1", "two-1"]


@pytest.mark.asyncio
async def test_cancel_active_turn_on_disconnect_stops_pending_generation():
    """A WebSocket disconnect (session_end / finally block) must cancel the
    in-flight turn so its producer stops and nothing more is sent."""
    adapter = _make_adapter()
    ws = FakeWebSocket()
    started = asyncio.Event()
    release = asyncio.Event()

    adapter.dispatch_turn(
        "call-1", _slow_turn(started, release, "call"), ws, 1, _format_response
    )
    await started.wait()

    adapter.cancel_active_turn("call-1")
    await asyncio.sleep(0.01)

    contents = [m["content"] for m in ws.sent]
    assert contents == ["call-1"]  # only the chunk sent before cancellation


@pytest.mark.asyncio
async def test_task_cancellation_does_not_raise_unhandled_exception():
    """Cancelling a turn must not leak an unretrieved CancelledError out of
    the background task — it's swallowed and logged inside _run_turn."""
    adapter = _make_adapter()
    ws = FakeWebSocket()
    started = asyncio.Event()
    release = asyncio.Event()

    adapter.dispatch_turn(
        "call-1", _slow_turn(started, release, "x"), ws, 1, _format_response
    )
    await started.wait()
    task = adapter._active_task
    task.cancel()
    await asyncio.sleep(0.01)

    assert task.done()
    assert task.cancelled() is False
    assert task.exception() is None


@pytest.mark.asyncio
async def test_send_failure_after_disconnect_does_not_crash_task():
    """If the WebSocket is already closed, send_json raising must not crash
    the background task or raise an unhandled exception."""
    adapter = _make_adapter()

    class DeadWebSocket:
        async def send_json(self, msg):
            raise RuntimeError("WebSocket is closed")

    adapter.dispatch_turn(
        "call-1", _instant_turn("one"), DeadWebSocket(), 1, _format_response
    )
    task = adapter._active_task
    await asyncio.sleep(0.01)

    assert task.done()
    assert task.exception() is None
