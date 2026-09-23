"""LearningPipeline — orchestrates the evidence-based learning flow.

    transcript / conversation
        -> Evidence (parse + persist)
        -> Conversation Moves (anchored + multi-signal scored)
        -> Winning/Anti Expressions (aggregated)
        -> Conversation DNA
        -> Style profile (recomputed from all of an agent's evidence)

Moves are stored as pending proposals; approving a move (MoveApprover) embeds it
and assigns it to a competing pattern cluster.
"""

import logging
from uuid import UUID

from prosales.engines.dna.profiler import DNAProfiler
from prosales.engines.evidence.models import EvidenceSource
from prosales.engines.evidence.parser import TranscriptParser
from prosales.engines.expressions.extractor import ExpressionExtractor
from prosales.engines.identity_learning.profiler import StyleProfiler
from prosales.engines.moves.extractor import MoveExtractor
from prosales.engines.performance.clusterer import PatternClusterer, _to_list
from prosales.engines.performance.scorer import OutcomeScorer
from prosales.engines.strategy.evidence_bridge import (
    CATEGORY_TO_MOVE_KINDS,
    MOVE_KIND_TO_CATEGORY,
)
from prosales.infrastructure.database.repositories.dna import SQLDNARepository
from prosales.infrastructure.database.repositories.evidence import SQLEvidenceRepository
from prosales.infrastructure.database.repositories.expressions import SQLExpressionsRepository
from prosales.infrastructure.database.repositories.moves import SQLMovesRepository
from prosales.infrastructure.database.repositories.performance import SQLPerformanceRepository
from prosales.infrastructure.database.repositories.style import SQLStyleRepository

logger = logging.getLogger(__name__)


class LearningPipeline:
    def __init__(self, session, llm_provider=None, vector_store=None):
        self.session = session
        self.parser = TranscriptParser()
        self.move_extractor = MoveExtractor(llm_provider) if llm_provider else None
        self.expr_extractor = ExpressionExtractor(llm_provider) if llm_provider else None
        self.dna_profiler = DNAProfiler(llm_provider)
        self.style_profiler = StyleProfiler(llm_provider)
        self.scorer = OutcomeScorer()
        self.vector_store = vector_store

        self.evidence_repo = SQLEvidenceRepository(session)
        self.moves_repo = SQLMovesRepository(session)
        self.expr_repo = SQLExpressionsRepository(session)
        self.dna_repo = SQLDNARepository(session)
        self.style_repo = SQLStyleRepository(session)

    async def _embed(self, text: str) -> list[float] | None:
        if not self.vector_store or not text:
            return None
        try:
            return await self.vector_store.embed(text[:8000])
        except Exception as e:  # noqa: BLE001
            logger.warning("Embedding failed (non-fatal): %s", e)
            return None

    async def ingest_transcript(
        self,
        transcript: str,
        agent_version_id: UUID,
        organization_id: UUID | None = None,
        session_id: UUID | None = None,
        source_type: str = "expert_transcript",
        outcome: str = "pending",
    ) -> dict:
        source = self.parser.to_source(
            transcript,
            source_type=source_type,
            agent_version_id=agent_version_id,
            organization_id=organization_id,
            session_id=session_id,
            outcome=outcome,
        )
        return await self.ingest_source(source)

    async def ingest_source(self, source: EvidenceSource, extract_expressions: bool = True) -> dict:
        """Run the full learning flow over one parsed evidence source.

        ``extract_expressions=False`` (used for live conversations that didn't
        convert) skips winning/anti expression capture to keep them curated.
        """
        await self.evidence_repo.save_source(source)  # sets source.id

        conv_outcome = source.outcome if source.outcome and source.outcome != "pending" else None

        # --- Conversation Moves (scored + embedded, saved as pending) ---
        moves = await self.move_extractor.extract(source) if self.move_extractor else []
        for m in moves:
            m.score = self.scorer.score(
                client_state_before=m.client_state_before,
                client_state_after=m.client_state_after,
                outcome=conv_outcome,
            ).score
            embedding = await self._embed(m.transcript_excerpt)
            await self.moves_repo.save(m, embedding=embedding)

        # --- Expressions (winning / anti, aggregated) ---
        expressions = []
        if extract_expressions and self.expr_extractor:
            expressions = await self.expr_extractor.extract(source)
            for e in expressions:
                e.score = 0.7 if e.polarity == "winning" else 0.2
                embedding = await self._embed(e.exact_phrase)
                await self.expr_repo.upsert(e, embedding=embedding)

        # --- Conversation DNA ---
        dna = await self.dna_profiler.profile(source)
        await self.dna_repo.save(dna)

        return {
            "evidence_source_id": str(source.id),
            "moves": moves,
            "expressions": expressions,
            "dna": dna,
            "counts": {
                "moves": len(moves),
                "expressions": len(expressions),
            },
        }

    async def recompute_style(self, agent_version_id: UUID) -> None:
        """Recompute the agent's style profile from all its evidence sources."""
        from sqlalchemy import select

        from prosales.infrastructure.database.models_evidence import EvidenceSourceModel

        ids = (
            await self.session.execute(
                select(EvidenceSourceModel.id).where(
                    EvidenceSourceModel.agent_version_id == agent_version_id
                )
            )
        ).scalars().all()
        sources = []
        for sid in ids:
            src = await self.evidence_repo.get_source(sid)
            if src:
                sources.append(src)
        if not sources:
            return
        profile = await self.style_profiler.profile(sources)
        profile.agent_version_id = agent_version_id
        await self.style_repo.upsert(profile)


