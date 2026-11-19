import logging
from typing import Any

from learning_engine.core.enums import Intent
from learning_engine.core.interfaces.engine import BaseEngine
from learning_engine.engines.response.models import ResponsePlan

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

        # Supporting points from knowledge — chunks are already small and
        # relevant by construction (retrieval enforces top_k + a per-document
        # dedup cap upstream, see PGVectorStore.search_by_embedding), so no
        # manual top-2 slice or 200-char truncation here. That combination
        # used to cut business-critical facts (e.g. a Saturday business-hours
        # line) mid-sentence, forcing the LLM to "complete" a fact it was
        # never fully given — confirmed root cause of a production
        # hallucination bug. If the retrieved-content budget ever needs to
        # shrink, the fix is lowering KnowledgeEngine's top_k, not truncating
        # here again.
        if knowledge and knowledge.documents:
            for doc in knowledge.documents:
                response_plan.supporting_points.append(
                    f"{doc.get('title', '')}: {doc.get('content', '')}"
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
