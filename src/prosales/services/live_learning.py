"""Learn from a live conversation once Cognition marks it terminal.

Runs in the background (never blocks a reply). Extracts moves + DNA from the
conversation, scores them by the Cognition-inferred outcome (+ derived
appointment/purchase signals), auto-approves and clusters them, and feeds RAG.
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
from prosales.services.learning_pipeline import LearningPipeline, MoveApprover

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


async def run_live_learning(conversation_id: UUID) -> None:
    """Idempotent: extracts + clusters moves for a terminal conversation once."""
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
                pipeline = LearningPipeline(
                    db, llm_provider=create_llm_provider(), vector_store=PGVectorStore(db)
                )
                positive = outcome == "scheduled"
                await pipeline.ingest_source(source, extract_expressions=positive)

                # Re-score moves with multi-signal, then auto-approve + cluster + RAG.
                appointment, purchase = outcome_signals(outcome)
                scorer = OutcomeScorer()
                moves_repo = SQLMovesRepository(db)
                approver = MoveApprover(db, vector_store=PGVectorStore(db))
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
                await db.flush()
                for m in moves:
                    await approver.approve(m.id)

                conv.learned_at = datetime.utcnow()
        logger.info("live learning complete for conversation %s (outcome=%s)", conversation_id, outcome)
    except Exception as e:  # noqa: BLE001 — background task must never crash the app
        logger.error("live learning failed for %s: %s", conversation_id, e)
