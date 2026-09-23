"""Tests for AudioTranscriber — Whisper API wrapper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from prosales.services.transcription import AudioTranscriber


class TestTranscribe:
    @pytest.mark.asyncio
    async def test_transcribes_audio_bytes(self):
        with patch("prosales.services.transcription.openai.AsyncOpenAI") as MockClient:
            mock_response = MagicMock()
            mock_response.text = "Hola, ¿cómo puedo ayudarle?"

            mock_client = AsyncMock()
            mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_client

            transcriber = AudioTranscriber(api_key="test-key")
            result = await transcriber.transcribe(b"fake-audio-bytes", "recording.mp3")

            assert result == "Hola, ¿cómo puedo ayudarle?"
            mock_client.audio.transcriptions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_rejects_unsupported_format(self):
        transcriber = AudioTranscriber(api_key="test-key")

        with pytest.raises(ValueError, match="Unsupported audio format"):
            await transcriber.transcribe(b"data", "file.txt")

    @pytest.mark.asyncio
    async def test_rejects_oversized_file(self):
        transcriber = AudioTranscriber(api_key="test-key")
        huge = b"x" * (26 * 1024 * 1024)  # 26MB

        with pytest.raises(ValueError, match="25MB"):
            await transcriber.transcribe(huge, "big.mp3")
