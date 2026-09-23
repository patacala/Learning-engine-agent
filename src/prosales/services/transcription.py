"""Audio transcription using OpenAI Whisper API.

Provider-neutral service (no learning/training coupling): raw audio bytes -> text.
"""

import io
import logging

import openai

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = {"mp3", "mp4", "m4a", "wav", "webm"}
MAX_SIZE_BYTES = 25 * 1024 * 1024  # 25MB Whisper API limit


class AudioTranscriber:
    def __init__(self, api_key: str | None = None):
        self.client = openai.AsyncOpenAI(api_key=api_key)

    async def transcribe(self, audio_bytes: bytes, filename: str) -> str:
        """Transcribe audio bytes to text using Whisper API."""
        if len(audio_bytes) > MAX_SIZE_BYTES:
            raise ValueError(f"Audio file exceeds 25MB limit ({len(audio_bytes)} bytes)")

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported audio format: {ext}. Supported: {SUPPORTED_FORMATS}")

        buffer = io.BytesIO(audio_bytes)
        buffer.name = filename

        try:
            response = await self.client.audio.transcriptions.create(
                model="whisper-1",
                file=buffer,
            )
            transcript = response.text
            logger.info("Transcribed %s: %d chars", filename, len(transcript))
            return transcript
        except Exception as e:
            logger.error("Whisper transcription failed: %s", e)
            raise
