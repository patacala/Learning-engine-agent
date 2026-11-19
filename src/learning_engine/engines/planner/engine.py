import logging
from typing import Any

from learning_engine.core.interfaces.engine import BaseEngine
from learning_engine.engines.planner.goals import get_plan_for_stage

logger = logging.getLogger(__name__)


class SalesPlannerEngine(BaseEngine):
    """Goal/Next/Fallback/Exit planner."""

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        analysis = state.get("analysis")
        stage = analysis.stage.stage if analysis else "opening"

        plan = get_plan_for_stage(stage)
        return {"plan": plan}
