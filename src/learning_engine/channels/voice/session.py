"""Voice session state — Redis-backed for active calls."""

import json
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from learning_engine.infrastructure.cache.redis import RedisCache


class VoiceSession(BaseModel):
    """State of an active voice call — stored in Redis."""

    session_id: str
    conversation_id: UUID
    client_id: UUID
    organization_id: UUID | None = None
    agent_context_data: dict | None = None
    turn_count: int = 0
    started_at: datetime
    provider_type: str = ""
    from_number: str | None = None
    to_number: str | None = None


class VoiceSessionManager:
    """Redis-backed session state for active voice calls."""

    KEY_PREFIX = "voice:session:"
    SESSION_TTL = 3600

    def __init__(self, redis: RedisCache):
        self.redis = redis

    def _key(self, session_id: str) -> str:
        return f"{self.KEY_PREFIX}{session_id}"

    async def create(self, session_id: str, session: VoiceSession) -> None:
        await self.redis.set(
            self._key(session_id),
            session.model_dump(mode="json"),
            ttl=self.SESSION_TTL,
        )

    async def get(self, session_id: str) -> VoiceSession | None:
        data = await self.redis.get(self._key(session_id))
        if data is None:
            return None
        return VoiceSession.model_validate(data)

    async def increment_turn(self, session_id: str) -> int:
        session = await self.get(session_id)
        if session is None:
            return 0
        session.turn_count += 1
        await self.create(session_id, session)
        return session.turn_count

    async def delete(self, session_id: str) -> None:
        await self.redis.delete(self._key(session_id))
