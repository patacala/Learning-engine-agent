"""Sentence splitter and streaming utilities for voice output."""

import re


def split_into_sentences(text: str, min_length: int = 10) -> list[str]:
    """Split text into natural speech segments for streaming.

    Splits on sentence-ending punctuation and merges short fragments
    to avoid choppy TTS output.
    """
    if not text or not text.strip():
        return []

    parts = re.split(r"(?<=[.!?])\s+", text.strip())

    result: list[str] = []
    buffer = ""
    for part in parts:
        buffer = f"{buffer} {part}".strip() if buffer else part
        if len(buffer) >= min_length:
            result.append(buffer)
            buffer = ""
    if buffer:
        if result:
            result[-1] = f"{result[-1]} {buffer}"
        else:
            result.append(buffer)
    return result
