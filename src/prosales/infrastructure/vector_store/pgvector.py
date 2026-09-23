from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from prosales.infrastructure.llm.clients import get_openai_client


class PGVectorStore:
    """Simple PGVector-based vector store using OpenAI embeddings."""

    def __init__(self, session: AsyncSession, api_key: str | None = None, organization_id=None):
        self.session = session
        self.openai = get_openai_client(api_key)  # shared embedding client
        self.organization_id = organization_id

    async def embed(self, text_content: str) -> list[float]:
        response = await self.openai.embeddings.create(
            model="text-embedding-3-small",
            input=text_content,
        )
        return response.data[0].embedding

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        query_embedding = await self.embed(query)
        return await self.search_by_embedding(query_embedding, top_k)

    async def search_by_embedding(
        self, query_embedding: list[float], top_k: int = 5
    ) -> list[dict]:
        """Search using a precomputed embedding (avoids re-embedding the query)."""
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # Build query with optional organization filter
        where_clauses = ["embedding IS NOT NULL"]
        params = {"embedding": embedding_str, "limit": top_k}

        if self.organization_id is not None:
            where_clauses.append("organization_id = :organization_id")
            params["organization_id"] = str(self.organization_id)

        where_sql = " AND ".join(where_clauses)
        stmt = text(f"""
            SELECT id, title, content, category, metadata,
                   embedding <=> CAST(:embedding AS vector) AS distance
            FROM knowledge_documents
            WHERE {where_sql}
            ORDER BY distance
            LIMIT :limit
        """)
        result = await self.session.execute(stmt, params)
        rows = result.fetchall()
        return [
            {
                "id": str(row.id),
                "title": row.title,
                "content": row.content,
                "category": row.category,
                "metadata": row.metadata,
                "distance": row.distance,
            }
            for row in rows
        ]
