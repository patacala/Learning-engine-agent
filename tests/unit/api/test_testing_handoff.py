"""Tests for promoting an isolated playground chat into a Learning draft."""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from prosales.api.v1.dependencies import get_db_session, verify_internal_token
from prosales.api.v1.endpoints.testing import router


app = FastAPI()
app.include_router(router, prefix="/api/v1")


@pytest.fixture(autouse=True)
def _bypass_auth():
    """This test exercises endpoint logic, not the auth gate (that's
    test_auth.py). Bypass the router-level verify_internal_token so a local
    .env with an internal token set doesn't 401 it."""
    app.dependency_overrides[verify_internal_token] = lambda: None
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_handoff_creates_a_draft_with_the_complete_transcript():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    agent_version_id = uuid4()
    transcript = "Cliente: Necesito una propuesta\nAgente: Claro, cuéntame más."
    app.dependency_overrides[get_db_session] = lambda: session

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/testing/handoff",
                json={
                    "agent_version_id": str(agent_version_id),
                    "source_label": "Playground: Acme",
                    "transcript": transcript,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "draft"
    session.flush.assert_awaited_once()
    draft = session.add.call_args.args[0]
    assert UUID(response.json()["session_id"]) == draft.id
    assert draft.agent_version_id == agent_version_id
    assert draft.source_label == "Playground: Acme"
    assert draft.transcript == transcript
    assert draft.status == "draft"
