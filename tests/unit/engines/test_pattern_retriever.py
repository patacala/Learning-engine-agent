"""Tests for PatternRetriever — contextual reuse of what worked."""

from uuid import uuid4

import pytest

from prosales.engines.expressions.models import Expression
from prosales.engines.knowledge.pattern_retriever import LearningContext, PatternRetriever

AGENT = uuid4()


class _Cluster:
    def __init__(self, move_kind, success_rate, excerpt, occ=2):
        self.move_kind = move_kind
        self.success_rate = success_rate
        self.canonical_excerpt = excerpt
        self.occurrence_count = occ


class _FakePerf:
    def __init__(self, clusters):
        self._clusters = sorted(clusters, key=lambda c: c.success_rate, reverse=True)

    async def list_clusters(self, agent_version_id, move_kind=None, polarity=None):
        return list(self._clusters)


class _FakeExpr:
    def __init__(self, winning, anti):
        self._by_polarity = {"winning": winning, "anti": anti}

    async def list_by_agent(self, agent_version_id, polarity=None, limit=100):
        return list(self._by_polarity.get(polarity, []))[:limit]


class _FakeInsights:
    def __init__(self, rules):
        self._rules = rules

    async def behavior_rules(self, agent_version_id, query_embedding=None):
        return list(self._rules)


def _expr(phrase, polarity, success):
    return Expression(exact_phrase=phrase, polarity=polarity, success_rate=success)


async def _run(perf, expr, insights, agent=AGENT, move_kinds=None, stage=None,
               client_state=None, limit=3):
    """Call the pure retrieval logic directly with fake repos (bypasses the
    session_factory, which is exercised in integration/e2e)."""
    r = PatternRetriever.__new__(PatternRetriever)
    return await r._retrieve(perf, expr, insights, agent, move_kinds, stage, client_state, limit)


@pytest.mark.asyncio
async def test_only_winning_plays_above_threshold_surface():
    perf = _FakePerf([
        _Cluster("closing", 0.9, "Book the test drive"),
        _Cluster("closing", 0.3, "Weak close"),  # below MIN_SUCCESS
    ])
    ctx = await _run(perf, _FakeExpr([], []), _FakeInsights([]))
    assert len(ctx.proven_plays) == 1
    assert ctx.proven_plays[0]["excerpt"] == "Book the test drive"


@pytest.mark.asyncio
async def test_move_kinds_filter_scopes_plays():
    perf = _FakePerf([
        _Cluster("closing", 0.9, "close phrase"),
        _Cluster("discovery", 0.8, "discovery phrase"),
    ])
    ctx = await _run(perf, _FakeExpr([], []), _FakeInsights([]), move_kinds=["discovery"])
    assert [p["move_kind"] for p in ctx.proven_plays] == ["discovery"]


@pytest.mark.asyncio
async def test_expressions_and_rules_included():
    ctx = await _run(
        _FakePerf([]),
        _FakeExpr(
            winning=[_expr("Tiene sentido tu duda", "winning", 0.8), _expr("weak", "winning", 0.2)],
            anti=[_expr("Créame", "anti", 0.0)],
        ),
        _FakeInsights(["Validate before pricing"]),
    )
    assert ctx.winning_expressions == ["Tiene sentido tu duda"]  # low-success dropped
    assert ctx.anti_expressions == ["Créame"]
    assert ctx.behavior_rules == ["Validate before pricing"]


def test_prompt_block_has_all_sections():
    ctx = LearningContext(
        proven_plays=[{"move_kind": "reframe", "success_rate": 0.9, "excerpt": "reframe it"}],
        winning_expressions=["good phrase"],
        anti_expressions=["Créame"],
        behavior_rules=["Validate first"],
    )
    block = ctx.to_prompt_block()
    assert "REGLAS APRENDIDAS" in block
    assert "JUGADAS QUE FUNCIONAN" in block
    assert "FRASES GANADORAS" in block
    assert "EVITA ESTAS FRASES" in block


def test_empty_context_is_empty():
    assert LearningContext().is_empty()
    assert LearningContext().to_prompt_block() == ""
