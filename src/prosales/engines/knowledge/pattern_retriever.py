"""PatternRetriever — reuse what historically worked, contextually.

Given an agent (and optionally the current move_kind / stage), returns the
best-performing conversation plays and exact phrases, anti-expressions to avoid,
and any published behavior rules. Clusters compete: only the winners (highest
success_rate) surface. The result renders a prompt block injected by the
PromptBuilder, closing the learning loop.
"""

from uuid import UUID

from pydantic import BaseModel, Field

from prosales.core.similarity import cosine
from prosales.core.similarity import to_list as _to_list
from prosales.infrastructure.database.repositories.expressions import SQLExpressionsRepository
from prosales.infrastructure.database.repositories.insights import SQLInsightsRepository
from prosales.infrastructure.database.repositories.performance import SQLPerformanceRepository

MIN_SUCCESS = 0.5  # only surface plays that work more often than not


def _matches_state(cluster, client_state: str) -> bool:
    """True if the cluster's aggregated works_when conditions mention the state."""
    profile = getattr(cluster, "condition_profile", None) or {}
    works_when = profile.get("works_when") if isinstance(profile, dict) else None
    if not works_when:
        return False
    needle = client_state.lower()
    return any(needle in str(k).lower() for k in works_when)


# Below this many observed occurrences, success_rate is degenerate (0%/50%/100%
# only) — it says "did the one/two examples we have cross the 0.5 bar", not
# "this reliably works". Below the threshold we show the real continuous
# avg_score instead, so a single decent example doesn't read as "100% éxito".
MIN_SAMPLE_FOR_RATE = 3


def confidence_label(occurrence_count: int, success_rate: float, avg_score: float) -> str:
    if occurrence_count >= MIN_SAMPLE_FOR_RATE:
        return f"{round(success_rate * 100)}% éxito en {occurrence_count} casos"
    times = "1 vez" if occurrence_count <= 1 else f"{occurrence_count} veces"
    return f"visto {times}, {round(avg_score * 100)}% de efectividad"


