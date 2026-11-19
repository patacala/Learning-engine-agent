"""PersonalityProfile.compile_static_*/compile_emotion_* — the split that
makes OpenAI prompt caching possible (Fase 4 latency, 2026-09-24). Before
this, compile_tone()/compile_instructions() mixed the emotion layer (varies
per turn by sentiment) into the same string as the 4 static layers, so the
system prompt built from it never had a stable prefix — verified empirically
that two turns of the same agent diverged at character 148."""

from learning_engine.core.models.personality import PersonalityLayer, PersonalityProfile


def _profile(emotion_tone="Empático", emotion_instructions=None):
    return PersonalityProfile(
        brand=PersonalityLayer(tone="Cálido", instructions=["Sé cálido"]),
        conversation=PersonalityLayer(tone="Consultivo", instructions=["Escucha primero"]),
        voice=PersonalityLayer(tone="Natural", instructions=["Habla natural"]),
        emotion=PersonalityLayer(tone=emotion_tone, instructions=emotion_instructions or ["Muestra empatía"]),
        identity=PersonalityLayer(tone="", instructions=["[Principle] Honestidad"]),
    )


def test_static_tone_excludes_emotion():
    profile = _profile(emotion_tone="Empático y comprensivo")
    assert "Empático y comprensivo" not in profile.compile_static_tone()
    assert profile.compile_static_tone() == "Cálido, Consultivo, Natural"


def test_static_instructions_exclude_emotion():
    profile = _profile(emotion_instructions=["Muestra comprensión genuina"])
    assert "Muestra comprensión genuina" not in profile.compile_static_instructions()
    assert profile.compile_static_instructions() == [
        "Sé cálido", "Escucha primero", "Habla natural", "[Principle] Honestidad",
    ]


def test_emotion_methods_return_only_emotion_layer():
    profile = _profile(emotion_tone="Entusiasta", emotion_instructions=["Comparte el entusiasmo"])
    assert profile.compile_emotion_tone() == "Entusiasta"
    assert profile.compile_emotion_instructions() == ["Comparte el entusiasmo"]


def test_static_split_is_identical_across_different_emotions():
    """The actual regression this exists to prevent: two profiles differing
    ONLY in emotion (as happens turn to turn from sentiment) must produce a
    byte-identical static_tone/static_instructions — that's what lets the
    system_msg built from them stay a stable, cacheable prefix."""
    negative = _profile(emotion_tone="Empático y comprensivo", emotion_instructions=["No minimices sus preocupaciones."])
    positive = _profile(emotion_tone="Entusiasta pero no exagerado", emotion_instructions=["Comparte el entusiasmo del cliente."])

    assert negative.compile_static_tone() == positive.compile_static_tone()
    assert negative.compile_static_instructions() == positive.compile_static_instructions()
    # ... but the old, unsplit methods still legitimately differ (that's the bug being fixed around).
    assert negative.compile_tone() != positive.compile_tone()
