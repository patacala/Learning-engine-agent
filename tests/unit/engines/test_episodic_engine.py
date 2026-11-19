"""Tests for EpisodicMemoryEngine — close conversation and persist episode."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from learning_engine.engines.episodic.engine import EpisodicMemoryEngine
from learning_engine.engines.episodic.models import Episode


def _make_episode(**kwargs):
    defaults = {
        "id": uuid4(),
        "conversation_id": uuid4(),
        "client_id": uuid4(),
        "dominant_intent": "inquiry",
        "dominant_sentiment": "positive",
        "strategies_used": ["consultive"],
        "message_count": 5,
    }
    defaults.update(kwargs)
    return Episode(**defaults)


class TestCloseConversation:
    @pytest.mark.asyncio
    async def test_close_stores_episode(self):
        episode = _make_episode()
        extractor = AsyncMock()
        extractor.extract.return_value = episode
        episodic_repo = AsyncMock()
        episodic_repo.save.return_value = MagicMock()

        engine = EpisodicMemoryEngine(extractor, episodic_repo)
        result = await engine.close_conversation(episode.conversation_id)

        assert result.conversation_id == episode.conversation_id
        assert result.dominant_intent == "inquiry"
        episodic_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_without_vector_store(self):
        episode = _make_episode()
        extractor = AsyncMock()
        extractor.extract.return_value = episode
        episodic_repo = AsyncMock()

        engine = EpisodicMemoryEngine(extractor, episodic_repo, vector_store=None)
        result = await engine.close_conversation(episode.conversation_id)

        assert result.outcome == "pending"
        episodic_repo.save.assert_called_once()
        # Verify the model passed to save has no embedding
        saved_model = episodic_repo.save.call_args[0][0]
        assert saved_model.embedding is None

    @pytest.mark.asyncio
    async def test_embedding_failure_is_graceful(self):
        episode = _make_episode()
        extractor = AsyncMock()
        extractor.extract.return_value = episode
        episodic_repo = AsyncMock()
        vector_store = AsyncMock()
        vector_store.embed_text.side_effect = Exception("OpenAI down")

        engine = EpisodicMemoryEngine(extractor, episodic_repo, vector_store=vector_store)
        # Should not raise
        result = await engine.close_conversation(episode.conversation_id)

        assert result.conversation_id == episode.conversation_id
        episodic_repo.save.assert_called_once()
