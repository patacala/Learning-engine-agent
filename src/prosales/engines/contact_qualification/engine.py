"""ContactQualificationEngine — deterministic, per-contact, funnel-agnostic.

Aggregates the accumulated prior qualification + this turn's analysis (signals,
facts, sentiment, intent, stage, urgency) + the conversation outcome into an
updated qualification. It emits ONLY universal signals; mapping to a CRM funnel
stage is the CRM's job.
"""

from prosales.core.enums import ConversationStage, Intent, Sentiment, UrgencyLevel
from prosales.core.models.analysis import AnalysisResult
from prosales.engines.contact_qualification.models import ContactQualification

_POSITIVE = {Sentiment.POSITIVE, Sentiment.VERY_POSITIVE}
_NEGATIVE = {Sentiment.NEGATIVE, Sentiment.VERY_NEGATIVE}

_POSITIVE_SIGNALS = {"positive_interest", "appointment_requested", "ready_to_buy", "budget_confirmed"}
_NEGATIVE_SIGNALS = {"not_interested", "price_objection", "comparing_competitors"}

# No fact is globally first-write-wins by default: the product the contact is
# interested in must be free to REFINE across the chat (e.g. Q5 -> Q7), so the
# last genuine mention wins. An agent can still opt a field into first-write-wins
# via its schema (QualificationField.sticky).
_STICKY_FACTS: set[str] = set()

# Anchor facts protected ONLY on a scheduling turn: that turn carries no new
# product/service info, and the extractor occasionally mislabels the scheduling
# action as product_interest ("agendar visita"). Protecting them there prevents
# that clobber without blocking normal refinement on inquiry/discovery turns.
_SCHEDULING_PROTECTED = {"product_interest", "service_needed"}


def _bant_fact_hit(dimension: str, schema, facts: dict, *fallback_keys: str) -> bool:
    """True if any captured fact feeds the given BANT dimension.

    Schema-driven: when the org's schema tags fields with this ``bant_dimension``,
    scoring reads exactly those (captured) fields — so each org drives its own
    BANT from its own fields. Falls back per-dimension to the legacy hardcoded
    keys only when the schema is absent or has no field tagged for this
    dimension, keeping agents without a (tagged) schema scoring as before.
    """
    if schema is not None:
        fields = schema.fields_for_bant(dimension)
        if fields:
            return any(bool(facts.get(f.key)) for f in fields)
    return any(bool(facts.get(k)) for k in fallback_keys)


class ContactQualificationEngine:
    def qualify(
        self,
        prior: ContactQualification,
        analysis: AnalysisResult,
        conversation_outcome: str = "open",
        sticky_keys: set[str] | None = None,
        schema=None,
    ) -> ContactQualification:
        cs = analysis.contact_signals
        intent = analysis.intent.intent
        sentiment = analysis.sentiment.sentiment
        stage = analysis.stage.stage
        urgency = analysis.urgency.level

        # --- accumulate signals (LLM + deterministic derivations) ---
        signals = dict(prior.signals)
        detected = list(cs.signals)
        if intent == Intent.SCHEDULING:
            detected.append("appointment_requested")
        if intent == Intent.COMPARISON:
            detected.append("comparing_competitors")
        if intent == Intent.FAREWELL and sentiment in _NEGATIVE:
            detected.append("not_interested")
        for s in detected:
            signals[s] = signals.get(s, 0) + 1

        # --- accumulate facts (new overrides, except sticky ones) ---
        if sticky_keys is None and schema is not None:
            sticky_keys = schema.sticky_keys()
        sticky = set(sticky_keys) if sticky_keys is not None else set(_STICKY_FACTS)
        if intent == Intent.SCHEDULING:
            sticky |= _SCHEDULING_PROTECTED
        facts = dict(prior.facts)
        for k, v in (cs.facts or {}).items():
            if not v:
                continue
            if k in sticky and facts.get(k):
                continue  # keep the first-captured value (see _STICKY_FACTS)
            facts[k] = v

        # --- BANT ---
        # Universal signal/intent/urgency heuristics stay (they're funnel-agnostic,
        # not business fields); the fact-based part is schema-driven per dimension
        # with a per-dimension fallback to the legacy keys (see _bant_fact_hit).
        has = signals.__contains__
        bant = {
            "need": has("positive_interest")
            or has("appointment_requested")
            or intent in (Intent.INQUIRY, Intent.SCHEDULING, Intent.NEGOTIATION)
            or _bant_fact_hit("need", schema, facts, "product_interest"),
            "budget": has("budget_confirmed")
            or _bant_fact_hit("budget", schema, facts, "budget"),
            "authority": has("decision_maker")
            or _bant_fact_hit("authority", schema, facts, "decision_role"),
            "timeline": has("ready_to_buy")
            or urgency in (UrgencyLevel.HIGH, UrgencyLevel.CRITICAL)
            or _bant_fact_hit("timeline", schema, facts, "timeline"),
        }
        bant_count = sum(1 for v in bant.values() if v)
        status = "qualified" if bant_count >= 3 else "qualifying" if bant_count >= 1 else "unqualified"

        # --- temperature score ---
        score = cs.buying_intent
        score += 0.15 * sum(1 for s in _POSITIVE_SIGNALS if has(s))
        score -= 0.15 * sum(1 for s in _NEGATIVE_SIGNALS if has(s))
        if sentiment in _POSITIVE:
            score += 0.1
        elif sentiment in _NEGATIVE:
            score -= 0.1
        if stage in (ConversationStage.CLOSING, ConversationStage.POST_SALE):
            score += 0.1
        if conversation_outcome == "scheduled":
            score = max(score, 0.75)  # a booked next step is at least hot-ish
        if conversation_outcome in ("lost",) or has("not_interested"):
            score = min(score, 0.2)
        score = max(0.0, min(1.0, score))
        temperature = "hot" if score >= 0.66 else "warm" if score >= 0.33 else "cold"

        # --- readiness ---
        readiness = round(
            0.4 * cs.buying_intent + 0.3 * (bant_count / 4.0) + 0.3 * score, 4
        )

        # --- suggested transition (abstract; the CRM maps to its funnel) ---
        if conversation_outcome == "lost" or has("not_interested"):
            transition = "lost"
        elif temperature == "hot" and status == "qualified":
            transition = "advance"
        elif status == "unqualified" and temperature == "cold":
            transition = "disqualify"
        else:
            transition = "hold"

        return ContactQualification(
            id=prior.id,
            client_id=prior.client_id,
            organization_id=prior.organization_id,
            temperature=temperature,
            status=status,
            readiness=readiness,
            bant=bant,
            signals=signals,
            facts=facts,
            suggested_transition=transition,
            last_conversation_id=prior.last_conversation_id,
        )
