"""Cognitive Learning Engine endpoints — the single learning flow.

Ingests transcripts/audio, groups them into sessions, extracts evidence-based
moves (shown as approvable pattern cards), and exposes the aggregate learned
knowledge (clusters, expressions, style, insights, DNA).
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from learning_engine.api.v1.dependencies import get_db_session, verify_internal_token
from learning_engine.api.v1.endpoints._sse import _sse_event
from learning_engine.config import settings
from learning_engine.di.container import create_llm_provider
from learning_engine.engines.insights.generator import InsightGenerator
from learning_engine.infrastructure.database.connection import async_session_factory
from learning_engine.infrastructure.database.models_learning_session import LearningSessionModel
from learning_engine.infrastructure.database.repositories.dna import SQLDNARepository
from learning_engine.infrastructure.database.repositories.evidence import SQLEvidenceRepository
from learning_engine.infrastructure.database.repositories.expressions import SQLExpressionsRepository
from learning_engine.infrastructure.database.repositories.insights import SQLInsightsRepository
from learning_engine.infrastructure.database.repositories.learning_session import (
    SQLLearningSessionRepository,
)
from learning_engine.infrastructure.database.repositories.moves import SQLMovesRepository
from learning_engine.infrastructure.database.repositories.performance import SQLPerformanceRepository
from learning_engine.infrastructure.database.repositories.style import SQLStyleRepository
from learning_engine.infrastructure.vector_store.pgvector import PGVectorStore
from learning_engine.services.learning_pipeline import LearningPipeline, MoveApprover
from learning_engine.services.transcription import AudioTranscriber

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/learning", tags=["learning"], dependencies=[Depends(verify_internal_token)])


class MoveUpdate(BaseModel):
    status: str  # approved | rejected
    human_rating: float | None = None


class BatchMoveUpdate(BaseModel):
    move_ids: list[UUID]
    status: str  # approved | rejected


class InsightUpdate(BaseModel):
    status: str  # published | dismissed


def _cluster_dict(m) -> dict:
    return {
        "id": str(m.id),
        "move_kind": m.move_kind,
        "polarity": m.polarity,
        "canonical_excerpt": m.canonical_excerpt,
        "occurrence_count": m.occurrence_count,
        "positive_count": m.positive_count,
        "negative_count": m.negative_count,
        "success_rate": m.success_rate,
        "avg_score": m.avg_score,
        "condition_profile": m.condition_profile or {},
        "rank": m.rank,
    }


def _move_to_proposal(m, session_id=None) -> dict:
    """Shape a ConversationMove like the UI's approvable pattern card."""
    return {
        "id": str(m.id),
        "session_id": str(session_id) if session_id else None,
        "agent_version_id": str(m.agent_version_id) if m.agent_version_id else None,
        "pattern_type": m.move_kind,
        "title": m.goal or m.move_kind,
        "content": m.transcript_excerpt,
        "raw_excerpt": m.transcript_excerpt,
        "confidence": m.score,
        "status": m.status,
        # Move-specific fields for the enhanced PatternCard
        "polarity": m.polarity,
        "client_state_before": m.client_state_before,
        "client_state_after": m.client_state_after,
        "score": m.score,
        "outcome_label": m.outcome_label,
        "start_turn_index": m.start_turn_index,
        "end_turn_index": m.end_turn_index,
    }


