# TECH STACK & FOLDER STRUCTURE — reference for every phase

## Tech stack (fixed for the whole project — do not substitute)

**Backend:** Python 3.11, FastAPI, Uvicorn, Pandas, NumPy, SciPy, Statsmodels, Ruptures
(change-point detection), Pydantic v2, SQLite (via built-in `sqlite3`, no ORM needed for a
prototype), `python-multipart` (file uploads), `python-dotenv` (secrets), `pytest` + `httpx`
(testing).

**Frontend:** React 18 + Vite + TypeScript, Tailwind CSS (styling), Recharts (charts), native
`fetch` for API calls (no need for axios).

**LLM (Phase 10 only):** Anthropic Claude API via `anthropic` Python SDK, key read from `.env` as
`ANTHROPIC_API_KEY`.

**No Docker, no git, no ORM, no auth provider** — keep the prototype's moving parts minimal so an
agent can build it reliably. Persona-based access control is implemented as application-level
filtering logic, not real authentication (a login screen is out of scope).

## Full target folder structure

This is the *end state* after Phase 11. Each phase creates only the pieces relevant to it — refer
back to this file to know exactly where a new file belongs.

```
kpi-intelligence-engine/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app, CORS, router registration
│   │   ├── config.py                  # loads .env, exposes settings object
│   │   ├── db.py                      # sqlite connection helper
│   │   ├── api/                       # HTTP route handlers only — thin, call into core/
│   │   │   ├── health.py
│   │   │   ├── ingestion.py
│   │   │   ├── profiling.py
│   │   │   ├── semantic_contract.py
│   │   │   ├── data_quality.py
│   │   │   ├── canonical_model.py
│   │   │   ├── kpi.py
│   │   │   ├── anomaly.py
│   │   │   ├── drivers.py
│   │   │   ├── evidence.py
│   │   │   ├── persona.py
│   │   │   ├── insights.py
│   │   │   ├── recommendations.py
│   │   │   ├── feedback.py
│   │   │   └── telemetry.py
│   │   ├── core/                      # all real logic lives here, framework-agnostic, unit-testable
│   │   │   ├── ingestion/
│   │   │   ├── profiling/
│   │   │   ├── semantic/
│   │   │   ├── quality/
│   │   │   ├── canonical/
│   │   │   ├── kpi_engine/
│   │   │   ├── anomaly/
│   │   │   ├── drivers/
│   │   │   ├── evidence/
│   │   │   ├── confidence/
│   │   │   ├── persona/
│   │   │   ├── insight_templates/
│   │   │   ├── recommendation/
│   │   │   ├── llm/
│   │   │   ├── feedback/
│   │   │   └── telemetry/
│   │   └── models/                    # pydantic request/response schemas, shared across api/
│   ├── tests/                         # one test file per core/ module, mirrors the structure above
│   ├── data/
│   │   ├── uploads/                   # raw uploaded source files, one subfolder per source_id
│   │   └── app.db                     # sqlite database file
│   ├── requirements.txt
│   └── .env.example                   # documents required env vars, no real secrets
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx                    # top-level layout: navbar, sidebar nav, persona switcher, routes
│   │   ├── pages/
│   │   │   ├── UploadPage.tsx
│   │   │   ├── ProfilePage.tsx
│   │   │   ├── SemanticContractPage.tsx
│   │   │   ├── DataQualityPage.tsx
│   │   │   ├── CanonicalModelPage.tsx
│   │   │   ├── KpiDashboardPage.tsx
│   │   │   ├── AnomalyPage.tsx
│   │   │   ├── DriversPage.tsx
│   │   │   ├── ConfidencePage.tsx
│   │   │   ├── InsightsPage.tsx
│   │   │   ├── RecommendationsPage.tsx
│   │   │   ├── FeedbackPage.tsx
│   │   │   ├── TelemetryPage.tsx
│   │   │   └── DashboardPage.tsx      # final "decision workspace" home page, built in Phase 11
│   │   ├── components/                # shared/reusable UI pieces (cards, badges, charts, tables)
│   │   ├── api/                       # one fetch-wrapper file per backend api/ module
│   │   └── types/                     # shared TypeScript interfaces matching backend pydantic models
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.ts
└── docs/
    ├── KPI_Engine_Final_Architecture.md
    └── kilo-build-plan/                # this folder, for Kilo to re-read if needed
```

## Naming conventions (keep consistent so things stay searchable)

- Backend module folder names under `core/` and `api/` match the architecture layer they implement
  (e.g. `core/anomaly/` ↔ "Anomaly Detection" step).
- Every `core/<module>/` has a matching `tests/test_<module>.py`.
- Every backend `api/<name>.py` has a matching frontend `src/api/<name>.ts` fetch wrapper and,
  where relevant, a matching `src/pages/<Name>Page.tsx`.
- IDs are UUID strings everywhere (`source_id`, `dataset_id`, `kpi_id`, `finding_id`) — never rely on
  row position or filename as an identifier.
