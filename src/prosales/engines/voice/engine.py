import logging
from typing import Any

from prosales.core.interfaces.engine import BaseEngine
from prosales.engines.voice.backchannel import BackchannelManager
from prosales.engines.voice.models import VoiceOutput
from prosales.engines.voice.pause_manager import PauseManager
from prosales.engines.voice.style_adapter import adapt_to_voice
from prosales.engines.voice.turn_manager import TurnManager

logger = logging.getLogger(__name__)


class VoiceLayerEngine(BaseEngine):
    """Transforms text into natural speech."""

    def __init__(self, voice_provider=None):
        self.voice_provider = voice_provider
        self.backchannel = BackchannelManager()
        self.pause_manager = PauseManager()
        self.turn_manager = TurnManager()

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        response = state.get("response", "")
        analysis = state.get("analysis")
        ctx = state.get("agent_context")
        language = analysis.language.language if analysis else "es"
        intent = analysis.intent.intent if analysis else None

        # Capability gating: passthrough if agent lacks voice
        if ctx and not ctx.has_agent_capability("voice"):
            return {"voice_output": VoiceOutput(text=response), "response": response}

        # Load voice config from agent
        voice_config = None
        if self.voice_provider and ctx:
            voice_config = await self.voice_provider.get(ctx.agent_version_id)

        # 1. Adapt style for voice
        voiced = adapt_to_voice(response, language)

        # 2. Maybe add backchannel (context-aware)
        if voice_config:
            backchannels = voice_config.backchannels_es if language == "es" else voice_config.backchannels_en
            self.backchannel = BackchannelManager(
                backchannels=backchannels,
                probability=voice_config.backchannel_probability,
            )
        voiced = self.backchannel.maybe_prepend(voiced, language, intent=intent)

        # 3. Add pauses
        _, pause_points = self.pause_manager.add_pauses(voiced)

        # 4. Generate SSML
        enable_ssml = voice_config.enable_ssml if voice_config else True
        ssml = self.pause_manager.to_ssml(voiced) if enable_ssml else ""

        output = VoiceOutput(
            text=voiced,
            ssml=ssml,
            pause_points=pause_points,
        )

        return {"voice_output": output, "response": voiced}
