"""Cosine similarity for embedding-based semantic dedup.

Shared by the Performance engine (pattern clustering) and the Expressions
repository (semantic dedup of winning/anti phrases) — both merge near-identical
embeddings above the same bar, so the threshold lives in one place.
"""

import math

SIMILARITY_THRESHOLD = 0.85


def to_list(vec) -> list[float] | None:
    """Normalize a pgvector column value (or plain list) to a plain list."""
    if vec is None:
        return None
    if hasattr(vec, "tolist"):
        return vec.tolist()
    return list(vec)


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
