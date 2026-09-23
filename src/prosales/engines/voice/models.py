from pydantic import BaseModel, Field


class VoiceOutput(BaseModel):
    text: str = ""
    ssml: str = ""
    pause_points: list[int] = Field(default_factory=list)  # char positions for pauses
    backchannel_added: bool = False
