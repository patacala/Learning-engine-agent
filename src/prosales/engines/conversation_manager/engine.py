import logging
from typing import Any

from prosales.core.enums import ConversationPath
from prosales.core.interfaces.engine import BaseEngine
from prosales.engines.conversation_manager.models import RouteDecision
from prosales.engines.conversation_manager.routes import FAST_PATH_SKIP_NODES, resolve_path

logger = logging.getLogger(__name__)


class ConversationManager(BaseEngine):
    """Router cognitivo: decides FAST_PATH vs FULL_PATH."""

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        analysis = state.get("analysis")
        message = state["current_message"]

        intent = analysis.intent.intent if analysis else None
        path = resolve_path(intent, len(message)) if intent else ConversationPath.FULL_PATH

        skip_nodes = FAST_PATH_SKIP_NODES if path == ConversationPath.FAST_PATH else []

        route = RouteDecision(
            path=path,
            skip_nodes=skip_nodes,
            reasoning=f"Intent={intent}, len={len(message)} → {path}",
        )

        logger.info("Route decision: %s", route.reasoning)
        return {"route": route}
