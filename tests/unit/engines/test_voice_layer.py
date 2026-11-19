import pytest

from learning_engine.engines.voice.style_adapter import adapt_to_voice
from learning_engine.engines.voice.backchannel import BackchannelManager
from learning_engine.engines.voice.turn_manager import TurnManager
from learning_engine.engines.voice.pause_manager import PauseManager


def test_formal_to_natural():
    text = "Le informo que nuestro vehículo tiene garantía."
    result = adapt_to_voice(text, "es")
    # Should not contain formal phrases
    assert "Le informo que" not in result


def test_backchannel_on_objection():
    from learning_engine.core.enums import Intent
    bc = BackchannelManager()
    # With probability 1.0 on objection, should always prepend
    result = bc.maybe_prepend("esto es una prueba", "es", intent=Intent.OBJECTION, probability=1.0)
    assert result != "esto es una prueba"
    assert result[0].isupper()


def test_no_backchannel_on_greeting():
    from learning_engine.core.enums import Intent
    bc = BackchannelManager()
    # Should NEVER prepend on greeting regardless of probability
    result = bc.maybe_prepend("Hola, bienvenido", "es", intent=Intent.GREETING, probability=1.0)
    assert result == "Hola, bienvenido"


def test_turn_manager_split():
    tm = TurnManager()
    long_text = "Primera oración. Segunda oración. Tercera oración. Cuarta oración larga con más contenido. Quinta oración."
    chunks = tm.split_for_turns(long_text, max_chars=60)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 100  # reasonable length


def test_pause_manager_ssml():
    pm = PauseManager()
    ssml = pm.to_ssml("Hola, bienvenido. ¿En qué le puedo ayudar?")
    assert "<speak>" in ssml
    assert "<break" in ssml


def test_short_text_no_split():
    tm = TurnManager()
    short = "Hola"
    chunks = tm.split_for_turns(short)
    assert len(chunks) == 1
