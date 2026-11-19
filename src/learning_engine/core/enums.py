from enum import StrEnum


class Intent(StrEnum):
    GREETING = "greeting"
    INQUIRY = "inquiry"
    COMPARISON = "comparison"
    OBJECTION = "objection"
    NEGOTIATION = "negotiation"
    SCHEDULING = "scheduling"
    FAREWELL = "farewell"
    COMPLAINT = "complaint"
    FOLLOW_UP = "follow_up"
    UNKNOWN = "unknown"


class Sentiment(StrEnum):
    VERY_POSITIVE = "very_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    VERY_NEGATIVE = "very_negative"


class ConversationStage(StrEnum):
    OPENING = "opening"
    DISCOVERY = "discovery"
    PRESENTATION = "presentation"
    OBJECTION_HANDLING = "objection_handling"
    NEGOTIATION = "negotiation"
    CLOSING = "closing"
    POST_SALE = "post_sale"


class UrgencyLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Outcome(StrEnum):
    """Conversation outcome inferred by Cognition (not the CRM).

    Terminal = SCHEDULED / ABANDONED / LOST. converted/purchase are excluded
    (require billing, unavailable); cold is a client state, not an outcome.
    """

    OPEN = "open"
    RESOLVED = "resolved"
    SCHEDULED = "scheduled"
    ABANDONED = "abandoned"
    LOST = "lost"

    @classmethod
    def terminal(cls) -> set["Outcome"]:
        return {cls.SCHEDULED, cls.ABANDONED, cls.LOST}

    def is_terminal(self) -> bool:
        return self in self.terminal()


class RoleplaySubOutcome(StrEnum):
    """Scenario-flavored outcome a roleplay trainer can pick at close, in
    addition to (or instead of) the coarse Outcome. Each maps to exactly one
    Outcome so the learning pipeline (run_live_learning, OutcomeScorer) keeps
    consuming Outcome unchanged.
    """

    OBJECTION_HANDLED = "objection_handled"
    CLOSE_ATTEMPTED = "close_attempted"
    DISCOVERY_INCOMPLETE = "discovery_incomplete"
    CLIENT_DISENGAGED = "client_disengaged"
    RAPPORT_ONLY = "rapport_only"


SUB_OUTCOME_TO_OUTCOME: dict[RoleplaySubOutcome, Outcome] = {
    RoleplaySubOutcome.OBJECTION_HANDLED: Outcome.SCHEDULED,
    RoleplaySubOutcome.CLOSE_ATTEMPTED: Outcome.SCHEDULED,
    RoleplaySubOutcome.DISCOVERY_INCOMPLETE: Outcome.ABANDONED,
    RoleplaySubOutcome.CLIENT_DISENGAGED: Outcome.LOST,
    RoleplaySubOutcome.RAPPORT_ONLY: Outcome.RESOLVED,
}


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Language(StrEnum):
    ES = "es"
    EN = "en"
    PT = "pt"
    FR = "fr"


class ConversationPath(StrEnum):
    FAST_PATH = "fast_path"
    FULL_PATH = "full_path"


class StrategyType(StrEnum):
    # Original 8
    CONSULTIVE = "consultive"
    SPIN_SELLING = "spin_selling"
    CHALLENGER = "challenger"
    URGENCY = "urgency"
    SOCIAL_PROOF = "social_proof"
    SCARCITY = "scarcity"
    VALUE_FIRST = "value_first"
    PRICE_DEFENSE = "price_defense"
    # Discovery
    NEEDS_DIAGNOSIS = "needs_diagnosis"
    PAIN_AMPLIFICATION = "pain_amplification"
    FUTURE_PACING = "future_pacing"
    # Closing
    ASSUMPTIVE_CLOSE = "assumptive_close"
    ALTERNATIVE_CLOSE = "alternative_close"
    TRIAL_CLOSE = "trial_close"
    SUMMARY_CLOSE = "summary_close"
    PUPPY_DOG_CLOSE = "puppy_dog_close"
    # Objection handling
    FEEL_FELT_FOUND = "feel_felt_found"
    BOOMERANG = "boomerang"
    ACKNOWLEDGE_REDIRECT = "acknowledge_redirect"
    ISOLATION = "isolation"
    # Rapport
    RAPPORT_BUILDING = "rapport_building"
    EMPATHIC_LISTENING = "empathic_listening"
    STORYTELLING = "storytelling"
    MIRRORING = "mirroring"
    # Retention
    FOLLOW_UP_VALUE = "follow_up_value"
    REACTIVATION = "reactivation"
    LOYALTY_REINFORCEMENT = "loyalty_reinforcement"
    # Specialized
    COMPARISON_ADVANTAGE = "comparison_advantage"
    EDUCATIONAL_SELLING = "educational_selling"
    SILENCE_ENGAGEMENT = "silence_engagement"
    RISK_REVERSAL = "risk_reversal"
    ANCHORING = "anchoring"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class LLMProvider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
