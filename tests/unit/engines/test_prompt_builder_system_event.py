"""System events (e.g. a confirmed payment) must be rendered as a prominent,
first instruction telling the agent this is a confirmed fact — not something
the customer said — so it acknowledges it and continues."""

import pytest

from learning_engine.engines.response.prompt_builder import PromptBuilder


def test_system_event_dict_renders_instruction_and_message():
    extra = {"system_event": {"type": "payment.received", "message": "Deposit of $500 confirmed."}}
    out = PromptBuilder()._format_external_context(extra)

    assert "SYSTEM EVENT" in out
    assert "the customer did NOT say this" in out
    assert "Deposit of $500 confirmed." in out


def test_system_event_renders_first_before_external_context():
    extra = {
        "system_event": {"type": "payment.received", "message": "Deposit confirmed."},
        "contact": {"first_name": "Ana", "last_name": "Lopez"},
    }
    out = PromptBuilder()._format_external_context(extra)

    assert out.index("SYSTEM EVENT") < out.index("EXTERNAL CONTEXT")
    assert "Deposit confirmed." in out
    assert "Ana Lopez" in out


def test_system_event_tolerates_bare_string():
    out = PromptBuilder()._format_external_context({"system_event": "Payment expired."})
    assert "SYSTEM EVENT" in out
    assert "Payment expired." in out


def test_system_event_empty_message_is_skipped():
    out = PromptBuilder()._format_external_context({"system_event": {"type": "payment.received"}})
    assert out == ""


@pytest.mark.asyncio
async def test_system_event_present_in_built_prompt():
    state = {
        "current_message": "Payment received: $500 deposit.",
        "extra_context": {
            "system_event": {"type": "payment.received", "message": "Deposit of $500 confirmed."}
        },
    }
    result = await PromptBuilder().process(state)
    combined = "\n".join(m.content for m in result["prompt_messages"])

    assert "SYSTEM EVENT" in combined
    assert "Deposit of $500 confirmed." in combined
