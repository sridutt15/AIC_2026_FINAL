# START HERE — How to use this build plan with Kilo (GLM 5.3, VS Code)

This folder is a complete, phase-by-phase build plan for the **KPI Intelligence-to-Action Engine**
(the architecture from `KPI_Engine_Final_Architecture.md`). It is written to be fed to an
autonomous coding agent (Kilo, running GLM 5.3, in VS Code) so it can build the project on its own,
one phase at a time, stopping for your approval after each phase.

## What's in this folder

```
kilo-build-plan/
├── 00_START_HERE.md                          ← you are here
├── 01_AGENT_RULES.md                         ← global rules — feed this to Kilo FIRST, every session
├── 02_TECH_STACK_AND_FOLDER_STRUCTURE.md      ← the target repo layout, feed SECOND
└── phases/
    ├── PHASE_00_setup.md
    ├── PHASE_01_ingestion_profiling.md
    ├── PHASE_02_semantic_contract.md
    ├── PHASE_03_data_quality.md
    ├── PHASE_04_canonical_model.md
    ├── PHASE_05_kpi_discovery_computation.md
    ├── PHASE_06_materiality_anomaly.md
    ├── PHASE_07_driver_evidence.md
    ├── PHASE_08_confidence_persona.md
    ├── PHASE_09_insight_generator.md
    ├── PHASE_10_llm_recommendation.md
    └── PHASE_11_feedback_telemetry_final.md
```

Files are numbered so they sort correctly in the VS Code file explorer — you'll always be able to
find "what phase am I on" and "what's next" at a glance.

## Exactly what to do (step by step)

1. **Create an empty project folder** on your machine, e.g. `kpi-intelligence-engine/`. Open it in
   VS Code. Open the Kilo panel.
2. **Copy this whole `kilo-build-plan/` folder** into the project folder too (e.g. as
   `kpi-intelligence-engine/docs/kilo-build-plan/`) so Kilo can re-read any file if it loses context
   mid-session.
3. **Start a new Kilo task.** Paste the full contents of `01_AGENT_RULES.md` first, then the full
   contents of `02_TECH_STACK_AND_FOLDER_STRUCTURE.md`, then the full contents of
   `phases/PHASE_00_setup.md`. Tell Kilo: *"Follow these rules for the entire project. Execute only
   Phase 0 right now. Stop and wait for my approval when it's done."*
4. **Review what Kilo built** using the "Manual verification checklist" at the bottom of the phase
   file. Run the backend and frontend yourself, click around.
5. If it looks right, reply to Kilo with something like **"Approved, continue to Phase 1"** and paste
   the contents of `phases/PHASE_01_ingestion_profiling.md`. If something's off, tell Kilo exactly
   what to fix before continuing — don't move to the next phase with unresolved issues.
6. **Repeat** for every phase file in order, 0 → 11. Never paste two phase files into the same
   uncompleted task.
7. If Kilo ever seems to have drifted (skipped tests, touched future-phase files, started using git),
   re-paste `01_AGENT_RULES.md` to re-anchor it before continuing.

## Non-negotiables (also repeated inside every phase file, on purpose)

- **No git.** Never `git init`, never commit, never create a `.gitignore`. Plain folders and files only.
- **One phase at a time.** Kilo must stop and explicitly ask your permission before starting the next phase.
- **UI every phase.** Every phase must end with something new and visible in the browser, not just backend code.
- **Tests every phase.** Every phase must end with an automated test run (pytest) that passes, plus a manual checklist for you.
- **No LLM calls anywhere except Phase 10.** Every other phase is deterministic/statistical so results are reproducible.

Once you've read this, open `01_AGENT_RULES.md` next.
