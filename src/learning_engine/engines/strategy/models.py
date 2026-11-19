from pydantic import BaseModel, Field

from learning_engine.core.enums import StrategyType


class StrategySelection(BaseModel):
    strategy_type: str | StrategyType = StrategyType.CONSULTIVE
    tactic_instruction: str = ""
    reasoning: str = ""
    candidates: list[str] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
    switched: bool = False
    tactic_position: int = 0
    tactic_total: int = 1
