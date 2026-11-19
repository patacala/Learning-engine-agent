import logging
import re
from typing import Any

from learning_engine.core.interfaces.engine import BaseEngine

logger = logging.getLogger(__name__)

# Patterns to remove from LLM output
FORBIDDEN_PATTERNS = [
    r"(?i)como (modelo de lenguaje|inteligencia artificial|IA|AI)",
    r"(?i)as an? (AI|language model|artificial intelligence)",
    r"(?i)no puedo (sentir|experimentar)",
    r"(?i)I (cannot|can't) (feel|experience)",
]


class PostProcessor(BaseEngine):
    """Validates and cleans LLM response."""

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        response = state.get("llm_response", "")

        # Remove AI self-references
        cleaned = response
        for pattern in FORBIDDEN_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned)

        # Remove excessive whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # Remove markdown formatting (not useful for voice)
        cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
        cleaned = re.sub(r"\*(.*?)\*", r"\1", cleaned)
        cleaned = re.sub(r"#{1,6}\s", "", cleaned)

        return {"response": cleaned}
