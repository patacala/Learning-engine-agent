"""Tests for StrategyEngine — multi-tactic, episodic passthrough, agent catalog override."""

import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

from learning_engine.core.enums import Intent, StrategyType
from learning_engine.core.models.analysis import AnalysisResult, IntentResult, StageResult
from learning_engine.core.enums import ConversationStage
from learning_engine.engines.strategy.engine import StrategyEngine


@pytest.mark.asyncio
async def test_multi_tactic_advances_position():
    engine = StrategyEngine()
    state = {
        "analysis": AnalysisResult(intent=IntentResult(intent=Intent.INQUIRY, confidence=0.9)),
        "current_strategy": "consultive",
        "strategy_attempts": 0,
        "tactic_position": 0,
    }
    result = await engine.process(state)
    selection = result["strategy"]
    # Same strategy selected → position should advance from 0 to 1
    assert selection.strategy_type == StrategyType.CONSULTIVE
    assert selection.tactic_position == 1
    assert selection.tactic_total == 2


@pytest.mark.asyncio
async def test_strategy_switch_resets_position():
    engine = StrategyEngine()
    state = {
        "analysis": AnalysisResult(intent=IntentResult(intent=Intent.OBJECTION, confidence=0.9)),
        "current_strategy": "consultive",  # Different from what will be selected
        "strategy_attempts": 0,
        "tactic_position": 2,
    }
    result = await engine.process(state)
    selection = result["strategy"]
    # Different strategy selected → position resets to 0
    assert selection.strategy_type == StrategyType.PRICE_DEFENSE
    assert selection.tactic_position == 0


@pytest.mark.asyncio
async def test_tactic_position_max_clamped():
    engine = StrategyEngine()
    state = {
        "analysis": AnalysisResult(intent=IntentResult(intent=Intent.INQUIRY, confidence=0.9)),
        "current_strategy": "consultive",
        "strategy_attempts": 0,
        "tactic_position": 10,  # Way beyond max
    }
    result = await engine.process(state)
    selection = result["strategy"]
    # Should clamp to last tactic (consultive has 2 tactics, max index = 1)
    assert selection.tactic_position == 1
    assert selection.tactic_total == 2


@pytest.mark.asyncio
async def test_episodic_data_passed_to_selector():
    """Engine should extract episodes from memory and pass to selector."""
    engine = StrategyEngine()
    # Without memory, should still work fine
    state = {
        "analysis": AnalysisResult(intent=IntentResult(intent=Intent.INQUIRY, confidence=0.8)),
        "current_strategy": None,
        "strategy_attempts": 0,
        "tactic_position": 0,
    }
    result = await engine.process(state)
    assert result["strategy"].strategy_type == StrategyType.CONSULTIVE


@pytest.mark.asyncio
async def test_agent_catalog_still_overrides():
    """When strategy_provider returns a catalog, it should override default."""
    mock_provider = AsyncMock()
    mock_strategy = type("S", (), {
        "strategy_type": "custom_strat",
        "name": "Custom",
        "triggers": [{"intent": "inquiry"}],
        "tactics": [
            type("T", (), {"prompt_instruction": "Do custom thing"})(),
        ],
    })()
    mock_provider.get.return_value = {"custom_strat": mock_strategy}

    ctx = type("Ctx", (), {
        "has_agent_capability": lambda self, c: True,
        "agent_version_id": uuid4(),
    })()

    engine = StrategyEngine(strategy_provider=mock_provider)
    state = {
        "analysis": AnalysisResult(intent=IntentResult(intent=Intent.INQUIRY, confidence=0.9)),
        "agent_context": ctx,
        "current_strategy": None,
        "strategy_attempts": 0,
        "tactic_position": 0,
    }
    result = await engine.process(state)
    assert result["strategy"].strategy_type == "custom_strat"
    assert result["strategy"].tactic_instruction == "Do custom thing"
