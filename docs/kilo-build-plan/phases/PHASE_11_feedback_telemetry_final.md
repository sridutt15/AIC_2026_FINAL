# PHASE 11 — Feedback Loop, Telemetry, Final Decision Workspace & Demo Scenarios

## Objective
Close the loop with analyst feedback, finish the telemetry/cost dashboard, build the unified home
"Decision Workspace" page, and script the four demo scenarios the brief requires as evidence.

## Prerequisites
Phase 10 approved and working (recommendations must be generating end-to-end).

## Backend tasks
1. `backend/app/db.py` — add `CREATE TABLE IF NOT EXISTS feedback (feedback_id TEXT PRIMARY KEY,
   target_type TEXT, target_id TEXT, verdict TEXT, note TEXT, created_at TEXT)` (`target_type` is
   `"insight"` or `"recommendation"`; `verdict` is `"confirm"|"correct"|"reject"`).
2. `backend/app/core/feedback/store.py` — `record_feedback(...)` stores feedback, and
   `apply_feedback_adjustments()` — a simple deterministic rule: repeated `"reject"` verdicts on a
   given driver type nudge down that driver's weight in future materiality scoring (adjust the
   default weight table used in `materiality.py`, read from a small persisted config, not from the
   LLM prompt).
3. `backend/app/core/telemetry/logger.py` — central helper other modules can call to record
   per-stage latency (wrap key functions with a timing decorator), aggregated with the existing
   `llm_calls` table data.
4. `backend/app/api/feedback.py` — `POST /feedback`, `GET /feedback/{target_id}`.
5. Finish `backend/app/api/telemetry.py` — `GET /telemetry/summary` returning: average latency per
   stage, total LLM calls, total tokens, total estimated cost, cache hit rate.
6. `backend/tests/test_e2e_scenarios.py` (integration-style test using seeded synthetic data
   covering the full pipeline) asserting all four scenarios behave correctly:
   - **Scenario A (multi-factor movement, 2 personas):** a KPI with a clear multi-driver movement
     produces different insight text for Category Manager vs CFO personas.
   - **Scenario B (abstention):** a deliberately weak-evidence finding returns `level == "abstain"`
     end-to-end through the API, not a fabricated insight.
   - **Scenario C (sparse-history):** a newly "launched" KPI with few periods is flagged
     `low-data` through discovery→validation and does not produce a false-confidence trend.
   - **Scenario D (role-based security):** the restricted persona's API responses never contain the
     restricted column/domain, verified directly on the JSON response.

## UI tasks
1. `frontend/src/pages/FeedbackPage.tsx` — list of recent insights/recommendations with
   confirm/correct/reject buttons and a note field.
2. `frontend/src/pages/TelemetryPage.tsx` — dashboard of the `/telemetry/summary` data: latency per
   stage (bar chart), LLM calls/tokens/cost over time (line chart), cache hit rate (gauge).
3. `frontend/src/pages/DashboardPage.tsx` — the final home "Decision Workspace": for a selected
   dataset + persona, shows a top-to-bottom flow: Dataset health (quality score) → Top KPIs →
   Anomalies → Top drivers → Evidence summary → Insight → Recommendation, all on one page, reusing
   the components/pages built in earlier phases. Make this the app's default landing route.
4. Enable "Feedback," "Telemetry," and "Dashboard" nav items; set Dashboard as the default route.
5. `frontend/src/api/feedback.ts`, `frontend/src/api/telemetry.ts` — fetch wrappers.

## Files to create
**Backend:** `backend/app/core/feedback/__init__.py`, `backend/app/core/feedback/store.py`,
`backend/app/core/telemetry/__init__.py`, `backend/app/core/telemetry/logger.py`,
`backend/app/api/feedback.py`; finish `backend/app/api/telemetry.py`;
`backend/tests/test_e2e_scenarios.py`.

**Frontend:** `frontend/src/pages/FeedbackPage.tsx`, `frontend/src/pages/TelemetryPage.tsx`,
`frontend/src/pages/DashboardPage.tsx`, `frontend/src/api/feedback.ts`,
`frontend/src/api/telemetry.ts`; update `App.tsx` routing.

## Tests to write & run
- `backend/tests/test_feedback.py`: recording repeated "reject" feedback on a driver type measurably
  lowers that driver's weight in a subsequent materiality score calculation.
- `backend/tests/test_telemetry.py`: `/telemetry/summary` returns correctly aggregated numbers
  against seeded `llm_calls` rows.
- `backend/tests/test_e2e_scenarios.py`: all four scenarios pass (see backend tasks above).
- Run `pytest` and confirm **all** tests across the whole project still pass (full regression run,
  not just this phase's new tests).

## Manual verification checklist
- [ ] Submit feedback on an insight, confirm it's stored and visible.
- [ ] Open the Telemetry dashboard, confirm charts reflect real logged data (not placeholders).
- [ ] Open the new Dashboard/Decision Workspace home page, confirm it tells a coherent top-to-
      bottom story for a chosen dataset and persona.
- [ ] Manually run through Scenarios A, B, C, D in the actual UI (not just the automated test) —
      this is your judge-facing demo script. Write down the exact click-path for each so it can be
      repeated live during the presentation.
- [ ] Full `pytest` suite passes.

## Definition of Done
The full pipeline works end-to-end from raw upload to persona-specific recommendation, with
feedback, telemetry, and all four required demo scenarios provably working, and everything is
reachable from the single Dashboard home page.

## STOP
Summarize everything built across all 12 phases, give the run commands, list the four scenario
click-paths for the demo, and write:
**"Phase 11 complete. The project is feature-complete per the build plan. Waiting for your
instructions on what to do next (e.g. seed data, demo polish, additional company data sources)."**
