"""IdentityEngine — loads agent identity into pipeline state."""

import logging
from typing import Any

from prosales.core.interfaces.engine import BaseEngine
from prosales.core.models.identity import AgentIdentity

logger = logging.getLogger(__name__)


class IdentityEngine(BaseEngine):
    """Loads agent identity. No transformations — just load and pass."""

    def __init__(self, identity_provider=None):
        self.identity_provider = identity_provider

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        ctx = state.get("agent_context")

        if not ctx:
            return {"identity": AgentIdentity()}

        if not self.identity_provider:
            return {"identity": AgentIdentity(name=ctx.agent_name)}

        identity = await self.identity_provider.get(ctx.agent_version_id)
        if identity is None:
            return {"identity": AgentIdentity(name=ctx.agent_name)}

        return {"identity": identity}
