# Learning Engine Agent — Cognitive Sales System

Learning Engine Agent is a **cognitive layer for sales conversations**: instead of a single
LLM call turning a message into a reply, every incoming message runs through
an explicit pipeline of specialized engines — memory, analysis, decision,
strategy, planning, personality, and voice — *before* the LLM ever generates
text. The LLM produces the final wording; the system decides what to say and
why.

It exists to answer, for every reply: *why this content, why this tactic,
why this tone* — and to get measurably better at that over time by learning
from real conversation outcomes (episodic memory + a continuous learning
loop), not by manually re-prompting.

If you're joining this project, read this file top to bottom once, then use
**graphify** (below) instead of grepping around — it's faster and it's the
convention this repo already follows.

## Start here

```bash
git clone <repo> && cd learning-engine-agent
cp .env.example .env               # fill in OPENAI_API_KEY at minimum
uv sync --extra dev                # or: pip install -e ".[dev]"

make up                            # postgres (pgvector) + redis via Docker
make migrate                       # alembic upgrade head
make run                           # uvicorn, reload, :8000

cd frontend && npm install && npm run dev   # vite dev server, :5173
```

Docker only runs the stateful infra (Postgres+pgvector, Redis). The API
(uvicorn) and the frontend (Vite) run on the host — this makes hot-reload and
debugging fast, and is a deliberate choice, not an oversight.

```bash
make test    # pytest -v (unit + integration)
make lint    # ruff check + format --check
make eval    # tests/evals/*.yaml through the real pipeline + LLM-as-judge; needs AGENT=<agent_version_id>
```

## Exploring the codebase: use graphify, not grep

This repo maintains a knowledge graph at `graphify-out/` (god nodes, community
structure, cross-file relationships) — see `CLAUDE.md`/`AGENTS.md`. If you're
using an AI coding assistant here, it already knows to prefer:

```bash
graphify query "<question>"          # scoped subgraph for a question
graphify path "<A>" "<B>"            # how two symbols relate
graphify explain "<concept>"         # focused view of one concept
graphify update .                    # AST-only refresh after you edit code, no API cost
```

`graphify-out/GRAPH_REPORT.md` has the god nodes and community map for a
from-scratch architecture read. `graphify-out/wiki/index.md` (if present) is
for broad navigation. Run `graphify update .` after any nontrivial change —
stale graphs actively mislead.

## Architecture

### The pipeline

Every message is a run through a **LangGraph `StateGraph`**
(`pipeline/graph.py`, entrypoint `build_cognitive_graph()`). Two routes:

```
remember → context_build → analyze → route → identify ─┬─ FAST_PATH ──────────────┐
                                                          └─ FULL_PATH: retrieve →   │
                                                             decide → strategize →   │
                                                             plan ───────────────────┤
                                                                                      ▼
                                          personify → response_plan → build_prompt → llm_call
                                                                                      │
                                          learn ← store ← voice_layer ← post_process ◄┘
```

- **FAST_PATH**: skips knowledge retrieval, rule-based decisions, and strategy
  selection — used when the router decides the turn doesn't need the full
  cognitive load (e.g. a quick backchannel-worthy message).
- **FULL_PATH**: the complete cognitive stack — RAG retrieval, decision rules,
  strategy scoring, tactical planning — runs before personality/prompt/LLM.

Each node wraps one **engine**. Engines are plain classes with one
responsibility; the graph only wires them together and times them
(`PipelineExecution`/`NodeTrace` — see Observability below).

### Engines (what each one owns)

