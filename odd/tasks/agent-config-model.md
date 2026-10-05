# Feature: Agent configuration model (type + additive brief + custom fields)

Plan: `~/.claude/plans/reactive-kindling-crab.md` (approved 2026-10-05).
Branch: `feat/agent-config-model`.

## Objective
Make per-org agent configuration real and not hardcoded: pick an agent type at
creation (template-first), let the brief add context on top without wiping the
template, make qualification fields + BANT scoring custom per org, and have the
agent ask for the name right after greeting. Deliver as chained slices (1 PR per
phase); Phase 1 is the base.

## Source of truth model
Type → seeds a solid template (role/tone/pressure/identity). Brief → additive
refinement. Tabs → final editable truth. A weak brief must not degrade the agent.

## Scope / constraints
- No Alembic migration (Phase 3 uses the existing JSONB `fields`).
- `capabilities_preset` stays `"full"` (out of scope).
- Backward-compat: existing orgs (no custom schema / default schema) must behave
  identically — BANT falls back per-dimension to current hardcoded logic.

## Tasks

### Phase 1 — Agent type selectable + role templates (base) ✅ DONE
- [x] 1.1 Expanded `AGENT_TEMPLATES` with `customer_service`, `consulting`,
      `technical_service`; `support` → alias of `customer_service`;
      `SELECTABLE_AGENT_TYPES` added. (templates.py)
- [x] 1.2 Replaced `DEFAULT_SYSTEM_TEMPLATE` with a neutral `{role}`-driven
      fallback + `_fallback_role(identity)` helper (prompt_builder.py).
- [x] 1.3 CRM: agent-type selector in `config/agents/page.tsx`; `agent_type`
      threaded page → useAIAgents → web service → API controller → API service →
      prosales-client (bootstrap body). CRM typecheck green (4/4).
- [x] 1.4 Tests: `tests/unit/agent/test_agent_templates.py` +
      `tests/unit/engines/test_prompt_builder_fallback.py` (8 new). Suite 433 green.

### Phase 2 — Additive brief (non-destructive) ✅ DONE
- [x] 2.1 `brief_extractor.py`: pure merge fns (`merge_identity/personality/
      rules/strategies`, `_union`) — lists unioned (template first), scalars kept
      from template, rules/strategies union by rule_id/strategy_type (template
      wins). `management.py configure_from_brief` reads base via new
      `_read_*_payload` helpers, merges, persists via existing `_persist_*`,
      returns merged. Empty base → brief alone (backward-safe).
- [x] 2.2 Tests: `tests/unit/services/test_brief_merge.py` (6). Suite 439 green.

### Phase 3 — Custom qualification fields + configurable BANT ✅ DONE
- [x] 3.1 `qualification_schema.py`: `bant_dimension` field + `fields_for_bant()`
      + `BANT_DIMENSIONS`; DEFAULT fields tagged (product_interest→need,
      has_budget/budget_amount→budget, purchase_timeline→timeline,
      is_decision_maker→authority).
- [x] 3.2 `contact_qualification/engine.py`: `qualify(schema=...)` + module-level
      `_bant_fact_hit(dim, schema, facts, *fallback_keys)` — schema-driven per
      dimension, per-dimension fallback to legacy keys. schema threaded from
      `nodes._qualify_contact`. (Also fixed a latent bug: under the default schema
      the engine read `facts["budget"/"timeline"/"decision_role"]` which the
      extractor never emits — now reads the tagged keys.)
- [x] 3.3 `crm_tools.py`: `_timeline_value(facts, schema)` resolves the
      timeline-tagged field; `_purchase_urgency` uses it (legacy pair fallback).
- [x] 3.4 CRM `QualificationTab.tsx` simplified: simple view = label + ask first
      + required to book + delete; type/enum/sticky/crm_field/BANT behind
      `expertMode` (passed from page.tsx); raw key never shown. Web type +=
      `bant_dimension`/`BantDimension`.
- [x] 3.5 Tests: `test_contact_qualification_bant_schema.py` (5). Suite 444 green,
      CRM typecheck green.

### Phase 4 — Ask name at greeting + tone by priority ✅ DONE
- [x] 4.1 `prompt_builder.py::_format_missing_fields` rewritten: name (early) =
      direct from greeting with a professional framing; other early fields = ASAP
      but gradual; rest = naturally later. `_is_name_field` helper. Empty schema
      → "".
- [x] 4.2 Tests: `test_prompt_builder_missing_fields.py` (6). Suite 450 green.

## Progress log
- 2026-10-05: feature doc created, branch `feat/agent-config-model`. Starting Phase 1.
- 2026-10-05: Phase 1 DONE (ProSales + CRM). 433 tests green, CRM typecheck green.
  ProSales commit on feat/agent-config-model; CRM commit on its own branch.
- 2026-10-05: Phase 2 DONE (ProSales only). Additive brief merge. 439 tests green.
- 2026-10-05: Phase 3 DONE (ProSales + CRM). Configurable BANT + simplified
  QualificationTab. 444 tests green, CRM typecheck green.
- 2026-10-05: Phase 4 DONE (ProSales only). Name asked at greeting, tone by
  priority. 450 tests green. ALL 4 PHASES COMPLETE.
