from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """A tool the model asked to run. ``arguments`` is the already-parsed JSON
    the model supplied (provider-neutral; each provider maps its own wire
    format to this)."""

    id: str
    name: str
    arguments: dict = Field(default_factory=dict)


class LLMMessage(BaseModel):
    role: str  # system | user | assistant | tool
    content: str = ""
    # Set on an assistant message that requested tools (role == "assistant").
    tool_calls: list[ToolCall] | None = None
    # Set on a tool-result message (role == "tool"): which call it answers.
    tool_call_id: str | None = None
    name: str | None = None  # tool name on a tool-result message


class LLMResponse(BaseModel):
    content: str
    model: str
    usage: dict = {}


class LLMToolResponse(BaseModel):
    """Result of a tools-enabled completion: either final text (``tool_calls``
    empty) or one+ tool requests to execute and feed back."""

    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    model: str = ""
    usage: dict = Field(default_factory=dict)


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

    async def complete_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMToolResponse:
        """One tools-enabled turn. ``tools`` are provider-neutral definitions
        ``{"name", "description", "parameters": <JSON schema>}``. Returns either
        final text or the tool calls the model wants run (see the tool loop in
        pipeline/nodes.py's llm_call). Not abstract: providers that don't
        support tools simply don't override it.
        """
        raise NotImplementedError("This LLM provider does not support tool calling")
