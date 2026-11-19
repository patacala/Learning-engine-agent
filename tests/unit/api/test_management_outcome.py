"""Tests for the CRM-verified outcome endpoint under /management.

Mirrors the mock style in test_management_api.py: override get_authenticated_org,
patch _get_session_from_org, and patch the learning hooks (run_live_learning,
_propagate_outcome_to_clusters) at the management module namespace so no DB or
background task runs.
"""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from learning_engine.api.v1.dependencies import get_authenticated_org
from learning_engine.api.v1.endpoints.management import router as management_router
from learning_engine.infrastructure.database.models_agent import OrganizationModel

app = FastAPI()
app.include_router(management_router, prefix="/api/v1")

ORG_API_KEY = "sk-testorg-abcdef123456abcdef123456"


def _mock_org(org_id=None):
    org = MagicMock(spec=OrganizationModel)
    org.id = org_id or uuid.uuid4()
    org._auth_api_key = ORG_API_KEY
    return org


def _override_org(org=None):
    org = org or _mock_org()

    async def _get_org():
        return org

    app.dependency_overrides[get_authenticated_org] = _get_org
    return org


def _cleanup():
    app.dependency_overrides.clear()


def _mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


def _mock_conversation(org_id, learned_at=None, outcome="open"):
    conv = MagicMock()
    conv.organization_id = org_id
    conv.learned_at = learned_at
    conv.outcome = outcome
    return conv


def _fake_session_factory():
    """Stand-in for async_session_factory(): an async-cm yielding a session
    whose .begin() is itself an async-cm. _propagate_outcome_to_clusters is
    mocked, so the yielded session is only a passthrough argument."""
    inner = MagicMock()

    @asynccontextmanager
    async def _begin():
        yield None

    inner.begin = _begin

    @asynccontextmanager
    async def _factory():
        yield inner

    return MagicMock(side_effect=lambda: _factory())


async def _post_outcome(client: AsyncClient, conversation_id: uuid.UUID, outcome: str = "converted"):
    return await client.post(
        f"/api/v1/management/conversations/{conversation_id}/outcome",
        json={"outcome": outcome},
        headers={"Authorization": f"Bearer {ORG_API_KEY}"},
    )


class TestOutcome:
    @pytest.mark.asyncio
    async def test_post_outcome_updates_conversation_and_returns_ok(self):
        org = _override_org()
        conv = _mock_conversation(org.id, learned_at=None)
        session = _mock_session()
        session.get = AsyncMock(return_value=conv)
        conversation_id = uuid.uuid4()

        with (
            patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=session),
            patch("learning_engine.api.v1.endpoints.management.run_live_learning", new_callable=AsyncMock) as mock_rll,
            patch("learning_engine.api.v1.endpoints.management._propagate_outcome_to_clusters", new_callable=AsyncMock),
            patch("learning_engine.api.v1.endpoints.management.async_session_factory", _fake_session_factory()),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await _post_outcome(client, conversation_id, "converted")

            assert response.status_code == 200
            data = response.json()
            assert data == {"status": "ok", "outcome": "converted"}
            assert conv.outcome == "converted"
            session.commit.assert_awaited()
            mock_rll.assert_awaited_once_with(conversation_id)

        _cleanup()

    @pytest.mark.asyncio
    async def test_learned_at_none_runs_live_learning_not_propagate(self):
        org = _override_org()
        conv = _mock_conversation(org.id, learned_at=None)
        session = _mock_session()
        session.get = AsyncMock(return_value=conv)
        conversation_id = uuid.uuid4()

        with (
            patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=session),
            patch("learning_engine.api.v1.endpoints.management.run_live_learning", new_callable=AsyncMock) as mock_rll,
            patch("learning_engine.api.v1.endpoints.management._propagate_outcome_to_clusters", new_callable=AsyncMock) as mock_prop,
            patch("learning_engine.api.v1.endpoints.management.async_session_factory", _fake_session_factory()),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await _post_outcome(client, conversation_id, "scheduled")

            assert response.status_code == 200
            mock_rll.assert_awaited_once_with(conversation_id)
            mock_prop.assert_not_awaited()

        _cleanup()

    @pytest.mark.asyncio
    async def test_learned_at_set_propagates_not_live_learning(self):
        org = _override_org()
        conv = _mock_conversation(org.id, learned_at=datetime.utcnow())
        session = _mock_session()
        session.get = AsyncMock(return_value=conv)
        conversation_id = uuid.uuid4()

        with (
            patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=session),
            patch("learning_engine.api.v1.endpoints.management.run_live_learning", new_callable=AsyncMock) as mock_rll,
            patch("learning_engine.api.v1.endpoints.management._propagate_outcome_to_clusters", new_callable=AsyncMock) as mock_prop,
            patch("learning_engine.api.v1.endpoints.management.async_session_factory", _fake_session_factory()),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await _post_outcome(client, conversation_id, "converted")

            assert response.status_code == 200
            mock_prop.assert_awaited_once()
            # positional args: (session, conversation_id, outcome)
            args = mock_prop.await_args.args
            assert args[1] == conversation_id
            assert args[2] == "converted"
            mock_rll.assert_not_awaited()

        _cleanup()

    @pytest.mark.asyncio
    async def test_conversation_other_org_404(self):
        org = _override_org()
        conv = _mock_conversation(uuid.uuid4(), learned_at=None)  # different org
        session = _mock_session()
        session.get = AsyncMock(return_value=conv)
        conversation_id = uuid.uuid4()

        with (
            patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=session),
            patch("learning_engine.api.v1.endpoints.management.run_live_learning", new_callable=AsyncMock) as mock_rll,
            patch("learning_engine.api.v1.endpoints.management._propagate_outcome_to_clusters", new_callable=AsyncMock) as mock_prop,
            patch("learning_engine.api.v1.endpoints.management.async_session_factory", _fake_session_factory()),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await _post_outcome(client, conversation_id, "converted")

            assert response.status_code == 404
            mock_rll.assert_not_awaited()
            mock_prop.assert_not_awaited()

        _cleanup()

    @pytest.mark.asyncio
    async def test_missing_conversation_404(self):
        org = _override_org()
        session = _mock_session()
        session.get = AsyncMock(return_value=None)
        conversation_id = uuid.uuid4()

        with (
            patch("learning_engine.api.v1.endpoints.management._get_session_from_org", new_callable=AsyncMock, return_value=session),
            patch("learning_engine.api.v1.endpoints.management.run_live_learning", new_callable=AsyncMock) as mock_rll,
            patch("learning_engine.api.v1.endpoints.management._propagate_outcome_to_clusters", new_callable=AsyncMock) as mock_prop,
            patch("learning_engine.api.v1.endpoints.management.async_session_factory", _fake_session_factory()),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await _post_outcome(client, conversation_id, "converted")

            assert response.status_code == 404
            mock_rll.assert_not_awaited()
            mock_prop.assert_not_awaited()

        _cleanup()
