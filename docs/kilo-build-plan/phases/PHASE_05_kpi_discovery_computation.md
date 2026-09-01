# PHASE 5 — KPI Discovery, Validation & Computation

## Objective
From a canonical dataset and its source semantic contract(s), automatically discover candidate
KPIs, validate them (including flagging sparse-history/new KPIs), and compute value/trend/baseline/
benchmark/confidence-interval for each valid KPI.

## Prerequisites
Phase 4 approved and working (a canonical dataset must exist).

## Backend tasks
1. `backend/app/db.py` — add `CREATE TABLE IF NOT EXISTS kpis (kpi_id TEXT PRIMARY KEY, dataset_id
   TEXT, definition_json TEXT, status TEXT)` and `CREATE TABLE IF NOT EXISTS kpi_computations
   (kpi_id TEXT PRIMARY KEY, computation_json TEXT, computed_at TEXT)`.
2. `backend/app/core/kpi_engine/discovery.py` — `discover_kpis(canonical_df, contracts) -> list`
   generates candidate KPIs from each `kpi_definitions` entry across the merged contracts (measure
   + aggregation + optional slice dimensions), deduplicating identical candidates.
3. `backend/app/core/kpi_engine/validation.py` — `validate_kpi(kpi, canonical_df) -> dict` checks:
   sample size (flag `low-data` if fewer than a defined minimum number of time periods, e.g. < 8),
   non-zero denominator for ratios, non-degenerate variance. Returns
   `{status: "valid"|"low-data"|"invalid", reason}`.
4. `backend/app/core/kpi_engine/computation.py` — `compute_kpi(kpi, canonical_df) -> dict` returns:
   `value` (latest period), `trend` (time series of period values), `baseline` (prior-period or
   rolling average), `benchmark` (overall average across full history), `confidence_interval`
   (bootstrap resample of the trend, e.g. 1000 resamples, 95% CI).
5. `backend/app/api/kpi.py` — `POST /kpi/discover/{dataset_id}` runs discovery+validation, stores
   and returns the KPI list with statuses. `GET /kpi/{kpi_id}/compute` runs/returns computation
   (cache in `kpi_computations`).

## UI tasks
1. `frontend/src/pages/KpiDashboardPage.tsx` — dataset selector, "Discover KPIs" button, then a
   card grid of discovered KPIs showing name, status badge (Valid green / Low-Data yellow / Invalid
   red), latest value. Clicking a card opens a detail view with a Recharts line chart of the trend,
   a shaded confidence-interval band, and a horizontal benchmark line.
2. Enable "KPIs" nav item.
3. `frontend/src/api/kpi.ts` — fetch wrapper.

## Files to create
**Backend:** `backend/app/core/kpi_engine/__init__.py`, `backend/app/core/kpi_engine/discovery.py`,
`backend/app/core/kpi_engine/validation.py`, `backend/app/core/kpi_engine/computation.py`,
`backend/app/api/kpi.py`.

**Frontend:** `frontend/src/pages/KpiDashboardPage.tsx`, `frontend/src/api/kpi.ts`.

## Tests to write & run
- `backend/tests/test_kpi_discovery.py`: given a contract with 2 measures × 1 slice dimension,
  assert the expected number of distinct KPI candidates is generated with no duplicates.
- `backend/tests/test_kpi_validation.py`: one KPI with 3 time periods → asserts status `low-data`;
  one KPI with 20 periods and healthy variance → asserts status `valid`.
- `backend/tests/test_kpi_computation.py`: synthetic time series with a known mean and known trend
  → asserts computed `value`/`baseline`/`benchmark` match expected numbers within a small tolerance,
  and the CI bounds contain the true mean.
- Run `pytest` and confirm all pass.

## Manual verification checklist
- [ ] Run KPI discovery on the Phase 4 canonical dataset; confirm 3–5+ KPIs are found.
- [ ] Confirm at least one KPI with genuinely short history is correctly flagged `low-data` (upload
      a small extra test source with only a few periods if needed to force this case).
- [ ] Open a KPI's detail chart and confirm the trend/CI/benchmark render correctly.
- [ ] `pytest` passes.

## Definition of Done
KPIs are discovered and computed with no LLM involvement, sparse-history KPIs are correctly
flagged, and everything is visible/reproducible in the UI.

## STOP
Summarize what was built, how to verify it, and write:
**"Phase 5 complete. Waiting for your approval before starting Phase 6."**
