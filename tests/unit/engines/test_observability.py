"""Tests for observability: execution models, decision trace, strategy trace, _timed wrapper."""

import asyncio
import time
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from learning_engine.core.enums import Intent, Sentiment, StrategyType, UrgencyLevel
from learning_engine.core.models.analysis import (
    AnalysisResult,
    IntentResult,
    SentimentResult,
    UrgencyResult,
)
from learning_engine.core.models.events import (
    AnalyzerCompleted,
    DecisionMade,
    KnowledgeRetrieved,
    PipelineCompleted,
    ResponseGenerated,
    StrategySelected,
)
from learning_engine.core.models.execution import (
    DecisionTrace,
    LLMCall,
    NodeTrace,
    PipelineExecution,
    RuleEvaluation,
    StrategyTrace,
    Versions,
)
from learning_engine.engines.decision.rules import apply_rules
from learning_engine.engines.strategy.selector import select_strategy


# --- Execution Model Tests ---


class TestPipelineExecution:
    def test_creates_with_defaults(self):
        execution = PipelineExecution()
        assert execution.trace_id is not None
        assert execution.request_id is not None
        assert execution.nodes == []
        assert execution.llm_calls == []
        assert execution.versions.pipeline == "1.0.0"

    def test_full_structure(self):
        execution = PipelineExecution(
            conversation_id=uuid4(),
            client_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            versions=Versions(pipeline="1.0.0", prompt="response_v1", model="gpt-4o"),
        )
        execution.nodes.append(NodeTrace(
            node_id="analyze",
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            duration_ms=45.2,
            status="success",
        ))
        execution.llm_calls.append(LLMCall(
            provider="openai",
            model="gpt-4o",
            temperature=0.7,
            prompt_tokens=150,
            completion_tokens=200,
            total_tokens=350,
            duration_ms=823.5,
        ))
        execution.decision = DecisionTrace(
            actions=["handle_objection", "empathize"],
            evaluations=[
                RuleEvaluation(rule="intent_objection_v1", matched=True, confidence=0.92),
            ],
            total_rules_evaluated=7,
        )
        execution.strategy = StrategyTrace(
            selected="price_defense",
            candidates=["price_defense", "consultive"],
            scores={"price_defense": 0.88, "consultive": 0.61},
            reason="Intent=objection → price_defense",
            switched=False,
        )

        # Serialize to JSON
        data = execution.model_dump(mode="json")
        assert data["versions"]["pipeline"] == "1.0.0"
        assert len(data["nodes"]) == 1
        assert data["decision"]["total_rules_evaluated"] == 7
        assert data["strategy"]["selected"] == "price_defense"


# --- Decision Rules Tests ---


class TestApplyRulesEvaluations:
    def test_returns_tuple(self):
        analysis = AnalysisResult(
            intent=IntentResult(intent=Intent.OBJECTION, confidence=0.92),
            sentiment=SentimentResult(sentiment=Sentiment.NEGATIVE, score=-0.7),
        )
        actions, evaluations = apply_rules(analysis)
        assert isinstance(actions, list)
        assert isinstance(evaluations, list)
        assert len(evaluations) == 7  # one per rule

    def test_objection_rule_matched(self):
        analysis = AnalysisResult(
            intent=IntentResult(intent=Intent.OBJECTION, confidence=0.92),
        )
        actions, evaluations = apply_rules(analysis)

        objection_eval = next(e for e in evaluations if e.rule == "intent_objection_v1")
        assert objection_eval.matched is True
        assert objection_eval.confidence == 0.92
        assert "handle_objection" in objection_eval.reason

    def test_unmatched_rules_have_evaluations(self):
        analysis = AnalysisResult(
            intent=IntentResult(intent=Intent.GREETING, confidence=0.95),
        )
        actions, evaluations = apply_rules(analysis)

        # Greeting matches
        greeting_eval = next(e for e in evaluations if e.rule == "intent_greeting_v1")
        assert greeting_eval.matched is True

        # Objection does not match
        objection_eval = next(e for e in evaluations if e.rule == "intent_objection_v1")
        assert objection_eval.matched is False

    def test_negative_sentiment_rule(self):
        analysis = AnalysisResult(
            intent=IntentResult(intent=Intent.INQUIRY),
            sentiment=SentimentResult(sentiment=Sentiment.NEGATIVE, score=-0.6),
        )
        actions, evaluations = apply_rules(analysis)

        sentiment_eval = next(e for e in evaluations if e.rule == "negative_sentiment_v1")
        assert sentiment_eval.matched is True
        assert sentiment_eval.confidence == 0.6  # abs of score

    def test_high_urgency_rule(self):
        analysis = AnalysisResult(
            intent=IntentResult(intent=Intent.INQUIRY),
            urgency=UrgencyResult(level=UrgencyLevel.HIGH),
        )
        actions, evaluations = apply_rules(analysis)

        urgency_eval = next(e for e in evaluations if e.rule == "high_urgency_v1")
        assert urgency_eval.matched is True


