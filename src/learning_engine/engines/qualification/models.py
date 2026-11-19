"""DTO for the qualification result."""

from pydantic import BaseModel

from learning_engine.core.enums import Outcome


class QualificationResult(BaseModel):
    outcome: Outcome = Outcome.OPEN
    confidence: float = 0.0
    is_terminal: bool = False
    reason: str = ""
