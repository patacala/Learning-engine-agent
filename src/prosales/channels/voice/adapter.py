"""Voice adapter — orchestrates a voice session, provider-agnostic."""

import logging
from collections.abc import AsyncGenerator
from datetime import datetime
from uuid import uuid4, UUID

from sqlalchemy.ext.asyncio import AsyncSession

from prosales.channels.voice.events import CallEndedEvent, CallStartedEvent
from prosales.channels.voice.notifier import CRMNotifier
from prosales.channels.voice.providers.base import VoiceChunk, VoiceProvider
from prosales.channels.voice.session import VoiceSession, VoiceSessionManager
from prosales.channels.voice.streaming import split_into_sentences
from prosales.core.models.agent import AgentContext
from prosales.channels.voice.crm_resolver import resolve_org_for_call
from prosales.infrastructure.agent.resolver import AgentContextResolver, resolve_by_ids
from prosales.infrastructure.cache.redis import RedisCache
from prosales.infrastructure.database.models import ConversationModel
from prosales.infrastructure.database.repositories.client import SQLClientRepository
from prosales.infrastructure.database.repositories.conversation import SQLConversationRepository
from prosales.services.pipeline_runner import PipelineRunner

logger = logging.getLogger(__name__)


class VoiceAdapter:
    """Orchestrates a voice session — provider-agnostic.

    Flow: Provider event → parse → run pipeline → format → send back
    """

    def __init__(
        self,
        provider: VoiceProvider,
        session_manager: VoiceSessionManager,
        session_factory,
        cache: RedisCache | None = None,
        notifier: CRMNotifier | None = None,
    ):
        self.provider = provider
        self.session_manager = session_manager
        self.session_factory = session_factory
        self.cache = cache
        self.notifier = notifier
        self._session_id: str | None = None
        self._db_session: AsyncSession | None = None

    async def on_session_start(self, session_id: str, metadata: dict) -> None:
        """Initialize voice session: resolve agent, create conversation."""
        self._session_id = session_id

        async with self.session_factory() as db_session:
            async with db_session.begin():
                # Resolve agent context from metadata
                # Retell sends call.direction at top level, our outbound puts it in metadata
                nested_meta = metadata.get("metadata", {})
                agent_context = None
                direction = (
                    metadata.get("direction")
                    or nested_meta.get("direction", "inbound")
                )

                # Outbound: resolve by IDs (no api_key needed)
                org_id = metadata.get("organization_id") or nested_meta.get("organization_id")
                ver_id = metadata.get("agent_version_id") or nested_meta.get("agent_version_id")
                if org_id and ver_id:
                    from uuid import UUID
                    agent_context = await resolve_by_ids(
                        db_session, UUID(str(org_id)), UUID(str(ver_id))
                    )
                else:
                    # Inbound: identify the org by the Retell agent that answered
                    # (the same agent configured on the org's voice channel). Ask
                    # the CRM to resolve it; the dialed number is a fallback.
                    # ProSales stores no agent/number->org mapping nor any Retell
                    # credential. Falls back to the legacy api_key path.
                    agent_id = metadata.get("agent_id") or nested_meta.get("agent_id")
                    dialed = (
                        metadata.get("to_number") or nested_meta.get("to_number")
                        or metadata.get("callee_number") or nested_meta.get("callee_number")
                    )
                    resolved = await resolve_org_for_call(agent_id, dialed)
                    if resolved:
                        from uuid import UUID
                        agent_context = await resolve_by_ids(
                            db_session,
                            UUID(str(resolved["organization_id"])),
                            UUID(str(resolved["agent_version_id"])),
                        )
                    else:
                        api_key = metadata.get("api_key") or nested_meta.get("api_key")
                        if api_key and self.cache:
                            resolver = AgentContextResolver(db_session, self.cache)
                            agent_context = await resolver.resolve(api_key)

                organization_id = (
                    agent_context.organization_id if agent_context else None
                )

                # Get or create client from phone number
                from_number = metadata.get("from_number") or metadata.get(
                    "caller_number"
                )
                to_number = metadata.get("to_number") or metadata.get(
                    "callee_number"
                )

                client_repo = SQLClientRepository(db_session)
                client = await client_repo.get_or_create(
                    external_id=from_number or f"voice-{session_id}",
                    organization_id=organization_id,
                )

                # Create conversation
                conversation_repo = SQLConversationRepository(db_session)
                conversation = ConversationModel(
                    id=uuid4(),
                    client_id=client.id,
                    organization_id=organization_id,
                    agent_version_id=agent_context.agent_version_id if agent_context else None,
                )
                await conversation_repo.save(conversation)

                # Store voice call record
                from prosales.infrastructure.database.models_voice import VoiceCallModel

                voice_call = VoiceCallModel(
                    id=uuid4(),
                    session_id=session_id,
                    provider_type=getattr(self.provider, "PROVIDER_TYPE", "unknown"),
                    conversation_id=conversation.id,
                    organization_id=organization_id,
                    client_id=client.id,
                    from_number=from_number,
                    to_number=to_number,
                    started_at=datetime.utcnow(),
                )
                db_session.add(voice_call)

                # Create Redis session
                voice_session = VoiceSession(
                    session_id=session_id,
                    conversation_id=conversation.id,
                    client_id=client.id,
                    organization_id=organization_id,
                    agent_context_data=(
                        agent_context.model_dump(mode="json")
                        if agent_context
                        else None
                    ),
                    started_at=datetime.utcnow(),
                    provider_type=getattr(
                        self.provider, "PROVIDER_TYPE", "unknown"
                    ),
                    from_number=from_number,
                    to_number=to_number,
                )
                await self.session_manager.create(session_id, voice_session)

        # Notify CRM
        if self.notifier:
            session = await self.session_manager.get(session_id)
            if session:
                await self.notifier.notify_call_started(
                    CallStartedEvent(
                        session_id=session_id,
                        conversation_id=session.conversation_id,
                        client_id=session.client_id,
                        organization_id=session.organization_id,
                        from_number=session.from_number,
                        to_number=session.to_number,
                        provider_type=session.provider_type,
                        started_at=session.started_at,
                    )
                )

        logger.info("Voice session started: %s", session_id)

    async def on_user_speech(
        self, session_id: str, transcript: str
    ) -> AsyncGenerator[VoiceChunk, None]:
        """Process user speech through the cognitive pipeline."""
        session = await self.session_manager.get(session_id)
        if not session:
            logger.warning("No session found for %s", session_id)
            return

        # Reconstruct agent context if available
        agent_context = None
        if session.agent_context_data:
            agent_context = AgentContext.model_validate(session.agent_context_data)

        # Run pipeline. The runner opens its own SHORT sessions per DB operation,
        # so no connection is held while the LLM works (do NOT wrap it in a
        # request-long transaction here).
        runner = PipelineRunner(self.session_factory, cache=self.cache)
        result = await runner.run(
            message=transcript,
            client_id=session.client_id,
            conversation_id=session.conversation_id,
            agent_context=agent_context,
        )

        # Cognition marked the call terminal → learn in the background (bounded).
        if result.qualification_terminal:
            from prosales.services.live_learning import spawn_live_learning

            spawn_live_learning(session.conversation_id)

        # Stream response as sentences
        sentences = split_into_sentences(result.voice_text)
        for i, sentence in enumerate(sentences):
            is_last = i == len(sentences) - 1
            yield VoiceChunk(content=sentence, end_of_turn=is_last)

        await self.session_manager.increment_turn(session_id)

    async def on_user_silence(
        self, session_id: str
    ) -> AsyncGenerator[VoiceChunk, None]:
        """Handle user silence with synthetic message."""
        async for chunk in self.on_user_speech(
            session_id, "[silencio del cliente]"
        ):
            yield chunk

    async def on_session_end(
        self, session_id: str, reason: str = "normal"
    ) -> None:
        """Finalize voice call: update DB, extract episode, notify CRM."""
        if not session_id:
            return

        session = await self.session_manager.get(session_id)
        if not session:
            return

        now = datetime.utcnow()
        duration = int((now - session.started_at).total_seconds())

        # Update DB record
        try:
            async with self.session_factory() as db_session:
                async with db_session.begin():
                    from sqlalchemy import update

                    from prosales.infrastructure.database.models_voice import (
                        VoiceCallModel,
                    )

                    await db_session.execute(
                        update(VoiceCallModel)
                        .where(VoiceCallModel.session_id == session_id)
                        .values(
                            status="completed",
                            ended_at=now,
                            duration_seconds=duration,
                            turn_count=session.turn_count,
                            disconnect_reason=reason,
                        )
                    )

                    # Trigger episode extraction
                    try:
                        from prosales.engines.episodic.engine import (
                            EpisodicMemoryEngine,
                        )
                        from prosales.engines.episodic.extractor import (
                            EpisodeExtractor,
                        )
                        from prosales.infrastructure.database.repositories.episodic import (
                            SQLEpisodicRepository,
                        )
                        from prosales.infrastructure.database.repositories.event import (
                            SQLEventRepository,
                        )

                        event_repo = SQLEventRepository(db_session)
                        episodic_repo = SQLEpisodicRepository(db_session)
                        extractor = EpisodeExtractor(event_repo)
                        episodic_engine = EpisodicMemoryEngine(
                            extractor=extractor, episodic_repo=episodic_repo
                        )
                        await episodic_engine.close_conversation(
                            session.conversation_id
                        )
                    except Exception as e:
                        logger.warning(
                            "Episode extraction failed for %s: %s",
                            session_id,
                            e,
                        )

                    # Mark the conversation closed (voice previously left it active).
                    from prosales.infrastructure.database.models import ConversationModel

                    await db_session.execute(
                        update(ConversationModel)
                        .where(ConversationModel.id == session.conversation_id)
                        .values(is_active=False, updated_at=now)
                    )
        except Exception as e:
            logger.error("Failed to finalize voice call %s: %s", session_id, e)

        # A finished call is a definitive end → learn from it (idempotent, bounded).
        from prosales.services.live_learning import spawn_live_learning

        spawn_live_learning(session.conversation_id)

        # Notify CRM
        if self.notifier:
            await self.notifier.notify_call_ended(
                CallEndedEvent(
                    session_id=session_id,
                    conversation_id=session.conversation_id,
                    client_id=session.client_id,
                    organization_id=session.organization_id,
                    duration_seconds=duration,
                    turn_count=session.turn_count,
                    disconnect_reason=reason,
                    ended_at=now,
                )
            )

        # Clean up Redis
        await self.session_manager.delete(session_id)
        logger.info(
            "Voice session ended: %s (duration=%ds, turns=%d)",
            session_id,
            duration,
            session.turn_count,
        )
