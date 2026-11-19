import logging
from typing import Any
from uuid import UUID

from learning_engine.core.enums import MessageRole
from learning_engine.core.interfaces.engine import BaseEngine
from learning_engine.core.models.client import ClientMemory
from learning_engine.core.models.conversation import Message
from learning_engine.engines.episodic.models import EpisodeSummary
from learning_engine.engines.memory.models import EpisodicMemory, FullMemory, SemanticMemory, WorkingMemory
from learning_engine.infrastructure.database.repositories.client import SQLClientRepository
from learning_engine.infrastructure.database.repositories.conversation import SQLConversationRepository
from learning_engine.infrastructure.database.repositories.episodic import SQLEpisodicRepository

logger = logging.getLogger(__name__)


class MemoryEngine(BaseEngine):
    """3-tier memory: working (current), episodic (past convos), semantic (facts).

    Uses a short read-session (via session_factory) so the DB connection is not
    held across the LLM-heavy nodes downstream.
    """

    def __init__(self, session_factory, use_episodic: bool = True):
        self._sf = session_factory
        self.use_episodic = use_episodic

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        conversation_id: UUID = state["conversation_id"]
        client_id: UUID = state["client_id"]

        async with self._sf() as s:
            conversation_repo = SQLConversationRepository(s)
            client_repo = SQLClientRepository(s)
            episodic_repo = SQLEpisodicRepository(s) if self.use_episodic else None
            working = await self._load_working(conversation_repo, conversation_id)
            episodic = await self._load_episodic(
                conversation_repo, episodic_repo, client_id, conversation_id
            )
            semantic = await self._load_semantic(client_repo, client_id)

        return {"memory": FullMemory(working=working, episodic=episodic, semantic=semantic)}

    async def _load_working(self, conversation_repo, conversation_id: UUID) -> WorkingMemory:
        messages_db = await conversation_repo.get_messages(conversation_id, limit=50)
        messages = [
            Message(
                id=m.id,
                conversation_id=m.conversation_id,
                role=MessageRole(m.role),
                content=m.content,
            )
            for m in messages_db
        ]
        return WorkingMemory(messages=messages)

    async def _load_episodic(
        self, conversation_repo, episodic_repo, client_id: UUID, current_conv_id: UUID
    ) -> EpisodicMemory:
        conversations = await conversation_repo.get_by_client(client_id)
        past = [
            {
                "id": str(c.id),
                "stage": c.stage,
                "created_at": str(c.created_at),
                "is_active": c.is_active,
            }
            for c in conversations
            if c.id != current_conv_id
        ]

        # Load structured episodes if repo available
        client_episodes: list[EpisodeSummary] = []
        last_interaction_summary = ""

        if episodic_repo:
            try:
                episodes_db = await episodic_repo.get_by_client(client_id, limit=10)
                client_episodes = [
                    EpisodeSummary(
                        conversation_id=ep.conversation_id,
                        dominant_intent=ep.dominant_intent,
                        dominant_sentiment=ep.dominant_sentiment,
                        objections_detected=ep.objections_detected or [],
                        strategies_used=ep.strategies_used or [],
                        outcome=ep.outcome,
                        closed_at=ep.closed_at,
                    )
                    for ep in episodes_db
                ]
                # Build factual summary from most recent episode
                if client_episodes:
                    latest = client_episodes[0]
                    parts = [f"outcome={latest.outcome}"]
                    if latest.dominant_intent:
                        parts.append(f"intent={latest.dominant_intent}")
                    if latest.objections_detected:
                        parts.append(f"objeciones={','.join(latest.objections_detected)}")
                    if latest.strategies_used:
                        parts.append(f"estrategias={','.join(latest.strategies_used)}")
                    last_interaction_summary = ", ".join(parts)
            except Exception as e:
                logger.warning("Failed to load episodic episodes: %s", e)

        return EpisodicMemory(
            past_conversations=past[:20],
            total_interactions=len(conversations),
            last_interaction_summary=last_interaction_summary,
            client_episodes=client_episodes,
        )

    async def _load_semantic(self, client_repo, client_id: UUID) -> SemanticMemory:
        memories_db = await client_repo.get_memories(client_id)
        facts = [
            ClientMemory(
                id=m.id,
                client_id=m.client_id,
                key=m.key,
                value=m.value,
                confidence=m.confidence,
            )
            for m in memories_db
        ]
        return SemanticMemory(facts=facts)