# --- Strategy Selector Tests ---


class TestSelectStrategyTrace:
    def test_returns_tuple(self):
        analysis = AnalysisResult(intent=IntentResult(intent=Intent.INQUIRY, confidence=0.85))
        result = select_strategy(analysis)
        assert isinstance(result, tuple)
        strategy_type, trace = result
        assert strategy_type == StrategyType.CONSULTIVE
        assert isinstance(trace, StrategyTrace)

    def test_trace_has_candidates_and_scores(self):
        analysis = AnalysisResult(intent=IntentResult(intent=Intent.OBJECTION, confidence=0.9))
        strategy_type, trace = select_strategy(analysis)

        assert strategy_type == StrategyType.PRICE_DEFENSE
        assert trace.selected == "price_defense"
        assert len(trace.candidates) > 0
        assert "price_defense" in trace.scores
        assert trace.scores["price_defense"] > trace.scores.get("consultive", 0)
        assert trace.switched is False

    def test_switch_after_3_attempts(self):
        analysis = AnalysisResult(intent=IntentResult(intent=Intent.INQUIRY, confidence=0.8))
        strategy_type, trace = select_strategy(
            analysis, current_strategy=StrategyType.CONSULTIVE, attempts=3
        )
        assert strategy_type != StrategyType.CONSULTIVE
        assert trace.switched is True

    def test_reason_includes_intent(self):
        analysis = AnalysisResult(intent=IntentResult(intent=Intent.COMPARISON, confidence=0.7))
        _, trace = select_strategy(analysis)
        assert "comparison" in trace.reason.lower()


# --- Atomic Events Tests ---


class TestAtomicEvents:
    def test_analyzer_completed_has_fields(self):
        event = AnalyzerCompleted(
            conversation_id=uuid4(),
            data={
                "intent": "objection",
                "intent_confidence": 0.92,
                "sentiment": "negative",
                "trace_id": str(uuid4()),
                "versions": {"pipeline": "1.0.0", "prompt": "response_v1", "model": "gpt-4o"},
            },
        )
        assert event.event_type == "analyzer.completed"
        assert event.data["intent"] == "objection"
        assert event.data["versions"]["pipeline"] == "1.0.0"

    def test_decision_made_event(self):
        event = DecisionMade(
            data={
                "actions": ["handle_objection", "empathize"],
                "evaluations": [{"rule": "intent_objection_v1", "matched": True, "confidence": 0.92}],
                "total_rules_evaluated": 7,
                "trace_id": str(uuid4()),
            },
        )
        assert event.event_type == "decision.made"
        assert len(event.data["evaluations"]) == 1

    def test_strategy_selected_event(self):
        event = StrategySelected(
            data={
                "selected": "price_defense",
                "candidates": ["price_defense", "consultive"],
                "scores": {"price_defense": 0.88, "consultive": 0.61},
                "reason": "Intent=objection → price_defense",
                "trace_id": str(uuid4()),
            },
        )
        assert event.event_type == "strategy.selected"
        assert event.data["selected"] == "price_defense"

    def test_response_generated_event(self):
        event = ResponseGenerated(
            data={
                "model": "gpt-4o",
                "total_tokens": 412,
                "duration_ms": 823,
                "trace_id": str(uuid4()),
            },
        )
        assert event.event_type == "response.generated"

    def test_pipeline_completed_event(self):
        event = PipelineCompleted(
            data={
                "total_ms": 1250,
                "versions": {"pipeline": "1.0.0"},
                "trace_id": str(uuid4()),
            },
        )
        assert event.event_type == "pipeline.completed"

    def test_all_events_have_timestamp(self):
        for EventClass in [AnalyzerCompleted, KnowledgeRetrieved, DecisionMade,
                           StrategySelected, ResponseGenerated, PipelineCompleted]:
            event = EventClass()
            assert event.timestamp is not None
            assert event.id is not None


# --- NodeTrace / _timed wrapper logic ---


class TestNodeTrace:
    def test_node_trace_structure(self):
        trace = NodeTrace(
            node_id="analyze",
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            duration_ms=45.2,
            status="success",
        )
        assert trace.node_id == "analyze"
        assert trace.error is None

    def test_node_trace_with_error(self):
        trace = NodeTrace(
            node_id="retrieve",
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            duration_ms=12.0,
            status="error",
            error="Connection timeout",
        )
        assert trace.status == "error"
        assert trace.error == "Connection timeout"


# --- Versions ---


class TestVersions:
    def test_default_versions(self):
        v = Versions()
        assert v.pipeline == "1.0.0"
        assert v.prompt == "response_v1"
        assert v.model == ""

    def test_custom_versions(self):
        v = Versions(pipeline="2.0.0", prompt="response_v2", model="gpt-4o")
        assert v.pipeline == "2.0.0"
        assert v.model == "gpt-4o"
