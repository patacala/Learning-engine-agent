import logging
from typing import Any

from prosales.core.interfaces.engine import BaseEngine
from prosales.engines.context_builder.models import RelevantContext
from prosales.engines.context_builder.relevance import select_critical_facts
from prosales.engines.memory.models import FullMemory

logger = logging.getLogger(__name__)

MAX_RECENT_MESSAGES = 10
MAX_CRITICAL_FACTS = 5


class ContextBuilderEngine(BaseEngine):
    """Filters full memory into compact, token-optimized context."""

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        memory: FullMemory = state["memory"]
        current_message: str = state["current_message"]

        # Recent messages (last N)
        recent_messages = memory.working.messages[-MAX_RECENT_MESSAGES:]

        # Critical facts
        critical_facts = select_critical_facts(memory.semantic.facts, MAX_CRITICAL_FACTS)
        facts_dicts = [{"key": f.key, "value": f.value} for f in critical_facts]

        # Conversation summary from episodic
        summary = ""
        if memory.episodic.total_interactions > 1:
            summary = (
                f"Cliente con {memory.episodic.total_interactions} interacciones previas."
            )
            if memory.episodic.last_interaction_summary:
                summary += f" Último: {memory.episodic.last_interaction_summary}"

        # Append factual historical context from episodes
        if memory.episodic.client_episodes:
            latest = memory.episodic.client_episodes[0]
            parts = []
            if latest.outcome and latest.outcome != "pending":
                parts.append(f"outcome={latest.outcome}")
            if latest.objections_detected:
                parts.append(f"objeciones={','.join(latest.objections_detected)}")
            if latest.strategies_used:
                parts.append(f"estrategias={','.join(latest.strategies_used)}")
            if parts:
                episode_ctx = f" Última conversación: {', '.join(parts)}."
                summary += episode_ctx

        context = RelevantContext(
            recent_messages=recent_messages,
            critical_facts=facts_dicts,
            conversation_summary=summary,
        )

        return {"context": context}
