"""Tests for the Strategy ↔ learned-cluster bridge."""

from uuid import uuid4

import pytest

from learning_engine.core.enums import StrategyType
from learning_engine.engines.strategy.evidence_bridge import (
    MOVE_KIND_TO_CATEGORY,
    StrategyEvidenceBridge,
    category_of_strategy,
    move_kinds_for_strategy,
)
from learning_engine.engines.strategy.taxonomy import StrategyCategory


def test_real_strategy_type_resolves_to_move_kinds():
    kinds = move_kinds_for_strategy(StrategyType.CONSULTIVE)
    assert "discovery" in kinds  # consultive is a discovery-category strategy


def test_string_strategy_type_accepted():
    assert move_kinds_for_strategy("consultive") == move_kinds_for_strategy(StrategyType.CONSULTIVE)


def test_unknown_strategy_returns_empty():
    assert move_kinds_for_strategy("not_a_strategy") == []
    assert category_of_strategy("not_a_strategy") is None


def test_every_move_kind_maps_to_a_category():
    for cat in MOVE_KIND_TO_CATEGORY.values():
        assert isinstance(cat, StrategyCategory)


class _Cluster:
    def __init__(self, move_kind, success, occ):
        self.move_kind = move_kind
        self.success_rate = success
        self.occurrence_count = occ


class _FakePerf:
    def __init__(self, clusters):
        self._clusters = clusters

    async def list_clusters(self, agent_version_id, move_kind=None, polarity=None):
        return list(self._clusters)


@pytest.mark.asyncio
async def test_performance_by_category_aggregates_weighted():
    bridge = StrategyEvidenceBridge.__new__(StrategyEvidenceBridge)
    bridge.performance = _FakePerf([
        _Cluster("objection_handling", 1.0, 3),
        _Cluster("reframe", 0.5, 1),  # same category (objection_handling)
        _Cluster("closing", 0.8, 2),
    ])
    result = await bridge.performance_by_category(uuid4())
    by_cat = {r["category"]: r for r in result}
    # objection_handling: (1.0*3 + 0.5*1) / 4 = 0.875
    assert by_cat["objection_handling"]["success_rate"] == 0.875
    assert by_cat["objection_handling"]["occurrences"] == 4
    # sorted by success_rate desc
    assert result[0]["success_rate"] >= result[-1]["success_rate"]
