"""History-awareness of the system/context prompt.

Regression guard for a real prod bug: on a brand-new contact (no prior
messages) the agent fabricated a previous conversation ("la última vez
discutimos..."). Root cause was an unconditional instruction telling the LLM
not to restart "as if meeting for the first time", which fired even on the
genuine first contact. The continuity hint must now be gated on whether real
conversation history exists, and first contact must get an explicit guard
against inventing a shared past.
"""

from types import SimpleNamespace

import pytest

from prosales.engines.response.prompt_builder import PromptBuilder


def _msg(role, content):
    return SimpleNamespace(role=role, content=content)


def _context(recent_messages):
    return SimpleNamespace(
        critical_facts=[],
        conversation_summary="",
        recent_messages=recent_messages,
    )


def _joined(result) -> str:
    return "\n".join(m.content for m in result["prompt_messages"]).lower()


@pytest.mark.asyncio
async def test_first_contact_has_no_continuity_and_guards_against_invented_history():
    state = {"current_message": "hola", "context": _context([])}
    text = _joined(await PromptBuilder().process(state))

    # The old unconditional instruction must be gone.
    assert "don't restart as if meeting for the first time" not in text
    # First contact must be told NOT to invent a shared past.
    assert "first message from this person" in text
    assert "do not reference" in text
    # And it must NOT be told it is continuing an existing conversation.
    assert "continuing an existing conversation" not in text


@pytest.mark.asyncio
async def test_existing_conversation_gets_continuity_instruction():
    state = {
        "current_message": "y el precio?",
        "context": _context([_msg("user", "hola"), _msg("assistant", "hola, en que te ayudo?")]),
    }
    text = _joined(await PromptBuilder().process(state))

    assert "continuing an existing conversation" in text
    assert "first message from this person" not in text
