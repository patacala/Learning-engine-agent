"""Repository for Conversation DNA + similarity search."""

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from prosales.engines.dna.models import ConversationDNA
from prosales.infrastructure.database.models_dna import ConversationDNAModel


def _to_dto(m: ConversationDNAModel) -> ConversationDNA:
    return ConversationDNA(
        id=m.id,
        evidence_source_id=m.evidence_source_id,
        conversation_id=m.conversation_id,
        agent_version_id=m.agent_version_id,
        organization_id=m.organization_id,
        trust_score=m.trust_score,
        curiosity_score=m.curiosity_score,
        empathy_score=m.empathy_score,
        urgency_score=m.urgency_score,
        storytelling_score=m.storytelling_score,
        pressure_score=m.pressure_score,
        question_count=m.question_count,
        objection_count=m.objection_count,
        objections_resolved=m.objections_resolved,
        avg_turn_length=m.avg_turn_length,
        talk_ratio=m.talk_ratio,
        conversational_balance=m.conversational_balance,
        outcome=m.outcome,
    )


class SQLDNARepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, dna: ConversationDNA) -> UUID:
        model = ConversationDNAModel(
            evidence_source_id=dna.evidence_source_id,
            conversation_id=dna.conversation_id,
            agent_version_id=dna.agent_version_id,
            organization_id=dna.organization_id,
            trust_score=dna.trust_score,
            curiosity_score=dna.curiosity_score,
            empathy_score=dna.empathy_score,
            urgency_score=dna.urgency_score,
            storytelling_score=dna.storytelling_score,
            pressure_score=dna.pressure_score,
            question_count=dna.question_count,
            objection_count=dna.objection_count,
            objections_resolved=dna.objections_resolved,
            avg_turn_length=dna.avg_turn_length,
            talk_ratio=dna.talk_ratio,
            conversational_balance=dna.conversational_balance,
            dna_vector=dna.to_vector(),
            outcome=dna.outcome,
        )
        self.session.add(model)
        await self.session.flush()
        dna.id = model.id
        return model.id

    async def get_by_conversation(self, conversation_id: UUID) -> ConversationDNA | None:
        stmt = select(ConversationDNAModel).where(
            ConversationDNAModel.conversation_id == conversation_id
        )
        m = (await self.session.execute(stmt)).scalar_one_or_none()
        return _to_dto(m) if m else None

    async def similar(
        self,
        dna_vector: list[float],
        outcome: str | None = None,
        agent_version_id: UUID | None = None,
        exclude_id: UUID | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """Find behaviorally similar conversations (optionally filtered by outcome)."""
        vec = "[" + ",".join(str(x) for x in dna_vector) + "]"
        where = ["dna_vector IS NOT NULL"]
        params: dict = {"vec": vec, "limit": limit}
        if outcome:
            where.append("outcome = :outcome")
            params["outcome"] = outcome
        if agent_version_id:
            where.append("agent_version_id = :avid")
            params["avid"] = str(agent_version_id)
        if exclude_id:
            where.append("id <> :exclude")
            params["exclude"] = str(exclude_id)
        where_sql = " AND ".join(where)
        stmt = text(f"""
            SELECT id, conversation_id, outcome, trust_score, empathy_score,
                   dna_vector <=> CAST(:vec AS vector) AS distance
            FROM conversation_dna
            WHERE {where_sql}
            ORDER BY distance
            LIMIT :limit
        """)
        rows = (await self.session.execute(stmt, params)).fetchall()
        return [
            {
                "id": str(r.id),
                "conversation_id": str(r.conversation_id) if r.conversation_id else None,
                "outcome": r.outcome,
                "trust_score": r.trust_score,
                "empathy_score": r.empathy_score,
                "distance": float(r.distance),
            }
            for r in rows
        ]
