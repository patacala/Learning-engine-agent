"""Tests for IdentityEngine."""

import uuid
from unittest.mock import AsyncMock

import pytest

from prosales.core.models.agent import AgentContext
from prosales.core.models.identity import AgentIdentity
from prosales.engines.identity.engine import IdentityEngine


def _make_ctx(**kwargs):
    defaults = {
        "organization_id": uuid.uuid4(),
        "organization_name": "Test Org",
        "agent_id": uuid.uuid4(),
        "agent_version_id": uuid.uuid4(),
        "agent_name": "Test Agent",
    }
    defaults.update(kwargs)
    return AgentContext(**defaults)


class TestIdentityEngine:
    @pytest.mark.asyncio
    async def test_no_agent_context_returns_defaults(self):
        engine = IdentityEngine()
        result = await engine.process({})
        identity = result["identity"]
        assert isinstance(identity, AgentIdentity)
        assert identity.name == ""
        assert identity.communication_style == "consultive"

    @pytest.mark.asyncio
    async def test_no_provider_returns_name_from_context(self):
        ctx = _make_ctx(agent_name="MyAgent")
        engine = IdentityEngine(identity_provider=None)
        result = await engine.process({"agent_context": ctx})
        assert result["identity"].name == "MyAgent"

    @pytest.mark.asyncio
    async def test_provider_returns_none_uses_context_name(self):
        ctx = _make_ctx(agent_name="FallbackAgent")
        provider = AsyncMock()
        provider.get = AsyncMock(return_value=None)
        engine = IdentityEngine(identity_provider=provider)
        result = await engine.process({"agent_context": ctx})
        assert result["identity"].name == "FallbackAgent"

    @pytest.mark.asyncio
    async def test_provider_returns_full_identity(self):
        ctx = _make_ctx()
        identity = AgentIdentity(
            name="Sales Pro",
            principles=["Never lie"],
            words_never_use=["cheap"],
        )
        provider = AsyncMock()
        provider.get = AsyncMock(return_value=identity)
        engine = IdentityEngine(identity_provider=provider)
        result = await engine.process({"agent_context": ctx})
        assert result["identity"].name == "Sales Pro"
        assert result["identity"].principles == ["Never lie"]
        provider.get.assert_called_once_with(ctx.agent_version_id)

    @pytest.mark.asyncio
    async def test_provider_called_with_correct_version_id(self):
        version_id = uuid.uuid4()
        ctx = _make_ctx(agent_version_id=version_id)
        provider = AsyncMock()
        provider.get = AsyncMock(return_value=AgentIdentity(name="X"))
        engine = IdentityEngine(identity_provider=provider)
        await engine.process({"agent_context": ctx})
        provider.get.assert_called_once_with(version_id)
