"""WebSocket endpoint for voice providers — generic + Retell shortcut."""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from prosales.channels.voice.adapter import VoiceAdapter
from prosales.channels.voice.notifier import CRMNotifier
from prosales.channels.voice.providers.base import VoiceProvider
from prosales.channels.voice.providers.retell import RetellProvider
from prosales.channels.voice.session import VoiceSessionManager
from prosales.config import settings
from prosales.api.v1.dependencies import get_redis_cache
from prosales.infrastructure.database.connection import async_session_factory

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
                    # talks, so emit the opening turn (response_id 0) on connect.
                    async for chunk in adapter.on_call_opening(session_id):
                        msg = await provider.format_response(chunk, 0)
                        await websocket.send_json(msg)
                case "user_speech":
                    async for chunk in adapter.on_user_speech(
                        session_id, event.transcript or ""
                    ):
                        msg = await provider.format_response(
                            chunk, response_id
                        )
                        await websocket.send_json(msg)
                case "user_silence":
                    async for chunk in adapter.on_user_silence(session_id):
                        msg = await provider.format_response(
                            chunk, response_id
                        )
                        await websocket.send_json(msg)
                case "session_end":
                    await adapter.on_session_end(session_id)
                    session_started = False
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("Voice WebSocket error: %s", e)
    finally:
        if session_started:
            await adapter.on_session_end(session_id, "disconnect")


@router.websocket("/llm-websocket/{call_id}")
async def retell_websocket(websocket: WebSocket, call_id: str):
    """Retell-compatible endpoint — delegates to generic handler."""
    await voice_websocket(websocket, "retell", call_id)
