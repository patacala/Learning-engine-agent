from pydantic import BaseModel, Field


class PersonalityLayer(BaseModel):
    traits: list[str] = Field(default_factory=list)
    tone: str = ""
    instructions: list[str] = Field(default_factory=list)


class PersonalityProfile(BaseModel):
    """Multi-layer personality composition for current moment."""

    brand: PersonalityLayer = Field(default_factory=PersonalityLayer)
    conversation: PersonalityLayer = Field(default_factory=PersonalityLayer)
    voice: PersonalityLayer = Field(default_factory=PersonalityLayer)
    emotion: PersonalityLayer = Field(default_factory=PersonalityLayer)
    identity: PersonalityLayer = Field(default_factory=PersonalityLayer)

    def compile_instructions(self) -> list[str]:
        """Merge all layers into a single instruction set."""
        instructions = []
        for layer in [self.brand, self.conversation, self.voice, self.emotion, self.identity]:
            instructions.extend(layer.instructions)
        return instructions

    def compile_tone(self) -> str:
        tones = [l.tone for l in [self.brand, self.conversation, self.voice, self.emotion, self.identity] if l.tone]
        return ", ".join(tones)

    # --- static/dynamic split (Fase 4 latency: prompt caching) -----------------
    # `emotion` is the only layer that varies per turn (derived from the
    # client's detected sentiment each message — see
    # engines/personality/layers.py:get_emotion_layer, 3 discrete values).
    # brand/conversation/voice/identity are fixed per agent_version_id. Mixing
    # emotion into compile_tone()/compile_instructions() above means the
    # combined string differs almost every turn — verified empirically
    # (2026-09-24): 2 turns of the same agent/conversation diverged at
    # character 148. OpenAI's automatic prompt caching needs an exact-matching
    # prefix (min 1024 tokens) to ever kick in; these split versions let
    # prompt_builder.py keep the static block in one message (cacheable
    # across turns) and the emotion-driven mood in the per-turn dynamic one.

    def compile_static_tone(self) -> str:
        tones = [l.tone for l in [self.brand, self.conversation, self.voice, self.identity] if l.tone]
        return ", ".join(tones)

    def compile_static_instructions(self) -> list[str]:
        instructions = []
        for layer in [self.brand, self.conversation, self.voice, self.identity]:
            instructions.extend(layer.instructions)
        return instructions

    def compile_emotion_tone(self) -> str:
        return self.emotion.tone

    def compile_emotion_instructions(self) -> list[str]:
        return list(self.emotion.instructions)
