"""Tests for Signal Scorers — each scorer tested in isolation."""

import pytest
from uuid import uuid4

from learning_engine.core.enums import Intent, Sentiment, StrategyType
from learning_engine.core.models.analysis import AnalysisResult, IntentResult, SentimentResult
from learning_engine.engines.episodic.models import EpisodeSummary
from learning_engine.engines.strategy.scorers import (
    EpisodicScorer,
    IntentScorer,
    SentimentScorer,
    StageScorer,
)

ALL_STRATEGIES = list(StrategyType)


def test_intent_scorer_boosts_mapped_strategy():
    scorer = IntentScorer()
    analysis = AnalysisResult(intent=IntentResult(intent=Intent.INQUIRY, confidence=0.9))
    signal = scorer.score(ALL_STRATEGIES, analysis=analysis)
    # CONSULTIVE is first mapped strategy for INQUIRY
    assert signal.scores.get("consultive", 0) > 0.5
    assert signal.source == "intent"


def test_intent_scorer_multi_candidate_ranking():
    scorer = IntentScorer()
    analysis = AnalysisResult(intent=IntentResult(intent=Intent.OBJECTION, confidence=0.8))
    signal = scorer.score(ALL_STRATEGIES, analysis=analysis)
    # PRICE_DEFENSE > FEEL_FELT_FOUND > BOOMERANG
    assert signal.scores.get("price_defense", 0) > signal.scores.get("feel_felt_found", 0)
    assert signal.scores.get("feel_felt_found", 0) > signal.scores.get("boomerang", 0)


def test_sentiment_scorer_negative_boosts_empathic():
    scorer = SentimentScorer()
    analysis = AnalysisResult(sentiment=SentimentResult(sentiment=Sentiment.NEGATIVE, score=-0.5))
    signal = scorer.score(ALL_STRATEGIES, analysis=analysis)
    assert signal.scores.get("empathic_listening", 0) == 0.1
    assert signal.scores.get("price_defense", 0) == 0.1
    assert signal.scores.get("urgency", 0) == -0.1


def test_sentiment_scorer_neutral_no_effect():
    scorer = SentimentScorer()
    analysis = AnalysisResult(sentiment=SentimentResult(sentiment=Sentiment.NEUTRAL, score=0.0))
    signal = scorer.score(ALL_STRATEGIES, analysis=analysis)
    assert signal.scores == {}


def test_stage_scorer_closing_stage():
    scorer = StageScorer()
    signal = scorer.score(ALL_STRATEGIES, stage="closing")
    # Strategies with "closing" in stage_fit should get +0.15
    assert signal.scores.get("assumptive_close", 0) == 0.15
    assert signal.scores.get("summary_close", 0) == 0.15
    # Discovery strategies should NOT get boosted in closing
    assert "needs_diagnosis" not in signal.scores


def test_episodic_scorer_boost_converted():
    scorer = EpisodicScorer()
    episodes = [
        EpisodeSummary(
            conversation_id=uuid4(),
            strategies_used=["consultive"],
            outcome="converted",
        ),
    ]
    signal = scorer.score(ALL_STRATEGIES, episodes=episodes)
    assert signal.scores.get("consultive", 0) == 0.2


def test_episodic_scorer_penalty_lost():
    scorer = EpisodicScorer()
    episodes = [
        EpisodeSummary(
            conversation_id=uuid4(),
            strategies_used=["urgency"],
            outcome="lost",
        ),
    ]
    signal = scorer.score(ALL_STRATEGIES, episodes=episodes)
    assert signal.scores.get("urgency", 0) == -0.15


def test_episodic_scorer_cap_at_03():
    scorer = EpisodicScorer()
    # 3 converted episodes → 3 × 0.2 = 0.6, should be capped at 0.3
    episodes = [
        EpisodeSummary(conversation_id=uuid4(), strategies_used=["consultive"], outcome="converted"),
        EpisodeSummary(conversation_id=uuid4(), strategies_used=["consultive"], outcome="converted"),
        EpisodeSummary(conversation_id=uuid4(), strategies_used=["consultive"], outcome="converted"),
    ]
    signal = scorer.score(ALL_STRATEGIES, episodes=episodes)
    assert signal.scores.get("consultive", 0) == 0.3
