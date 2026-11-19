"""AgentQualificationProvider: returns the configured schema, falls back to the
default when none exists, and caches. Plus QualificationSchema helpers."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from learning_engine.core.models.qualification_schema import (
    QualificationField,
    QualificationSchema,
    default_schema,
)
from learning_engine.infrastructure.agent.providers import AgentQualificationProvider


def _session_factory(row):
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    @asynccontextmanager
    async def factory():
        yield session

    return factory


class FakeCache:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ttl=300):
        self.store[key] = value


def test_schema_helpers():
    s = default_schema()
    # product_interest must NOT be sticky: it has to refine across the chat
    # (e.g. Q5 -> Q7); no default field is first-write-wins.
    assert s.sticky_keys() == set()
    req = {f.key for f in s.required_for_scheduling()}
    assert req == {"full_name", "email", "phone"}
    # target() falls back to key when crm_field is empty
    f = QualificationField(key="k", label="K")
    assert f.target() == "k"
    assert QualificationField(key="k", label="K", crm_field="mapped").target() == "mapped"


@pytest.mark.asyncio
async def test_provider_returns_default_when_no_row():
    provider = AgentQualificationProvider(_session_factory(None), cache=FakeCache())
    schema = await provider.get(uuid4())
    assert isinstance(schema, QualificationSchema)
    assert [f.key for f in schema.fields] == [f.key for f in default_schema().fields]


@pytest.mark.asyncio
async def test_provider_returns_configured_schema():
    row = MagicMock()
    row.fields = [
        {"key": "area", "label": "Zona", "type": "text", "required_for_scheduling": True},
    ]
    provider = AgentQualificationProvider(_session_factory(row), cache=FakeCache())
    schema = await provider.get(uuid4())
    assert [f.key for f in schema.fields] == ["area"]
    assert schema.fields[0].required_for_scheduling is True


@pytest.mark.asyncio
async def test_provider_caches_result():
    cache = FakeCache()
    factory = _session_factory(None)
    provider = AgentQualificationProvider(factory, cache=cache)
    vid = uuid4()
    await provider.get(vid)
    assert f"agent_version:{vid}:qualification" in cache.store
    # Second call served from cache (no row needed).
    schema2 = await provider.get(vid)
    assert [f.key for f in schema2.fields] == [f.key for f in default_schema().fields]
