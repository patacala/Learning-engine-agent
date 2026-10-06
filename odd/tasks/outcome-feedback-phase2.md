# Feature: outcome-feedback-phase2 (appointment-confirmed WITHOUT payment → ProSales)

## Objective
Extend the verified-outcome learning loop (Phase 1) to the second TIGHT signal:
an appointment that gets CONFIRMED without a payment. Push `"scheduled"` to
ProSales so the conversation's moves are re-scored with real ground truth.

## Scope decision (user, 2026-10-06)
Phase 2 = ONLY the appointment-confirmed-without-payment path (camino A).
The "deal won" path (contact `stage_type === 'won'`) is **OUT of scope / deferred**:
the `CONTACT_STAGE_CHANGED` event is per-contact with NO conversation link, so
attributing a "converted" outcome would require guessing the contact's latest
conversation — a real mis-attribution risk that would poison the learning signal.
Revisit later with a proper stage↔conversation link.

## Background (verified in CRM code)
- `scheduling.service.ts:825 emitAppointmentConfirmed` emits
  `RABBITMQ_QUEUES.APPOINTMENT_CONFIRMED` ('appointment.confirmed') via
  `appointmentEventPayload` (line 787). That payload **does NOT include
  conversation_id today** — only `realtimeBroadcast` (appointment.created) does.
- `AppointmentEntity.conversation_id` (appointment.entity.ts:33) exists, so the
  confirm payload can carry it.
- Phase 1 already wired `AIAgentsModule` into `NotificationsModule.imports`, so
  `ProsalesClientService` (with `reportOutcome(orgId, convId, outcome, notes?)`)
  is injectable in notifications consumers.
- ProSales side needs NO change: `POST /management/conversations/{id}/outcome`
  (Phase 1) already handles `outcome="scheduled"`.

## Design (CRM only)
1. `scheduling.service.ts` `appointmentEventPayload`: add
   `conversation_id: appt.conversation_id ?? null` so every appointment lifecycle
   event (confirmed/created/rescheduled/…) carries the conversation link.
2. New consumer `notifications/outcome-feedback.consumer.ts`:
   - `@EventPattern(APPOINTMENT_CONFIRMED)`; injects `ProsalesClientService`.
   - If `data.conversation_id`, call
     `reportOutcome(org, conversation_id, 'scheduled')` in its own try/catch
     (log a warn, never rethrow — must not break the event ack).
   - No-op when `conversation_id` is absent (manually-created CRM appointments).
3. `notifications.module.ts`: register `OutcomeFeedbackConsumer` in `controllers`.

## Known / accepted behavior
- Double-report with Phase 1: when a payment confirms an appointment, BOTH
  `payment.completed` (Phase 1 → 'scheduled') and `appointment.confirmed`
  (Phase 2 → 'scheduled') fire. Same conversation, same outcome. ProSales is
  idempotent-ish (learned_at gate; then `_propagate_outcome_to_clusters`
  re-scores to the same outcome). Redundant work, harmless. Accepted.
- Re-confirm / reschedule re-fires the push. Same outcome each time. Accepted.
- Not filtering by `origin` for the outcome push (unlike the email consumer):
  a confirmed appointment tied to a conversation is a legit 'scheduled' signal.

## Does NOT change
ProSales (no endpoint/schema/migration change). The move-approval model (moves
stay `pending`; only cluster success_rate re-scored).

## Test-first / verification
CRM has no meaningful runnable RED for a thin event-forwarding consumer (same
exception Phase 1 took: tsc only). Verify:
- `npx tsc -p apps/api/tsconfig.json --noEmit` → exit 0.
- If a jest consumer-test pattern exists cheaply, add one asserting
  `reportOutcome` called with ('org','conv','scheduled') when conversation_id
  present, and NOT called when absent.

## Tasks
- [x] T1 (CRM) add conversation_id to appointmentEventPayload — scheduling.service.ts
- [x] T2 (CRM) new OutcomeFeedbackConsumer — notifications/outcome-feedback.consumer.ts
- [x] T3 (CRM) register consumer — notifications.module.ts
- [x] T4 Verify: tsc clean (no jest specs exist in apps/api — followed Phase 1 precedent)

## Route
Direct inline: 1 non-trivial file (the consumer) + 2 mechanical edits (payload
line, module registration). Full context already gathered.

## Progress / evidence
Implemented 2026-10-06. CRM-only (ProSales unchanged — Phase 1 endpoint already
handles outcome="scheduled").

- **T1** `scheduling.service.ts` `appointmentEventPayload`: added
  `conversation_id: appt.conversation_id ?? null`. Now every appointment lifecycle
  event (created/confirmed/rescheduled/completed/no_show) carries the link.
- **T2** new `notifications/outcome-feedback.consumer.ts`: `OutcomeFeedbackConsumer`,
  `@EventPattern(APPOINTMENT_CONFIRMED)`, injects `ProsalesClientService`. No-ops when
  `conversation_id` absent; otherwise `reportOutcome(org, conv, 'scheduled')` in its
  own try/catch (warn, never rethrow).
- **T3** `notifications.module.ts`: imported + registered `OutcomeFeedbackConsumer`
  in `controllers`. (AIAgentsModule already in imports from Phase 1.)

### Verification (observed)
- `npx tsc -p apps/api/tsconfig.json --noEmit`: **exit 0, clean.**
- No `*.spec.ts` exist anywhere under `apps/api/src`; the `test` script runs jest but
  there is no established consumer-test pattern, so a unit test was NOT added (same
  thin-forwarder exception Phase 1 took). RED/GREEN not applicable.

Not done (out of scope / human-owned): no commit/push; "won" path deferred (see
Scope decision); no live E2E against a real confirmed-appointment event.
