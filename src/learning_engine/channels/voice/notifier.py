"""CRM notifier — fire-and-forget HTTP notifications for voice call events."""

import logging

import httpx

from learning_engine.channels.voice.events import CallEndedEvent, CallStartedEvent

logger = logging.getLogger(__name__)


class CRMNotifier:
    """Fire-and-forget HTTP notifications to CRM."""

    def __init__(self, webhook_url: str | None = None):
        self.webhook_url = webhook_url

    async def notify_call_started(self, event: CallStartedEvent) -> None:
        """POST to CRM webhook — async, no retry, log errors."""
        await self._send("call_started", event.model_dump(mode="json"))

    async def notify_call_ended(self, event: CallEndedEvent) -> None:
        """POST to CRM webhook with call summary."""
        await self._send("call_ended", event.model_dump(mode="json"))

    async def _send(self, event_type: str, payload: dict) -> None:
        if not self.webhook_url:
            return
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    self.webhook_url,
                    json={"event_type": event_type, "data": payload},
                )
        except Exception as e:
            logger.warning("CRM notification failed (%s): %s", event_type, e)
