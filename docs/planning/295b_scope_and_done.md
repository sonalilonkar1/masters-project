# TraceAdvisor 295B Scope and Definition of Done

This document records what the team must finish in CMPE 295B, so that nobody needs the 295A Workbook to decide what is mandatory.

**How to use this document**

- **Live task status is on the [project board](https://github.com/users/sonalilonkar1/projects/2)**, not here. This document does not track status.
- Scope and the Definition of Done come from the team's planning document, *TraceAdvisor 295B Project Completion GitHub Issue Backlog* (CMPE 295B, October 2026), referred to below as **the backlog**. The backlog has an original issue list and a later section titled *TraceAdvisor 295B Revised Development and Completion Issues*, referred to below as **the revised plan**.
- Where the original issue list and the revised plan disagree, the disagreement is listed in [Section 7](#7-open-questions-and-known-conflicts). Confirm with the team before acting on a conflicting item.

---

## 1. Source-of-Truth Hierarchy

From the backlog:

1. Current main branch + latest 295B direction/design notes — authoritative for implementation
2. Submitted final-report Table of Contents — authoritative for final report structure
3. Submitted 295A Chapter 1 — preserved research framing; consistency edits only as needed
4. 295A Workbook / Workbook 2 — historical background only, not a final-project requirement list

---

## 2. Final Report Status

From the backlog: the Table of Contents and Chapter 1 are already submitted; the remaining report work is Chapters 2–9 plus final consistency, figures, and appendices (backlog Issue 17). Final Google result numbers must come from the one-time final-test evaluation (backlog Issue 12).

---

## 3. 295B Completion Scope

From the backlog, with the revised plan's changes noted:

- **Primary core track:** Google ClusterData2019 CPU and memory pre-execution recommendation for recurring workloads.
- **Canonical modeling/evaluation unit:** full-workload occurrence, not an individual execution row. In the current Google pipeline, `occurrence_key = recurrence_key || execution_start_time_us` (Notebook 04 metadata).
- **Core final policy comparison:** Request, Mean, P90, P95, P99, ML-only, and Hybrid.
- **ML sizing method:** regression is primary; classification remains supporting analysis unless it is explicitly wired into policy logic.
- **Final-test discipline:** all choices are locked from training/validation before one final untouched-test evaluation.
- **Cross-platform track:** canonical workload interface plus dataset-specific adapters. The revised plan's active external datasets are **Alibaba** and **Azure VM**; Splitwise and ModServe are scope-pending (see Section 7).
- **Product track:** the original list names a recommendation output contract, prototype API/CLI, then interactive UI/dashboard over precomputed artifacts. The revised plan replaces these with a common output interface (New Issue 5), an objective-driven Hybrid policy engine (New Issue 6), a read-only API (New Issue 7), UI simulation and policy controls (New Issue 8), and UI/API integration with an end-to-end demo (New Issue 9).
- **Academic track:** complete final report Chapters 2–9 from the submitted TOC, then final demo/presentation/release.

Planning rules stated in the revised plan:

- The shared evaluator and metrics are common across Google, Alibaba, and Azure VM. New datasets must produce standardized inputs for the shared evaluator.
- Raw datasets and fitted models are dataset-specific. Do not merge raw datasets or reuse a fitted Google model without dataset-specific validation.

### Explicitly not required to close the project (unless advisor feedback changes scope)

From the backlog, verbatim:

- Full production-system reimplementations or extra learned-model extensions for Splitwise/ModServe beyond the required adapter + reproducible validation tracks. Their inclusion is mandatory; deeper extensions are optional unless advisor feedback expands scope.
- GPU recommendation support. Current completion backlog is CPU + memory.
- OpenStack integration.
- Full Google ClusterData2019 processing if compute/storage constraints make it impractical; larger-scale validation can be a documented limitation unless explicitly required.
- A full refactor of history_profiler.py / feature_builder.py if the current pipeline is stable and tested. The 295B notes describe reusable profiling modules as "if time permits."
- Live scheduler integration, online inference, autoscaling deployment, authentication, cloud hosting, or production multi-user backend.
- Industry-specific/NVIDIA AI integration or an LLM assistant unless specifically requested by the advisor.

Note: the first bullet calls Splitwise/ModServe inclusion mandatory, while the revised plan makes them scope-pending. See Section 7.

---

## 4. Project-Level Definition of Done

From the backlog, verbatim:

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

Note: the sixth item lists Splitwise and ModServe as required, which conflicts with the revised plan (see Section 7).

---

## 5. Backlog Items and GitHub Issues

This table lists only GitHub issues whose title or description names the backlog item. For current status and owner, see the [project board](https://github.com/users/sonalilonkar1/projects/2).

| Backlog item | GitHub issue |
|---|---|
| Issue 00 — Reset project tracking to the 295B source of truth | #68 |
| New Issue 1 — Study Alibaba and Azure VM dataset semantics | #62 |
| New Issue 2 — Define canonical workload interface and schema | #64 |
| New Issue 3 — Build adapter framework and validation | #65 |
| New Issue 4 — Integrate Alibaba and Azure VM datasets | #66 |
| New Issue 5 — Define common ML and baseline recommendation output interface | #67 |
| Issues 06 and 07, and the tuning/lock part of Issue 08, for Google (Notebook 05) | #63 |

**Issues 01–02** are marked DONE in the revised plan. The related closed GitHub issues for the Notebook 02–04 corrections are #53 (Notebook 2 resource aggregation), #54 (Notebook 3 historical profiles), and #55 (Notebook 4 targets, baselines, and evaluation). #56 is a closed issue with the same title as #55.

As of 2026-10-14, backlog items not listed above had no GitHub issue. Check the board before creating one, to avoid duplicates.

**Notebook 05 / Notebook 06 split (team decision shared in the team chat; not in the backlog):**

- Notebook 05: tune and select the final ML models, refit the locked models, generate final ML predictions, and provide the final ML/P95 inputs for authoritative evaluation.
- Notebook 06: evaluate Request/Mean/P90/P95/P99, receive the ML predictions, construct Hybrid recommendations, and compare all policies through the shared evaluator.

This differs from the backlog, which places tuning and model locking (Issue 08) in Notebook 06.

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
| `05_evaluateRecommendations.ipynb` | ML stage. As of 2026-10-14 this file is an empty placeholder on `main`; the implementation is in PR #61 |

Shared modules: `src/evaluation/` (shared evaluator and metrics, used by Notebook 04) and `src/features/` (chronological split utility used by Notebook 04, plus feature configuration and ML preparation helpers), with tests in `tests/`.

**Earlier 295A-era material:** `notebooks/subset/`, `notebooks/GoogleCluster2019/`, `notebooks/modserve/`, `notebooks/splitwise/`, `notebooks/resource-central/`, `src/eval/evaluator_v0.py`, `src/baselines/`, and the results under `reports/eval/`. These are not part of the occurrence-level Google pipeline above. The backlog requires that the final report contain no stale pre-refactor metric, execution-target definition, or outdated scope claim (Issue 17), and that existing Splitwise and ModServe outputs not be reused without rerunning and validating them (Issues 04A and 04B).

---

## 7. Open Questions and Known Conflicts

| Topic | What the backlog says | Status |
|---|---|---|
| Splitwise and ModServe | The original issue list (Scope, Definition of Done, Issues 04A/04B, and "not required" list) calls them required external validation tracks. The revised plan says they "remain outside the active external-dataset implementation until the team or advisor confirms that they are mandatory" (P2 or scope-pending). | Unresolved; confirm with the team or advisor |
| Where tuning and model locking happen | The backlog places Issue 08 in Notebook 06. | The team moved it into Notebook 05 (Section 5) |
| Open 295A-era issue #4 ("[UI] Decide UI approach + wireframe") | Not mentioned in the backlog. Its topic overlaps the revised plan's UI work (New Issues 8 and 9). | Triage decision pending |

---

## 8. Sources

- *TraceAdvisor 295B Project Completion GitHub Issue Backlog* (CMPE 295B, October 2026), including *TraceAdvisor 295B Revised Development and Completion Issues*
- [Project board](https://github.com/users/sonalilonkar1/projects/2) and GitHub issues of this repository, read on 2026-10-14
- Team decision on the Notebook 05/06 split, shared in the team chat
- Notebook 04 metadata (`occurrence_key` definition)
