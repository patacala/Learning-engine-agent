import logging
from typing import Any

from prosales.core.enums import Intent
from prosales.core.interfaces.engine import BaseEngine
from prosales.engines.response.models import ResponsePlan

logger = logging.getLogger(__name__)


class ResponsePlanner(BaseEngine):
    """Decides WHAT to say (structure of the response)."""

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        analysis = state.get("analysis")
        decision = state.get("decision")
        plan = state.get("plan")
        knowledge = state.get("knowledge")

        response_plan = ResponsePlan()

        # Main point from sales plan
        if plan and plan.next_action:
            response_plan.main_point = plan.next_action.description

        # Supporting points from knowledge
        if knowledge and knowledge.documents:
            for doc in knowledge.documents[:2]:
                response_plan.supporting_points.append(
                    f"{doc.get('title', '')}: {doc.get('content', '')[:200]}"
                )

        # Call to action from decision
        if decision and decision.actions:
            top_action = decision.actions[0]
            if top_action.type == "schedule":
                response_plan.call_to_action = "Propose scheduling a visit or test drive"
            elif top_action.type == "inform":
                response_plan.call_to_action = "Ask what specific information they need"

        # Adjust length for greeting/farewell
        intent = analysis.intent.intent if analysis else Intent.UNKNOWN
        if intent in (Intent.GREETING, Intent.FAREWELL):
            response_plan.max_sentences = 2

        return {"response_plan": response_plan}
