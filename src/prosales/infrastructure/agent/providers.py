"""Agent providers: specialized config loaders for each engine."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from prosales.core.models.agent import (
    AgentPersonalityConfig,
    AgentRule,
    AgentStrategy,
    AgentStrategyTactic,
    AgentVoiceConfig,
)
from prosales.core.models.identity import AgentIdentity
from prosales.engines.identity_learning.models import AgentStyleProfile
from prosales.infrastructure.cache.redis import RedisCache
from prosales.infrastructure.database.models_agent import (
    AgentIdentityModel,
    AgentPersonalityModel,
    AgentPromptTemplateModel,
    AgentRuleModel,
    AgentStrategyModel,
    AgentVoiceModel,
)
from prosales.infrastructure.database.models_performance import AgentStyleProfileModel

CACHE_TTL = 300  # 5 minutes


class _BaseProvider:
    """Cache-first provider. On a cache miss, opens a SHORT DB session via the
    session_factory (connection not held across the pipeline)."""

    def __init__(self, session_factory, cache: RedisCache | None = None):
        self._sf = session_factory
        self.cache = cache

    async def _execute(self, stmt):
        async with self._sf() as s:
            return await s.execute(stmt)

    async def _get_cached(self, key: str) -> dict | list | None:
        if self.cache:
            return await self.cache.get(key)
        return None

    async def _set_cached(self, key: str, value) -> None:
        if self.cache:
            await self.cache.set(key, value, ttl=CACHE_TTL)


class AgentIdentityProvider(_BaseProvider):
    async def get(self, agent_version_id: UUID) -> AgentIdentity | None:
        cache_key = f"agent_version:{agent_version_id}:identity"
        cached = await self._get_cached(cache_key)
        if cached:
            return AgentIdentity(**cached)

        stmt = select(AgentIdentityModel).where(
            AgentIdentityModel.agent_version_id == agent_version_id
        )
        result = await self._execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None

        identity = AgentIdentity(
            name=row.name,
            description=row.description or "",
            communication_style=row.communication_style or "consultive",
            compliance_notes=row.compliance_notes or "",
            principles=row.principles or [],
            beliefs=row.beliefs or [],
            values=row.values_list or [],
            words_never_use=row.words_never_use or [],
            words_prefer=row.words_prefer or [],
        )
        await self._set_cached(cache_key, identity.model_dump())
        return identity


class AgentStyleProvider(_BaseProvider):
    """Loads the learned style profile (Cognitive Learning Engine) for an agent."""

    _FLOAT_FIELDS = (
        "empathy_level", "question_ratio", "formality", "avg_response_length",
        "technical_level", "analogy_use", "example_use", "humor_use",
        "emotional_validation_freq", "sales_pressure", "confidence_level",
    )

    async def get(self, agent_version_id: UUID) -> AgentStyleProfile | None:
        cache_key = f"agent_version:{agent_version_id}:style"
        cached = await self._get_cached(cache_key)
        if cached:
            return AgentStyleProfile(**cached)

        stmt = select(AgentStyleProfileModel).where(
            AgentStyleProfileModel.agent_version_id == agent_version_id
        )
        row = (await self._execute(stmt)).scalar_one_or_none()
        if row is None:
            return None

        profile = AgentStyleProfile(
            agent_version_id=row.agent_version_id,
            organization_id=row.organization_id,
            microexpressions=row.microexpressions or [],
            linguistic_style=row.linguistic_style or {},
            computed_from_n_conversations=row.computed_from_n_conversations,
            **{f: getattr(row, f) for f in self._FLOAT_FIELDS},
        )
        await self._set_cached(cache_key, profile.model_dump(mode="json"))
        return profile


class AgentPersonalityProvider(_BaseProvider):
    async def get(self, agent_version_id: UUID) -> AgentPersonalityConfig | None:
        cache_key = f"agent_version:{agent_version_id}:personality"
        cached = await self._get_cached(cache_key)
        if cached:
            return AgentPersonalityConfig(**cached)

        stmt = select(AgentPersonalityModel).where(
            AgentPersonalityModel.agent_version_id == agent_version_id,
            AgentPersonalityModel.is_active.is_(True),
        )
        result = await self._execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None

        config = AgentPersonalityConfig(
            brand_traits=row.brand_traits or [],
            brand_tone=row.brand_tone or "Profesional y cercano",
            brand_instructions=row.brand_instructions or [],
            voice_traits=row.voice_traits or [],
            voice_tone=row.voice_tone or "Natural y conversacional",
            voice_instructions=row.voice_instructions or [],
        )
        await self._set_cached(cache_key, config.model_dump())
        return config


class AgentRuleProvider(_BaseProvider):
    async def get(self, agent_version_id: UUID) -> list[AgentRule]:
        cache_key = f"agent_version:{agent_version_id}:rules"
        cached = await self._get_cached(cache_key)
        if cached:
            return [AgentRule(**r) for r in cached]

        stmt = (
            select(AgentRuleModel)
            .where(
                AgentRuleModel.agent_version_id == agent_version_id,
                AgentRuleModel.enabled.is_(True),
            )
            .order_by(AgentRuleModel.priority.desc())
        )
        result = await self._execute(stmt)
        rows = result.scalars().all()

        rules = [
            AgentRule(
                rule_id=r.rule_id,
                version=r.version,
                intent=r.intent,
                sentiment=r.sentiment,
                urgency=r.urgency,
                action_type=r.action_type,
                action_params=r.action_params or {},
                priority=r.priority,
            )
            for r in rows
        ]
        await self._set_cached(cache_key, [r.model_dump() for r in rules])
        return rules


class AgentStrategyProvider(_BaseProvider):
    async def get(self, agent_version_id: UUID) -> dict[str, AgentStrategy]:
        cache_key = f"agent_version:{agent_version_id}:strategies"
        cached = await self._get_cached(cache_key)
        if cached:
            return {k: AgentStrategy(**v) for k, v in cached.items()}

        stmt = (
            select(AgentStrategyModel)
            .options(selectinload(AgentStrategyModel.tactics))
            .where(
                AgentStrategyModel.agent_version_id == agent_version_id,
                AgentStrategyModel.enabled.is_(True),
            )
        )
        result = await self._execute(stmt)
        rows = result.scalars().all()

        catalog: dict[str, AgentStrategy] = {}
        for s in rows:
            tactics = [
                AgentStrategyTactic(
                    name=t.name,
                    prompt_instruction=t.prompt_instruction,
                    position=t.position,
                )
                for t in sorted(s.tactics, key=lambda t: t.position)
            ]
            catalog[s.strategy_type] = AgentStrategy(
                strategy_type=s.strategy_type,
                name=s.name,
                description=s.description or "",
                triggers=s.triggers or [],
                priority=s.priority,
                cooldown_seconds=s.cooldown_seconds,
                tactics=tactics,
            )

        await self._set_cached(cache_key, {k: v.model_dump() for k, v in catalog.items()})
        return catalog


class AgentPromptProvider(_BaseProvider):
    async def get(self, agent_version_id: UUID) -> dict[str, str]:
        cache_key = f"agent_version:{agent_version_id}:prompts"
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        stmt = (
            select(AgentPromptTemplateModel)
            .where(
                AgentPromptTemplateModel.agent_version_id == agent_version_id,
                AgentPromptTemplateModel.is_active.is_(True),
            )
        )
        result = await self._execute(stmt)
        rows = result.scalars().all()

        templates = {r.component: r.content for r in rows}
        if templates:
            await self._set_cached(cache_key, templates)
        return templates


class AgentVoiceProvider(_BaseProvider):
    async def get(self, agent_version_id: UUID) -> AgentVoiceConfig | None:
        cache_key = f"agent_version:{agent_version_id}:voice"
        cached = await self._get_cached(cache_key)
        if cached:
            return AgentVoiceConfig(**cached)

        stmt = select(AgentVoiceModel).where(
            AgentVoiceModel.agent_version_id == agent_version_id
        )
        result = await self._execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None

        config = AgentVoiceConfig(
            backchannels_es=row.backchannels_es or ["claro", "entiendo"],
            backchannels_en=row.backchannels_en or ["I see", "sure"],
            backchannel_probability=row.backchannel_probability,
            enable_ssml=row.enable_ssml,
            style_adaptations=row.style_adaptations or {},
        )
        await self._set_cached(cache_key, config.model_dump())
        return config
