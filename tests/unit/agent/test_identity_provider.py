"""Tests for AgentIdentityProvider with new identity fields."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from learning_engine.infrastructure.database.connection import live_session_factory
from learning_engine.core.models.identity import AgentIdentity
from learning_engine.infrastructure.agent.providers import AgentIdentityProvider


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


class TestIdentityProviderNewFields:
    @pytest.mark.asyncio
    async def test_maps_new_fields_from_db(self, mock_session, mock_cache, version_id):
        row = MagicMock()
        row.name = "Agent"
        row.description = "desc"
        row.communication_style = "direct"
        row.compliance_notes = "GDPR"
        row.principles = ["P1", "P2"]
        row.beliefs = ["B1"]
        row.values_list = ["V1"]
        row.words_never_use = ["bad"]
        row.words_prefer = ["good"]

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = row
        mock_session.execute = AsyncMock(return_value=result_mock)

        provider = AgentIdentityProvider(live_session_factory(mock_session), mock_cache)
        identity = await provider.get(version_id)

        assert isinstance(identity, AgentIdentity)
        assert identity.principles == ["P1", "P2"]
        assert identity.beliefs == ["B1"]
        assert identity.values == ["V1"]
        assert identity.words_never_use == ["bad"]
        assert identity.words_prefer == ["good"]
        assert identity.communication_style == "direct"

    @pytest.mark.asyncio
    async def test_handles_null_new_fields(self, mock_session, mock_cache, version_id):
        row = MagicMock()
        row.name = "Agent"
        row.description = ""
        row.communication_style = None
        row.compliance_notes = None
        row.principles = None
        row.beliefs = None
        row.values_list = None
        row.words_never_use = None
        row.words_prefer = None

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = row
        mock_session.execute = AsyncMock(return_value=result_mock)

        provider = AgentIdentityProvider(live_session_factory(mock_session), mock_cache)
        identity = await provider.get(version_id)

        assert identity.principles == []
        assert identity.values == []
        assert identity.communication_style == "consultive"

    @pytest.mark.asyncio
    async def test_cache_stores_identity(self, mock_session, mock_cache, version_id):
        row = MagicMock()
        row.name = "Agent"
        row.description = ""
        row.communication_style = "consultive"
        row.compliance_notes = ""
        row.principles = []
        row.beliefs = []
        row.values_list = []
        row.words_never_use = []
        row.words_prefer = []

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = row
        mock_session.execute = AsyncMock(return_value=result_mock)

        provider = AgentIdentityProvider(live_session_factory(mock_session), mock_cache)
        await provider.get(version_id)

        mock_cache.set.assert_called_once()
        cached_data = mock_cache.set.call_args[0][1]
        assert "principles" in cached_data
        assert "values" in cached_data
        assert "words_never_use" in cached_data

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, mock_session, mock_cache, version_id):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=result_mock)

        provider = AgentIdentityProvider(live_session_factory(mock_session), mock_cache)
        identity = await provider.get(version_id)

        assert identity is None