class MoveApprover:
    """Approve/reject a move; approval triggers clustering (Performance layer)."""

    def __init__(self, session, vector_store=None):
        self.session = session
        self.moves_repo = SQLMovesRepository(session)
        self.clusterer = PatternClusterer(SQLPerformanceRepository(session))
        self.scorer = OutcomeScorer()
        self.vector_store = vector_store

    async def approve(self, move_id: UUID, human_rating: float | None = None) -> UUID | None:
        model = await self.moves_repo.get_model(move_id)
        if model is None:
            return None

        if human_rating is not None:
            model.human_rating = human_rating
            model.score = self.scorer.score(
                client_state_before=model.client_state_before,
                client_state_after=model.client_state_after,
                human_rating=human_rating,
            ).score

        move = await self.moves_repo.get(move_id)  # DTO with the (possibly) new score
        move.score = model.score
        embedding = _to_list(model.embedding)
        if embedding is None and self.vector_store:
            embedding = await self.vector_store.embed(model.transcript_excerpt[:8000])
        if embedding is None:
            # Without an embedding we cannot cluster; approve without a cluster.
            model.status = "approved"
            await self._finalize_approval(model)
            await self.session.flush()
            return None

        category = MOVE_KIND_TO_CATEGORY.get(move.move_kind)
        sibling_kinds = CATEGORY_TO_MOVE_KINDS.get(category) if category else None
        cluster_id = await self.clusterer.assign(
            move, embedding, candidate_move_kinds=sibling_kinds
        )
        model.cluster_id = cluster_id
        model.status = "approved"
        await self._finalize_approval(model)
        await self.session.flush()
        return cluster_id

    async def _finalize_approval(self, model) -> None:
        """Post-approval side effects: bump the session counter and feed RAG."""
        from sqlalchemy import select

        from prosales.engines.knowledge.indexer import index_document
        from prosales.infrastructure.database.models_evidence import EvidenceSourceModel
        from prosales.infrastructure.database.repositories.learning_session import (
            SQLLearningSessionRepository,
        )

        session_id = await self.session.scalar(
            select(EvidenceSourceModel.session_id).where(
                EvidenceSourceModel.id == model.evidence_source_id
            )
        )
        if session_id:
            await SQLLearningSessionRepository(self.session).increment_approved(session_id, 1)

        # Index the verbatim evidence for RAG retrieval (positive plays only).
        # In a SAVEPOINT: a plain try/except here only stops the Python exception
        # from propagating — it does NOT protect the session's transaction state.
        # If index_document's flush fails, the whole approval (cluster creation,
        # status='approved') would be rolled back with it despite this comment's
        # intent, unless the failure is isolated to a nested transaction.
        if model.polarity == "positive" and model.transcript_excerpt.strip():
            try:
                async with self.session.begin_nested():
                    await index_document(
                        session=self.session,
                        title=(model.goal or model.move_kind),
                        content=model.transcript_excerpt,
                        category=f"learning:{model.move_kind}",
                        organization_id=model.organization_id,
                        metadata={
                            "agent_version_id": str(model.agent_version_id),
                            "source": "learning",
                            "move_kind": model.move_kind,
                            "score": model.score,
                            "session_id": str(session_id) if session_id else None,
                        },
                    )
            except Exception as e:  # noqa: BLE001 — RAG indexing must not block approval
                logger.warning("RAG indexing failed (non-fatal): %s", e)

    async def reject(self, move_id: UUID) -> None:
        await self.moves_repo.update_status(move_id, "rejected")
