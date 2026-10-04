"""_push_qualification: pushes the cognitive qualification to the CRM via
update_contact, but dedups against the last push (Redis) so an unchanged
qualification isn't re-sent every turn."""

import pytest

from prosales.api.v1.endpoints.crm_inbound import _push_qualification


class FakeExecutor:
    def __init__(self):
        self.calls = []

    async def execute(self, name, args):
        self.calls.append((name, args))
        return {"ok": True}


class FakeCache:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ttl=3600):
        self.store[key] = value


QUAL = {
    "temperature": "hot",
    "status": "qualified",
    "readiness": 0.8,
    "bant": {"authority": True, "budget": True, "timeline": False, "need": True},
    "signals": ["positive_interest"],
    "facts": {"product_interest": "Audi A5"},
    "suggested_transition": "advance",
}


@pytest.mark.asyncio
async def test_push_then_skip_when_unchanged():
    ex, cache = FakeExecutor(), FakeCache()

    await _push_qualification(ex, cache, "contact-1", QUAL)
    assert len(ex.calls) == 1
    assert ex.calls[0][0] == "update_contact"

    # Same qualification next turn → deduped, no second call.
    await _push_qualification(ex, cache, "contact-1", QUAL)
    assert len(ex.calls) == 1


@pytest.mark.asyncio
async def test_push_again_when_changed():
    ex, cache = FakeExecutor(), FakeCache()
    await _push_qualification(ex, cache, "contact-1", QUAL)

    changed = {**QUAL, "temperature": "warm", "readiness": 0.5}
    await _push_qualification(ex, cache, "contact-1", changed)
    assert len(ex.calls) == 2


@pytest.mark.asyncio
async def test_push_noop_without_contact_or_qual():
    ex, cache = FakeExecutor(), FakeCache()
    await _push_qualification(ex, cache, None, QUAL)
    await _push_qualification(ex, cache, "contact-1", {})
    assert ex.calls == []
