from pydantic import BaseModel, Field

from learning_engine.core.models.execution import RuleEvaluation


class Action(BaseModel):
    type: str
    params: dict = Field(default_factory=dict)
    priority: int = 0


class Decision(BaseModel):
    actions: list[Action] = Field(default_factory=list)
    reasoning: str = ""
    constraints: list[str] = Field(default_factory=list)
    evaluations: list[RuleEvaluation] = Field(default_factory=list)
