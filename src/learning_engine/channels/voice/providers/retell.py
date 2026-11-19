"""Retell voice provider — translates Retell WebSocket protocol."""

from learning_engine.channels.voice.providers.base import VoiceChunk, VoiceEvent, VoiceProvider


class RetellProvider(VoiceProvider):
    """Translates Retell WebSocket protocol ↔ internal VoiceEvent/VoiceChunk."""

    PROVIDER_TYPE = "retell"

    async def parse_event(self, raw: dict) -> VoiceEvent | None:
        match raw.get("interaction_type"):
            case "call_details":
                return VoiceEvent(
                    event_type="session_start",
                    metadata=raw.get("call", {}),
                )
            case "response_required":
                transcript = raw.get("transcript", [])
                last_user = next(
                    (
                        u["content"]
                        for u in reversed(transcript)
                        if u["role"] == "user"
                    ),
                    "",
                )
                return VoiceEvent(
                    event_type="user_speech", transcript=last_user
                )
            case "reminder_required":
                return VoiceEvent(event_type="user_silence")
            case "ping_pong":
                return None
            case "update_only":
                # Per Retell's protocol, update_only never supersedes a
                # pending response/reminder_required — the server still owes
                # a reply to the earlier one. Returning None here (no event
                # dispatched) is what keeps adapter.dispatch_turn from ever
                # cancelling the in-flight turn on an update_only.
                return None
        return None

    async def format_response(
        self, chunk: VoiceChunk, response_id: int | None = None
    ) -> dict:
        return {
            "response_type": "response",
            "response_id": response_id or 0,
            "content": chunk.content,
            "content_complete": chunk.end_of_turn,
            "end_call": chunk.end_session,
        }

    async def format_config(self) -> dict | None:
        return {
            "response_type": "config",
            "config": {
                "auto_reconnect": True,
                "call_details": True,
            },
        }

    async def format_keepalive(self, raw: dict) -> dict | None:
        if raw.get("interaction_type") == "ping_pong":
            return {
                "response_type": "ping_pong",
                "timestamp": raw.get("timestamp"),
            }
        return None
