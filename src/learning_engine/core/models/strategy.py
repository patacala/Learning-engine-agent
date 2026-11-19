from pydantic import BaseModel, Field

from learning_engine.core.enums import StrategyType


class Tactic(BaseModel):
    name: str
    description: str
    prompt_instruction: str


class Strategy(BaseModel):
    type: StrategyType
    name: str
    description: str
    tactics: list[Tactic] = Field(default_factory=list)
    effectiveness_score: float = 0.5
    attempts: int = 0
