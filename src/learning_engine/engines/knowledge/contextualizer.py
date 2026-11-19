"""LLM-generated context for each chunk — Anthropic's Contextual Retrieval.

A chunk taken out of its document can be ambiguous (e.g. "Saturday: 9:00 am -
6:00 pm" doesn't say which department). This generates a short, chunk-specific
blurb from the whole document as reference, and prepends it to the chunk
before embedding AND before storing — so it helps both retrieval (better
embedding) and the final response synthesis (the LLM sees the disambiguated
fact, not a bare fragment).

https://www.anthropic.com/engineering/contextual-retrieval
"""

import asyncio
import logging

from learning_engine.engines.knowledge.chunker import ENCODING, count_tokens
from learning_engine.infrastructure.llm.provider import LLMMessage, LLMProvider

logger = logging.getLogger(__name__)

_CONTEXT_MAX_TOKENS = 100
_CONTEXT_TEMPERATURE = 0.3
# Anthropic's template passes the whole document. That stays for short
# references. A long file (a 143KB markdown is tens of thousands of tokens
# and hundreds of chunks) cannot be repeated in full on every call — the
# sync dies before any chunk is stored. Above this budget each call gets
# the enclosing section instead, which is the part that says what the
# fragment belongs to. The stored result is still "{context}\\n\\n{chunk}".
_FULL_DOC_TOKEN_BUDGET = 6_000
_EXCERPT_TOKEN_BUDGET = 2_000
_CONTEXT_CONCURRENCY = 16

_SYSTEM_PROMPT = (
    "You situate a document fragment within its source document so it can be "
    "retrieved correctly later. Respond with ONLY the short context — no "
    "preamble, no quotes, 1-2 sentences."
)

_USER_TEMPLATE = """<document>
{document_content}
</document>

Here is a chunk from that document:
<chunk>
{chunk_text}
</chunk>

Give a short context (1-2 sentences) situating this chunk within the \
overall document, so it can be found by a search on the topic it covers."""


async def generate_chunk_context(
    llm: LLMProvider, document_title: str, document_content: str, chunk_text: str
) -> str:
    """One short, chunk-specific context blurb, generated from the whole
    document as reference (per Anthropic's Contextual Retrieval template)."""
    response = await llm.complete(
        messages=[
            LLMMessage(role="system", content=_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=_USER_TEMPLATE.replace(
                    "{document_content}", f"{document_title}\n\n{document_content}"
                ).replace("{chunk_text}", chunk_text),
            ),
        ],
        max_tokens=_CONTEXT_MAX_TOKENS,
        temperature=_CONTEXT_TEMPERATURE,
    )
    return response.content.strip()


def _source_for_chunk(content: str, chunk: str, full_tokens: int) -> str:
    """Document text the context prompt may see. The whole document when it
    fits; otherwise the section that contains this chunk."""
    if full_tokens <= _FULL_DOC_TOKEN_BUDGET:
        return content
    return _excerpt_around_chunk(content, chunk)


def _excerpt_around_chunk(content: str, chunk: str) -> str:
    probe = _probe(chunk)
    pos = content.find(probe) if probe else -1
    if pos < 0:
        pos = 0
    header_at = content.rfind("\n#", 0, max(pos, 1))
    start = 0 if header_at < 0 else header_at + 1
    next_header = content.find("\n#", pos + max(len(probe), 1))
    end = len(content) if next_header < 0 else next_header
    section = content[start:end].strip() or chunk
    if count_tokens(section) <= _EXCERPT_TOKEN_BUDGET:
        return section
    return ENCODING.decode(ENCODING.encode(section)[:_EXCERPT_TOKEN_BUDGET])


def _probe(chunk: str) -> str:
    text = chunk.strip()
    if text.startswith("#"):
        parts = text.split("\n", 1)
        text = parts[1].strip() if len(parts) > 1 else ""
    return text[:80]


async def contextualize_chunks(
    llm: LLMProvider, title: str, content: str, chunks: list[str]
) -> list[str]:
    """Contextualize every chunk; returns "{context}\\n\\n{chunk}" per chunk.
    That string is what gets embedded and stored."""
    if not chunks:
        return []

    source_tokens = count_tokens(content)
    sources = [_source_for_chunk(content, chunk, source_tokens) for chunk in chunks]
    semaphore = asyncio.Semaphore(_CONTEXT_CONCURRENCY)

    async def _one(chunk: str, source: str) -> str:
        async with semaphore:
            return await generate_chunk_context(llm, title, source, chunk)

    contexts = await asyncio.gather(
        *(_one(chunk, source) for chunk, source in zip(chunks, sources)),
        return_exceptions=True,
    )

    out: list[str] = []
    for chunk, context in zip(chunks, contexts):
        if isinstance(context, Exception):
            # Never let a contextualization failure block indexing — fall
            # back to the plain chunk, which is still fully usable on its
            # own (structure-aware splitting already carries its section
            # header — see chunker.py).
            logger.warning("Chunk context generation failed, using plain chunk: %s", context)
            out.append(chunk)
        else:
            out.append(f"{context}\n\n{chunk}")
    return out
