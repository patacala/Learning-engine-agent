from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from pydantic import BaseModel


class LLMMessage(BaseModel):
    role: str
    content: str


class LLMResponse(BaseModel):
    content: str
    model: str
    usage: dict = {}


class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        ...

    @abstractmethod
    async def complete_json(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.3,
    ) -> dict:
        ...

    @abstractmethod
    def stream(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        usage_sink: dict | None = None,
    ) -> AsyncIterator[str]:
        """Yield response text incrementally as the model generates it.

        Same call shape as ``complete``. Usage/model metadata is only known
        once the stream finishes (it arrives in/after the last chunk), so it
        can't ride the return type (an async generator can't also return a
        value the caller can read before exhausting it) — pass a plain dict
        as ``usage_sink`` and read ``usage_sink["usage"]`` /
        ``usage_sink["model"]`` after the iteration completes.
        """
        ...
