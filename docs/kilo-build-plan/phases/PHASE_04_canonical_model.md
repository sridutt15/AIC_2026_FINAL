# PHASE 4 — Canonical Data Model (Reconciliation Layer)

## Objective
Merge two or more sources — potentially at different grains and refresh cadences — into a single
canonical dataset, using explicit, documented reconciliation rules so the result stays traceable.

## Prerequisites
Phase 3 approved and working, and at least 2 sources uploaded (upload a second sample source now if
you only have one — note this in your Phase 4 summary).

## Backend tasks
1. `backend/app/db.py` — add `CREATE TABLE IF NOT EXISTS canonical_datasets (dataset_id TEXT
   PRIMARY KEY, source_ids TEXT, join_config_json TEXT, created_at TEXT)`.
2. `backend/app/core/canonical/reconciler.py`:
   - `align_grain(df, from_cadence, to_cadence)` — deterministic upsampling/downsampling rule
     (e.g. daily→weekly = sum/avg per week depending on measure type; weekly→daily = forward-fill,
     clearly documented as "last-observation-carried-forward"). Document the exact rule used in a
     docstring — this must be explainable, not a black box.
   - `reconcile(sources: list[dict], join_keys: dict) -> DataFrame` — takes 2+ loaded DataFrames
     plus a join key mapping (e.g. `{"date": "date", "region": "region_code"}`), aligns their grain
     via `align_grain`, and merges them into one canonical table.
3. `backend/app/api/canonical_model.py` — `POST /canonical/build` (body: list of source_ids + join
   key mapping) builds and stores the canonical dataset (as a parquet/csv file under
   `data/uploads/canonical/{dataset_id}.csv` plus a DB row), returns `dataset_id` + a preview
   (first 20 rows). `GET /canonical/{dataset_id}/preview?page=` for paginated preview.

## UI tasks
1. `frontend/src/pages/CanonicalModelPage.tsx` — multi-select of existing sources, a simple
   key-mapping UI (for each selected source, let the user pick which of its columns maps to a
   common join key), a "Build" button, then a paginated preview table of the resulting canonical
   dataset once built. List of previously built canonical datasets below.
2. Enable "Canonical Model" nav item.
3. `frontend/src/api/canonicalModel.ts` — fetch wrapper.

## Files to create
**Backend:** `backend/app/core/canonical/__init__.py`, `backend/app/core/canonical/reconciler.py`,
`backend/app/api/canonical_model.py`.

**Frontend:** `frontend/src/pages/CanonicalModelPage.tsx`, `frontend/src/api/canonicalModel.ts`.

## Tests to write & run
- `backend/tests/test_canonical.py`: build two small synthetic DataFrames — one daily, one weekly,
  sharing a `date` + `region` key — with known values. Run `reconcile` and assert the merged
  output's row count and specific cell values match hand-computed expected results given the
  documented alignment rule.
- Run `pytest` and confirm all pass.

## Manual verification checklist
- [ ] Build a canonical dataset from 2 uploaded sources with different grains.
- [ ] Confirm the preview table looks correctly merged (spot-check a few rows against the raw
      source files).
- [ ] `pytest` passes.

## Definition of Done
Two or more heterogeneous sources can be combined into one canonical dataset via an explicit,
testable, documented reconciliation rule, previewable in the UI.

## STOP
Summarize what was built, how to verify it, and write:
**"Phase 4 complete. Waiting for your approval before starting Phase 5."**
