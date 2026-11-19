"""_format_actions_hint: the opt-out instruction must reach the model whenever
the Action Layer is on, regardless of the org's appointment capability — only
the appointment/payment guidance is capability-gated."""

from learning_engine.engines.response.prompt_builder import PromptBuilder


class FakeAgentContext:
    def __init__(self, capabilities):
        self._capabilities = set(capabilities)

    def has_capability(self, cap):
        return cap in self._capabilities


def test_no_hint_without_tool_executor():
    builder = PromptBuilder()
    assert builder._format_actions_hint({}) == ""


def test_opt_out_hint_shown_without_appointment_capability():
    builder = PromptBuilder()
    state = {
        "tool_executor": object(),
        "agent_context": FakeAgentContext([]),
    }
    hint = builder._format_actions_hint(state)
    assert "opt_out_contact" in hint
    assert "payment link" not in hint


def test_appointment_hint_added_with_capability():
    builder = PromptBuilder()
    state = {
        "tool_executor": object(),
        "agent_context": FakeAgentContext(["appointment"]),
    }
    hint = builder._format_actions_hint(state)
    assert "opt_out_contact" in hint
    assert "payment link" in hint
