import random

from learning_engine.core.enums import Intent

# Backchannels that acknowledge the client is explaining/sharing something
ACKNOWLEDGMENT_ES = ["claro", "entiendo", "sí", "por supuesto"]
ACKNOWLEDGMENT_EN = ["I see", "sure", "of course", "got it"]

# Intents where backchannels make sense (client is explaining, objecting, describing)
BACKCHANNEL_INTENTS = {
    Intent.OBJECTION,
    Intent.COMPLAINT,
    Intent.FOLLOW_UP,
}

# Intents where backchannels should NEVER be used
NO_BACKCHANNEL_INTENTS = {
    Intent.GREETING,
    Intent.FAREWELL,
    Intent.SCHEDULING,
}


class BackchannelManager:
    """Adds conversational backchannels to responses — only when contextually appropriate."""

    def __init__(self, backchannels: list[str] | None = None, probability: float = 0.3):
        self._custom_backchannels = backchannels
        self._default_probability = probability

    def maybe_prepend(
        self,
        text: str,
        language: str = "es",
        intent: Intent | None = None,
        probability: float | None = None,
    ) -> str:
        """Maybe prepend a backchannel. Only when the client was explaining something."""
        # Never on greetings, farewells, etc.
        if intent in NO_BACKCHANNEL_INTENTS:
            return text

        base_prob = probability if probability is not None else self._default_probability

        # Higher chance when client is objecting/complaining
        effective_probability = base_prob
        if intent in BACKCHANNEL_INTENTS:
            effective_probability = max(base_prob, 0.5)

        if random.random() > effective_probability:
            return text

        if self._custom_backchannels:
            backchannels = self._custom_backchannels
        else:
            backchannels = ACKNOWLEDGMENT_ES if language == "es" else ACKNOWLEDGMENT_EN

        bc = random.choice(backchannels)
        return f"{bc.capitalize()}, {text[0].lower()}{text[1:]}"
