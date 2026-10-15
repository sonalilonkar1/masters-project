# TraceAdvisor 295B Scope and Definition of Done

This is the single current reference for what the team must finish in CMPE 295B.
Nobody should need the 295A Workbook to decide what is mandatory.

- **Tracking:** [Project board](https://github.com/users/sonalilonkar1/projects/2) and GitHub issues
- **Detailed plan:** *TraceAdvisor 295B Project Completion GitHub Issue Backlog* (October 2026), including its *Revised Development and Completion Issues* section
- **Advisor:** Dan Harkey (295B; previously Dr. Gheorghi Guzun)

---

## 1. Source-of-Truth Hierarchy

1. **Current `main` branch + latest 295B direction/design notes** — authoritative for implementation.
2. **Submitted final-report Table of Contents** — authoritative for final report structure.
3. **Submitted 295A Chapter 1** — preserved research framing; consistency edits only as needed.
4. **295A Workbook / Workbook 2** — historical background only, not a requirement list.

When the backlog's original issue list and its revised section disagree, the **revised section** applies.

---

## 2. Final Report Status

| Part | Status |
|---|---|
| Table of Contents | Submitted |
| Chapter 1 — Project Overview | Submitted (consistency edits only) |
| Chapters 2–9 | Remaining (backlog Issue 17) |

Chapters 2–9 follow the submitted TOC. Final Google result numbers come only from the one-time final-test evaluation (backlog Issue 12).

---

## 3. 295B Completion Scope

- **Primary track:** Google ClusterData 2019 CPU and memory pre-execution recommendations for recurring workloads.
- **Modeling and evaluation unit:** the full-workload **occurrence** (`occurrence_key = recurrence_key || execution_start_time_us`), not an individual execution row.
- **Core policy comparison:** Request, Mean, P90, P95, P99, ML-only, and Hybrid, all scored by the shared evaluator (`src/evaluation/`) against the same next-occurrence targets.
- **ML sizing:** regression is primary; classification is supporting analysis only.
- **Final-test discipline:** every choice is locked from training/validation before one untouched final-test evaluation.
- **Cross-platform track:** canonical workload interface plus dataset-specific adapters. Active external datasets: **Alibaba** and **Azure VM (Resource Central)**. Each dataset keeps its native resource semantics, and fitted models are dataset-specific.
- **Product track:** recommendation output contract, objective-driven Hybrid policy engine, read-only API, then UI over precomputed artifacts.
- **Academic track:** final report Chapters 2–9, presentation, demo, and release.

### Scope-pending

- **Azure Splitwise and Azure ModServe** stay outside the active implementation until the team or advisor confirms they are mandatory. If confirmed, they get dataset-specific adapters and must not be treated as CPU/memory substitutes.

### Not required to close the project (unless advisor feedback changes scope)

- GPU recommendations (the backlog is CPU + memory).
- OpenStack integration.
- Full ClusterData 2019 processing if compute/storage makes it impractical (document as a limitation).
- Full production reimplementations of Splitwise/ModServe or extra learned models for them.
- Live scheduler integration, online inference, autoscaling, authentication, cloud hosting, or a multi-user backend.
- Industry-specific/NVIDIA integration or an LLM assistant.

---

## 4. Project-Level Definition of Done

- [ ] Full-workload occurrence CPU/memory resources are correct and independently verified.
- [ ] Chronological train/validation/final-test artifacts are leakage-safe and use next-distinct-occurrence targets.
- [ ] Request, Mean, P90, P95, P99, ML, and Hybrid use the same target columns and the shared evaluator.
- [ ] Baseline/`min_runs`, feature set, ML models/hyperparameters, Hybrid rules/thresholds, and fallback behavior are selected using training/validation only.
- [ ] One final test evaluation is produced after every decision is frozen; no post-test tuning occurs.
- [ ] The canonical adapter/interface path works for Google and each active external dataset, with dataset-specific capability handling.
- [ ] Developer-facing output contract, API, and UI work end to end from saved artifacts.
- [ ] Tests and a fresh-environment smoke run verify schemas, leakage rules, evaluator behavior, artifacts, and the demo path.
- [ ] Final report Chapters 2–9, figures/tables, demo, presentation, README/runbook, and release manifest agree with the same frozen artifacts.
- [ ] All required GitHub issues are closed or explicitly waived by advisor feedback; stale 295A issues are not confused with 295B work.

---

## 5. Backlog-to-GitHub Map

Status as recorded on the project board. Board columns: Backlog → Todo → In Progress → Review → Done.

| Backlog item | GitHub | Board status |
|---|---|---|
| Issue 00 — Reset tracking to the 295B source of truth | #68 | In Progress |
| Issue 01 — Correct full-workload occurrence aggregation (N02/N03) | #53, #54 | Done |
| Issue 02 — Rebuild N04 splits, targets, baselines | #55, #56 | Done |
| New Issue 1 — Study Alibaba and Azure VM dataset semantics | #62 | Review |
| New Issue 2 — Canonical workload interface and schema | #64 | In Progress |
| New Issue 3 — Adapter framework and validation | #65 | Todo |
| New Issue 4 — Integrate Alibaba and Azure VM datasets | #66 | Todo |
| New Issue 5 — Common ML and baseline recommendation output interface | #67 | Todo |
| Issues 06–08 (Google) — ML features, model comparison, tuning and lock (N05) | #63 (PR #61) | Review |
| N06 — Hybrid construction and final policy comparison | not yet created | — |
| New Issue 6 — Objective-driven Hybrid policy engine | not yet created | — |
| New Issues 7–9 — API, UI simulation, UI/API integration and demo | not yet created | — |
| Issues 11–13 — Decision freeze, final test, explainability | not yet created | — |
| Issues 16–18 — QA/README, final report, presentation/release | not yet created | — |

**Notebook split (team decision):** N05 tunes and locks the ML models and produces final ML/P95 inputs; N06 evaluates the baselines, builds Hybrid, and compares all policies through the shared evaluator.

### Legacy 295A issues

| Issue | Treatment |
|---|---|
| #4 — [UI] Decide UI approach + wireframe | Superseded by New Issue 8 (UI simulation and policy controls) and New Issue 9 (UI/API integration) |

---

## 6. Current Code vs Historical Material

**Current 295B pipeline (authoritative):**

- `pipelines/google_subset/` — notebooks 00–05 (N06 planned)
- `src/evaluation/` — shared evaluator and metrics
- `src/features/` — feature contract, ML preparation, chronological split utilities
- `tests/`

**Historical 295A material (background only; numbers are pre-refactor and not final results):**

- `notebooks/subset/`, `notebooks/GoogleCluster2019/`, `notebooks/modserve/`, `notebooks/splitwise/`, `notebooks/resource-central/`
- `src/eval/evaluator_v0.py`, `src/baselines/`
- `reports/eval/`
- `docs/baseline_experiments/`, `docs/evaluation/*_v0.md`
- The 295A Workbook / Workbook 2

---

## 7. Working Rules

- Check the project board before picking up work; an issue is **Ready** only when all its dependencies are done or explicitly waived.
- Do not assign or start a blocked issue.
- Each parent issue is a workstream and may have several contributors; create child issues only for independently owned work.
- P0 blocks downstream work, P1 is required after its dependencies, P2 is optional or scope-pending.
- Do not merge raw Google, Alibaba, and Azure rows into one training dataframe, and do not reuse a fitted Google model on another dataset without dataset-specific validation.
- All violation, utilization, waste, and shortfall numbers come from the shared evaluator only.
