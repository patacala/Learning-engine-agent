"""Tests for the multi-signal OutcomeScorer."""

from learning_engine.engines.performance.scorer import OutcomeScorer


def test_positive_transition_scores_high():
    r = OutcomeScorer().score(client_state_before="desconfiado", client_state_after="convencido")
    assert r.score > 0.6
    assert r.confidence > 0


def test_negative_transition_scores_low():
    r = OutcomeScorer().score(client_state_before="comparando", client_state_after="perdio_confianza")
    assert r.score < 0.4


def test_confidence_grows_with_more_signals():
    single = OutcomeScorer().score(client_state_before="curioso", client_state_after="convencido")
    multi = OutcomeScorer().score(
        client_state_before="curioso", client_state_after="convencido",
        outcome="converted", purchase=True, human_rating=0.9,
    )
    assert multi.confidence > single.confidence


def test_lost_outcome_drags_score_down():
    good = OutcomeScorer().score(client_state_before="curioso", client_state_after="mas_interesado")
    lost = OutcomeScorer().score(
        client_state_before="curioso", client_state_after="mas_interesado", outcome="lost"
    )
    assert lost.score < good.score


def test_no_signals_returns_neutral_zero_confidence():
    r = OutcomeScorer().score()
    assert r.score == 0.5
    assert r.confidence == 0.0


def test_breakdown_lists_present_signals():
    r = OutcomeScorer().score(outcome="scheduled", human_rating=0.7)
    assert set(r.breakdown) == {"outcome", "human"}
