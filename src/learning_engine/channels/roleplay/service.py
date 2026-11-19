"""Roleplay session orchestration.

A roleplay session is a normal ``conversations`` row with ``channel="roleplay"``,
a ``scenario`` prompt and a ``roleplay_mode``:

- ``mode="agent"``  → Cognition plays the SELLER (full sales pipeline via
  ``PipelineRunner``); the human trainer plays the client. Standard role storage
  (client=user, seller=assistant).
- ``mode="client"`` → Cognition plays the CLIENT (lightweight persona LLM); the
  human trainer plays the SELLER. To make learning capture the human seller's
  technique, we store the seller's turns as role="assistant" and Cognition's
  client replies as role="user" — because the evidence layer maps
  ``assistant → agent`` / ``user → client`` (see ``_ROLE_TO_SPEAKER``).

Either way, on ``end`` the transcript is fed to ``run_live_learning`` exactly like
a pasted transcript, so good seller lines become winning expressions / moves.
"""

import logging
from uuid import UUID, uuid4

from learning_engine.channels.roleplay.engine import ClientPersonaResponder
from learning_engine.core.enums import SUB_OUTCOME_TO_OUTCOME, Outcome, RoleplaySubOutcome
from learning_engine.core.models.agent import AgentContext
from learning_engine.di.container import create_llm_provider
from learning_engine.infrastructure.cache.redis import RedisCache
from learning_engine.infrastructure.database.connection import async_session_factory
from learning_engine.infrastructure.database.models import ConversationModel, MessageModel
from learning_engine.infrastructure.database.repositories.client import SQLClientRepository
from learning_engine.infrastructure.database.repositories.conversation import (
    SQLConversationRepository,
)
from learning_engine.infrastructure.llm.provider import LLMMessage
from learning_engine.services.pipeline_runner import PipelineRunner

logger = logging.getLogger(__name__)

AGENT = "agent"
CLIENT = "client"
_VALID_MODES = {AGENT, CLIENT}


class RoleplaySessionNotFound(Exception):
    pass


class RoleplayModeError(Exception):
    pass


class RoleplayClosedError(Exception):
    """Raised when a turn is attempted on an already-closed roleplay session."""


class RoleplayOutcomeError(Exception):
    """Raised when end() is called with an outcome outside the Outcome vocabulary."""


