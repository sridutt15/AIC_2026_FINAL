# PHASE 9 — Insight Generator & Recommendation Evidence Package (still no LLM)

## Objective
Turn verified findings into persona-specific insight text using deterministic templates (no LLM),
and assemble the structured package that Phase 10's LLM will eventually phrase into
recommendations.

## Prerequisites
Phase 8 approved and working (confidence-scored, persona-filtered findings must exist).

## Backend tasks
1. `backend/app/db.py` — add `CREATE TABLE IF NOT EXISTS insights (insight_id TEXT PRIMARY KEY,
   kpi_id TEXT, persona_id TEXT, text TEXT, generated_at TEXT)` and `CREATE TABLE IF NOT EXISTS
   recommendation_packages (package_id TEXT PRIMARY KEY, kpi_id TEXT, package_json TEXT, created_at
   TEXT)`.
2. `backend/app/core/insight_templates/generator.py` — deterministic string-template functions
   (plain Python f-strings or a simple template engine — **not** an LLM) that fill in: KPI name,
   direction (up/down), magnitude, top driver, confidence level, and a persona-appropriate tone
   (e.g. Category Manager gets driver-level detail; CFO gets headline + financial impact only).
   Must be provably deterministic: calling it twice with identical inputs returns an identical
   string.
3. `backend/app/core/recommendation/lever_library.py` — a small rule-based lookup mapping driver
   types (price/volume/mix/marketing/supply/seasonality/etc., inferred from dimension names in the
   contract) to plausible controllable levers and candidate actions. Document that this is a
   heuristic starting library, not exhaustive.
4. `backend/app/core/recommendation/package_builder.py` — `build_package(finding, evidence,
   confidence, lever_library) -> dict` assembles: `driver → controllable_lever → candidate_action →
   expected_impact → owner (persona) → confidence → monitoring_plan`. This structured object is
   exactly what gets handed to the LLM in Phase 10 — no raw data included.
5. `backend/app/api/insights.py` — `GET /insights/{kpi_id}?persona_id=` generates/returns insight
   text.
6. `backend/app/api/recommendations.py` (partial — Phase 10 finishes it) — for now, add
   `GET /recommendations/{kpi_id}/package` returning the built structured package only (no LLM call
   yet).

## UI tasks
1. `frontend/src/pages/InsightsPage.tsx` — KPI + persona selector, insight card showing the
   generated text, plus a "Regenerate" button and a note: "Deterministic — regenerating produces
   identical text." Include a small diff-check in the UI (call regenerate, show both outputs side
   by side) to visibly prove determinism.
2. Enable "Insights" nav item.
3. `frontend/src/api/insights.ts`, `frontend/src/api/recommendations.ts` — fetch wrappers (the
   latter will be extended in Phase 10).

## Files to create
**Backend:** `backend/app/core/insight_templates/__init__.py`,
`backend/app/core/insight_templates/generator.py`,
`backend/app/core/recommendation/__init__.py`,
`backend/app/core/recommendation/lever_library.py`,
`backend/app/core/recommendation/package_builder.py`, `backend/app/api/insights.py`,
`backend/app/api/recommendations.py`.

**Frontend:** `frontend/src/pages/InsightsPage.tsx`, `frontend/src/api/insights.ts`,
`frontend/src/api/recommendations.ts`.

## Tests to write & run
- `backend/tests/test_insight_generator.py`: call the generator twice with identical synthetic
  input, assert the output strings are byte-for-byte identical.
- `backend/tests/test_recommendation_package.py`: assert `build_package` output always contains
  all seven required fields, non-null, for a range of synthetic driver types.
- Run `pytest` and confirm all pass.

## Manual verification checklist
- [ ] Generate an insight, click Regenerate, confirm the two outputs are identical.
- [ ] Check the structured recommendation package for a KPI includes all seven fields sensibly
      filled in.
- [ ] `pytest` passes.

## Definition of Done
Insight text and the recommendation's underlying structure are both fully deterministic and
reproducible, with zero LLM calls anywhere in this phase.

## STOP
Summarize what was built, how to verify it, and write:
**"Phase 9 complete. Waiting for your approval before starting Phase 10."**
