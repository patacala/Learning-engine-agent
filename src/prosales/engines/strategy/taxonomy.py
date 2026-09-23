"""Strategy taxonomy — categories, client profiles, and metadata per strategy."""

from dataclasses import dataclass, field
from enum import StrEnum

from prosales.core.enums import StrategyType


class StrategyCategory(StrEnum):
    DISCOVERY = "discovery"
    PRESENTATION = "presentation"
    OBJECTION_HANDLING = "objection_handling"
    CLOSING = "closing"
    NEGOTIATION = "negotiation"
    RAPPORT = "rapport"
    RETENTION = "retention"
    SPECIALIZED = "specialized"


class ClientProfile(StrEnum):
    RATIONAL = "rational"
    EMOTIONAL = "emotional"
    DISTRUSTFUL = "distrustful"
    RUSHED = "rushed"
    SILENT = "silent"
    ANALYTICAL = "analytical"


@dataclass
class StrategyMeta:
    category: StrategyCategory
    client_profiles: list[ClientProfile] = field(default_factory=list)
    stage_fit: list[str] = field(default_factory=list)
    base_priority: int = 5


STRATEGY_TAXONOMY: dict[StrategyType, StrategyMeta] = {
    # Original 8
    StrategyType.CONSULTIVE: StrategyMeta(
        category=StrategyCategory.DISCOVERY,
        client_profiles=[ClientProfile.RATIONAL, ClientProfile.ANALYTICAL],
        stage_fit=["discovery", "presentation"],
    ),
    StrategyType.SPIN_SELLING: StrategyMeta(
        category=StrategyCategory.DISCOVERY,
        client_profiles=[ClientProfile.RATIONAL, ClientProfile.ANALYTICAL],
        stage_fit=["discovery"],
        base_priority=6,
    ),
    StrategyType.CHALLENGER: StrategyMeta(
        category=StrategyCategory.PRESENTATION,
        client_profiles=[ClientProfile.RATIONAL, ClientProfile.ANALYTICAL],
        stage_fit=["presentation", "negotiation"],
        base_priority=6,
    ),
    StrategyType.URGENCY: StrategyMeta(
        category=StrategyCategory.CLOSING,
        client_profiles=[ClientProfile.RUSHED, ClientProfile.EMOTIONAL],
        stage_fit=["closing", "negotiation"],
    ),
    StrategyType.SOCIAL_PROOF: StrategyMeta(
        category=StrategyCategory.PRESENTATION,
        client_profiles=[ClientProfile.DISTRUSTFUL, ClientProfile.EMOTIONAL],
        stage_fit=["presentation", "objection_handling"],
    ),
    StrategyType.SCARCITY: StrategyMeta(
        category=StrategyCategory.CLOSING,
        client_profiles=[ClientProfile.RUSHED, ClientProfile.EMOTIONAL],
        stage_fit=["closing"],
    ),
    StrategyType.VALUE_FIRST: StrategyMeta(
        category=StrategyCategory.PRESENTATION,
        client_profiles=[ClientProfile.RATIONAL, ClientProfile.ANALYTICAL, ClientProfile.DISTRUSTFUL],
        stage_fit=["presentation", "negotiation"],
    ),
    StrategyType.PRICE_DEFENSE: StrategyMeta(
        category=StrategyCategory.OBJECTION_HANDLING,
        client_profiles=[ClientProfile.RATIONAL, ClientProfile.ANALYTICAL],
        stage_fit=["objection_handling", "negotiation"],
    ),
    # Discovery
    StrategyType.NEEDS_DIAGNOSIS: StrategyMeta(
        category=StrategyCategory.DISCOVERY,
        client_profiles=[ClientProfile.SILENT, ClientProfile.ANALYTICAL],
        stage_fit=["opening", "discovery"],
    ),
    StrategyType.PAIN_AMPLIFICATION: StrategyMeta(
        category=StrategyCategory.DISCOVERY,
        client_profiles=[ClientProfile.RATIONAL, ClientProfile.EMOTIONAL],
        stage_fit=["discovery", "presentation"],
    ),
    StrategyType.FUTURE_PACING: StrategyMeta(
        category=StrategyCategory.PRESENTATION,
        client_profiles=[ClientProfile.EMOTIONAL, ClientProfile.RATIONAL],
        stage_fit=["presentation", "closing"],
    ),
    # Closing
    StrategyType.ASSUMPTIVE_CLOSE: StrategyMeta(
        category=StrategyCategory.CLOSING,
        client_profiles=[ClientProfile.RUSHED, ClientProfile.EMOTIONAL],
        stage_fit=["closing"],
        base_priority=6,
    ),
    StrategyType.ALTERNATIVE_CLOSE: StrategyMeta(
        category=StrategyCategory.CLOSING,
        client_profiles=[ClientProfile.ANALYTICAL, ClientProfile.RATIONAL],
        stage_fit=["closing"],
    ),
    StrategyType.TRIAL_CLOSE: StrategyMeta(
        category=StrategyCategory.CLOSING,
        client_profiles=[ClientProfile.DISTRUSTFUL, ClientProfile.SILENT],
        stage_fit=["presentation", "closing"],
    ),
    StrategyType.SUMMARY_CLOSE: StrategyMeta(
        category=StrategyCategory.CLOSING,
        client_profiles=[ClientProfile.RATIONAL, ClientProfile.ANALYTICAL],
        stage_fit=["closing"],
    ),
    StrategyType.PUPPY_DOG_CLOSE: StrategyMeta(
        category=StrategyCategory.CLOSING,
        client_profiles=[ClientProfile.DISTRUSTFUL, ClientProfile.EMOTIONAL],
        stage_fit=["closing"],
    ),
    # Objection handling
    StrategyType.FEEL_FELT_FOUND: StrategyMeta(
        category=StrategyCategory.OBJECTION_HANDLING,
        client_profiles=[ClientProfile.EMOTIONAL, ClientProfile.DISTRUSTFUL],
        stage_fit=["objection_handling"],
        base_priority=6,
    ),
    StrategyType.BOOMERANG: StrategyMeta(
        category=StrategyCategory.OBJECTION_HANDLING,
        client_profiles=[ClientProfile.RATIONAL, ClientProfile.ANALYTICAL],
        stage_fit=["objection_handling"],
    ),
    StrategyType.ACKNOWLEDGE_REDIRECT: StrategyMeta(
        category=StrategyCategory.OBJECTION_HANDLING,
        client_profiles=[ClientProfile.EMOTIONAL, ClientProfile.DISTRUSTFUL],
        stage_fit=["objection_handling"],
    ),
    StrategyType.ISOLATION: StrategyMeta(
        category=StrategyCategory.OBJECTION_HANDLING,
        client_profiles=[ClientProfile.RATIONAL, ClientProfile.ANALYTICAL],
        stage_fit=["objection_handling", "negotiation"],
    ),
    # Rapport
    StrategyType.RAPPORT_BUILDING: StrategyMeta(
        category=StrategyCategory.RAPPORT,
        client_profiles=[ClientProfile.EMOTIONAL, ClientProfile.SILENT, ClientProfile.DISTRUSTFUL],
        stage_fit=["opening", "discovery"],
    ),
    StrategyType.EMPATHIC_LISTENING: StrategyMeta(
        category=StrategyCategory.RAPPORT,
        client_profiles=[ClientProfile.EMOTIONAL, ClientProfile.DISTRUSTFUL],
        stage_fit=["opening", "discovery", "objection_handling"],
    ),
    StrategyType.STORYTELLING: StrategyMeta(
        category=StrategyCategory.RAPPORT,
        client_profiles=[ClientProfile.EMOTIONAL, ClientProfile.SILENT],
        stage_fit=["presentation"],
    ),
    StrategyType.MIRRORING: StrategyMeta(
        category=StrategyCategory.RAPPORT,
        client_profiles=[ClientProfile.EMOTIONAL, ClientProfile.SILENT],
        stage_fit=["opening", "discovery"],
    ),
    # Retention
    StrategyType.FOLLOW_UP_VALUE: StrategyMeta(
        category=StrategyCategory.RETENTION,
        client_profiles=[ClientProfile.RATIONAL, ClientProfile.ANALYTICAL],
        stage_fit=["post_sale"],
    ),
    StrategyType.REACTIVATION: StrategyMeta(
        category=StrategyCategory.RETENTION,
        client_profiles=[ClientProfile.RATIONAL, ClientProfile.EMOTIONAL],
        stage_fit=["opening", "post_sale"],
    ),
    StrategyType.LOYALTY_REINFORCEMENT: StrategyMeta(
        category=StrategyCategory.RETENTION,
        client_profiles=[ClientProfile.EMOTIONAL, ClientProfile.RATIONAL],
        stage_fit=["post_sale"],
    ),
    # Specialized
    StrategyType.COMPARISON_ADVANTAGE: StrategyMeta(
        category=StrategyCategory.SPECIALIZED,
        client_profiles=[ClientProfile.ANALYTICAL, ClientProfile.RATIONAL],
        stage_fit=["presentation", "objection_handling"],
    ),
    StrategyType.EDUCATIONAL_SELLING: StrategyMeta(
        category=StrategyCategory.SPECIALIZED,
        client_profiles=[ClientProfile.ANALYTICAL, ClientProfile.RATIONAL],
        stage_fit=["discovery", "presentation"],
    ),
    StrategyType.SILENCE_ENGAGEMENT: StrategyMeta(
        category=StrategyCategory.SPECIALIZED,
        client_profiles=[ClientProfile.SILENT],
        stage_fit=["opening", "discovery"],
    ),
    StrategyType.RISK_REVERSAL: StrategyMeta(
        category=StrategyCategory.SPECIALIZED,
        client_profiles=[ClientProfile.DISTRUSTFUL, ClientProfile.ANALYTICAL],
        stage_fit=["closing", "objection_handling"],
    ),
    StrategyType.ANCHORING: StrategyMeta(
        category=StrategyCategory.SPECIALIZED,
        client_profiles=[ClientProfile.RATIONAL, ClientProfile.ANALYTICAL],
        stage_fit=["presentation", "negotiation"],
    ),
}
