import logging
from typing import Any

from prosales.core.enums import Sentiment
from prosales.core.interfaces.engine import BaseEngine
from prosales.core.models.personality import PersonalityLayer, PersonalityProfile
from prosales.engines.personality.layers import (
    CONVERSATION_STYLES,
    DEFAULT_BRAND,
    VOICE_PERSONALITY,
    get_emotion_layer,
)

logger = logging.getLogger(__name__)


class PersonalityEngine(BaseEngine):
    """Multi-layer personality composition."""

    def __init__(self, personality_provider=None):
        self.personality_provider = personality_provider

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        analysis = state.get("analysis")
        ctx = state.get("agent_context")
        identity = state.get("identity")

        # Brand layer — from agent or default
        brand = DEFAULT_BRAND
        voice = VOICE_PERSONALITY
        if self.personality_provider and ctx:
            config = await self.personality_provider.get(ctx.agent_version_id)
            if config:
                brand = PersonalityLayer(
                    traits=config.brand_traits,
                    tone=config.brand_tone,
                    instructions=config.brand_instructions,
                )
                voice = PersonalityLayer(
                    traits=config.voice_traits,
                    tone=config.voice_tone,
                    instructions=config.voice_instructions,
                )

        # Conversation style — from identity or default
        style_key = "consultive"
        if identity and identity.communication_style:
            style_key = identity.communication_style
        conv_style = CONVERSATION_STYLES.get(style_key, CONVERSATION_STYLES["consultive"])

        # Emotion layer (dynamic based on sentiment)
        sentiment = analysis.sentiment.sentiment if analysis else Sentiment.NEUTRAL
        emotion = get_emotion_layer(sentiment)

        # Identity layer — from principles + beliefs
        identity_layer = PersonalityLayer()
        if identity:
            identity_instructions = []
            for p in identity.principles:
                identity_instructions.append(f"[Principle] {p}")
            for b in identity.beliefs:
                identity_instructions.append(f"[Belief] {b}")
            if identity_instructions:
                identity_layer = PersonalityLayer(
                    traits=[],
                    tone="",
                    instructions=identity_instructions,
                )

        profile = PersonalityProfile(
            brand=brand,
            conversation=conv_style,
            voice=voice,
            emotion=emotion,
            identity=identity_layer,
        )

        return {"personality": profile}
