"""Agent listing and brain endpoints — for Training UI."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from prosales.api.v1.dependencies import get_db_session, verify_internal_token
from prosales.infrastructure.database.models import KnowledgeDocumentModel
from prosales.infrastructure.database.models_agent import (
    AgentIdentityModel,
    AgentModel,
    AgentStrategyModel,
    AgentVersionModel,
)
from prosales.infrastructure.database.models_moves import ConversationMoveModel
from prosales.infrastructure.database.models_learning_session import LearningSessionModel
from prosales.infrastructure.database.repositories.expressions import SQLExpressionsRepository
from prosales.infrastructure.database.repositories.insights import SQLInsightsRepository
from prosales.infrastructure.database.repositories.performance import SQLPerformanceRepository
from prosales.infrastructure.database.repositories.style import SQLStyleRepository

router = APIRouter(prefix="/agents", tags=["agents"], dependencies=[Depends(verify_internal_token)])

# Maps a learned move_kind to the Knowledge Areas widget bucket it belongs to
# (frontend/src/constants/categories.ts CATEGORY_ORDER). Distinct from
# MOVE_KIND_TO_CATEGORY in engines/strategy/evidence_bridge.py, which buckets
# by StrategyCategory for a different purpose — keep both in sync manually if
# MOVE_KINDS changes (engines/moves/states.py).
WIDGET_CATEGORY_FOR_MOVE_KIND: dict[str, str] = {
    "greeting": "technique",
    "rapport": "technique",
    "value_prop": "technique",
    "social_proof": "technique",
    "follow_up": "technique",
    "discovery": "needs_discovery",
    "needs_diagnosis": "needs_discovery",
    "qualification": "needs_discovery",
    "objection_handling": "objection_handling",
    "reframe": "objection_handling",
    "urgency": "closing",
    "closing": "closing",
}


@router.get("")
async def list_agents(session: AsyncSession = Depends(get_db_session)):
    """List active agents with published versions (for UI selectors)."""
    stmt = (
        select(
            AgentVersionModel.id.label("id"),
            AgentModel.name,
            AgentModel.agent_type,
            AgentModel.description,
        )
        .join(AgentModel, AgentVersionModel.agent_id == AgentModel.id)
        .where(AgentModel.is_active.is_(True))
        .where(AgentVersionModel.is_published.is_(True))
        .order_by(AgentModel.name)
    )
    result = await session.execute(stmt)
    rows = result.all()
    return [
        {
            "id": str(row.id),
            "name": row.name,
            "agent_type": row.agent_type,
            "description": row.description,
        }
        for row in rows
    ]


@router.get("/{agent_version_id}/brain")
async def get_agent_brain(
    agent_version_id: UUID,
    session: AsyncSession = Depends(get_db_session),
):
    """Get agent brain dashboard data: identity, knowledge counts, training stats."""
    # Identity
    identity_stmt = select(AgentIdentityModel).where(
        AgentIdentityModel.agent_version_id == agent_version_id
    )
    identity_result = await session.execute(identity_stmt)
    identity = identity_result.scalar_one_or_none()

    identity_data = None
    if identity:
        identity_data = {
            "name": identity.name,
            "description": identity.description,
            "communication_style": identity.communication_style,
            "principles": identity.principles or [],
            "beliefs": identity.beliefs or [],
            "values": identity.values_list or [],
            "words_never_use": identity.words_never_use or [],
            "words_prefer": identity.words_prefer or [],
        }

    # Knowledge counts by category — counts parent documents, not chunks.
    # KnowledgeDocumentModel stays one row per source document even after
    # chunking (see engines/knowledge/chunker.py, knowledge_chunks table).
    # Do not point this at KnowledgeChunkModel.
    knowledge_stmt = (
        select(
            KnowledgeDocumentModel.category,
            func.count(KnowledgeDocumentModel.id),
        )
        .group_by(KnowledgeDocumentModel.category)
    )
    knowledge_result = await session.execute(knowledge_stmt)
    knowledge_counts = {row[0]: row[1] for row in knowledge_result.all()}

    # Learned stats — counts only; no raw-text fetch, so this stays cheap
    # however many moves accumulate.
    total_stmt = select(func.count(ConversationMoveModel.id)).where(
        ConversationMoveModel.agent_version_id == agent_version_id
    )
    total_moves = (await session.execute(total_stmt)).scalar() or 0

    approved_stmt = (
        select(func.count(ConversationMoveModel.id))
        .where(ConversationMoveModel.agent_version_id == agent_version_id)
        .where(ConversationMoveModel.status == "approved")
    )
    approved_count = (await session.execute(approved_stmt)).scalar() or 0

    sessions_stmt = select(func.count(LearningSessionModel.id)).where(
        LearningSessionModel.agent_version_id == agent_version_id
    )
    total_sessions = (await session.execute(sessions_stmt)).scalar() or 0

    clusters = await SQLPerformanceRepository(session).list_clusters(agent_version_id)
    expressions = await SQLExpressionsRepository(session).list_by_agent(agent_version_id)
    style = await SQLStyleRepository(session).get(agent_version_id)
    insights = await SQLInsightsRepository(session).list_by_agent(agent_version_id)

    # "Learned" per category is built from clusters, NOT raw approved moves:
    # clusters already dedupe near-identical evidence and carry a real
    # success_rate, so this stays browsable at any volume of training data
    # instead of listing every single approved move under a repeated title.
    from prosales.engines.knowledge.pattern_retriever import confidence_label

    learned_items: dict[str, list] = {}
    for c in sorted(clusters, key=lambda c: c.success_rate, reverse=True):
        if not c.canonical_excerpt:
            continue
        label = confidence_label(c.occurrence_count, c.success_rate, c.avg_score)
        # Group by the Knowledge Areas widget bucket, not the raw move_kind —
        # the UI's category ids (needs_discovery, technique, ...) don't match
        # move_kind values 1:1 (e.g. "discovery" + "needs_diagnosis" both feed
        # "needs_discovery"). See WIDGET_CATEGORY_FOR_MOVE_KIND above.
        bucket = WIDGET_CATEGORY_FOR_MOVE_KIND.get(c.move_kind, c.move_kind)
        learned_items.setdefault(bucket, []).append(
            {
                "id": str(c.id),
                "title": f"{c.move_kind} · {label}",
                "content": c.canonical_excerpt,
            }
        )

    return {
        "identity": identity_data,
        "knowledge": knowledge_counts,
        "training": {
            "total_sessions": total_sessions,
            "total_extracted": total_moves,
            "approved": approved_count,
            "pending": 0,
            "rejected": 0,
        },
        "learned": learned_items,
        "clusters": [
            {
                "id": str(c.id),
                "move_kind": c.move_kind,
                "polarity": c.polarity,
                "canonical_excerpt": c.canonical_excerpt,
                "success_rate": c.success_rate,
                "occurrence_count": c.occurrence_count,
                "rank": c.rank,
            }
            for c in clusters
        ],
        "expressions": [
            {
                "exact_phrase": e.exact_phrase,
                "polarity": e.polarity,
                "success_rate": e.success_rate,
                "times_used": e.times_used,
            }
            for e in expressions
        ],
        "style": (
            {**style.model_dump(mode="json"), "prompt_block": style.to_prompt_block()}
            if style
            else None
        ),
        "insights": [i.model_dump(mode="json") for i in insights],
    }


@router.get("/{agent_version_id}/strategy-catalog")
async def get_strategy_catalog(
    agent_version_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """What StrategyEngine actually uses for this agent right now.

    The switch is all-or-nothing at the agent level (see StrategyEngine.process):
    if the agent has ANY custom strategy configured, ALL selection uses ONLY
    those — the built-in catalog becomes entirely unreachable for this agent,
    even for strategy_types the custom set doesn't cover. If the agent has
    none, every selection falls back to the built-in catalog (generic,
    hardcoded in engines/strategy/catalog.py — not editable from this API).
    """
    from prosales.engines.strategy.catalog import STRATEGY_CATALOG

    stmt = (
        select(AgentStrategyModel)
        .options(selectinload(AgentStrategyModel.tactics))
        .where(AgentStrategyModel.agent_version_id == agent_version_id)
    )
    custom = (await session.execute(stmt)).scalars().all()

    if custom:
        return {
            "mode": "custom",
            "note": (
                "Este agente tiene estrategias propias configuradas — el catálogo "
                "genérico por defecto no se usa en absoluto para este agente."
            ),
            "strategies": [
                {
                    "strategy_type": s.strategy_type,
                    "name": s.name,
                    "source": "custom",
                    "enabled": s.enabled,
                    "tactics": [
                        {"name": t.name, "prompt_instruction": t.prompt_instruction}
                        for t in sorted(s.tactics, key=lambda t: t.position)
                    ],
                }
                for s in custom
            ],
        }

    return {
        "mode": "default",
        "note": (
            "Este agente no tiene estrategias propias — usa el catálogo genérico "
            "de fábrica para TODAS las situaciones (objeciones, cierre, descubrimiento, "
            "etc.), sin conocimiento de este negocio en particular."
        ),
        "strategies": [
            {
                "strategy_type": st.value,
                "name": strat.name,
                "source": "default",
                "enabled": True,
                "tactics": [
                    {"name": t.name, "prompt_instruction": t.prompt_instruction}
                    for t in strat.tactics
                ],
            }
            for st, strat in STRATEGY_CATALOG.items()
        ],
    }
