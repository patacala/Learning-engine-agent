"""Repository for agent style profiles (one per agent_version_id)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from prosales.engines.identity_learning.models import AgentStyleProfile
from prosales.infrastructure.database.models_performance import AgentStyleProfileModel

_FLOAT_FIELDS = (
    "empathy_level", "question_ratio", "formality", "avg_response_length",
    "technical_level", "analogy_use", "example_use", "humor_use",
    "emotional_validation_freq", "sales_pressure", "confidence_level",
)


def _to_dto(m: AgentStyleProfileModel) -> AgentStyleProfile:
    dto = AgentStyleProfile(
        id=m.id,
        agent_version_id=m.agent_version_id,
        organization_id=m.organization_id,
        microexpressions=m.microexpressions or [],
        linguistic_style=m.linguistic_style or {},
        computed_from_n_conversations=m.computed_from_n_conversations,
    )
    for f in _FLOAT_FIELDS:
        setattr(dto, f, getattr(m, f))
    return dto


class SQLStyleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, agent_version_id: UUID) -> AgentStyleProfile | None:
        stmt = select(AgentStyleProfileModel).where(
            AgentStyleProfileModel.agent_version_id == agent_version_id
        )
        m = (await self.session.execute(stmt)).scalar_one_or_none()
        return _to_dto(m) if m else None

    async def upsert(self, profile: AgentStyleProfile) -> UUID:
        stmt = select(AgentStyleProfileModel).where(
            AgentStyleProfileModel.agent_version_id == profile.agent_version_id
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()

        if existing is None:
            model = AgentStyleProfileModel(
                agent_version_id=profile.agent_version_id,
                organization_id=profile.organization_id,
                microexpressions=profile.microexpressions,
                linguistic_style=profile.linguistic_style,
                computed_from_n_conversations=profile.computed_from_n_conversations,
            )
            for f in _FLOAT_FIELDS:
                setattr(model, f, getattr(profile, f))
            self.session.add(model)
            await self.session.flush()
            return model.id

        for f in _FLOAT_FIELDS:
            setattr(existing, f, getattr(profile, f))
        existing.microexpressions = profile.microexpressions
        existing.linguistic_style = profile.linguistic_style
        existing.computed_from_n_conversations = profile.computed_from_n_conversations
        existing.updated_at = datetime.utcnow()
        await self.session.flush()
        return existing.id
