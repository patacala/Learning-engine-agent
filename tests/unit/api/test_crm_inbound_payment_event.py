"""Payment (system) events continue the conversation: a payment.received inbound
carries a confirmed fact — not a user utterance — so it runs the pipeline
immediately (no debounce), without persisting a user turn, and injects a
system_event the prompt can acknowledge."""

from uuid import uuid4

import pytest
from fastapi import BackgroundTasks

import prosales.api.v1.endpoints.crm_inbound as ci
from prosales.api.v1.schemas.crm_inbound import CRMInboundRequest


def _payment_payload(conversation_id):
    """A payment.received inbound — note the payload has NO `channel`."""
    return {
        "organization_id": str(uuid4()),
        "event_type": "payment.received",
        "conversation_id": str(conversation_id),
        "contact_id": "c1",
        "payload": {"message": "Payment received: $500 deposit for the Audi A5."},
    }


class FakeCache:
    """Records list_push so the test can assert debounce was bypassed."""

    def __init__(self):
        self.pushes: list[tuple[str, str]] = []

    async def list_push(self, key, value, ttl=300):
        self.pushes.append((key, value))

    async def list_drain(self, key):
        return []


class FakeResult:
    qualification_terminal = False
    response = "Perfect, your deposit is confirmed — I'll hold the A5 for you."
    contact_qualification = {}
    analysis_summary = {}


def _agent_context(organization_id):
    return type(
        "AC",
        (),
        {
            "organization_id": organization_id,
            "agent_version_id": None,
            "has_capability": lambda self, c: False,
        },
    )()


def test_payment_payload_without_channel_validates():
    """(a) The payment payload has no `channel` and must still validate."""
    req = CRMInboundRequest(**_payment_payload(uuid4()))
    assert req.payload.channel is None
    assert req.event_type == "payment.received"


@pytest.mark.asyncio
async def test_payment_event_runs_system_event_pipeline(monkeypatch):
    """(b) store_user_message=False, (c) debounce bypassed, (d) system_event
    injected, (e) _send_reply_to_crm called."""
    conversation_id = uuid4()
    organization_id = uuid4()
    client_id = uuid4()

    run_calls: list[dict] = []
    sends: list[tuple] = []
    cache = FakeCache()

    class FakeRunner:
        def __init__(self, *a, **kw):
            pass

        async def run(self, **kwargs):
            run_calls.append(kwargs)
            return FakeResult()

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    async def fake_require_agent_context(session, x_api_key):
        return _agent_context(organization_id)

    async def fake_resolve(body, agent_context):
        return client_id, conversation_id

    async def fake_load_org(org_id):
        return None  # no CRM connectivity — _send_reply_to_crm would just warn

    async def fake_send(org, conv_id, content):
        sends.append((org, conv_id, content))

    monkeypatch.setattr(ci, "async_session_factory", lambda: _FakeSession())
    monkeypatch.setattr(ci, "require_agent_context", fake_require_agent_context)
    monkeypatch.setattr(ci, "_resolve_client_and_conversation", fake_resolve)
    monkeypatch.setattr(ci, "get_redis_cache", lambda: cache)
    monkeypatch.setattr(ci, "_load_org", fake_load_org)
    monkeypatch.setattr(ci, "PipelineRunner", FakeRunner)
    monkeypatch.setattr(ci, "_send_reply_to_crm", fake_send)

    body = CRMInboundRequest(**_payment_payload(conversation_id))
    background_tasks = BackgroundTasks()

    resp = await ci.crm_inbound(body, background_tasks, x_api_key="key")
    assert resp["status"] == "accepted"

    # (c) debounce bypassed — nothing buffered, no per-conversation timer armed.
    assert cache.pushes == []
    assert str(conversation_id) not in ci._debounce_tasks

    # Run the queued background task (the pipeline + reply).
    await background_tasks()

    assert len(run_calls) == 1
    kwargs = run_calls[0]
    # (b) the system confirmation is NOT persisted as a user turn.
    assert kwargs["store_user_message"] is False
    # (d) system_event injected with the confirmed-fact message.
    assert kwargs["extra_context"]["system_event"] == {
        "type": "payment.received",
        "message": "Payment received: $500 deposit for the Audi A5.",
    }
    # current_message still carries the content so analyzers/response have it.
    assert kwargs["message"] == "Payment received: $500 deposit for the Audi A5."
    # (e) the generated reply is delivered back to the CRM.
    assert sends == [(None, conversation_id, FakeResult.response)]
