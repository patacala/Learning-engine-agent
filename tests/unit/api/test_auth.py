"""Auth gates: tenant endpoints require an API key; internal endpoints require
the internal token (fail closed outside development); dual endpoints accept
either the internal token or a valid org API key."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from prosales.api.v1.dependencies import get_db_session
from prosales.api.v1.endpoints.agents import router as agents_router
from prosales.api.v1.endpoints.contact import router as contact_router
from prosales.api.v1.endpoints.conversation import router as conversation_router
from prosales.api.v1.endpoints.episode import router as episode_router
from prosales.config import settings

app = FastAPI()
app.include_router(conversation_router, prefix="/api/v1")
app.include_router(contact_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1")
app.include_router(episode_router, prefix="/api/v1")


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    return session


class TestTenantEndpointsRequireApiKey:
    @pytest.mark.asyncio
    async def test_conversation_message_without_key_is_401(self):
        async with _client() as client:
            response = await client.post(
                "/api/v1/conversation/message",
                json={"client_id": "c-1", "message": "hola"},
            )
        assert response.status_code == 401
        assert "X-API-Key" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_contact_qualification_without_key_is_401(self):
        session = _mock_session()
        app.dependency_overrides[get_db_session] = lambda: session
        try:
            async with _client() as client:
                response = await client.get("/api/v1/contact/ext-1/qualification")
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 401


class TestInternalToken:
    @pytest.mark.asyncio
    async def test_development_without_token_allows(self, monkeypatch):
        monkeypatch.setattr(settings, "internal_api_token", "")
        monkeypatch.setattr(settings, "app_env", "development")
        mock_result = MagicMock()
        mock_result.all.return_value = []
        session = _mock_session()
        session.execute = AsyncMock(return_value=mock_result)
        app.dependency_overrides[get_db_session] = lambda: session
        try:
            async with _client() as client:
                response = await client.get("/api/v1/agents")
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_production_without_token_fails_closed(self, monkeypatch):
        monkeypatch.setattr(settings, "internal_api_token", "")
        monkeypatch.setattr(settings, "app_env", "production")
        async with _client() as client:
            response = await client.get("/api/v1/agents")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_token_is_401(self, monkeypatch):
        monkeypatch.setattr(settings, "internal_api_token", "secret-token")
        async with _client() as client:
            response = await client.get(
                "/api/v1/agents", headers={"X-Internal-Token": "wrong"}
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_correct_token_passes(self, monkeypatch):
        monkeypatch.setattr(settings, "internal_api_token", "secret-token")
        monkeypatch.setattr(settings, "app_env", "production")
        mock_result = MagicMock()
        mock_result.all.return_value = []
        session = _mock_session()
        session.execute = AsyncMock(return_value=mock_result)
        app.dependency_overrides[get_db_session] = lambda: session
        try:
            async with _client() as client:
                response = await client.get(
                    "/api/v1/agents", headers={"X-Internal-Token": "secret-token"}
                )
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 200


class TestInternalOrApiKey:
    """Episode endpoints accept internal token OR a valid org API key (CRM)."""

    @pytest.mark.asyncio
    async def test_no_credentials_in_production_is_401(self, monkeypatch):
        monkeypatch.setattr(settings, "internal_api_token", "secret-token")
        monkeypatch.setattr(settings, "app_env", "production")
        async with _client() as client:
            response = await client.post("/api/v1/conversation/00000000-0000-0000-0000-000000000000/close")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_org_api_key_passes_gate(self, monkeypatch):
        monkeypatch.setattr(settings, "internal_api_token", "secret-token")
        monkeypatch.setattr(settings, "app_env", "production")

        # A valid org row exists for this key.
        key_lookup = MagicMock()
        key_lookup.scalar_one_or_none.return_value = "org-id"
        gate_session = _mock_session()
        gate_session.execute = AsyncMock(return_value=key_lookup)

        @asynccontextmanager
        async def fake_factory():
            yield gate_session

        # The endpoint itself 404s on a missing conversation — that's enough to
        # prove the auth gate passed (401 would mean it didn't).
        not_found = MagicMock()
        not_found.scalar_one_or_none.return_value = None
        endpoint_session = _mock_session()
        endpoint_session.execute = AsyncMock(return_value=not_found)
        endpoint_session.get = AsyncMock(return_value=None)
        app.dependency_overrides[get_db_session] = lambda: endpoint_session

        try:
            with patch(
                "prosales.api.v1.dependencies.async_session_factory", fake_factory
            ):
                async with _client() as client:
                    response = await client.post(
                        "/api/v1/conversation/00000000-0000-0000-0000-000000000000/close",
                        headers={"X-API-Key": "pk_live_abcdef123456"},
                    )
        finally:
            app.dependency_overrides.clear()
        assert response.status_code != 401
