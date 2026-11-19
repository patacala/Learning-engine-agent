"""Tests for AgentContext domain model."""

import uuid

import pytest

from learning_engine.core.models.agent import AgentContext


@pytest.fixture
def agent_context():
    return AgentContext(
        organization_id=uuid.uuid4(),
        organization_name="AutoMax",
        org_capabilities=["knowledge", "inventory"],
        agent_id=uuid.uuid4(),
        agent_version_id=uuid.uuid4(),
        agent_name="Sales Bot",
        agent_type="sales",
        agent_capabilities=["voice", "negotiation"],
    )


def test_has_capability_org(agent_context):
    assert agent_context.has_capability("knowledge") is True
    assert agent_context.has_capability("inventory") is True


def test_has_capability_agent(agent_context):
    assert agent_context.has_capability("voice") is True
    assert agent_context.has_capability("negotiation") is True


def test_has_capability_missing(agent_context):
    assert agent_context.has_capability("crm") is False


def test_has_org_capability(agent_context):
    assert agent_context.has_org_capability("knowledge") is True
    assert agent_context.has_org_capability("voice") is False


def test_has_agent_capability(agent_context):
    assert agent_context.has_agent_capability("voice") is True
    assert agent_context.has_agent_capability("negotiation") is True
    assert agent_context.has_agent_capability("knowledge") is False


def test_capability_split_semantics():
    """Knowledge belongs to org, voice/negotiation to agent."""
    ctx = AgentContext(
        organization_id=uuid.uuid4(),
        organization_name="Test Org",
        org_capabilities=["knowledge", "escalation"],
        agent_id=uuid.uuid4(),
        agent_version_id=uuid.uuid4(),
        agent_name="Support Bot",
        agent_type="support",
        agent_capabilities=["voice"],
    )

    # Org-level capabilities
    assert ctx.has_org_capability("knowledge") is True
    assert ctx.has_org_capability("escalation") is True
    assert ctx.has_org_capability("voice") is False

    # Agent-level capabilities
    assert ctx.has_agent_capability("voice") is True
    assert ctx.has_agent_capability("negotiation") is False

    # Combined check
    assert ctx.has_capability("knowledge") is True
    assert ctx.has_capability("voice") is True
    assert ctx.has_capability("crm") is False


def test_training_agent_has_no_organization():
    ctx = AgentContext(
        agent_id=uuid.uuid4(),
        agent_version_id=uuid.uuid4(),
        agent_name="Cognition Agent",
        org_capabilities=["knowledge", "voice"],
    )
    assert ctx.organization_id is None
    assert ctx.has_org_capability("knowledge") is True
