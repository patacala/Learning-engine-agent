import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from learning_engine.core.exceptions import LLMError
from learning_engine.infrastructure.llm.clients import get_openai_client

logger = logging.getLogger(__name__)

# Columns every retrieval path selects, so vector and lexical rows share a shape.
_CHUNK_COLUMNS = (
    "c.id AS chunk_id, c.document_id AS document_id, c.chunk_index, "
    "d.title, c.content, d.category, d.metadata"
)


def _rrf_fuse(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    """Reciprocal Rank Fusion: merge several ranked id-lists into one score map.
    A document ranked highly by EITHER retriever scores well; agreement compounds.
    k=60 is the canonical RRF constant."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, _id in enumerate(ranking):
            scores[_id] = scores.get(_id, 0.0) + 1.0 / (k + rank + 1)
    return scores


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

    # --- hybrid (dense + lexical) retrieval -------------------------------

    def _scope(self) -> tuple[list[str], dict]:
        """Tenant isolation shared by every retrieval path: a tenant sees its own
        docs plus global/template docs; no tenant sees only global docs."""
        if self.organization_id is not None:
            return (
                ["(c.organization_id = :organization_id OR c.organization_id IS NULL)"],
                {"organization_id": str(self.organization_id)},
            )
        return ["c.organization_id IS NULL"], {}

    @staticmethod
    def _row_to_dict(row) -> dict:
        return {
            "id": str(row.chunk_id),
            "document_id": str(row.document_id),
            "chunk_index": row.chunk_index,
            "title": row.title,
            "content": row.content,
            "category": row.category,
            "metadata": row.metadata,
        }

    async def _vector_rows(self, embedding_str: str, limit: int) -> list[dict]:
        where, params = self._scope()
        where = ["c.embedding IS NOT NULL", *where]
        params |= {"embedding": embedding_str, "limit": limit}
        stmt = text(f"""
            SELECT {_CHUNK_COLUMNS},
                   c.embedding <=> CAST(:embedding AS vector) AS distance
            FROM knowledge_chunks c
            JOIN knowledge_documents d ON d.id = c.document_id
            WHERE {" AND ".join(where)}
            ORDER BY distance
            LIMIT :limit
        """)
        rows = (await self.session.execute(stmt, params)).fetchall()
        return [{**self._row_to_dict(r), "distance": r.distance} for r in rows]

    async def _lexical_rows(self, query_text: str, limit: int) -> list[dict]:
        """Postgres full-text search over chunk content. 'simple' config (no
        stemming) keeps it language-agnostic for mixed ES/EN content."""
        where, params = self._scope()
        where.append("to_tsvector('simple', c.content) @@ plainto_tsquery('simple', :q)")
        params |= {"q": query_text, "limit": limit}
        stmt = text(f"""
            SELECT {_CHUNK_COLUMNS},
                   ts_rank(to_tsvector('simple', c.content),
                           plainto_tsquery('simple', :q)) AS rank
            FROM knowledge_chunks c
            JOIN knowledge_documents d ON d.id = c.document_id
            WHERE {" AND ".join(where)}
            ORDER BY rank DESC
            LIMIT :limit
        """)
        rows = (await self.session.execute(stmt, params)).fetchall()
        return [{**self._row_to_dict(r), "rank": r.rank} for r in rows]

    async def search_hybrid(
        self,
        query_text: str,
        query_embedding: list[float],
        top_k: int = 5,
        per_document_limit: int = 2,
    ) -> list[dict]:
        """Dense (vector) + lexical (full-text) retrieval fused with Reciprocal
        Rank Fusion. Falls back to the proven vector-only path on any lexical
        error, so a FTS issue never breaks retrieval."""
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        pool = max(top_k * 3, 20)
        try:
            vector_rows = await self._vector_rows(embedding_str, pool)
            lexical_rows = await self._lexical_rows(query_text, pool)
        except Exception:
            logger.exception("Lexical/hybrid retrieval failed — falling back to vector-only")
            return await self.search_by_embedding(query_embedding, top_k, per_document_limit)

        by_id = {r["id"]: r for r in (*vector_rows, *lexical_rows)}
        scores = _rrf_fuse([[r["id"] for r in vector_rows], [r["id"] for r in lexical_rows]])
        ordered_ids = sorted(scores, key=lambda i: scores[i], reverse=True)

        per_doc: dict[str, int] = {}
        out: list[dict] = []
        for cid in ordered_ids:
            row = by_id[cid]
            doc_id = row["document_id"]
            if per_doc.get(doc_id, 0) >= per_document_limit:
                continue
            per_doc[doc_id] = per_doc.get(doc_id, 0) + 1
            out.append(row)
            if len(out) >= top_k:
                break
        return out
