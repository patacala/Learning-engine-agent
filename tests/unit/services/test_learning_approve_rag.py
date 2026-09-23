"""MoveApprover feeds RAG on approval (positive plays only)."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from prosales.services.learning_pipeline import MoveApprover


def _model(polarity: str):
    m = MagicMock()
    m.polarity = polarity
    m.transcript_excerpt = "Agente: Muchos clientes empezaron con esa duda."
    m.move_kind = "objection_handling"
    m.goal = "resolver objeción"
    m.agent_version_id = uuid4()
    m.organization_id = None
    m.score = 0.8
    m.evidence_source_id = uuid4()
    return m


def _approver():
    session = MagicMock()
    session.scalar = AsyncMock(return_value=uuid4())  # evidence -> session_id
    session.flush = AsyncMock()
    approver = MoveApprover(session)
    return approver, session


@pytest.mark.asyncio
async def test_positive_move_indexed_to_rag():
    approver, _ = _approver()
    with (
        patch("prosales.engines.knowledge.indexer.index_document", new=AsyncMock()) as idx,
        patch(
            "prosales.infrastructure.database.repositories.learning_session.SQLLearningSessionRepository.increment_approved",
            new=AsyncMock(),
        ) as inc,
    ):
        await approver._finalize_approval(_model("positive"))
        idx.assert_called_once()
        assert idx.call_args.kwargs["category"] == "learning:objection_handling"
        inc.assert_called_once()


@pytest.mark.asyncio
async def test_anti_pattern_not_indexed_to_rag():
    approver, _ = _approver()
    with (
        patch("prosales.engines.knowledge.indexer.index_document", new=AsyncMock()) as idx,
        patch(
            "prosales.infrastructure.database.repositories.learning_session.SQLLearningSessionRepository.increment_approved",
            new=AsyncMock(),
        ),
    ):
        await approver._finalize_approval(_model("negative"))
        idx.assert_not_called()  # anti-patterns must never feed RAG


@pytest.mark.asyncio
async def test_approve_passes_sibling_kinds_to_clusterer():
    """objection_handling's cross-move_kind category siblings (incl. reframe)
    are forwarded to the clusterer's merge search, widening it beyond the
    move's own move_kind."""
    approver, _ = _approver()
    model = _model("positive")
    model.embedding = [1.0, 0.0, 0.0]
    move = MagicMock()
    move.score = model.score
    move.move_kind = "objection_handling"

    approver.moves_repo.get_model = AsyncMock(return_value=model)
    approver.moves_repo.get = AsyncMock(return_value=move)
    approver.clusterer.assign = AsyncMock(return_value=uuid4())

    with (
        patch("prosales.engines.knowledge.indexer.index_document", new=AsyncMock()),
        patch(
            "prosales.infrastructure.database.repositories.learning_session.SQLLearningSessionRepository.increment_approved",
            new=AsyncMock(),
        ),
    ):
        await approver.approve(uuid4())

    approver.clusterer.assign.assert_called_once()
    kwargs = approver.clusterer.assign.call_args.kwargs
    assert "objection_handling" in kwargs["candidate_move_kinds"]
    assert "reframe" in kwargs["candidate_move_kinds"]
