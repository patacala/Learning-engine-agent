class TurnManager:
    """Manages conversation turns and interruptions."""

    def should_yield_turn(self, response_length: int) -> bool:
        """Determine if the response is too long and should pause."""
        return response_length > 200

    def split_for_turns(self, text: str, max_chars: int = 150) -> list[str]:
        """Split long responses into turn-friendly chunks."""
        if len(text) <= max_chars:
            return [text]

        sentences = text.split(". ")
        chunks = []
        current = ""
        for sentence in sentences:
            if len(current) + len(sentence) > max_chars and current:
                chunks.append(current.strip())
                current = sentence
            else:
                current = f"{current}. {sentence}" if current else sentence
        if current:
            chunks.append(current.strip())
        return chunks
