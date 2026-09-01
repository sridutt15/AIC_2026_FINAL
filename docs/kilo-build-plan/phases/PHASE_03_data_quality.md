# PHASE 3 — Data Quality Engine

## Objective
Run deterministic data-quality checks against a source (using thresholds from its semantic
contract where relevant) and surface a quality report in the UI.

## Prerequisites
Phase 2 approved and working (a semantic contract must exist for the source).

## Backend tasks
1. `backend/app/db.py` — add `CREATE TABLE IF NOT EXISTS quality_reports (source_id TEXT PRIMARY
   KEY, report_json TEXT, created_at TEXT)`.
2. `backend/app/core/quality/checks.py` — pure functions, each returning a list of issues
   (column, issue_type, severity, affected_row_count):
   - `check_missing_values(df)` — flags columns above a null-ratio threshold (e.g. >5%).
   - `check_duplicates(df)` — flags fully duplicate rows.
   - `check_invalid_ranges(df, contract)` — for measure columns, flags impossible values (e.g.
     negative values where the contract doesn't allow negatives — default: flag negatives on any
     measure unless the user's contract says otherwise).
   - `check_type_violations(df)` — values that don't match the column's declared dtype from
     profiling.
   - `check_outliers(df)` — IQR-based outlier flags on numeric columns.
3. `backend/app/core/quality/report_builder.py` — `build_quality_report(df, contract) -> dict`
   runs all checks, computes an overall 0–100 quality score (deterministic formula: start at 100,
   subtract weighted penalties per issue type — document the weights in a comment), and returns
   `{score, issues: [...]}`.
4. `backend/app/api/data_quality.py` — `GET /data-quality/{source_id}` (build if not cached, else
   return stored).

## UI tasks
1. `frontend/src/pages/DataQualityPage.tsx` — source selector, a large quality-score gauge/badge
   (color-coded: green ≥80, yellow 50–79, red <50), and a table of issues (column, issue type,
   severity, affected row count), sortable by severity.
2. Enable "Data Quality" nav item.
3. `frontend/src/api/dataQuality.ts` — fetch wrapper.

## Files to create
**Backend:** `backend/app/core/quality/__init__.py`, `backend/app/core/quality/checks.py`,
`backend/app/core/quality/report_builder.py`, `backend/app/api/data_quality.py`.

**Frontend:** `frontend/src/pages/DataQualityPage.tsx`, `frontend/src/api/dataQuality.ts`.

## Tests to write & run
- `backend/tests/test_quality.py`: build a synthetic "dirty" DataFrame with a known number of
  nulls, a known number of duplicate rows, one negative value in a measure column, and one
  statistical outlier. Assert each check function returns the exact expected count, and assert the
  computed score is lower than a clean DataFrame's score.
- Run `pytest` and confirm all pass.

## Manual verification checklist
- [ ] Run the quality report on the Phase 1 source.
- [ ] Confirm the score and issue list look reasonable given the data's actual condition.
- [ ] `pytest` passes.

## Definition of Done
Any uploaded source gets an accurate, deterministic quality score and issue breakdown, visible in
the UI.

## STOP
Summarize what was built, how to verify it, and write:
**"Phase 3 complete. Waiting for your approval before starting Phase 4."**
