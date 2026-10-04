"""PromptBuilder._format_missing_fields: lists schema fields still missing
(early ones first), excludes what's already captured or known to the CRM, and
flags what's required before booking."""

from types import SimpleNamespace

from prosales.core.models.qualification_schema import QualificationField, QualificationSchema
from prosales.engines.response.prompt_builder import PromptBuilder


def _schema():
    return QualificationSchema(fields=[
        QualificationField(key="full_name", label="Full name", ask_priority="early",
                           required_for_scheduling=True),
        QualificationField(key="email", label="Email", type="email", ask_priority="early",
                           required_for_scheduling=True),
        QualificationField(key="phone", label="Phone", type="phone", ask_priority="early",
                           required_for_scheduling=True),
        QualificationField(key="product_interest", label="Product of interest"),
        QualificationField(key="has_budget", label="Has budget", type="boolean"),
    ])


def _memory(fact_keys):
    facts = [SimpleNamespace(key=k) for k in fact_keys]
    return SimpleNamespace(semantic=SimpleNamespace(facts=facts))


def test_lists_missing_early_first():
    pb = PromptBuilder()
    state = {
        "qualification_schema": _schema(),
        "memory": _memory(["product_interest"]),  # already have product
        "analysis": None,
        "extra_context": {"contact": {"phone": "123"}},  # CRM already has phone
    }
    out = pb._format_missing_fields(state)
    assert "DATA TO CAPTURE" in out
    # product_interest captured, phone known to CRM → not asked.
    assert "Product of interest" not in out
    assert "Phone" not in out
    # Missing: full_name, email (early), has_budget.
    assert "Full name" in out and "Email" in out and "Has budget" in out
    # Required-before-booking line mentions the missing required fields.
    assert "Required before booking" in out
    assert "Full name" in out.split("Required before booking")[1]


def test_nothing_missing_returns_empty():
    pb = PromptBuilder()
    state = {
        "qualification_schema": _schema(),
        "memory": _memory(["full_name", "email", "phone", "product_interest", "has_budget"]),
        "analysis": None,
        "extra_context": {},
    }
    assert pb._format_missing_fields(state) == ""


def test_no_schema_returns_empty():
    assert PromptBuilder()._format_missing_fields({}) == ""
