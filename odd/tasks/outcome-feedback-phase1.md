# Feature: outcome-feedback-phase1 (verified CRM outcome → LearningEngine learning)

## Objective
Close the learning loop for the TIGHT, unambiguous signal first: when a payment
succeeds in the CRM, push the verified outcome to LearningEngine so the learning
engine re-scores the conversation's moves with real ground truth (instead of
only Cognition's inferred outcome). Phase 2 (deal-won, appointment-confirmed
without payment) is out of scope.

## Background (verified in code)
- LearningEngine already has the machinery (`episode.py:_propagate_outcome_to_clusters`,
  `services/live_learning.py:run_live_learning`) but the CRM NEVER calls any
  outcome/episode endpoint — the loop is disconnected.
- Auth wrinkle: the episode endpoint (`/conversation/{id}/episode`) uses
  `verify_internal_or_api_key` (reads `x-api-key`/`x-internal-token`), but the
  CRM's `learning_engine-client.request()` sends `Authorization: Bearer`. So the CRM
  can't reach the episode endpoint as-is. The CRM's Bearer DOES work against
  `/management` (`get_authenticated_org`). → Expose the outcome under /management.
- `update_episode_feedback` 404s when no Episode row exists; CRM conversations
  (fast-ACK, never /close) have none. So do NOT reuse it directly — must not 404.
- `run_live_learning` needs no Episode (works off message turns), is idempotent
  via `conv.learned_at`, and reads `conv.outcome`. If it already ran at terminal
  with "open", re-scoring the verified outcome needs `_propagate_outcome_to_clusters`.
- `run_live_learning` opens its OWN session (`async_session_factory`). It will
  only see `conversation.outcome` if that update is COMMITTED first (same
  mid-handler commit pattern as the /management/knowledge endpoint).

## Design

