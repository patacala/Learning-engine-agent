"""Repository for episodic memory persistence."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from learning_engine.infrastructure.database.models import EpisodicMemoryModel


class SQLEpisodicRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, model: EpisodicMemoryModel) -> EpisodicMemoryModel:
        async with self.session.begin_nested():
            self.session.add(model)
        return model

    async def get_by_conversation(self, conversation_id: UUID) -> EpisodicMemoryModel | None:
        stmt = select(EpisodicMemoryModel).where(
            EpisodicMemoryModel.conversation_id == conversation_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_client(self, client_id: UUID, limit: int = 10) -> list[EpisodicMemoryModel]:
        stmt = (
            select(EpisodicMemoryModel)
            .where(EpisodicMemoryModel.client_id == client_id)
            .order_by(EpisodicMemoryModel.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_feedback(
        self, conversation_id: UUID, outcome: str, outcome_notes: str
    ) -> EpisodicMemoryModel | None:
        # Check exists first
        existing = await self.get_by_conversation(conversation_id)
        if not existing:
            return None

        stmt = (
            update(EpisodicMemoryModel)
            .where(EpisodicMemoryModel.conversation_id == conversation_id)
            .values(outcome=outcome, outcome_notes=outcome_notes)
        )
        await self.session.execute(stmt)
        await self.session.flush()

        # Return updated
        return await self.get_by_conversation(conversation_id)

    async def search_similar(
        self, embedding: list[float], organization_id: UUID | None = None, top_k: int = 5
    ) -> list[EpisodicMemoryModel]:
        """Similarity search infrastructure — ready for future use."""
        from sqlalchemy import text

        org_filter = ""
        params: dict = {"embedding": str(embedding), "top_k": top_k}
        if organization_id:
            org_filter = "AND organization_id = :org_id"
            params["org_id"] = str(organization_id)

        query = text(f"""
            SELECT * FROM episodic_memories
            WHERE embedding IS NOT NULL {org_filter}
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """)

        result = await self.session.execute(query, params)
        return list(result.fetchall())
