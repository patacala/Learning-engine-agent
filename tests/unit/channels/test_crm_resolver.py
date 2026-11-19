"""Inbound voice: LearningEngine asks the CRM which org owns the Retell agent that
answered (LearningEngine stores no agent/number->org mapping nor any credential)."""

import httpx
import pytest

from learning_engine.channels.voice import crm_resolver


@pytest.mark.asyncio
async def test_returns_none_without_config(monkeypatch):
    monkeypatch.setattr(crm_resolver.settings, "crm_base_url", "")
    assert await crm_resolver.resolve_org_for_call("agent_x", "+1234567890") is None


@pytest.mark.asyncio
async def test_returns_none_without_agent_or_number(monkeypatch):
    monkeypatch.setattr(crm_resolver.settings, "crm_base_url", "https://crm.example.com")
    assert await crm_resolver.resolve_org_for_call(None, None) is None


def _fake_client(capture: dict, payload: dict):
    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return payload

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None, headers=None):
            capture["url"] = url
            capture["params"] = params
            capture["headers"] = headers
            return FakeResp()

    return FakeClient


@pytest.mark.asyncio
async def test_sends_agent_as_primary_and_returns_ids(monkeypatch):
    monkeypatch.setattr(crm_resolver.settings, "crm_base_url", "https://crm.example.com/")
    monkeypatch.setattr(crm_resolver.settings, "internal_api_token", "shared-secret")
    captured: dict = {}
    monkeypatch.setattr(
        httpx, "AsyncClient",
        _fake_client(captured, {"organization_id": "org-1", "agent_version_id": "ver-1"}),
    )

    out = await crm_resolver.resolve_org_for_call("agent_x", "+1234567890")

    assert out == {"organization_id": "org-1", "agent_version_id": "ver-1"}
    assert captured["params"] == {"agent": "agent_x", "number": "+1234567890"}
    assert captured["headers"]["x-internal-token"] == "shared-secret"
    assert captured["url"].endswith("/api/v1/integrations/voice/resolve")


@pytest.mark.asyncio
async def test_unwraps_crm_data_envelope(monkeypatch):
    """The CRM wraps every response in {data: {...}, timestamp}; the ids live
    under "data". Reading them at the root silently yields a generic agent."""
    monkeypatch.setattr(crm_resolver.settings, "crm_base_url", "https://crm.example.com/")
    monkeypatch.setattr(crm_resolver.settings, "internal_api_token", "shared-secret")
    captured: dict = {}
    monkeypatch.setattr(
        httpx, "AsyncClient",
        _fake_client(
            captured,
            {
                "data": {"organization_id": "org-1", "agent_version_id": "ver-1"},
                "timestamp": "2026-10-16T00:00:00Z",
            },
        ),
    )

    out = await crm_resolver.resolve_org_for_call("agent_x", "+1234567890")

    assert out == {"organization_id": "org-1", "agent_version_id": "ver-1"}


@pytest.mark.asyncio
async def test_best_effort_on_error_returns_none(monkeypatch):
    monkeypatch.setattr(crm_resolver.settings, "crm_base_url", "https://crm.example.com")
    monkeypatch.setattr(crm_resolver.settings, "internal_api_token", "shared-secret")

    class Boom:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            raise httpx.HTTPError("crm down")

    monkeypatch.setattr(httpx, "AsyncClient", Boom)
    assert await crm_resolver.resolve_org_for_call("agent_x") is None
