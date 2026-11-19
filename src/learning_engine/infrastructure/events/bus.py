import asyncio
import logging
from collections import defaultdict
from typing import Any

from learning_engine.core.interfaces.event_bus import EventBus, EventHandler

logger = logging.getLogger(__name__)


class InMemoryEventBus(EventBus):
    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    async def publish(self, event_name: str, data: Any) -> None:
        handlers = self._handlers.get(event_name, [])
        for handler in handlers:
            try:
                asyncio.create_task(handler(data))
            except Exception:
                logger.exception("Event handler error for %s", event_name)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._handlers[event_name].append(handler)
