"""Tests for DNAProfiler (deterministic metrics, llm=None)."""

import pytest

from learning_engine.engines.dna.models import DNA_FEATURES
from learning_engine.engines.dna.profiler import DNAProfiler
from learning_engine.engines.evidence.models import EvidenceSource
from learning_engine.engines.evidence.parser import TranscriptParser

TRANSCRIPT = (
    "Cliente: Hola, me interesa el auto.\n"
    "Agente: Genial, ¿qué buscas exactamente?\n"
    "Cliente: Algo seguro, pero el precio me preocupa.\n"
    "Agente: Entiendo, veámoslo con calma."
)


def _source():
    return EvidenceSource(turns=TranscriptParser().parse(TRANSCRIPT), conversation_id=None)


@pytest.mark.asyncio
async def test_objective_metrics_are_deterministic():
    dna = await DNAProfiler(llm_provider=None).profile(_source())
    assert dna.question_count == 1  # one '?' in agent turns
    assert dna.objection_count == 1  # "el precio me preocupa"
    assert 0.0 < dna.talk_ratio < 1.0


@pytest.mark.asyncio
async def test_subjective_defaults_to_neutral_without_llm():
    dna = await DNAProfiler(llm_provider=None).profile(_source())
    assert dna.trust_score == 0.5
    assert dna.empathy_score == 0.5


@pytest.mark.asyncio
async def test_dna_vector_matches_feature_dim():
    dna = await DNAProfiler(llm_provider=None).profile(_source())
    vec = dna.to_vector()
    assert len(vec) == len(DNA_FEATURES) == 12
    assert all(0.0 <= v <= 1.0 for v in vec)


@pytest.mark.asyncio
async def test_empty_source_returns_zeroed_dna():
    dna = await DNAProfiler(llm_provider=None).profile(EvidenceSource(turns=[]))
    assert dna.question_count == 0
    assert dna.talk_ratio == 0.0
