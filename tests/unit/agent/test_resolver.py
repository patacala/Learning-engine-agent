"""Tests for AgentContextResolver."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from prosales.core.models.agent import AgentContext
from prosales.infrastructure.agent.resolver import (
    AgentContextResolver,
    resolve_published_version,
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


def _make_org_row(org_id=None, api_key="sk-orgsl-1234567890ab"):
    row = MagicMock()
    row.id = org_id or uuid.uuid4()
    row.name = "AutoMax Corp"
    row.slug = "automax"
    row.api_key = api_key
    row.api_key_prefix = api_key[:8]
    row.capabilities = ["knowledge", "inventory"]
    row.is_active = True
    return row


def _make_assignment_row(org_id, version_id):
    row = MagicMock()
    row.organization_id = org_id
    row.agent_version_id = version_id
    row.is_primary = True
    row.is_active = True
    return row


def _make_version_row(version_id, agent_id):
    row = MagicMock()
    row.id = version_id
    row.agent_id = agent_id
    row.version_number = 1
    row.is_published = True
    row.capabilities = ["voice", "negotiation"]
    return row


def _make_agent_row(agent_id):
    row = MagicMock()
    row.id = agent_id
    row.name = "Sales Bot"
    row.slug = "sales-bot"
    row.agent_type = "sales"
    return row


@pytest.mark.asyncio
async def test_resolve_full_chain(mock_session, mock_cache):
    """Test full resolution: API key → org → assignment → version → agent → context."""
    org_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    version_id = uuid.uuid4()

    org_row = _make_org_row(org_id=org_id)
    assignment_row = _make_assignment_row(org_id, version_id)
    version_row = _make_version_row(version_id, agent_id)
    agent_row = _make_agent_row(agent_id)

    # Mock 4 sequential DB calls
    results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=org_row)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=assignment_row)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=version_row)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=agent_row)),
    ]
    mock_session.execute = AsyncMock(side_effect=results)

    resolver = AgentContextResolver(mock_session, mock_cache)
    ctx = await resolver.resolve("sk-orgsl-1234567890ab")

    assert ctx is not None
    assert ctx.organization_id == org_id
    assert ctx.organization_name == "AutoMax Corp"
    assert ctx.org_capabilities == ["knowledge", "inventory"]
    assert ctx.agent_id == agent_id
    assert ctx.agent_version_id == version_id
    assert ctx.agent_name == "Sales Bot"
    assert ctx.agent_type == "sales"
    assert ctx.agent_capabilities == ["voice", "negotiation"]
    mock_cache.set.assert_called_once()


@pytest.mark.asyncio
async def test_resolve_from_cache(mock_session, mock_cache):
    """Test cache hit returns AgentContext without DB queries."""
    org_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    version_id = uuid.uuid4()

    mock_cache.get = AsyncMock(return_value={
        "organization_id": str(org_id),
        "organization_name": "Cached Org",
        "org_capabilities": ["knowledge"],
        "agent_id": str(agent_id),
        "agent_version_id": str(version_id),
        "agent_name": "Cached Agent",
        "agent_type": "support",
        "agent_capabilities": ["voice"],
    })

    resolver = AgentContextResolver(mock_session, mock_cache)
    ctx = await resolver.resolve("sk-cache-123456789abc")

    assert ctx is not None
    assert ctx.organization_name == "Cached Org"
    assert ctx.agent_name == "Cached Agent"
    mock_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_invalid_key(mock_session, mock_cache):
    """Test invalid API key returns None."""
    result_mock = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_session.execute = AsyncMock(return_value=result_mock)

    resolver = AgentContextResolver(mock_session, mock_cache)
    ctx = await resolver.resolve("sk-inval-invalid-key-here")

    assert ctx is None


@pytest.mark.asyncio
async def test_resolve_no_assignment(mock_session, mock_cache):
    """Test org exists but no agent assignment returns None."""
    org_row = _make_org_row()

    results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=org_row)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # no assignment
    ]
    mock_session.execute = AsyncMock(side_effect=results)

    resolver = AgentContextResolver(mock_session, mock_cache)
    ctx = await resolver.resolve("sk-orgsl-1234567890ab")

    assert ctx is None


@pytest.mark.asyncio
async def test_resolve_no_cache(mock_session):
    """Test resolution without cache."""
    org_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    version_id = uuid.uuid4()

    results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=_make_org_row(org_id=org_id))),
        MagicMock(scalar_one_or_none=MagicMock(return_value=_make_assignment_row(org_id, version_id))),
        MagicMock(scalar_one_or_none=MagicMock(return_value=_make_version_row(version_id, agent_id))),
        MagicMock(scalar_one_or_none=MagicMock(return_value=_make_agent_row(agent_id))),
    ]
    mock_session.execute = AsyncMock(side_effect=results)

    resolver = AgentContextResolver(mock_session, cache=None)
    ctx = await resolver.resolve("sk-orgsl-1234567890ab")

    assert ctx is not None
    assert ctx.organization_id == org_id


@pytest.mark.asyncio
async def test_resolve_published_version_no_org(mock_session):
    agent_id = uuid.uuid4()
    version_id = uuid.uuid4()
    results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=_make_version_row(version_id, agent_id))),
        MagicMock(scalar_one_or_none=MagicMock(return_value=_make_agent_row(agent_id))),
    ]
    mock_session.execute = AsyncMock(side_effect=results)

    ctx = await resolve_published_version(mock_session, version_id)

    assert ctx is not None
    assert ctx.organization_id is None
    assert ctx.organization_name == "Cognition"
    assert ctx.agent_version_id == version_id
    assert ctx.agent_name == "Sales Bot"


@pytest.mark.asyncio
async def test_resolve_published_version_missing(mock_session):
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )

    ctx = await resolve_published_version(mock_session, uuid.uuid4())

    assert ctx is None