class LearningContext(BaseModel):
    # {move_kind, success_rate, avg_score, occurrence_count, excerpt}
    proven_plays: list[dict] = Field(default_factory=list)
    winning_expressions: list[str] = Field(default_factory=list)
    anti_expressions: list[str] = Field(default_factory=list)
    behavior_rules: list[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not (
            self.proven_plays
            or self.winning_expressions
            or self.anti_expressions
            or self.behavior_rules
        )

    def to_prompt_block(self) -> str:
        parts: list[str] = []
        if self.behavior_rules:
            parts.append(
                "REGLAS APRENDIDAS (síguelas):\n"
                + "\n".join(f"- {r}" for r in self.behavior_rules)
            )
        if self.proven_plays:
            plays = "\n".join(
                f'- [{p["move_kind"]} · '
                f'{confidence_label(p.get("occurrence_count", 1), p["success_rate"], p.get("avg_score", p["success_rate"]))}'
                f'] "{p["excerpt"]}"'
                for p in self.proven_plays
            )
            parts.append(
                "JUGADAS QUE FUNCIONAN (evidencia real de ESTE negocio — si alguna aplica a "
                "esta situación, PRIORIZALA sobre la instrucción genérica de STRATEGY; "
                "adáptala a tu voz, no la recites literal):\n" + plays
            )
        if self.winning_expressions:
            parts.append(
                "FRASES GANADORAS (referencia; inspírate mas no las recites literal):\n"
                + "\n".join(f'- "{e}"' for e in self.winning_expressions)
            )
        if self.anti_expressions:
            parts.append(
                "EVITA ESTAS FRASES (generan rechazo):\n"
                + "\n".join(f'- "{e}"' for e in self.anti_expressions)
            )
        return "\n\n".join(parts)


class PatternRetriever:
    """Reads learned patterns in a SHORT session (via session_factory) so the DB
    connection is not held across the LLM-heavy prompt-building phase."""

    def __init__(self, session_factory):
        self._sf = session_factory

    async def retrieve(
        self,
        agent_version_id: UUID,
        move_kinds: list[str] | None = None,
        stage: str | None = None,
        client_state: str | None = None,
        limit: int = 3,
        message: str | None = None,
    ) -> LearningContext:
        """``message`` (the client's current turn) scopes both proven_plays and
        behavior_rules to what's topically relevant to THIS message, instead of
        just the highest-scored plays in the whole move_kind category (which
        would win identically for every objection regardless of topic) and
        every published rule on every turn. Optional and best-effort: embedding
        failure falls back to plain score-based ranking / all rules.
        """
        async with self._sf() as s:
            performance = SQLPerformanceRepository(s)
            expressions = SQLExpressionsRepository(s)
            insights = SQLInsightsRepository(s)
            message_embedding = await self._embed_message(s, message)
            return await self._retrieve(
                performance, expressions, insights,
                agent_version_id, move_kinds, stage, client_state, limit, message_embedding,
            )

    async def _embed_message(self, session, message: str | None) -> list[float] | None:
        if not message:
            return None
        try:
            from prosales.infrastructure.vector_store.pgvector import PGVectorStore

            return await PGVectorStore(session).embed(message[:2000])
        except Exception as e:  # noqa: BLE001 — scoping is best-effort
            import logging

            logging.getLogger(__name__).warning("Behavior-rule embedding failed: %s", e)
            return None

    async def _retrieve(
        self, performance, expressions, insights,
        agent_version_id, move_kinds, stage, client_state, limit, message_embedding=None,
    ) -> LearningContext:
        clusters = await performance.list_clusters(agent_version_id, polarity="positive")
        # list_clusters already orders by success_rate desc; keep the winners,
        # optionally scoped to the move_kinds relevant to the current strategy.
        kinds = set(move_kinds) if move_kinds else None
        candidates = [
            c
            for c in clusters
            if c.success_rate >= MIN_SUCCESS
            and c.canonical_excerpt
            and (kinds is None or c.move_kind in kinds)
        ]

        # Rank by topical fit to THIS message, not just aggregate score — without
        # this, ranking was purely (success_rate, occurrence_count, avg_score),
        # so within a broad move_kind like "objection_handling" (price, warranty,
        # comparison, ... all mixed together) the same highest-scored handful of
        # plays won every single time regardless of what the client actually
        # asked about. A topically on-point play with a decent score now
        # outranks an off-topic one with a marginally better score.
        #
        # client_state match is a small BOOST added to the semantic score, not a
        # hard filter: a coarse categorical works_when tag (often missing or
        # narrower than reality — a play demonstrated from "frustrado" can
        # still be the best answer for a "desconfiado" client asking the same
        # underlying question) shouldn't override genuine topical relevance,
        # which the embedding captures far more precisely than a handful of
        # hand-picked labels ever will.
        STATE_MATCH_BOOST = 0.05
        if message_embedding is not None:
            scored = [
                (
                    c,
                    cosine(message_embedding, _to_list(getattr(c, "centroid", None)))
                    + (STATE_MATCH_BOOST if client_state and _matches_state(c, client_state) else 0.0),
                )
                for c in candidates
                if getattr(c, "centroid", None) is not None
            ]
            unscored = [c for c in candidates if getattr(c, "centroid", None) is None]
            scored.sort(key=lambda pair: pair[1], reverse=True)
            candidates = [c for c, _ in scored] + unscored
        elif client_state:
            # No message embedding available (e.g. embedding call failed) —
            # fall back to the old hard filter rather than pure score order.
            contextual = [c for c in candidates if _matches_state(c, client_state)]
            if contextual:
                candidates = contextual

        proven = [
            {
                "move_kind": c.move_kind,
                "success_rate": c.success_rate,
                "avg_score": getattr(c, "avg_score", c.success_rate),
                "occurrence_count": getattr(c, "occurrence_count", 1),
                "excerpt": (c.canonical_excerpt or "").strip(),
            }
            for c in candidates
        ][:limit]

        winning = await expressions.list_by_agent(
            agent_version_id, polarity="winning", limit=limit
        )
        anti = await expressions.list_by_agent(agent_version_id, polarity="anti", limit=limit)
        rules = await insights.behavior_rules(agent_version_id, query_embedding=message_embedding)

        return LearningContext(
            proven_plays=proven,
            winning_expressions=[e.exact_phrase for e in winning if e.success_rate >= MIN_SUCCESS],
            anti_expressions=[e.exact_phrase for e in anti],
            behavior_rules=rules,
        )
