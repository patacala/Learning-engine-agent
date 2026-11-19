"""Repository for the Evidence layer (sources + turns)."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from learning_engine.engines.evidence.models import EvidenceSource, EvidenceTurn
from learning_engine.infrastructure.database.models import MessageModel
from learning_engine.infrastructure.database.models_evidence import (
    EvidenceSourceModel,
    EvidenceTurnModel,
)

# messages.role -> evidence speaker
_ROLE_TO_SPEAKER = {"user": "client", "assistant": "agent"}


class SQLEvidenceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_source(self, source: EvidenceSource) -> UUID:
        """Persist an EvidenceSource and its turns. Returns the source id."""
        model = EvidenceSourceModel(
            source_type=source.source_type,
            agent_version_id=source.agent_version_id,
            organization_id=source.organization_id,
            conversation_id=source.conversation_id,
            session_id=source.session_id,
            outcome=source.outcome,
            outcome_score=source.outcome_score,
        )
        self.session.add(model)
        await self.session.flush()

        for turn in source.turns:
            self.session.add(
                EvidenceTurnModel(
                    evidence_source_id=model.id,
                    turn_index=turn.turn_index,
                    speaker=turn.speaker,
                    text=turn.text,
                    timestamp=turn.timestamp,
                )
            )
        await self.session.flush()
        source.id = model.id
        return model.id

    async def get_turns(self, evidence_source_id: UUID) -> list[EvidenceTurn]:
        stmt = (
            select(EvidenceTurnModel)
            .where(EvidenceTurnModel.evidence_source_id == evidence_source_id)
            .order_by(EvidenceTurnModel.turn_index)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [
            EvidenceTurn(turn_index=r.turn_index, speaker=r.speaker, text=r.text, timestamp=r.timestamp)
            for r in rows
        ]

    async def get_source(self, evidence_source_id: UUID) -> EvidenceSource | None:
        model = await self.session.get(EvidenceSourceModel, evidence_source_id)
        if not model:
            return None
        turns = await self.get_turns(evidence_source_id)
        return EvidenceSource(
            id=model.id,
            source_type=model.source_type,
            agent_version_id=model.agent_version_id,
            organization_id=model.organization_id,
            conversation_id=model.conversation_id,
            session_id=model.session_id,
            outcome=model.outcome,
            outcome_score=model.outcome_score,
            turns=turns,
        )

    async def set_outcome(
        self, evidence_source_id: UUID, outcome: str, outcome_score: float | None = None
    ) -> None:
        values = {"outcome": outcome}
        if outcome_score is not None:
            values["outcome_score"] = outcome_score
        await self.session.execute(
            update(EvidenceSourceModel)
            .where(EvidenceSourceModel.id == evidence_source_id)
            .values(**values)
        )

    async def list_source_ids_by_session(self, session_id: UUID) -> list[UUID]:
        stmt = select(EvidenceSourceModel.id).where(
            EvidenceSourceModel.session_id == session_id
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def find_by_conversation(self, conversation_id: UUID) -> UUID | None:
        stmt = select(EvidenceSourceModel.id).where(
            EvidenceSourceModel.conversation_id == conversation_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def read_turns_from_messages(self, conversation_id: UUID) -> list[EvidenceTurn]:
        """Build in-memory turns from a conversation's messages (no persistence)."""
        stmt = (
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.turn_index, MessageModel.created_at)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [
            EvidenceTurn(
                turn_index=i,
                speaker=_ROLE_TO_SPEAKER.get(r.role, "agent"),
                text=r.content,
                timestamp=r.created_at,
            )
            for i, r in enumerate(rows)
        ]

    async def materialize_from_messages(
        self,
        conversation_id: UUID,
        agent_version_id: UUID | None,
        organization_id: UUID | None = None,
        source_type: str = "live_conversation",
    ) -> EvidenceSource:
        """Build an EvidenceSource from a live conversation's messages table."""
        stmt = (
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.turn_index, MessageModel.created_at)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        turns = [
            EvidenceTurn(
                turn_index=i,
                speaker=_ROLE_TO_SPEAKER.get(r.role, "agent"),
                text=r.content,
                timestamp=r.created_at,
            )
            for i, r in enumerate(rows)
        ]
        source = EvidenceSource(
            source_type=source_type,
            agent_version_id=agent_version_id,
            organization_id=organization_id,
            conversation_id=conversation_id,
            turns=turns,
        )
        await self.save_source(source)
        return source
