"""Tests for MemoryEngine episodic enhancement — loading structured episodes."""

from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from prosales.engines.memory.engine import MemoryEngine


def _make_episodic_model(
    conversation_id=None, dominant_intent="inquiry", dominant_sentiment="positive",
    objections=None, strategies=None, outcome="follow_up", closed_at=None,
):
    model = MagicMock()
    model.conversation_id = conversation_id or uuid4()
    model.dominant_intent = dominant_intent
    model.dominant_sentiment = dominant_sentiment
    model.objections_detected = objections or []
    model.strategies_used = strategies or []
    model.outcome = outcome
    model.closed_at = closed_at or datetime(2026, 7, 13, 10, 0, 0)
    return model


def _factory():
    """A session_factory yielding a dummy session (repos are patched out)."""
    @asynccontextmanager
    async def _sf():
        yield MagicMock()
    return _sf


async def _run(conversation_repo, client_repo, episodic_repo, use_episodic):
    """Run MemoryEngine.process with the repo classes patched to return the
    injected mocks (the engine builds them from its short session internally)."""
    engine = MemoryEngine(_factory(), use_episodic=use_episodic)
    mod = "prosales.engines.memory.engine"
    with patch(f"{mod}.SQLConversationRepository", return_value=conversation_repo), \
         patch(f"{mod}.SQLClientRepository", return_value=client_repo), \
         patch(f"{mod}.SQLEpisodicRepository", return_value=episodic_repo):
        return await engine.process({"conversation_id": uuid4(), "client_id": uuid4()})


class TestMemoryEngineEpisodic:
    @pytest.mark.asyncio
    async def test_load_with_episodes(self):
        conversation_repo = AsyncMock()
        conversation_repo.get_messages.return_value = []
        conversation_repo.get_by_client.return_value = []

        client_repo = AsyncMock()
        client_repo.get_memories.return_value = []

        episodic_repo = AsyncMock()
        episodic_repo.get_by_client.return_value = [
            _make_episodic_model(
                dominant_intent="objection",
                objections=["price", "timing"],
                strategies=["empathy", "price_defense"],
                outcome="follow_up",
            ),
        ]

        result = await _run(conversation_repo, client_repo, episodic_repo, use_episodic=True)

        memory = result["memory"]
        assert len(memory.episodic.client_episodes) == 1
        ep = memory.episodic.client_episodes[0]
        assert ep.dominant_intent == "objection"
        assert ep.objections_detected == ["price", "timing"]
        assert ep.strategies_used == ["empathy", "price_defense"]
        assert ep.outcome == "follow_up"

    @pytest.mark.asyncio
    async def test_backward_compat_without_repo(self):
        conversation_repo = AsyncMock()
        conversation_repo.get_messages.return_value = []
        conversation_repo.get_by_client.return_value = []

        client_repo = AsyncMock()
        client_repo.get_memories.return_value = []

        # use_episodic=False → episodic repo never consulted
        result = await _run(conversation_repo, client_repo, AsyncMock(), use_episodic=False)

        memory = result["memory"]
        assert memory.episodic.client_episodes == []
        assert memory.episodic.last_interaction_summary == ""

    @pytest.mark.asyncio
    async def test_last_interaction_summary_factual(self):
        conversation_repo = AsyncMock()
        conversation_repo.get_messages.return_value = []
        conversation_repo.get_by_client.return_value = []

        client_repo = AsyncMock()
        client_repo.get_memories.return_value = []

        episodic_repo = AsyncMock()
        episodic_repo.get_by_client.return_value = [
            _make_episodic_model(
                dominant_intent="inquiry",
                objections=["price"],
                strategies=["consultive"],
                outcome="sale_closed",
            ),
        ]

        result = await _run(conversation_repo, client_repo, episodic_repo, use_episodic=True)

        summary = result["memory"].episodic.last_interaction_summary
        assert "outcome=sale_closed" in summary
        assert "intent=inquiry" in summary
        assert "objeciones=price" in summary
        assert "estrategias=consultive" in summary
