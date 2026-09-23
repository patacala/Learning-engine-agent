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
