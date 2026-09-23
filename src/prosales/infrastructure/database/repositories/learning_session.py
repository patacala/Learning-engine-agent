"""Repository for Learning sessions."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from prosales.infrastructure.database.models_evidence import EvidenceSourceModel
from prosales.infrastructure.database.models_learning_session import LearningSessionModel


class SQLLearningSessionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_session(self, model: LearningSessionModel) -> LearningSessionModel:
        self.session.add(model)
        await self.session.flush()
        return model

    async def get_session(self, session_id: UUID) -> LearningSessionModel | None:
        return await self.session.get(LearningSessionModel, session_id)

    async def list_sessions(self, agent_version_id: UUID) -> list[LearningSessionModel]:
        stmt = (
            select(LearningSessionModel)
            .where(LearningSessionModel.agent_version_id == agent_version_id)
            .order_by(LearningSessionModel.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def update_status(
        self, session_id: UUID, status: str, moves_extracted: int | None = None
    ) -> None:
        values: dict = {"status": status, "updated_at": datetime.utcnow()}
        if moves_extracted is not None:
            values["moves_extracted"] = moves_extracted
        await self.session.execute(
            update(LearningSessionModel).where(LearningSessionModel.id == session_id).values(**values)
        )
        await self.session.flush()

    async def append_transcript(self, session_id: UUID, text: str) -> None:
        await self.session.execute(
            update(LearningSessionModel)
            .where(LearningSessionModel.id == session_id)
            .values(
                transcript=LearningSessionModel.transcript + "\n\n---\n\n" + text,
                updated_at=datetime.utcnow(),
            )
        )
        await self.session.flush()

    async def increment_extracted(self, session_id: UUID, count: int) -> None:
        await self.session.execute(
            update(LearningSessionModel)
            .where(LearningSessionModel.id == session_id)
            .values(
                moves_extracted=LearningSessionModel.moves_extracted + count,
                updated_at=datetime.utcnow(),
            )
        )
        await self.session.flush()

    async def increment_approved(self, session_id: UUID, count: int = 1) -> None:
        await self.session.execute(
            update(LearningSessionModel)
            .where(LearningSessionModel.id == session_id)
            .values(
                moves_approved=LearningSessionModel.moves_approved + count,
                updated_at=datetime.utcnow(),
            )
        )
        await self.session.flush()

    async def delete_session(self, session_id: UUID) -> bool:
        """Delete a session and unlink its evidence sources (keeps evidence rows)."""
        await self.session.execute(
            update(EvidenceSourceModel)
            .where(EvidenceSourceModel.session_id == session_id)
            .values(session_id=None)
        )
        result = await self.session.execute(
            delete(LearningSessionModel).where(LearningSessionModel.id == session_id)
        )
        await self.session.flush()
        return result.rowcount > 0
