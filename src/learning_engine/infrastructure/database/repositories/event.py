from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from learning_engine.core.interfaces.repository import EventRepository
from learning_engine.infrastructure.database.models import EventModel


class SQLEventRepository(EventRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: UUID) -> EventModel | None:
        return await self.session.get(EventModel, id)

    async def append(self, event: EventModel) -> None:
        async with self.session.begin_nested():
            self.session.add(event)

    async def get_by_conversation(self, conversation_id: UUID) -> list[EventModel]:
        stmt = (
            select(EventModel)
            .where(EventModel.conversation_id == conversation_id)
            .order_by(EventModel.timestamp)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
