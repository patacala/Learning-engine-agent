"""Timeline endpoint — enriched view of pipeline execution events."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from prosales.api.v1.dependencies import get_db_session, verify_internal_token
from prosales.api.v1.schemas.timeline import TimelineEntry, TimelineResponse
from prosales.infrastructure.database.repositories.event import SQLEventRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversation", tags=["timeline"], dependencies=[Depends(verify_internal_token)])


def _summarize_event(event_type: str, data: dict) -> str:
    """Generate a human-readable summary for an event."""
    match event_type:
        case "analyzer.completed":
            intent = data.get("intent", "unknown")
            confidence = data.get("intent_confidence", 0)
            sentiment = data.get("sentiment", "neutral")
            return f"Intent: {intent} ({confidence:.2f}), Sentiment: {sentiment}"
        case "knowledge.retrieved":
            num = data.get("num_chunks", 0)
            return f"Retrieved {num} chunks"
        case "decision.made":
            actions = data.get("actions", [])
            total = data.get("total_rules_evaluated", 0)
            return f"Actions: {actions}, {total} rules evaluated"
        case "strategy.selected":
            selected = data.get("selected", "")
            score = data.get("scores", {}).get(selected, 0)
            switched = data.get("switched", False)
            suffix = " (switched)" if switched else ""
            return f"Strategy: {selected} ({score:.2f}){suffix}"
        case "response.generated":
            model = data.get("model", "")
            tokens = data.get("total_tokens", 0)
            duration = data.get("duration_ms", 0)
            return f"{model}, {tokens} tokens, {duration:.0f}ms"
        case "pipeline.completed":
            total_ms = data.get("total_ms", 0)
            versions = data.get("versions", {})
            pipeline_v = versions.get("pipeline", "")
            return f"Completed in {total_ms:.0f}ms (pipeline v{pipeline_v})"
        case _:
            return event_type


@router.get("/{conversation_id}/timeline", response_model=TimelineResponse)
async def get_timeline(
    conversation_id: UUID,
    event_type: str | None = Query(None, description="Filter by event type"),
    session: AsyncSession = Depends(get_db_session),
):
    """Get enriched timeline of pipeline events for a conversation."""
    event_repo = SQLEventRepository(session)
    events = await event_repo.get_by_conversation(conversation_id)

    entries: list[TimelineEntry] = []
    total_duration_ms = 0.0
    total_tokens = 0
    pipeline_version = ""
    model_used = ""

    for event in events:
        # Apply filter
        if event_type and event.event_type != event_type:
            continue

        data = event.data or {}
        summary = _summarize_event(event.event_type, data)
        duration_ms = data.get("duration_ms")

        entries.append(TimelineEntry(
            timestamp=event.timestamp,
            event_type=event.event_type,
            summary=summary,
            details=data,
            duration_ms=duration_ms,
        ))

        # Aggregate stats from pipeline.completed
        if event.event_type == "pipeline.completed":
            total_duration_ms = data.get("total_ms", 0)
            versions = data.get("versions", {})
            pipeline_version = versions.get("pipeline", "")
            model_used = versions.get("model", "")

        # Aggregate tokens from response.generated
        if event.event_type == "response.generated":
            total_tokens += data.get("total_tokens", 0)

    return TimelineResponse(
        conversation_id=conversation_id,
        entries=entries,
        total_duration_ms=total_duration_ms,
        total_tokens=total_tokens,
        pipeline_version=pipeline_version,
        model_used=model_used,
    )
