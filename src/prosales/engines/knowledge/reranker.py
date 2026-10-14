"""LLMReranker — second-stage reranking of hybrid-retrieved chunks.

First-stage retrieval (dense + lexical, fused by RRF) is recall-oriented: it
casts a wide net cheaply. The reranker is precision-oriented: it reads the
actual query against each candidate and reorders by true relevance, then keeps
the top_k. This is the classic retrieve-then-rerank pattern.

It uses the same cheap analyzer LLM as the detectors (one JSON call scoring all
candidates at once). Any failure degrades gracefully to the pre-rerank order,
so reranking never breaks retrieval.
"""

import logging
from typing import Any

from prosales.infrastructure.llm.provider import LLMMessage, LLMProvider

logger = logging.getLogger(__name__)

_SNIPPET_CHARS = 500

RERANK_PROMPT = """Reordená estos fragmentos por relevancia para responder la consulta.
No inventes; juzgá solo qué tan útil es cada fragmento para la consulta.

Consulta: {query}

Fragmentos:
{candidates}

Respondé SOLO JSON: {{"ranking": [{{"index": <n>, "score": <0.0-1.0>}}]}}
Incluí solo los índices relevantes (score > 0), del más al menos relevante."""


def _apply_ranking(candidates: list[dict], ranking: list[Any], top_k: int) -> list[dict]:
    """Map the model's ranking onto the candidate list. Pure + defensive:
    ignores out-of-range/duplicate indices; if the model returned nothing
    usable, falls back to the original order truncated to top_k."""
    seen: set[int] = set()
    ordered: list[dict] = []
    for item in ranking:
        idx = item.get("index") if isinstance(item, dict) else item
        if not isinstance(idx, int) or idx < 0 or idx >= len(candidates) or idx in seen:
            continue
        seen.add(idx)
        ordered.append(candidates[idx])
        if len(ordered) >= top_k:
            break
    if not ordered:
        return candidates[:top_k]
    return ordered


class LLMReranker:
    def __init__(self, llm: LLMProvider, model: str = "gpt-4o-mini"):
        self.llm = llm
        self.model = model

    async def rerank(self, query: str, candidates: list[dict], top_k: int) -> list[dict]:
        if len(candidates) <= top_k:
            return candidates  # nothing to narrow down
        listed = "\n".join(
            f"[{i}] {(c.get('content') or '')[:_SNIPPET_CHARS]}" for i, c in enumerate(candidates)
        )
        try:
            result = await self.llm.complete_json(
                messages=[
                    LLMMessage(
                        role="system",
                        content="Sos un reranker de recuperación. Respondés solo JSON.",
                    ),
                    LLMMessage(
                        role="user",
                        content=RERANK_PROMPT.format(query=query, candidates=listed),
                    ),
                ],
                model=self.model,
            )
            ranking = result.get("ranking", [])
            if not isinstance(ranking, list):
                ranking = []
            # Sort by score desc when scores are present; _apply_ranking keeps the order.
            ranking = sorted(
                ranking,
                key=lambda it: it.get("score", 0.0) if isinstance(it, dict) else 0.0,
                reverse=True,
            )
            return _apply_ranking(candidates, ranking, top_k)
        except Exception:
            logger.exception("Rerank failed — keeping pre-rerank order")
            return candidates[:top_k]
