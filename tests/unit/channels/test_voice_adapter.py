"""Tests for VoiceAdapter — voice session orchestration."""

import pytest
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from prosales.channels.voice.adapter import VoiceAdapter
from prosales.channels.voice.providers.base import VoiceChunk, VoiceProvider
from prosales.channels.voice.session import VoiceSession, VoiceSessionManager


class FakeRedisCache:
    def __init__(self):
        self._store: dict = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value, ttl: int = 3600):
        self._store[key] = value

    async def delete(self, key: str):
        self._store.pop(key, None)


class MockProvider(VoiceProvider):
    """Mock voice provider for testing adapter logic."""

    PROVIDER_TYPE = "mock"

    async def parse_event(self, raw: dict):
        return None

    async def format_response(self, chunk, response_id=None):
        return {"content": chunk.content}

    async def format_config(self):
        return None

    async def format_keepalive(self, raw):
        return None


def _make_session(session_id: str = "test-call") -> VoiceSession:
    return VoiceSession(
        session_id=session_id,
        conversation_id=uuid4(),
        client_id=uuid4(),
        organization_id=uuid4(),
        started_at=datetime.utcnow(),
        provider_type="mock",
    )


def _make_adapter(session_manager, notifier=None):
    mock_factory = MagicMock()
    return VoiceAdapter(
        provider=MockProvider(),
        session_manager=session_manager,
        session_factory=mock_factory,
        cache=None,
        notifier=notifier,
    )


@pytest.mark.asyncio
async def test_on_user_speech_runs_pipeline():
    """on_user_speech should run the pipeline and yield voice chunks."""
    cache = FakeRedisCache()
    manager = VoiceSessionManager(cache)

    session = _make_session("call-speech")
    await manager.create("call-speech", session)

    mock_db_session = AsyncMock()

    @asynccontextmanager
    async def fake_factory():
        @asynccontextmanager
        async def begin():
            yield
        mock_db_session.begin = begin
        yield mock_db_session

    adapter = VoiceAdapter(
        provider=MockProvider(),
        session_manager=manager,
        session_factory=fake_factory,
        cache=None,
    )

    # Mock PipelineRunner
    with patch("prosales.channels.voice.adapter.PipelineRunner") as MockRunner:
        mock_runner_instance = AsyncMock()
        mock_result = MagicMock()
        mock_result.voice_text = "Hola, bienvenido. ¿En qué puedo ayudarte?"
        mock_runner_instance.run.return_value = mock_result
        MockRunner.return_value = mock_runner_instance

        chunks = []
        async for chunk in adapter.on_user_speech("call-speech", "Hola"):
            chunks.append(chunk)

        assert len(chunks) >= 1
        assert all(isinstance(c, VoiceChunk) for c in chunks)
        # Last chunk should have end_of_turn=True
        assert chunks[-1].end_of_turn is True
        # Content should be present
        combined = " ".join(c.content for c in chunks)
        assert "Hola" in combined


@pytest.mark.asyncio
async def test_on_user_silence_uses_synthetic():
    """on_user_silence should pass synthetic silence message to pipeline."""
    cache = FakeRedisCache()
    manager = VoiceSessionManager(cache)

    session = _make_session("call-silence")
    await manager.create("call-silence", session)

    mock_db_session = AsyncMock()

    @asynccontextmanager
    async def fake_factory():
        @asynccontextmanager
        async def begin():
            yield
        mock_db_session.begin = begin
        yield mock_db_session

    adapter = VoiceAdapter(
        provider=MockProvider(),
        session_manager=manager,
        session_factory=fake_factory,
        cache=None,
    )

    with patch("prosales.channels.voice.adapter.PipelineRunner") as MockRunner:
        mock_runner_instance = AsyncMock()
        mock_result = MagicMock()
        mock_result.voice_text = "¿Sigues ahí?"
        mock_runner_instance.run.return_value = mock_result
        MockRunner.return_value = mock_runner_instance

        chunks = []
        async for chunk in adapter.on_user_silence("call-silence"):
            chunks.append(chunk)

        # Verify pipeline was called with synthetic silence message
        assert "[silencio del cliente]" in str(mock_runner_instance.run.call_args)


