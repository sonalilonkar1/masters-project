# TraceAdvisor 295B Scope and Definition of Done

This document records what the team must finish in CMPE 295B, so that nobody needs the 295A Workbook to decide what is mandatory.

**How to use this document**

- **This document defines scope; the [project board](https://github.com/users/sonalilonkar1/projects/2) tracks live status and owners.** Lines marked **Snapshot (2026-10-14)** were true on that date; verify them on the board or on `main` before acting on them.
- Scope, rules, and the Definition of Done come from the team's planning document, *TraceAdvisor 295B Project Completion GitHub Issue Backlog* (CMPE 295B, October 2026), referred to below as **the backlog**. The backlog is not stored in this repository; ask the team for a copy. It has an original issue list and a later section titled *TraceAdvisor 295B Revised Development and Completion Issues*, referred to below as **the revised plan**.
- Quoted text is copied from the backlog. Statements that come from somewhere else name their source.
- Known disagreements between the original issue list and the revised plan are listed in [Section 7](#7-open-questions-and-known-conflicts). Confirm with the team before acting on a conflicting item.

---

## 1. Source-of-Truth Hierarchy

From the backlog:

1. Current main branch + latest 295B direction/design notes — authoritative for implementation
2. Submitted final-report Table of Contents — authoritative for final report structure
3. Submitted 295A Chapter 1 — preserved research framing; consistency edits only as needed
4. 295A Workbook / Workbook 2 — historical background only, not a final-project requirement list

---

## 2. Final Report Status

From the backlog (section 1, "What Changed in This Revision"): "Chapter 1 and the report Table of Contents are already submitted; the remaining report work is Chapters 2-9 plus final consistency, figures, and appendices." This work is backlog Issue 17.

Rules for final Google numbers, from backlog Issue 12:

- "A final comparison table/CSV/JSON is generated and is the only source for final Google report numbers."
- "If a true implementation bug is discovered, document the invalid run and restart the lock/test process transparently."

---

## 3. 295B Completion Scope

From the backlog, with the revised plan's changes noted:

- **Primary core track:** Google ClusterData2019 CPU and memory pre-execution recommendation for recurring workloads.
- **Canonical modeling/evaluation unit:** full-workload occurrence, not an individual execution row. Backlog Issue 01: "Use occurrence_key = recurrence_key + execution_start_time_us." Notebook 04 metadata records it as `occurrence_key = recurrence_key || execution_start_time_us`.
- **Core final policy comparison:** Request, Mean, P90, P95, P99, ML-only, and Hybrid.
- **ML sizing method:** regression is primary; classification remains supporting analysis unless it is explicitly wired into policy logic.
- **Final-test discipline:** all choices are locked from training/validation before one final untouched-test evaluation.
- **Cross-platform track:** canonical workload interface plus dataset-specific adapters. In the revised plan, the active external datasets are **Alibaba** and **Azure VM** ("Active work becomes New Issues 1 and 4 for Alibaba and Azure VM"), and "Splitwise and ModServe remain P2 or scope-pending" (see Section 7).
- **Dataset-specific ML (revised plan):** "Issues 06–08 are required. The correct scope is dataset-specific ML using shared pipeline conventions and shared evaluation code. Each selected dataset must run through its own compatible data, feature, target, model, and policy artifacts. The fitted Google model is not automatically reused for Alibaba or Azure VM."
- **Product track:** the original list names a recommendation output contract, prototype API/CLI, then interactive UI/dashboard over precomputed artifacts. The revised plan replaces old Issues 09–10 with New Issues 5 and 6, and old Issues 14–15 with New Issues 7, 8, and 9 (Section 5).
- **Hybrid starting rule (revised plan, New Issue 6):** "Use the existing Google Hybrid rule as a starting point: HybridCPU = max(MLPredictedCPU, P95CPU) and HybridMemory = max(MLPredictedMemory, P95Memory)." New Issue 6 also requires: "Define Conservative, Balanced, and Efficient objectives."
- **Academic track:** complete final report Chapters 2–9 from the submitted TOC, then final demo/presentation/release.

### Planning rules

From the revised plan, verbatim:

- Each parent issue is a workstream and may have multiple contributors.
- Use the task checklist inside a parent issue for small tasks; create a child issue only when the work can be independently owned and is large enough to track separately.
- P0 issues block downstream work. P1 issues are required after dependencies are ready. P2 issues are optional or scope-pending.
- Issues 01 and 02 are completed Google-subset foundation work and should be marked DONE, not repeated.
- The shared evaluator and metrics are common across Google, Alibaba, and Azure VM. New datasets must produce standardized inputs for the shared evaluator.
- Raw datasets and fitted models are dataset-specific. Do not merge raw datasets or reuse a fitted Google model without dataset-specific validation.

From the revised plan's "GitHub issue template" section, verbatim: "Do not assign a blocked issue. An issue becomes Ready only after all listed dependencies are complete or explicitly waived. Parent issues may have multiple contributors; use separate child issues only for independently owned work that is large enough to track."

### Explicitly not required to close the project (unless advisor feedback changes scope)

From the backlog, verbatim:

- Full production-system reimplementations or extra learned-model extensions for Splitwise/ModServe beyond the required adapter + reproducible validation tracks. Their inclusion is mandatory; deeper extensions are optional unless advisor feedback expands scope.
- GPU recommendation support. Current completion backlog is CPU + memory.
- OpenStack integration.
- Full Google ClusterData2019 processing if compute/storage constraints make it impractical; larger-scale validation can be a documented limitation unless explicitly required.
- A full refactor of history_profiler.py / feature_builder.py if the current pipeline is stable and tested. The 295B notes describe reusable profiling modules as "if time permits."
- Live scheduler integration, online inference, autoscaling deployment, authentication, cloud hosting, or production multi-user backend.
- Industry-specific/NVIDIA AI integration or an LLM assistant unless specifically requested by the advisor.

Note: the first bullet calls Splitwise/ModServe inclusion mandatory, while the revised plan makes them P2 or scope-pending. See Section 7.

---

## 4. Project-Level Definition of Done

From the backlog's original issue list, verbatim:

- [ ] Full-workload occurrence CPU/memory resources are correct and independently verified.
- [ ] Chronological train/validation/final-test artifacts are leakage-safe and use next-distinct-occurrence targets.
- [ ] Request, Mean, P90, P95, P99, ML, and Hybrid use the same target columns and shared evaluator.
- [ ] Baseline/min_runs, feature set, ML models/hyperparameters, Hybrid rules/thresholds, and fallback behavior are selected using training/validation only.
- [ ] One final test evaluation is produced after every decision is frozen; no post-test tuning occurs.
- [ ] Canonical adapter/interface path works for Google plus all required external validation tracks: Resource Central, Splitwise, ModServe, and Alibaba, with dataset-specific capability handling.
- [ ] Developer-facing output contract, API/CLI, and interactive dashboard work end to end from saved artifacts.
- [ ] Tests and a fresh-environment smoke run verify schemas, leakage rules, evaluator behavior, artifacts, and demo path.
- [ ] Final report Chapters 2-9, figures/tables, demo, presentation, README/runbook, and release manifest all agree with the same frozen artifacts.
- [ ] All required GitHub issues are closed or explicitly waived by advisor feedback; stale 295A issues are not confused with 295B completion work.

The revised plan does not restate this list. In this document's assessment (not stated in the backlog), items 6 and 7 conflict with the revised plan (external datasets and product track); see Section 7 before using them as closing criteria.

---

## 5. Revised Plan Issues and GitHub Issues

### Treatment of the original issues

From the revised plan's "Issue mapping from the original backlog":

| Original issue | Treatment | Scope |
|---|---|---|
| Issue 00 | Retained unchanged | Project tracking and source-of-truth cleanup. |
| Issues 01–02 | DONE | Google occurrence correction and N04 split, target, baseline, and validation rebuild. |
| Old Issue 03 | Replaced | Covered by New Issues 2 and 3; no separate Google adapter issue. |
| Old Issues 04, 04A, 04B, 05 | Replaced or pending | Active work becomes New Issues 1 and 4 for Alibaba and Azure VM. Splitwise and ModServe remain P2 or scope-pending. |
| Issues 06–08 | Retained with exact scope below | Dataset-specific ML preparation, model comparison, and model locking. |
| Old Issues 09–10 | Replaced | Covered by New Issues 5 and 6. |
| Issues 11–13 | Retained unchanged | Decision freeze, final test, explainability, and error analysis. |
| Old Issues 14–15 | Replaced | Covered by New Issues 7, 8, and 9. |
| Issues 16–18 | Retained unchanged | QA, reproducibility, report, presentation, release, and submission. |

### Current issues, priorities, and dependencies

Priority and "Depends on" are copied from the revised plan. The GitHub column lists only issues whose title or description names the item; the board has live status and owners.

| Item | Priority | Depends on (or role) | GitHub |
|---|---|---|---|
| Issue 00 — Reset project tracking to the current 295B source of truth | P0 | Planning and stale-issue cleanup. | #68 |
| New Issue 1 — Study Alibaba and Azure VM Dataset Semantics | P0 | None | #62 |
| New Issue 2 — Define Canonical Workload Interface and Schema | P0 | New Issue 1 and completed Google artifacts | #64 |
| New Issue 3 — Build Adapter Framework and Validation | P0 | New Issue 2 | #65 |
| New Issue 4 — Integrate Alibaba and Azure VM Datasets | P1 | New Issue 3 | #66 |
| New Issue 5 — Define Common ML and Baseline Recommendation Output Interface | P0 | New Issue 2 and current Google baseline/ML outputs | #67 |
| New Issue 6 — Define and Implement Objective Driven Hybrid Policy Engine | P0 | New Issue 5 and Issue 08 locked model and policy candidates | — |
| New Issue 7 — Prototype Recommendation Output and API | P1 | New Issues 5 and 6 | — |
| New Issue 8 — Build UI Simulation and Policy Controls | P1 | New Issues 5 and 6 | — |
| New Issue 9 — Integrate UI with API and Create End to End Demo | P1 | New Issues 7 and 8 | — |
| Issue 06 — Align ML Preparation with Canonical Dataset Targets and Features | P0 | Issues 01–02 DONE; New Issues 1–4 | #63 (Google only) |
| Issue 07 — Train and Compare Dataset Specific ML Models and Recommendation Candidates | P1 | Issue 06 | #63 (Google only; see Notebook 05/06 split below) |
| Issue 08 — Tune Validate and Lock Dataset Specific ML Models | P0 | Issue 07 | #63 (Google only; see Notebook 05/06 split below) |
| Issue 11 — Freeze all validation decisions and create the final decision manifest | P0 | Depends on Issue 08 and Issue 06 policy decisions; precedes final-test scoring. | — |
| Issue 12 — Run one-time untouched final-test evaluation | P0 | Depends on Issue 11; use the shared evaluator and locked artifacts. | — |
| Issue 13 — Create explainability, failure analysis, and report-ready results | P1 | Depends on locked models and final artifacts. | — |
| Issue 16 — Complete QA, reproducibility, README, and repository cleanup | P0 | Closes after implementation and integration work merges. | — |
| Issue 17 — Complete final report Chapters 2 to 9 | P0 | Can start early; final quantitative claims depend on frozen artifacts. | — |
| Issue 18 — Prepare final presentation, demo, release, and submission checklist | P0 | Depends on final report, demo, QA, and release artifacts. | — |

**Snapshot (2026-10-14):** items marked "—" had no GitHub issue, and no GitHub issue tracked Issues 06–08 for Alibaba or Azure VM. Check the board before creating one, to avoid duplicates.

Dependency flow, from the revised plan:

- New Issue 1 Dataset study → New Issue 2 Canonical schema → New Issue 3 Adapter framework → New Issue 4 Alibaba and Azure VM integration
- New Issue 2 → Issue 06 ML preparation → Issue 07 model and policy comparison → Issue 08 model lock
- New Issue 5 output contract → New Issue 6 objective-driven policy engine → New Issue 7 API → New Issue 9 UI integration
- New Issue 8 UI simulation can begin after the output contract and policy behavior are defined, using saved or mock artifacts.

The closed GitHub issues for the related Notebook 02–04 corrections are #53 (Notebook 2 resource aggregation), #54 (Notebook 3 historical profiles), and #55 (Notebook 4 targets, baselines, and evaluation). #56 is a closed issue with the same title as #55.

### Notebook 05 / Notebook 06 split for Google

A team decision shared in the team chat (not in the backlog) splits the Google ML and evaluation work as follows:

> Notebook 4 → corrected occurrence artifacts and baseline recommendations
> Notebook 5 (ML) → tune and select final ML models → refit locked models → generate final ML predictions → provide final ML/P95/Hybrid inputs for authoritative evaluation.
> Notebook 6 (final) → evaluate Request/Mean/P90/P95/P99 → receive ML predictions → construct Hybrid recommendations → compare all policies through shared evaluator

This differs from the backlog as follows:

- Issue 08 in the revised plan says "Keep hyperparameter tuning in Notebook 6" and has the acceptance criterion "Notebook 6 contains tuning, TimeSeriesSplit, GroupKFold, model selection, refit, locked artifact creation, and prediction generation." Under the team decision (and GitHub #63, which lists TimeSeriesSplit and GroupKFold under Notebook 05), these are in Notebook 05.
- Issue 07 in the revised plan includes "Generate Part A Hybrid predictions using the same formula for each dataset/resource: max(ML prediction, P95 baseline)." The revised plan does not say which notebook runs Issue 07; the original issue list labels it "Train/compare CPU and memory ML models (N05)". Under the team decision, Hybrid recommendations are constructed in Notebook 06, not Notebook 05.

---

## 6. Where the Code Lives

**Current Google pipeline** (`pipelines/google_subset/`):

| Notebook | Role |
|---|---|
| `00_dataQualityReview.ipynb` | Raw data quality review |
| `01_dataIngestion.ipynb` | Ingestion and canonical observations |
| `02_reconstructExecutions.ipynb` | Execution reconstruction |
| `03_buildProfilesAndMetrics.ipynb` | Occurrence-level point-in-time historical profiles |
| `04_splitAndBaselines.ipynb` | Chronological splits, next-occurrence targets, and baselines |
| `05_evaluateRecommendations.ipynb` | Notebook 05 (ML stage in the team's split above; despite the filename, it does not run the policy comparison). **Snapshot (2026-10-14):** an empty placeholder on `main`; the implementation is in PR #61 |

**Snapshot (2026-10-14):** no Notebook 06 file exists yet. Under the team decision, Hybrid construction and the comparison of all policies through the shared evaluator belong in Notebook 06.

Shared modules: `src/evaluation/` (shared evaluator and metrics, used by Notebook 04) and `src/features/` (chronological split utility used by Notebook 04, plus feature configuration and ML preparation helpers), with tests in `tests/`.

**Earlier 295A-era material:** `notebooks/subset/`, `notebooks/GoogleCluster2019/`, `notebooks/modserve/`, `notebooks/splitwise/`, `notebooks/resource-central/`, `notebooks/Experiments_HistoryBasedBaselines.ipynb`, `src/eval/evaluator_v0.py`, `src/baselines/`, and the results under `reports/eval/`. These are not part of the occurrence-level Google pipeline above. Backlog Issue 17 requires that the final report contain "No stale pre-refactor metric, execution-target definition, or outdated scope claim". The original Issues 04A and 04B (replaced or pending in the revised plan) also require that existing Splitwise and ModServe outputs be "reconciled with current code; stale 295A numbers are not reused without rerunning/validating them".

---

## 7. Open Questions and Known Conflicts

| Topic | What the backlog says | Status |
|---|---|---|
| Splitwise and ModServe | The original issue list calls them required (Scope, Definition of Done item 6, Issues 04A/04B, and the "not required" list). The revised plan says: "Splitwise and ModServe remain outside the active external-dataset implementation until the team or advisor confirms that they are mandatory. If confirmed, add them as dataset-specific adapters and full pipeline paths. Do not treat them as Google CPU/memory substitutes without semantic validation." | **Snapshot (2026-10-14):** no confirmation found in the backlog, the team meeting log (`docs/meetings/Harkey-Sp26-1-meeting log1.docx`), or the project board (this document's check). Per the revised plan, they stay outside active implementation until confirmed |
| Role of external datasets | The original list treats them as validation tracks (for example, Issue 05: "Alibaba results are presented as external validation, not used to retune the locked Google policy"). The revised plan requires full pipelines for Alibaba and Azure VM: New Issue 4, "Each selected dataset can proceed to downstream feature, baseline, ML, policy, API, and UI stages", and dataset-specific Issues 06–08 (Section 3). | Confirm with the team |
| CLI and product priorities | The original Scope, Definition of Done item 7, and Issue 14 include an API/CLI and an interactive dashboard (Issues 14 and 15 are P0). The revised New Issues 7–9 describe a read-only API, UI simulation, and UI/API integration, do not mention a CLI, and are P1. | Confirm with the team |
| Where Google tuning, model lock, and Hybrid happen | Issue 08 places tuning through prediction generation in Notebook 6; Issue 07 includes Hybrid predictions. | The team decision moves tuning through final ML predictions into Notebook 05 and keeps Hybrid in Notebook 06 (Section 5) |
| Open 295A-era issue #4 ("Issue 4 — [UI] Decide UI approach + wireframe") | Not mentioned in the backlog. Issue 00 requires triaging old open 295A issues. In this document's assessment (not stated in the backlog), its topic overlaps the revised plan's UI work (New Issues 8 and 9). | **Snapshot (2026-10-14):** triage decision pending (board status: Backlog) |
| Backlog section 9, "Final Closure Checklist" | Written with the original issue list. It refers to issues the revised plan replaces or makes pending: "Issue 10 Hybrid policy", "Issues 04, 04A, 04B, and 05 external validation", and "Issues 14-15 API/CLI/dashboard". | Read it together with the revised plan's issue mapping (Section 5) |

---

## 8. Sources

- *TraceAdvisor 295B Project Completion GitHub Issue Backlog* (CMPE 295B, October 2026), including *TraceAdvisor 295B Revised Development and Completion Issues* (not stored in this repository)
- [Project board](https://github.com/users/sonalilonkar1/projects/2) and GitHub issues of this repository, read on 2026-10-14
- Team decision on the Notebook 05/06 split, shared in the team chat
- Notebook 04 metadata (`occurrence_key` definition)
