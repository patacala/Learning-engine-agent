"""Repository for Insights."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from prosales.core.similarity import cosine
from prosales.core.similarity import to_list as _to_list
from prosales.engines.insights.models import Insight
from prosales.infrastructure.database.models_insights import InsightModel

# How many behavior_rules to inject per turn when scoping by relevance.
BEHAVIOR_RULES_LIMIT = 5


def _to_dto(m: InsightModel) -> Insight:
    return Insight(
        id=m.id,
        agent_version_id=m.agent_version_id,
        organization_id=m.organization_id,
        insight_text=m.insight_text,
        behavior_rule=m.behavior_rule,
        supporting_cluster_ids=m.supporting_cluster_ids or [],
        pattern_kinds=m.pattern_kinds or [],
        confidence=m.confidence,
        sample_size=m.sample_size,
        status=m.status,
    )


class SQLInsightsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(
        self, insight: Insight, agent_version_id: UUID, embedding: list[float] | None = None
    ) -> UUID:
        model = InsightModel(
            agent_version_id=agent_version_id,
            organization_id=insight.organization_id,
            insight_text=insight.insight_text,
            behavior_rule=insight.behavior_rule,
            supporting_cluster_ids=insight.supporting_cluster_ids,
            pattern_kinds=insight.pattern_kinds,
            confidence=insight.confidence,
            sample_size=insight.sample_size,
            status=insight.status,
            embedding=embedding,
        )
        self.session.add(model)
        await self.session.flush()
        return model.id

    async def list_by_agent(
        self, agent_version_id: UUID, status: str | None = None
    ) -> list[Insight]:
        stmt = select(InsightModel).where(InsightModel.agent_version_id == agent_version_id)
        if status:
            stmt = stmt.where(InsightModel.status == status)
        stmt = stmt.order_by(InsightModel.confidence.desc(), InsightModel.created_at.desc())
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_to_dto(r) for r in rows]

    async def behavior_rules(
        self, agent_version_id: UUID, query_embedding: list[float] | None = None
    ) -> list[str]:
        """Published behavior rules for prompt injection.

        Without ``query_embedding``, returns everything published (legacy
        behavior — used by admin listing). With it, ranks by similarity to the
        current message and caps at ``BEHAVIOR_RULES_LIMIT``, so a turn about
        warranties doesn't drag in unrelated rules about scheduling calls.
        Rules that haven't been embedded yet (e.g. published before this
        existed, or a backfill hasn't run) rank last and may be excluded by
        the cap — run ``scripts/backfill_insight_embeddings.py`` after
        deploying this so old rules compete fairly instead of dropping out.
        """
        stmt = select(InsightModel.behavior_rule, InsightModel.embedding).where(
            InsightModel.agent_version_id == agent_version_id,
            InsightModel.status == "published",
            InsightModel.behavior_rule != "",
        )
        rows = [(r, e) for r, e in (await self.session.execute(stmt)).all() if r]
        if query_embedding is None:
            return [r for r, _ in rows]

        scored = [
            (r, cosine(query_embedding, _to_list(e)) if e is not None else -1.0) for r, e in rows
        ]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [r for r, _ in scored[:BEHAVIOR_RULES_LIMIT]]

    async def update_status(self, insight_id: UUID, status: str) -> Insight | None:
        await self.session.execute(
            update(InsightModel)
            .where(InsightModel.id == insight_id)
            .values(status=status, updated_at=datetime.utcnow())
        )
        model = await self.session.get(InsightModel, insight_id)
        return _to_dto(model) if model else None
