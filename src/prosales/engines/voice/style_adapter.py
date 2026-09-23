import random

# Transformations: formal → conversational
FORMAL_TO_NATURAL = {
    "Nuestro vehículo": "Este carro",
    "Le informo que": "Mira,",
    "Cabe mencionar que": "Y algo importante,",
    "Es importante destacar que": "Lo bueno es que",
    "Con gusto le": "Claro, te",
    "Permítame": "Déjame",
    "Le comento": "Te cuento",
}

FILLER_WORDS_ES = ["bueno", "fíjate", "te cuento"]
FILLER_WORDS_EN = ["well", "so", "look"]

# Minimum sentences to start adding fillers (don't add to short responses)
MIN_SENTENCES_FOR_FILLERS = 3


def adapt_to_voice(text: str, language: str = "es") -> str:
    """Transform formal text to natural spoken style."""
    result = text

    # Apply formal → natural replacements
    for formal, natural in FORMAL_TO_NATURAL.items():
        result = result.replace(formal, natural)

    # Only add fillers to longer responses (3+ sentences)
    sentences = result.split(". ")
    if len(sentences) < MIN_SENTENCES_FOR_FILLERS:
        return result

    fillers = FILLER_WORDS_ES if language == "es" else FILLER_WORDS_EN
    adapted = []
    for i, sentence in enumerate(sentences):
        # Only mid-response sentences, 20% chance, skip first and last
        if 0 < i < len(sentences) - 1 and random.random() < 0.2 and sentence:
            filler = random.choice(fillers)
            sentence = f"{filler.capitalize()}, {sentence[0].lower()}{sentence[1:]}"
        adapted.append(sentence)

    return ". ".join(adapted)
