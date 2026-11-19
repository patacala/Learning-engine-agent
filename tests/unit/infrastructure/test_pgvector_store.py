from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from learning_engine.infrastructure.vector_store.pgvector import PGVectorStore


class _Result:
    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchall(self):
        return self._rows


def _row(document_id, distance, chunk_index=0):
    return SimpleNamespace(
        chunk_id=uuid4(),
        document_id=document_id,
        chunk_index=chunk_index,
        title="Business Hours",
        content="chunk text",
        category="general",
        metadata={},
        distance=distance,
    )


@pytest.mark.asyncio
async def test_search_without_org_filters_to_global_docs_only():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Result())
    store = PGVectorStore(session)

    await store.search_by_embedding([0.1, 0.2], top_k=3)

    stmt, params = session.execute.call_args.args
    sql = str(stmt)
    assert "organization_id IS NULL" in sql
    assert "organization_id = :organization_id" not in sql
    assert "organization_id" not in params
    assert "FROM knowledge_chunks c" in sql
    assert "JOIN knowledge_documents d ON d.id = c.document_id" in sql


@pytest.mark.asyncio
async def test_search_with_org_allows_tenant_and_global_docs():
    org_id = uuid4()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Result())
    store = PGVectorStore(session, organization_id=org_id)

    await store.search_by_embedding([0.1, 0.2], top_k=3)

    stmt, params = session.execute.call_args.args
    sql = str(stmt)
    assert "c.organization_id = :organization_id OR c.organization_id IS NULL" in sql
    assert params["organization_id"] == str(org_id)


@pytest.mark.asyncio
async def test_search_caps_chunks_per_parent_document():
    """One dense document's chunks shouldn't fill every result slot."""
    doc_a, doc_b = uuid4(), uuid4()
    # 3 chunks of doc_a (closest) then 2 of doc_b, ordered by distance.
    rows = [
        _row(doc_a, 0.1, chunk_index=0),
        _row(doc_a, 0.2, chunk_index=1),
        _row(doc_a, 0.3, chunk_index=2),
        _row(doc_b, 0.4, chunk_index=0),
        _row(doc_b, 0.5, chunk_index=1),
    ]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Result(rows))
    store = PGVectorStore(session)

    results = await store.search_by_embedding([0.1, 0.2], top_k=6, per_document_limit=2)

    # At most 2 chunks per document, so doc_a's 3rd chunk is dropped even
    # though it's closer than either of doc_b's chunks.
    assert len(results) == 4
    doc_ids = [r["document_id"] for r in results]
    assert doc_ids.count(str(doc_a)) == 2
    assert doc_ids.count(str(doc_b)) == 2
