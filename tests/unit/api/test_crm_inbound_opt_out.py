"""Opt-out gate: once a contact carries the CRM's 'opt-out' tag, LearningEngine must
stop responding entirely — not just avoid re-calling opt_out_contact."""

from uuid import uuid4

import pytest

import learning_engine.api.v1.endpoints.crm_inbound as ci


class FakeCache:
    async def get(self, key):
        return None

    async def set(self, key, value, ttl=3600):
        pass


class ExplodingPipelineRunner:
    """Fails the test if the pipeline is ever constructed for an opted-out contact."""

    def __init__(self, *a, **kw):
        raise AssertionError("PipelineRunner should not run for an opted-out contact")


@pytest.mark.asyncio
async def test_skips_pipeline_when_contact_already_opted_out(monkeypatch):
    monkeypatch.setattr(ci, "get_redis_cache", lambda: FakeCache())
    monkeypatch.setattr(ci, "PipelineRunner", ExplodingPipelineRunner)

    extra_context = {"contact": {"id": "c1", "tags": ["warm", "opt-out"]}}

    await ci._run_pipeline_and_reply(
        "no me escribas mas", uuid4(), uuid4(), object(), uuid4(),
        extra_context=extra_context, contact_id="c1",
    )


@pytest.mark.asyncio
async def test_runs_pipeline_when_contact_not_opted_out(monkeypatch):
    calls = []

    class FakeResult:
        qualification_terminal = False
        response = "hola"
        contact_qualification = {}
        analysis_summary = {}

    class FakeRunner:
        def __init__(self, *a, **kw):
            pass

        async def run(self, **kwargs):
            calls.append(kwargs)
            return FakeResult()

    async def fake_load_org(organization_id):
        return None  # no CRM connectivity — _send_reply_to_crm just warns & returns

    monkeypatch.setattr(ci, "get_redis_cache", lambda: FakeCache())
    monkeypatch.setattr(ci, "_load_org", fake_load_org)
    monkeypatch.setattr(ci, "PipelineRunner", FakeRunner)

    extra_context = {"contact": {"id": "c1", "tags": ["warm"]}}
    agent_context = type(
        "AC", (), {"agent_version_id": None, "has_capability": lambda self, c: False}
    )()

    await ci._run_pipeline_and_reply(
        "hola", uuid4(), uuid4(), agent_context, uuid4(),
        extra_context=extra_context, contact_id="c1",
    )

    assert len(calls) == 1
