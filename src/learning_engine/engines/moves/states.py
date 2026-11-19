"""Client mental states and move kinds.

A sales move's real objective is to move the client from one mental state to a
better one. These enums keep the vocabulary consistent across extraction,
scoring and retrieval.
"""

from enum import Enum


class ClientState(str, Enum):
    # "Before" states
    CURIOSO = "curioso"
    DESCONFIADO = "desconfiado"
    FRUSTRADO = "frustrado"
    COMPARANDO = "comparando"
    INDECISO = "indeciso"
    LISTO_PARA_COMPRAR = "listo_para_comprar"
    # "After" (result) states
    MAS_INTERESADO = "mas_interesado"
    CONVENCIDO = "convencido"
    TRANQUILO = "tranquilo"
    CONFUNDIDO = "confundido"
    PERDIO_CONFIANZA = "perdio_confianza"

    @classmethod
    def values(cls) -> list[str]:
        return [s.value for s in cls]


# A move's category (metadata, not the memory). Anchored to sales stages.
MOVE_KINDS = [
    "greeting",
    "discovery",
    "needs_diagnosis",
    "value_prop",
    "objection_handling",
    "reframe",
    "social_proof",
    "rapport",
    "urgency",
    "qualification",
    "closing",
    "follow_up",
]

# States that indicate the move improved the client's disposition.
POSITIVE_AFTER_STATES = {
    ClientState.MAS_INTERESADO.value,
    ClientState.CONVENCIDO.value,
    ClientState.TRANQUILO.value,
    ClientState.LISTO_PARA_COMPRAR.value,
}

# States that indicate the move backfired.
NEGATIVE_AFTER_STATES = {
    ClientState.CONFUNDIDO.value,
    ClientState.PERDIO_CONFIANZA.value,
    ClientState.FRUSTRADO.value,
}


def infer_client_state(sentiment: str, stage: str, intent: str) -> str | None:
    """Map the current live analysis (sentiment/stage/intent) to a ClientState.

    Used to retrieve moves whose ``works_when`` conditions match the client's
    current disposition. Returns None when nothing maps confidently.
    """
    sentiment = (sentiment or "").lower()
    stage = (stage or "").lower()
    intent = (intent or "").lower()

    if sentiment == "very_negative":
        return ClientState.FRUSTRADO.value
    if intent == "objection" or (sentiment == "negative" and stage == "objection_handling"):
        return ClientState.DESCONFIADO.value
    if stage in ("closing", "post_sale") and sentiment in ("positive", "very_positive"):
        return ClientState.LISTO_PARA_COMPRAR.value
    if intent == "comparison" or stage == "presentation":
        return ClientState.COMPARANDO.value
    if sentiment in ("positive", "very_positive"):
        return ClientState.MAS_INTERESADO.value
    if sentiment == "negative":
        return ClientState.DESCONFIADO.value
    if intent in ("inquiry", "greeting"):
        return ClientState.CURIOSO.value
    return None
