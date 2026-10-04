"""Provider-neutral LLMMessage (incl. tool_calls / tool-result) maps correctly
to each provider's wire format. Pure static helpers — no network."""

from prosales.infrastructure.llm.anthropic import AnthropicProvider
from prosales.infrastructure.llm.openai import OpenAIProvider
from prosales.infrastructure.llm.provider import LLMMessage, ToolCall


def _convo():
    return [
        LLMMessage(role="system", content="You are helpful"),
        LLMMessage(role="user", content="agenda el martes"),
        LLMMessage(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="t1", name="get_available_slots", arguments={"from": "x"})],
        ),
        LLMMessage(role="tool", tool_call_id="t1", name="get_available_slots", content='{"slots": []}'),
    ]


def test_openai_mapping():
    msgs = [OpenAIProvider._to_openai_message(m) for m in _convo()]
    # assistant tool-call message
    assert msgs[2]["role"] == "assistant"
    assert msgs[2]["tool_calls"][0]["function"]["name"] == "get_available_slots"
    assert msgs[2]["tool_calls"][0]["function"]["arguments"] == '{"from": "x"}'
    # tool-result message
    assert msgs[3] == {"role": "tool", "tool_call_id": "t1", "content": '{"slots": []}'}


def test_anthropic_mapping():
    system, conv = AnthropicProvider._split_messages(_convo())
    assert system == "You are helpful"
    # assistant tool_use block
    assistant = conv[1]
    assert assistant["role"] == "assistant"
    assert assistant["content"][0]["type"] == "tool_use"
    assert assistant["content"][0]["name"] == "get_available_slots"
    assert assistant["content"][0]["input"] == {"from": "x"}
    # tool_result mapped onto a user turn
    tool_turn = conv[2]
    assert tool_turn["role"] == "user"
    assert tool_turn["content"][0]["type"] == "tool_result"
    assert tool_turn["content"][0]["tool_use_id"] == "t1"
