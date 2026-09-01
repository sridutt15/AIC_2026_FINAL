# PHASE 10 — LLM Recommendation Layer (the ONLY phase allowed to call an LLM)

## Objective
Turn the Phase 9 structured recommendation package into persona-phrased natural-language
recommendations using an LLM — and only the LLM, never raw data. Track tokens/cost/latency and
prove, via a ledger, that every earlier stage used no LLM.

## Prerequisites
Phase 9 approved and working (structured recommendation packages must exist).

## Backend tasks
1. `backend/app/db.py` — add `CREATE TABLE IF NOT EXISTS llm_calls (call_id TEXT PRIMARY KEY,
   kpi_id TEXT, package_hash TEXT, prompt_tokens INTEGER, completion_tokens INTEGER, latency_ms
   INTEGER, cost_usd REAL, cached BOOLEAN, created_at TEXT)`.
2. `backend/app/core/llm/client.py` — thin wrapper around the `anthropic` SDK, reading
   `ANTHROPIC_API_KEY` from settings. Function `call_llm(prompt: str) -> dict` returns text +
   usage stats. Must be easily mockable for tests (accept an injectable client/transport).
3. `backend/app/core/llm/prompt_templates.py` — builds the prompt **strictly from the structured
   package fields** (driver, lever, action, impact, owner, confidence, monitoring_plan) plus the
   persona's tone preference. Never includes raw dataframes or unaggregated data.
4. `backend/app/core/llm/cache.py` — hashes the structured package (stable JSON hash), checks
   `llm_calls` for an existing result with that hash before calling the API; if found, reuse it and
   mark `cached=true`, skipping the API call entirely.
5. Finish `backend/app/api/recommendations.py` — `GET /recommendations/{kpi_id}?persona_id=`:
   fetches/builds the package (Phase 9 logic), checks cache, calls LLM if needed, logs the call to
   `llm_calls` (tokens, latency, estimated cost using the model's published per-token rate), returns
   `{recommendation_text, package, llm_call_metadata}`.
6. `backend/app/api/telemetry.py` (partial — Phase 11 finishes it) — add `GET /telemetry/llm-ledger`
   returning a fixed table listing every architecture stage (ingestion, profiling, semantic
   contract, data quality, canonical model, KPI discovery/validation/computation, materiality,
   anomaly detection, driver analysis, evidence, confidence, insight generation, recommendation
   packaging) each marked `llm_used: false`, plus the recommendation stage marked `llm_used: true` —
   this is a static/documented list, not something requiring live inspection, since the codebase
   itself guarantees it.

## UI tasks
1. `frontend/src/pages/RecommendationsPage.tsx` — KPI + persona selector, shows the LLM-phrased
   recommendation text alongside the underlying structured package (driver/lever/action/impact/
   owner/confidence/monitoring) in a table, so a user can visually confirm the LLM didn't invent
   structure beyond what was given. Below that, a small "LLM Ledger" widget rendering the
   `/telemetry/llm-ledger` table (stage → LLM used Yes/No), and the last call's tokens/latency/cost
   if available.
2. Enable "Recommendations" nav item.
3. Update `frontend/src/api/recommendations.ts` to call the finished endpoint.

## Files to create
**Backend:** `backend/app/core/llm/__init__.py`, `backend/app/core/llm/client.py`,
`backend/app/core/llm/prompt_templates.py`, `backend/app/core/llm/cache.py`; finish
`backend/app/api/recommendations.py`; add ledger route to `backend/app/api/telemetry.py`.

**Frontend:** `frontend/src/pages/RecommendationsPage.tsx`; update
`frontend/src/api/recommendations.ts`.

## Tests to write & run
- `backend/tests/test_llm_client.py`: **mock** the Anthropic API call (do not hit the real API in
  automated tests) — assert `call_llm` correctly parses a mocked response into text + usage stats.
- `backend/tests/test_recommendations_endpoint.py`: with the LLM client mocked, call the endpoint
  twice with the same package — assert the second call is served from cache (`cached=true`, no
  second mock invocation).
- Run `pytest` and confirm all pass (no real API key needed for automated tests).

## Manual verification checklist
- [ ] With a real `ANTHROPIC_API_KEY` set in `.env`, generate one live recommendation and confirm
      readable, sensible text appears.
- [ ] Confirm tokens/latency/cost are logged and shown in the UI.
- [ ] Regenerate the same recommendation and confirm it's served from cache instantly (no
      duplicate API cost).
- [ ] Confirm the LLM Ledger widget shows every prior stage as `llm_used: No` and only this stage
      as `Yes`.
- [ ] `pytest` passes (using the mocked client, not a live key).

## Definition of Done
Exactly one place in the entire codebase calls an LLM, it never sees raw data, results are cached
to control cost, and the UI makes the LLM-vs-non-LLM split visibly provable.

## STOP
Summarize what was built, how to verify it, and write:
**"Phase 10 complete. Waiting for your approval before starting Phase 11."**
