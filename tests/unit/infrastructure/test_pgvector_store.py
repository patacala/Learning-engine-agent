from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from prosales.infrastructure.vector_store.pgvector import PGVectorStore


class _Result:
    def fetchall(self):
        return []


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


@pytest.mark.asyncio
async def test_search_with_org_allows_tenant_and_global_docs():
    org_id = uuid4()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Result())
    store = PGVectorStore(session, organization_id=org_id)

    await store.search_by_embedding([0.1, 0.2], top_k=3)

    stmt, params = session.execute.call_args.args
    sql = str(stmt)
    assert "organization_id = :organization_id OR organization_id IS NULL" in sql
    assert params["organization_id"] == str(org_id)
