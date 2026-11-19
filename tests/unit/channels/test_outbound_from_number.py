"""Picking the Retell 'from' number for an outbound call when the CRM only
stored the agent id (the phone lives on the agent in Retell)."""

from learning_engine.channels.voice.outbound import from_number_for_agent


def test_prefers_outbound_agent_binding():
    numbers = [
        {"phone_number": "+111", "inbound_agents": [{"agent_id": "agent_x"}]},
        {"phone_number": "+222", "outbound_agents": [{"agent_id": "agent_x"}]},
    ]
    assert from_number_for_agent(numbers, "agent_x") == "+222"


def test_falls_back_to_inbound_binding():
    numbers = [{"phone_number": "+111", "inbound_agents": [{"agent_id": "agent_x"}]}]
    assert from_number_for_agent(numbers, "agent_x") == "+111"


def test_supports_legacy_scalar_agent_id():
    numbers = [{"phone_number": "+333", "outbound_agent_id": "agent_x"}]
    assert from_number_for_agent(numbers, "agent_x") == "+333"


def test_returns_none_when_no_number_bound_to_agent():
    numbers = [{"phone_number": "+111", "outbound_agents": [{"agent_id": "agent_other"}]}]
    assert from_number_for_agent(numbers, "agent_x") is None
