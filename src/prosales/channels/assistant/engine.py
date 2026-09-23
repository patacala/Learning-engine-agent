"""Neutral assistant responder — the app's default conversational state.

A lightweight sales-training coach that just *talks*: it helps the user prepare
and practice selling, answers questions, and can *suggest* running a roleplay,
but it never triggers anything. Unlike roleplay's ``ClientPersonaResponder``,
the assistant IS the "assistant" role — a normal conversation, not a persona
speaking as the client. It does NOT run the sales pipeline and never learns.
"""

from prosales.infrastructure.llm.provider import LLMMessage, LLMProvider

_SYSTEM = """Eres un asistente y coach de entrenamiento de ventas. Tu rol es conversar \
de forma natural para ayudar al usuario a prepararse y practicar sus ventas.

You are a sales-training assistant and coach. Converse naturally to help the user \
prepare and practice their selling.

Reglas / Rules:
- Responde SIEMPRE en el mismo idioma que usa el usuario (español o inglés). \
Always reply in the same language the user is writing in.
- Sé cercano, claro y práctico: da consejos accionables sobre técnicas de venta, \
manejo de objeciones, discovery, cierre y seguimiento. Be warm, clear and practical.
- Puedes SUGERIR practicar: "podemos hacer un roleplay cuando quieras" / "we can do a \
roleplay whenever you'd like", pero NO inicias nada: el cambio de modo lo decide la app. \
Never claim to have started a roleplay or any other action.
- No evalúas ni calificas conversaciones reales de ventas; esto es solo conversación de \
apoyo. You are not scoring or analyzing real sales calls here — this is just supportive chat.
- Mantén tus respuestas conversacionales y del largo apropiado; no te extiendas de más."""


class AssistantResponder:
    """Generates the assistant's next reply for a neutral coaching session."""

    def __init__(self, llm: LLMProvider):
        self._llm = llm

    async def respond(self, history: list[LLMMessage], text: str) -> str:
        """Produce the assistant's next line.

        ``history`` is the prior dialogue as LLMMessages with standard roles
        (the user's lines are role="user", the assistant's are role="assistant").
        """
        messages = [
            LLMMessage(role="system", content=_SYSTEM),
            *history,
            LLMMessage(role="user", content=text),
        ]
        response = await self._llm.complete(messages, temperature=0.7, max_tokens=800)
        return response.content.strip()
