"""CRM tool contract for the in-turn Action Layer (Modelo A).

ProSales' Response engine runs a tool-use loop (see pipeline/nodes.py's
llm_call): the LLM may request a tool, which we execute by calling the CRM's
own ``POST /api/v1/ai/tools/execute`` — the exact same contract any other
automation target (n8n) uses, so every action lands in the CRM's audit/event
trail. Nothing here is a special-cased direct write.

Two rules keep this safe and simple:
  - ``contact_id`` / ``conversation_id`` are SERVER-INJECTED from the request,
    never taken from the model — it can't act on another contact/conversation,
    and it isn't burdened with passing IDs it shouldn't have to know.
  - ``send_message`` is deliberately NOT exposed as a tool: the reply is the
    pipeline's final output, delivered once by crm_inbound's callback, not a
    thing the model chooses to call mid-turn.
"""

import logging
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)

# Each spec's ``parameters`` is the JSON schema shown to the LLM (without the
# server-injected fields). ``inject`` maps an input field name -> the executor
# attribute whose value is merged in at execution time.
TOOL_SPECS: list[dict] = [
    {
        "name": "get_available_slots",
        "description": (
            "List free appointment slots in a time range. Returns slots as "
            "UTC ISO timestamps — present them to the customer in the "
            "organization's local timezone (given in the context block)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "from": {"type": "string", "description": "Range start, ISO 8601 (UTC)."},
                "to": {"type": "string", "description": "Range end, ISO 8601 (UTC)."},
                "duration_minutes": {"type": "integer", "description": "Desired slot length."},
                "calendar_id": {"type": "string", "description": "Optional specific calendar."},
            },
            "required": ["from", "to"],
        },
        "inject": {},
    },
    {
        "name": "create_appointment",
        "description": (
            "Book an appointment for this contact once they've agreed on a "
            "specific slot. If the CRM responds that the calendar charges a "
            "fee, call create_payment_link instead — payment comes first."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "What the appointment is for."},
                "starts_at": {"type": "string", "description": "Start time, ISO 8601 (UTC)."},
                "duration_minutes": {"type": "integer"},
                "calendar_id": {"type": "string"},
                "description": {"type": "string"},
                "location": {"type": "string"},
            },
            "required": ["title", "starts_at", "duration_minutes"],
        },
        "inject": {"contact_id": "contact_id", "conversation_id": "conversation_id"},
    },
    {
        "name": "create_payment_link",
        "description": (
            "Create a payment/checkout link for a paid service. Use when "
            "create_appointment reports the calendar requires payment, or when "
            "the customer wants to pay for a listed service. Share the returned "
            "link; the appointment is created automatically after payment."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "service_id": {"type": "string", "description": "Id from list_payment_services."},
                "booking": {
                    "type": "object",
                    "description": "Slot to reserve once paid.",
                    "properties": {
                        "calendar_id": {"type": "string"},
                        "title": {"type": "string"},
                        "starts_at": {"type": "string"},
                        "duration_minutes": {"type": "integer"},
                        "timezone": {"type": "string"},
                    },
                },
            },
            "required": ["service_id"],
        },
        "inject": {"contact_id": "contact_id", "conversation_id": "conversation_id"},
    },
    {
        "name": "list_payment_services",
        "description": "List the organization's paid services (name, price, currency).",
        "parameters": {"type": "object", "properties": {}},
        "inject": {},
    },
    {
        "name": "get_contact_appointments",
        "description": "List this contact's recent/upcoming appointments.",
        "parameters": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Max to return (default 5)."}},
        },
        "inject": {"contact_id": "contact_id"},
    },
    {
        "name": "update_contact",
        "description": (
            "Correct or enrich this contact's own details (name, email, phone) "
            "when the customer provides them. Do NOT use this to set lead stage "
            "or qualification — that's handled automatically."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "first_name": {"type": "string"},
                "last_name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
            },
        },
        "inject": {"contact_id": "contact_id"},
    },
]

_SPECS_BY_NAME = {s["name"]: s for s in TOOL_SPECS}

