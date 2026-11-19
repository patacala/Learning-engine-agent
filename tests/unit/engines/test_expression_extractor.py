"""Tests for ExpressionExtractor — verbatim winning/anti phrases."""

import pytest

from learning_engine.engines.evidence.models import EvidenceSource
from learning_engine.engines.evidence.parser import TranscriptParser
from learning_engine.engines.expressions.extractor import ExpressionExtractor


class _MockLLM:
    def __init__(self, payload):
        self.payload = payload

    async def complete(self, *a, **k): ...

    async def complete_json(self, messages, temperature=0.3):
        return self.payload


TRANSCRIPT = (
    "Cliente: El precio me preocupa.\n"
    "Agente: Tiene todo el sentido que hagas esa pregunta. Vamos a verlo con calma.\n"
    "Cliente: Ok.\n"
    "Agente: Créame, es el mejor precio."
)


def _source():
    return EvidenceSource(turns=TranscriptParser().parse(TRANSCRIPT))


@pytest.mark.asyncio
async def test_extracts_verbatim_substring():
    llm = _MockLLM({"expressions": [
        {"turn_index": 1, "polarity": "winning", "goal": "validar",
         "stage": "objecion", "quote": "Tiene todo el sentido que hagas esa pregunta"},
    ]})
    exprs = await ExpressionExtractor(llm).extract(_source())
    assert len(exprs) == 1
    assert exprs[0].exact_phrase == "Tiene todo el sentido que hagas esa pregunta"
    assert exprs[0].polarity == "winning"


@pytest.mark.asyncio
async def test_anti_expression_detected():
    llm = _MockLLM({"expressions": [
        {"turn_index": 3, "polarity": "anti", "goal": "cerrar", "stage": "cierre",
         "quote": "Créame"},
    ]})
    exprs = await ExpressionExtractor(llm).extract(_source())
    assert exprs[0].polarity == "anti"
    assert "Créame" in exprs[0].exact_phrase


@pytest.mark.asyncio
async def test_quote_not_in_turn_falls_back_to_full_turn():
    llm = _MockLLM({"expressions": [
        {"turn_index": 1, "polarity": "winning", "quote": "frase que el LLM inventó"},
    ]})
    exprs = await ExpressionExtractor(llm).extract(_source())
    # Falls back to the real turn text, never the fabricated quote.
    assert exprs[0].exact_phrase.startswith("Tiene todo el sentido")


@pytest.mark.asyncio
async def test_client_turn_index_is_ignored():
    llm = _MockLLM({"expressions": [
        {"turn_index": 0, "polarity": "winning", "quote": "El precio me preocupa"},
    ]})
    exprs = await ExpressionExtractor(llm).extract(_source())
    assert exprs == []
