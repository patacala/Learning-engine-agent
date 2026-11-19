"""Tests for TranscriptParser and EvidenceSource."""

from learning_engine.engines.evidence.models import EvidenceSource
from learning_engine.engines.evidence.parser import TranscriptParser


def test_parses_speaker_labels_and_indexes():
    t = "Cliente: Hola\nAgente: Buenas, ¿en qué te ayudo?"
    turns = TranscriptParser().parse(t)
    assert [x.speaker for x in turns] == ["client", "agent"]
    assert [x.turn_index for x in turns] == [0, 1]


def test_merges_multiline_content_into_current_turn():
    t = "Agente: Primera línea.\nSegunda línea.\nCliente: Ok"
    turns = TranscriptParser().parse(t)
    assert turns[0].text == "Primera línea. Segunda línea."
    assert turns[1].text == "Ok"


def test_alternate_labels_normalize():
    t = "Vendedor: Hola\nComprador: Info por favor"
    turns = TranscriptParser().parse(t)
    assert turns[0].speaker == "agent"
    assert turns[1].speaker == "client"


def test_empty_transcript_returns_no_turns():
    assert TranscriptParser().parse("") == []


def test_parses_markdown_turno_headers():
    t = (
        "### Turno 1 — Asesor\r\n\r\n"
        "Hola, bienvenido a Audi.\r\n\r\n"
        "### Turno 2 — Cliente\r\n\r\n"
        "Estoy interesado en una Q5.\r\n\r\n"
        "### Turno 3 — Asesor\r\n\r\n"
        "¿Qué te llamó la atención?"
    )
    turns = TranscriptParser().parse(t)
    assert [x.speaker for x in turns] == ["agent", "client", "agent"]
    assert turns[0].text == "Hola, bienvenido a Audi."
    assert turns[1].text == "Estoy interesado en una Q5."
    assert turns[2].text == "¿Qué te llamó la atención?"


def test_excerpt_is_verbatim_and_labelled():
    turns = TranscriptParser().parse("Cliente: A\nAgente: B\nCliente: C")
    src = EvidenceSource(turns=turns)
    excerpt = src.excerpt(1, 2)
    assert excerpt == "Agente: B\nCliente: C"


def test_turn_at_and_agent_turns():
    turns = TranscriptParser().parse("Cliente: A\nAgente: B")
    src = EvidenceSource(turns=turns)
    assert src.turn_at(1).text == "B"
    assert len(src.agent_turns()) == 1
