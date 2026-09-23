"""OutcomeScorer — combine multiple signals into a reliable 0-1 score.

The more signals present, the higher the confidence. Signals:
  1. client-state transition inside the transcript (before -> after)
  2. conversation outcome (episode)
  3. appointment scheduled
  4. purchase
  5. later CRM result
  6. human evaluation (rating)

A single-transcript pattern is scored mostly by (1); real conversations gain
(2)-(6) over time, sharpening both score and confidence.
"""

from dataclasses import dataclass, field

# Rank of each client state on a disposition axis (higher = closer to buying).
_STATE_RANK = {
    "perdio_confianza": -2,
    "frustrado": -1,
    "confundido": -1,
    "desconfiado": 0,
    "comparando": 1,
    "indeciso": 1,
    "curioso": 2,
    "tranquilo": 3,
    "mas_interesado": 3,
    "convencido": 4,
    "listo_para_comprar": 5,
}
_RANK_SPAN = 7.0  # max(-2..5) spread used to normalize a transition delta

# Conversation-level outcome -> score.
_OUTCOME_SCORE = {
    "converted": 1.0,
    "purchase": 1.0,
    "scheduled": 0.8,
    "appointment": 0.8,
    "resolved": 0.75,
    "pending": 0.5,
    "cold": 0.3,
    "abandoned": 0.2,
    "lost": 0.0,
}

# Relative weights per signal (only present signals are normalized together).
_WEIGHTS = {
    "transition": 1.0,
    "outcome": 1.2,
    "appointment": 0.8,
    "purchase": 1.5,
    "crm": 1.2,
    "human": 1.3,
}


@dataclass
class ScoreResult:
    score: float
    confidence: float
    breakdown: dict = field(default_factory=dict)


def _transition_score(before: str, after: str) -> float | None:
    if not after:
        return None
    a = _STATE_RANK.get(after)
    b = _STATE_RANK.get(before, 0)
    if a is None:
        return None
    delta = a - b
    # Map delta in [-RANK_SPAN, RANK_SPAN] to [0, 1].
    return max(0.0, min(1.0, (delta + _RANK_SPAN) / (2 * _RANK_SPAN)))


class OutcomeScorer:
    def score(
        self,
        *,
        client_state_before: str = "",
        client_state_after: str = "",
        outcome: str | None = None,
        appointment_scheduled: bool | None = None,
        purchase: bool | None = None,
        crm_outcome: str | None = None,
        human_rating: float | None = None,
    ) -> ScoreResult:
        signals: dict[str, float] = {}

        t = _transition_score(client_state_before, client_state_after)
        if t is not None:
            signals["transition"] = t
        if outcome:
            signals["outcome"] = _OUTCOME_SCORE.get(outcome.lower(), 0.5)
        if appointment_scheduled is not None:
            signals["appointment"] = 1.0 if appointment_scheduled else 0.2
        if purchase is not None:
            signals["purchase"] = 1.0 if purchase else 0.0
        if crm_outcome:
            signals["crm"] = _OUTCOME_SCORE.get(crm_outcome.lower(), 0.5)
        if human_rating is not None:
            signals["human"] = max(0.0, min(1.0, human_rating))

        if not signals:
            return ScoreResult(score=0.5, confidence=0.0, breakdown={})

        total_w = sum(_WEIGHTS[k] for k in signals)
        score = sum(v * _WEIGHTS[k] for k, v in signals.items()) / total_w
        # Confidence grows with the number of independent signals.
        confidence = min(1.0, len(signals) / len(_WEIGHTS))
        return ScoreResult(
            score=round(score, 4),
            confidence=round(confidence, 4),
            breakdown={k: round(v, 4) for k, v in signals.items()},
        )
