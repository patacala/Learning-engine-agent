"""Tests for EpisodeExtractor — deterministic fact extraction from events."""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from prosales.engines.episodic.extractor import EpisodeExtractor


def _make_event(event_type: str, data: dict, ts_offset_seconds: int = 0):
    """Create a mock EventModel."""
    event = MagicMock()
    event.event_type = event_type
    event.data = data
    event.timestamp = datetime(2026, 7, 13, 10, 0, 0) + timedelta(seconds=ts_offset_seconds)
    return event


def _make_conversation(client_id=None, org_id=None, stage="negotiation"):
    conv = MagicMock()
    conv.id = uuid4()
    conv.client_id = client_id or uuid4()
    conv.organization_id = org_id
    conv.stage = stage
    conv.created_at = datetime(2026, 7, 13, 10, 0, 0)
    return conv


class TestDominantIntent:
    @pytest.mark.asyncio
    async def test_most_frequent_intent_wins(self):
        conv = _make_conversation()
        events = [
            _make_event("analyzer.completed", {"intent": "inquiry"}, 0),
            _make_event("analyzer.completed", {"intent": "objection"}, 10),
            _make_event("analyzer.completed", {"intent": "inquiry"}, 20),
            _make_event("analyzer.completed", {"intent": "inquiry"}, 30),
        ]
        event_repo = AsyncMock()
        event_repo.get_by_conversation.return_value = events
        conv_repo = AsyncMock()
        conv_repo.get_by_id.return_value = conv
        conv_repo.get_messages.return_value = [MagicMock(), MagicMock()]

        extractor = EpisodeExtractor(event_repo, conv_repo)
        episode = await extractor.extract(conv.id)

        assert episode.dominant_intent == "inquiry"


class TestDominantSentiment:
    @pytest.mark.asyncio
    async def test_most_frequent_sentiment_wins(self):
        conv = _make_conversation()
        events = [
            _make_event("analyzer.completed", {"sentiment": "positive"}, 0),
            _make_event("analyzer.completed", {"sentiment": "negative"}, 10),
            _make_event("analyzer.completed", {"sentiment": "positive"}, 20),
        ]
        event_repo = AsyncMock()
        event_repo.get_by_conversation.return_value = events
        conv_repo = AsyncMock()
        conv_repo.get_by_id.return_value = conv
        conv_repo.get_messages.return_value = []

        extractor = EpisodeExtractor(event_repo, conv_repo)
        episode = await extractor.extract(conv.id)

        assert episode.dominant_sentiment == "positive"


class TestSentimentShifts:
    @pytest.mark.asyncio
    async def test_counts_shifts(self):
        conv = _make_conversation()
        events = [
            _make_event("analyzer.completed", {"sentiment": "positive"}, 0),
            _make_event("analyzer.completed", {"sentiment": "negative"}, 10),
            _make_event("analyzer.completed", {"sentiment": "negative"}, 20),
            _make_event("analyzer.completed", {"sentiment": "positive"}, 30),
        ]
        event_repo = AsyncMock()
        event_repo.get_by_conversation.return_value = events
        conv_repo = AsyncMock()
        conv_repo.get_by_id.return_value = conv
        conv_repo.get_messages.return_value = []

        extractor = EpisodeExtractor(event_repo, conv_repo)
        episode = await extractor.extract(conv.id)

        assert episode.sentiment_shifts == 2  # pos→neg, neg→pos


class TestObjections:
    @pytest.mark.asyncio
    async def test_collects_objections(self):
        conv = _make_conversation()
        events = [
            _make_event("analyzer.completed", {"intent": "objection", "intent_detail": "price"}, 0),
            _make_event("analyzer.completed", {"intent": "inquiry"}, 10),
            _make_event("analyzer.completed", {"intent": "objection", "intent_detail": "timing"}, 20),
            _make_event("analyzer.completed", {"intent": "objection", "intent_detail": "price"}, 30),
        ]
        event_repo = AsyncMock()
        event_repo.get_by_conversation.return_value = events
        conv_repo = AsyncMock()
        conv_repo.get_by_id.return_value = conv
        conv_repo.get_messages.return_value = []

        extractor = EpisodeExtractor(event_repo, conv_repo)
        episode = await extractor.extract(conv.id)

        assert "price" in episode.objections_detected
        assert "timing" in episode.objections_detected
        assert len(episode.objections_detected) == 2  # unique


class TestStrategies:
    @pytest.mark.asyncio
    async def test_collects_unique_strategies(self):
        conv = _make_conversation()
        events = [
            _make_event("strategy.selected", {"strategy_type": "consultive"}, 0),
            _make_event("strategy.selected", {"strategy_type": "price_defense"}, 10),
            _make_event("strategy.selected", {"strategy_type": "consultive"}, 20),
        ]
        event_repo = AsyncMock()
        event_repo.get_by_conversation.return_value = events
        conv_repo = AsyncMock()
        conv_repo.get_by_id.return_value = conv
        conv_repo.get_messages.return_value = []

        extractor = EpisodeExtractor(event_repo, conv_repo)
        episode = await extractor.extract(conv.id)

        assert sorted(episode.strategies_used) == ["consultive", "price_defense"]


class TestSignals:
    @pytest.mark.asyncio
    async def test_collects_notable_signals(self):
        conv = _make_conversation()
        events = [
            _make_event("analyzer.completed", {"urgency": "high", "risk": "budget_risk"}, 0),
            _make_event("analyzer.completed", {"urgency": "low", "risk": "none"}, 10),
            _make_event("analyzer.completed", {"urgency": "high", "risk": "churn_risk"}, 20),
        ]
        event_repo = AsyncMock()
        event_repo.get_by_conversation.return_value = events
        conv_repo = AsyncMock()
        conv_repo.get_by_id.return_value = conv
        conv_repo.get_messages.return_value = []

        extractor = EpisodeExtractor(event_repo, conv_repo)
        episode = await extractor.extract(conv.id)

        assert "high" in episode.urgency_signals
        assert "budget_risk" in episode.risk_signals
        assert "churn_risk" in episode.risk_signals
        # "low" and "none" are filtered out
        assert "low" not in episode.urgency_signals
        assert "none" not in episode.risk_signals


class TestEmptyEvents:
    @pytest.mark.asyncio
    async def test_empty_events_return_empty_episode(self):
        conv = _make_conversation()
        event_repo = AsyncMock()
        event_repo.get_by_conversation.return_value = []
        conv_repo = AsyncMock()
        conv_repo.get_by_id.return_value = conv
        conv_repo.get_messages.return_value = []

        extractor = EpisodeExtractor(event_repo, conv_repo)
        episode = await extractor.extract(conv.id)

        assert episode.dominant_intent == ""
        assert episode.dominant_sentiment == ""
        assert episode.sentiment_shifts == 0
        assert episode.objections_detected == []
        assert episode.strategies_used == []
        assert episode.urgency_signals == []
        assert episode.risk_signals == []
        assert episode.duration_seconds == 0.0
        assert episode.message_count == 0
