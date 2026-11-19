class RepairManager:
    """Handles interruptions and self-corrections in voice."""

    def handle_interruption(self, partial_response: str, new_message: str) -> str:
        """When user interrupts, acknowledge and pivot."""
        return f"Ah, perdón. {new_message}"

    def self_correct(self, text: str, correction: str) -> str:
        """Simulate natural self-correction."""
        return f"{text}... bueno, más bien, {correction}"
