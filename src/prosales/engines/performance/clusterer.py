"""PatternClusterer — group similar moves; clusters compete by success_rate.

On approval a move is embedded and attached to the nearest cluster of the same
(agent, move_kind, polarity) above a cosine threshold, or seeds a new cluster.
Aggregates (occurrence_count, success_rate, avg_score, centroid, condition
profile) are recomputed, then clusters are re-ranked so retrieval can prefer the
winner. This is what turns single-conversation evidence into historical
performance.
"""

from uuid import UUID

from prosales.core.similarity import SIMILARITY_THRESHOLD, cosine
from prosales.core.similarity import to_list as _to_list
from prosales.engines.moves.models import ConversationMove
from prosales.infrastructure.database.models_performance import PatternClusterModel
from prosales.infrastructure.database.repositories.performance import (
    SQLPerformanceRepository,
)


def _merge_conditions(profile: dict, conditions: dict) -> dict:
    profile = dict(profile or {})
    works = conditions.get("works_when") if isinstance(conditions, dict) else None
    if works:
        bucket = dict(profile.get("works_when", {}))
        for cond in works:
            key = str(cond)
            bucket[key] = bucket.get(key, 0) + 1
        profile["works_when"] = bucket
    return profile


class PatternClusterer:
    def __init__(self, performance_repo: SQLPerformanceRepository):
        self.repo = performance_repo

    async def assign(
        self,
        move: ConversationMove,
        embedding: list[float],
        candidate_move_kinds: list[str] | None = None,
    ) -> UUID:
        """Attach ``move`` to its nearest cluster, or seed a new one.

        ``candidate_move_kinds``, when given, widens the merge search beyond
        the move's own ``move_kind`` (e.g. sibling kinds in the same strategy
        category) — the semantic bar (``cosine >= SIMILARITY_THRESHOLD``) stays
        the same, only the candidate pool grows. Defaults to the move's own
        kind, i.e. today's exact-match search.
        """
        worked = 1 if move.score >= 0.5 else 0
        candidates = await self.repo.list_clusters(
            move.agent_version_id,
            move_kind=candidate_move_kinds or move.move_kind,
            polarity=move.polarity,
        )

        best: PatternClusterModel | None = None
        best_sim = 0.0
        for c in candidates:
            centroid = _to_list(c.centroid)
            sim = cosine(embedding, centroid) if centroid else 0.0
            if sim > best_sim:
                best_sim, best = sim, c

        if best is not None and best_sim >= SIMILARITY_THRESHOLD:
            cluster = await self._attach(best, move, embedding, worked)
        else:
            cluster = await self._create(move, embedding, worked)

        await self.repo.rerank(move.agent_version_id, move.move_kind)
        return cluster.id

    async def recompute_cluster(
        self, cluster_id: UUID, moves: list[ConversationMove]
    ) -> None:
        """Recalculate a cluster's aggregates from its member moves (idempotent).

        Used when member scores change (e.g. CRM outcome arrives), so success_rate
        and rank reflect the new reality.
        """
        cluster = await self.repo.get_cluster(cluster_id)
        if cluster is None or not moves:
            return
        n = len(moves)
        positive = sum(1 for m in moves if m.score >= 0.5)
        cluster.occurrence_count = n
        cluster.positive_count = positive
        cluster.negative_count = n - positive
        cluster.success_rate = round(positive / n, 4)
        cluster.avg_score = round(sum(m.score for m in moves) / n, 4)
        await self.repo.touch(cluster)
        await self.repo.rerank(cluster.agent_version_id, cluster.move_kind)

    async def _create(
        self, move: ConversationMove, embedding: list[float], worked: int
    ) -> PatternClusterModel:
        model = PatternClusterModel(
            agent_version_id=move.agent_version_id,
            organization_id=move.organization_id,
            move_kind=move.move_kind,
            polarity=move.polarity,
            canonical_excerpt=move.transcript_excerpt,
            centroid=embedding,
            occurrence_count=1,
            positive_count=worked,
            negative_count=1 - worked,
            success_rate=float(worked),
            avg_score=round(move.score, 4),
            condition_profile=_merge_conditions({}, move.conditions),
        )
        return await self.repo.create_cluster(model)

    async def _attach(
        self,
        cluster: PatternClusterModel,
        move: ConversationMove,
        embedding: list[float],
        worked: int,
    ) -> PatternClusterModel:
        n_old = cluster.occurrence_count
        n_new = n_old + 1
        cluster.occurrence_count = n_new
        cluster.positive_count += worked
        cluster.negative_count += 1 - worked
        cluster.success_rate = round(cluster.positive_count / n_new, 4)
        cluster.avg_score = round((cluster.avg_score * n_old + move.score) / n_new, 4)

        old_centroid = _to_list(cluster.centroid) or embedding
        cluster.centroid = [
            (o * n_old + e) / n_new for o, e in zip(old_centroid, embedding)
        ]
        if move.score >= cluster.avg_score:
            cluster.canonical_excerpt = move.transcript_excerpt
        cluster.condition_profile = _merge_conditions(cluster.condition_profile, move.conditions)
        await self.repo.touch(cluster)
        return cluster
