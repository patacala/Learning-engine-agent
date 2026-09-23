"""Tests for PatternClusterer — competing clusters and idempotent recompute."""

from uuid import uuid4

import pytest

from prosales.engines.moves.models import ConversationMove
from prosales.engines.performance.clusterer import PatternClusterer, cosine
from prosales.infrastructure.database.models_performance import PatternClusterModel

AGENT = uuid4()


class FakePerfRepo:
    def __init__(self):
        self.clusters: list[PatternClusterModel] = []

    async def list_clusters(self, agent_version_id, move_kind=None, polarity=None):
        kinds = {move_kind} if isinstance(move_kind, str) else move_kind
        return [
            c for c in self.clusters
            if c.agent_version_id == agent_version_id
            and (kinds is None or c.move_kind in kinds)
            and (polarity is None or c.polarity == polarity)
        ]

    async def get_cluster(self, cluster_id):
        return next((c for c in self.clusters if c.id == cluster_id), None)

    async def create_cluster(self, model):
        model.id = uuid4()
        self.clusters.append(model)
        return model

    async def touch(self, model):
        return None

    async def rerank(self, agent_version_id, move_kind):
        cs = await self.list_clusters(agent_version_id, move_kind=move_kind)
        for i, c in enumerate(
            sorted(cs, key=lambda c: (c.success_rate, c.occurrence_count, c.avg_score), reverse=True),
            start=1,
        ):
            c.rank = i


def _move(excerpt, score, polarity="positive", kind="objection_handling", conditions=None):
    return ConversationMove(
        evidence_source_id=uuid4(), agent_version_id=AGENT, move_kind=kind,
        transcript_excerpt=excerpt, polarity=polarity, score=score,
        conditions=conditions or {},
    )


def test_cosine_basic():
    assert cosine([1, 0, 0], [1, 0, 0]) == 1.0
    assert cosine([1, 0, 0], [0, 1, 0]) == 0.0


@pytest.mark.asyncio
async def test_similar_moves_merge_into_one_cluster():
    repo = FakePerfRepo()
    clusterer = PatternClusterer(repo)
    c1 = await clusterer.assign(_move("Muchos clientes tenían esa duda", 0.9), [1.0, 0.0, 0.0])
    c2 = await clusterer.assign(_move("Muchos clientes empezaron así", 0.8), [0.99, 0.1, 0.0])
    assert c1 == c2
    cluster = await repo.get_cluster(c1)
    assert cluster.occurrence_count == 2
    assert cluster.success_rate == 1.0  # both worked


@pytest.mark.asyncio
async def test_dissimilar_moves_form_competing_clusters_and_rank():
    repo = FakePerfRepo()
    clusterer = PatternClusterer(repo)
    # Two winners in cluster A
    await clusterer.assign(_move("A phrase one", 0.9), [1.0, 0.0, 0.0])
    await clusterer.assign(_move("A phrase two", 0.8), [0.98, 0.02, 0.0])
    # One loser in a distinct cluster B (same move_kind -> competes)
    await clusterer.assign(_move("B totally different", 0.2), [0.0, 1.0, 0.0])

    clusters = await repo.list_clusters(AGENT, move_kind="objection_handling")
    assert len(clusters) == 2
    winner = min(clusters, key=lambda c: c.rank)
    loser = max(clusters, key=lambda c: c.rank)
    assert winner.rank == 1 and winner.success_rate > loser.success_rate


@pytest.mark.asyncio
async def test_condition_profile_aggregates_works_when():
    repo = FakePerfRepo()
    clusterer = PatternClusterer(repo)
    cid = await clusterer.assign(
        _move("phrase", 0.9, conditions={"works_when": ["objecion de precio"]}), [1.0, 0.0, 0.0]
    )
    await clusterer.assign(
        _move("phrase two", 0.9, conditions={"works_when": ["objecion de precio"]}), [0.99, 0.01, 0.0]
    )
    cluster = await repo.get_cluster(cid)
    assert cluster.condition_profile["works_when"]["objecion de precio"] == 2


@pytest.mark.asyncio
async def test_candidate_move_kinds_widens_merge_search():
    """A sibling-kind move merges into an existing cluster when the caller
    widens the search via candidate_move_kinds (e.g. same strategy category)."""
    repo = FakePerfRepo()
    clusterer = PatternClusterer(repo)
    c1 = await clusterer.assign(
        _move("Muchos clientes tenían esa duda", 0.9, kind="objection_handling"),
        [1.0, 0.0, 0.0],
    )
    c2 = await clusterer.assign(
        _move("Muchos clientes empezaron así", 0.8, kind="reframe"),
        [0.99, 0.1, 0.0],
        candidate_move_kinds=["objection_handling", "reframe"],
    )
    assert c1 == c2
    cluster = await repo.get_cluster(c1)
    assert cluster.occurrence_count == 2


@pytest.mark.asyncio
async def test_default_candidate_move_kinds_is_exact_match_only():
    """Without candidate_move_kinds, a sibling-kind move never merges — proves
    today's exact-match behavior is unchanged when the caller passes nothing."""
    repo = FakePerfRepo()
    clusterer = PatternClusterer(repo)
    c1 = await clusterer.assign(
        _move("Muchos clientes tenían esa duda", 0.9, kind="objection_handling"),
        [1.0, 0.0, 0.0],
    )
    c2 = await clusterer.assign(
        _move("Muchos clientes empezaron así", 0.8, kind="reframe"),
        [0.99, 0.1, 0.0],
    )
    assert c1 != c2


@pytest.mark.asyncio
async def test_recompute_cluster_reflects_new_scores():
    repo = FakePerfRepo()
    clusterer = PatternClusterer(repo)
    cid = await clusterer.assign(_move("p1", 0.9), [1.0, 0.0, 0.0])
    await clusterer.assign(_move("p2", 0.9), [0.99, 0.0, 0.0])
    cluster = await repo.get_cluster(cid)
    assert cluster.success_rate == 1.0

    # CRM says these actually failed -> recompute with low scores.
    members = [_move("p1", 0.1), _move("p2", 0.2)]
    await clusterer.recompute_cluster(cid, members)
    assert cluster.success_rate == 0.0
    assert cluster.occurrence_count == 2
