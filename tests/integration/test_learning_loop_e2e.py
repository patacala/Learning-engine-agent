"""End-to-end regression test for the learning loop this project actually depends on:

    ingest a transcript -> a move gets extracted -> a human approves it ->
    a LATER, unrelated conversation retrieves it via PatternRetriever and it
    would be injected into that conversation's prompt.

Before this test, that loop had been verified exactly once, manually, in a chat
session -- never as a repeatable regression test (tests/integration/ was empty
except for __init__.py). If this test ever goes red, "the agent learns from
ingested conversations" has silently stopped being true.

The LLM call inside MoveExtractor and the embedding call inside the approval
step are faked (deterministic, no network/API key needed) -- this test's job is
to prove the DB-backed ingest -> approve -> cluster -> retrieve WIRING works,
not to grade LLM extraction quality (that's a separate concern, already covered
informally by manual review in this project's learning pipeline work).
"""

from uuid import uuid4

import pytest
from sqlalchemy import text

# Registers Organization (and other agent models) in Base.metadata. Without this,
# approval's RAG-indexing step fails to resolve the knowledge_documents.organization_id
# FK target and silently rolls back the ENTIRE approval transaction -- not just the
# indexing side effect, even though the code catches that exception as "non-fatal".
import prosales.infrastructure.database.models_agent  # noqa: F401
from prosales.engines.knowledge.pattern_retriever import PatternRetriever
from prosales.infrastructure.database.connection import async_session_factory
from prosales.infrastructure.llm.provider import LLMResponse
from prosales.services.learning_pipeline import LearningPipeline, MoveApprover

MARKER = "zz_e2e_marker_leasing_flexible_payment_9f3a"

FAKE_EMBEDDING = [0.01] * 1536


class FakeLLMProvider:
    """Returns one fixed, valid move extraction — deterministic, no API call."""

    async def complete_json(self, messages, temperature: float = 0.2) -> dict:
        return {
            "moves": [
                {
                    "start_turn_index": 0,
                    "end_turn_index": 1,
                    "move_kind": "objection_handling",
                    "goal": "resolve financing concern",
                    "client_state_before": "desconfiado",
                    "client_state_after": "tranquilo",
                    "polarity": "positive",
                    "outcome_label": "objecion_resuelta",
                    "confidence": 0.9,
                    "conditions": {},
                }
            ]
        }

    async def complete(self, messages, **kwargs) -> LLMResponse:  # pragma: no cover - unused here
        raise NotImplementedError


class FakeVectorStore:
    """Deterministic fake embedding — no OpenAI call needed for this test."""

    async def embed(self, text_: str) -> list[float]:
        return FAKE_EMBEDDING


TRANSCRIPT = f"""Agent: {MARKER} — I understand the monthly payment is a concern, we do offer flexible leasing options.
Client: Okay, that actually sounds reasonable, tell me more about it.
Agent: Great, with leasing your payment could be lower and you can upgrade sooner.
Client: Alright, I'm interested in that option."""


@pytest.mark.asyncio
async def test_ingest_approve_then_later_conversation_retrieves_it():
    agent_version_id = uuid4()  # no FK to agent_versions on evidence/moves tables

    # --- 1. Ingest a transcript (real DB, fake LLM for extraction) ---
    async with async_session_factory() as db:
        async with db.begin():
            pipeline = LearningPipeline(db, llm_provider=FakeLLMProvider(), vector_store=None)
            result = await pipeline.ingest_transcript(
                transcript=TRANSCRIPT,
                agent_version_id=agent_version_id,
                outcome="scheduled",
            )

    assert result["counts"]["moves"] == 1
    move = result["moves"][0]
    assert MARKER in move.transcript_excerpt
    assert move.status == "pending"  # nothing is learned/retrievable until approved

    # --- 2. Before approval: PatternRetriever must NOT surface it yet ---
    retriever = PatternRetriever(async_session_factory)
    ctx_before = await retriever.retrieve(
        agent_version_id=agent_version_id,
        move_kinds=["objection_handling"],
        limit=3,
    )
    assert not any(MARKER in p["excerpt"] for p in ctx_before.proven_plays), (
        "a pending (unapproved) move must not be retrievable — otherwise "
        "approval review is meaningless"
    )

    # --- 3. Approve it (real clustering, fake embedding) ---
    async with async_session_factory() as db:
        async with db.begin():
            approver = MoveApprover(db, vector_store=FakeVectorStore())
            cluster_id = await approver.approve(move.id)
    assert cluster_id is not None, "approval should have created a pattern cluster"

    # --- 4. A LATER, separate conversation retrieves it ---
    ctx_after = await retriever.retrieve(
        agent_version_id=agent_version_id,
        move_kinds=["objection_handling"],
        limit=3,
    )
    assert any(MARKER in p["excerpt"] for p in ctx_after.proven_plays), (
        "approving a move must make it retrievable in a subsequent conversation — "
        "this is the core claim that 'the agent learns from ingested conversations'"
    )
    assert MARKER in ctx_after.to_prompt_block(), (
        "the retrieved play must actually reach the prompt block that gets "
        "injected into the agent's context, not just sit in proven_plays"
    )

    # --- Cleanup: this agent_version_id is throwaway, but leave the DB clean ---
    async with async_session_factory() as db:
        async with db.begin():
            await db.execute(
                text("DELETE FROM pattern_clusters WHERE agent_version_id = :aid"),
                {"aid": agent_version_id},
            )
            await db.execute(
                text("DELETE FROM conversation_moves WHERE agent_version_id = :aid"),
                {"aid": agent_version_id},
            )
            await db.execute(
                text("DELETE FROM evidence_turns WHERE evidence_source_id IN "
                     "(SELECT id FROM evidence_sources WHERE agent_version_id = :aid)"),
                {"aid": agent_version_id},
            )
            await db.execute(
                text("DELETE FROM evidence_sources WHERE agent_version_id = :aid"),
                {"aid": agent_version_id},
            )
