"""Hybrid retrieval fusion (RRF) and LLM reranking — the pure, deterministic
parts that need neither a database nor an LLM."""

import pytest

from learning_engine.engines.knowledge.reranker import LLMReranker, _apply_ranking
from learning_engine.infrastructure.vector_store.pgvector import _rrf_fuse


def test_rrf_rewards_agreement_between_retrievers():
    # "a" is top of both the dense and lexical rankings → must win; a doc ranked
    # by only one retriever scores lower.
    scores = _rrf_fuse([["a", "b", "c"], ["a", "d", "e"]])
    ranked = sorted(scores, key=lambda i: scores[i], reverse=True)
    assert ranked[0] == "a"
    assert scores["a"] > scores["b"]
    assert scores["b"] == pytest.approx(scores["d"])  # both single rank-1 hits


def test_apply_ranking_orders_filters_and_caps():
    cands = [{"id": 0}, {"id": 1}, {"id": 2}]
    out = _apply_ranking(
        cands, [{"index": 2}, {"index": 0}, {"index": 99}, {"index": 2}], top_k=2
    )
    assert out == [cands[2], cands[0]]  # out-of-range + duplicate ignored, capped at top_k


def test_apply_ranking_falls_back_to_original_order_when_empty():
    cands = [{"id": 0}, {"id": 1}, {"id": 2}]
    assert _apply_ranking(cands, [], top_k=2) == cands[:2]


@pytest.mark.asyncio
async def test_rerank_is_noop_when_within_k():
    # Fewer candidates than requested → nothing to narrow, no LLM call.
    reranker = LLMReranker(llm=object())  # llm never touched
    cands = [{"content": "x"}, {"content": "y"}]
    assert await reranker.rerank("q", cands, top_k=5) == cands
