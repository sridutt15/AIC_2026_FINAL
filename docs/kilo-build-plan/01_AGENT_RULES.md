# AGENT RULES — read and follow for the entire project, every session

You are building the **KPI Intelligence-to-Action Engine**, an enterprise business-analytics tool
that takes any company's data as input and produces KPIs, anomalies, drivers, evidence, confidence
scores, insights, and recommendations. The full target architecture is in
`KPI_Engine_Final_Architecture.md`. You will build it **one phase at a time**, from files named
`PHASE_00_...md` through `PHASE_11_...md`, in that exact order.

## Hard rules — never break these

1. **No git, ever.** Do not run `git init`, `git add`, `git commit`, or create any git-related files
   (`.gitignore`, `.git/`, etc.). This project is managed as plain files only. If you are tempted to
   version-control something, don't — just save the file.
2. **Work only on the phase you were given.** Each phase file is self-contained: objective,
   prerequisites, exact files to create, backend tasks, UI tasks, tests, and a "Definition of Done."
   Do not read ahead or start work described in a later phase file, even if it would be convenient.
3. **Every phase must end with a working UI update.** Backend-only progress is not acceptable. If a
   phase's spec includes a frontend page or component, it must be built, wired to the backend, and
   visually confirmable in the browser before the phase is considered done.
4. **Every phase must end with tests actually run, not just written.** Run `pytest` (backend) and
   report the pass/fail output. If anything fails, fix it before declaring the phase done — do not
   move to the "STOP" step with failing tests.
5. **Stop after every phase and ask permission.** When a phase's Definition of Done is met:
   - Summarize what you built (backend files, frontend files, what the UI now shows, test results).
   - Give the exact commands the user needs to run to see it (e.g. `uvicorn app.main:app --reload`,
     `npm run dev`).
   - Explicitly write: **"Phase N complete. Waiting for your approval before starting Phase N+1."**
   - Then stop. Do not write any more code until the user replies with approval.
6. **No LLM calls anywhere except Phase 10.** Every stage before Phase 10 (ingestion, profiling,
   semantic contract, data quality, canonical model, KPI discovery/validation/computation,
   materiality, anomaly detection, driver analysis, evidence, confidence/abstention, persona/access
   control, insight generation, recommendation packaging) must be deterministic code: rules,
   pandas/numpy/scipy/statsmodels, or explicit statistical tests. No calls to any language model.
   This is required so results are reproducible: same input data → same output every time, except
   for the Phase 10 recommendation text.
7. **Enterprise-generic, not hardcoded.** Never hardcode column names, company names, or KPI names
   into the core logic. Everything must be derived from whatever data and semantic contract the user
   provides at runtime, so the same code works for any company's dataset.
8. **Keep secrets out of code.** API keys (e.g. `ANTHROPIC_API_KEY`) go in a `.env` file, loaded via
   `python-dotenv`, and are never hardcoded or printed to logs.
9. **If a phase file references a file structure, follow `02_TECH_STACK_AND_FOLDER_STRUCTURE.md`
   exactly** — same paths, same names, so the project stays easy to navigate.

## What "Definition of Done" means for every phase (checklist to self-verify before stopping)

- [ ] All backend files listed in the phase exist and the backend starts without errors.
- [ ] All frontend files/pages listed in the phase exist and the frontend starts without errors.
- [ ] The new UI page/feature is reachable from the app's navigation, not just present in code.
- [ ] `pytest` was run and all tests pass (paste the output in your summary).
- [ ] The manual verification checklist in the phase file was performed by you (the agent) at least
      once end-to-end before handing off, and you describe what you observed.
- [ ] No git commands were used.
- [ ] No LLM calls were added (unless this is Phase 10).
- [ ] You have written the "Phase N complete, waiting for approval" stop message.

If you ever cannot satisfy one of these, say so explicitly instead of declaring the phase done.
