"""Tests for VoiceSessionManager — Redis-backed session state."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

from learning_engine.channels.voice.session import VoiceSession, VoiceSessionManager


class FakeRedisCache:
    """In-memory Redis cache substitute for testing."""

    def __init__(self):
        self._store: dict = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value, ttl: int = 3600):
        self._store[key] = value

    async def delete(self, key: str):
        self._store.pop(key, None)


def _make_session(session_id: str = "test-123") -> VoiceSession:
    return VoiceSession(
        session_id=session_id,
        conversation_id=uuid4(),
        client_id=uuid4(),
        organization_id=uuid4(),
        started_at=datetime.now(timezone.utc),
        provider_type="retell",
        from_number="+1234567890",
    )


@pytest.mark.asyncio
async def test_create_and_get_session():
    """Should store and retrieve a voice session."""
    cache = FakeRedisCache()
    manager = VoiceSessionManager(cache)

    session = _make_session("call-abc")
    await manager.create("call-abc", session)

    retrieved = await manager.get("call-abc")
    assert retrieved is not None
    assert retrieved.session_id == "call-abc"
    assert retrieved.conversation_id == session.conversation_id
    assert retrieved.from_number == "+1234567890"


@pytest.mark.asyncio
async def test_increment_turn():
    """Should increment turn count and persist."""
    cache = FakeRedisCache()
    manager = VoiceSessionManager(cache)

    session = _make_session("call-inc")
    await manager.create("call-inc", session)

    count = await manager.increment_turn("call-inc")
    assert count == 1

    count = await manager.increment_turn("call-inc")
    assert count == 2

    updated = await manager.get("call-inc")
    assert updated.turn_count == 2


@pytest.mark.asyncio
async def test_get_nonexistent_returns_none():
    """Should return None for non-existent session."""
    cache = FakeRedisCache()
    manager = VoiceSessionManager(cache)

    result = await manager.get("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_delete_removes_session():
    """Should remove session from store."""
    cache = FakeRedisCache()
    manager = VoiceSessionManager(cache)

    session = _make_session("call-del")
    await manager.create("call-del", session)

    await manager.delete("call-del")
    result = await manager.get("call-del")
    assert result is None
