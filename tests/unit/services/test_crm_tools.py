"""CRMToolExecutor: server-injected contact_id/conversation_id (the model never
supplies them), the unknown-tool guard, and graceful error handling so a failing
CRM call doesn't crash the turn."""

from uuid import uuid4

import httpx
import pytest

from prosales.services.crm_tools import (
    CRMToolExecutor,
    qualification_to_contact_update,
    tool_schemas,
)


def _executor(contact_id="contact-123"):
    return CRMToolExecutor(
        base_url="https://crm.example.com/",
        api_key="crm_key",
        agent_id="agent-1",
        conversation_id=uuid4(),
        contact_id=contact_id,
    )


def test_tool_schemas_hide_injected_fields():
    schemas = {t["name"]: t for t in tool_schemas()}
    # contact_id/conversation_id are server-injected, never exposed to the model.
    props = schemas["create_appointment"]["parameters"]["properties"]
    assert "contact_id" not in props
    assert "conversation_id" not in props


def test_inject_adds_contact_id():
    ex = _executor()
    merged = ex._inject("create_appointment", {"title": "Test drive"})
    assert merged["contact_id"] == "contact-123"
    assert merged["conversation_id"] == ex.conversation_id
    assert merged["title"] == "Test drive"


def test_inject_skips_tools_without_injection():
    ex = _executor()
    merged = ex._inject("get_available_slots", {"from": "a", "to": "b"})
    assert merged == {"from": "a", "to": "b"}  # no IDs forced in


def test_qualification_mapping_uses_crm_leadscore_keys():
    update = qualification_to_contact_update(
        {
            "temperature": "hot",
            "status": "qualified",
            "readiness": 0.8,
            "bant": {"authority": True, "budget": True, "timeline": False, "need": True},
            "signals": ["positive_interest"],
            "facts": {"product_interest": "Audi A5"},
            "suggested_transition": "advance",
        }
    )
    cf = update["custom_fields"]
    # Keys the CRM's applyLeadScoreSignals actually reads.
    assert cf["urgency_level"] == "high"  # hot -> high tier
    assert cf["is_decision_maker"] is True
    assert cf["has_budget"] is True
    assert cf["service_needed"] == "Audi A5"
    assert cf["product_interest"] == "Audi A5"
    assert update["lead_score"] == 80
    assert update["ai_insights"]["temperature"] == "hot"


def test_qualification_mapping_cold_contact():
    update = qualification_to_contact_update(
        {"temperature": "cold", "bant": {}, "facts": {}, "readiness": 0.1}
    )
    assert update["custom_fields"]["urgency_level"] == "low"
    assert "service_needed" not in update["custom_fields"]  # no product yet
    assert update["lead_score"] == 10


@pytest.mark.asyncio
async def test_execute_unknown_tool_returns_error():
    result = await _executor().execute("nope", {})
    assert "unknown tool" in result["error"]


@pytest.mark.asyncio
async def test_execute_posts_expected_payload(monkeypatch):
    captured = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"ok": True}

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    ex = _executor()
    result = await ex.execute("update_contact", {"email": "a@b.com"})

    assert result == {"ok": True}
    assert captured["url"] == "https://crm.example.com/api/v1/ai/tools/execute"
    assert captured["json"]["tool"] == "update_contact"
    assert captured["json"]["agent_id"] == "agent-1"
    assert captured["json"]["input"]["contact_id"] == "contact-123"
    assert captured["json"]["input"]["email"] == "a@b.com"
    assert captured["headers"]["x-api-key"] == "crm_key"


@pytest.mark.asyncio
async def test_execute_http_error_returns_error_dict(monkeypatch):
    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            raise httpx.HTTPError("boom")

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    result = await _executor().execute("get_available_slots", {"from": "a", "to": "b"})
    assert "error" in result
