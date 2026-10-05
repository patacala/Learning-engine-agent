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

### Phase 3 — Custom qualification fields + configurable BANT
- [ ] 3.1 `core/models/qualification_schema.py`: add `bant_dimension` +
      `fields_for_bant(dim)`; tag DEFAULT fields. Per-type default schema.
- [ ] 3.2 `engines/contact_qualification/engine.py`: `qualify(schema=...)`;
      BANT per dimension from schema with per-dimension hardcoded fallback; pass
      schema from `pipeline/nodes.py::_qualify_contact`.
- [ ] 3.3 `services/crm_tools.py`: `_purchase_urgency` resolves the
      `bant_dimension="timeline"` field (fallback to current pair).
- [ ] 3.4 CRM `QualificationTab.tsx` redesign: simple view = label + "ask first"
      + "required to book" + delete; move type/sticky/crm_field/BANT to advanced
      (expert mode); hide raw key. `ai-agents.service.ts` type += `bant_dimension`.
- [ ] 3.5 Tests: custom field mapped to a BANT dimension flips bant; default
      schema → identical scoring.

### Phase 4 — Ask name at greeting + tone by priority
- [ ] 4.1 `prompt_builder.py::_format_missing_fields`: early name = direct from
      greeting; early email/phone = ASAP but gradual; rest = gradual. Empty
      schema → "".
- [ ] 4.2 Tests: early name produces a direct greeting instruction; empty schema
      produces no capture block.

## Progress log
- 2026-10-05: feature doc created, branch `feat/agent-config-model`. Starting Phase 1.
- 2026-10-05: Phase 1 DONE (ProSales + CRM). 433 tests green, CRM typecheck green.
  ProSales commit on feat/agent-config-model; CRM commit on its own branch.
- 2026-10-05: Phase 2 DONE (ProSales only). Additive brief merge. 439 tests green.
