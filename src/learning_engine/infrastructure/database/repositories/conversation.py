from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from learning_engine.core.interfaces.repository import ConversationRepository
from learning_engine.infrastructure.database.models import ConversationModel, MessageModel


class SQLConversationRepository(ConversationRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: UUID) -> ConversationModel | None:
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.id == id)
            .options(selectinload(ConversationModel.messages))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def save(self, entity: ConversationModel) -> ConversationModel:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def get_by_client(self, client_id: UUID) -> list[ConversationModel]:
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.client_id == client_id)
            .order_by(ConversationModel.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_messages(self, conversation_id: UUID, limit: int = 50) -> list[MessageModel]:
        stmt = (
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(reversed(result.scalars().all()))

    async def add_message(self, message: MessageModel) -> MessageModel:
        # Assign a provenance turn_index (evidence layer) if not set.
        if message.turn_index is None:
            count = await self.session.scalar(
                select(func.count(MessageModel.id)).where(
                    MessageModel.conversation_id == message.conversation_id
                )
            )
            message.turn_index = int(count or 0)
        self.session.add(message)
        await self.session.flush()
        return message
