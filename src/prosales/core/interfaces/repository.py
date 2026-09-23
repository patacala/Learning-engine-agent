from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID


class BaseRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID) -> Any | None:
        ...

    @abstractmethod
    async def save(self, entity: Any) -> Any:
        ...


class ConversationRepository(BaseRepository):
    @abstractmethod
    async def get_by_client(self, client_id: UUID) -> list[Any]:
        ...

    @abstractmethod
    async def get_messages(self, conversation_id: UUID, limit: int = 50) -> list[Any]:
        ...


class ClientRepository(BaseRepository):
    @abstractmethod
    async def get_memories(self, client_id: UUID) -> list[Any]:
        ...

    @abstractmethod
    async def save_memory(self, client_id: UUID, key: str, value: str) -> Any:
        ...


class KnowledgeRepository(BaseRepository):
    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> list[Any]:
        ...


class EventRepository(ABC):
    @abstractmethod
    async def append(self, event: Any) -> None:
        ...

    @abstractmethod
    async def get_by_conversation(self, conversation_id: UUID) -> list[Any]:
        ...
