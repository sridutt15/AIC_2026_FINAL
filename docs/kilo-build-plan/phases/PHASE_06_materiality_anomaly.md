# PHASE 6 — Materiality/Prioritization & Anomaly Detection

## Objective
Rank KPI movements by combined statistical + business materiality, and detect anomalies/change
points in each KPI's trend.

## Prerequisites
Phase 5 approved and working (computed KPIs must exist).

## Backend tasks
1. `backend/app/db.py` — add `CREATE TABLE IF NOT EXISTS anomalies (kpi_id TEXT, anomaly_json TEXT,
   detected_at TEXT)`.
2. `backend/app/core/kpi_engine/materiality.py` — `score_materiality(kpi_computation, contract) ->
   float` combines a statistical-significance component (how many standard deviations the latest
   value is from baseline) with a business-impact weight (from the contract's threshold/weight
   config, default equal weighting if not set by the user). Document the exact formula in a
   docstring.
3. `backend/app/core/anomaly/detectors.py`:
   - `detect_change_points(series) -> list[int]` using `ruptures` (e.g. PELT method).
   - `detect_control_limit_breaches(series) -> list[int]` — points beyond ±3 std dev of a rolling
     mean.
   - `detect_outliers(series) -> list[int]` — robust MAD-based outlier indices.
   - `run_all_detectors(series) -> dict` combining all three with which method flagged which index.
4. `backend/app/api/anomaly.py` — `GET /anomaly/{kpi_id}` runs detectors on the KPI's trend, stores
   and returns results.
5. Update `backend/app/api/kpi.py`'s discover/list response to include the materiality score so the
   frontend can sort by it.

## UI tasks
1. Update `KpiDashboardPage.tsx` — sort the KPI card grid by materiality score descending by
   default, add a materiality score badge to each card.
2. `frontend/src/pages/AnomalyPage.tsx` — KPI selector, trend line chart with detected anomaly
   points/change-points highlighted (different marker colors per detection method), a small legend.
3. Enable "Anomalies" nav item.
4. `frontend/src/api/anomaly.ts` — fetch wrapper.

## Files to create
**Backend:** `backend/app/core/kpi_engine/materiality.py`, `backend/app/core/anomaly/__init__.py`,
`backend/app/core/anomaly/detectors.py`, `backend/app/api/anomaly.py`.

**Frontend:** `frontend/src/pages/AnomalyPage.tsx`, `frontend/src/api/anomaly.ts`; update
`KpiDashboardPage.tsx`.

## Tests to write & run
- `backend/tests/test_materiality.py`: two synthetic KPIs, one with a large statistically
  significant movement and high business weight, one with a small movement and low weight —
  assert the first scores higher.
- `backend/tests/test_anomaly.py`: synthetic series with a deliberately injected level shift at a
  known index — assert `detect_change_points` flags an index within a small tolerance window of
  the true shift, and a series with no shift produces no false positive change point.
- Run `pytest` and confirm all pass.

## Manual verification checklist
- [ ] Confirm the KPI dashboard now sorts by materiality with the most material movement first.
- [ ] Open the Anomaly page for a KPI with a visible shift in its trend, confirm it's highlighted
      correctly.
- [ ] `pytest` passes.

## Definition of Done
KPI movements are prioritized by a combined statistical + business score, and anomalies/change
points are detected and visualized without any LLM involvement.

## STOP
Summarize what was built, how to verify it, and write:
**"Phase 6 complete. Waiting for your approval before starting Phase 7."**
