"""Signal Scorers — independent, testable, pluggable scoring components.

Each scorer calculates score deltas from a single signal source.
The selector combines all signals. Adding a new factor = new scorer class.
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel

from prosales.core.enums import Intent, Sentiment, StrategyType
from prosales.engines.strategy.taxonomy import STRATEGY_TAXONOMY


class StrategySignal(BaseModel):
    """Score contribution from a single source."""
    scores: dict[str, float] = {}
    source: str = ""


class BaseScorer(ABC):
    @abstractmethod
    def score(self, strategies: list[StrategyType], **context) -> StrategySignal:
        ...


# --- 1:N intent mapping ---
INTENT_STRATEGY_MAP: dict[Intent, list[StrategyType]] = {
    Intent.INQUIRY: [StrategyType.CONSULTIVE, StrategyType.NEEDS_DIAGNOSIS, StrategyType.EDUCATIONAL_SELLING],
    Intent.COMPARISON: [StrategyType.VALUE_FIRST, StrategyType.COMPARISON_ADVANTAGE],
    Intent.OBJECTION: [StrategyType.PRICE_DEFENSE, StrategyType.FEEL_FELT_FOUND, StrategyType.BOOMERANG],
    Intent.NEGOTIATION: [StrategyType.VALUE_FIRST, StrategyType.ANCHORING],
    Intent.SCHEDULING: [StrategyType.URGENCY, StrategyType.ASSUMPTIVE_CLOSE],
    Intent.GREETING: [StrategyType.RAPPORT_BUILDING],
    Intent.COMPLAINT: [StrategyType.EMPATHIC_LISTENING, StrategyType.ACKNOWLEDGE_REDIRECT],
    Intent.FOLLOW_UP: [StrategyType.FOLLOW_UP_VALUE, StrategyType.REACTIVATION],
}


class IntentScorer(BaseScorer):
    """Scores based on intent → strategy mapping (1:N)."""

    def score(self, strategies, *, analysis=None, **_) -> StrategySignal:
        scores: dict[str, float] = {}
        if not analysis:
            return StrategySignal(scores=scores, source="intent")

        intent = analysis.intent.intent
        confidence = analysis.intent.confidence
        mapped = INTENT_STRATEGY_MAP.get(intent, [])

        for i, strategy_type in enumerate(mapped):
            key = strategy_type.value if isinstance(strategy_type, StrategyType) else strategy_type
            if i == 0:
                scores[key] = 0.2 + 0.5 * confidence
            elif i == 1:
                scores[key] = 0.1 + 0.3 * confidence
            else:
                scores[key] = 0.05

        return StrategySignal(scores=scores, source="intent")


class SentimentScorer(BaseScorer):
    """Boosts empathic strategies for negative sentiment."""

    def score(self, strategies, *, analysis=None, **_) -> StrategySignal:
        scores: dict[str, float] = {}
        if not analysis:
            return StrategySignal(scores=scores, source="sentiment")

        sentiment = analysis.sentiment.sentiment
        if sentiment in (Sentiment.NEGATIVE, Sentiment.VERY_NEGATIVE):
            scores[StrategyType.PRICE_DEFENSE.value] = 0.1
            scores[StrategyType.EMPATHIC_LISTENING.value] = 0.1
            scores[StrategyType.URGENCY.value] = -0.1

        return StrategySignal(scores=scores, source="sentiment")


class StageScorer(BaseScorer):
    """Boosts strategies whose taxonomy stage_fit matches the current stage."""

    def score(self, strategies, *, stage=None, **_) -> StrategySignal:
        scores: dict[str, float] = {}
        if not stage:
            return StrategySignal(scores=scores, source="stage")

        for strategy_type in strategies:
            meta = STRATEGY_TAXONOMY.get(strategy_type)
            if meta and stage in meta.stage_fit:
                scores[strategy_type.value] = 0.15

        return StrategySignal(scores=scores, source="stage")


class EpisodicScorer(BaseScorer):
    """Boosts/penalizes based on historical outcomes with similar clients.

    +0.2 per episode where this strategy led to conversion.
    -0.15 per episode where this strategy was used and client was lost.
    Capped at ±0.3 total per strategy.
    """

    MAX_DELTA = 0.3

    def score(self, strategies, *, episodes=None, analysis=None, **_) -> StrategySignal:
        scores: dict[str, float] = {}
        if not episodes:
            return StrategySignal(scores=scores, source="episodic")

        # Accumulate per strategy
        raw: dict[str, float] = {}
        for episode in episodes:
            for strat_name in episode.strategies_used:
                if episode.outcome == "converted":
                    raw[strat_name] = raw.get(strat_name, 0.0) + 0.2
                elif episode.outcome == "lost":
                    raw[strat_name] = raw.get(strat_name, 0.0) - 0.15

        # Cap at ±MAX_DELTA
        for key, delta in raw.items():
            scores[key] = max(-self.MAX_DELTA, min(self.MAX_DELTA, delta))

        return StrategySignal(scores=scores, source="episodic")


DEFAULT_SCORERS: list[BaseScorer] = [
    IntentScorer(),
    SentimentScorer(),
    StageScorer(),
    EpisodicScorer(),
]
