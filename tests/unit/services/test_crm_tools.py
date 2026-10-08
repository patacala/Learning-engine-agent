"""CRMToolExecutor: server-injected contact_id/conversation_id (the model never
supplies them), the unknown-tool guard, and graceful error handling so a failing
CRM call doesn't crash the turn."""

from uuid import uuid4

import httpx
import pytest

from prosales.core.models.qualification_schema import default_schema
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


def test_opt_out_available_without_appointment_capability():
    ex = _executor()
    ex.actions_enabled = False
    names = {t["name"] for t in ex.tool_schemas()}
    assert names == {"opt_out_contact"}


def test_all_tools_available_with_appointment_capability():
    ex = _executor()  # actions_enabled defaults to True
    names = {t["name"] for t in ex.tool_schemas()}
    assert "opt_out_contact" in names
    assert "create_appointment" in names


@pytest.mark.asyncio
async def test_execute_rejects_gated_tool_without_capability():
    ex = _executor()
    ex.actions_enabled = False
    result = await ex.execute("create_appointment", {"title": "x", "starts_at": "t", "duration_minutes": 30})
    assert "not available" in result["error"]


@pytest.mark.asyncio
async def test_execute_allows_opt_out_without_capability(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"opted_out": True}

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            return FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    ex = _executor()
    ex.actions_enabled = False
    result = await ex.execute("opt_out_contact", {})
    assert result == {"opted_out": True}


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


def test_qualification_mapping_service_and_product_are_distinct():
    schema = default_schema()
    update = qualification_to_contact_update(
        {
            "temperature": "hot",
            "status": "qualified",
            "bant": {"authority": True, "budget": True, "timeline": True, "need": True},
            "signals": ["positive_interest"],
            "facts": {
                "product_interest": "Audi A5",
                "service_needed": "financiamiento",
                "full_name": "Peter Barranco",
                "email": "p@b.com",
            },
            "suggested_transition": "advance",
        },
        schema=schema,
        analysis_summary={"intent": "inquiry", "sentiment": "positive"},
    )
    cf = update["custom_fields"]
    assert cf["product_interest"] == "Audi A5"
    assert cf["service_needed"] == "financiamiento"  # distinct, not aliased
    assert cf["is_decision_maker"] is True
    assert cf["has_budget"] is True
    # Native contact fields routed top-level, name split.
    assert update["first_name"] == "Peter"
    assert update["last_name"] == "Barranco"
    assert update["email"] == "p@b.com"
    assert update["ai_insights"]["intent"] == "inquiry"
    assert "lead_score" not in update  # CRM computes it from custom_fields


def test_urgency_from_purchase_timeline_not_temperature():
    schema = default_schema()
    # Hot lead but buying "in 3 months" → urgency low (score not inflated).
    slow = qualification_to_contact_update(
        {"temperature": "hot", "bant": {}, "facts": {"purchase_timeline": "en 3 meses"}},
        schema=schema,
    )
    assert slow["custom_fields"]["urgency_level"] == "low"
    # Same hot lead buying "this week" → high.
    fast = qualification_to_contact_update(
        {"temperature": "hot", "bant": {}, "facts": {"purchase_timeline": "esta semana"}},
        schema=schema,
    )
    assert fast["custom_fields"]["urgency_level"] == "high"


def test_tags_union_with_existing():
    update = qualification_to_contact_update(
        {"temperature": "warm", "signals": ["price_objection", "appointment_requested"], "facts": {}},
        existing_tags=["vip", "warm"],
    )
    tags = set(update["tags"])
    assert {"vip", "warm", "objecion-precio", "pidio-cita"} <= tags  # human 'vip' preserved


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


# --- communication tools (send_email / send_sms) --------------------------


def test_send_email_and_sms_hide_injected_fields():
    schemas = {t["name"]: t for t in tool_schemas()}
    for name in ("send_email", "send_sms"):
        props = schemas[name]["parameters"]["properties"]
        assert "contact_id" not in props
        assert "conversation_id" not in props


def test_communication_tools_gated_behind_appointment_capability():
    ex = _executor()
    ex.actions_enabled = False
    names = {t["name"] for t in ex.tool_schemas()}
    assert "send_email" not in names
    assert "send_sms" not in names
    ex.actions_enabled = True
    names = {t["name"] for t in ex.tool_schemas()}
    assert {"send_email", "send_sms"} <= names


@pytest.mark.asyncio
async def test_send_email_blocked_without_known_email():
    ex = _executor()  # known_fields empty
    result = await ex.execute("send_email", {"subject": "Quote", "body": "..."})
    assert result["error"] == "missing_required_fields"
    assert result["fields"] == ["email"]


@pytest.mark.asyncio
async def test_send_sms_blocked_without_known_phone():
    ex = _executor()
    result = await ex.execute("send_sms", {"message": "Hi"})
    assert result["error"] == "missing_required_fields"
    assert result["fields"] == ["phone"]


@pytest.mark.asyncio
async def test_send_email_proceeds_when_email_known(monkeypatch):
    captured = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"sent": True, "message_id": "m-1"}

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            captured["json"] = json
            return FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    ex = _executor()
    ex.known_fields.add("email")
    result = await ex.execute("send_email", {"subject": "Quote", "body": "Audi Q5 pricing"})

    assert result == {"sent": True, "message_id": "m-1"}
    assert captured["json"]["tool"] == "send_email"
    assert captured["json"]["input"]["contact_id"] == "contact-123"
    assert captured["json"]["input"]["subject"] == "Quote"
