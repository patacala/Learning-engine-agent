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
    {
        "name": "opt_out_contact",
        "description": (
            "Opt this contact out of ALL automated communications. Cancels any "
            "active follow-up sequences and tags the contact so no agent "
            "messages them again. Call this ONLY when the customer explicitly "
            "asks to stop receiving messages (e.g. 'no me escribas más', "
            "'stop', 'unsubscribe', 'cancelar') — never on vague disinterest. "
            "After calling it, acknowledge briefly and do not continue selling."
        ),
        "parameters": {"type": "object", "properties": {}},
        "inject": {"contact_id": "contact_id"},
        # Always exposed to the model, independent of the org's appointment
        # capability — opting out is the user's right, not a sales feature.
        "always_available": True,
    },
    {
        "name": "send_email",
        "description": (
            "Email this contact the information they asked for (e.g. a quote, "
            "vehicle details, or next steps). Compose a clear subject and body. "
            "Use only when the customer agrees to or asks for an email. If the "
            "result contains an 'error', do NOT claim the email was sent — tell "
            "the customer you couldn't send it and offer an alternative."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Email subject line."},
                "body": {
                    "type": "string",
                    "description": "Email body; include the requested information.",
                },
            },
            "required": ["subject", "body"],
        },
        "inject": {"contact_id": "contact_id", "conversation_id": "conversation_id"},
    },
    {
        "name": "send_sms",
        "description": (
            "Text this contact a short SMS with information they asked for. Use "
            "ONLY when the customer explicitly asks to receive something by SMS. "
            "Do NOT use it to confirm an appointment — that confirmation SMS is "
            "sent automatically when the booking is created. If the result "
            "contains an 'error', do NOT claim the SMS was sent."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "SMS text to send."},
            },
            "required": ["message"],
        },
        "inject": {"contact_id": "contact_id", "conversation_id": "conversation_id"},
    },
]

_SPECS_BY_NAME = {s["name"]: s for s in TOOL_SPECS}

# Communication tools can only reach a contact through a channel we already have
# on file: email for send_email, phone for send_sms. Maps tool name -> the
# known_fields key that must be present before it can run.
_CONTACT_CHANNEL_REQS = {"send_email": "email", "send_sms": "phone"}

# Native CRM contact fields (everything else lands in custom_fields).
_NATIVE_CONTACT_FIELDS = {"first_name", "last_name", "full_name", "email", "phone"}

# Cognitive signal → human-readable tag the CRM can filter/segment on.
_SIGNAL_TAGS = {
    "positive_interest": "interesado",
    "appointment_requested": "pidio-cita",
    "ready_to_buy": "listo-para-comprar",
    "budget_confirmed": "presupuesto-confirmado",
    "decision_maker": "decision-maker",
    "asked_for_quote": "pidio-cotizacion",
    "price_objection": "objecion-precio",
    "comparing_competitors": "compara-competencia",
    "needs_more_info": "necesita-info",
    "wants_followup": "seguimiento",
    "not_interested": "no-interesado",
}

_URGENCY_HIGH = ("asap", "ya", "hoy", "today", "now", "ahora", "esta semana",
                 "this week", "urgente", "inmediato", "immediately")
_URGENCY_MEDIUM = ("este mes", "this month", "pronto", "soon", "próxima semana",
                   "next week", "quincena", "15 días", "dos semanas")


def _purchase_urgency(timeline: str | None) -> str:
    """Classify the PURCHASE timeline (when they plan to buy — not the
    appointment date) into the CRM's urgency_level tier. Unknown → low, so an
    unqualified lead doesn't get an inflated score."""
    if not timeline:
        return "low"
    t = str(timeline).lower()
    if any(k in t for k in _URGENCY_HIGH):
        return "high"
    if any(k in t for k in _URGENCY_MEDIUM):
        return "medium"
    return "low"


