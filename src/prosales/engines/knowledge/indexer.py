import logging
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from prosales.infrastructure.database.models import KnowledgeDocumentModel
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
    """Index a document with its embedding."""
    vector_store = PGVectorStore(session)
    embedding = await vector_store.embed(content[:8000])

    doc = KnowledgeDocumentModel(
        id=uuid4(),
        title=title,
        content=content,
        category=category,
        organization_id=organization_id,
        metadata_=metadata or {},
        embedding=embedding,
    )
    session.add(doc)
    await session.flush()
    logger.info("Indexed document: %s", title)
    return doc
