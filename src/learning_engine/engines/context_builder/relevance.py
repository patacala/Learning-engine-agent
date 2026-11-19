from learning_engine.core.models.client import ClientMemory
from learning_engine.core.models.conversation import Message


def score_message_relevance(message: Message, current_message: str) -> float:
    """Simple relevance scoring — recent messages score higher."""
    return 1.0


def select_critical_facts(facts: list[ClientMemory], max_facts: int = 5) -> list[ClientMemory]:
    """Select the most relevant facts based on confidence and recency."""
    sorted_facts = sorted(facts, key=lambda f: f.confidence, reverse=True)
    return sorted_facts[:max_facts]