class RoleplayService:
    def __init__(self, cache: RedisCache | None = None):
        self._cache = cache

    async def start(
        self, scenario: str, mode: str, agent_context: AgentContext | None
    ) -> ConversationModel:
        """Create a roleplay conversation and return it (detached fields copied)."""
        if mode not in _VALID_MODES:
            raise RoleplayModeError(f"mode must be one of {_VALID_MODES}, got {mode!r}")

        organization_id = agent_context.organization_id if agent_context else None
        agent_version_id = agent_context.agent_version_id if agent_context else None

        async with async_session_factory() as session:
            async with session.begin():
                client_repo = SQLClientRepository(session)
                conv_repo = SQLConversationRepository(session)

                # Each roleplay is an isolated synthetic prospect.
                client = await client_repo.get_or_create(
                    f"roleplay-{uuid4()}", organization_id=organization_id
                )
                conversation = ConversationModel(
                    id=uuid4(),
                    client_id=client.id,
                    organization_id=organization_id,
                    agent_version_id=agent_version_id,
                    channel="roleplay",
                    scenario=scenario,
                    roleplay_mode=mode,
                )
                await conv_repo.save(conversation)
                # Safe to return past the session: expire_on_commit=False.
                return conversation

    async def turn(
        self, conversation_id: UUID, text: str, agent_context: AgentContext | None
    ) -> str:
        """Advance the roleplay one turn and return Cognition's reply."""
        conv = await self._load(conversation_id)
        if conv.channel != "roleplay":
            raise RoleplayModeError("conversation is not a roleplay session")
        if not conv.is_active:
            # end() already scheduled idempotent learning (learned_at); further
            # turns would silently never be learned, so reject them outright.
            raise RoleplayClosedError(str(conversation_id))

        if conv.roleplay_mode == AGENT:
            return await self._turn_agent(conv, text, agent_context)
        return await self._turn_client(conv, text)

    async def _turn_agent(
        self, conv: ConversationModel, text: str, agent_context: AgentContext | None
    ) -> str:
        """Cognition = seller. Reuse the full sales pipeline; standard role storage."""
        runner = PipelineRunner(async_session_factory, cache=self._cache)
        result = await runner.run(
            message=text,
            client_id=conv.client_id,
            conversation_id=conv.id,
            agent_context=agent_context,
            store_user_message=True,
        )
        return result.response

    async def _turn_client(self, conv: ConversationModel, text: str) -> str:
        """Cognition = client persona. Human's turn is the seller (stored as agent)."""
        responder = ClientPersonaResponder(create_llm_provider())

        async with async_session_factory() as session:
            async with session.begin():
                # Serialize turns of the SAME session: turn_index is derived from a
                # row count, so concurrent turns could interleave the seller/client
                # pair and break the seller→client ordering the evidence layer assumes.
                await session.get(ConversationModel, conv.id, with_for_update=True)

                conv_repo = SQLConversationRepository(session)
                history = await conv_repo.get_messages(conv.id, limit=100)
                # Orient history from the client-persona's point of view: the
                # persona's own past lines (stored role="user") are "assistant";
                # the seller's lines (stored role="assistant") are "user".
                llm_history = [
                    LLMMessage(
                        role="assistant" if m.role == "user" else "user",
                        content=m.content,
                    )
                    for m in history
                ]

                reply = await responder.respond(
                    scenario=conv.scenario or "", history=llm_history, seller_message=text
                )

                # Store with SALES roles (not who-is-the-AI) so learning is correct:
                # seller (human) → assistant, client (Cognition) → user.
                await conv_repo.add_message(
                    MessageModel(conversation_id=conv.id, role="assistant", content=text)
                )
                await conv_repo.add_message(
                    MessageModel(conversation_id=conv.id, role="user", content=reply)
                )
                return reply

    async def end(
        self, conversation_id: UUID, outcome: str, sub_outcome: str | None = None
    ) -> tuple[UUID, str]:
        """Close the session and set the outcome that drives learning.

        If ``sub_outcome`` is given (a scenario-flavored signal like
        "objection_handled"), it overrides ``outcome`` via
        ``SUB_OUTCOME_TO_OUTCOME`` so the trainer can give finer feedback while
        the learning pipeline keeps consuming the coarse terminal Outcome
        unchanged. Without it, behavior is identical to before.

        Returns ``(conversation_id, effective_outcome)`` — the caller uses
        ``effective_outcome`` (not the raw request field) to decide whether to
        schedule background learning, since ``sub_outcome`` may have overridden it.
        """
        effective_outcome = resolve_outcome(outcome, sub_outcome)
        async with async_session_factory() as session:
            async with session.begin():
                conv = await session.get(ConversationModel, conversation_id)
                if conv is None or conv.channel != "roleplay":
                    raise RoleplaySessionNotFound(str(conversation_id))
                conv.outcome = effective_outcome
                conv.sub_outcome = sub_outcome
                conv.is_active = False
        return conversation_id, effective_outcome

    async def _load(self, conversation_id: UUID) -> ConversationModel:
        async with async_session_factory() as session:
            conv = await session.get(ConversationModel, conversation_id)
            if conv is None:
                raise RoleplaySessionNotFound(str(conversation_id))
            # Detach a plain snapshot of the fields we use downstream.
            session.expunge(conv)
            return conv

    async def transcript(self, conversation_id: UUID) -> ConversationModel:
        """Load the conversation with its messages for presentation."""
        async with async_session_factory() as session:
            conv_repo = SQLConversationRepository(session)
            conv = await conv_repo.get_by_id(conversation_id)
            if conv is None or conv.channel != "roleplay":
                raise RoleplaySessionNotFound(str(conversation_id))
            return conv


def resolve_outcome(outcome: str, sub_outcome: str | None) -> str:
    """Derive the terminal-vocabulary outcome to persist, validating the input.

    ``sub_outcome``, when given, wins over ``outcome`` via ``SUB_OUTCOME_TO_OUTCOME``.
    Raises ``RoleplayOutcomeError`` if neither is a valid vocabulary value.
    """
    if sub_outcome is not None:
        if sub_outcome not in {s.value for s in RoleplaySubOutcome}:
            raise RoleplayOutcomeError(
                f"sub_outcome must be one of {[s.value for s in RoleplaySubOutcome]}, "
                f"got {sub_outcome!r}"
            )
        return SUB_OUTCOME_TO_OUTCOME[RoleplaySubOutcome(sub_outcome)].value
    if outcome not in {o.value for o in Outcome}:
        raise RoleplayOutcomeError(
            f"outcome must be one of {[o.value for o in Outcome]}, got {outcome!r}"
        )
    return outcome


def learns_from_outcome(outcome: str) -> bool:
    """Whether an outcome triggers background learning (only terminal ones do)."""
    try:
        return Outcome(outcome).is_terminal()
    except ValueError:
        return False


def speaker_for(role: str, mode: str | None) -> str:
    """Map a stored message role to who actually spoke, given the roleplay mode."""
    if mode == CLIENT:
        # seller (human) stored as assistant; client (Cognition) stored as user.
        return "trainer" if role == "assistant" else "cognition"
    # agent mode (or default): client (human) is user; seller (Cognition) is assistant.
    return "trainer" if role == "user" else "cognition"
