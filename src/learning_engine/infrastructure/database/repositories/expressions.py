"""Repository for Expressions with similarity aggregation (dedup by normalized phrase)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from learning_engine.core.similarity import SIMILARITY_THRESHOLD, cosine
from learning_engine.core.similarity import to_list as _to_list
from learning_engine.engines.expressions.models import Expression, normalize_phrase
from learning_engine.infrastructure.database.models_performance import ExpressionModel


def _merge_unique(existing: list, incoming: list) -> list:
    seen = list(existing or [])
    for item in incoming or []:
        if item and item not in seen:
            seen.append(item)
    return seen


def best_semantic_match(
    embedding: list[float], candidates: list[tuple[UUID, list[float] | None]]
) -> UUID | None:
    """Pick the closest candidate embedding above SIMILARITY_THRESHOLD, if any.

    Pure/DB-free so it's unit-testable without a session — mirrors
    PatternClusterer's merge decision (same threshold, same "best cosine wins"
    rule), just for expressions instead of moves.
    """
    best: UUID | None = None
    best_sim = 0.0
    for cid, cand_embedding in candidates:
        sim = cosine(embedding, cand_embedding) if cand_embedding else 0.0
        if sim > best_sim:
            best_sim, best = sim, cid
    return best if best_sim >= SIMILARITY_THRESHOLD else None


def _to_dto(m: ExpressionModel) -> Expression:
    return Expression(
        id=m.id,
        agent_version_id=m.agent_version_id,
        organization_id=m.organization_id,
        exact_phrase=m.exact_phrase,
        polarity=m.polarity,
        goal=m.goal,
        stage=m.stage,
        contexts=m.contexts or [],
        conversation_ids=m.conversation_ids or [],
        agent_ids=m.agent_ids or [],
        times_used=m.times_used,
        success_rate=m.success_rate,
        avg_score=m.avg_score,
    )


class SQLExpressionsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(self, expr: Expression, embedding: list[float] | None = None) -> UUID:
        """Insert a new expression or aggregate into an existing similar one.

        Aggregation is first by exact match on (agent_version_id,
        normalized_phrase, polarity). On a miss, and only when ``embedding`` is
        given, falls back to a semantic match: the closest existing expression
        for (agent_version_id, polarity) whose cosine similarity is
        ``>= SIMILARITY_THRESHOLD`` (mirrors PatternClusterer's move dedup) —
        catches paraphrases of the same line that would otherwise fragment
        stats across near-duplicate rows. Either way, on a hit we bump
        times_used, merge provenance and recompute avg_score / success_rate as
        running statistics.
        """
        norm = normalize_phrase(expr.exact_phrase)
        stmt = select(ExpressionModel).where(
            ExpressionModel.agent_version_id == expr.agent_version_id,
            ExpressionModel.normalized_phrase == norm,
            ExpressionModel.polarity == expr.polarity,
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()

        if existing is None and embedding:
            existing = await self._find_semantic_match(
                expr.agent_version_id, expr.polarity, embedding
            )

        worked = 1 if expr.score >= 0.5 else 0

        if existing is None:
            model = ExpressionModel(
                agent_version_id=expr.agent_version_id,
                organization_id=expr.organization_id,
                exact_phrase=expr.exact_phrase,
                normalized_phrase=norm,
                polarity=expr.polarity,
                goal=expr.goal,
                contexts=expr.contexts or [],
                stage=expr.stage,
                times_used=1,
                avg_score=round(expr.score, 4),
                success_rate=float(worked),
                conversation_ids=expr.conversation_ids or [],
                agent_ids=expr.agent_ids or [],
                embedding=embedding,
            )
            self.session.add(model)
            await self.session.flush()
            return model.id

        new_times = existing.times_used + 1
        prev_positive = round(existing.success_rate * existing.times_used)
        existing.times_used = new_times
        if expr.score > existing.avg_score:
            existing.exact_phrase = expr.exact_phrase
            existing.normalized_phrase = norm
        existing.avg_score = round(
            (existing.avg_score * (new_times - 1) + expr.score) / new_times, 4
        )
        existing.success_rate = round((prev_positive + worked) / new_times, 4)
        existing.contexts = _merge_unique(existing.contexts, expr.contexts)
        existing.conversation_ids = _merge_unique(existing.conversation_ids, expr.conversation_ids)
        existing.agent_ids = _merge_unique(existing.agent_ids, expr.agent_ids)
        existing.updated_at = datetime.utcnow()
        await self.session.flush()
        return existing.id

    async def _find_semantic_match(
        self, agent_version_id: UUID, polarity: str, embedding: list[float]
    ) -> ExpressionModel | None:
        stmt = select(ExpressionModel).where(
            ExpressionModel.agent_version_id == agent_version_id,
            ExpressionModel.polarity == polarity,
            ExpressionModel.embedding.isnot(None),
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        by_id = {r.id: r for r in rows}
        match_id = best_semantic_match(
            embedding, [(r.id, _to_list(r.embedding)) for r in rows]
        )
        return by_id.get(match_id) if match_id else None

    async def list_by_conversation(self, conversation_id: UUID) -> list[Expression]:
        """Expressions whose provenance includes a given conversation.

        Expressions are deduped across sources by normalized phrase, so a
        roleplay session may share an expression with other conversations; we
        match by JSONB containment of the session id in ``conversation_ids``.
        """
        stmt = (
            select(ExpressionModel)
            .where(ExpressionModel.conversation_ids.contains([str(conversation_id)]))
            .order_by(ExpressionModel.success_rate.desc(), ExpressionModel.times_used.desc())
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_to_dto(r) for r in rows]

    async def list_by_agent(
        self, agent_version_id: UUID, polarity: str | None = None, limit: int = 100
    ) -> list[Expression]:
        stmt = select(ExpressionModel).where(
            ExpressionModel.agent_version_id == agent_version_id
        )
        if polarity:
            stmt = stmt.where(ExpressionModel.polarity == polarity)
        stmt = stmt.order_by(
            ExpressionModel.success_rate.desc(), ExpressionModel.times_used.desc()
        ).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_to_dto(r) for r in rows]