def _timeline_value(facts: dict, schema=None) -> str | None:
    """Resolve the 'when they plan to buy' value from the schema's timeline-tagged
    field(s), falling back to the legacy fixed keys when no schema/field is set."""
    if schema is not None:
        for f in schema.fields_for_bant("timeline"):
            value = facts.get(f.key)
            if value:
                return value
    return facts.get("purchase_timeline") or facts.get("timeline")


def _derive_tags(qual: dict) -> list[str]:
    tags: list[str] = []
    temperature = qual.get("temperature")
    if temperature:
        tags.append(temperature)  # hot | warm | cold
    for sig in qual.get("signals") or []:
        if sig in _SIGNAL_TAGS:
            tags.append(_SIGNAL_TAGS[sig])
    return sorted(set(tags))


def qualification_to_contact_update(
    qual: dict,
    schema=None,
    analysis_summary: dict | None = None,
    existing_tags: list[str] | None = None,
) -> dict:
    """Map ProSales' qualification (ContactQualification.to_public) to the CRM's
    update_contact input.

    - When a ``schema`` (QualificationSchema) is given, each captured fact is
      routed to its configured CRM target: native contact fields (name/email/
      phone) go top-level, the rest into ``custom_fields``. This keeps
      ``service_needed`` and ``product_interest`` as DISTINCT fields.
    - ``urgency_level`` is derived from the PURCHASE timeline, not temperature,
      so the CRM's lead_score is driven by real BANT + buying urgency (we do NOT
      push an inflated lead_score; the CRM recomputes it from these custom_fields).
    - ``ai_insights`` carries summary/intent/sentiment (fills the CRM's "RESUMEN
      IA" and improves its next-action), shallow-merged by the CRM.
    - ``tags`` unions derived segment tags with the contact's existing tags so
      human-added tags aren't wiped (the CRM replaces the tags array on update).
    """
    bant = qual.get("bant") or {}
    facts = qual.get("facts") or {}
    analysis_summary = analysis_summary or {}

    update: dict = {}
    custom_fields: dict = {}

    fields = schema.enabled_fields() if schema is not None else None
    if fields:
        for f in fields:
            value = facts.get(f.key)
            if value in (None, ""):
                continue
            target = f.target()
            if target == "full_name":
                parts = str(value).split(" ", 1)
                update["first_name"] = parts[0]
                if len(parts) > 1:
                    update["last_name"] = parts[1]
            elif target in _NATIVE_CONTACT_FIELDS:
                update[target] = value
            else:
                custom_fields[target] = value
    else:
        # Legacy (no schema): keep product/service and timeline from facts.
        if facts.get("product_interest"):
            custom_fields["product_interest"] = facts["product_interest"]
        if facts.get("service_needed"):
            custom_fields["service_needed"] = facts["service_needed"]

    # BANT booleans the CRM scores on (derived, not raw facts).
    custom_fields["is_decision_maker"] = bool(bant.get("authority"))
    custom_fields["has_budget"] = bool(bant.get("budget"))
    # urgency_level from the purchase timeline (facts), NOT temperature.
    custom_fields["urgency_level"] = _purchase_urgency(_timeline_value(facts, schema))

    update["custom_fields"] = custom_fields
    update["ai_insights"] = {
        "summary": _build_summary(qual, facts),
        "intent": analysis_summary.get("intent"),
        "sentiment": analysis_summary.get("sentiment"),
        "temperature": qual.get("temperature"),
        "status": qual.get("status"),
        "readiness": qual.get("readiness"),
        "bant": bant,
        "signals": qual.get("signals"),
        "suggested_transition": qual.get("suggested_transition"),
    }

    derived = _derive_tags(qual)
    update["tags"] = sorted(set(derived) | set(existing_tags or []))
    return update


