"""Configurable lead-qualification schema (per agent version).

Defines WHICH fields the agent should capture from a lead, how they map to the
CRM, and which are required before booking an appointment. One schema drives
four places: extraction (ContactSignalDetector), the "ask for missing data"
prompt block, the scheduling gate, and the CRM push mapping.

The field set is industry-agnostic — the default below fits sales, but each
agent can override it (generated from the brief and editable in the CRM).
"""

from pydantic import BaseModel, Field

# Field types the UI/extractor understand.
FIELD_TYPES = {"text", "number", "email", "phone", "boolean", "enum", "date"}


class QualificationField(BaseModel):
    key: str
    label: str
    type: str = "text"
    options: list[str] = Field(default_factory=list)  # for type == "enum"
    # "early" → capture as soon as possible (name/email/phone); "normal" → during the chat.
    ask_priority: str = "normal"
    # Must be captured before the agent is allowed to create_appointment.
    required_for_scheduling: bool = False
    # CRM target: a native contact field (email/phone/full_name) or a custom_fields key.
    # Empty → defaults to `key`.
    crm_field: str = ""
    # First-write-wins: once captured, a later turn must not overwrite it (e.g. product_interest).
    sticky: bool = False
    enabled: bool = True

    def target(self) -> str:
        return self.crm_field or self.key


class QualificationSchema(BaseModel):
    fields: list[QualificationField] = Field(default_factory=list)

    def enabled_fields(self) -> list[QualificationField]:
        return [f for f in self.fields if f.enabled]

    def sticky_keys(self) -> set[str]:
        return {f.key for f in self.fields if f.sticky}

    def required_for_scheduling(self) -> list[QualificationField]:
        return [f for f in self.enabled_fields() if f.required_for_scheduling]


# Default schema: sensible for sales, used when an agent has no custom schema.
# Native contact fields (full_name/email/phone) vs CRM custom_fields (the rest).
DEFAULT_QUALIFICATION_FIELDS: list[QualificationField] = [
    QualificationField(key="full_name", label="Full name", type="text",
                       ask_priority="early", required_for_scheduling=True, crm_field="full_name"),
    QualificationField(key="email", label="Email", type="email",
                       ask_priority="early", required_for_scheduling=True, crm_field="email"),
    QualificationField(key="phone", label="Phone", type="phone",
                       ask_priority="early", required_for_scheduling=True, crm_field="phone"),
    QualificationField(key="product_interest", label="Product of interest", type="text",
                       sticky=True, crm_field="product_interest"),
    QualificationField(key="service_needed", label="Type of service/operation", type="text",
                       crm_field="service_needed"),
    QualificationField(key="purchase_timeline", label="When they plan to buy", type="text",
                       crm_field="timeline"),
    QualificationField(key="has_budget", label="Has budget", type="boolean",
                       crm_field="has_budget"),
    QualificationField(key="budget_type", label="Budget type", type="enum",
                       options=["cuotas", "total"], crm_field="budget_type"),
    QualificationField(key="budget_amount", label="Budget amount", type="number",
                       crm_field="budget_amount"),
    QualificationField(key="is_decision_maker", label="Is decision maker", type="boolean",
                       crm_field="is_decision_maker"),
]


def default_schema() -> QualificationSchema:
    return QualificationSchema(fields=list(DEFAULT_QUALIFICATION_FIELDS))
