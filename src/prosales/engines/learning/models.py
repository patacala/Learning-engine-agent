from pydantic import BaseModel, Field


class LearningInsight(BaseModel):
    category: str = ""
    insight: str = ""
    confidence: float = 0.0
    applied: bool = False
