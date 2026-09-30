from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from prosales.engines.knowledge.indexer import index_document
from prosales.infrastructure.database.models import KnowledgeChunkModel, KnowledgeDocumentModel


@pytest.mark.asyncio
async def test_index_document_creates_one_chunk_row_per_chunk():
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    # Realistically sized sections (like the real Business Hours doc's
    # per-department day lists) — short enough to stay whole, but long
    # enough not to trip the tiny-fragment merge floor (MIN_CHUNK_TOKENS).
    dealership_days = "\n".join(f"{d}: 9:00 am - 7:00 pm" for d in
                                 ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
    service_days = "\n".join(f"{d}: 7:30 am - 7:00 pm" for d in
                              ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
    content = f"## Dealership\n\n{dealership_days}\n\n## Service\n\n{service_days}"

    with (
        patch(
            "prosales.engines.knowledge.indexer.contextualize_chunks",
            AsyncMock(
                side_effect=lambda llm, title, content, chunks: [f"ctx: {c}" for c in chunks]
            ),
        ),
        patch("prosales.engines.knowledge.indexer.create_analyzer_llm", return_value=MagicMock()),
        patch(
            "prosales.engines.knowledge.indexer.PGVectorStore.embed",
            AsyncMock(return_value=[0.1] * 1536),
        ),
    ):
        doc = await index_document(session, title="Hours", content=content, category="general")

    assert isinstance(doc, KnowledgeDocumentModel)
    assert not hasattr(doc, "embedding")  # embedding moved off the parent document

    added = [call.args[0] for call in session.add.call_args_list]
    doc_rows = [a for a in added if isinstance(a, KnowledgeDocumentModel)]
    chunk_rows = [a for a in added if isinstance(a, KnowledgeChunkModel)]

    assert len(doc_rows) == 1
    assert len(chunk_rows) == 2  # one per "##" section, both short enough to stay whole
    assert [c.chunk_index for c in chunk_rows] == [0, 1]
    assert all(c.document_id == doc.id for c in chunk_rows)
    assert all(c.content.startswith("ctx: ") for c in chunk_rows)  # contextualized
    assert all(c.embedding == [0.1] * 1536 for c in chunk_rows)


@pytest.mark.asyncio
async def test_index_document_empty_content_still_creates_document_no_chunks():
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    doc = await index_document(session, title="Empty", content="   ", category="general")

    added = [call.args[0] for call in session.add.call_args_list]
    assert len(added) == 1
    assert isinstance(added[0], KnowledgeDocumentModel)
    assert doc is added[0]
