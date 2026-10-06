import logging
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from prosales.di.container import create_analyzer_llm
from prosales.engines.knowledge.chunker import ENCODING, MAX_EMBED_TOKENS, chunk_document
from prosales.engines.knowledge.contextualizer import contextualize_chunks
from prosales.infrastructure.database.connection import async_session_factory
from prosales.infrastructure.database.models import KnowledgeChunkModel, KnowledgeDocumentModel
from prosales.infrastructure.vector_store.pgvector import PGVectorStore

logger = logging.getLogger(__name__)


async def index_document(
    session: AsyncSession | None = None,
    *,
    title: str,
    content: str,
    category: str,
    organization_id=None,
    metadata: dict | None = None,
) -> KnowledgeDocumentModel:
    """Index a document: split, contextualize, embed, then store.

    Chunk context and embeddings are computed before any insert. Passing no
    session opens a short one only for that write, so a long document does
    not sit in an idle transaction while the LLM runs."""
    # Postgres rejects NUL in text. A PDF/docx extraction can contain one
    # and then only that entry fails.
    content = content.replace("\x00", "")
    prepared = await _prepare_chunks(title, content)
    if session is not None:
        return await _persist(
            session, title, content, category, organization_id, metadata, prepared
        )
    async with async_session_factory() as owned:
        async with owned.begin():
            return await _persist(
                owned, title, content, category, organization_id, metadata, prepared
            )


async def _prepare_chunks(title: str, content: str) -> list[tuple[str, int, list[float]]]:
    raw_chunks = chunk_document(content)
    if not raw_chunks:
        logger.warning("No content to chunk for document: %s", title)
        return []

    contextualized = await contextualize_chunks(create_analyzer_llm(), title, content, raw_chunks)
    texts: list[str] = []
    token_counts: list[int] = []
    for index, chunk_text in enumerate(contextualized):
        tokens = ENCODING.encode(chunk_text)
        if len(tokens) > MAX_EMBED_TOKENS:
            logger.warning("Chunk %d of %s exceeded MAX_EMBED_TOKENS, truncating", index, title)
            tokens = tokens[:MAX_EMBED_TOKENS]
            chunk_text = ENCODING.decode(tokens)
        texts.append(chunk_text.replace("\x00", ""))
        token_counts.append(len(tokens))

    # embed_many does not touch the session. Don't check a connection out
    # while waiting on the embedding API.
    embeddings = await PGVectorStore().embed_many(texts)
    return list(zip(texts, token_counts, embeddings))


async def _persist(
    session: AsyncSession,
    title: str,
    content: str,
    category: str,
    organization_id,
    metadata: dict | None,
    prepared: list[tuple[str, int, list[float]]],
) -> KnowledgeDocumentModel:
    doc = KnowledgeDocumentModel(
        id=uuid4(),
        title=title[:500],
        content=content,
        category=category[:100],
        organization_id=organization_id,
        metadata_=metadata or {},
    )
    session.add(doc)
    for index, (chunk_text, token_count, embedding) in enumerate(prepared):
        session.add(
            KnowledgeChunkModel(
                id=uuid4(),
                document_id=doc.id,
                organization_id=organization_id,
                chunk_index=index,
                content=chunk_text,
                embedding=embedding,
                token_count=token_count,
            )
        )
    await session.flush()
    logger.info("Indexed document %s into %d chunk(s)", title, len(prepared))
    return doc