def _session_dict(s) -> dict:
    return {
        "id": str(s.id),
        "agent_version_id": str(s.agent_version_id),
        "source_label": s.source_label,
        "source_type": s.source_type,
        "status": s.status,
        "patterns_extracted": s.moves_extracted,
        "patterns_approved": s.moves_approved,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


async def _run_extraction(db, agent_version_id, text, session_row, organization_id, outcome):
    """Extract moves/expressions/DNA for a transcript into an existing session."""
    pipeline = LearningPipeline(
        db, llm_provider=create_llm_provider(), vector_store=PGVectorStore(db)
    )
    result = await pipeline.ingest_transcript(
        transcript=text,
        agent_version_id=agent_version_id,
        organization_id=organization_id,
        session_id=session_row.id,
        outcome=outcome,
    )
    await pipeline.recompute_style(agent_version_id)
    session_repo = SQLLearningSessionRepository(db)
    await session_repo.increment_extracted(session_row.id, result["counts"]["moves"])
    await session_repo.update_status(session_row.id, "completed")
    return {
        "session_id": str(session_row.id),
        "source_label": session_row.source_label,
        "patterns_extracted": result["counts"]["moves"],
        "proposals": [_move_to_proposal(m, session_row.id) for m in result["moves"]],
    }


@router.post("/ingest")
async def ingest(
    agent_version_id: UUID = Form(...),
    transcript: str | None = Form(None),
    source_label: str = Form(""),
    session_id: str = Form(""),
    outcome: str = Form("pending"),
    organization_id: str = Form(""),
    audio: UploadFile | None = File(None),
):
    """Ingest a transcript or audio → SSE stream of stages → moves as proposals."""
    audio_bytes = await audio.read() if audio else None
    audio_filename = audio.filename if audio else None

    async def event_stream():
        try:
            text = (transcript or "").strip()
            source_type = "text"

            if audio_bytes:
                yield _sse_event({"stage": "transcribing"})
                try:
                    text = await AudioTranscriber(api_key=settings.openai_api_key).transcribe(
                        audio_bytes, audio_filename or "audio.mp3"
                    )
                    source_type = "audio"
                except ValueError as e:
                    yield _sse_event({"stage": "error", "message": str(e)})
                    return
                except Exception as e:  # noqa: BLE001
                    logger.error("Transcription failed: %s", e)
                    yield _sse_event({"stage": "error", "message": "Transcription failed"})
                    return

            if not text.strip():
                yield _sse_event({"stage": "error", "message": "Empty transcript"})
                return

            org_id = UUID(organization_id) if organization_id else None
            payload: dict
            async with async_session_factory() as db:
                async with db.begin():
                    session_repo = SQLLearningSessionRepository(db)
                    if session_id:
                        session_row = await session_repo.get_session(UUID(session_id))
                        await session_repo.append_transcript(session_row.id, text)
                    else:
                        session_row = await session_repo.save_session(
                            LearningSessionModel(
                                agent_version_id=agent_version_id,
                                organization_id=org_id,
                                source_label=source_label or text[:50],
                                transcript=text,
                                source_type=source_type,
                                status="processing",
                            )
                        )

                    yield _sse_event({"stage": "extracting"})
                    payload = await _run_extraction(
                        db, agent_version_id, text, session_row, org_id, outcome
                    )
                    yield _sse_event({"stage": "analyzing"})

            yield _sse_event({"stage": "completed", "result": payload})
        except Exception as e:  # noqa: BLE001
            logger.error("Learn ingest failed: %s", e)
            yield _sse_event({"stage": "error", "message": str(e)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/sessions")
async def list_sessions(
    agent_version_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> list[dict]:
    rows = await SQLLearningSessionRepository(session).list_sessions(agent_version_id)
    return [_session_dict(s) for s in rows]


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> dict:
    repo = SQLLearningSessionRepository(session)
    row = await repo.get_session(session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    moves = await SQLMovesRepository(session).list_by_session(session_id)
    return {
        **_session_dict(row),
        "proposals": [_move_to_proposal(m, session_id) for m in moves],
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> dict:
    ok = await SQLLearningSessionRepository(session).delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted"}


@router.post("/sessions/{session_id}/extract")
async def extract_session(
    session_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> dict:
    """Process a draft session's stored transcript into moves (Test handoff path)."""
    repo = SQLLearningSessionRepository(session)
    row = await repo.get_session(session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return await _run_extraction(
        session, row.agent_version_id, row.transcript, row, row.organization_id, "pending"
    )


@router.get("/agents/{agent_version_id}/moves")
async def list_moves(
    agent_version_id: UUID,
    status: str | None = Query(None),
    polarity: str | None = Query(None),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    repo = SQLMovesRepository(session)
    moves = await repo.list_by_agent(agent_version_id, status=status, polarity=polarity)
    return [m.model_dump(mode="json") for m in moves]


@router.patch("/moves/batch")
async def batch_update_moves(
    update: BatchMoveUpdate, session: AsyncSession = Depends(get_db_session)
) -> dict:
    """Approve or reject many moves at once (for 'Approve all')."""
    if update.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="status must be approved or rejected")
    approver = MoveApprover(session, vector_store=PGVectorStore(session))
    processed = 0
    for move_id in update.move_ids:
        if update.status == "approved":
            await approver.approve(move_id)
        else:
            await approver.reject(move_id)
        processed += 1
    return {"status": update.status, "processed": processed}


@router.patch("/moves/{move_id}")
async def update_move(
    move_id: UUID, update: MoveUpdate, session: AsyncSession = Depends(get_db_session)
) -> dict:
    approver = MoveApprover(session, vector_store=PGVectorStore(session))
    if update.status == "approved":
        cluster_id = await approver.approve(move_id, human_rating=update.human_rating)
        if cluster_id is None:
            # Either the move was missing, or it was approved without an embedding.
            existing = await SQLMovesRepository(session).get(move_id)
            if existing is None:
                raise HTTPException(status_code=404, detail="Move not found")
            return {"status": "approved", "cluster_id": None}
        return {"status": "approved", "cluster_id": str(cluster_id)}
    elif update.status == "rejected":
        await approver.reject(move_id)
        return {"status": "rejected"}
    raise HTTPException(status_code=400, detail="status must be approved or rejected")


@router.get("/agents/{agent_version_id}/clusters")
async def list_clusters(
    agent_version_id: UUID,
    move_kind: str | None = Query(None),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    repo = SQLPerformanceRepository(session)
    clusters = await repo.list_clusters(agent_version_id, move_kind=move_kind)
    return [_cluster_dict(c) for c in clusters]


@router.get("/agents/{agent_version_id}/expressions")
async def list_expressions(
    agent_version_id: UUID,
    polarity: str | None = Query(None),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    repo = SQLExpressionsRepository(session)
    exprs = await repo.list_by_agent(agent_version_id, polarity=polarity)
    return [e.model_dump(mode="json") for e in exprs]


@router.get("/agents/{agent_version_id}/strategy-performance")
async def strategy_performance(
    agent_version_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> list[dict]:
    """Learned cluster performance aggregated per strategy category."""
    from learning_engine.engines.strategy.evidence_bridge import StrategyEvidenceBridge

    return await StrategyEvidenceBridge(session).performance_by_category(agent_version_id)


@router.get("/agents/{agent_version_id}/style")
async def get_style(
    agent_version_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> dict:
    profile = await SQLStyleRepository(session).get(agent_version_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="No style profile yet")
    data = profile.model_dump(mode="json")
    data["prompt_block"] = profile.to_prompt_block()
    return data


@router.post("/agents/{agent_version_id}/style/recompute")
async def recompute_style(
    agent_version_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> dict:
    pipeline = LearningPipeline(session, llm_provider=create_llm_provider())
    await pipeline.recompute_style(agent_version_id)
    profile = await SQLStyleRepository(session).get(agent_version_id)
    return profile.model_dump(mode="json") if profile else {"status": "no_evidence"}


@router.post("/agents/{agent_version_id}/insights/generate")
async def generate_insights(
    agent_version_id: UUID,
    min_occurrences: int = Query(2),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    """Generate insights from accumulated cluster statistics (grounded, gated)."""
    clusters = await SQLPerformanceRepository(session).list_clusters(agent_version_id)
    generator = InsightGenerator(create_llm_provider(), min_occurrences=min_occurrences)
    insights = await generator.generate(clusters)

    repo = SQLInsightsRepository(session)
    vector_store = PGVectorStore(session)
    out = []
    for ins in insights:
        # Embed the rule so it can be scoped by relevance at retrieval time
        # instead of every published rule going into every prompt.
        embedding = None
        if ins.behavior_rule:
            try:
                embedding = await vector_store.embed(ins.behavior_rule[:2000])
            except Exception as e:  # noqa: BLE001 — embedding is best-effort
                logger.warning("Insight embedding failed (non-fatal): %s", e)
        ins.id = await repo.save(ins, agent_version_id, embedding=embedding)
        out.append(ins.model_dump(mode="json"))
    return out


@router.get("/agents/{agent_version_id}/insights")
async def list_insights(
    agent_version_id: UUID,
    status: str | None = Query(None),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    insights = await SQLInsightsRepository(session).list_by_agent(agent_version_id, status=status)
    return [i.model_dump(mode="json") for i in insights]


@router.patch("/insights/{insight_id}")
async def update_insight(
    insight_id: UUID, update: InsightUpdate, session: AsyncSession = Depends(get_db_session)
) -> dict:
    if update.status not in ("published", "dismissed"):
        raise HTTPException(status_code=400, detail="status must be published or dismissed")
    insight = await SQLInsightsRepository(session).update_status(insight_id, update.status)
    if insight is None:
        raise HTTPException(status_code=404, detail="Insight not found")
    return insight.model_dump(mode="json")


@router.get("/dna/{conversation_id}")
async def get_dna(
    conversation_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> dict:
    dna = await SQLDNARepository(session).get_by_conversation(conversation_id)
    if dna is None:
        raise HTTPException(status_code=404, detail="No DNA for conversation")
    return dna.model_dump(mode="json")


@router.get("/dna/{conversation_id}/similar")
async def similar_dna(
    conversation_id: UUID,
    outcome: str | None = Query(None),
    limit: int = Query(5),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    repo = SQLDNARepository(session)
    dna = await repo.get_by_conversation(conversation_id)
    if dna is None:
        raise HTTPException(status_code=404, detail="No DNA for conversation")
    return await repo.similar(
        dna.to_vector(), outcome=outcome, exclude_id=dna.id, limit=limit
    )
