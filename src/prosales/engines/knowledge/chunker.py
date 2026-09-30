"""Structure-aware chunking for Knowledge/RAG.

Splits a document's Markdown content into small, fact-sized chunks:
1. Split on Markdown headers (#, ##, ###) so a whole logical section (e.g.
   one department's full week of hours) stays together when it fits.
2. Any section still over CHUNK_TARGET_TOKENS gets sub-split by a sliding
   token window with overlap; its own section header is prepended to every
   sub-chunk so a lone fragment (e.g. "Saturday: 9:00 am - 6:00 pm") doesn't
   lose which department/section it belongs to. LLM-generated context (full
   Contextual Retrieval) is added separately, see contextualizer.py.

Sized in tokens, not characters: text-embedding-3-small's real ceiling is
8191 tokens, and this org's documents are short structured references
(business hours, vehicle specs) where small chunks help fact-lookup queries
specifically — this was the root cause of a production hallucination bug
(see engines/response/planner.py).
"""

import re

import tiktoken

CHUNK_TARGET_TOKENS = 300
CHUNK_OVERLAP_TOKENS = 45  # ~15%
MIN_CHUNK_TOKENS = 20
MAX_EMBED_TOKENS = 8000  # safety margin below text-embedding-3-small's 8191 ceiling

ENCODING = tiktoken.get_encoding("cl100k_base")

_HEADER_RE = re.compile(r"^(#{1,6})\s+.*$", re.MULTILINE)


def count_tokens(text: str) -> int:
    return len(ENCODING.encode(text))


def chunk_document(content: str) -> list[str]:
    """Split document content into an ordered list of chunk texts."""
    content = content.strip()
    if not content:
        return []

    sections = _split_sections(content)
    chunks: list[str] = []
    for header, body in sections:
        section_text = f"{header}\n{body}".strip() if header else body.strip()
        if not section_text:
            continue
        if count_tokens(section_text) <= CHUNK_TARGET_TOKENS:
            chunks.append(section_text)
        else:
            chunks.extend(_sliding_window_split(body, header))

    return _merge_tiny_trailing_chunks(chunks)


def _split_sections(content: str) -> list[tuple[str | None, str]]:
    """Split on Markdown headers; a document with no headers is one section."""
    matches = list(_HEADER_RE.finditer(content))
    if not matches:
        return [(None, content)]

    sections: list[tuple[str | None, str]] = []
    if matches[0].start() > 0:
        sections.append((None, content[: matches[0].start()]))
    for i, m in enumerate(matches):
        header = m.group(0)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        sections.append((header, content[start:end]))
    return sections


def _sliding_window_split(body: str, header: str | None) -> list[str]:
    tokens = ENCODING.encode(body)
    stride = CHUNK_TARGET_TOKENS - CHUNK_OVERLAP_TOKENS
    out: list[str] = []
    i = 0
    while i < len(tokens):
        window = tokens[i : i + CHUNK_TARGET_TOKENS]
        text = ENCODING.decode(window).strip()
        if text:
            out.append(f"{header}\n{text}".strip() if header else text)
        i += stride
    return out


def _merge_tiny_trailing_chunks(chunks: list[str]) -> list[str]:
    merged: list[str] = []
    for c in chunks:
        if merged and count_tokens(c) < MIN_CHUNK_TOKENS:
            merged[-1] = f"{merged[-1]}\n{c}"
        else:
            merged.append(c)
    return merged
