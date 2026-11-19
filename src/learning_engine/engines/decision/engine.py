import logging
from typing import Any

from learning_engine.core.interfaces.engine import BaseEngine
from learning_engine.core.models.decision import Decision
from learning_engine.engines.decision.rules import apply_rules, apply_agent_rules

logger = logging.getLogger(__name__)


class DecisionEngine(BaseEngine):
    """Rule-based decision engine."""

    def __init__(self, rule_provider=None):
        self.rule_provider = rule_provider

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        analysis = state.get("analysis")
        if not analysis:
            return {"decision": Decision()}

        ctx = state.get("agent_context")

        # Try agent rules first, fallback to hardcoded
        if self.rule_provider and ctx:
            rules = await self.rule_provider.get(ctx.agent_version_id)
            if rules:
                actions, evaluations = apply_agent_rules(analysis, rules)
            else:
                actions, evaluations = apply_rules(analysis)
        else:
            actions, evaluations = apply_rules(analysis)

        decision = Decision(
            actions=actions,
            reasoning=f"Applied {len(evaluations)} rules based on intent={analysis.intent.intent}",
            evaluations=evaluations,
        )

        return {"decision": decision}
