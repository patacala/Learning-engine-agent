import json

from prosales.core.exceptions import LLMError
from prosales.infrastructure.llm.clients import get_anthropic_client
from prosales.infrastructure.llm.provider import LLMMessage, LLMProvider, LLMResponse


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
