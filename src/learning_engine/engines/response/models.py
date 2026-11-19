from pydantic import BaseModel, Field


class ResponsePlan(BaseModel):
    """What to say (structure)."""

    main_point: str = ""
    supporting_points: list[str] = Field(default_factory=list)
    call_to_action: str = ""
    max_sentences: int = 3


class GeneratedResponse(BaseModel):
    content: str = ""
    model_used: str = ""
    tokens_used: dict = Field(default_factory=dict)
