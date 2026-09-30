import logging
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from prosales.di.container import create_analyzer_llm
from prosales.engines.knowledge.chunker import ENCODING, MAX_EMBED_TOKENS, chunk_document
from prosales.engines.knowledge.contextualizer import contextualize_chunks
from prosales.infrastructure.database.models import KnowledgeChunkModel, KnowledgeDocumentModel
from prosales.infrastructure.vector_store.pgvector import PGVectorStore

logger = logging.getLogger(__name__)


async def index_document(
    session: AsyncSession,
    title: str,
    content: str,
    category: str,
    organization_id=None,
    metadata: dict | None = None,
) -> KnowledgeDocumentModel:
    """Index a document: persist the source row, split it into chunks,
    contextualize each one (Anthropic's Contextual Retrieval — see
    contextualizer.py), embed, and store each chunk separately so retrieval
    returns small, complete, fact-sized units instead of one embedding for
    the whole document."""
    doc = KnowledgeDocumentModel(
        id=uuid4(),
        title=title,
        content=content,
        category=category,
        organization_id=organization_id,
        metadata_=metadata or {},
    )
    session.add(doc)

    raw_chunks = chunk_document(content)
    if not raw_chunks:
        logger.warning("No content to chunk for document: %s", title)
        await session.flush()
        return doc

    # Instantiate the LLM internally (same pattern PGVectorStore already uses
    # for its embedding client) so no caller needs to change.
    contextualized = await contextualize_chunks(create_analyzer_llm(), title, content, raw_chunks)

    vector_store = PGVectorStore(session)
    for index, chunk_text in enumerate(contextualized):
        tokens = ENCODING.encode(chunk_text)
        if len(tokens) > MAX_EMBED_TOKENS:
            # Defensive last resort: chunker + contextualizer should never
            # produce this, but never let one pathological chunk crash
            # indexing or exceed the embedding model's real 8191-token ceiling.
            logger.warning("Chunk %d of %s exceeded MAX_EMBED_TOKENS, truncating", index, title)
            chunk_text = ENCODING.decode(tokens[:MAX_EMBED_TOKENS])

        embedding = await vector_store.embed(chunk_text)
        session.add(
            KnowledgeChunkModel(
                id=uuid4(),
                document_id=doc.id,
                organization_id=organization_id,
                chunk_index=index,
                content=chunk_text,
                embedding=embedding,
                token_count=len(tokens),
            )
        )

    await session.flush()
    logger.info("Indexed document %s into %d chunk(s)", title, len(contextualized))
    return doc
