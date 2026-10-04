"""Scheduling gate: create_appointment is blocked until the required contact
fields are known; saving them via update_contact in the same turn opens it."""

from uuid import uuid4

import httpx
import pytest

from prosales.services.crm_tools import CRMToolExecutor


def _executor(required, known=None):
    return CRMToolExecutor(
        base_url="https://crm.example.com",
        api_key="k",
        agent_id="a",
        conversation_id=uuid4(),
        contact_id="c1",
        required_fields=required,
        known_fields=known or set(),
    )


def _patch_http(monkeypatch):
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
            return FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)


@pytest.mark.asyncio
async def test_booking_blocked_when_required_missing(monkeypatch):
    _patch_http(monkeypatch)
    ex = _executor(required=["email", "phone"])
    result = await ex.execute("create_appointment", {"title": "Test drive", "starts_at": "x", "duration_minutes": 30})
    assert result["error"] == "missing_required_fields"
    assert set(result["fields"]) == {"email", "phone"}


@pytest.mark.asyncio
async def test_booking_allowed_when_seeded(monkeypatch):
    _patch_http(monkeypatch)
    ex = _executor(required=["email", "phone"], known={"email", "phone"})
    result = await ex.execute("create_appointment", {"title": "x", "starts_at": "x", "duration_minutes": 30})
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_update_contact_opens_gate_in_same_turn(monkeypatch):
    _patch_http(monkeypatch)
    ex = _executor(required=["email", "phone"], known={"phone"})

    # First booking attempt fails (email missing).
    r1 = await ex.execute("create_appointment", {"title": "x", "starts_at": "x", "duration_minutes": 30})
    assert r1["error"] == "missing_required_fields"

    # Agent saves the email → gate opens.
    await ex.execute("update_contact", {"email": "a@b.com"})
    r2 = await ex.execute("create_appointment", {"title": "x", "starts_at": "x", "duration_minutes": 30})
    assert r2 == {"ok": True}
