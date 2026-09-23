from prosales.core.enums import ConversationPath, Intent

# Intents that can skip the full pipeline
FAST_PATH_INTENTS = {
    Intent.GREETING,
    Intent.FAREWELL,
}

# Intents that always need full pipeline
FULL_PATH_INTENTS = {
    Intent.COMPARISON,
    Intent.OBJECTION,
    Intent.NEGOTIATION,
    Intent.COMPLAINT,
}

FAST_PATH_SKIP_NODES = ["knowledge", "decision", "strategy", "planner"]


def resolve_path(intent: Intent, message_length: int) -> ConversationPath:
    if intent in FAST_PATH_INTENTS and message_length < 50:
        return ConversationPath.FAST_PATH
    return ConversationPath.FULL_PATH
