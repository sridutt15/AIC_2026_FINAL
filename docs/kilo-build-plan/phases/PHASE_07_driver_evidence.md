# PHASE 7 — Driver/Contribution Analysis & Evidence Engine

## Objective
For a KPI movement, decompose it across contributing dimensions (drivers) and attach traceable
numeric evidence (test used, freshness, lineage) to every finding.

## Prerequisites
Phase 6 approved and working (anomalies/materiality must exist).

## Backend tasks
1. `backend/app/db.py` — add `CREATE TABLE IF NOT EXISTS findings (finding_id TEXT PRIMARY KEY,
   kpi_id TEXT, finding_type TEXT, finding_json TEXT, evidence_json TEXT, created_at TEXT)`.
2. `backend/app/core/drivers/contribution.py` — `decompose_contribution(canonical_df, kpi,
   dimensions) -> dict` for an additive/ratio metric, computes each dimension-slice's contribution
   to the total period-over-period movement (waterfall-style decomposition: sum of slice
   contributions should reconcile to the total movement within rounding — assert this in the
   function itself as a sanity check, not just in tests).
3. `backend/app/core/drivers/causal.py` — `diff_in_diff(canonical_df, treatment_dim, outcome,
   before_period, after_period) -> dict` — a simple difference-in-differences estimator, used only
   when the user explicitly flags a driver as "suspected confounded" (optional advanced path — a
   basic UI trigger is enough, don't over-build this).
4. `backend/app/core/evidence/evidence_builder.py` — `build_evidence(finding_type, computation,
   source_freshness, method_used) -> dict` returns `{method, statistic, p_value_or_effect_size,
   source_freshness, lineage: [source_ids/steps that produced this]}`. Every driver/anomaly finding
   must be wrapped through this before being stored.
5. `backend/app/api/drivers.py` — `GET /drivers/{kpi_id}` runs decomposition across all dimensions
   in the KPI's contract, stores each as a `finding` with evidence, returns the ranked list.
6. `backend/app/api/evidence.py` — `GET /evidence/{finding_id}` returns the full evidence record.

## UI tasks
1. `frontend/src/pages/DriversPage.tsx` — KPI selector, a waterfall/bar chart (Recharts) of driver
   contributions summing to the total movement, each bar clickable.
2. Clicking a driver bar opens an "Evidence" side panel/modal showing: method used, statistic/
   p-value, source freshness timestamp, and the lineage trail (plain text list, e.g. "source:
   sales.csv → canonical dataset X → KPI Y → driver decomposition").
3. Enable "Drivers" nav item.
4. `frontend/src/api/drivers.ts`, `frontend/src/api/evidence.ts` — fetch wrappers.

## Files to create
**Backend:** `backend/app/core/drivers/__init__.py`, `backend/app/core/drivers/contribution.py`,
`backend/app/core/drivers/causal.py`, `backend/app/core/evidence/__init__.py`,
`backend/app/core/evidence/evidence_builder.py`, `backend/app/api/drivers.py`,
`backend/app/api/evidence.py`.

**Frontend:** `frontend/src/pages/DriversPage.tsx`, `frontend/src/api/drivers.ts`,
`frontend/src/api/evidence.ts`.

## Tests to write & run
- `backend/tests/test_contribution.py`: construct a synthetic dataset where the movement across 2
  dimension slices is known by design (e.g. slice A contributes +10, slice B contributes -3, total
  +7) — assert `decompose_contribution` recovers these numbers within a small tolerance and that
  they sum to the total.
- `backend/tests/test_evidence.py`: assert every finding returned by `/drivers/{kpi_id}` has all
  required evidence fields populated and non-null.
- Run `pytest` and confirm all pass.

## Manual verification checklist
- [ ] Open Drivers for a materially-moved KPI, confirm the bars sum to the KPI's total movement.
- [ ] Click a driver, confirm the evidence panel shows a real method name, statistic, freshness
      timestamp, and lineage trail (not placeholder text).
- [ ] `pytest` passes.

## Definition of Done
Every driver finding is decomposed with numbers that reconcile to the total movement, and every
finding is backed by inspectable, traceable evidence.

## STOP
Summarize what was built, how to verify it, and write:
**"Phase 7 complete. Waiting for your approval before starting Phase 8."**