# ProSales temperature → the CRM's urgency_level tier (it scores lead_score from
# urgency_level via URGENCY_SCORE). Lets a hotter contact raise its score — and
# thus move its card — automatically on the CRM side.
_TEMPERATURE_TO_URGENCY = {"hot": "high", "warm": "medium", "cold": "low"}


def qualification_to_contact_update(qual: dict) -> dict:
    """Map ProSales' funnel-agnostic qualification (ContactQualification.to_public)
    to the CRM's update_contact input.

    ``custom_fields`` uses the exact keys the CRM's lead_score recompute reads
    (urgency_level, is_decision_maker, has_budget, timeline, service_needed) so
    the contact's card moves through the funnel on the CRM's own rules.
    ``ai_insights`` carries the richer cognitive read (shallow-merged by the CRM).
    product_interest is sticky upstream, so it's safe to forward every turn.
    """
    bant = qual.get("bant") or {}
    facts = qual.get("facts") or {}
    temperature = qual.get("temperature", "cold")

    custom_fields: dict = {
        "urgency_level": _TEMPERATURE_TO_URGENCY.get(temperature, "low"),
        "is_decision_maker": bool(bant.get("authority")),
        "has_budget": bool(bant.get("budget")),
    }
    timeline = facts.get("timeline")
    if timeline or bant.get("timeline"):
        custom_fields["timeline"] = timeline or "yes"
    product_interest = facts.get("product_interest")
    if product_interest:
        custom_fields["service_needed"] = product_interest
        custom_fields["product_interest"] = product_interest

    update: dict = {
        "custom_fields": custom_fields,
        "ai_insights": {
            "temperature": temperature,
            "status": qual.get("status"),
            "readiness": qual.get("readiness"),
            "bant": bant,
            "signals": qual.get("signals"),
            "suggested_transition": qual.get("suggested_transition"),
        },
    }
    readiness = qual.get("readiness")
    if isinstance(readiness, (int, float)):
        update["lead_score"] = int(round(readiness * 100))
    return update


def tool_schemas() -> list[dict]:
    """Provider-neutral tool definitions for the LLM (no injected fields)."""
    return [
        {"name": s["name"], "description": s["description"], "parameters": s["parameters"]}
        for s in TOOL_SPECS
    ]


class CRMToolExecutor:
    """Runs an LLM-requested tool against the CRM's /ai/tools/execute endpoint.

    Scoped to a single org + conversation + contact; holds the CRM credentials
    (per-org, from OrganizationModel) so the pipeline never sees them directly.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        agent_id: str,
        conversation_id: UUID,
        contact_id: str | None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.agent_id = agent_id
        self.conversation_id = str(conversation_id)
        self.contact_id = contact_id

    @staticmethod
    def tool_schemas() -> list[dict]:
        return tool_schemas()

    def _inject(self, name: str, args: dict) -> dict:
        spec = _SPECS_BY_NAME.get(name, {})
        merged = dict(args)
        for field, attr in spec.get("inject", {}).items():
            value = getattr(self, attr, None)
            if value is not None:
                merged[field] = value
        return merged

    async def execute(self, name: str, args: dict) -> dict:
        """Execute one tool. Returns the CRM's JSON result, or an ``{"error":
        ...}`` dict the loop can feed back to the model instead of crashing the
        whole turn (a failed tool should let the agent recover, not 500)."""
        if name not in _SPECS_BY_NAME:
            return {"error": f"unknown tool: {name}"}

        payload = {
            "agent_id": self.agent_id,
            "tool": name,
            "input": self._inject(name, args),
            "conversation_id": self.conversation_id,
        }
        url = f"{self.base_url}/api/v1/ai/tools/execute"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload, headers={"x-api-key": self.api_key})
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500] if e.response is not None else ""
            logger.warning("CRM tool '%s' failed: %s %s", name, e, body)
            return {"error": f"tool '{name}' failed", "detail": body}
        except Exception as e:  # noqa: BLE001 — a tool error must not kill the turn
            logger.warning("CRM tool '%s' error: %s", name, e)
            return {"error": f"tool '{name}' error: {e}"}
