import logging
from typing import Any
from uuid import UUID

from learning_engine.core.models.events import DomainEvent
from learning_engine.infrastructure.database.models import EventModel
from learning_engine.infrastructure.database.repositories.event import SQLEventRepository

logger = logging.getLogger(__name__)


class EventStore:
    """Persists atomic domain events for learning."""

    def __init__(self, repo: SQLEventRepository):
        self.repo = repo

    async def store(self, event: DomainEvent) -> None:
        # Strip timezone info — DB column is naive UTC
        ts = event.timestamp.replace(tzinfo=None) if event.timestamp.tzinfo else event.timestamp
        model = EventModel(
            id=event.id,
            event_type=event.event_type,
            conversation_id=event.conversation_id,
            client_id=event.client_id,
            data=event.data,
            timestamp=ts,
        )
        await self.repo.append(model)

    async def get_conversation_events(self, conversation_id: UUID) -> list[EventModel]:
        return await self.repo.get_by_conversation(conversation_id)