def _build_summary(qual: dict, facts: dict) -> str:
    """A compact, deterministic recap for the CRM's "RESUMEN IA" — built from
    captured facts (free, multilingual since it echoes the captured values)."""
    bits: list[str] = []
    if facts.get("product_interest"):
        bits.append(f"Interés: {facts['product_interest']}")
    if facts.get("service_needed"):
        bits.append(str(facts["service_needed"]))
    if facts.get("purchase_timeline"):
        bits.append(f"compra: {facts['purchase_timeline']}")
    if facts.get("budget") or facts.get("budget_amount"):
        bits.append(f"presupuesto: {facts.get('budget_amount') or facts.get('budget')}")
    temp = qual.get("temperature")
    status = qual.get("status")
    if temp or status:
        bits.append(f"({temp or ''}{'/' + status if status else ''})".strip("/ "))
    return " · ".join(b for b in bits if b)


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
        required_fields: list[str] | None = None,
        known_fields: set[str] | None = None,
        actions_enabled: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.agent_id = agent_id
        self.conversation_id = str(conversation_id)
        self.contact_id = contact_id
        # Scheduling gate: field keys that must be known before create_appointment,
        # and the set already satisfied (seeded from the CRM contact + grown as the
        # agent saves data via update_contact in this turn).
        self.required_fields = list(required_fields or [])
        self.known_fields = set(known_fields or [])
        # Gates the appointment/payment tools behind the org's "appointment"
        # capability. Tools marked always_available (opt_out_contact) ignore
        # this — opting out isn't a sales feature the org can turn off.
        self.actions_enabled = actions_enabled

    def tool_schemas(self) -> list[dict]:
        specs = TOOL_SPECS if self.actions_enabled else [
            s for s in TOOL_SPECS if s.get("always_available")
        ]
        return [
            {"name": s["name"], "description": s["description"], "parameters": s["parameters"]}
            for s in specs
        ]

    def _inject(self, name: str, args: dict) -> dict:
        spec = _SPECS_BY_NAME.get(name, {})
        merged = dict(args)
        for field, attr in spec.get("inject", {}).items():
            value = getattr(self, attr, None)
            if value is not None:
                merged[field] = value
        return merged

    def _missing_required(self) -> list[str]:
        return [f for f in self.required_fields if f not in self.known_fields]

    async def execute(self, name: str, args: dict) -> dict:
        """Execute one tool. Returns the CRM's JSON result, or an ``{"error":
        ...}`` dict the loop can feed back to the model instead of crashing the
        whole turn (a failed tool should let the agent recover, not 500)."""
        spec = _SPECS_BY_NAME.get(name)
        if spec is None:
            return {"error": f"unknown tool: {name}"}
        if not self.actions_enabled and not spec.get("always_available"):
            return {"error": f"tool '{name}' not available for this agent"}

        # Scheduling gate: don't book until the required contact data is saved.
        if name == "create_appointment":
            missing = self._missing_required()
            if missing:
                return {
                    "error": "missing_required_fields",
                    "fields": missing,
                    "message": (
                        "Cannot book yet. First collect and save these fields "
                        f"(via update_contact): {', '.join(missing)}."
                    ),
                }

        # Communication gate: can't email/text a contact whose email/phone we
        # don't have yet. Return a recoverable error so the agent collects it
        # (via update_contact) and retries, instead of calling the CRM blindly.
        channel_field = _CONTACT_CHANNEL_REQS.get(name)
        if channel_field and channel_field not in self.known_fields:
            return {
                "error": "missing_required_fields",
                "fields": [channel_field],
                "message": (
                    f"Cannot {name.replace('_', ' ')} yet: no {channel_field} on "
                    f"file. First collect and save it via update_contact."
                ),
            }

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
                result = resp.json()
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500] if e.response is not None else ""
            logger.warning("CRM tool '%s' failed: %s %s", name, e, body)
            return {"error": f"tool '{name}' failed", "detail": body}
        except Exception as e:  # noqa: BLE001 — a tool error must not kill the turn
            logger.warning("CRM tool '%s' error: %s", name, e)
            return {"error": f"tool '{name}' error: {e}"}

        # When the agent saves contact data, mark those fields satisfied so the
        # scheduling gate opens within the same turn.
        if name == "update_contact":
            if args.get("email"):
                self.known_fields.add("email")
            if args.get("phone"):
                self.known_fields.add("phone")
            if args.get("first_name") or args.get("last_name"):
                self.known_fields.add("full_name")
        return result
