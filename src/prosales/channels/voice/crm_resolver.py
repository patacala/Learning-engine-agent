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


async def resolve_org_for_call(agent_id: str | None, number: str | None = None) -> dict | None:
    """Return {"organization_id", "agent_version_id"} for the org that owns this
    inbound call, or None. The Retell agent id is the primary key (the same
    agent is configured on the org's voice channel); the dialed number is sent
    as a fallback. Best-effort: never raises, so a CRM outage degrades to an
    unresolved (default) agent instead of dropping the call."""
    if not (agent_id or number) or not settings.crm_base_url or not settings.internal_api_token:
        return None
    url = f"{settings.crm_base_url.rstrip('/')}/api/v1/integrations/voice/resolve"
    params = {}
    if agent_id:
        params["agent"] = agent_id
    if number:
        params["number"] = number
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                url,
                params=params,
                headers={"x-internal-token": settings.internal_api_token},
            )
            resp.raise_for_status()
            payload = resp.json()
    except Exception as e:  # noqa: BLE001 — resolution is best-effort
        logger.warning("CRM voice resolve failed (agent=%s number=%s): %s", agent_id, number, e)
        return None

    # The CRM wraps every response in {data: {...}, timestamp}; the ids live
    # under "data". Fall back to the raw payload if it's ever returned flat.
    inner = payload.get("data") if isinstance(payload, dict) else None
    data = inner if isinstance(inner, dict) else (payload if isinstance(payload, dict) else {})

    if data.get("organization_id") and data.get("agent_version_id"):
        return {
            "organization_id": data["organization_id"],
            "agent_version_id": data["agent_version_id"],
        }
    # 200 but no usable ids → the call degrades to the generic (default) agent.
    # Log the keys the CRM actually returned so this silent failure is
    # diagnosable (the agent likely isn't mapped to an agent_version in the CRM).
    logger.warning(
        "CRM voice resolve returned no org/agent_version (agent=%s number=%s): keys=%s",
        agent_id,
        number,
        sorted(data.keys()) if isinstance(data, dict) else type(data).__name__,
    )
    return None
