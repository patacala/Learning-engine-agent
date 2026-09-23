from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from prosales.core.interfaces.repository import ClientRepository
from prosales.infrastructure.database.models import ClientMemoryModel, ClientModel


class SQLClientRepository(ClientRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: UUID) -> ClientModel | None:
        stmt = (
            select(ClientModel)
            .where(ClientModel.id == id)
            .options(selectinload(ClientModel.memories))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(self, external_id: str, organization_id=None) -> ClientModel:
        stmt = select(ClientModel).where(ClientModel.external_id == external_id)
        if organization_id is not None:
            stmt = stmt.where(ClientModel.organization_id == organization_id)
        result = await self.session.execute(stmt)
        client = result.scalar_one_or_none()
        if not client:
            client = ClientModel(external_id=external_id, organization_id=organization_id)
            self.session.add(client)
            await self.session.flush()
        return client

    async def save(self, entity: ClientModel) -> ClientModel:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def get_memories(self, client_id: UUID) -> list[ClientMemoryModel]:
        stmt = (
            select(ClientMemoryModel)
            .where(ClientMemoryModel.client_id == client_id)
            .order_by(ClientMemoryModel.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def save_memory(self, client_id: UUID, key: str, value: str) -> ClientMemoryModel:
        stmt = select(ClientMemoryModel).where(
            ClientMemoryModel.client_id == client_id,
            ClientMemoryModel.key == key,
        )
        result = await self.session.execute(stmt)
        memory = result.scalar_one_or_none()
        if memory:
            memory.value = value
        else:
            memory = ClientMemoryModel(client_id=client_id, key=key, value=value)
            self.session.add(memory)
        await self.session.flush()
        return memory
