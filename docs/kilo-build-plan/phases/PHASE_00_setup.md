# PHASE 0 — Project Setup & Scaffolding

## Objective
Stand up an empty but fully runnable full-stack skeleton: FastAPI backend with one health-check
endpoint, React+Vite frontend with a basic layout that shows backend connection status. No business
logic yet. This proves the toolchain works before any real feature is built.

## Prerequisites
None — this is the first phase.

## Backend tasks
1. Create the folder structure under `backend/` exactly as shown in
   `02_TECH_STACK_AND_FOLDER_STRUCTURE.md` (empty `__init__.py` files where needed for Python
   packages: `app/`, `app/api/`, `app/core/`, `app/models/`).
2. Create `backend/requirements.txt` with: `fastapi`, `uvicorn[standard]`, `pandas`, `numpy`,
   `scipy`, `statsmodels`, `ruptures`, `pydantic`, `python-multipart`, `python-dotenv`, `pytest`,
   `httpx`, `anthropic`.
3. Create `backend/app/config.py` — loads `.env` via `python-dotenv`, exposes a `Settings` object
   with at least `PORT`, `ANTHROPIC_API_KEY` (optional, may be empty for now), `DATABASE_PATH`.
4. Create `backend/.env.example` documenting the above variables with placeholder values (no real
   keys).
5. Create `backend/app/db.py` — a helper that opens a sqlite connection to `backend/data/app.db`
   (creating the file/folder if missing) and a function `init_db()` that creates any needed tables
   (empty for now — later phases will add `CREATE TABLE` statements here).
6. Create `backend/app/api/health.py` with a router exposing `GET /health` returning
   `{"status": "ok"}`.
7. Create `backend/app/main.py` — FastAPI app instance, CORS middleware allowing the frontend's
   dev origin (`http://localhost:5173`), registers the health router, calls `init_db()` on startup.
8. Create `backend/data/uploads/` (empty folder, e.g. via a `.gitkeep`-style placeholder file if
   needed — NOT a git file, just an empty marker file like `README.md` saying "uploaded files go
   here").

## UI tasks
1. Scaffold a Vite + React + TypeScript project in `frontend/` (`npm create vite@latest`
   equivalent, template `react-ts`).
2. Install and configure Tailwind CSS.
3. Install `recharts` (not used yet, but confirm it installs cleanly).
4. Build `frontend/src/App.tsx`: a top navbar titled "KPI Intelligence-to-Action Engine", a left
   sidebar listing all future phase pages as disabled/greyed-out nav items (Upload, Profile,
   Semantic Contract, Data Quality, Canonical Model, KPIs, Anomalies, Drivers, Confidence,
   Insights, Recommendations, Feedback, Telemetry, Dashboard), and a main content area.
5. On load, `App.tsx` calls `GET http://localhost:8000/health` and displays "Backend: Connected"
   in green or "Backend: Not reachable" in red.
6. Create `frontend/src/api/health.ts` as the fetch wrapper for this call, establishing the pattern
   future phases will follow (one file per backend api module).

## Files to create
**Backend:** `backend/requirements.txt`, `backend/.env.example`, `backend/app/__init__.py`,
`backend/app/config.py`, `backend/app/db.py`, `backend/app/main.py`, `backend/app/api/__init__.py`,
`backend/app/api/health.py`, `backend/app/core/__init__.py`, `backend/app/models/__init__.py`,
`backend/data/uploads/README.md`.

**Frontend:** `frontend/` (full Vite scaffold), `frontend/src/App.tsx`, `frontend/src/api/health.ts`,
`frontend/tailwind.config.js`.

## Tests to write & run
- `backend/tests/test_health.py`: calls `GET /health` via `httpx`/FastAPI TestClient, asserts status
  code 200 and body `{"status": "ok"}`.
- Run `pytest` from `backend/` and confirm it passes.

## Manual verification checklist
- [ ] `uvicorn app.main:app --reload` starts without errors from `backend/`.
- [ ] `npm run dev` starts without errors from `frontend/`.
- [ ] Opening the frontend in a browser shows the navbar, sidebar with all future pages listed
      (disabled), and "Backend: Connected" in green.
- [ ] `pytest` passes.

## Definition of Done
Both servers run cleanly, the health check round-trips from UI to backend and back, the full future
navigation structure is visible (even if disabled), and the test passes.

## STOP
Summarize what was created, give the exact run commands for both servers, and write:
**"Phase 0 complete. Waiting for your approval before starting Phase 1."**
