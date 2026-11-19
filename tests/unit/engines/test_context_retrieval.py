"""Tests for infer_client_state, retriever context filter, and outcome signals."""

from uuid import uuid4

import pytest

from learning_engine.engines.knowledge.pattern_retriever import PatternRetriever, _matches_state
from learning_engine.engines.moves.states import infer_client_state
from learning_engine.engines.performance.scorer import OutcomeScorer
from learning_engine.services.live_learning import outcome_signals


# --- infer_client_state ---

def test_infer_desconfiado_on_objection():
    assert infer_client_state("negative", "objection_handling", "objection") == "desconfiado"


def test_infer_listo_on_positive_close():
    assert infer_client_state("very_positive", "closing", "scheduling") == "listo_para_comprar"


def test_infer_frustrado_on_very_negative():
    assert infer_client_state("very_negative", "discovery", "complaint") == "frustrado"


def test_infer_none_when_unmapped():
    assert infer_client_state("neutral", "negotiation", "unknown") is None


# --- outcome → multi-signal ---

def test_outcome_signals_scheduled():
    appt, purchase = outcome_signals("scheduled")
    assert appt and not purchase


def test_outcome_signals_converted():
    appt, purchase = outcome_signals("converted")
    assert appt and purchase


def test_outcome_signals_lost():
    assert outcome_signals("lost") == (False, False)


def test_scorer_uses_signals():
    base = OutcomeScorer().score(client_state_before="desconfiado", client_state_after="tranquilo")
    boosted = OutcomeScorer().score(
        client_state_before="desconfiado",
        client_state_after="tranquilo",
        outcome="scheduled",
        appointment_scheduled=True,
    )
    assert boosted.score > base.score
    assert boosted.confidence > base.confidence


# --- retriever contextual soft filter ---

class _Cluster:
    def __init__(self, excerpt, success, works_when):
        self.move_kind = "objection_handling"
        self.success_rate = success
        self.canonical_excerpt = excerpt
        self.occurrence_count = 2
        self.condition_profile = {"works_when": {w: 1 for w in works_when}}


def test_matches_state_helper():
    c = _Cluster("x", 0.9, ["cliente desconfiado", "objecion de precio"])
    assert _matches_state(c, "desconfiado")
    assert not _matches_state(c, "frustrado")


class _FakePerf:
    def __init__(self, clusters):
        self._c = sorted(clusters, key=lambda c: c.success_rate, reverse=True)

    async def list_clusters(self, agent_version_id, move_kind=None, polarity=None):
        return list(self._c)


class _Empty:
    async def list_by_agent(self, *a, **k):
        return []

    async def behavior_rules(self, *a, **k):
        return []


@pytest.mark.asyncio
async def test_retrieve_prefers_matching_state():
    perf = _FakePerf([
        _Cluster("generic play", 0.95, ["objecion de precio"]),
        _Cluster("play for distrustful", 0.7, ["cliente desconfiado"]),
    ])
    r = PatternRetriever.__new__(PatternRetriever)
    ctx = await r._retrieve(perf, _Empty(), _Empty(), uuid4(), None, None, "desconfiado", 3)
    # Even though it has lower success, the state-matching play surfaces.
    assert ctx.proven_plays[0]["excerpt"] == "play for distrustful"


@pytest.mark.asyncio
async def test_retrieve_falls_back_when_no_state_match():
    perf = _FakePerf([_Cluster("generic play", 0.95, ["objecion de precio"])])
    r = PatternRetriever.__new__(PatternRetriever)
    ctx = await r._retrieve(perf, _Empty(), _Empty(), uuid4(), None, None, "frustrado", 3)
    assert ctx.proven_plays and ctx.proven_plays[0]["excerpt"] == "generic play"
