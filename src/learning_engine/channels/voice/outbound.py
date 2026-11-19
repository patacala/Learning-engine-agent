"""Outbound call service — initiates calls via Retell API."""

import logging

import httpx

from learning_engine.config import settings

logger = logging.getLogger(__name__)

RETELL_CREATE_CALL_URL = "https://api.retellai.com/v2/create-phone-call"
RETELL_LIST_NUMBERS_URL = "https://api.retellai.com/list-phone-numbers"


class OutboundCallError(Exception):
    """The call cannot be placed. The route turns this into HTTP 400."""


class OutboundCallService:
    """Initiates outbound calls via Retell. Metadata only carries IDs, never secrets."""

    async def initiate(
        self,
        to_number: str,
        organization_id: str,
        agent_version_id: str,
        from_number: str | None = None,
        retell_agent_id: str | None = None,
        api_key: str | None = None,
        extra_metadata: dict | None = None,
    ) -> dict:
        """POST to Retell to create an outbound phone call.

        ``api_key`` is the org's Retell key, passed per-call by the CRM and never
        stored. Falls back to the global key only when absent.

        ``from_number`` is optional. The CRM keeps the agent id, and the phone
        number lives on that agent in Retell. When no number is given, this
        lists the account's numbers and uses the one bound to ``retell_agent_id``.

        Returns the Retell response dict (call_id, status, etc).
        """
        retell_key = api_key or settings.retell_api_key
        if not retell_key:
            raise OutboundCallError("Voice provider not configured")

        caller = from_number if _looks_like_phone(from_number) else None
        if caller is None:
            if not retell_agent_id:
                raise OutboundCallError("Retell agent id is required to place the call")
            caller = await self._from_number_for_agent(retell_key, retell_agent_id)
            if caller is None:
                raise OutboundCallError(
                    f"No Retell phone number is bound to agent {retell_agent_id}"
                )

        metadata = {
            "organization_id": organization_id,
            "agent_version_id": agent_version_id,
            "direction": "outbound",
            **(extra_metadata or {}),
        }

        payload = {
            "to_number": to_number,
            "from_number": caller,
            "metadata": metadata,
        }
        if retell_agent_id:
            payload["override_agent_id"] = retell_agent_id

        async with httpx.AsyncClient() as client:
            response = await client.post(
                RETELL_CREATE_CALL_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {retell_key}",
                    "Content-Type": "application/json",
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

        logger.info("Outbound call initiated: %s → %s", caller, to_number)
        return data

    async def _from_number_for_agent(self, api_key: str, agent_id: str) -> str | None:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                RETELL_LIST_NUMBERS_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0,
            )
            response.raise_for_status()
            numbers = response.json()
        if not isinstance(numbers, list):
            raise OutboundCallError("Retell list-phone-numbers returned an unexpected payload")
        return from_number_for_agent(numbers, agent_id)


def from_number_for_agent(numbers: list[dict], agent_id: str) -> str | None:
    """Pick the Retell number that should dial for this agent.

    Prefer a number whose outbound agents include it. Fall back to a number
    that only lists the agent as inbound, which is how a single-agent account
    is usually bound.
    """
    outbound = _first_number(numbers, agent_id, "outbound_agents", "outbound_agent_id")
    if outbound:
        return outbound
    return _first_number(numbers, agent_id, "inbound_agents", "inbound_agent_id")


def _first_number(
    numbers: list[dict],
    agent_id: str,
    list_key: str,
    legacy_key: str,
) -> str | None:
    for number in numbers:
        agents = number.get(list_key) or []
        listed = (
            isinstance(agents, list)
            and any(isinstance(item, dict) and item.get("agent_id") == agent_id for item in agents)
        )
        if listed or number.get(legacy_key) == agent_id:
            phone = number.get("phone_number")
            if isinstance(phone, str) and phone:
                return phone
    return None


def _looks_like_phone(value: str | None) -> bool:
    if not value or value.startswith("agent_"):
        return False
    digits = "".join(char for char in value if char.isdigit())
    return len(digits) >= 8
