"""Tests for MoveExtractor — LLM anchors, code extracts verbatim."""

import pytest

from learning_engine.engines.evidence.models import EvidenceSource
from learning_engine.engines.evidence.parser import TranscriptParser
from learning_engine.engines.moves.extractor import MoveExtractor


class _MockLLM:
    def __init__(self, payload):
        self.payload = payload

    async def complete(self, *a, **k): ...

    async def complete_json(self, messages, temperature=0.3):
        return self.payload


TRANSCRIPT = (
    "Cliente: Hola.\n"
    "Agente: Excelente elección. La prueba de manejo es la mejor forma de conocer el auto.\n"
    "Cliente: El precio me preocupa.\n"
    "Agente: Lo entiendo. Muchos clientes empezaron con esa misma duda.\n"
    "Cliente: Gracias, lo pensaré."
)


def _source():
    return EvidenceSource(turns=TranscriptParser().parse(TRANSCRIPT))


@pytest.mark.asyncio
async def test_excerpt_is_verbatim_from_anchored_turns():
    llm = _MockLLM({"moves": [{
        "start_turn_index": 1, "end_turn_index": 2, "move_kind": "objection_handling",
        "goal": "resolver precio", "client_state_before": "desconfiado",
        "client_state_after": "tranquilo", "polarity": "positive",
        "outcome_label": "objecion_resuelta", "confidence": 0.9,
    }]})
    moves = await MoveExtractor(llm).extract(_source())
    assert len(moves) == 1
    # The stored excerpt is the real turn text, not anything the LLM wrote.
    assert "Excelente elección" in moves[0].transcript_excerpt
    assert "El precio me preocupa" in moves[0].transcript_excerpt


@pytest.mark.asyncio
async def test_polarity_guardrail_flips_on_negative_after_state():
    # LLM claims positive, but the client ends up "perdio_confianza".
    llm = _MockLLM({"moves": [{
        "start_turn_index": 3, "end_turn_index": 4, "move_kind": "closing",
        "goal": "cerrar", "client_state_before": "comparando",
        "client_state_after": "perdio_confianza", "polarity": "positive",
        "outcome_label": "abandono", "confidence": 0.6,
    }]})
    moves = await MoveExtractor(llm).extract(_source())
    assert moves[0].polarity == "negative"


@pytest.mark.asyncio
async def test_out_of_range_indices_are_clamped():
    llm = _MockLLM({"moves": [{
        "start_turn_index": 99, "end_turn_index": 200, "move_kind": "discovery",
        "client_state_after": "mas_interesado",
    }]})
    moves = await MoveExtractor(llm).extract(_source())
    assert moves and moves[0].end_turn_index <= 4


@pytest.mark.asyncio
async def test_empty_source_returns_empty():
    moves = await MoveExtractor(_MockLLM({"moves": []})).extract(EvidenceSource(turns=[]))
    assert moves == []
