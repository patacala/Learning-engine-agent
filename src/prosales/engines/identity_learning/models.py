"""DTO for the learned agent style profile."""

from uuid import UUID

from pydantic import BaseModel, Field


class AgentStyleProfile(BaseModel):
    id: UUID | None = None
    agent_version_id: UUID | None = None
    organization_id: UUID | None = None

    empathy_level: float = 0.0
    question_ratio: float = 0.0
    formality: float = 0.0
    avg_response_length: float = 0.0
    technical_level: float = 0.0
    analogy_use: float = 0.0
    example_use: float = 0.0
    humor_use: float = 0.0
    emotional_validation_freq: float = 0.0
    sales_pressure: float = 0.0
    confidence_level: float = 0.0

    microexpressions: list = Field(default_factory=list)  # [{"phrase": str, "frequency": float}]
    linguistic_style: dict = Field(default_factory=dict)
    computed_from_n_conversations: int = 0

    def to_prompt_block(self) -> str:
        """Render the learned style as a natural-language directive for the prompt."""
        lines: list[str] = []
        if self.empathy_level >= 0.6:
            lines.append("Muestra empatía y valida las emociones del cliente antes de responder.")
        if self.question_ratio >= 0.4:
            lines.append("Haz preguntas con frecuencia para descubrir necesidades.")
        if self.formality >= 0.6:
            lines.append("Mantén un tono formal y profesional.")
        elif self.formality and self.formality < 0.4:
            lines.append("Usa un tono cercano e informal.")
        if self.technical_level >= 0.6:
            lines.append("Puedes entrar en detalle técnico cuando aporte valor.")
        if self.analogy_use >= 0.5:
            lines.append("Apóyate en analogías para explicar.")
        if self.example_use >= 0.5:
            lines.append("Usa ejemplos concretos.")
        if self.humor_use >= 0.5:
            lines.append("Un toque de humor ligero es bienvenido.")
        if self.sales_pressure and self.sales_pressure < 0.3:
            lines.append("Evita la presión comercial; acompaña sin presionar.")

        phrases = [m.get("phrase") for m in self.microexpressions if m.get("phrase")][:6]
        if phrases:
            lines.append("Usa expresiones características como: " + ", ".join(f'"{p}"' for p in phrases) + ".")

        if not lines:
            return ""
        return "ESTILO APRENDIDO DEL VENDEDOR:\n" + "\n".join(f"- {l}" for l in lines)
