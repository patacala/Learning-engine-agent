"""Repository for Test Playground saved scenarios."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from learning_engine.infrastructure.database.models_testing import TestScenarioModel


class SQLScenarioRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, model: TestScenarioModel) -> TestScenarioModel:
        self.session.add(model)
        await self.session.flush()
        return model

    async def get(self, scenario_id: UUID) -> TestScenarioModel | None:
        stmt = select(TestScenarioModel).where(TestScenarioModel.id == scenario_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_agent(self, agent_version_id: UUID) -> list[TestScenarioModel]:
        stmt = (
            select(TestScenarioModel)
            .where(TestScenarioModel.agent_version_id == agent_version_id)
            .order_by(TestScenarioModel.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(
        self,
        scenario_id: UUID,
        name: str | None = None,
        company_name: str | None = None,
        documents: list | None = None,
        quick_facts: dict | None = None,
    ) -> TestScenarioModel | None:
        model = await self.get(scenario_id)
        if model is None:
            return None
        if name is not None:
            model.name = name
        if company_name is not None:
            model.company_name = company_name
        if documents is not None:
            model.documents = documents
        if quick_facts is not None:
            model.quick_facts = quick_facts
        model.updated_at = datetime.utcnow()
        await self.session.flush()
        return model

    async def delete(self, scenario_id: UUID) -> bool:
        result = await self.session.execute(
            delete(TestScenarioModel).where(TestScenarioModel.id == scenario_id)
        )
        await self.session.flush()
        return result.rowcount > 0
