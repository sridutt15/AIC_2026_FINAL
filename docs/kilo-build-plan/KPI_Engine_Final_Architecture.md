# KPI Intelligence-to-Action Engine — Final Architecture (Round 2)

## Design principles

1. **LLM is never the source of quantitative truth.** Every number, trend, anomaly, driver, and confidence score is produced by deterministic logic, statistics, or traditional ML — never inferred by a language model.
2. **The LLM speaks last.** It receives a pre-verified evidence package and turns it into persona-appropriate language and recommendations. It cannot invent facts because it never sees raw data — only the structured evidence package.
3. **Determinism = reproducibility.** Same input data → same KPIs, same anomalies, same drivers, same confidence scores. Only the LLM's prose can vary; the facts underneath cannot.
4. **Every insight carries a ledger entry** stating which stage produced it, which method was used (rule / SQL / statistical test / ML model / causal method / LLM), and why that method was chosen. This directly satisfies the brief's requirement to "explicitly demonstrate when you use deterministic logic, SQL, business rules, statistics, traditional ML, causal inference, retrieval, or LLMs — and why."

## Layer map

| Layer | Steps | Purpose |
|---|---|---|
| A — Ingestion & Reconciliation | 1–5 | Get heterogeneous enterprise data into one governed, analyzable model |
| B — KPI Discovery & Computation | 6–9 | Find, validate, compute, and prioritize KPIs |
| C — Anomaly, Driver & Evidence | 10–13 | Detect what moved, why, and how confident we are |
| D — Personalization & Governance | 14–16 | Apply security/persona rules, generate deterministic insight text |
| E — LLM Recommendation | 17 | The *only* LLM step — turn verified evidence into action language |
| F — Feedback, Telemetry & UI | 18–20 | Learn, monitor cost/latency, and present |

---

## Layer A — Ingestion & Reconciliation

**1. Multi-Source Ingestion**
- Connectors for CSV/XLSX/JSON/Parquet, DB (SQL), and API sources.
- Each source tagged with **grain** (row-level, daily, weekly, regional, etc.) and **refresh cadence** (real-time, nightly batch, weekly).
- Satisfies the "3–5 connected KPIs across 2–3 sources with different grains/cadences" minimum expectation — design ingestion to explicitly log source, grain, and freshness timestamp on every record.

**2. Schema Profiler**
- Deterministic profiling: column types, cardinality, null ratio, uniqueness, distributions, detection of temporal/categorical/numerical/identifier columns.
- Method: rule-based + descriptive statistics. No LLM.

**3. Semantic Discovery + KPI Semantic Contract**
- Infers business roles of columns (measure, dimension, time, identifier) via deterministic rules + statistical signatures (e.g., monotonic increasing + unique = surrogate key).
- Outputs a **lightweight semantic contract**: KPI definitions, calculation formulas, business hierarchies (product → category, region → country), calendar alignment rules, thresholds for materiality, lineage pointers, and access-restriction tags. This *is* the artifact the brief asks for under "governed KPI semantics."

**4. Data Quality Engine**
- Checks: missing values, duplicates, invalid values, type violations, impossible ranges (e.g., negative revenue), statistical outliers (IQR/MAD-based).
- Produces a per-source **data quality score** that later feeds the confidence engine.

**5. Canonical Data Model (Reconciliation Layer)**
- Converts arbitrary heterogeneous input into a shared analytical model (conformed dimensions, aligned calendars, common grain via aggregation/interpolation rules).
- Explicitly resolves cadence mismatches (e.g., daily sales vs. weekly marketing spend) using documented, deterministic reconciliation rules (last-observation-carried-forward, pro-rata allocation, etc.) — each rule logged so evidence stays traceable.

---

## Layer B — KPI Discovery & Computation

**6. KPI Discovery Engine**
- Deterministic candidate generation: ratios, sums, rates, and rate-of-change over numeric measures against relevant dimensions (rule-based combinatorics, not ML guessing).
- Cross-checked against the semantic contract so discovered KPIs respect business definitions instead of being arbitrary.

**7. KPI Validation**
- Statistical validity (sufficient sample size, non-degenerate variance), mathematical validity (denominator ≠ 0, unit consistency), and data-sufficiency checks.
- **Sparse-history / new-KPI handling**: if history < minimum window, the KPI is flagged `low-data` and routed to a Bayesian/shrinkage estimator or held out until abstention logic (step 13) decides whether to report it with wide confidence bounds or suppress it. This satisfies the "one sparse-history or newly launched KPI scenario" requirement.

**8. KPI Computation**
- Computes value, trend (rolling averages, YoY/WoW), baseline, benchmark, and confidence interval (bootstrap or analytic CI depending on sample size).

**9. Materiality & Prioritization Engine**
- Ranks KPI movements by combining **statistical significance** (z-score/CI vs. baseline) with **business impact** (weighted by revenue/margin exposure from the semantic contract). This directly implements brief objective 1: "detects and prioritises material KPI movements... based on both statistical significance and business impact."

---

## Layer C — Anomaly, Driver & Evidence

**10. Anomaly Detection**
- Control charts / CUSUM for gradual drift, change-point detection (e.g., PELT) for structural breaks, robust z-score for point outliers. Method chosen per KPI's data characteristics and logged.