### LearningEngine — new endpoint under /management
`POST /api/v1/management/conversations/{conversation_id}/outcome`
- Auth: `get_authenticated_org` (Bearer), like the rest of /management.
- Body schema (schemas/management.py): `OutcomeUpdateRequest { outcome: str, outcome_notes: str = "" }`.
- Logic:
  1. Load conversation; 404 if missing OR `conversation.organization_id != org.id`
     (tenant safety — the episode endpoint lacks this check; do it here).
  2. Set `conversation.outcome = outcome` (+ updated_at) and COMMIT this first
     (so the own-session `run_live_learning` can see it).
  3. If `conversation.learned_at is None`: `await run_live_learning(conversation_id)`
     (extracts + scores moves with the verified outcome; own session).
     Else: open a fresh `async_session_factory()` session and
     `await _propagate_outcome_to_clusters(session, conversation_id, outcome)`
     (re-score existing moves/clusters).
  4. Best-effort: if an Episode exists, also update its feedback (don't 404 if not).
  - Import `run_live_learning` from services.live_learning and
    `_propagate_outcome_to_clusters` from endpoints.episode (module-level). If a
    tiny relocation to a shared module reads cleaner, that's allowed but keep
    behavior identical.
- Return 200 with a small JSON (e.g. {status, outcome}).

### CRM — push on payment completed
- `learning_engine-client.service.ts`: add
  `reportOutcome(orgId, conversationId, outcome, notes?)` →
  `request(orgId, 'POST', /api/v1/management/conversations/${conversationId}/outcome,
   { outcome, outcome_notes: notes ?? '' })`. Non-fatal on error (log + swallow in caller).
- `notifications/payment-event.consumer.ts` `handlePaymentCompleted`: after the
  analytics track, if `data.conversation_id`, call
  `this.learning_engine.reportOutcome(data.organization_id, data.conversation_id,
   data.appointment_confirmed ? 'scheduled' : 'converted')` inside try/catch
  (payment success already carries conversation_id + appointment_confirmed).
- `notifications/notifications.module.ts`: import `AiAgentsModule` (which exports
  `ProsalesClientService`) so the consumer can inject it.

## Outcome mapping
- `appointment_confirmed === true` → `"scheduled"` (outcome_signals: appointment=True).
- otherwise (paid, no appointment) → `"converted"` (purchase=True).
- PAYMENT_EXPIRED / negative outcomes: OUT of scope (Phase 1 = positive only).
- Note: `run_live_learning` extracts winning EXPRESSIONS only when outcome=="scheduled";
  a "converted" purchase still scores moves but won't mine exact phrases. Leaving
  that as-is for Phase 1 (one-line change later if wanted).

## Does NOT change
The move-approval model: moves stay `pending`; this only re-scores clusters
(Knowledge Areas success_rate). Auto-approving moves into the RAG/"Approved"
pool is a separate, later decision.

## Test-first (LearningEngine pytest)
`tests/unit/api/test_management_outcome.py` (new), mocking `run_live_learning`
and `_propagate_outcome_to_clusters`:
- outcome set on the conversation; 200.
- `learned_at is None` → `run_live_learning` called, `_propagate` not.
- `learned_at` set → `_propagate_outcome_to_clusters` called, `run_live_learning` not.
- conversation of another org → 404 (tenant check).
- missing conversation → 404.

## Tasks
- [x] T1 (LearningEngine) OutcomeUpdateRequest schema — schemas/management.py
- [x] T2 (LearningEngine) POST /management/conversations/{id}/outcome endpoint — management.py
- [x] T3 (CRM) reportOutcome in learning_engine-client.service.ts
- [x] T4 (CRM) call it from payment-event.consumer.ts + wire AIAgentsModule in notifications.module.ts
- [x] T5 Tests (LearningEngine pytest RED→GREEN) + CRM tsc
- [x] T6 Verify suite green; lint; tsc clean

## Route
Delegated-direct: one bounded writer (cross-repo, ~5 non-trivial files + test).

## Progress / evidence
Implemented 2026-10-06. RED→GREEN done (5 new tests failed first against a module
missing the endpoint, then passed after implementation).

- **T1** `schemas/management.py`: added `OutcomeUpdateRequest { outcome: str, outcome_notes: str = "" }`.
- **T2** `endpoints/management.py`: added `POST /conversations/{conversation_id}/outcome`
  (`Depends(get_authenticated_org)`). Loads `ConversationModel` via the request
  session; 404 on missing OR `organization_id != org.id` (tenant check). Sets
  `outcome` + `updated_at = datetime.utcnow()` and `await session.commit()` BEFORE
  learning (mid-handler commit, same as `index_knowledge`, so the own-session
  `run_live_learning` sees the value). `learned_at is None` → `run_live_learning`;
  else fresh `async_session_factory()` + `session.begin()` →
  `_propagate_outcome_to_clusters`. Best-effort episode-feedback mirror wrapped in
  try/except (never 404s if no Episode). `_propagate_outcome_to_clusters` imported
  from `endpoints.episode` (episode.py untouched). New module `logger`.
- **T3** CRM `learning_engine-client.service.ts`: added `reportOutcome(orgId, conversationId, outcome, notes?)`
  → `request(orgId, 'POST', /api/v1/management/conversations/${id}/outcome, { outcome, outcome_notes })`.
- **T4** CRM `payment-event.consumer.ts`: injected `ProsalesClientService`; after the
  analytics track in `handlePaymentCompleted`, when `conversation_id` present, calls
  `reportOutcome(org, conv, appointment_confirmed ? 'scheduled' : 'converted')` in its
  own try/catch (logs a warn, never rethrows). `handlePaymentExpired` untouched.
  `notifications.module.ts`: added `AIAgentsModule` to `imports` (note: real export is
  `AIAgentsModule`, not `AiAgentsModule`).

### Verification (observed)
- `pytest tests/unit/api/test_management_outcome.py tests/unit/api/test_management_api.py -q`: **30 passed** (5 new + 25 existing).
- `ruff check src/learning_engine/api/v1/endpoints/management.py src/learning_engine/api/v1/schemas/management.py`: 23 errors, **all pre-existing** (per-file counts unchanged vs HEAD: management.py 22, schemas 1 — E501/I001/UP017 legacy debt). **Zero new.**
- CRM `npx tsc -p apps/api/tsconfig.json --noEmit`: **exit 0, clean.**

Not done (out of scope / human-owned): no commit/push; no DB migration (additive, none needed);
no live E2E against a real CRM payment event.
