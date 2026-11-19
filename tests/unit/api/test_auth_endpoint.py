"""Auth endpoints: login exchanges the UI password for a session cookie,
/session reports whether the caller already has one, logout clears it — the
flow that replaced baking the internal token into the frontend bundle."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from learning_engine.api.v1.endpoints.auth import router as auth_router
from learning_engine.api.v1.dependencies import SESSION_COOKIE_NAME
from learning_engine.config import settings

app = FastAPI()
app.include_router(auth_router, prefix="/api/v1")


def _client() -> AsyncClient:
    # https:// base_url: the login cookie is Secure outside development, and
    # httpx's cookie jar (like a real browser) won't persist/resend a Secure
    # cookie against a plain http:// origin.
    return AsyncClient(transport=ASGITransport(app=app), base_url="https://test")


@pytest.mark.asyncio
async def test_login_fails_closed_without_password_in_production(monkeypatch):
    monkeypatch.setattr(settings, "ui_login_password", "")
    monkeypatch.setattr(settings, "app_env", "production")
    async with _client() as client:
        response = await client.post("/api/v1/auth/login", json={"password": "anything"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_open_without_password_in_development(monkeypatch):
    monkeypatch.setattr(settings, "ui_login_password", "")
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "internal_api_token", "")
    async with _client() as client:
        response = await client.post("/api/v1/auth/login", json={"password": "anything"})
    assert response.status_code == 200
    assert SESSION_COOKIE_NAME in response.cookies


@pytest.mark.asyncio
async def test_login_wrong_password_rejected(monkeypatch):
    monkeypatch.setattr(settings, "ui_login_password", "correct-horse")
    async with _client() as client:
        response = await client.post("/api/v1/auth/login", json={"password": "wrong"})
    assert response.status_code == 401
    assert SESSION_COOKIE_NAME not in response.cookies


@pytest.mark.asyncio
async def test_login_correct_password_sets_session_cookie(monkeypatch):
    monkeypatch.setattr(settings, "ui_login_password", "correct-horse")
    monkeypatch.setattr(settings, "internal_api_token", "signing-secret")
    monkeypatch.setattr(settings, "app_env", "production")
    async with _client() as client:
        response = await client.post(
            "/api/v1/auth/login", json={"password": "correct-horse"}
        )
    assert response.status_code == 200
    assert SESSION_COOKIE_NAME in response.cookies


@pytest.mark.asyncio
async def test_session_check_passes_with_valid_cookie_then_logout_clears_it(monkeypatch):
    monkeypatch.setattr(settings, "ui_login_password", "correct-horse")
    monkeypatch.setattr(settings, "internal_api_token", "signing-secret")
    monkeypatch.setattr(settings, "app_env", "production")
    async with _client() as client:
        login_resp = await client.post(
            "/api/v1/auth/login", json={"password": "correct-horse"}
        )
        assert login_resp.status_code == 200

        session_resp = await client.get("/api/v1/auth/session")
        assert session_resp.status_code == 200

        await client.post("/api/v1/auth/logout")
        # Cookie jar still holds whatever the server returned on logout — a
        # cleared/expired cookie is what makes the NEXT request unauthenticated.
        session_resp_after = await client.get("/api/v1/auth/session")
    assert session_resp_after.status_code == 401


@pytest.mark.asyncio
async def test_session_check_fails_without_cookie(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_token", "signing-secret")
    monkeypatch.setattr(settings, "app_env", "production")
    async with _client() as client:
        response = await client.get("/api/v1/auth/session")
    assert response.status_code == 401
