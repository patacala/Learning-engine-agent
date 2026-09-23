"""Outbound call service — initiates calls via Retell API."""

import logging

import httpx

from prosales.config import settings

logger = logging.getLogger(__name__)

RETELL_CREATE_CALL_URL = "https://api.retellai.com/v2/create-phone-call"


class OutboundCallService:
    """Initiates outbound calls via Retell. Metadata only carries IDs, never secrets."""

    async def initiate(
        self,
        to_number: str,
        from_number: str,
        organization_id: str,
        agent_version_id: str,
        retell_agent_id: str | None = None,
        extra_metadata: dict | None = None,
    ) -> dict:
        """POST to Retell to create an outbound phone call.

        Returns the Retell response dict (call_id, status, etc).
        """
        metadata = {
            "organization_id": organization_id,
            "agent_version_id": agent_version_id,
            "direction": "outbound",
            **(extra_metadata or {}),
        }

        payload = {
            "to_number": to_number,
            "from_number": from_number,
            "metadata": metadata,
        }
        if retell_agent_id:
            payload["agent_id"] = retell_agent_id

        async with httpx.AsyncClient() as client:
            response = await client.post(
                RETELL_CREATE_CALL_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.retell_api_key}",
                    "Content-Type": "application/json",
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

        logger.info("Outbound call initiated: %s → %s", from_number, to_number)
        return data
