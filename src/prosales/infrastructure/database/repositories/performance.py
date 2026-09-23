"""Repository for pattern clusters (Performance layer)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from prosales.infrastructure.database.models_performance import PatternClusterModel


class SQLPerformanceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_clusters(
        self,
        agent_version_id: UUID,
        move_kind: str | list[str] | None = None,
        polarity: str | None = None,
    ) -> list[PatternClusterModel]:
        stmt = select(PatternClusterModel).where(
            PatternClusterModel.agent_version_id == agent_version_id
        )
        if isinstance(move_kind, list):
            if move_kind:
                stmt = stmt.where(PatternClusterModel.move_kind.in_(move_kind))
        elif move_kind:
            stmt = stmt.where(PatternClusterModel.move_kind == move_kind)
        if polarity:
            stmt = stmt.where(PatternClusterModel.polarity == polarity)
        stmt = stmt.order_by(
            PatternClusterModel.success_rate.desc(),
            PatternClusterModel.occurrence_count.desc(),
            # Tie-break by avg_score too — with occurrence_count=1 (the common
            # case for freshly-approved moves), success_rate is binary (0/1),
            # so without this, ties resolve to arbitrary DB row order instead
            # of the actually-better-scored example.
            PatternClusterModel.avg_score.desc(),
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_cluster(self, cluster_id: UUID) -> PatternClusterModel | None:
        return await self.session.get(PatternClusterModel, cluster_id)

    async def create_cluster(self, model: PatternClusterModel) -> PatternClusterModel:
        self.session.add(model)
        await self.session.flush()
        return model

    async def touch(self, model: PatternClusterModel) -> None:
        model.updated_at = datetime.utcnow()
        await self.session.flush()

    async def rerank(self, agent_version_id: UUID, move_kind: str) -> None:
        """Assign competitive rank (1 = best) within a move_kind by success_rate."""
        clusters = await self.list_clusters(agent_version_id, move_kind=move_kind)
        ordered = sorted(
            clusters,
            key=lambda c: (c.success_rate, c.occurrence_count, c.avg_score),
            reverse=True,
        )
        for i, c in enumerate(ordered, start=1):
            c.rank = i
        await self.session.flush()
