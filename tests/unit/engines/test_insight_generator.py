"""Tests for InsightGenerator — grounded, sample-gated conclusions."""

from uuid import uuid4

import pytest

from learning_engine.engines.insights.generator import InsightGenerator
from learning_engine.infrastructure.database.models_performance import PatternClusterModel


class _MockLLM:
    def __init__(self, payload):
        self.payload = payload

    async def complete(self, *a, **k): ...

    async def complete_json(self, messages, temperature=0.3):
        return self.payload


def _cluster(move_kind, success, occ, excerpt="phrase"):
    c = PatternClusterModel(
        agent_version_id=uuid4(),
        move_kind=move_kind,
        polarity="positive",
        canonical_excerpt=excerpt,
        occurrence_count=occ,
        success_rate=success,
        avg_score=success,
    )
    c.id = uuid4()
    return c


@pytest.mark.asyncio
async def test_no_insights_below_sample_gate():
    clusters = [_cluster("closing", 1.0, 1)]  # only 1 occurrence, 1 cluster
    gen = InsightGenerator(_MockLLM({"insights": [{"insight_text": "x"}]}), min_occurrences=2)
    assert await gen.generate(clusters) == []


@pytest.mark.asyncio
async def test_no_llm_returns_empty():
    clusters = [_cluster("closing", 1.0, 3), _cluster("reframe", 0.9, 4)]
    assert await InsightGenerator(None, min_occurrences=2).generate(clusters) == []


@pytest.mark.asyncio
async def test_generates_insight_with_grounding_guard():
    c1 = _cluster("reframe", 0.9, 5)
    c2 = _cluster("objection_handling", 0.2, 4)
    llm = _MockLLM({
        "insights": [{
            "insight_text": "Reframing price beats defending it.",
            "behavior_rule": "Reframe the price around total value.",
            "supporting_cluster_ids": [str(c1.id), "fabricated-id-not-in-input"],
        }]
    })
    insights = await InsightGenerator(llm, min_occurrences=2).generate([c1, c2])
    assert len(insights) == 1
    ins = insights[0]
    # Fabricated id is dropped (grounding guard); only real one kept.
    assert ins.supporting_cluster_ids == [str(c1.id)]
    assert ins.pattern_kinds == ["reframe"]
    assert ins.behavior_rule
    assert ins.sample_size == 5


@pytest.mark.asyncio
async def test_insight_without_text_skipped():
    c1 = _cluster("reframe", 0.9, 5)
    c2 = _cluster("closing", 0.8, 3)
    llm = _MockLLM({"insights": [{"insight_text": "  ", "behavior_rule": "x"}]})
    assert await InsightGenerator(llm, min_occurrences=2).generate([c1, c2]) == []
