"""Tests for LearningEngine — effectiveness evaluation and event emission."""

import pytest
from unittest.mock import AsyncMock

from prosales.core.enums import Intent, Sentiment, StrategyType
from prosales.core.models.analysis import AnalysisResult, IntentResult, SentimentResult
from prosales.engines.learning.engine import LearningEngine, evaluate_effectiveness
from prosales.engines.strategy.models import StrategySelection


@pytest.mark.asyncio
async def test_learning_evaluates_effectiveness():
    engine = LearningEngine()
    state = {
        "strategy": StrategySelection(strategy_type=StrategyType.CONSULTIVE),
        "analysis": AnalysisResult(
            sentiment=SentimentResult(sentiment=Sentiment.POSITIVE, score=0.5),
        ),
        "initial_sentiment": "neutral",
    }
    result = await engine.process(state)
    assert "learning" in result
    assert "effectiveness_score" in result["learning"]
    assert 0.0 <= result["learning"]["effectiveness_score"] <= 1.0


@pytest.mark.asyncio
async def test_learning_emits_event():
    mock_store = AsyncMock()
    engine = LearningEngine(event_store=mock_store)
    state = {
        "strategy": StrategySelection(strategy_type=StrategyType.CONSULTIVE),
        "analysis": AnalysisResult(
            sentiment=SentimentResult(sentiment=Sentiment.POSITIVE, score=0.5),
        ),
        "initial_sentiment": "neutral",
    }
    await engine.process(state)
    mock_store.store.assert_called_once()
    event = mock_store.store.call_args[0][0]
    assert event.event_type == "strategy.evaluated"
    assert "effectiveness_score" in event.data


@pytest.mark.asyncio
async def test_learning_no_strategy_returns_empty():
    engine = LearningEngine()
    result = await engine.process({"analysis": AnalysisResult()})
    assert result == {}


def test_effectiveness_improves_with_positive_shift():
    # neutral → positive = improvement
    score_improved = evaluate_effectiveness("neutral", "positive")
    # neutral → negative = decline
    score_declined = evaluate_effectiveness("neutral", "negative")
    assert score_improved > score_declined
