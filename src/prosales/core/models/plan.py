from pydantic import BaseModel


class NextAction(BaseModel):
    description: str
    prompt_instruction: str


class SalesPlan(BaseModel):
    goal: str = ""
    next_action: NextAction | None = None
    fallback: NextAction | None = None
    exit_condition: str = ""
    goal_achieved: bool = False
