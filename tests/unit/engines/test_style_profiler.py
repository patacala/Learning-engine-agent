"""Tests for StyleProfiler (deterministic path, llm=None)."""

import pytest

from prosales.engines.evidence.models import EvidenceSource
from prosales.engines.evidence.parser import TranscriptParser
from prosales.engines.identity_learning.profiler import StyleProfiler

TRANSCRIPT = (
    "Cliente: Hola.\n"
    "Agente: Excelente. ¿Qué es lo que más te importa?\n"
    "Cliente: Seguridad.\n"
    "Agente: Perfecto, tiene sentido. ¿Manejas en carretera?\n"
    "Cliente: Sí.\n"
    "Agente: Claro. Excelente elección. ¿Agendamos una prueba?"
)


def _source():
    return EvidenceSource(turns=TranscriptParser().parse(TRANSCRIPT))


@pytest.mark.asyncio
async def test_detects_microexpressions_by_frequency():
    profile = await StyleProfiler(llm_provider=None).profile([_source()])
    phrases = [m["phrase"] for m in profile.microexpressions]
    assert "Excelente" in phrases  # appears in 2/3 agent turns


@pytest.mark.asyncio
async def test_question_ratio_and_prompt_block():
    profile = await StyleProfiler(llm_provider=None).profile([_source()])
    assert profile.question_ratio >= 0.9  # every agent turn has a question
    block = profile.to_prompt_block()
    assert "ESTILO APRENDIDO" in block
    assert "expresiones características" in block


@pytest.mark.asyncio
async def test_empty_returns_neutral_profile():
    profile = await StyleProfiler(llm_provider=None).profile([])
    assert profile.microexpressions == []
    assert profile.to_prompt_block() == ""
