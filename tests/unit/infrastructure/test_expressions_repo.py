"""Tests for the pure semantic-match decision behind expressions dedup.

SQLExpressionsRepository.upsert falls back to a semantic match (cosine on
embeddings) when the exact normalized_phrase lookup misses. The DB query
itself has no dedicated unit test (no repository in this codebase is unit
tested against a live/fake session — see engines/performance's FakePerfRepo
pattern for the equivalent at the engine layer instead); the interesting,
DB-free decision logic (best_semantic_match) is what's covered here.
"""

from uuid import uuid4

from learning_engine.infrastructure.database.repositories.expressions import best_semantic_match


def test_merges_semantically_similar_phrase():
    existing_id = uuid4()
    candidates = [(existing_id, [1.0, 0.0, 0.0])]
    # A near-identical embedding (paraphrase) should match.
    match = best_semantic_match([0.99, 0.1, 0.0], candidates)
    assert match == existing_id


def test_does_not_match_dissimilar_phrase():
    candidates = [(uuid4(), [1.0, 0.0, 0.0])]
    match = best_semantic_match([0.0, 1.0, 0.0], candidates)
    assert match is None


def test_picks_the_closest_of_multiple_candidates():
    close_id, far_id = uuid4(), uuid4()
    candidates = [(far_id, [0.9, 0.1, 0.0]), (close_id, [1.0, 0.0, 0.0])]
    match = best_semantic_match([0.995, 0.05, 0.0], candidates)
    assert match == close_id


def test_no_candidates_returns_none():
    assert best_semantic_match([1.0, 0.0, 0.0], []) is None


def test_candidate_without_embedding_is_skipped():
    candidates = [(uuid4(), None)]
    assert best_semantic_match([1.0, 0.0, 0.0], candidates) is None
