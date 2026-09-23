"""Assistant session orchestration — the app's default conversational state.

An assistant session is a normal ``conversations`` row with ``channel="assistant"``.
It stores standard-role messages (user=user, assistant=assistant) and is deliberately
isolated from chat/roleplay: it never runs the sales pipeline and never feeds
``run_live_learning`` — so it neither qualifies contacts nor learns.

Follows the same short-session pattern as ``RoleplayService``: every DB operation
opens a short session via ``async_session_factory`` and no connection is held during
the LLM call.
"""

import logging
from uuid import UUID, uuid4

from prosales.channels.assistant.engine import AssistantResponder
from prosales.core.models.agent import AgentContext
from prosales.di.container import create_llm_provider
from prosales.infrastructure.database.connection import async_session_factory
from prosales.infrastructure.database.models import ConversationModel, MessageModel
from prosales.infrastructure.database.repositories.client import SQLClientRepository
from prosales.infrastructure.database.repositories.conversation import (
    SQLConversationRepository,
)
from prosales.infrastructure.llm.provider import LLMMessage

logger = logging.getLogger(__name__)

CHANNEL = "assistant"


class AssistantSessionNotFound(Exception):
    pass


class AssistantService:
    async def start(self, agent_context: AgentContext | None) -> ConversationModel:
        """Create an assistant conversation and return it (detached fields copied)."""
        organization_id = agent_context.organization_id if agent_context else None

        async with async_session_factory() as session:
            async with session.begin():
                client_repo = SQLClientRepository(session)
                conv_repo = SQLConversationRepository(session)

                # Each assistant session is an isolated synthetic client.
                client = await client_repo.get_or_create(
                    f"assistant-{uuid4()}", organization_id=organization_id
                )
                conversation = ConversationModel(
                    id=uuid4(),
                    client_id=client.id,
                    organization_id=organization_id,
                    channel=CHANNEL,
                )
                await conv_repo.save(conversation)
                # Safe to return past the session: expire_on_commit=False.
                return conversation

    async def message(
        self, session_id: UUID, text: str, agent_context: AgentContext | None
    ) -> str:
        """Advance the assistant conversation one turn and return its reply."""
        # Load history in a short session, then release the connection for the LLM call.
        async with async_session_factory() as session:
            conv_repo = SQLConversationRepository(session)
            conv = await conv_repo.get_by_id(session_id)
            if conv is None or conv.channel != CHANNEL:
                raise AssistantSessionNotFound(str(session_id))
            history = await conv_repo.get_messages(session_id, limit=40)
            # Standard role mapping: the assistant IS role="assistant".
            llm_history = [
                LLMMessage(role=m.role, content=m.content) for m in history
            ]

        responder = AssistantResponder(create_llm_provider())
        reply = await responder.respond(llm_history, text)

        async with async_session_factory() as session:
            async with session.begin():
                conv_repo = SQLConversationRepository(session)
                await conv_repo.add_message(
                    MessageModel(conversation_id=session_id, role="user", content=text)
                )
                await conv_repo.add_message(
                    MessageModel(
                        conversation_id=session_id, role="assistant", content=reply
                    )
                )
        return reply
