from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine


EventHandler = Callable[[Any], Coroutine[Any, Any, None]]


class EventBus(ABC):
    """Protocol for async event bus."""

    @abstractmethod
    async def publish(self, event_name: str, data: Any) -> None:
        ...

    @abstractmethod
    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        ...
