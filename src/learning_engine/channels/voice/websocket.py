"""WebSocket endpoint for voice providers — generic + Retell shortcut."""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from learning_engine.channels.voice.adapter import VoiceAdapter
from learning_engine.channels.voice.notifier import CRMNotifier
from learning_engine.channels.voice.providers.base import VoiceProvider
from learning_engine.channels.voice.providers.retell import RetellProvider
from learning_engine.channels.voice.session import VoiceSessionManager
from learning_engine.config import settings
from learning_engine.api.v1.dependencies import get_redis_cache
from learning_engine.infrastructure.database.connection import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voice"])


def get_voice_provider(provider_type: str) -> VoiceProvider:
    """Factory for voice providers."""
    match provider_type:
        case "retell":
            return RetellProvider()
        case _:
            raise ValueError(f"Unknown voice provider: {provider_type}")


def _build_adapter(provider: VoiceProvider) -> VoiceAdapter:
    """Build a VoiceAdapter with all dependencies."""
    cache = get_redis_cache()
    session_manager = VoiceSessionManager(cache)
    notifier = CRMNotifier(
        webhook_url=settings.crm_webhook_url or None
    )
    return VoiceAdapter(
        provider=provider,
        session_manager=session_manager,
        session_factory=async_session_factory,
        cache=cache,
        notifier=notifier,
    )


@router.websocket("/voice/ws/{provider_type}/{session_id}")
async def voice_websocket(
    websocket: WebSocket, provider_type: str, session_id: str
):
    """Generic voice WebSocket — provider resolved by path."""
    await websocket.accept()

    try:
        provider = get_voice_provider(provider_type)
    except ValueError as e:
        await websocket.close(code=1008, reason=str(e))
        return

    adapter = _build_adapter(provider)
    session_started = False

    try:
        # Send initial config
        config = await provider.format_config()
        if config:
            await websocket.send_json(config)

        async for raw_text in websocket.iter_text():
            data = json.loads(raw_text)

            # Handle keepalive
            keepalive = await provider.format_keepalive(data)
            if keepalive:
                await websocket.send_json(keepalive)
                continue

            # Parse to internal event
            event = await provider.parse_event(data)
            if not event:
                continue

            response_id = data.get("response_id")

            match event.event_type:
                case "session_start":
                    await adapter.on_session_start(session_id, event.metadata)
                    session_started = True
                    # Agent speaks first: providers stay silent until the caller
                    # talks, so dispatch the opening turn (response_id 0) as a
                    # cancellable background task like any other turn — a
                    # caller who starts talking immediately correctly
                    # interrupts it instead of blocking on it.
                    adapter.dispatch_turn(
                        session_id,
                        adapter.on_call_opening(session_id),
                        websocket,
                        0,
                        provider.format_response,
                    )
                case "user_speech":
                    # Dispatched as a background task, NOT awaited here: per
                    # Retell's protocol a new response_required supersedes
                    # whatever is still generating, so this loop must keep
                    # reading the next WebSocket message instead of blocking
                    # on the previous turn's full generation + send.
                    adapter.dispatch_turn(
                        session_id,
                        adapter.on_user_speech(session_id, event.transcript or ""),
                        websocket,
                        response_id,
                        provider.format_response,
                    )
                case "user_silence":
                    adapter.dispatch_turn(
                        session_id,
                        adapter.on_user_silence(session_id),
                        websocket,
                        response_id,
                        provider.format_response,
                    )
                case "session_end":
                    adapter.cancel_active_turn(session_id)
                    await adapter.on_session_end(session_id)
                    session_started = False
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("Voice WebSocket error: %s", e)
    finally:
        if session_started:
            adapter.cancel_active_turn(session_id)
            await adapter.on_session_end(session_id, "disconnect")


@router.websocket("/llm-websocket/{call_id}")
async def retell_websocket(websocket: WebSocket, call_id: str):
    """Retell-compatible endpoint — delegates to generic handler."""
    await voice_websocket(websocket, "retell", call_id)
