"""EphemeralMemoryEngine — in-memory memory for the Test Playground.

Replaces the DB-backed MemoryEngine during isolated test conversations. It
builds working memory from the history the UI sends and exposes scenario
quick-facts as semantic facts, without reading or writing any client,
conversation, or episode rows.
"""

from typing import Any
from uuid import uuid4

from learning_engine.core.enums import MessageRole
from learning_engine.core.interfaces.engine import BaseEngine
from learning_engine.core.models.client import ClientMemory
from learning_engine.core.models.conversation import Message
from learning_engine.engines.memory.models import (
    EpisodicMemory,
    FullMemory,
    SemanticMemory,
    WorkingMemory,
)


class EphemeralMemoryEngine(BaseEngine):
    """Builds FullMemory from request payload; never touches the database."""

    def __init__(
        self,
        history: list[dict] | None = None,
        quick_facts: dict[str, str] | None = None,
    ):
        self.history = history or []
        self.quick_facts = quick_facts or {}

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        conversation_id = state.get("conversation_id")

        messages: list[Message] = []
        for turn in self.history:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if not content:
                continue
            try:
                role_enum = MessageRole(role)
            except ValueError:
                role_enum = MessageRole.USER
            messages.append(
                Message(
                    id=uuid4(),
                    conversation_id=conversation_id,
                    role=role_enum,
                    content=content,
                )
            )

        facts = [
            ClientMemory(
                id=uuid4(),
                client_id=state.get("client_id"),
                key=key,
                value=str(value),
                confidence=1.0,
            )
            for key, value in self.quick_facts.items()
            if str(value).strip()
        ]

        memory = FullMemory(
            working=WorkingMemory(messages=messages),
            episodic=EpisodicMemory(),
            semantic=SemanticMemory(facts=facts),
        )
        return {"memory": memory}
