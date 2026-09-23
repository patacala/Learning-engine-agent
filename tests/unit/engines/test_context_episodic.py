"""Tests for ContextBuilder episodic enhancement — factual historical context."""

from datetime import datetime
from uuid import uuid4

import pytest

from prosales.engines.context_builder.engine import ContextBuilderEngine
from prosales.engines.episodic.models import EpisodeSummary
from prosales.engines.memory.models import EpisodicMemory, FullMemory, SemanticMemory, WorkingMemory


class TestContextBuilderEpisodic:
    @pytest.mark.asyncio
    async def test_appends_factual_episode_context(self):
        episodes = [
            EpisodeSummary(
                conversation_id=uuid4(),
                dominant_intent="objection",
                dominant_sentiment="negative",
                objections_detected=["price", "timing"],
                strategies_used=["empathy", "price_defense"],
                outcome="follow_up",
                closed_at=datetime(2026, 7, 12, 10, 0, 0),
            ),
        ]
        memory = FullMemory(
            working=WorkingMemory(),
            episodic=EpisodicMemory(
                total_interactions=3,
                client_episodes=episodes,
            ),
            semantic=SemanticMemory(),
        )
        engine = ContextBuilderEngine()
        result = await engine.process({
            "memory": memory,
            "current_message": "Hola",
        })

        context = result["context"]
        summary = context.conversation_summary
        assert "3 interacciones previas" in summary
        assert "outcome=follow_up" in summary
        assert "objeciones=price,timing" in summary
        assert "estrategias=empathy,price_defense" in summary

    @pytest.mark.asyncio
    async def test_no_episodes_unchanged(self):
        memory = FullMemory(
            working=WorkingMemory(),
            episodic=EpisodicMemory(total_interactions=1),
            semantic=SemanticMemory(),
        )
        engine = ContextBuilderEngine()
        result = await engine.process({
            "memory": memory,
            "current_message": "Hola",
        })

        context = result["context"]
        # With only 1 interaction, no summary generated
        assert context.conversation_summary == ""
