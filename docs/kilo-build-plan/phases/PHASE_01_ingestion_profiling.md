# PHASE 1 — Data Ingestion & Schema Profiler

## Objective
Let a user upload any CSV/XLSX/JSON file as a "source," declare its grain and refresh cadence, and
see a deterministic profile of every column (type, nulls, cardinality, detected role). This must
work for arbitrary company data — never hardcode column names.

## Prerequisites
Phase 0 approved and working.

## Backend tasks
1. `backend/app/db.py` — add `CREATE TABLE IF NOT EXISTS sources (source_id TEXT PRIMARY KEY,
   filename TEXT, grain TEXT, cadence TEXT, uploaded_at TEXT)` and `CREATE TABLE IF NOT EXISTS
   profiles (source_id TEXT, profile_json TEXT, created_at TEXT)` to `init_db()`.
2. `backend/app/core/ingestion/loaders.py` — pure functions `load_csv(path)`, `load_xlsx(path)`,
   `load_json(path)`, each returning a pandas DataFrame with standardized column names (trimmed,
   lower-cased, spaces→underscores). A dispatcher `load_source(path, filetype)` picks the right
   loader. No assumptions about specific column names anywhere.
3. `backend/app/api/ingestion.py` — `POST /ingestion/upload` (multipart form: file + `grain` +
   `cadence` fields) saves the raw file to `data/uploads/{source_id}/`, generates a UUID
   `source_id`, inserts a row into `sources`, returns `{source_id, filename, grain, cadence}`.
   `GET /ingestion/sources` lists all uploaded sources.
4. `backend/app/core/profiling/profiler.py` — pure function `profile_dataframe(df) -> dict`
   returning, per column: `dtype`, `null_ratio`, `cardinality`, `is_unique`, sample values (first 5
   non-null), and a heuristic `detected_role` in
   `{"temporal", "numerical", "categorical", "identifier"}` (identifier = cardinality ratio > 0.95;
   temporal = column parses as a date for >90% of non-null values; numerical = numeric dtype;
   else categorical).
5. `backend/app/api/profiling.py` — `GET /profiling/{source_id}` loads the source's raw file, runs
   `profile_dataframe`, stores result in `profiles`, returns it (or returns cached result if
   already profiled).

## UI tasks
1. `frontend/src/pages/UploadPage.tsx` — file picker, dropdown for grain (Transactional / Daily /
   Weekly / Monthly / Custom) and cadence (Real-time / Nightly batch / Weekly), upload button, and
   a list below showing all previously uploaded sources with filename/grain/cadence/upload time.
2. `frontend/src/pages/ProfilePage.tsx` — source selector dropdown, then a table: column name,
   dtype, null %, cardinality, detected role (as a colored badge), sample values.
3. Enable the "Upload" and "Profile" nav items in the sidebar (remove disabled state), route to
   these pages.
4. `frontend/src/api/ingestion.ts`, `frontend/src/api/profiling.ts` — fetch wrappers.

## Files to create
**Backend:** `backend/app/core/ingestion/__init__.py`, `backend/app/core/ingestion/loaders.py`,
`backend/app/api/ingestion.py`, `backend/app/core/profiling/__init__.py`,
`backend/app/core/profiling/profiler.py`, `backend/app/api/profiling.py`.

**Frontend:** `frontend/src/pages/UploadPage.tsx`, `frontend/src/pages/ProfilePage.tsx`,
`frontend/src/api/ingestion.ts`, `frontend/src/api/profiling.ts`.

## Tests to write & run
- `backend/tests/test_ingestion.py`: uploads a small synthetic CSV via TestClient, asserts a row
  appears in `sources` and the file exists on disk.
- `backend/tests/test_profiling.py`: builds a small synthetic DataFrame with a known date column,
  numeric column, and a near-unique ID column; asserts `profile_dataframe` detects each role
  correctly and null_ratio/cardinality match hand-computed expected values.
- Run `pytest` and confirm all pass.

## Manual verification checklist
- [ ] Upload a real or sample CSV with mixed column types.
- [ ] Confirm it appears in the source list with correct grain/cadence.
- [ ] Open the Profile page, select the source, confirm each column's detected role looks sensible.
- [ ] `pytest` passes.

## Definition of Done
A user can upload any tabular file and immediately see a correct, deterministic profile of it in
the UI, with no hardcoded assumptions about its columns.

## STOP
Summarize what was built, how to run/verify it, and write:
**"Phase 1 complete. Waiting for your approval before starting Phase 2."**
