"""Episode endpoints — close conversation and update feedback."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from prosales.api.v1.dependencies import get_db_session, verify_internal_or_api_key
from prosales.core.models.events import EpisodeExtracted
from prosales.engines.episodic.engine import EpisodicMemoryEngine
from prosales.engines.episodic.extractor import EpisodeExtractor
from prosales.engines.episodic.models import Episode, EpisodeFeedback
from prosales.engines.learning.event_store import EventStore
from prosales.infrastructure.database.models import EventModel
from prosales.infrastructure.database.repositories.conversation import SQLConversationRepository
from prosales.infrastructure.database.repositories.episodic import SQLEpisodicRepository
from prosales.infrastructure.database.repositories.event import SQLEventRepository
from prosales.services.live_learning import run_live_learning

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversation", tags=["episode"], dependencies=[Depends(verify_internal_or_api_key)])


async def _capture_dna(session, conversation_id, organization_id) -> None:
    """Build and persist Conversation DNA from a conversation's messages."""
    from prosales.di.container import create_llm_provider
    from prosales.engines.dna.profiler import DNAProfiler
    from prosales.engines.evidence.models import EvidenceSource
    from prosales.infrastructure.database.repositories.dna import SQLDNARepository
    from prosales.infrastructure.database.repositories.evidence import SQLEvidenceRepository

    try:
        turns = await SQLEvidenceRepository(session).read_turns_from_messages(conversation_id)
        if not turns:
            return
        source = EvidenceSource(
            source_type="live_conversation",
            conversation_id=conversation_id,
            organization_id=organization_id,
            turns=turns,
        )
        dna = await DNAProfiler(create_llm_provider()).profile(source)
        await SQLDNARepository(session).save(dna)
    except Exception as e:  # noqa: BLE001 — DNA capture must never block close
        logger.warning("DNA capture failed (non-fatal): %s", e)


async def _propagate_outcome_to_clusters(session, conversation_id, outcome) -> None:
    """When CRM outcome arrives, re-score live moves and their clusters."""
    from prosales.engines.performance.clusterer import PatternClusterer
    from prosales.engines.performance.scorer import OutcomeScorer
    from prosales.infrastructure.database.repositories.evidence import SQLEvidenceRepository
    from prosales.infrastructure.database.repositories.moves import SQLMovesRepository
    from prosales.infrastructure.database.repositories.performance import SQLPerformanceRepository

    from prosales.services.live_learning import outcome_signals

    try:
        evidence_repo = SQLEvidenceRepository(session)
        source_id = await evidence_repo.find_by_conversation(conversation_id)
        if source_id is None:
            return
        await evidence_repo.set_outcome(source_id, outcome)

        appointment, purchase = outcome_signals(outcome)
        moves_repo = SQLMovesRepository(session)
        scorer = OutcomeScorer()
        moves = await moves_repo.list_by_source(source_id)
        affected_clusters = set()
        for m in moves:
            new_score = scorer.score(
                client_state_before=m.client_state_before,
                client_state_after=m.client_state_after,
                outcome=outcome,
                appointment_scheduled=appointment,
                purchase=purchase,
                human_rating=m.human_rating,
            ).score
            await moves_repo.set_score(m.id, new_score)
            if m.cluster_id:
                affected_clusters.add(m.cluster_id)
        await session.flush()

        clusterer = PatternClusterer(SQLPerformanceRepository(session))
        for cluster_id in affected_clusters:
            members = await moves_repo.list_by_cluster(cluster_id)
            await clusterer.recompute_cluster(cluster_id, members)
    except Exception as e:  # noqa: BLE001
        logger.warning("Outcome propagation failed (non-fatal): %s", e)


@router.post("/{conversation_id}/close", response_model=Episode)
async def close_conversation(
    conversation_id: UUID,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
):
    """Close a conversation and extract an Episode with observable facts."""
    conversation_repo = SQLConversationRepository(session)
    event_repo = SQLEventRepository(session)
    episodic_repo = SQLEpisodicRepository(session)

    # Verify conversation exists
    conversation = await conversation_repo.get_by_id(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if already closed
    existing = await episodic_repo.get_by_conversation(conversation_id)
    if existing:
        raise HTTPException(status_code=409, detail="Conversation already closed")

    # Extract and persist episode
    extractor = EpisodeExtractor(event_repo, conversation_repo)
    engine = EpisodicMemoryEngine(extractor, episodic_repo)

    try:
        episode = await engine.close_conversation(conversation_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Episode extraction failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Episode extraction failed: {e}")

    # Mark conversation as inactive
    conversation.is_active = False
    conversation.updated_at = datetime.utcnow()
    await session.flush()

    # Explicit close is a definitive end → learn from it (moves + DNA) in background.
    background_tasks.add_task(run_live_learning, conversation_id)

    # Emit event
    event_store = EventStore(event_repo)
    await event_store.store(
        EpisodeExtracted(
            conversation_id=conversation_id,
            client_id=conversation.client_id,
            data={
                "episode_id": str(episode.id),
                "dominant_intent": episode.dominant_intent,
                "strategies_used": episode.strategies_used,
                "message_count": episode.message_count,
            },
        )
    )

    return episode


@router.patch("/{conversation_id}/episode", response_model=Episode)
async def update_episode_feedback(
    conversation_id: UUID,
    feedback: EpisodeFeedback,
    session: AsyncSession = Depends(get_db_session),
):
    """Optional CRM override of the outcome (Cognition is the primary source)."""
    episodic_repo = SQLEpisodicRepository(session)

    updated = await episodic_repo.update_feedback(
        conversation_id, feedback.outcome, feedback.outcome_notes
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Episode not found for this conversation")

    # CRM override wins over the Cognition-inferred outcome on the conversation.
    from sqlalchemy import update as sa_update

    from prosales.infrastructure.database.models import ConversationModel

    await session.execute(
        sa_update(ConversationModel)
        .where(ConversationModel.id == conversation_id)
        .values(outcome=feedback.outcome, updated_at=datetime.utcnow())
    )

    # Propagate the real outcome into evidence-based performance (re-score clusters).
    await _propagate_outcome_to_clusters(session, conversation_id, feedback.outcome)

    # Convert model back to Episode DTO
    return Episode(
        id=updated.id,
        conversation_id=updated.conversation_id,
        client_id=updated.client_id,
        organization_id=updated.organization_id,
        started_at=updated.started_at,
        closed_at=updated.closed_at,
        duration_seconds=updated.duration_seconds,
        message_count=updated.message_count,
        dominant_intent=updated.dominant_intent,
        dominant_sentiment=updated.dominant_sentiment,
        sentiment_shifts=updated.sentiment_shifts,
        final_stage=updated.final_stage,
        objections_detected=updated.objections_detected or [],
        strategies_used=updated.strategies_used or [],
        urgency_signals=updated.urgency_signals or [],
        risk_signals=updated.risk_signals or [],
        outcome=updated.outcome,
        outcome_notes=updated.outcome_notes,
    )
