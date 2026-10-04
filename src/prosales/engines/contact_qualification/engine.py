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

# Facts that are first-write-wins: once captured, a later turn must NOT overwrite
# them. The product/service the contact is interested in (e.g. "Audi A5") is the
# anchor of the whole conversation — a later "agendar una visita" turn would
# otherwise clobber product_interest with the scheduling intent and lose it.
_STICKY_FACTS = {"product_interest"}


class ContactQualificationEngine:
    def qualify(
        self,
        prior: ContactQualification,
        analysis: AnalysisResult,
        conversation_outcome: str = "open",
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
        facts = dict(prior.facts)
        for k, v in (cs.facts or {}).items():
            if not v:
                continue
            if k in _STICKY_FACTS and facts.get(k):
                continue  # keep the first-captured value (see _STICKY_FACTS)
            facts[k] = v

        # --- BANT ---
        has = signals.__contains__
        bant = {
            "need": has("positive_interest")
            or has("appointment_requested")
            or bool(facts.get("product_interest"))
            or intent in (Intent.INQUIRY, Intent.SCHEDULING, Intent.NEGOTIATION),
            "budget": has("budget_confirmed") or bool(facts.get("budget")),
            "authority": has("decision_maker") or bool(facts.get("decision_role")),
            "timeline": bool(facts.get("timeline"))
            or has("ready_to_buy")
            or urgency in (UrgencyLevel.HIGH, UrgencyLevel.CRITICAL),
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
