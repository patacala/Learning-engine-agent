"""Live learning scores moves from Cognition's inferred outcome but must NOT
auto-approve them — Cognition's outcome is not verified ground truth (see
Fase 2.1 of the improvement plan). Approval only happens via a human in the
training UI, or later, via a verified CRM outcome (episode.py)."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

import prosales.services.live_learning as live_learning


def test_module_never_imports_approver():
    """Regression guard: auto-approve must not sneak back in via this import."""
    assert not hasattr(live_learning, "MoveApprover")


@pytest.mark.asyncio
async def test_run_live_learning_scores_but_does_not_approve():
    conversation_id = uuid4()
    agent_version_id = uuid4()
    source_id = uuid4()

    conv = MagicMock()
    conv.id = conversation_id
    conv.learned_at = None
    conv.organization_id = None
    conv.agent_version_id = agent_version_id
    conv.outcome = "scheduled"

    move = MagicMock()
    move.id = uuid4()
    move.client_state_before = "desconfiado"
    move.client_state_after = "tranquilo"

    db = MagicMock()
    db.get = AsyncMock(return_value=conv)
    db.flush = AsyncMock()

    @asynccontextmanager
    async def fake_begin():
        yield

    db.begin = fake_begin

    @asynccontextmanager
    async def fake_factory():
        yield db

    fake_source = MagicMock()
    fake_source.id = source_id

    with (
        patch.object(live_learning, "async_session_factory", fake_factory),
        patch.object(
            live_learning, "SQLEvidenceRepository"
        ) as MockEvidenceRepo,
        patch.object(live_learning, "SQLMovesRepository") as MockMovesRepo,
        patch.object(live_learning, "LearningPipeline") as MockPipeline,
        patch.object(live_learning, "EvidenceSource", return_value=fake_source),
        patch.object(live_learning, "PGVectorStore"),
        patch.object(live_learning, "create_llm_provider"),
    ):
        MockEvidenceRepo.return_value.read_turns_from_messages = AsyncMock(
            return_value=[{"role": "client", "text": "hola"}]
        )
        MockPipeline.return_value.ingest_source = AsyncMock()
        moves_repo = MockMovesRepo.return_value
        moves_repo.list_by_source = AsyncMock(return_value=[move])
        moves_repo.set_score = AsyncMock()

        await live_learning.run_live_learning(conversation_id)

    # Scored ...
    moves_repo.set_score.assert_awaited_once()
    assert moves_repo.set_score.await_args.args[0] == move.id

    # ... but never approved: approval (via MoveApprover) would attach a
    # cluster and flip status, neither of which run_live_learning may do.
    moves_repo.attach_cluster.assert_not_called()
    moves_repo.update_status.assert_not_called()
    assert conv.learned_at is not None
