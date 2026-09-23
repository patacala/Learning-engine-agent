import logging
from typing import Any

from prosales.core.interfaces.engine import BaseEngine
from prosales.engines.strategy.catalog import STRATEGY_CATALOG
from prosales.engines.strategy.models import StrategySelection
from prosales.engines.strategy.selector import select_strategy

logger = logging.getLogger(__name__)


class StrategyEngine(BaseEngine):
    """Strategy motor: SELECT → APPLY → EVALUATE → LEARN → SWITCH."""

    def __init__(self, strategy_provider=None):
        self.strategy_provider = strategy_provider

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        analysis = state.get("analysis")
        if not analysis:
            return {"strategy": StrategySelection()}

        ctx = state.get("agent_context")

        # Capability gating: skip if agent lacks negotiation
        if ctx and not ctx.has_agent_capability("negotiation"):
            return {"strategy": StrategySelection(reasoning="negotiation capability disabled")}

        current = state.get("current_strategy")
        attempts = state.get("strategy_attempts", 0)
        tactic_position = state.get("tactic_position", 0)

        # Try agent strategies first
        if self.strategy_provider and ctx:
            catalog = await self.strategy_provider.get(ctx.agent_version_id)
            if catalog:
                return self._select_from_catalog(analysis, catalog, current, tactic_position)

        # Extract episodic data from memory
        episodes = None
        memory = state.get("memory")
        if memory and hasattr(memory, "episodic") and hasattr(memory.episodic, "client_episodes"):
            episodes = memory.episodic.client_episodes if memory.episodic.client_episodes else None

        # Extract conversation stage
        stage = None
        if analysis and hasattr(analysis, "stage") and analysis.stage:
            stage = analysis.stage.stage.value if hasattr(analysis.stage.stage, "value") else str(analysis.stage.stage)

        # Select strategy with all signals
        strategy_type, trace = select_strategy(
            analysis, current, attempts,
            client_episodes=episodes,
            conversation_stage=stage,
        )
        strategy = STRATEGY_CATALOG.get(strategy_type)

        # Multi-tactic: advance position if same strategy, reset if different
        if current and strategy_type.value == current:
            new_position = tactic_position + 1
        else:
            new_position = 0

        # Get tactic instruction at the right position
        instruction = ""
        tactic_total = 1
        if strategy and strategy.tactics:
            tactic_total = len(strategy.tactics)
            clamped_position = min(new_position, tactic_total - 1)
            instruction = strategy.tactics[clamped_position].prompt_instruction
            new_position = clamped_position

        selection = StrategySelection(
            strategy_type=strategy_type,
            tactic_instruction=instruction,
            reasoning=trace.reason,
            candidates=trace.candidates,
            scores=trace.scores,
            switched=trace.switched,
            tactic_position=new_position,
            tactic_total=tactic_total,
        )

        return {
            "strategy": selection,
            "tactic_position": new_position,
        }

    def _select_from_catalog(self, analysis, catalog: dict, current: str | None = None, tactic_position: int = 0) -> dict[str, Any]:
        """Select from agent-defined strategies."""
        intent_str = analysis.intent.intent.value if analysis.intent else ""

        best = None
        for stype, strategy in catalog.items():
            for trigger in strategy.triggers:
                if trigger.get("intent") == intent_str:
                    best = strategy
                    break
            if best:
                break

        if not best:
            best = next(iter(catalog.values()), None)

        if not best:
            return {"strategy": StrategySelection(reasoning="no strategies found")}

        # Multi-tactic for agent catalog
        stype_str = best.strategy_type if isinstance(best.strategy_type, str) else best.strategy_type.value
        if current and stype_str == current:
            new_position = tactic_position + 1
        else:
            new_position = 0

        instruction = ""
        tactic_total = 1
        if best.tactics:
            tactic_total = len(best.tactics)
            clamped = min(new_position, tactic_total - 1)
            instruction = best.tactics[clamped].prompt_instruction
            new_position = clamped

        return {
            "strategy": StrategySelection(
                strategy_type=best.strategy_type,
                tactic_instruction=instruction,
                reasoning=f"agent strategy: {best.name}",
                tactic_position=new_position,
                tactic_total=tactic_total,
            ),
            "tactic_position": new_position,
        }
