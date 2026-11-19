"""create_llm_call_node's tool-use branch (state["tool_executor"]): the model
may request CRM tools, whose results are fed back until it produces final text.
Exercises the happy path, a failing tool (must not crash the turn), and the
iteration cap."""

import json

import pytest

from learning_engine.core.models.execution import PipelineExecution, Versions
from learning_engine.infrastructure.llm.provider import LLMMessage, LLMToolResponse, ToolCall
from learning_engine.pipeline.nodes import MAX_TOOL_ITERATIONS, create_llm_call_node


class ScriptedToolLLM:
    """Returns a queued sequence of LLMToolResponses, one per complete_with_tools
    call. Records the message lists it was called with so tests can assert the
    tool results were fed back."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[list[LLMMessage]] = []

    async def complete_with_tools(self, messages, tools, model=None, **kw):
        self.calls.append(list(messages))
        return self._responses.pop(0)


class FakeExecutor:
    def __init__(self, result=None, tools=None):
        self._result = result if result is not None else {"ok": True}
        self.executed: list[tuple[str, dict]] = []
        self._tools = tools or [{"name": "get_available_slots", "description": "", "parameters": {}}]

    def tool_schemas(self):
        return self._tools

    async def execute(self, name, args):
        self.executed.append((name, args))
        return self._result


def _execution():
    return PipelineExecution(versions=Versions())


@pytest.mark.asyncio
async def test_tool_loop_executes_tool_then_returns_final_text():
    llm = ScriptedToolLLM(
        [
            LLMToolResponse(
                content="",
                tool_calls=[ToolCall(id="t1", name="get_available_slots", arguments={"from": "x"})],
                model="gpt-4o",
                usage={"prompt_tokens": 10, "completion_tokens": 2},
            ),
            LLMToolResponse(content="Tengo el martes a las 3pm.", model="gpt-4o"),
        ]
    )
    executor = FakeExecutor(result={"slots": [{"starts_at": "2026-10-06T15:00:00Z"}]})
    execution = _execution()
    node = create_llm_call_node(llm)

    result = await node(
        {
            "prompt_messages": [LLMMessage(role="user", content="quiero agendar")],
            "execution": execution,
            "tool_executor": executor,
        }
    )

    assert result["llm_response"] == "Tengo el martes a las 3pm."
    assert executor.executed == [("get_available_slots", {"from": "x"})]
    # The second LLM call must have seen the tool result fed back as a tool msg.
    second_call = llm.calls[1]
    tool_msgs = [m for m in second_call if m.role == "tool"]
    assert tool_msgs and json.loads(tool_msgs[0].content)["slots"]
    # Both LLM calls recorded as traces.
    assert len(execution.llm_calls) == 2


@pytest.mark.asyncio
async def test_failing_tool_feeds_error_back_not_crash():
    class BoomExecutor(FakeExecutor):
        async def execute(self, name, args):
            return {"error": "tool 'create_appointment' failed", "detail": "calendar busy"}

    llm = ScriptedToolLLM(
        [
            LLMToolResponse(
                tool_calls=[ToolCall(id="t1", name="create_appointment", arguments={})],
                model="gpt-4o",
            ),
            LLMToolResponse(content="Ese horario no está disponible, ¿probamos otro?", model="gpt-4o"),
        ]
    )
    node = create_llm_call_node(llm)

    result = await node(
        {
            "prompt_messages": [LLMMessage(role="user", content="agenda el lunes")],
            "execution": _execution(),
            "tool_executor": BoomExecutor(),
        }
    )

    assert "no está disponible" in result["llm_response"]
    fed = [m for m in llm.calls[1] if m.role == "tool"]
    assert json.loads(fed[0].content)["error"]


@pytest.mark.asyncio
async def test_tool_loop_respects_iteration_cap():
    # Model that always asks for a tool, never settles on text.
    responses = [
        LLMToolResponse(
            content=f"thinking {i}",
            tool_calls=[ToolCall(id=f"t{i}", name="get_available_slots", arguments={})],
            model="gpt-4o",
        )
        for i in range(MAX_TOOL_ITERATIONS + 3)
    ]
    llm = ScriptedToolLLM(responses)
    node = create_llm_call_node(llm)

    result = await node(
        {
            "prompt_messages": [LLMMessage(role="user", content="hola")],
            "execution": _execution(),
            "tool_executor": FakeExecutor(),
        }
    )

    # Stops at the cap and returns the last text it had rather than looping forever.
    assert len(llm.calls) == MAX_TOOL_ITERATIONS
    assert result["llm_response"] == f"thinking {MAX_TOOL_ITERATIONS - 1}"
