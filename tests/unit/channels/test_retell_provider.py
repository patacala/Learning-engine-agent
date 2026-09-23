"""Tests for RetellProvider — Retell WebSocket protocol translation."""

import pytest

from prosales.channels.voice.providers.base import VoiceChunk
from prosales.channels.voice.providers.retell import RetellProvider


@pytest.fixture
def provider():
    return RetellProvider()


@pytest.mark.asyncio
async def test_parse_response_required_extracts_transcript(provider):
    """response_required should extract last user message from transcript."""
    raw = {
        "interaction_type": "response_required",
        "response_id": 1,
        "transcript": [
            {"role": "agent", "content": "Hola"},
            {"role": "user", "content": "Quiero comprar"},
            {"role": "agent", "content": "Claro"},
            {"role": "user", "content": "¿Cuánto cuesta?"},
        ],
    }
    event = await provider.parse_event(raw)
    assert event is not None
    assert event.event_type == "user_speech"
    assert event.transcript == "¿Cuánto cuesta?"


@pytest.mark.asyncio
async def test_parse_call_details_returns_session_start(provider):
    """call_details should produce a session_start event with metadata."""
    raw = {
        "interaction_type": "call_details",
        "call": {
            "call_id": "abc-123",
            "metadata": {"api_key": "sk-test"},
            "from_number": "+1234567890",
        },
    }
    event = await provider.parse_event(raw)
    assert event is not None
    assert event.event_type == "session_start"
    assert event.metadata["call_id"] == "abc-123"
    assert event.metadata["metadata"]["api_key"] == "sk-test"


@pytest.mark.asyncio
async def test_parse_reminder_returns_silence(provider):
    """reminder_required should produce a user_silence event."""
    raw = {"interaction_type": "reminder_required"}
    event = await provider.parse_event(raw)
    assert event is not None
    assert event.event_type == "user_silence"


@pytest.mark.asyncio
async def test_format_response_retell_schema(provider):
    """format_response should produce Retell-compatible response dict."""
    chunk = VoiceChunk(content="Hola, ¿cómo estás?", end_of_turn=False)
    msg = await provider.format_response(chunk, response_id=5)
    assert msg == {
        "response_type": "response",
        "response_id": 5,
        "content": "Hola, ¿cómo estás?",
        "content_complete": False,
        "end_call": False,
    }

    final = VoiceChunk(content="Adiós", end_of_turn=True, end_session=True)
    msg2 = await provider.format_response(final, response_id=6)
    assert msg2["content_complete"] is True
    assert msg2["end_call"] is True
