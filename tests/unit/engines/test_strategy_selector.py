import pytest

from prosales.core.enums import Intent, Sentiment, StrategyType
from prosales.core.models.analysis import AnalysisResult, IntentResult, SentimentResult, StageResult
from prosales.core.enums import ConversationStage
from prosales.engines.strategy.selector import select_strategy


def test_consultive_for_inquiry():
    analysis = AnalysisResult(intent=IntentResult(intent=Intent.INQUIRY, confidence=0.85))
    strategy_type, trace = select_strategy(analysis)
    assert strategy_type == StrategyType.CONSULTIVE


def test_price_defense_for_objection():
    analysis = AnalysisResult(intent=IntentResult(intent=Intent.OBJECTION, confidence=0.9))
    strategy_type, trace = select_strategy(analysis)
    assert strategy_type == StrategyType.PRICE_DEFENSE


def test_switch_after_3_attempts():
    analysis = AnalysisResult(intent=IntentResult(intent=Intent.INQUIRY, confidence=0.8))
    strategy_type, trace = select_strategy(analysis, current_strategy=StrategyType.CONSULTIVE, attempts=3)
    assert strategy_type != StrategyType.CONSULTIVE
    assert trace.switched is True


def test_complaint_maps_to_empathic_listening():
    analysis = AnalysisResult(intent=IntentResult(intent=Intent.COMPLAINT, confidence=0.9))
    strategy_type, trace = select_strategy(analysis)
    assert strategy_type == StrategyType.EMPATHIC_LISTENING


def test_follow_up_maps_to_follow_up_value():
    analysis = AnalysisResult(intent=IntentResult(intent=Intent.FOLLOW_UP, confidence=0.85))
    strategy_type, trace = select_strategy(analysis)
    assert strategy_type == StrategyType.FOLLOW_UP_VALUE


def test_greeting_maps_to_rapport_building():
    analysis = AnalysisResult(intent=IntentResult(intent=Intent.GREETING, confidence=0.95))
    strategy_type, trace = select_strategy(analysis)
    assert strategy_type == StrategyType.RAPPORT_BUILDING


def test_selector_combines_scorer_signals():
    """Stage scorer should boost closing strategies when in closing stage."""
    analysis = AnalysisResult(
        intent=IntentResult(intent=Intent.UNKNOWN, confidence=0.5),
        stage=StageResult(stage=ConversationStage.CLOSING, confidence=0.9),
    )
    strategy_type, trace = select_strategy(analysis, conversation_stage="closing")
    # Should pick a closing-stage strategy due to stage boost
    assert trace.scores.get(strategy_type.value, 0) > 0.3
