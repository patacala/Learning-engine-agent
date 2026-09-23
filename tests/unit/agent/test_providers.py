"""Tests for agent providers."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from prosales.infrastructure.database.connection import live_session_factory
from prosales.core.models.agent import (
    AgentPersonalityConfig,
    AgentRule,
    AgentStrategy,
    AgentVoiceConfig,
)
from prosales.core.models.identity import AgentIdentity
from prosales.infrastructure.agent.providers import (
    AgentIdentityProvider,
    AgentPersonalityProvider,
    AgentPromptProvider,
    AgentRuleProvider,
    AgentStrategyProvider,
    AgentVoiceProvider,
)


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def mock_cache():
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    return cache


@pytest.fixture
def version_id():
    return uuid.uuid4()


class TestIdentityProvider:
    @pytest.mark.asyncio
    async def test_get_from_db(self, mock_session, mock_cache, version_id):
        row = MagicMock()
        row.name = "Sales Bot"
        row.description = "AI sales assistant"
        row.communication_style = "consultive"
        row.compliance_notes = ""
        row.principles = ["Never lie"]
        row.beliefs = ["Silence is powerful"]
        row.values_list = ["Honesty > sale"]
        row.words_never_use = ["cheap"]
        row.words_prefer = ["investment"]

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = row
        mock_session.execute = AsyncMock(return_value=result_mock)

        provider = AgentIdentityProvider(live_session_factory(mock_session), mock_cache)
        identity = await provider.get(version_id)

        assert identity is not None
        assert identity.name == "Sales Bot"
        assert identity.communication_style == "consultive"
        assert identity.principles == ["Never lie"]
        assert identity.values == ["Honesty > sale"]
        assert identity.words_never_use == ["cheap"]
        mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_from_cache(self, mock_session, mock_cache, version_id):
        mock_cache.get = AsyncMock(return_value={
            "name": "Cached Bot",
            "description": "cached",
            "communication_style": "consultive",
            "compliance_notes": "",
            "principles": [],
            "beliefs": [],
            "values": [],
            "words_never_use": [],
            "words_prefer": [],
        })

        provider = AgentIdentityProvider(live_session_factory(mock_session), mock_cache)
        identity = await provider.get(version_id)

        assert identity.name == "Cached Bot"
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_not_found(self, mock_session, mock_cache, version_id):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=result_mock)

        provider = AgentIdentityProvider(live_session_factory(mock_session), mock_cache)
        config = await provider.get(version_id)

        assert config is None


class TestPersonalityProvider:
    @pytest.mark.asyncio
    async def test_get_from_db(self, mock_session, mock_cache, version_id):
        row = MagicMock()
        row.brand_traits = ["premium", "cercano"]
        row.brand_tone = "Cálido"
        row.brand_instructions = ["Be warm"]
        row.voice_traits = ["natural"]
        row.voice_tone = "Natural"
        row.voice_instructions = ["Be natural"]

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = row
        mock_session.execute = AsyncMock(return_value=result_mock)

        provider = AgentPersonalityProvider(live_session_factory(mock_session), mock_cache)
        config = await provider.get(version_id)

        assert config is not None
        assert config.brand_traits == ["premium", "cercano"]
        assert config.brand_tone == "Cálido"


class TestRuleProvider:
    @pytest.mark.asyncio
    async def test_get_from_db(self, mock_session, mock_cache, version_id):
        row1 = MagicMock()
        row1.rule_id = "r1"
        row1.version = 1
        row1.intent = "greeting"
        row1.sentiment = None
        row1.urgency = None
        row1.action_type = "greet"
        row1.action_params = {}
        row1.priority = 10

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [row1]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        mock_session.execute = AsyncMock(return_value=result_mock)

        provider = AgentRuleProvider(live_session_factory(mock_session), mock_cache)
        rules = await provider.get(version_id)

        assert len(rules) == 1
        assert rules[0].rule_id == "r1"
        assert rules[0].action_type == "greet"


class TestStrategyProvider:
    @pytest.mark.asyncio
    async def test_get_from_db(self, mock_session, mock_cache, version_id):
        tactic = MagicMock()
        tactic.name = "needs_discovery"
        tactic.prompt_instruction = "Ask questions"
        tactic.position = 0

        row = MagicMock()
        row.strategy_type = "consultive"
        row.name = "Consultive Selling"
        row.description = "Understand needs"
        row.triggers = [{"intent": "inquiry"}]
        row.priority = 5
        row.cooldown_seconds = 0
        row.tactics = [tactic]

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [row]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        mock_session.execute = AsyncMock(return_value=result_mock)

        provider = AgentStrategyProvider(live_session_factory(mock_session), mock_cache)
        catalog = await provider.get(version_id)

        assert "consultive" in catalog
        assert catalog["consultive"].name == "Consultive Selling"
        assert len(catalog["consultive"].tactics) == 1


class TestPromptProvider:
    @pytest.mark.asyncio
    async def test_get_from_db(self, mock_session, mock_cache, version_id):
        row = MagicMock()
        row.component = "role"
        row.content = "You are a helpful sales assistant."

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [row]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        mock_session.execute = AsyncMock(return_value=result_mock)

        provider = AgentPromptProvider(live_session_factory(mock_session), mock_cache)
        templates = await provider.get(version_id)

        assert templates == {"role": "You are a helpful sales assistant."}


class TestVoiceProvider:
    @pytest.mark.asyncio
    async def test_get_from_db(self, mock_session, mock_cache, version_id):
        row = MagicMock()
        row.backchannels_es = ["claro", "entiendo"]
        row.backchannels_en = ["sure", "I see"]
        row.backchannel_probability = 0.3
        row.enable_ssml = True
        row.style_adaptations = {}

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = row
        mock_session.execute = AsyncMock(return_value=result_mock)

        provider = AgentVoiceProvider(live_session_factory(mock_session), mock_cache)
        config = await provider.get(version_id)

        assert config is not None
        assert config.backchannels_es == ["claro", "entiendo"]
        assert config.enable_ssml is True
