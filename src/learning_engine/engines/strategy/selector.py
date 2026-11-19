"""Strategy selector — combines signals from independent scorers."""

from learning_engine.core.enums import StrategyType
from learning_engine.core.models.analysis import AnalysisResult
from learning_engine.core.models.execution import StrategyTrace
from learning_engine.engines.strategy.catalog import STRATEGY_CATALOG
from learning_engine.engines.strategy.scorers import DEFAULT_SCORERS, BaseScorer

_BASE_SCORE = 0.3

# Strategies whose tactics assume a prior (closed) relationship with the client
# ("reference their previous interest", "since their last interaction"). Without
# any episodic history that past does not exist, so these must never be selected
# on a first contact — a misclassified follow_up intent would otherwise make the
# agent fabricate a shared history. See REACTIVATION tactics in the catalog.
_RELATIONSHIP_DEPENDENT = frozenset({StrategyType.REACTIVATION.value})


def select_strategy(
    analysis: AnalysisResult,
    current_strategy: StrategyType | None = None,
    attempts: int = 0,
    client_episodes: list | None = None,
    conversation_stage: str | None = None,
    scorers: list[BaseScorer] | None = None,
) -> tuple[StrategyType, StrategyTrace]:
    """Select best strategy based on analysis signals. Returns strategy and trace."""
    scorers = scorers or DEFAULT_SCORERS
    all_strategies = list(STRATEGY_CATALOG.keys())

    # 1. Base score for all strategies in catalog
    combined: dict[str, float] = {s.value: _BASE_SCORE for s in all_strategies}

    # 2. Collect signals from each scorer
    context = dict(analysis=analysis, episodes=client_episodes, stage=conversation_stage)
    signals = []
    for scorer in scorers:
        signal = scorer.score(all_strategies, **context)
        signals.append(signal)
        for st, delta in signal.scores.items():
            combined[st] = combined.get(st, _BASE_SCORE) + delta

    # Round scores
    combined = {k: round(v, 2) for k, v in combined.items()}

    # Drop relationship-dependent strategies when there is no prior relationship
    # evidence, so they can never win on a first contact (see _RELATIONSHIP_DEPENDENT).
    if not client_episodes:
        for strategy_value in _RELATIONSHIP_DEPENDENT:
            combined.pop(strategy_value, None)

    # 3. Sort candidates
    candidates = sorted(combined.keys(), key=lambda k: combined[k], reverse=True)
    switched = False

    # 4. Switch logic: if current strategy failed too many times
    if current_strategy and attempts >= 3:
        alternatives = [s for s in all_strategies if s != current_strategy]
        # Pick highest-scored alternative
        alt_sorted = sorted(alternatives, key=lambda s: combined.get(s.value, 0), reverse=True)
        selected = alt_sorted[0] if alt_sorted else StrategyType.CONSULTIVE
        switched = True
    else:
        selected = StrategyType(candidates[0]) if candidates else StrategyType.CONSULTIVE

    # Build signal breakdown for observability
    signal_breakdown = {sig.source: sig.scores for sig in signals if sig.scores}

    trace = StrategyTrace(
        selected=selected.value,
        candidates=candidates,
        scores=combined,
        reason=f"Intent={analysis.intent.intent.value} → {selected.value} ({combined.get(selected.value, 0)})",
        switched=switched,
    )

    return selected, trace
