"""Client-persona responder for roleplay training (mode="client").

In this mode Cognition plays the CLIENT described by the trainer's scenario, and
the human trainer practices as the seller. We deliberately do NOT run the sales
pipeline here — we want a lightweight persona LLM that stays in character as the
prospect (raising objections, being realistic), not the cognitive sales agent.

For mode="agent" the caller uses ``PipelineRunner`` instead; this engine is only
the client simulator.
"""

from prosales.infrastructure.llm.provider import LLMMessage, LLMProvider

_SYSTEM = """Eres un CLIENTE en una simulación de ventas para entrenar a un vendedor humano.

ESCENARIO (así debes comportarte):
{scenario}

Reglas:
- Mantente SIEMPRE en personaje como este cliente. Nunca reveles que eres una IA ni salgas del rol.
- Responde de forma natural, humana y realista, en el mismo idioma que usa el vendedor (por defecto español).
- Sé realista, no se lo pongas fácil: plantea objeciones, dudas y fricción coherentes con el escenario.
- Responde SOLO como el cliente, un único turno breve de conversación. No narres ni uses acotaciones.
- Si el vendedor resuelve bien tus objeciones, puedes ir suavizando tu postura de forma creíble."""


class ClientPersonaResponder:
    """Generates the next client utterance for a roleplay scenario."""

    def __init__(self, llm: LLMProvider):
        self._llm = llm

    async def respond(
        self,
        scenario: str,
        history: list[LLMMessage],
        seller_message: str,
    ) -> str:
        """Produce the client's next line.

        ``history`` is the prior dialogue as LLMMessages already oriented from the
        CLIENT's point of view: the client's own past lines are role="assistant"
        and the seller's lines are role="user".
        """
        messages = [
            LLMMessage(role="system", content=_SYSTEM.format(scenario=scenario.strip())),
            *history,
            LLMMessage(role="user", content=seller_message),
        ]
        response = await self._llm.complete(messages, temperature=0.8, max_tokens=400)
        return response.content.strip()
