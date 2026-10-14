"""Learn from a live conversation once Cognition marks it terminal.

Runs in the background (never blocks a reply). Extracts moves + DNA from the
conversation and scores them by the Cognition-inferred outcome (+ derived
appointment/purchase signals). Moves are left `pending` — Cognition's inferred
outcome alone is not verified ground truth (e.g. a client asking "can we meet
Saturday?" reads as "scheduled" even if no appointment is ever confirmed), so
nothing reaches the approved/RAG-retrievable pool automatically. A move only
becomes retrievable when a human approves it in the training UI, or later,
when a verified CRM outcome triggers approval (see api/v1/endpoints/episode.py).
Winning expressions are captured only when the outcome was positive (scheduled).
"""

import asyncio
import logging
from datetime import datetime
from uuid import UUID

from prosales.config import settings
from prosales.di.container import create_llm_provider
from prosales.engines.evidence.models import EvidenceSource
from prosales.engines.performance.scorer import OutcomeScorer
from prosales.infrastructure.agent.resolver import resolve_agent_version_for_org
from prosales.infrastructure.database.connection import async_session_factory
from prosales.infrastructure.database.models import ConversationModel
from prosales.infrastructure.database.repositories.evidence import SQLEvidenceRepository
from prosales.infrastructure.database.repositories.moves import SQLMovesRepository
from prosales.infrastructure.vector_store.pgvector import PGVectorStore
from prosales.services.learning_pipeline import LearningPipeline

logger = logging.getLogger(__name__)

# Cap concurrent background learning so it never exhausts the DB pool / OpenAI.
_bg_semaphore = asyncio.Semaphore(settings.background_max_concurrency)
# Keep strong refs to fire-and-forget tasks so they aren't GC'd mid-flight.
_background_tasks: set[asyncio.Task] = set()


def spawn_live_learning(conversation_id: UUID) -> None:
    """Fire-and-forget live learning with a retained, tracked task (voice path)."""
    task = asyncio.create_task(run_live_learning(conversation_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def outcome_signals(outcome: str) -> tuple[bool, bool]:
    """Derive multi-signal booleans from an outcome string."""
    appointment = outcome in {"scheduled", "appointment", "converted"}
    purchase = outcome in {"converted", "purchase"}
    return appointment, purchase


async def approve_moves_for_conversation(session, conversation_id) -> None:
    """Move this conversation's extracted moves out of the `pending` pool:
    approve them, which clusters them and feeds RAG (see MoveApprover.approve).
    Called only when the outcome is trustworthy enough to learn from — a
    CRM-verified outcome (ground truth) or a confident terminal negative.
    Positive-outcome moves become retrievable proven plays; negative-outcome
    moves still cluster, dragging their cluster's success_rate so retrieval
    stays discriminating. Idempotent: already-approved moves are skipped.
    """
    from prosales.infrastructure.database.repositories.evidence import SQLEvidenceRepository
    from prosales.infrastructure.database.repositories.moves import SQLMovesRepository
    from prosales.infrastructure.vector_store.pgvector import PGVectorStore
    from prosales.services.learning_pipeline import MoveApprover

    try:
        source_id = await SQLEvidenceRepository(session).find_by_conversation(conversation_id)
        if source_id is None:
            return
        moves_repo = SQLMovesRepository(session)
        pending = [m for m in await moves_repo.list_by_source(source_id) if m.status == "pending"]
        if not pending:
            return
        approver = MoveApprover(
            session, vector_store=PGVectorStore(session, organization_id=pending[0].organization_id)
        )
        for m in pending:
            await approver.approve(m.id)
    except Exception as e:  # noqa: BLE001 — approval must never block the caller
        logger.warning("Move auto-approval failed (non-fatal): %s", e)


async def run_live_learning(conversation_id: UUID) -> None:
    """Idempotent: extracts + scores pending moves for a terminal conversation once."""
    try:
        async with _bg_semaphore:  # bound concurrency vs the DB pool / OpenAI
          async with async_session_factory() as db:
            async with db.begin():
                conv = await db.get(ConversationModel, conversation_id)
                if conv is None or conv.learned_at is not None:
                    return  # missing or already learned

                agent_version_id = conv.agent_version_id
                if agent_version_id is None and conv.organization_id:
                    agent_version_id = await resolve_agent_version_for_org(db, conv.organization_id)
                if agent_version_id is None:
                    logger.warning(
                        "live learning skipped: no agent_version for conversation %s",
                        conversation_id,
                    )
                    return

                evidence_repo = SQLEvidenceRepository(db)
                turns = await evidence_repo.read_turns_from_messages(conversation_id)
                if not turns:
                    return

                outcome = conv.outcome or "open"
                source = EvidenceSource(
                    source_type="live_conversation",
                    conversation_id=conversation_id,
                    organization_id=conv.organization_id,
                    agent_version_id=agent_version_id,
                    outcome=outcome,
                    turns=turns,
                )
                vector_store = PGVectorStore(db, organization_id=conv.organization_id)
                pipeline = LearningPipeline(
                    db, llm_provider=create_llm_provider(), vector_store=vector_store
                )
                positive = outcome == "scheduled"
                await pipeline.ingest_source(source, extract_expressions=positive)

                # Re-score moves with multi-signal so a reviewer (human or, once
                # wired, CRM-triggered approval) sees an informed score. Moves stay
                # `pending`: Cognition's inferred outcome is not verified ground
                # truth, so nothing is approved/clustered/fed to RAG here.
                appointment, purchase = outcome_signals(outcome)
                scorer = OutcomeScorer()
                moves_repo = SQLMovesRepository(db)
                moves = await moves_repo.list_by_source(source.id)
                for m in moves:
                    new_score = scorer.score(
                        client_state_before=m.client_state_before,
                        client_state_after=m.client_state_after,
                        outcome=outcome,
                        appointment_scheduled=appointment,
                        purchase=purchase,
                    ).score
                    await moves_repo.set_score(m.id, new_score)

                # A confident terminal negative (lost) is reliable enough to
                # learn from: cluster these moves as negatives so they drag the
                # success_rate of plays that don't work, keeping retrieval
                # discriminating. Positives are NEVER approved here — only on
                # CRM-verified ground truth (see the verified-outcome endpoint).
                if outcome == "lost":
                    await approve_moves_for_conversation(db, conversation_id)

                conv.learned_at = datetime.utcnow()
        logger.info("live learning complete for conversation %s (outcome=%s)", conversation_id, outcome)
    except Exception as e:  # noqa: BLE001 — background task must never crash the app
        logger.error("live learning failed for %s: %s", conversation_id, e)
