# Feature: payment-continues-conversation

## Objective
After a successful (or expired) Stripe payment, the agent must continue the
conversation automatically (acknowledge the payment/booking and proceed),
instead of going silent.

## Problem (verified in code)
The CRM already fires a `payment.received` trigger after
`checkout.session.completed` (payments.service.ts:290-334) carrying
`conversation_id` and a system confirmation `message`. But it never reaches
the LearningEngine conversational agent, for three reasons:

1. **Routing** — `AgentTriggerProcessor.process` resolves targets via
   `findAgentsForEvent(org, event_type)` and agents match a single exact
   `trigger_event` (agent-trigger.service.ts:20-24). The LearningEngine agent is
   registered for `message.received`, so `payment.received` matches zero agents
   unless a second agent row is configured. → event dies in the worker.
2. **Schema** — even if delivered, `CRMInboundPayload` requires both `message`
   AND `channel` (schemas/crm_inbound.py:41-43); the payment payload has no
   `channel` → 422 → `workflow_failed`.
3. **No event branching** — `/crm/inbound` ignores `event_type` entirely
   (built only for `message.received`). It would store the system confirmation
   as a USER turn (`store_user_message=True`), exactly what the CRM warns
   against ("NOT a user utterance").

## Scope (authorized)
Fix both sides. CRM routing approach chosen by user: **route in the processor**
(fall back payment events to the active `message.received` agent; no extra
config row).

## Design
- **CRM** `agent-trigger.processor.ts`: define `PAYMENT_EVENTS =
  {'payment.received','payment.expired'}`. In `process`, if
  `findAgentsForEvent(org, event_type)` is empty AND `event_type ∈
  PAYMENT_EVENTS`, retry with `'message.received'`. The POST still sends the
  original `event_type` so LearningEngine branches correctly. Explicit payment-agent
  config still wins (only fall back when empty).
- **LearningEngine schema** `schemas/crm_inbound.py`: `CRMInboundPayload.channel:
  str | None = None` (payment payload has no channel).
- **LearningEngine endpoint** `crm_inbound.py`:
  - Treat `body.event_type != "message.received"` as a **system event**.
  - System event path: run immediately (NO debounce), call
    `_run_pipeline_and_reply(..., store_user_message=False)` with
    `extra_context["system_event"] = {"type": event_type, "message":
    payload.message}`.
  - Parametrize `_run_pipeline_and_reply` with `store_user_message: bool = True`
    and pass it to `runner.run(...)`.
  - `current_message` = `payload.message` (so analyzers/response have content;
    not persisted because store_user_message=False).
  - Build `extra_context` with `payload.channel or "system"`.
- **LearningEngine prompt** `prompt_builder.py` `_format_external_context`: render
  `extra["system_event"]` FIRST as a prominent system instruction, e.g.:
  `SYSTEM EVENT (confirmed fact, the customer did NOT say this — acknowledge it
  and continue naturally):\n<message>`.

## Preconditions / non-goals
- Works only when the payment carries a `conversation_id` (it does, created
  in-conversation by `create_payment_link`). Null conversation_id → nothing to
  continue (out of scope).
- `payment.expired` is handled by the same system-event path for free if routed.

## Test-first policy (LearningEngine has pytest; RED→GREEN)
- `tests/unit/api/test_crm_inbound*.py` (new or existing): a `payment.received`
  inbound runs the pipeline with `store_user_message=False`, bypasses debounce,
  injects `extra_context["system_event"]`, and calls `_send_reply_to_crm`.
  Accepts a payload with NO `channel`.
- `tests/unit/engines/` prompt_builder: `extra_context["system_event"]` renders
  a system instruction containing the message.
- CRM: add processor fallback unit test if a Jest harness exists; otherwise
  verify with `tsc`/build and note it.

## Tasks
- [x] T1 (CRM) processor payment→message.received fallback — agent-trigger.processor.ts
- [x] T2 (LearningEngine) channel optional — schemas/crm_inbound.py
- [x] T3 (LearningEngine) event_type branching + store_user_message param + system_event injection — crm_inbound.py
- [x] T4 (LearningEngine) prompt_builder renders system_event — prompt_builder.py
- [x] T5 Tests (LearningEngine pytest; CRM verified via tsc — no Jest harness) + run suite
- [x] T6 Verify: LearningEngine crm_inbound+prompt tests green; lint (no new errors); CRM tsc clean

## Route
Delegated-direct: one bounded writer (4 non-trivial files + tests across 2 repos).

## Progress / evidence
Implemented 2026-10-05 (delegated-direct writer).

- **T1 CRM** `agent-trigger.processor.ts`: added module-scope
  `PAYMENT_EVENTS = new Set(['payment.received','payment.expired'])`; made
  `agents` a `let`; after the first `findAgentsForEvent`, if empty AND the
  event is a payment event, re-resolve with `'message.received'` (debug log).
  The POST still sends the original `event_type` (n8nPayload uses the
  destructured `event_type`, untouched). Existing "No active agents"
  early-return kept after the fallback.
- **T2 LearningEngine** `schemas/crm_inbound.py`: `CRMInboundPayload.channel: str | None = None`.
- **T3 LearningEngine** `endpoints/crm_inbound.py`: `_run_pipeline_and_reply` gained
  `store_user_message: bool = True`, passed through to `runner.run(...)`
  (was hardcoded True). `extra_context["channel"] = body.payload.channel or "system"`.
  New system-event branch in `crm_inbound` (any `event_type != "message.received"`):
  NO debounce, injects `extra_context["system_event"] = {"type", "message"}`,
  calls `_run_pipeline_and_reply(..., store_user_message=False)` with
  `current_message = body.payload.message` via `background_tasks.add_task`
  (same fast-ACK 202). The `message.received` path (debounce/immediate) is
  byte-for-byte unchanged. Opt-out short-circuit untouched.
- **T4 LearningEngine** `prompt_builder.py` `_format_external_context`: renders
  `extra["system_event"]` FIRST (before Contact/appointments) as
  `SYSTEM EVENT (confirmed fact — the customer did NOT say this; acknowledge
  it and continue naturally):\n<message>`. Tolerates dict `{type,message}` or
  bare string; empty message skipped; never raises.

### Verification
- `pytest` (5 files incl. 2 new): **15 passed**.
- `ruff check` (3 changed src files): 5 errors, ALL pre-existing on base
  (4× E501 at prompt_builder L30/31/66/295; 1× I001 import sort in
  crm_inbound L27) — my diff introduced **0 new** lint errors. Left untouched
  (unrelated debt; conventions skill forbids cosmetic reformatting).
- CRM `npx tsc -p apps/api/tsconfig.json --noEmit`: **exit 0, no errors**
  (no Jest harness in the module, so typecheck is the CRM proof per spec).

### Deviations / notes
- The three skill paths in the task prompt don't exist on disk; loaded the
  equivalent skills via the Skill tool instead (same content).
- No commit/push performed (per instructions).
