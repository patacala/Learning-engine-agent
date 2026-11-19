"""Voice adapter — orchestrates a voice session, provider-agnostic."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from datetime import datetime
from uuid import uuid4, UUID

from sqlalchemy.ext.asyncio import AsyncSession

from learning_engine.channels.voice.events import CallEndedEvent, CallStartedEvent
from learning_engine.channels.voice.notifier import CRMNotifier
from learning_engine.channels.voice.providers.base import VoiceChunk, VoiceProvider
from learning_engine.channels.voice.session import VoiceSession, VoiceSessionManager
from learning_engine.channels.voice.streaming import split_into_sentences
from learning_engine.core.models.agent import AgentContext
from learning_engine.channels.voice.crm_resolver import resolve_org_for_call
from learning_engine.infrastructure.agent.resolver import (
    AgentContextResolver,
    resolve_by_ids,
    resolve_by_version_id,
)
from learning_engine.infrastructure.cache.redis import RedisCache
from learning_engine.infrastructure.database.models import ConversationModel
from learning_engine.infrastructure.database.repositories.client import SQLClientRepository
from learning_engine.infrastructure.database.repositories.conversation import SQLConversationRepository
from learning_engine.services.pipeline_runner import PipelineRunner

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
        # Per-connection turn concurrency state (in-memory, not Redis — this
        # tracks the live asyncio task for the current WebSocket, not
        # conversation state). See dispatch_turn/_run_turn.
        self._active_turn_id: int = 0
        self._active_task: asyncio.Task | None = None

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
                    # LearningEngine stores no agent/number->org mapping nor any Retell
                    # credential. Falls back to the legacy api_key path.
                    agent_id = metadata.get("agent_id") or nested_meta.get("agent_id")
                    dialed = (
                        metadata.get("to_number") or nested_meta.get("to_number")
                        or metadata.get("callee_number") or nested_meta.get("callee_number")
                    )
                    resolved = await resolve_org_for_call(agent_id, dialed)
                    if resolved:
                        from uuid import UUID
                        # Resolve by agent_version_id only: it is the one
                        # LearningEngine-owned id in the CRM's response. The CRM's
                        # organization_id is its own id space and never matches
                        # an OrganizationModel here, so we derive the tenant from
                        # the version instead.
                        agent_context = await resolve_by_version_id(
                            db_session,
                            UUID(str(resolved["agent_version_id"])),
                        )
                        if agent_context is None:
                            # The version doesn't resolve to a published version
                            # of an active org in LearningEngine — the call would
                            # silently degrade to the generic agent. Surface it.
                            logger.warning(
                                "Voice resolve: CRM returned agent_version=%s "
                                "but no published version / active org in LearningEngine "
                                "— call degrades to generic agent",
                                resolved["agent_version_id"],
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
                from learning_engine.infrastructure.database.models_voice import VoiceCallModel

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

    async def on_call_opening(
        self, session_id: str
    ) -> AsyncGenerator[VoiceChunk, None]:
        """Emit the agent's opening turn right after the call connects.

        Voice providers (Retell) stay silent until the caller speaks, so the
        agent would otherwise never greet first. We run the SAME cognitive
        pipeline with a synthetic greeting trigger — reusing the resolved agent
        identity and the warm_opening path, so the opening matches the agent
        (e.g. the dealership) instead of a generic assistant. The trigger is not
        persisted (store_user_message=False), so it never pollutes history."""
        session = await self.session_manager.get(session_id)
        if not session:
            logger.warning("No session found for opening %s", session_id)
            return

        # Best-effort opening: a malformed agent_context or a transient
        # pipeline/LLM/network failure on this first synthetic turn must NOT
        # abort the call. Degrade to no greeting and let the caller speak —
        # same except-and-continue contract as crm_resolver.
        try:
            agent_context = None
            if session.agent_context_data:
                agent_context = AgentContext.model_validate(session.agent_context_data)

            runner = PipelineRunner(self.session_factory, cache=self.cache)
            result = await runner.run(
                message="Hola",
                client_id=session.client_id,
                conversation_id=session.conversation_id,
                agent_context=agent_context,
                store_user_message=False,
            )
        except Exception as e:  # noqa: BLE001 — opening is best-effort
            logger.warning("Voice opening failed for %s: %s", session_id, e)
            return

        sentences = split_into_sentences(result.voice_text)
        for i, sentence in enumerate(sentences):
            is_last = i == len(sentences) - 1
            yield VoiceChunk(content=sentence, end_of_turn=is_last)

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
            from learning_engine.services.live_learning import spawn_live_learning

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

                    from learning_engine.infrastructure.database.models_voice import (
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
                        from learning_engine.engines.episodic.engine import (
                            EpisodicMemoryEngine,
                        )
                        from learning_engine.engines.episodic.extractor import (
                            EpisodeExtractor,
                        )
                        from learning_engine.infrastructure.database.repositories.episodic import (
                            SQLEpisodicRepository,
                        )
                        from learning_engine.infrastructure.database.repositories.event import (
                            SQLEventRepository,
                        )

                        event_repo = SQLEventRepository(db_session)
                        episodic_repo = SQLEpisodicRepository(db_session)
                        extractor = EpisodeExtractor(
                            event_repo, SQLConversationRepository(db_session)
                        )
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
                    from learning_engine.infrastructure.database.models import ConversationModel

                    await db_session.execute(
                        update(ConversationModel)
                        .where(ConversationModel.id == session.conversation_id)
                        .values(is_active=False, updated_at=now)
                    )
        except Exception as e:
            logger.error("Failed to finalize voice call %s: %s", session_id, e)

        # A finished call is a definitive end → learn from it (idempotent, bounded).
        from learning_engine.services.live_learning import spawn_live_learning

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

    def dispatch_turn(
        self,
        session_id: str,
        chunks: AsyncGenerator[VoiceChunk, None],
        websocket,
        response_id: int | None,
        format_response,
    ) -> None:
        """Start a turn as a cancellable background task instead of blocking
        the WebSocket read loop on it. Per Retell's protocol, a newer
        response_required/reminder_required supersedes whatever response is
        still being generated for a previous one — so any turn still in
        flight here is cancelled, and its remaining chunks must never reach
        Retell. update_only events never call this (see providers/retell.py),
        so they correctly never supersede a pending turn — Retell still
        expects a reply to it."""
        self._active_turn_id += 1
        turn_id = self._active_turn_id

        previous = self._active_task
        if previous is not None and not previous.done():
            logger.info(
                "Voice turn superseded: session=%s stale_turn=%s new_turn=%s new_response_id=%s",
                session_id,
                previous.get_name(),
                turn_id,
                response_id,
            )
            previous.cancel()

        self._active_task = asyncio.create_task(
            self._run_turn(
                turn_id, session_id, chunks, websocket, response_id, format_response
            ),
            name=str(turn_id),
        )

    def cancel_active_turn(self, session_id: str) -> None:
        """Cancel whatever turn is still generating — called on session_end
        and on WebSocket disconnect so no background task outlives the
        connection it was streaming chunks to."""
        if self._active_task is not None and not self._active_task.done():
            logger.info(
                "Voice turn cancelled (session end/disconnect): session=%s turn=%s",
                session_id,
                self._active_task.get_name(),
            )
            self._active_task.cancel()

    async def _run_turn(
        self,
        turn_id: int,
        session_id: str,
        chunks: AsyncGenerator[VoiceChunk, None],
        websocket,
        response_id: int | None,
        format_response,
    ) -> None:
        """Stream one turn's chunks, gated on every send by turn_id so a
        chunk produced by an already-superseded turn is dropped even if
        cancellation hasn't propagated yet (defense in depth alongside
        task.cancel()). Cancelling here stops the chunk producer itself —
        the `async for` suspends inside the adapter's on_user_speech/
        on_call_opening generator, so CancelledError raised at that await
        point ends the pipeline call too, not just this loop."""
        sent = 0
        try:
            async for chunk in chunks:
                if turn_id != self._active_turn_id:
                    logger.info(
                        "Voice turn dropped stale chunk: session=%s turn=%s response_id=%s sent=%s",
                        session_id,
                        turn_id,
                        response_id,
                        sent,
                    )
                    return
                msg = await format_response(chunk, response_id)
                await websocket.send_json(msg)
                sent += 1
            logger.info(
                "Voice turn completed: session=%s turn=%s response_id=%s chunks=%s",
                session_id,
                turn_id,
                response_id,
                sent,
            )
        except asyncio.CancelledError:
            logger.info(
                "Voice turn cancelled: session=%s turn=%s response_id=%s chunks_sent=%s",
                session_id,
                turn_id,
                response_id,
                sent,
            )
        except Exception as e:  # noqa: BLE001 — a dead socket must not crash the task
            logger.warning(
                "Voice turn send failed: session=%s turn=%s response_id=%s error=%s",
                session_id,
                turn_id,
                response_id,
                e,
            )
