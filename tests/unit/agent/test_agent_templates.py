"""Agent templates: the selectable types each define a distinct role, and the
legacy 'support' type aliases customer_service for backward compatibility."""

from prosales.infrastructure.agent.templates import (
    AGENT_TEMPLATES,
    SELECTABLE_AGENT_TYPES,
)


def test_selectable_types_all_have_a_template():
    for t in SELECTABLE_AGENT_TYPES:
        assert t in AGENT_TEMPLATES, f"missing template for selectable type {t}"


def test_support_is_backward_compat_alias_of_customer_service():
    # Existing agents created as "support" must keep resolving to a template.
    assert AGENT_TEMPLATES["support"] is AGENT_TEMPLATES["customer_service"]
    # ...but the alias is NOT offered as a new choice.
    assert "support" not in SELECTABLE_AGENT_TYPES


def test_each_type_has_a_distinct_role_identity():
    names = {t: AGENT_TEMPLATES[t]["identity"]["name"] for t in SELECTABLE_AGENT_TYPES}
    # No two selectable types share the same identity name → distinct roles.
    assert len(set(names.values())) == len(names), names


def test_non_sales_types_are_not_sales_flavored():
    # Technical service and consulting must not read as sales roles.
    tech = AGENT_TEMPLATES["technical_service"]
    assert "sales" not in tech["identity"]["description"].lower()
    # Their personality instructions explicitly avoid sales pressure.
    joined = " ".join(tech["personality"]["brand_instructions"]).lower()
    assert "no sales pressure" in joined


def test_new_types_have_personality_and_identity():
    for t in ("consulting", "technical_service", "customer_service"):
        tmpl = AGENT_TEMPLATES[t]
        assert tmpl["identity"]["name"]
        assert tmpl["personality"]["brand_tone"]