@pytest.mark.asyncio
async def test_streaming_yields_sentences():
    """Streaming should split response into sentence chunks."""
    cache = FakeRedisCache()
    manager = VoiceSessionManager(cache)

    session = _make_session("call-stream")
    await manager.create("call-stream", session)

    mock_db_session = AsyncMock()

    @asynccontextmanager
    async def fake_factory():
        @asynccontextmanager
        async def begin():
            yield
        mock_db_session.begin = begin
        yield mock_db_session

    adapter = VoiceAdapter(
        provider=MockProvider(),
        session_manager=manager,
        session_factory=fake_factory,
        cache=None,
    )

    with patch("prosales.channels.voice.adapter.PipelineRunner") as MockRunner:
        mock_runner_instance = AsyncMock()
        mock_result = MagicMock()
        mock_result.voice_text = "Primera oración. Segunda oración. Tercera oración."
        mock_runner_instance.run.return_value = mock_result
        MockRunner.return_value = mock_runner_instance

        chunks = []
        async for chunk in adapter.on_user_speech("call-stream", "test"):
            chunks.append(chunk)

        assert len(chunks) == 3
        assert chunks[0].end_of_turn is False
        assert chunks[1].end_of_turn is False
        assert chunks[2].end_of_turn is True


@pytest.mark.asyncio
async def test_on_session_end_triggers_cleanup():
    """on_session_end should clean up Redis session."""
    cache = FakeRedisCache()
    manager = VoiceSessionManager(cache)

    session = _make_session("call-end")
    await manager.create("call-end", session)

    mock_db_session = AsyncMock()
    mock_db_session.execute = AsyncMock()

    @asynccontextmanager
    async def fake_factory():
        @asynccontextmanager
        async def begin():
            yield
        mock_db_session.begin = begin
        yield mock_db_session

    adapter = VoiceAdapter(
        provider=MockProvider(),
        session_manager=manager,
        session_factory=fake_factory,
        cache=None,
    )

    # Patch DB model and episodic imports used inside on_session_end
    with patch("prosales.infrastructure.database.models_voice.VoiceCallModel") as MockVCM:
        MockVCM.session_id = "session_id"
        await adapter.on_session_end("call-end", "normal")

    # Session should be deleted from Redis
    result = await manager.get("call-end")
    assert result is None


@pytest.mark.asyncio
async def test_on_session_start_creates_conversation():
    """on_session_start should create conversation and Redis session."""
    cache = FakeRedisCache()
    manager = VoiceSessionManager(cache)

    mock_db_session = AsyncMock()
    mock_db_session.add = MagicMock()
    mock_db_session.flush = AsyncMock()

    @asynccontextmanager
    async def fake_factory():
        @asynccontextmanager
        async def begin():
            yield
        mock_db_session.begin = begin
        yield mock_db_session

    adapter = VoiceAdapter(
        provider=MockProvider(),
        session_manager=manager,
        session_factory=fake_factory,
        cache=None,
    )

    mock_client = MagicMock()
    mock_client.id = uuid4()

    with patch("prosales.channels.voice.adapter.SQLClientRepository") as MockClientRepo, \
         patch("prosales.channels.voice.adapter.SQLConversationRepository") as MockConvRepo, \
         patch("prosales.infrastructure.database.models_voice.VoiceCallModel"):
        mock_client_repo = AsyncMock()
        mock_client_repo.get_or_create.return_value = mock_client
        MockClientRepo.return_value = mock_client_repo

        mock_conv_repo = AsyncMock()
        MockConvRepo.return_value = mock_conv_repo

        await adapter.on_session_start("call-new", {"from_number": "+1234"})

    # Redis session should exist
    stored = await manager.get("call-new")
    assert stored is not None
    assert stored.session_id == "call-new"
    assert stored.from_number == "+1234"
