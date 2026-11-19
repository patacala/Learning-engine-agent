import json
from collections.abc import AsyncIterator

from learning_engine.core.exceptions import LLMError
from learning_engine.infrastructure.llm.clients import get_anthropic_client
from learning_engine.infrastructure.llm.provider import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    LLMToolResponse,
    ToolCall,
)


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str | None = None):
        self.client = get_anthropic_client(api_key)  # shared, retry/timeout configured
        self.default_model = "claude-sonnet-4-20250514"

    async def complete(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        try:
            # Separate system message from conversation
            system_msg = ""
            conv_messages = []
            for m in messages:
                if m.role == "system":
                    system_msg = m.content
                else:
                    conv_messages.append({"role": m.role, "content": m.content})

            kwargs = {
                "model": model or self.default_model,
                "messages": conv_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if system_msg:
                kwargs["system"] = system_msg

            response = await self.client.messages.create(**kwargs)
            return LLMResponse(
                content=response.content[0].text,
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                },
            )
        except Exception as e:
            raise LLMError(f"Anthropic error: {e}") from e

    async def stream(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        usage_sink: dict | None = None,
    ) -> AsyncIterator[str]:
        try:
            system_msg = ""
            conv_messages = []
            for m in messages:
                if m.role == "system":
                    system_msg = m.content
                else:
                    conv_messages.append({"role": m.role, "content": m.content})

            kwargs = {
                "model": model or self.default_model,
                "messages": conv_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if system_msg:
                kwargs["system"] = system_msg

            async with self.client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
                final = await stream.get_final_message()
                if usage_sink is not None:
                    usage_sink["model"] = final.model
                    usage_sink["usage"] = {
                        "prompt_tokens": final.usage.input_tokens,
                        "completion_tokens": final.usage.output_tokens,
                    }
        except Exception as e:
            raise LLMError(f"Anthropic stream error: {e}") from e

    @staticmethod
    def _split_messages(messages: list[LLMMessage]) -> tuple[str, list[dict]]:
        """Split out the system prompt and map the rest to Anthropic content
        blocks, translating assistant tool_calls (tool_use) and tool-result
        messages (tool_result)."""
        system_msg = ""
        conv: list[dict] = []
        for m in messages:
            if m.role == "system":
                system_msg = m.content
            elif m.role == "assistant" and m.tool_calls:
                blocks: list[dict] = []
                if m.content:
                    blocks.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    blocks.append(
                        {"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments}
                    )
                conv.append({"role": "assistant", "content": blocks})
            elif m.role == "tool":
                conv.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m.tool_call_id,
                                "content": m.content,
                            }
                        ],
                    }
                )
            else:
                conv.append({"role": m.role, "content": m.content})
        return system_msg, conv

    async def complete_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMToolResponse:
        try:
            system_msg, conv_messages = self._split_messages(messages)
            kwargs = {
                "model": model or self.default_model,
                "messages": conv_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "tools": [
                    {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
                    }
                    for t in tools
                ],
            }
            if system_msg:
                kwargs["system"] = system_msg

            response = await self.client.messages.create(**kwargs)
            content = ""
            tool_calls = []
            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "tool_use":
                    tool_calls.append(
                        ToolCall(id=block.id, name=block.name, arguments=dict(block.input or {}))
                    )
            return LLMToolResponse(
                content=content,
                tool_calls=tool_calls,
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                },
            )
        except Exception as e:
            raise LLMError(f"Anthropic tool-call error: {e}") from e

    async def complete_json(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.3,
    ) -> dict:
        # Append JSON instruction to system message
        json_messages = []
        found_system = False
        for m in messages:
            if m.role == "system":
                found_system = True
                json_messages.append(
                    LLMMessage(
                        role="system",
                        content=m.content + "\n\nRespond ONLY with valid JSON, no other text.",
                    )
                )
            else:
                json_messages.append(m)
        if not found_system:
            json_messages.insert(
                0,
                LLMMessage(role="system", content="Respond ONLY with valid JSON, no other text."),
            )

        response = await self.complete(json_messages, model=model, temperature=temperature)
        try:
            return json.loads(response.content)
        except json.JSONDecodeError as e:
            raise LLMError(f"Anthropic returned invalid JSON: {response.content}") from e
