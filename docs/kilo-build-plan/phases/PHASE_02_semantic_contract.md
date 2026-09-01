# PHASE 2 — Semantic Discovery & KPI Semantic Contract

## Objective
Turn a profiled source into a governed, human-reviewable "semantic contract": inferred KPI
definitions, business hierarchies, calendar rules, materiality thresholds, and access tags. This is
a critical **human-in-the-loop checkpoint** — the user must be able to see exactly what the system
inferred and correct it before anything downstream is built on top of it.

## Prerequisites
Phase 1 approved and working (a profiled source must exist).

## Backend tasks
1. `backend/app/db.py` — add `CREATE TABLE IF NOT EXISTS semantic_contracts (source_id TEXT
   PRIMARY KEY, contract_json TEXT, updated_at TEXT)`.
2. `backend/app/core/semantic/rules.py` — deterministic rules mapping each profiled column to a
   semantic role: `measure` (numerical, not identifier), `dimension` (categorical), `time`
   (temporal), `identifier`. No ML, no LLM — pure rule logic based on the Phase 1 profile output.
3. `backend/app/core/semantic/contract_builder.py` — function `build_contract(profile) -> dict`
   producing:
   - `kpi_definitions`: candidate KPIs (each measure column paired with a default aggregation —
     sum/avg/rate — and any dimension columns it could be sliced by).
   - `hierarchies`: any dimension columns that look related (e.g. columns sharing a common prefix
     or one being a coarser grouping of another — simple heuristic, document the rule used).
   - `calendar`: the detected time column and its granularity (day/week/month) from Phase 1.
   - `thresholds`: default materiality threshold (e.g. movement > 1 std dev = material) — a
     starting default the user can edit.
   - `access_tags`: default `"public"` tag on every column — the user will restrict specific
     columns in Phase 8 (Persona & Access Control).
4. `backend/app/api/semantic_contract.py` — `GET /semantic-contract/{source_id}` (build if not
   exists, else return stored), `PUT /semantic-contract/{source_id}` (accepts a full edited
   contract JSON from the user, overwrites stored version, updates `updated_at`).

## UI tasks
1. `frontend/src/pages/SemanticContractPage.tsx` — source selector, then an **editable** view:
   - Table of KPI definitions: column, aggregation type (dropdown: sum/avg/rate/count), sliceable
     dimensions (multi-select), each row has a delete button and an "add custom KPI" button.
   - Hierarchies list: editable pairs (parent dimension → child dimension), add/remove rows.
   - Calendar: shows detected time column + granularity (editable dropdown).
   - Thresholds: editable numeric input for the default materiality threshold.
   - "Save Contract" button calling `PUT`, with a success confirmation.
2. Enable "Semantic Contract" nav item.
3. `frontend/src/api/semanticContract.ts` — fetch wrapper.

## Files to create
**Backend:** `backend/app/core/semantic/__init__.py`, `backend/app/core/semantic/rules.py`,
`backend/app/core/semantic/contract_builder.py`, `backend/app/api/semantic_contract.py`.

**Frontend:** `frontend/src/pages/SemanticContractPage.tsx`,
`frontend/src/api/semanticContract.ts`.

## Tests to write & run
- `backend/tests/test_semantic.py`: given a synthetic profile with one measure, one dimension, one
  time column, and one identifier column, `build_contract` produces exactly one KPI definition,
  correctly excludes the identifier from KPI candidates, and detects the time column's granularity
  correctly.
- Run `pytest` and confirm all pass.

## Manual verification checklist
- [ ] Generate a semantic contract for the source uploaded in Phase 1.
- [ ] Edit one KPI's aggregation type and save.
- [ ] Reload the page and confirm the edit persisted (proves `PUT` + storage works, not just the UI
      state).
- [ ] `pytest` passes.

## Definition of Done
The user can review and correct the system's inferred KPI/business semantics before any KPI is
actually computed, and edits persist across page reloads.

## STOP
Summarize what was built, how to verify it, and write:
**"Phase 2 complete. Waiting for your approval before starting Phase 3."**
