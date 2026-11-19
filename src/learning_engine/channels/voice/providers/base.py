"""Voice provider abstraction — provider-agnostic protocol translation."""

from abc import ABC, abstractmethod

from pydantic import BaseModel


class VoiceEvent(BaseModel):
    """Internal voice event — provider-agnostic."""

    event_type: str  # "session_start" | "user_speech" | "user_silence" | "session_end"
    transcript: str | None = None
    metadata: dict = {}


class VoiceChunk(BaseModel):
    """Response chunk sent back to the voice provider."""

    content: str
    end_of_turn: bool = False
    end_session: bool = False


class VoiceProvider(ABC):
    """Abstraction for any voice provider (Retell, ElevenLabs, OpenAI, etc.)."""

    @abstractmethod
    async def parse_event(self, raw: dict) -> VoiceEvent | None:
        """Translate provider-specific message → internal VoiceEvent."""
        ...

    @abstractmethod
    async def format_response(
        self, chunk: VoiceChunk, response_id: int | None = None
    ) -> dict:
        """Translate internal VoiceChunk → provider-specific message."""
        ...

    @abstractmethod
    async def format_config(self) -> dict | None:
        """Initial config message to send on connection (or None)."""
        ...

    @abstractmethod
    async def format_keepalive(self, raw: dict) -> dict | None:
        """Handle ping/pong or keepalive (or None if not needed)."""
        ...
