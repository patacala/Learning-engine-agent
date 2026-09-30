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

from prosales.infrastructure.llm.provider import LLMMessage, LLMProvider

logger = logging.getLogger(__name__)

_CONTEXT_MAX_TOKENS = 100
_CONTEXT_TEMPERATURE = 0.3

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
                content=_USER_TEMPLATE.format(
                    document_content=f"{document_title}\n\n{document_content}",
                    chunk_text=chunk_text,
                ),
            ),
        ],
        max_tokens=_CONTEXT_MAX_TOKENS,
        temperature=_CONTEXT_TEMPERATURE,
    )
    return response.content.strip()


async def contextualize_chunks(
    llm: LLMProvider, title: str, content: str, chunks: list[str]
) -> list[str]:
    """Contextualize every chunk in parallel; returns "{context}\\n\\n{chunk}"
    per chunk — this is the text that gets embedded and stored."""
    if not chunks:
        return []

    contexts = await asyncio.gather(
        *(generate_chunk_context(llm, title, content, chunk) for chunk in chunks),
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