| Engine | Responsibility |
|---|---|
| **Memory** (3-tier) | short-term (session), episodic (past conversations), long-term facts |
| **ContextBuilder** | assembles the working context for this turn |
| **Analyzers** | 6 parallel detectors — intent, sentiment, stage, urgency, language, contact signals — or 1 fused call (`UnifiedAnalyzer`, see Latency below) |
| **ConversationManager** | routes FAST_PATH vs FULL_PATH |
| **Identity** | who the agent *is* (principles, beliefs, tone) — not a prompt, a mental model |
| **Knowledge** | RAG over PGVector — proven plays, past winning/losing expressions |
| **Decision** | rule-based actions from analysis (`apply_rules`) |
| **Strategy** | 30-tactic catalog + signal scorers + multi-tactic selection (`SELECT → APPLY → EVALUATE → LEARN → SWITCH`) |
| **Planner** | turns strategy into a concrete response plan |
| **Personality** | 5-layer composition merged into one instruction set |
| **Response** | planner → prompt builder → LLM call → post-processor |
| **Voice** | backchannels, interruption/repair handling, TTS-facing text shaping |
| **Learning** | turns conversation outcomes into durable patterns (see below) |

### Agents are configuration, not code forks

A single codebase serves multiple tenants/verticals via `AgentContext`
(`core/models/agent.py`): `organization_id → agent_id → agent_version_id`,
resolved by API key (`infrastructure/agent/resolver.py`, cached 300s). Each
`agent_version` carries its own identity, personality, rules, strategies,
tactics, prompt templates, and voice config — loaded through **Providers**
(`infrastructure/agent/providers.py`), one per config type, all keyed by
`agent_version_id` and cache→DB with the same 300s TTL.

**Capability gating**: `org_capabilities` (e.g. `knowledge`, `inventory`) and
`agent_capabilities` (e.g. `voice`, `negotiation`) decide which engines
actually run for a given agent — no API key means no `AgentContext`, which
means engines fall back to hardcoded defaults instead of failing.

⚠️ Known limitation (tracked in memory, not yet fixed): the strategy catalog
is currently all-or-nothing per agent — if an agent has *any* custom
`agent_strategies`, the generic 30-tactic catalog becomes entirely
unreachable for it, even for tactic types the custom set doesn't cover. See
`engines/strategy/engine.py::StrategyEngine.process`. Blocks onboarding a
second (non-automotive) vertical cleanly.

### Learning loop

