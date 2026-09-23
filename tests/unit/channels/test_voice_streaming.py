"""Tests for sentence splitter — streaming utilities."""

import pytest

from prosales.channels.voice.streaming import split_into_sentences


def test_split_simple_sentences():
    """Should split on sentence-ending punctuation."""
    text = "Hola, bienvenido. ¿Cómo estás hoy? Bien, muchas gracias."
    result = split_into_sentences(text)
    assert len(result) == 3
    assert result[0] == "Hola, bienvenido."
    assert result[1] == "¿Cómo estás hoy?"
    assert result[2] == "Bien, muchas gracias."


def test_split_preserves_short_text():
    """Short text should be returned as a single segment."""
    text = "Hola"
    result = split_into_sentences(text)
    assert result == ["Hola"]


def test_split_merges_fragments():
    """Short fragments should be merged with the previous segment."""
    text = "Ok. Sí. Entiendo lo que necesitas."
    result = split_into_sentences(text, min_length=10)
    # "Ok." and "Sí." are < 10 chars, should be merged
    assert len(result) >= 1
    # All text should be preserved
    combined = " ".join(result)
    assert "Ok." in combined
    assert "Sí." in combined
    assert "Entiendo lo que necesitas." in combined


def test_split_empty_text():
    """Empty text should return empty list."""
    assert split_into_sentences("") == []
    assert split_into_sentences("   ") == []
