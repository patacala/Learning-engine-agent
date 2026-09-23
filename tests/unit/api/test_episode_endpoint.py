"""Tests for episode API endpoints — close and feedback."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from prosales.api.v1.endpoints.episode import router

app = FastAPI()
app.include_router(router, prefix="/api/v1")


def _mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    return session


def _mock_conversation(conversation_id=None, client_id=None):
    conv = MagicMock()
    conv.id = conversation_id or uuid4()
    conv.client_id = client_id or uuid4()
    conv.organization_id = None
    conv.is_active = True
    conv.stage = "negotiation"
    conv.created_at = datetime(2026, 7, 13, 10, 0, 0)
    conv.updated_at = datetime(2026, 7, 13, 10, 0, 0)
    return conv


def _mock_episode_model(conversation_id=None):
    model = MagicMock()
    model.id = uuid4()
    model.conversation_id = conversation_id or uuid4()
    model.client_id = uuid4()
    model.organization_id = None
    model.started_at = datetime(2026, 7, 13, 10, 0, 0)
    model.closed_at = datetime(2026, 7, 13, 10, 30, 0)
    model.duration_seconds = 1800.0
    model.message_count = 10
    model.dominant_intent = "inquiry"
    model.dominant_sentiment = "positive"
    model.sentiment_shifts = 1
    model.final_stage = "closing"
    model.objections_detected = ["price"]
    model.strategies_used = ["consultive"]
    model.urgency_signals = []
    model.risk_signals = []
    model.outcome = "sale_closed"
    model.outcome_notes = "Cerró en primera llamada"
    return model


class TestCloseEndpoint:
    @pytest.mark.asyncio
    async def test_close_returns_episode(self):
        conv_id = uuid4()
        conv = _mock_conversation(conversation_id=conv_id)

        with (
            patch("prosales.api.v1.endpoints.episode.get_db_session") as mock_deps,
            patch("prosales.api.v1.endpoints.episode.SQLConversationRepository") as MockConvRepo,
            patch("prosales.api.v1.endpoints.episode.SQLEventRepository") as MockEventRepo,
            patch("prosales.api.v1.endpoints.episode.SQLEpisodicRepository") as MockEpRepo,
            patch("prosales.api.v1.endpoints.episode.EpisodeExtractor") as MockExtractor,
            patch("prosales.api.v1.endpoints.episode.EpisodicMemoryEngine") as MockEngine,
            patch("prosales.api.v1.endpoints.episode.EventStore") as MockEventStore,
        ):
            session = _mock_session()
            mock_deps.return_value = session

            MockConvRepo.return_value.get_by_id = AsyncMock(return_value=conv)
            MockEpRepo.return_value.get_by_conversation = AsyncMock(return_value=None)

            from prosales.engines.episodic.models import Episode
            episode = Episode(
                conversation_id=conv_id,
                client_id=conv.client_id,
                dominant_intent="inquiry",
                message_count=5,
            )
            MockEngine.return_value.close_conversation = AsyncMock(return_value=episode)
            MockEventStore.return_value.store = AsyncMock()

            app.dependency_overrides[router.dependencies[0].dependency if router.dependencies else None] = lambda: session

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # Override the dependency
                from prosales.api.v1.dependencies import get_db_session
                app.dependency_overrides[get_db_session] = lambda: session

                response = await client.post(f"/api/v1/conversation/{conv_id}/close")

            assert response.status_code == 200
            data = response.json()
            assert data["dominant_intent"] == "inquiry"
            assert data["outcome"] == "pending"

            app.dependency_overrides.clear()


class TestFeedbackEndpoint:
    @pytest.mark.asyncio
    async def test_feedback_updates_episode(self):
        conv_id = uuid4()
        model = _mock_episode_model(conversation_id=conv_id)

        with (
            patch("prosales.api.v1.endpoints.episode.SQLEpisodicRepository") as MockEpRepo,
        ):
            MockEpRepo.return_value.update_feedback = AsyncMock(return_value=model)

            session = _mock_session()
            from prosales.api.v1.dependencies import get_db_session
            app.dependency_overrides[get_db_session] = lambda: session

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/v1/conversation/{conv_id}/episode",
                    json={"outcome": "sale_closed", "outcome_notes": "Cerró en primera llamada"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["outcome"] == "sale_closed"

            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_feedback_404_if_no_episode(self):
        conv_id = uuid4()

        with (
            patch("prosales.api.v1.endpoints.episode.SQLEpisodicRepository") as MockEpRepo,
        ):
            MockEpRepo.return_value.update_feedback = AsyncMock(return_value=None)

            session = _mock_session()
            from prosales.api.v1.dependencies import get_db_session
            app.dependency_overrides[get_db_session] = lambda: session

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/v1/conversation/{conv_id}/episode",
                    json={"outcome": "lost"},
                )

            assert response.status_code == 404

            app.dependency_overrides.clear()
