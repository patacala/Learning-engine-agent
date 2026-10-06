from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from prosales.core.exceptions import LLMError
from prosales.infrastructure.llm.clients import get_openai_client


class PGVectorStore:
    """Simple PGVector-based vector store using OpenAI embeddings."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        api_key: str | None = None,
        organization_id=None,
    ):
        self.session = session
        self.openai = get_openai_client(api_key)  # shared embedding client
        self.organization_id = organization_id

    async def embed(self, text_content: str) -> list[float]:
        vectors = await self.embed_many([text_content])
        return vectors[0]

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Embed every text. One request covers a long document's chunks
        (text-embedding-3-small accepts up to 2048 inputs); a single
        143KB markdown is a few hundred chunks and must not be N sequential
        HTTP calls."""
        if not texts:
            return []

        # 128 inputs stays far under the 300k-token request ceiling when each
        # input is a ~300-token chunk.
        batch_size = 128
        out: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            response = await self.openai.embeddings.create(
                model="text-embedding-3-small",
                input=batch,
            )
            ordered = sorted(response.data, key=lambda item: item.index)
            out.extend(item.embedding for item in ordered)
        if len(out) != len(texts):
            raise LLMError(f"Embedding API returned {len(out)} vectors for {len(texts)} chunks")
        return out

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        query_embedding = await self.embed(query)
        return await self.search_by_embedding(query_embedding, top_k)

    async def search_by_embedding(
        self, query_embedding: list[float], top_k: int = 5, per_document_limit: int = 2
    ) -> list[dict]:
        """Search chunks using a precomputed embedding (avoids re-embedding
        the query). Over-fetches a wider candidate pool (top_k * 3) ordered
        by distance, then walks it keeping at most `per_document_limit`
        chunks per parent document, so a single dense source document can't
        occupy every result slot."""
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # Tenant isolation:
        # - Tenant context sees its own docs plus global/template docs.
        # - No tenant context sees only global docs. Never fall back to all docs.
        where_clauses = ["c.embedding IS NOT NULL"]
        params = {"embedding": embedding_str, "limit": top_k * 3}

        if self.organization_id is not None:
            where_clauses.append(
                "(c.organization_id = :organization_id OR c.organization_id IS NULL)"
            )
            params["organization_id"] = str(self.organization_id)
        else:
            where_clauses.append("c.organization_id IS NULL")

        where_sql = " AND ".join(where_clauses)
        stmt = text(f"""
            SELECT c.id AS chunk_id, c.document_id AS document_id, c.chunk_index,
                   d.title, c.content, d.category, d.metadata,
                   c.embedding <=> CAST(:embedding AS vector) AS distance
            FROM knowledge_chunks c
            JOIN knowledge_documents d ON d.id = c.document_id
            WHERE {where_sql}
            ORDER BY distance
            LIMIT :limit
        """)
        result = await self.session.execute(stmt, params)
        rows = result.fetchall()

        per_doc_count: dict[str, int] = {}
        out: list[dict] = []
        for row in rows:
            doc_id = str(row.document_id)
            if per_doc_count.get(doc_id, 0) >= per_document_limit:
                continue
            per_doc_count[doc_id] = per_doc_count.get(doc_id, 0) + 1
            out.append(
                {
                    "id": str(row.chunk_id),
                    "document_id": doc_id,
                    "chunk_index": row.chunk_index,
                    "title": row.title,
                    "content": row.content,
                    "category": row.category,
                    "metadata": row.metadata,
                    "distance": row.distance,
                }
            )
            if len(out) >= top_k:
                break

        return out
