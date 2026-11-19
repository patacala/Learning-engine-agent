from learning_engine.core.enums import Intent, Sentiment, UrgencyLevel
from learning_engine.core.models.analysis import AnalysisResult
from learning_engine.core.models.decision import Action
from learning_engine.core.models.execution import RuleEvaluation
from learning_engine.core.models.agent import AgentRule


def apply_rules(analysis: AnalysisResult) -> tuple[list[Action], list[RuleEvaluation]]:
    """Apply business rules based on analysis results. Returns actions and evaluations."""
    actions = []
    evaluations = []

    # Greeting → warm welcome
    matched = analysis.intent.intent == Intent.GREETING
    evaluations.append(RuleEvaluation(
        rule="intent_greeting_v1",
        matched=matched,
        confidence=analysis.intent.confidence,
        reason=f"Intent={analysis.intent.intent.value}, triggers greet" if matched else "",
    ))
    if matched:
        actions.append(Action(type="greet", priority=10))

    # Inquiry → provide information
    matched = analysis.intent.intent == Intent.INQUIRY
    evaluations.append(RuleEvaluation(
        rule="intent_inquiry_v1",
        matched=matched,
        confidence=analysis.intent.confidence,
        reason=f"Intent={analysis.intent.intent.value}, triggers inform" if matched else "",
    ))
    if matched:
        actions.append(Action(type="inform", priority=8))

    # Comparison → highlight differentiators
    matched = analysis.intent.intent == Intent.COMPARISON
    evaluations.append(RuleEvaluation(
        rule="intent_comparison_v1",
        matched=matched,
        confidence=analysis.intent.confidence,
        reason=f"Intent={analysis.intent.intent.value}, triggers compare+differentiate" if matched else "",
    ))
    if matched:
        actions.append(Action(type="compare", priority=9))
        actions.append(Action(type="differentiate", priority=7))

    # Objection → address concern
    matched = analysis.intent.intent == Intent.OBJECTION
    evaluations.append(RuleEvaluation(
        rule="intent_objection_v1",
        matched=matched,
        confidence=analysis.intent.confidence,
        reason=f"Intent={analysis.intent.intent.value}, triggers handle_objection" if matched else "",
    ))
    if matched:
        actions.append(Action(type="handle_objection", priority=10))

    # Negative sentiment → empathize first
    matched = analysis.sentiment.sentiment in (Sentiment.NEGATIVE, Sentiment.VERY_NEGATIVE)
    evaluations.append(RuleEvaluation(
        rule="negative_sentiment_v1",
        matched=matched,
        confidence=abs(analysis.sentiment.score),
        reason=f"Sentiment={analysis.sentiment.sentiment.value}, triggers empathize" if matched else "",
    ))
    if matched:
        actions.append(Action(type="empathize", priority=11))

    # High urgency → expedite
    matched = analysis.urgency.level == UrgencyLevel.HIGH
    evaluations.append(RuleEvaluation(
        rule="high_urgency_v1",
        matched=matched,
        confidence=1.0,
        reason=f"Urgency={analysis.urgency.level.value}, triggers expedite" if matched else "",
    ))
    if matched:
        actions.append(Action(type="expedite", priority=9))

    # Scheduling → offer appointment
    matched = analysis.intent.intent == Intent.SCHEDULING
    evaluations.append(RuleEvaluation(
        rule="intent_scheduling_v1",
        matched=matched,
        confidence=analysis.intent.confidence,
        reason=f"Intent={analysis.intent.intent.value}, triggers schedule" if matched else "",
    ))
    if matched:
        actions.append(Action(type="schedule", priority=10))

    # Default
    if not actions:
        actions.append(Action(type="continue_conversation", priority=5))

    return sorted(actions, key=lambda a: a.priority, reverse=True), evaluations


def apply_agent_rules(
    analysis: AnalysisResult, rules: list[AgentRule]
) -> tuple[list[Action], list[RuleEvaluation]]:
    """Apply agent-defined rules based on analysis results."""
    actions = []
    evaluations = []

    intent_str = analysis.intent.intent.value if analysis.intent else ""
    sentiment_str = analysis.sentiment.sentiment.value if analysis.sentiment else ""
    urgency_str = analysis.urgency.level.value if analysis.urgency else ""

    for rule in rules:
        matched = True

        if rule.intent and rule.intent != intent_str:
            matched = False
        if rule.sentiment and rule.sentiment != sentiment_str:
            matched = False
        if rule.urgency and rule.urgency != urgency_str:
            matched = False

        evaluations.append(RuleEvaluation(
            rule=rule.rule_id,
            matched=matched,
            confidence=analysis.intent.confidence if matched else 0.0,
            reason=f"agent rule {rule.rule_id} → {rule.action_type}" if matched else "",
        ))

        if matched:
            actions.append(Action(
                type=rule.action_type,
                priority=rule.priority,
                params=rule.action_params,
            ))

    if not actions:
        actions.append(Action(type="continue_conversation", priority=5))

    return sorted(actions, key=lambda a: a.priority, reverse=True), evaluations
