"""Tests for agent listing endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from prosales.api.v1.endpoints.agents import router

app = FastAPI()
app.include_router(router, prefix="/api/v1")


def _mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    return session


class TestListAgents:
    @pytest.mark.asyncio
    async def test_list_agents_returns_active_published(self):
        agent_version_id = uuid4()

        mock_row = type("Row", (), {
            "id": agent_version_id,
            "name": "Sales Pro",
            "agent_type": "sales",
            "description": "A sales agent",
        })()

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]

        session = _mock_session()
        session.execute = AsyncMock(return_value=mock_result)

        from prosales.api.v1.dependencies import get_db_session
        app.dependency_overrides[get_db_session] = lambda: session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/agents")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Sales Pro"
        assert data[0]["agent_type"] == "sales"
        assert data[0]["id"] == str(agent_version_id)

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_agents_empty(self):
        mock_result = MagicMock()
        mock_result.all.return_value = []

        session = _mock_session()
        session.execute = AsyncMock(return_value=mock_result)

        from prosales.api.v1.dependencies import get_db_session
        app.dependency_overrides[get_db_session] = lambda: session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/agents")

        assert response.status_code == 200
        assert response.json() == []

        app.dependency_overrides.clear()
