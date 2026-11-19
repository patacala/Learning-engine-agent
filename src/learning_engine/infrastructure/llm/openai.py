import json
from collections.abc import AsyncIterator

from learning_engine.config import settings
from learning_engine.core.exceptions import LLMError
from learning_engine.infrastructure.llm.clients import get_openai_client
from learning_engine.infrastructure.llm.provider import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    LLMToolResponse,
    ToolCall,
)


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, service_tier: str | None = None):
        self.client = get_openai_client(api_key)  # shared, retry/timeout configured
        self.default_model = settings.primary_llm_model
        # OpenAI Fast mode ("priority") — set at construction (di/container.py
        # keys it per role: primary vs analyzer), not per-call, so call sites
        # (pipeline/nodes.py, detectors) never need to know about it.
        self.service_tier = service_tier

    def _tier_kwargs(self) -> dict:
        return {"service_tier": self.service_tier} if self.service_tier else {}

    async def complete(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        try:
            response = await self.client.chat.completions.create(
                model=model or self.default_model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                max_tokens=max_tokens,
                **self._tier_kwargs(),
            )
            return LLMResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                },
            )
        except Exception as e:
            raise LLMError(f"OpenAI error: {e}") from e

    async def stream(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        usage_sink: dict | None = None,
    ) -> AsyncIterator[str]:
        try:
            response = await self.client.chat.completions.create(
                model=model or self.default_model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True},  # usage rides the final chunk
                **self._tier_kwargs(),
            )
            async for chunk in response:
                if chunk.usage is not None and usage_sink is not None:
                    usage_sink["model"] = chunk.model
                    usage_sink["usage"] = {
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                    }
                if not chunk.choices:
                    continue  # the usage-only final chunk has no choices
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            raise LLMError(f"OpenAI stream error: {e}") from e

    @staticmethod
    def _to_openai_message(m: LLMMessage) -> dict:
        """Map a provider-neutral LLMMessage to OpenAI's chat-completions wire
        format, including assistant tool_calls and tool-result messages."""
        if m.role == "assistant" and m.tool_calls:
            return {
                "role": "assistant",
                "content": m.content or None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in m.tool_calls
                ],
            }
        if m.role == "tool":
            return {"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content}
        return {"role": m.role, "content": m.content}

    async def complete_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMToolResponse:
        try:
            response = await self.client.chat.completions.create(
                model=model or self.default_model,
                messages=[self._to_openai_message(m) for m in messages],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": t["name"],
                            "description": t.get("description", ""),
                            "parameters": t.get("parameters", {"type": "object", "properties": {}}),
                        },
                    }
                    for t in tools
                ],
                tool_choice="auto",
                temperature=temperature,
                max_tokens=max_tokens,
                **self._tier_kwargs(),
            )
            msg = response.choices[0].message
            tool_calls = []
            for tc in msg.tool_calls or []:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
            return LLMToolResponse(
                content=msg.content or "",
                tool_calls=tool_calls,
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                },
            )
        except Exception as e:
            raise LLMError(f"OpenAI tool-call error: {e}") from e

    async def complete_json(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.3,
    ) -> dict:
        try:
            response = await self.client.chat.completions.create(
                model=model or self.default_model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                response_format={"type": "json_object"},
                **self._tier_kwargs(),
            )
            return json.loads(response.choices[0].message.content or "{}")
        except Exception as e:
            raise LLMError(f"OpenAI JSON error: {e}") from e
