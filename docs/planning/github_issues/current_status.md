# Current Status of Tasks and Issues

**Snapshot:** 2026-11-16, checked against `main` at `ea6aa08` (PR #124 merged), the open GitHub issues and pull requests, and the task files in this folder. GitHub is the live record; check it before acting on any row here.

---

## 1. Completed

| Task | Issue | Evidence on `main` | Note |
|---|---|---|---|
| Tasks 1–5, schema 0.2.0 and Alibaba 2018 corrections | #66, #77, #79, #80, #81, #82, #85 | All closed; PRs #86–#96 merged | Done |
| Task 6: Alibaba GPU 2020 baselines and `min_runs` | **#87 (still open)** | PR #97 merged; PR #124 added `dataset_id` and `schema_version` metadata | Work done; close the issue |
| Task 7: ML, Hybrid and final test | **#89 (still open)** | PRs #98, #99, #102, #103 and the provenance follow-up #124 merged | Work done; close the issue after Task 8 merges |
| Task 13: Google subset thin adapter | #118 | PR #122 merged | Closed |
| Report: Abstract and Chapters 1–9, LaTeX and Overleaf | #71, #100, #107, #108 | PRs #101–#112 merged | Closed |

## 2. In Progress or Remaining

| Task | Issue | Priority | Status | What is left |
|---|---|---|---|---|
| Task 8: Alibaba GPU 2020 final verification | #113 | P1 | **PR #121 open, not merged** (34 of 34 checks pass; final run ID `7dd3942e-c2c0-4816-9466-efd32e486cc2`) | Review and merge PR #121; close #113, #87 and #89 |
| Task 12: final cross-dataset reporting | #117 | P1 | **PR 1 merged (#123)**; outputs in `reports/results/cross_dataset_pr1/` are provisional | PR 2: verified status, final manifest, limitations, conclusions, README and reproducibility (table 3.2) |
| Task 15: developer API and risk-based frontend | #120 | P1 | **Not started**; no API or frontend code on `main` | Export step, read-only API, web frontend, tests, report Figures 8.1 and 8.2 (table 3.3) |
| Task 10: Google subset corrections and rerun | #115 | P3 | **Not started** | Targets after split assignment, reselection, rerun of Notebooks 04–06, or a recorded decision to keep the current results with limitations (table 3.5) |
| Task 14: Google evaluation follow-ups | #119 | P3 | **Not started** | Cross-split targets (through Task 10), confidence intervals, feature importance (table 3.4) |
| Task 9: Alibaba 2018 adapter demonstration | #114 | P2 | Adapter updated for 0.2.0 (PR #92); **no outcome recorded** | Framework run, validated output, one recorded outcome (table 3.6) |
| Task 11: Azure VM dataset integration | #116 | P4 | Stage 1 study in `docs/data/azure_vm_traceadvisor_feasibility.md` (2026-10-29); old `src/adapters/azure_vm.py` (2026-10-14) | Record the go or stop decision; Stage 2 only on go (table 3.7) |
| Task 3 follow-up: peak memory of the Alibaba GPU 2020 build | **No GitHub issue** | P2 | **Not started**; adapter unchanged since 2026-10-25 | File the issue from `task3_followup_memory.md`; optional (table 3.8) |

## 3. Stale Items to Close

| Item | Reason |
|---|---|
| #75 N06: Google Hybrid and final comparison (P0) | Notebook PR #88 merged and the Google results are in Chapter 7; a corrected rerun belongs to Task 10 |
| #67 Issue 5: common recommendation output interface (P0) | Opened before the 295B scope reset; close, or fold the output format into Task 15 Part A |
| `pr70_schema_followup_review.md` | Review notes for #80, which is closed; the file can be removed |

---

## 4. Remaining Work by Task

### 4.1 Task 8: Alibaba GPU 2020 Final Verification (#113, PR #121)

| # | Item | Status | Note |
|---|---|---|---|
| 1 | Checksums of the Task 3, 4, 6 and 7 artifacts | Done in PR #121 | |
| 2 | Contract checks (dataset ID, schema 0.2.0, seven policies, memory first, separate denominators, no GPU or any-resource metric) | Done in PR #121 | |
| 3 | Lock predates the final test; one test-target read; one evaluator call | Done in PR #121 | Depends on the counters from PR #124 |
| 4 | Review PR #121 | **Remaining** | |
| 5 | Merge PR #121 and close #113, #87 and #89 | **Remaining** | Unblocks Task 12 PR 2 for Alibaba |

### 4.2 Task 12 PR 2: Final Cross-Dataset Reporting (#117)

| # | Item (task file section) | Status | Note |
|---|---|---|---|
| 1 | Reporting script, configuration, input-integrity and provenance checks | Done in PR 1 | `scripts/build_final_cross_dataset_report.py` |
| 2 | Per-dataset results tables and figures (§3) | Done in PR 1, provisional | Alibaba memory first; CPU labeled average usage |
| 3 | Contract comparison and comparable/non-comparable table (§2, §4) | Done in PR 1 | `contract_comparison`, `comparability` |
| 4 | Dataset completion status (§1) | Provisional in PR 1 | Final once Tasks 9, 10 and 11 have recorded outcomes |
| 5 | Move from provisional to verified status for Alibaba | **Remaining** | Needs Task 8 merged; checksums alone are not enough (task file, Current Project State) |
| 6 | Google results final, or kept with documented limitations | **Remaining** | Needs Task 10 decision |
| 7 | Alibaba 2018 and Azure scope statements (§3) | **Remaining** | Needs Task 9 and Task 11 outcomes |
| 8 | Limitations per dataset (§5) | **Remaining** | |
| 9 | Adapter integration evidence: same contract, framework and evaluator per dataset (§6) | **Remaining** | Task 13 adapter can be cited for Google |
| 10 | Final artifact manifest covering every reported artifact (§7) | **Remaining** | Extends the Task 8 manifest |
| 11 | Fresh-environment reproduction from `requirements.txt` (§7) | **Remaining** | |
| 12 | Conclusions per dataset and overall; README and runbook (§8) | **Remaining** | |
| 13 | Required tests: traceability, identical regeneration, CPU label check, no cross-dataset ranking, full `pytest` | Partly done in PR 1 | Recheck after PR 2 changes |

### 4.3 Task 15: Developer API and Risk-Based Frontend (#120)

| # | Item | Status | Note |
|---|---|---|---|
| 1 | Decide frameworks for API and frontend | **Remaining** | Team decision before starting |
| 2 | Decide where the Alibaba export lives (Git if under ~20 MB, else Drive with checksums) | **Remaining** | |
| 3 | Confirm "latest recommendation" = last test occurrence of the workload | **Remaining** | Proposed in the task file |
| 4 | Part A: `scripts/export_ui_artifacts.py` (risk levels, policy summaries, long-format workloads, metadata, `SHA256SUMS`) | **Remaining** | Copy and reshape only; no recalculation; nulls stay null |
| 5 | Part B: read-only REST API (`/datasets`, `/risk-levels`, workloads, history, policies, `/health`) | **Remaining** | Units on every value; refuses to start on checksum mismatch |
| 6 | Part C: frontend (lookup, risk selector, history chart, policy comparison, about page) | **Remaining** | Can start on mock API responses once the Part A format is agreed |
| 7 | Part D: export, API and frontend smoke tests | **Remaining** | Locked environment; update `requirements.txt` and lock file |
| 8 | Part E: Figures 8.1 and 8.2 screenshots, §8.3 "planned" → "implemented", README, demo script | **Remaining** | Also recheck Ch2 Fig 2.1 and Ch4 Fig 4.4 |

### 4.4 Task 14: Google Evaluation Follow-ups (#119)

| # | Item | Status | Note |
|---|---|---|---|
| 1 | Cross-split Google targets | **Remaining** | Carried out by Task 10, or a recorded decision not to run it |
| 2 | Bootstrap confidence intervals for the Google and Alibaba test tables | **Remaining** | From local row-level outputs; no new decisions |
| 3 | Optional: rerun Google on a larger ClusterData 2019 sample | **Remaining (optional)** | |
| 4 | Feature importance (permutation; impurity for Google random forests) on training rows only | **Remaining** | Alibaba model binaries come from the local `data/processed/` lock |
| 5 | Label all new results as post-report follow-ups | **Remaining** | Published results and manifests unchanged |

### 4.5 Task 10: Google Subset Corrections and Rerun (#115)

| # | Item (task file section) | Status | Note |
|---|---|---|---|
| 1 | Decisions D-1 (target isolation), D-3 (Google final evaluation) | **Remaining** | Or decide to keep current results with limitations |
| 2 | Assign splits first, then build next-occurrence targets; fix F5 markdown (§1) | **Remaining** | |
| 3 | Freeze validation population; rerun baselines for `min_runs` 1, 3, 5, 10; select on validation (§2) | **Remaining** | |
| 4 | Resource fields, missing memory as NaN, split integrity (§3, §4) | **Remaining** | |
| 5 | Regenerate `data/processed/google_subset_v1/` and metadata with `target_split_isolation` (§5) | **Remaining** | Back up the earlier versions first |
| 6 | Before/after comparison and leakage audit (§6) | **Remaining** | |
| 7 | Update the target-null test; rerun Notebook 05 (§7) | **Remaining** | |
| 8 | Notebook 06 one-time Google final test, if approved (§8) | **Remaining** | New manifest; reported as a new run |

### 4.6 Task 9: Alibaba 2018 Adapter Demonstration (#114)

| # | Item (task file section) | Status | Note |
|---|---|---|---|
| 1 | Run `Alibaba2018Adapter` through the Task 1 framework; output unchanged (§1) | **Remaining** | |
| 2 | Validated `instance` rows and metadata at 0.2.0; no recurrence fields; gaps recorded (§2) | **Remaining** | |
| 3 | Capability checks; `occurrence` and `role_occurrence` rows rejected (§3) | **Remaining** | |
| 4 | Optional request-versus-observed comparison (§4) | **Remaining (optional)** | Task file recommends deferring (D-1, D-2) |
| 5 | Record one outcome: demonstrated, partially integrated or deferred (§5) | **Remaining** | Needed by Task 12 |

### 4.7 Task 11: Azure VM Dataset Integration (#116)

| # | Item | Status | Note |
|---|---|---|---|
| 1 | Stage 1 inspection (version, tables, timestamps, identity, resource fields, semantics) | Mostly done | Feasibility study; some points marked "needs data" |
| 2 | Recurrence, targets and evaluation options | Partly done | Study finds no observed memory and no status field |
| 3 | Record the go or stop decision | **Remaining** | Needed by Task 12 |
| 4 | Stage 2 integration | **Remaining, only on go** | |

### 4.8 Task 3 Follow-up: Peak Memory of the Alibaba GPU 2020 Build (no issue)

| # | Item | Status | Note |
|---|---|---|---|
| 1 | File the GitHub issue from `task3_followup_memory.md` | **Remaining** | |
| 2 | Step 1: release `prepared` frames before validation (`base.py`) | **Remaining** | Framework change; separate PR |
| 3 | Step 2: linkage and uniqueness validation without full copies | **Remaining** | Framework change |
| 4 | Step 3: adapter copies, view assembly, validity strings | **Remaining** | Target Part B stage at or below 14 GB |
| 5 | Step 4: optional deep-copy and non-finite check changes | **Remaining (optional)** | |
| 6 | Step 5: full build, B7 checks, `--verify`, two-build determinism | **Remaining** | |

### 4.9 Issue Housekeeping

| # | Item | Status |
|---|---|---|
| 1 | Close #87 (Task 6) and #89 (Task 7) after Task 8 merges | **Remaining** |
| 2 | Close #75 (N06) and #67 (Issue 5) | **Remaining** |
| 3 | Remove `pr70_schema_followup_review.md` | **Remaining** |
