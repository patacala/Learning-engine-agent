"""Resolve which organization owns a dialed phone number by asking the CRM.

Inbound voice calls reach ProSales (Retell custom-LLM websocket) carrying only
the dialed number. The CRM is the source of truth for which org owns which
Retell number, so ProSales asks it here instead of storing that mapping (or any
Retell credential). Authenticated with internal_api_token as a shared
ProSales<->CRM secret.
"""

import logging

import httpx

from prosales.config import settings

logger = logging.getLogger(__name__)


async def resolve_org_by_phone(phone: str | None) -> dict | None:
    """Return {"organization_id", "agent_version_id"} for the org that owns
    ``phone``, or None. Best-effort: never raises, so a CRM outage degrades to
    an unresolved (default) agent instead of dropping the call."""
    if not phone or not settings.crm_base_url or not settings.internal_api_token:
        return None
    url = f"{settings.crm_base_url.rstrip('/')}/api/v1/integrations/voice/resolve"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                url,
                params={"number": phone},
                headers={"x-internal-token": settings.internal_api_token},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:  # noqa: BLE001 — resolution is best-effort
        logger.warning("CRM phone resolve failed for %s: %s", phone, e)
        return None

    if data.get("organization_id") and data.get("agent_version_id"):
        return {
            "organization_id": data["organization_id"],
            "agent_version_id": data["agent_version_id"],
        }
    return None
