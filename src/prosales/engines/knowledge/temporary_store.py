"""In-memory vector store for the Test Playground.

Holds a scenario's business-context documents for the lifetime of a single
request. Nothing here is persisted: it exists only to let a saved scenario
participate in the same RAG retrieval as permanent knowledge, without writing
to the database.
"""

import math


class TemporaryVectorStore:
    """Ephemeral cosine-similarity store built per test request."""

    def __init__(self) -> None:
        self._docs: list[dict] = []
        self._embeddings: list[list[float]] = []

    def add_document(
        self,
        doc_id: str,
        title: str,
        content: str,
        category: str,
        embedding: list[float],
    ) -> None:
        self._docs.append(
            {
                "id": doc_id,
                "title": title,
                "content": content,
                "category": category,
            }
        )
        self._embeddings.append(embedding)

    @property
    def is_empty(self) -> bool:
        return not self._docs

    def search_by_embedding(
        self, query_embedding: list[float], top_k: int = 5
    ) -> list[dict]:
        """Return top_k documents ranked by cosine distance (lower = closer).

        Distance mirrors pgvector's ``<=>`` operator (cosine distance) so
        results can be merged with the permanent store on the same scale.
        """
        if not self._docs:
            return []

        query_norm = _norm(query_embedding)
        scored: list[dict] = []
        for doc, emb in zip(self._docs, self._embeddings):
            distance = _cosine_distance(query_embedding, emb, query_norm)
            scored.append({**doc, "distance": distance})

        scored.sort(key=lambda d: d["distance"])
        return scored[:top_k]


def _norm(vec: list[float]) -> float:
    return math.sqrt(sum(v * v for v in vec)) or 1e-12


def _cosine_distance(a: list[float], b: list[float], a_norm: float | None = None) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    denom = (a_norm or _norm(a)) * _norm(b)
    if denom == 0:
        return 1.0
    return 1.0 - (dot / denom)
