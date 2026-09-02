<div align="center">

# RootLens AI

### KPI Intelligence-to-Action Engine

**From KPI movement to evidence-backed, confidence-aware business action.**

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=111111)
![TypeScript](https://img.shields.io/badge/TypeScript-Frontend-3178C6?logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-3ECF8E?logo=supabase&logoColor=white)
![JWT](https://img.shields.io/badge/Auth-JWT-000000?logo=jsonwebtokens&logoColor=white)
![Claude](https://img.shields.io/badge/LLM-Final%20Stage%20Only-6F42C1)

**Accenture Innovation Challenge 2026 · Round 2 · BusinessIntelligence.ai**
**Team CreativeChaos · IIT Patna**

</div>

---

## Overview

Enterprise dashboards are good at showing **what changed**. The harder questions come next:

- **Why did the KPI move?**
- **Which drivers actually explain the movement?**
- **What evidence supports that explanation?**
- **How confident should we be?**
- **What should this specific decision-maker do next?**

**RootLens AI** is a governed KPI Intelligence-to-Action Engine that turns heterogeneous enterprise
data into trustworthy, evidence-backed recommendations, with every user's data kept fully private to
their own account.

Its central design rule is simple:

> **Every KPI, trend, anomaly, driver and confidence score is produced by deterministic logic,
> statistics or traditional ML. The LLM never sees raw data; it receives only a pre-verified
> evidence package and phrases the final recommendation.**

```text
IDENTITY      → real accounts, per-user data isolation
TRUTH         → deterministic analytics
EVIDENCE      → traceable support and context
CONFIDENCE    → explain, caveat, or abstain
COMMUNICATION → one final LLM step
ACTION        → concise, bulleted recommendation
```

---

## Why RootLens AI

| Enterprise challenge | RootLens capability | Business outcome |
|---|---|---|
| Fragmented data and inconsistent KPI definitions | Governed ingestion, profiling, semantic contract and canonical model | Consistent KPI truth |
| Data can arrive as a single file or from multiple systems | Canonical model works identically for one source or a multi-source merge | No dead end for smaller datasets |
| Too many KPI alerts | Materiality + anomaly detection | Focus on movements that matter |
| Slow root-cause investigation | Driver decomposition and ranked contribution analysis | Faster diagnosis |
| Generic AI explanations | Evidence ledger + confidence scoring | Traceable, reviewable reasoning |
| Hallucination risk | Deterministic quantitative pipeline | LLM cannot create numerical truth |
| Weak or contradictory evidence | Confidence gate + abstention | System can refuse to guess |
| Multiple users, one deployment | Real authentication + per-user data isolation | No user ever sees another user's data |
| Unclear GenAI economics | Runtime telemetry | Visible latency, calls and cost |

---

## Core Design Principles

| Principle | What it means in practice |
|---|---|
| **LLM is never the source of truth** | Numbers come from rules, statistics and ML — never from model inference |
| **The LLM speaks last** | It receives a verified evidence package only after analytical validation |
| **Determinism = reproducibility** | Same input + same configuration → same analytical output |
| **Every insight is traceable** | Findings carry method, evidence, confidence and lineage |
| **Uncertainty is explicit** | Low-confidence cases can caveat or abstain instead of forcing an answer |
| **Isolation is enforced, not assumed** | Every table and every stored file is scoped to the authenticated user, checked on every request |

---

## System Architecture

```mermaid
flowchart LR
    ID["Identity &\nAccess"] --> A["Layer A\nIngestion &\nReconciliation"] --> B["Layer B\nKPI Discovery &\nComputation"]
    B --> C["Layer C\nAnomaly, Driver\n& Evidence"]
    C --> D["Layer D\nInsight\nGeneration"]
    D --> E["Layer E\nLLM Recommendation\nONLY LLM STEP"]
    E --> F["Layer F\nFeedback, Telemetry\n& Activity History"]
    F -. corrections & drift signals .-> A
```

| Layer | Purpose | Main backend modules |
|---|---|---|
| **Identity & Access** | Register/login, JWT sessions, per-user data and file isolation | `auth/` |
| **A — Ingestion & Reconciliation** | Unify one or more sources into a governed analytical model | `ingestion/`, `profiling/`, `semantic/`, `quality/`, `canonical/`, `storage/` |
| **B — KPI Discovery & Computation** | Discover, validate, compute and prioritize KPIs | `kpi_engine/` |
| **C — Anomaly, Driver & Evidence** | Detect what moved, explain why, attach evidence and score confidence | `anomaly/`, `drivers/`, `evidence/`, `confidence/` |
| **D — Insight Generation** | Deterministic, bulleted insight structure from verified findings | `insight_templates/`, `recommendation/` |
| **E — LLM Recommendation** | Convert verified evidence into a concise, bulleted recommendation | `llm/` |
| **F — Feedback, Telemetry & Activity History** | Capture corrections, observe runtime behavior, log what each user did | `feedback/`, `telemetry/`, `activity/` |

---

## End-to-End Run Test

The prototype is designed around one judge-friendly action: **Run Test**.

```text
Register / log in
              ↓
    Select data / KPI / scope
              ↓
           RUN TEST
              ↓
      Profile & reconcile data
              ↓
       Compute / validate KPI
              ↓
  Detect material movement / anomaly
              ↓
      Rank explanatory drivers
              ↓
       Attach traceable evidence
              ↓
       Score confidence level
          ↙             ↘
      ABSTAIN          CONTINUE
    (no LLM call)     (verified package)
                           ↓
                    Final LLM phrasing
                           ↓
                  Bulleted recommendation
                           ↓
                        Telemetry
```

A strong test run should make the reasoning inspectable rather than merely display a generated
paragraph.

### What the user should be able to inspect

- KPI value, trend and materiality
- anomaly / structural-change signal
- ranked explanatory drivers
- contribution or analytical method used
- supporting evidence and lineage
- confidence level and caveats
- bulleted recommendation with owner / next action / monitoring plan
- their own activity history
- runtime telemetry

---

## Analytical Pipeline

### 0. Identity & Access

Every user registers their own account. Passwords are bcrypt-hashed, sessions are JWT-based, and
every table and every uploaded file is scoped to the authenticated user — verified with automated
isolation tests, not just assumed by convention. There is no shared or global view of anyone's data.

### 1. Ingestion & Profiling

RootLens accepts heterogeneous enterprise inputs and profiles them before analysis. Uploaded files
are stored in a private, per-user folder in Supabase Storage.

Key responsibilities:

- schema and type inspection
- missing-value and duplicate checks
- categorical consistency checks
- source metadata capture
- data-quality issue logging
- dataset and source identifiers

Raw problems are **logged and governed**, not silently hidden.

### 2. Semantic Contract & Canonical Model

KPI definitions, formulas, thresholds, drivers, lineage and access rules belong in a governed
semantic layer instead of being scattered across UI or model prompts.

This gives RootLens a reproducible rulebook for:

- what each KPI means
- how it is calculated
- which dimensions and drivers are valid
- what constitutes a material movement

A canonical dataset can be built from **two or more sources merged together**, or from **a single
source used directly** — both paths go through the same downstream pipeline with no special-casing
required. Every canonical dataset is given a readable, auto-generated name (editable by the user)
instead of an opaque identifier.

### 3. KPI Intelligence

The KPI engine computes and validates KPI candidates before downstream analysis. No LLM is involved
in KPI computation.

### 4. Anomaly & Change Detection

The analytics layer uses deterministic statistical methods to detect meaningful changes rather than
treating every fluctuation as a business event.

Current stack support includes:

- statistical baselines
- robust anomaly statistics
- time-series analysis
- change-point detection with **Ruptures**
- business materiality thresholds

### 5. Driver Analysis

RootLens moves beyond "anomaly detected" and asks **what explains the movement?**

Driver analysis can use deterministic, explainable methods such as:

- contribution decomposition
- dimensional drill-down
- regression / association analysis
- statistical comparison across candidate factors

Driver language remains appropriately cautious: association is not presented as causal proof unless
the analytical design supports that claim.

### 6. Evidence & Confidence

Each insight is paired with supporting evidence and a confidence decision.

A confidence score can combine factors such as:

- statistical strength
- data completeness / quality
- agreement across analytical methods
- supporting vs. contradictory evidence
- evidence freshness and lineage

```text
HIGH confidence   → explain and recommend
MEDIUM confidence → explain with caveats
LOW confidence    → abstain / request review
```

**Low-confidence path = zero LLM calls.**

### 7. Insight & Recommendation

Insights and recommendations are both rendered as short, scannable **bullet points** — what happened,
why, the recommended action, expected impact, and confidence — rather than dense paragraphs. The
recommendation stage is the single place in the entire system where an LLM is called, and it only
ever receives the pre-verified structured evidence package, never raw data.

### 8. Feedback, Telemetry & Activity History

The system captures user feedback, runtime observability, and a private log of each user's own
actions, so recommendations are not treated as an unreviewed black box.

Telemetry can include:

- stage-level latency
- number of LLM calls
- token usage
- estimated model cost
- cache hit rate
- feedback / correction events

Activity history includes: uploads, KPI discovery runs, driver analyses, insights generated,
recommendations generated, and feedback submitted — visible only to the user who performed them.

---

## LLM vs. Non-LLM Ledger

| Stage | Primary method | LLM used? |
|---|---|---:|
| Identity & access control | JWT / bcrypt | No |
| Ingestion / profiling | Python rules + validation | No |
| Semantic contract | Deterministic configuration | No |
| KPI computation | Rules / statistics | No |
| Anomaly detection | Statistical / change-point methods | No |
| Driver analysis | Contribution / statistical analysis | No |
| Evidence assembly | Deterministic evidence pipeline | No |
| Confidence scoring | Weighted deterministic logic | No |
| Abstention | Rule-based confidence gate | No |
| Deterministic insight structure | Templates | No |
| Activity logging | Deterministic event capture | No |
| **Recommendation phrasing** | **LLM over verified evidence package** | **Yes** |

> **The LLM communicates the analytical truth; it does not create it.**

---

## Tech Stack

### Backend

| Area | Technology |
|---|---|
| Runtime | **Python 3.11** |
| API | **FastAPI + Uvicorn** |
| Data / Analytics | **Pandas, NumPy, SciPy, Statsmodels** |
| Change-point detection | **Ruptures** |
| Validation / Schemas | **Pydantic v2** |
| Database | **PostgreSQL (Supabase), via SQLAlchemy** |
| File storage | **Supabase Storage** — private, per-user folders |
| Authentication | **JWT (python-jose) + bcrypt (passlib)** |
| Upload handling | **python-multipart** |
| Environment configuration | **python-dotenv** |
| Testing | **pytest + httpx** |

### Frontend

| Area | Technology |
|---|---|
| UI | **React 18** |
| Build tool | **Vite** |
| Language | **TypeScript** |
| Styling | **Tailwind CSS** |
| Charts | **Recharts** |
| API client | **Native `fetch`, JWT-authenticated wrapper** |

### LLM

- **Google Gemini API** via the official `google-genai` Python SDK
- API key loaded from `.env` as `GEMINI_API_KEY`
- Used only in the final recommendation stage
- The model receives only the pre-verified structured evidence package, never raw enterprise data

### Deployment target

- **Backend:** Render
- **Frontend:** Vercel
- **Database & Storage:** Supabase (managed Postgres + object storage)

Currently developed and verified running locally against a live Supabase project; deployment to
Render/Vercel is a configuration-only step (environment variables), not a code change.

### Deliberately Out of Scope for the Prototype

- Docker
- Enterprise SSO / OAuth (Okta, Azure AD, etc.)
- Horizontal scaling / load balancing

Authentication in this prototype is a genuine, working JWT-based system with per-user data
isolation — not a stub — but it is not yet integrated with an enterprise identity provider.

---

## Repository Structure

```text
kpi-intelligence-engine/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI app / CORS / routers / global error handling
│   │   ├── config.py                   # environment configuration
│   │   ├── db.py                       # SQLAlchemy engine & session
│   │   ├── models/
│   │   │   └── tables.py               # SQLAlchemy models (all tables, incl. users, activity_log)
│   │   ├── api/                        # thin HTTP route handlers
│   │   │   ├── health.py
│   │   │   ├── auth.py
│   │   │   ├── ingestion.py
│   │   │   ├── profiling.py
│   │   │   ├── semantic_contract.py
│   │   │   ├── data_quality.py
│   │   │   ├── canonical_model.py
│   │   │   ├── kpi.py
│   │   │   ├── anomaly.py
│   │   │   ├── drivers.py
│   │   │   ├── evidence.py
│   │   │   ├── insights.py
│   │   │   ├── recommendations.py
│   │   │   ├── feedback.py
│   │   │   ├── history.py
│   │   │   └── telemetry.py
│   │   ├── core/                       # framework-agnostic business logic
│   │   │   ├── auth/
│   │   │   ├── ingestion/
│   │   │   ├── profiling/
│   │   │   ├── semantic/
│   │   │   ├── quality/
│   │   │   ├── canonical/
│   │   │   ├── storage/
│   │   │   ├── kpi_engine/
│   │   │   ├── anomaly/
│   │   │   ├── drivers/
│   │   │   ├── evidence/
│   │   │   ├── confidence/
│   │   │   ├── insight_templates/
│   │   │   ├── recommendation/
│   │   │   ├── llm/
│   │   │   ├── feedback/
│   │   │   ├── activity/
│   │   │   ├── telemetry/
│   │   │   └── errors.py               # standardized error shape                      
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── context/
│   │   │   └── AuthContext.tsx
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── RegisterPage.tsx
│   │   │   ├── UploadPage.tsx          # default landing page
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
│   │   │   ├── HistoryPage.tsx
│   │   │   ├── TelemetryPage.tsx
│   │   │   └── DashboardPage.tsx
│   │   ├── components/
│   │   ├── api/                        # authenticated fetch wrappers, one per backend domain
│   │   └── types/
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.ts
└── docs/
    └── KPI_Engine_Final_Architecture.md
```

### Naming Conventions

- `core/<module>/` contains framework-independent logic.
- `api/<name>.py` stays thin and delegates to `core/`.
- Every protected route depends on `get_current_user`; every user-owned table carries a `user_id`.
- Each core module should have a matching backend test module.
- Frontend API wrappers mirror backend API domains and route through the authenticated client.
- Shared frontend types should match backend Pydantic response contracts.
- IDs use UUID strings rather than row positions or filenames.

---

## Getting Started

### Prerequisites

- Python **3.11**
- Node.js + npm
- A Supabase project (PostgreSQL database + a private Storage bucket)
- An Anthropic API key for the final LLM stage

### 1. Clone the repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd kpi-intelligence-engine
```

### 2. Start the backend

```bash
cd backend
python -m venv .venv
```

Activate the environment:

**Windows**

```bash
.venv\Scripts\activate
```

**macOS / Linux**

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create `backend/.env` from `.env.example` and fill in:

```env
DATABASE_URL=your_supabase_pooler_connection_string
SUPABASE_URL=your_supabase_project_url
SUPABASE_SERVICE_KEY=your_supabase_service_role_key
SUPABASE_STORAGE_BUCKET=uploads
SECRET_KEY=your_generated_jwt_secret
ANTHROPIC_API_KEY=your_key_here
```

Run the API:

```bash
uvicorn app.main:app --reload
```

### 3. Start the frontend

Open a second terminal:

```bash
cd frontend
npm install
```

Create `frontend/.env` from `.env.example` with `VITE_API_BASE_URL=http://localhost:8000`.

```bash
npm run dev
```

Open the local Vite URL displayed in the terminal, **register a new account**, and you'll land on
the Upload page to begin.

---

## Security & Governance

RootLens keeps governance visible rather than implicit.

### Identity & access

- Real user accounts: bcrypt-hashed passwords, JWT-based sessions
- Every table and every stored file is scoped to the authenticated user, enforced on every request
  — verified by automated cross-user isolation tests, not left to convention
- Uploaded files live in private, per-user Supabase Storage folders

### Analytical governance

- deterministic KPI definitions
- explicit confidence and abstention
- method / evidence / lineage visibility
- no raw-data reasoning by the final LLM
- model usage telemetry

### Important boundary

Authentication here is a real, working system, not a demonstration stub — but it has not been
extended to enterprise identity providers (SSO/OAuth), rate limiting, or advanced session policies.
A production deployment would add those on top of the isolation model already in place.

---

## Alignment with AIC Round 2 — BusinessIntelligence.ai

| Round 2 expectation | RootLens implementation |
|---|---|
| Detect and prioritize material KPI movements | KPI materiality + anomaly engine |
| Reconcile heterogeneous enterprise data | Ingestion, profiling, data quality and canonical model — single-source or multi-source |
| Identify and rank explanatory drivers | Deterministic driver analysis |
| Produce clear, decision-ready narratives | Bulleted insight and recommendation output, final LLM phrasing |
| Communicate uncertainty and abstain | Confidence engine + explicit abstention path |
| Recommend practical business actions | Verified recommendation evidence package |
| Learn from analyst / user feedback | Feedback module and correction loop |
| Protect user data and respect cost/latency constraints | Per-user authentication and isolation + telemetry + one final LLM stage |
| Show evidence freshness, method, contribution, confidence and lineage | Evidence / confidence ledger |
| Clearly separate LLM and non-LLM processing | Explicit processing ledger above |
| Show runtime telemetry and user activity | Telemetry module + activity history |

---

## Demo Strategy

The strongest demo is one continuous investigation rather than a feature tour:

```text
Register / log in
   ↓
KPI movement
   ↓
materiality / anomaly
   ↓
ranked drivers
   ↓
evidence
   ↓
confidence
   ↓
bulleted recommendation
   ↓
telemetry & activity history
```

Recommended recording sequence:

1. Register two separate accounts and briefly show that each only ever sees its own uploaded data —
   proves isolation before anything else.
2. Run one **high-confidence, multi-factor** case in one account.
3. Inspect ranked drivers and evidence.
4. Show that the LLM only appears after verification, via the LLM ledger.
5. Run one **low-confidence** case and show abstention.
6. Finish on telemetry and that account's activity history.

---

## Limitations

RootLens AI is a competition prototype, not a finished production deployment.

Current limitations include:

- driver association does not automatically prove causation
- confidence depends on available data and evidence quality
- sparse history can reduce analytical certainty
- authentication is self-hosted JWT, not integrated with an enterprise SSO/OAuth provider
- currently verified running locally against a live Supabase project; Render/Vercel deployment is a
  planned next step, not yet live
- production deployment would require stronger rate limiting, session policy, and infrastructure
  observability beyond what a prototype needs

The system is intentionally designed to **surface uncertainty and constraints instead of hiding
them** — that applies to its own maturity as a project, too.

---

## Project Links

> Replace these before final submission.

- **Demo Video:** `<https://drive.google.com/file/d/1VChmUIpTrfZFgR-VB6StVOQ92OmF6E5h/view?usp=sharing>`
- **Repository:** `<https://github.com/prajyoth2006/AIC_2026>`

---

## Team

**Team CreativeChaos — IIT Patna**

- Dikshant Khobragade — Team Lead
- M. Prajyoth
- R. SriDutt

Built for **Accenture Innovation Challenge 2026 — Round 2, BusinessIntelligence.ai**.

---

<div align="center">

### Identity → Detect → Diagnose → Verify → Confidence → Act

**Every number is computed. Every insight is evidenced. Every user's data is their own. The LLM
speaks last.**

</div>