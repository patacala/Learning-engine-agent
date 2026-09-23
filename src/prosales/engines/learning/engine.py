import logging
from typing import Any

from prosales.core.enums import Sentiment
from prosales.core.interfaces.engine import BaseEngine
from prosales.core.models.events import StrategyEvaluated
from prosales.engines.learning.event_store import EventStore

logger = logging.getLogger(__name__)

# Sentiment ordering for shift calculation
_SENTIMENT_ORDER = {
    Sentiment.VERY_NEGATIVE: 0,
    Sentiment.NEGATIVE: 1,
    Sentiment.NEUTRAL: 2,
    Sentiment.POSITIVE: 3,
    Sentiment.VERY_POSITIVE: 4,
}


def evaluate_effectiveness(
    pre_sentiment: str,
    post_sentiment: str,
    goal_achieved: bool = False,
) -> float:
    """Evaluate strategy effectiveness from sentiment shift and goal achievement.

    Returns a score between 0.0 and 1.0.
    """
    # Parse sentiments
    try:
        pre_val = _SENTIMENT_ORDER.get(Sentiment(pre_sentiment), 2)
    except ValueError:
        pre_val = 2
    try:
        post_val = _SENTIMENT_ORDER.get(Sentiment(post_sentiment), 2)
    except ValueError:
        post_val = 2

    # Shift component: -4 to +4, normalized to 0-0.5
    shift = post_val - pre_val
    shift_score = max(0.0, min(0.5, (shift + 2) / 8.0 * 1.0))
    # Normalize: shift of 0 → 0.25, shift of +4 → 0.5, shift of -4 → 0.0
    shift_score = (shift + 4) / 8.0 * 0.5

    # Goal component
    goal_score = 0.5 if goal_achieved else 0.0

    return round(min(1.0, shift_score + goal_score), 2)


class LearningEngine(BaseEngine):
    """Feedback loop: evaluates strategy effectiveness and emits learning events."""

    def __init__(self, event_store: EventStore | None = None):
        self.event_store = event_store

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        strategy = state.get("strategy")
        analysis = state.get("analysis")

        if not strategy or not analysis:
            return {}

        strategy_type = strategy.strategy_type
        if isinstance(strategy_type, str) and not strategy_type:
            return {}

        # Get pre/post sentiment
        pre_sentiment = state.get("initial_sentiment", "neutral")
        post_sentiment = analysis.sentiment.sentiment.value if analysis.sentiment else "neutral"

        # Evaluate effectiveness
        score = evaluate_effectiveness(pre_sentiment, post_sentiment)

        # Buffer the event; PipelineRunner flushes all pending events once at the end.
        stype = strategy_type.value if hasattr(strategy_type, "value") else str(strategy_type)
        event = StrategyEvaluated(data={
            "strategy_type": stype,
            "effectiveness_score": score,
            "pre_sentiment": pre_sentiment,
            "post_sentiment": post_sentiment,
        })
        execution = state.get("execution")
        if execution:
            event.conversation_id = execution.conversation_id
            event.client_id = execution.client_id
            execution.pending_events.append(event)
        elif self.event_store:
            try:
                await self.event_store.store(event)
            except Exception as e:
                logger.warning("Failed to store strategy.evaluated event: %s", e)

        return {"learning": {"effectiveness_score": score}}