**11. Driver / Contribution Analysis**
- Decomposes movement across interacting factors — price, volume, mix, marketing spend, seasonality, competitor signals, supply — using contribution/waterfall decomposition for additive metrics and causal inference (e.g., differences-in-differences, or a lightweight structural model) where confounding is likely.
- **This is where your Limiting / Challenging / Comparison agent roles slot in cleanly** if you want an agentic variant: "Limiting" = constrains the hypothesis space to plausible drivers given the semantic contract; "Challenging" = stress-tests each candidate driver against counter-evidence; "Comparison/Competition" = ranks competing driver hypotheses. All of this can run as pure statistical logic, or as LLM-orchestrated agents reasoning strictly over the numeric outputs from steps 8–10 (never over raw data) — your call on how strict you want the "no LLM until the end" rule to be.

**12. Evidence Engine**
- Attaches to every insight: the numeric evidence, the statistical test used, source freshness timestamp, and lineage (which raw records/rules produced it). This is the artifact that satisfies "evidence showing source freshness, analytical method, contribution, confidence and lineage."

**13. Confidence & Abstention Engine**
- Combines evidence quality, statistical significance, sample size, effect size, and cross-source agreement into a single confidence score.
- If confidence falls below threshold, or evidence from two sources contradicts, the engine **abstains**: it returns "insufficient/contradictory evidence" plus what additional data would resolve it, instead of forcing a narrative. This is your required "one low-confidence scenario in which the engine requests clarification or abstains."

---

## Layer D — Personalization, Governance & Insight

**14. Persona & Access Control Layer**
- Role-based entitlements at row, column, and domain level (e.g., a regional manager sees only their region; a finance persona sees margin data a marketing persona doesn't).
- Defines at least **two personas** (e.g., "Category Manager" — wants driver-level tactical detail; "CFO" — wants headline movement + financial impact + top action) with different insight depth and channel (dashboard vs. daily digest). This is your required role-based security/entitlement scenario plus the 2-persona minimum.

**15. Insight Generator**
- **Deterministic templates, no LLM.** Fills structured sentence templates from the evidence package (KPI, direction, magnitude, driver, confidence, comparison to benchmark). Guarantees reproducibility: same input → same insight text every run.

**16. Recommendation Evidence Package**
- Structures everything the LLM will need, and nothing more:
  `driver → controllable lever → candidate action → expected impact → owner → confidence → monitoring plan`
- This package is the *only* thing that crosses into Layer E — the LLM never touches raw data.

---

## Layer E — LLM Recommendation (the only LLM step)

**17. LLM Recommendation Layer**
- Input: the verified evidence package from step 16 (facts only).
- Output: natural-language recommendation, phrased per persona, with the action structure preserved.
- Explicit **model choice / cost controls**: pick smallest capable model for templated phrasing, cache repeated evidence-package shapes, log tokens and cost per insight. This satisfies "LLM economics" and the "clear breakdown of LLM vs. non-LLM processing" minimum expectation — you can literally show a ledger like:

| Stage | Method | LLM used? |
|---|---|---|
| KPI computation | Statistics | No |
| Anomaly detection | Change-point detection | No |
| Driver analysis | Contribution decomposition | No |
| Confidence scoring | Weighted composite score | No |
| Insight text | Deterministic template | No |
| Recommendation phrasing | Claude/GPT on evidence package | **Yes** |

---

## Layer F — Feedback, Telemetry & UI

**18. Feedback & Learning Loop**
- Analysts/business users can confirm, correct, or reject an insight or recommendation. Corrections feed back into: driver-weighting priors, materiality thresholds, and confidence calibration (not into the LLM prompt directly — keeps the system auditable).
- Monitors model/data drift (e.g., KPI distribution shift over time) and flags when semantic contract or thresholds need review.

**19. Telemetry & Observability**
- Tracks latency per stage, number of LLM calls, token usage, and estimated cost per insight — the "runtime telemetry" minimum expectation. Also tracks cache hit rate for the LLM layer.

**20. Final UI / Decision Workspace**
- Dataset health → Discovered KPIs → Trends → Anomalies → Drivers → Evidence → Insights → Recommendations, filtered by the logged-in persona's entitlements. Optional conversational layer on top, but note-worthy: any conversational Q&A would be a second, clearly-labeled LLM touchpoint (retrieval-augmented, still not a source of new facts).

---

## Coverage checklist vs. official Round 2 minimum expectations

| Requirement | Where it's handled |
|---|---|
| 3–5 KPIs, 2–3 sources, different grains/cadences | Steps 1, 5 |
| Lightweight KPI/semantic contract | Step 3 |
| ≥2 personas, different narratives/actions | Step 14 |
| Multi-factor KPI movement | Step 11 |
| Low-confidence/abstention scenario | Step 13 |
| Sparse-history/new-KPI scenario | Step 7 |
| Role-based security/entitlement scenario | Step 14 |
| Evidence: freshness, method, contribution, confidence, lineage | Step 12 |
| LLM vs non-LLM breakdown | Step 17 ledger |
| Runtime telemetry (latency, calls, tokens, cost) | Step 19 |

## Enterprise-scale notes
- Every reconciliation, aggregation, and materiality rule in Layers A–B should be config-driven (not hardcoded) so the same pipeline runs against any company's schema — this is what makes it work "for any type of enterprise-level company data."
- Platform-agnostic: the pipeline can sit natively on Databricks/Snowflake/Fabric for steps 1–13, with steps 14–20 as a custom app layer — or be fully custom-built. Explicitly label each capability in your deck as native / configured / custom-built / externally integrated, since the brief asks you to distinguish these.
