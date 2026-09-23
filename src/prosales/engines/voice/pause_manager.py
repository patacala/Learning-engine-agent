import re


class PauseManager:
    """Inserts natural pauses into speech."""

    PAUSE_AFTER = [",", ".", ":", ";", "?", "!"]
    SSML_PAUSE = '<break time="{ms}ms"/>'

    def add_pauses(self, text: str) -> tuple[str, list[int]]:
        """Returns text with SSML pauses and pause positions."""
        pause_points = []
        for i, char in enumerate(text):
            if char in self.PAUSE_AFTER:
                pause_points.append(i)
        return text, pause_points

    def to_ssml(self, text: str) -> str:
        """Convert text to SSML with natural pauses."""
        ssml = text
        # Add short pause after commas
        ssml = ssml.replace(", ", f', {self.SSML_PAUSE.format(ms=200)} ')
        # Add medium pause after periods
        ssml = re.sub(r'\. ', f'. {self.SSML_PAUSE.format(ms=400)} ', ssml)
        return f"<speak>{ssml}</speak>"
