"""Tests for VoiceProvider base models."""

import pytest

from learning_engine.channels.voice.providers.base import VoiceChunk, VoiceEvent


@pytest.mark.asyncio
async def test_voice_event_model():
    """VoiceEvent should hold event_type, optional transcript, and metadata."""
    event = VoiceEvent(
        event_type="user_speech",
        transcript="Hola, quiero información",
        metadata={"source": "retell"},
    )
    assert event.event_type == "user_speech"
    assert event.transcript == "Hola, quiero información"
    assert event.metadata["source"] == "retell"


@pytest.mark.asyncio
async def test_voice_chunk_model():
    """VoiceChunk should hold content and control flags."""
    chunk = VoiceChunk(content="Hola, ¿en qué puedo ayudarte?", end_of_turn=True)
    assert chunk.content == "Hola, ¿en qué puedo ayudarte?"
    assert chunk.end_of_turn is True
    assert chunk.end_session is False

    final = VoiceChunk(content="Adiós", end_of_turn=True, end_session=True)
    assert final.end_session is True