The system doesn't just log conversations — it turns them into evidence.
`services/learning_pipeline.py` + `engines/{moves,expressions,performance,
insights}/*`: conversation moves get extracted, clustered by
(agent, move_kind, polarity) via cosine similarity (`core/similarity.py`,
shared — don't duplicate it), semantically deduped, and aggregated into
performance stats that feed back into `PatternRetriever` for future RAG
retrieval. Outcomes are **cognition-inferred** (the system's own read of how
a conversation ended), not dependent on a CRM — there is no CRM integration
yet; that's planned as the eventual source of truth once latency work lands.

**Roleplay Training Channel** (`channels/roleplay/*`) generates synthetic
conversations against a simulated client persona so the learning loop has
data to train on without waiting on live traffic volume.

### Observability

Every pipeline run is a `PipelineExecution` with a `NodeTrace` per node
(timing) and a `DecisionTrace`/`StrategyTrace` capturing *why* — which rule
matched, which tactic candidates were scored and why one won. Exposed via
`GET /conversation/{id}/timeline`. This is the mechanism that makes "why did
it say that" answerable after the fact instead of only in a debugger.

### Latency work (active area)

Two shipped changes worth knowing about before touching the hot path:
- `UnifiedAnalyzer` (`engines/analyzers/unified.py`, flag
  `settings.use_unified_analyzer`) fuses 4 parallel LLM calls into 1 — cuts
  ~57% of turn latency at the cost of correlated fallback if the single call
  fails. Flip the flag to roll back with no redeploy if eval quality
  regresses.
- `primary_llm_service_tier = "priority"` (OpenAI Fast mode) trades ~2x token
  cost for materially lower tail latency — measured, not guessed (see
  `config.py` comment for the numbers).

Real per-turn SSE token streaming exists but — measured finding — doesn't cut
time-to-first-token as much as expected; treat "we streamed it" and "it feels
faster" as separate claims until re-measured.

## Repo layout

```
src/learning_engine/
  api/v1/endpoints/     REST endpoints (conversation, learning, roleplay, management, ...)
  channels/             voice/ roleplay/ assistant/ — alternate conversation surfaces
  core/                 domain models, enums, interfaces — no I/O
  di/                   provider wiring (create_llm_provider, container)
  engines/              one dir per engine (see table above)
  infrastructure/       agent/ database/ llm/ vector_store/ cache/ events/ security/
  pipeline/             graph.py (the StateGraph), nodes.py, edges.py, state.py
  services/             cross-engine orchestration (learning_pipeline, pipeline_runner, live_learning)
alembic/versions/       schema migrations (check the highest-numbered file for current head — don't hardcode a number here, it drifts)
tests/{unit,integration,evals,fixtures}/
frontend/src/           React 19 + Vite + Tailwind — brain dashboard, chat, training UI
scripts/                seed_knowledge.py, seed_strategies.py, eval_suite.py, loadtest_chat.py
```

## Conventions worth knowing before your first PR

- **DateTime**: DB columns are naive (`TIMESTAMP WITHOUT TIME ZONE`). Use
  `datetime.utcnow()` — `datetime.now(timezone.utc)` produces a tz-aware
  value asyncpg can reject against a naive column. (There are existing
  violations of this in the codebase — don't copy them; fix opportunistically
  if you're touching that code.)
- **PGVector**: parametrize as `CAST(:param AS vector)`, not `:param::vector`
  — asyncpg needs the explicit cast form.
- **JSONB migration defaults**: `sa.text("'{}'")` / `sa.text("'[]'")`, not a
  raw Python dict/list literal.
- **Enums**: `.value` when writing to the DB, `str()` when serializing to
  JSON. `StrategySelection.strategy_type` is typed `str | StrategyType`
  deliberately — handle both.
- **Prompt templates**: escape literal `{}` as `{{}}` before `.format()`.
- **Sessions**: `session.begin()` lives in the dependency; don't manually
  commit/rollback inside a route or engine. DB-touching engines open *short*
  sessions via `session_factory` so no connection is held across LLM calls.
- **Similarity/embeddings**: `cosine`, `to_list`, `SIMILARITY_THRESHOLD` live
  in `core/similarity.py` and are shared by Performance and Expressions —
  don't reimplement them.
- **SSE progress events**: use the `_sse_event` helper in
  `api/v1/endpoints/_sse.py` (`thinking/extracting/...→completed|error`
  pattern) rather than hand-rolling a new event shape.
- **Language**: source code (including docstrings/comments) is 100% English.
  Project-memory notes (not part of this repo's tracked docs) mix Spanish
  prose with untranslated English technical terms — that convention doesn't
  apply to anything under `src/`.

## Claude Code skills for this repo

`.claude/skills/` — Claude Code loads these automatically when relevant;
worth knowing they exist so you know what's already enforced instead of
re-explaining it in a prompt:

- `run` / `verify` — launch the app; what to run before a commit.
- `following-learning_engine-conventions` — datetime/PGVector/JSONB/enum/session/
  similarity/SSE rules (narrow, fragile, "wrong choice fails at runtime").
- `writing-learning_engine-python` / `writing-learning_engine-frontend` — idiomatic shape
  of the code (the engine pattern, Pydantic DTOs, component/hook structure).
- `using-learning_engine-domain-vocabulary` — Episode vs Move vs Expression vs
  Evidence vs Outcome vs Qualification, and the Organization→Agent→
  AgentVersion hierarchy.
- `enforcing-agent-context-boundaries` — multi-tenant business rules,
  capability gating, the strategy-catalog limitation.
- `guarding-sensitive-operations` — migrations, secrets/tokens, learning-loop
  data integrity — things that are hard or impossible to undo.

## Where to look next

- `AGENTS.md` / `CLAUDE.md` — graphify usage rules for AI assistants working
  in this repo.
- `graphify-out/GRAPH_REPORT.md` — god nodes, communities, full architecture
  map generated from the actual code, not from this document.
- `tests/evals/README.md` — how the eval suite scores pipeline output
  (deterministic checks + LLM-as-judge) and why it's structured that way.
- `alembic/versions/` — read migrations in order for the schema's evolution;
  each one's docstring explains the *why*, not just the *what*.
