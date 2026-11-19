"""Strategy bridge — connect learned move clusters to the strategy catalog.

Conversation moves are grouped by ``move_kind``; the strategy engine works with
``StrategyType`` / ``StrategyCategory``. This bridge maps between them so that
(a) learned performance can be reported per strategy category and (b) the
PromptBuilder can retrieve the plays relevant to the strategy currently selected.
"""

from uuid import UUID

from learning_engine.core.enums import StrategyType
from learning_engine.engines.strategy.taxonomy import STRATEGY_TAXONOMY, StrategyCategory
from learning_engine.infrastructure.database.repositories.performance import (
    SQLPerformanceRepository,
)

# Each learned move_kind belongs to one strategy category.
MOVE_KIND_TO_CATEGORY: dict[str, StrategyCategory] = {
    "greeting": StrategyCategory.RAPPORT,
    "rapport": StrategyCategory.RAPPORT,
    "discovery": StrategyCategory.DISCOVERY,
    "needs_diagnosis": StrategyCategory.DISCOVERY,
    "qualification": StrategyCategory.DISCOVERY,
    "value_prop": StrategyCategory.PRESENTATION,
    "social_proof": StrategyCategory.PRESENTATION,
    "objection_handling": StrategyCategory.OBJECTION_HANDLING,
    "reframe": StrategyCategory.OBJECTION_HANDLING,
    "urgency": StrategyCategory.CLOSING,
    "closing": StrategyCategory.CLOSING,
    "follow_up": StrategyCategory.RETENTION,
}

CATEGORY_TO_MOVE_KINDS: dict[StrategyCategory, list[str]] = {}
for _mk, _cat in MOVE_KIND_TO_CATEGORY.items():
    CATEGORY_TO_MOVE_KINDS.setdefault(_cat, []).append(_mk)


def category_of_strategy(strategy_type) -> StrategyCategory | None:
    """Resolve a StrategyType (enum or str) to its StrategyCategory."""
    try:
        st = strategy_type if isinstance(strategy_type, StrategyType) else StrategyType(str(strategy_type))
    except ValueError:
        return None
    meta = STRATEGY_TAXONOMY.get(st)
    return meta.category if meta else None


def move_kinds_for_strategy(strategy_type) -> list[str]:
    """The learned move_kinds relevant to a selected strategy."""
    category = category_of_strategy(strategy_type)
    return CATEGORY_TO_MOVE_KINDS.get(category, []) if category else []


class StrategyEvidenceBridge:
    """Aggregate learned cluster performance per strategy category."""

    def __init__(self, session):
        self.performance = SQLPerformanceRepository(session)

    async def performance_by_category(self, agent_version_id: UUID) -> list[dict]:
        clusters = await self.performance.list_clusters(agent_version_id, polarity="positive")
        buckets: dict[str, dict] = {}
        for c in clusters:
            category = MOVE_KIND_TO_CATEGORY.get(c.move_kind)
            if category is None:
                continue
            b = buckets.setdefault(
                category.value, {"category": category.value, "weighted": 0.0, "occurrences": 0}
            )
            b["weighted"] += c.success_rate * c.occurrence_count
            b["occurrences"] += c.occurrence_count
        result = []
        for b in buckets.values():
            occ = b["occurrences"] or 1
            result.append(
                {
                    "category": b["category"],
                    "success_rate": round(b["weighted"] / occ, 4),
                    "occurrences": b["occurrences"],
                }
            )
        result.sort(key=lambda x: x["success_rate"], reverse=True)
        return result
