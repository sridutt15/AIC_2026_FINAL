# PHASE 8 — Confidence & Abstention Engine + Persona & Access Control

## Objective
Score confidence for every finding and abstain when evidence is weak/contradictory instead of
forcing a narrative. Add role-based personas that filter what data/findings each role can see.

## Prerequisites
Phase 7 approved and working (findings with evidence must exist).

## Backend tasks
1. `backend/app/db.py` — add `CREATE TABLE IF NOT EXISTS personas (persona_id TEXT PRIMARY KEY,
   name TEXT, access_json TEXT)`. Seed two personas on `init_db()` if the table is empty:
   `"category_manager"` (broad access, tactical detail) and `"cfo"` (financial/headline-level
   access only, restricted from operational-detail columns — pick a plausible restriction, e.g. a
   `cost_breakdown`-type column if present, otherwise restrict by column role instead of a specific
   name).
2. `backend/app/core/confidence/scorer.py` — `score_confidence(finding, evidence, quality_report)
   -> dict` combines: evidence quality (from data quality score), statistical significance
   (p-value/effect size from evidence), sample size (from KPI validation status), and — if multiple
   sources/methods flagged the same finding — cross-method agreement. Returns
   `{level: "high"|"medium"|"low"|"abstain", reasons: [...], missing_evidence: [...]}`. Below a
   defined threshold, or on contradictory signals (e.g. two detectors disagree on direction),
   `level` must be `"abstain"`.
3. `backend/app/core/persona/access_control.py` — `filter_for_persona(data, persona) -> data`
   applies the persona's `access_json` rules (row/column/domain-level) to any findings/KPI list
   before it's returned to the API layer.
4. `backend/app/api/persona.py` — `GET /personas` (list seeded personas).
5. Update every existing GET endpoint that returns KPI/driver/insight data (`kpi.py`, `drivers.py`,
   `anomaly.py`) to accept a `persona_id` query parameter and apply `filter_for_persona` before
   responding. Update `drivers.py`/`anomaly.py` responses to include the confidence result from
   `score_confidence`, with `abstain`-level findings replaced by a message describing what
   evidence is missing instead of a fabricated conclusion.

## UI tasks
1. Add a persona switcher dropdown to the navbar in `App.tsx` (Category Manager / CFO), stored in
   app-level state, passed as a query param on every relevant fetch.
2. Update `DriversPage.tsx` / `KpiDashboardPage.tsx` / `AnomalyPage.tsx` to show a confidence badge
   (High/Medium/Low/Abstained) on each finding; abstained findings render a distinct "insufficient
   or contradictory evidence" card explaining what's missing, instead of a chart.
3. Confirm switching personas visibly changes what's shown (fewer KPIs/columns for the restricted
   persona).
4. `frontend/src/api/persona.ts` — fetch wrapper.

## Files to create
**Backend:** `backend/app/core/confidence/__init__.py`, `backend/app/core/confidence/scorer.py`,
`backend/app/core/persona/__init__.py`, `backend/app/core/persona/access_control.py`,
`backend/app/api/persona.py`; modify `kpi.py`, `drivers.py`, `anomaly.py`.

**Frontend:** modify `App.tsx`, `KpiDashboardPage.tsx`, `DriversPage.tsx`, `AnomalyPage.tsx`;
create `frontend/src/api/persona.ts`.

## Tests to write & run
- `backend/tests/test_confidence.py`: a finding with small sample size and low data-quality score
  → asserts `level == "abstain"`; a finding with strong significance and high quality → asserts
  `level == "high"`.
- `backend/tests/test_persona_access.py`: given a persona with a restricted column/domain, assert
  `filter_for_persona` removes that data from the output for that persona but not for an
  unrestricted persona.
- Run `pytest` and confirm all pass.

## Manual verification checklist
- [ ] Switch personas in the navbar, confirm restricted data disappears for the CFO persona.
- [ ] Locate or force a low-confidence finding (e.g. a low-data KPI's driver breakdown), confirm it
      renders as an honest "abstain" message rather than a confident-looking chart.
- [ ] `pytest` passes.

## Definition of Done
Every finding carries a real confidence level, weak findings abstain honestly, and access is
enforced per persona across every relevant endpoint and page.

## STOP
Summarize what was built, how to verify it, and write:
**"Phase 8 complete. Waiting for your approval before starting Phase 9."**
