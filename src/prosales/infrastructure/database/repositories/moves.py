"""Repository for Conversation Moves."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from prosales.engines.moves.models import ConversationMove
from prosales.infrastructure.database.models_evidence import EvidenceSourceModel
from prosales.infrastructure.database.models_moves import ConversationMoveModel


def _to_dto(m: ConversationMoveModel) -> ConversationMove:
    return ConversationMove(
        id=m.id,
        evidence_source_id=m.evidence_source_id,
        agent_version_id=m.agent_version_id,
        organization_id=m.organization_id,
        start_turn_index=m.start_turn_index,
        end_turn_index=m.end_turn_index,
        move_kind=m.move_kind,
        goal=m.goal,
        client_state_before=m.client_state_before,
        client_state_after=m.client_state_after,
        transcript_excerpt=m.transcript_excerpt,
        polarity=m.polarity,
        outcome_label=m.outcome_label,
        score=m.score,
        confidence=m.confidence,
        human_rating=m.human_rating,
        conditions=m.conditions or {},
        cluster_id=m.cluster_id,
        status=m.status,
    )


class SQLMovesRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, move: ConversationMove, embedding: list[float] | None = None) -> UUID:
        model = ConversationMoveModel(
            evidence_source_id=move.evidence_source_id,
            agent_version_id=move.agent_version_id,
            organization_id=move.organization_id,
            start_turn_index=move.start_turn_index,
            end_turn_index=move.end_turn_index,
            move_kind=move.move_kind,
            goal=move.goal,
            client_state_before=move.client_state_before,
            client_state_after=move.client_state_after,
            transcript_excerpt=move.transcript_excerpt,
            polarity=move.polarity,
            outcome_label=move.outcome_label,
            score=move.score,
            confidence=move.confidence,
            human_rating=move.human_rating,
            conditions=move.conditions or {},
            status=move.status,
            embedding=embedding,
        )
        self.session.add(model)
        await self.session.flush()
        move.id = model.id
        return model.id

    async def get_model(self, move_id: UUID) -> ConversationMoveModel | None:
        return await self.session.get(ConversationMoveModel, move_id)

    async def get(self, move_id: UUID) -> ConversationMove | None:
        model = await self.get_model(move_id)
        return _to_dto(model) if model else None

    async def list_by_source(self, evidence_source_id: UUID) -> list[ConversationMove]:
        stmt = (
            select(ConversationMoveModel)
            .where(ConversationMoveModel.evidence_source_id == evidence_source_id)
            .order_by(ConversationMoveModel.start_turn_index)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_to_dto(r) for r in rows]

    async def list_by_conversation(self, conversation_id: UUID) -> list[ConversationMove]:
        """Moves learned from a specific conversation (e.g. a roleplay session).

        Joins moves to their evidence source by ``conversation_id`` so a roleplay
        session can show exactly what Cognition learned from it.
        """
        stmt = (
            select(ConversationMoveModel)
            .join(
                EvidenceSourceModel,
                EvidenceSourceModel.id == ConversationMoveModel.evidence_source_id,
            )
            .where(EvidenceSourceModel.conversation_id == conversation_id)
            .order_by(ConversationMoveModel.start_turn_index)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_to_dto(r) for r in rows]

    async def list_by_agent(
        self, agent_version_id: UUID, status: str | None = None, polarity: str | None = None
    ) -> list[ConversationMove]:
        stmt = select(ConversationMoveModel).where(
            ConversationMoveModel.agent_version_id == agent_version_id
        )
        if status:
            stmt = stmt.where(ConversationMoveModel.status == status)
        if polarity:
            stmt = stmt.where(ConversationMoveModel.polarity == polarity)
        stmt = stmt.order_by(ConversationMoveModel.created_at.desc())
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_to_dto(r) for r in rows]

    async def update_status(self, move_id: UUID, status: str) -> None:
        await self.session.execute(
            update(ConversationMoveModel)
            .where(ConversationMoveModel.id == move_id)
            .values(status=status, updated_at=datetime.utcnow())
        )

    async def attach_cluster(self, move_id: UUID, cluster_id: UUID) -> None:
        await self.session.execute(
            update(ConversationMoveModel)
            .where(ConversationMoveModel.id == move_id)
            .values(cluster_id=cluster_id, updated_at=datetime.utcnow())
        )

    async def set_human_rating(self, move_id: UUID, rating: float) -> None:
        await self.session.execute(
            update(ConversationMoveModel)
            .where(ConversationMoveModel.id == move_id)
            .values(human_rating=rating, updated_at=datetime.utcnow())
        )

    async def set_score(self, move_id: UUID, score: float) -> None:
        await self.session.execute(
            update(ConversationMoveModel)
            .where(ConversationMoveModel.id == move_id)
            .values(score=score, updated_at=datetime.utcnow())
        )

    async def list_by_session(self, session_id: UUID) -> list[ConversationMove]:
        """Moves whose evidence source belongs to the given learning session."""
        from prosales.infrastructure.database.models_evidence import EvidenceSourceModel

        subq = select(EvidenceSourceModel.id).where(EvidenceSourceModel.session_id == session_id)
        stmt = (
            select(ConversationMoveModel)
            .where(ConversationMoveModel.evidence_source_id.in_(subq))
            .order_by(ConversationMoveModel.created_at.desc())
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_to_dto(r) for r in rows]

    async def list_by_cluster(self, cluster_id: UUID) -> list[ConversationMove]:
        stmt = select(ConversationMoveModel).where(
            ConversationMoveModel.cluster_id == cluster_id
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_to_dto(r) for r in rows]
