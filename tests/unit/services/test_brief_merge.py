"""Additive brief merge: the brief enriches the template-seeded config, it never
degrades it. Lists are unioned (template first), scalars are kept from the
template, rules/strategies union by rule_id/strategy_type."""

from prosales.api.v1.schemas.management import (
    IdentityPayload,
    PersonalityPayload,
    RulePayload,
    StrategyPayload,
)
from prosales.services.brief_extractor import (
    merge_identity,
    merge_personality,
    merge_rules,
    merge_strategies,
)


def test_identity_scalars_kept_from_template_lists_unioned():
    base = IdentityPayload(
        name="Technical Support", description="AI technical service specialist",
        communication_style="direct", principles=["Diagnose first"], words_prefer=["let's check"],
    )
    brief = IdentityPayload(
        name="Generic Bot", description="answers calls", communication_style="consultive",
        principles=["Diagnose first", "Be kind"], words_prefer=["please"],
    )
    merged = merge_identity(base, brief)

    # Scalars keep the template's identity (a weak brief can't flatten the role).
    assert merged.name == "Technical Support"
    assert merged.description == "AI technical service specialist"
    assert merged.communication_style == "direct"
    # Lists union, template items first, deduped.
    assert merged.principles == ["Diagnose first", "Be kind"]
    assert merged.words_prefer == ["let's check", "please"]


def test_empty_brief_identity_preserves_template():
    base = IdentityPayload(name="Advisor", description="d", principles=["P1", "P2"])
    empty = IdentityPayload(name="", description="")
    merged = merge_identity(base, empty)
    assert merged.name == "Advisor"
    assert merged.principles == ["P1", "P2"]


def test_personality_tone_kept_lists_unioned():
    base = PersonalityPayload(
        brand_tone="Precise and calm", brand_traits=["precise"], brand_instructions=["No sales pressure"],
    )
    brief = PersonalityPayload(
        brand_tone="Salesy and pushy", brand_traits=["precise", "friendly"], brand_instructions=["Upsell"],
    )
    merged = merge_personality(base, brief)
    assert merged.brand_tone == "Precise and calm"  # template tone survives
    assert merged.brand_traits == ["precise", "friendly"]
    assert merged.brand_instructions == ["No sales pressure", "Upsell"]


def test_rules_union_by_rule_id_template_wins():
    base = [RulePayload(rule_id="greet", action_type="greet", priority=10)]
    brief = [
        RulePayload(rule_id="greet", action_type="OVERWRITE_ATTEMPT", priority=1),
        RulePayload(rule_id="brief_rule_0", action_type="inform", priority=5),
    ]
    merged = merge_rules(base, brief)
    ids = [r.rule_id for r in merged]
    assert ids == ["greet", "brief_rule_0"]
    # The template's 'greet' rule is NOT overwritten by the brief's same-id rule.
    assert merged[0].action_type == "greet"


def test_strategies_union_by_type_template_wins():
    base = [StrategyPayload(strategy_type="needs_diagnosis", name="Troubleshooting")]
    brief = [
        StrategyPayload(strategy_type="needs_diagnosis", name="BriefDiag"),
        StrategyPayload(strategy_type="social_proof", name="Social Proof"),
    ]
    merged = merge_strategies(base, brief)
    types = [s.strategy_type for s in merged]
    assert types == ["needs_diagnosis", "social_proof"]
    assert merged[0].name == "Troubleshooting"  # template strategy preserved


def test_empty_base_merge_is_brief_alone():
    # Agent created without a template (no base) → merge == brief.
    brief_rules = [RulePayload(rule_id="r1", action_type="inform", priority=5)]
    assert merge_rules([], brief_rules) == brief_rules
    brief_strats = [StrategyPayload(strategy_type="consultive", name="C")]
    assert merge_strategies([], brief_strats) == brief_strats
