from types import SimpleNamespace

from learning_engine.core.enums import ConversationStage, Intent, StrategyType
from learning_engine.core.models.analysis import AnalysisResult, IntentResult, StageResult
from learning_engine.engines.strategy.selector import select_strategy


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


def test_reactivation_suppressed_without_episodic_history():
    """REACTIVATION's tactics reference a past interaction ("reference their
    previous interest", "since their last interaction"). With no episodic history
    that past does not exist, so the strategy must not even be a candidate —
    otherwise a misclassified follow_up intent on a first contact makes the agent
    invent a shared history."""
    analysis = AnalysisResult(intent=IntentResult(intent=Intent.FOLLOW_UP, confidence=0.95))
    strategy_type, trace = select_strategy(analysis, client_episodes=None)
    assert strategy_type != StrategyType.REACTIVATION
    assert StrategyType.REACTIVATION.value not in trace.scores


def test_reactivation_available_with_episodic_history():
    """With real episodic history the strategy stays available (not over-suppressed)."""
    analysis = AnalysisResult(intent=IntentResult(intent=Intent.FOLLOW_UP, confidence=0.9))
    episode = SimpleNamespace(strategies_used=["reactivation"], outcome="converted")
    _, trace = select_strategy(analysis, client_episodes=[episode])
    assert StrategyType.REACTIVATION.value in trace.scores


def test_selector_combines_scorer_signals():
    """Stage scorer should boost closing strategies when in closing stage."""
    analysis = AnalysisResult(
        intent=IntentResult(intent=Intent.UNKNOWN, confidence=0.5),
        stage=StageResult(stage=ConversationStage.CLOSING, confidence=0.9),
    )
    strategy_type, trace = select_strategy(analysis, conversation_stage="closing")
    # Should pick a closing-stage strategy due to stage boost
    assert trace.scores.get(strategy_type.value, 0) > 0.3
