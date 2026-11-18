# Current Status of Tasks and Issues

**Snapshot:** 2026-11-18, checked against `main` at `a4db373` (PR #129 merged), the open GitHub issues and pull requests, and the task files in this folder. Task 15 was split into Tasks 15 (backend) and 16 (web UI) the same day, and Task 8 rows were updated after PR #121 merged (`7eb48a7`). GitHub is the live record; check it before acting on any row here.

---

## 1. Completed

| Task | Issue | Evidence on `main` | Note |
|---|---|---|---|
| Tasks 1–5, schema 0.2.0 and Alibaba 2018 corrections | #66, #77, #79, #80, #81, #82, #85 | All closed; PRs #86–#96 merged | Done |
| Task 6: Alibaba GPU 2020 baselines and `min_runs` | **#87 (still open)** | PR #97 merged; PR #124 added `dataset_id` and `schema_version` metadata | Work done; close the issue |
| Task 7: ML, Hybrid and final test | **#89 (still open)** | PRs #98, #99, #102, #103 and the provenance follow-up #124 merged | Work done; close the issue (Task 8 merged 2026-11-16) |
| Task 13: Google subset thin adapter | #118 | PR #122 merged | Closed |
| Report: Abstract and Chapters 1–9, LaTeX and Overleaf | #71, #100, #107, #108 | PRs #101–#112 merged | Closed |

## 2. In Progress or Remaining

| Task | Issue | Priority | Status | What is left |
|---|---|---|---|---|
| Task 8: Alibaba GPU 2020 final verification | #113 | P1 | **PR #121 merged 2026-11-16.** `main` now holds the Nov 15 run (`4fdc7e96…`), which re-ran Tasks 4–7 and the final test in a different environment and replaced the Oct 30 results and run log | Follow-ups: record the rerun, update the report's Alibaba ML/Hybrid numbers, check the environment against the lock file; close #113 (table 4.1) |
| Task 8 follow-up: share the Nov 15 Alibaba run artifacts | #130 | P1 | **Done** (2026-11-16): uploaded to Drive `CMPE 295A_B/alibaba_gpu_v2020_run_4fdc7e96/`; 31/31 checksums matched on the uploader's machine and again on a second machine | Close #130 |
| Task 12: final cross-dataset reporting | #117 (open) | P1 | **PR 1 (#123) and PR 2 (#129) merged**; final bundle in `reports/results/cross_dataset_final/` is `DECISION_PENDING` | Google, Azure and Alibaba 2018 decisions; Task 10 before/after comparison (table 4.2) |
| Task 15: recommendation backend (UI export and read-only API) | #120 | P1 | **Done on `feature/task15-backend`** (2026-11-16); verified bundle from the Nov 15 run in `reports/results/ui/` | Merge PR #131; close #120 (table 4.3) |
| Task 16: recommendation web UI | *new; file the issue* | P1 | **Not started**; split from Task 15 | Framework choice, views, tests, report Figures 8.1 and 8.2 (table 4.4) |
| Task 10: Google subset corrections and rerun | #115 | P3 | **Not started** | Targets after split assignment, reselection, rerun of Notebooks 04–06, or a recorded decision to keep the current results with limitations (table 4.6) |
| Task 14: Google evaluation follow-ups | #119 | P3 | **Not started** | Cross-split targets (through Task 10), confidence intervals, feature importance (table 4.5) |
| Task 9: Alibaba 2018 adapter demonstration | #114 | P2 | Adapter updated for 0.2.0 (PR #92); **no outcome recorded** | Framework run, validated output, one recorded outcome (table 4.7) |
| Task 11: Azure VM dataset integration | #116 | P4 | Stage 1 study in `docs/data/azure_vm_traceadvisor_feasibility.md` (2026-10-29); old `src/adapters/azure_vm.py` (2026-10-14) | Record the go or stop decision; Stage 2 only on go (table 4.8) |
| Task 3 follow-up: peak memory of the Alibaba GPU 2020 build | **No GitHub issue** | P2 | **Not started**; adapter unchanged since 2026-10-25 | File the issue from `task3_followup_memory.md`; optional (table 4.9) |

## 3. Stale Items to Close

| Item | Reason |
|---|---|
| #75 N06: Google Hybrid and final comparison (P0) | Notebook PR #88 merged and the Google results are in Chapter 7; a corrected rerun belongs to Task 10 |
| #67 Issue 5: common recommendation output interface (P0) | Opened before the 295B scope reset; superseded by the Task 15 UI bundle format (design plan §6) |
| `pr70_schema_followup_review.md` | Review notes for #80, which is closed; the file can be removed |

---

## 4. Remaining Work by Task

### 4.1 Task 8: Alibaba GPU 2020 Final Verification (#113, PR #121)

| # | Item | Status | Note |
|---|---|---|---|
| 1 | Checksums of the Task 3, 4, 6 and 7 artifacts | Done in PR #121 | |
| 2 | Contract checks (dataset ID, schema 0.2.0, seven policies, memory first, separate denominators, no GPU or any-resource metric) | Done in PR #121 | |
| 3 | Lock predates the final test; one test-target read; one evaluator call | Done in PR #121 | Depends on the counters from PR #124 |
| 4 | Review PR #121 | Done 2026-11-16 | Findings in `docs/design/discussion_summary_2026-11-16.md` §3 |
| 5 | Merge PR #121 | Done 2026-11-16 | The Nov 15 run is now the published Alibaba result on `main` |
| 6 | Record the rerun: add the Oct 30 run (and `7dd3942e…`) to the run log or a provenance note, with the reason for the rerun | **Remaining** | Run log on `main` still shows one run with `prior_runs: 0` |
| 7 | Fix the verifier's run-history check (all manifest hashes; fail when `prior_runs = 0` but earlier runs exist) | **Remaining** | Follow-up PR |
| 8 | Environment: the Nov 15 run used Python 3.11, pandas 3.0.2, scikit-learn 1.8.0, xgboost 3.2.0; either update `requirements-lock.txt` or document the difference | **Remaining** | Reproducibility (Ch8) |
| 9 | Update the report's Alibaba ML and Hybrid numbers (abstract, Ch5, Ch7, Ch9) to the Nov 15 run | **Remaining** | Separate PR; baselines unchanged |
| 10 | Close #113, #87 and #89 | **Remaining** | |

### 4.2 Task 12 PR 2: Final Cross-Dataset Reporting (#117)

PR #129 merged on 2026-11-18 (`a4db373`). It adds the separate
`cross_dataset_final/` bundle with published Task 8 provenance, limitations,
conclusions and reporting-only reproduction instructions.
This status file is no longer pinned as Task 12 evidence (it changes with every
update); the bundle was regenerated in PR #131 with only checksum changes.
Google retention, Azure go/stop and Alibaba 2018 outcomes remain `decision_pending`.
Issue #117 remains open while those decisions and the Task 10 before/after
comparison await evidence.
Task 8 history/environment repairs and manuscript updates remain separate work.


| # | Item (task file section) | Status | Note |
|---|---|---|---|
| 1 | Reporting script, configuration, input-integrity and provenance checks | Done in PR 1 | `scripts/build_final_cross_dataset_report.py` |
| 2 | Per-dataset results tables and figures (§3) | Done in PR 1, provisional | Alibaba memory first; CPU labeled average usage |
| 3 | Contract comparison and comparable/non-comparable table (§2, §4) | Done in PR 1 | `contract_comparison`, `comparability` |
| 4 | Dataset completion status (§1) | Provisional in PR 1 | Final once Tasks 9, 10 and 11 have recorded outcomes |
| 5 | Link Alibaba reporting to the accepted Task 8 run | Done in PR #129 | Task 8 (#121) is merged. The bundle preserves its verification limits |
| 6 | Google results final, or kept with documented limitations | **Remaining** | Needs Task 10 decision |
| 7 | Alibaba 2018 and Azure scope statements (§3) | **Remaining** | Needs Task 9 and Task 11 outcomes |
| 8 | Limitations per dataset (§5) | Done in PR #129 | Included in the final bundle |
| 9 | Adapter integration evidence: same contract, framework and evaluator per dataset (§6) | **Remaining** | Task 13 adapter can be cited for Google |
| 10 | Final artifact manifest covering the reporting bundle (§7) | Done in PR #129 | Includes the published Task 8 evidence linkage |
| 11 | Reproduction in the locked Python 3.12 environment (§7) | Done in PR #129 | Use `requirements-lock.txt` |
| 12 | Conclusions per dataset and overall; README and runbook (§8) | Done in PR #129 | Dataset decisions remain pending |
| 13 | Required tests: traceability, identical regeneration, CPU label check, no cross-dataset ranking, full `pytest` | Done in PR #129 | Full suite passes in the locked environment |

### 4.3 Task 15: Recommendation Backend (#120)

| # | Item | Status | Note |
|---|---|---|---|
| 1 | Design plan agreed | **Done** | `docs/design/recommendation_service_design_plan.md` |
| 2 | Part A: `config/ui_risk_levels.json` (Restrictive → Hybrid, Balanced → P95, Efficient → P90) | **Done** | |
| 3 | Part B: `scripts/export_ui_artifacts.py` writes the UI bundle with checksums and metadata | **Done** | Copy and reshape only; Google Hybrid re-applied by the existing rule and checked against stored values |
| 4 | Part B: measure the bundle; commit if under 20 MB, else Drive with checksums | **Done** | 12 MB with zstd Parquet; committed |
| 5 | Part C: read-only API under `/api/v1`, checksum check at start-up | **Done** | FastAPI |
| 6 | Part C: OpenAPI contract committed for Task 16 | **Done** | Unblocks Task 16 |
| 7 | Part D: export tests, fixture bundle, API tests; dependencies in the lock file | **Done** | |
| 8 | Final export from the Nov 15 Alibaba run now on `main` | **Done** | 31/31 checksums matched; both datasets `verified` |
| 9 | README: run the export and the API | **Done** | |

### 4.4 Task 16: Recommendation Web UI (no issue yet)

| # | Item | Status | Note |
|---|---|---|---|
| 1 | File the GitHub issue from `task16_recommendation_web_ui.md` | **Remaining** | |
| 2 | Part A: choose the frontend approach | **Remaining** | Proposal: static HTML/JS with Chart.js, served by the API |
| 3 | Part B: dataset selector, workload lookup, recommendation panel with risk selector, history chart, policy comparison, about page | **Remaining** | Against the fixture-backed API first |
| 4 | Part C: display rules (units, "not available", Alibaba CPU label, no cross-dataset view) | **Remaining** | |
| 5 | Part D: UI smoke tests | **Remaining** | |
| 6 | Part E: Figures 8.1 and 8.2 screenshots, §8.3 "planned" → "implemented", README, demo script | **Remaining** | Needs the real bundle |

### 4.5 Task 14: Google Evaluation Follow-ups (#119)

| # | Item | Status | Note |
|---|---|---|---|
| 1 | Cross-split Google targets | **Remaining** | Carried out by Task 10, or a recorded decision not to run it |
| 2 | Bootstrap confidence intervals for the Google and Alibaba test tables | **Remaining** | From local row-level outputs; no new decisions |
| 3 | Optional: rerun Google on a larger ClusterData 2019 sample | **Remaining (optional)** | |
| 4 | Feature importance (permutation; impurity for Google random forests) on training rows only | **Remaining** | Alibaba model binaries come from the local `data/processed/` lock |
| 5 | Label all new results as post-report follow-ups | **Remaining** | Published results and manifests unchanged |

### 4.6 Task 10: Google Subset Corrections and Rerun (#115)

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

### 4.7 Task 9: Alibaba 2018 Adapter Demonstration (#114)

| # | Item (task file section) | Status | Note |
|---|---|---|---|
| 1 | Run `Alibaba2018Adapter` through the Task 1 framework; output unchanged (§1) | **Remaining** | |
| 2 | Validated `instance` rows and metadata at 0.2.0; no recurrence fields; gaps recorded (§2) | **Remaining** | |
| 3 | Capability checks; `occurrence` and `role_occurrence` rows rejected (§3) | **Remaining** | |
| 4 | Optional request-versus-observed comparison (§4) | **Remaining (optional)** | Task file recommends deferring (D-1, D-2) |
| 5 | Record one outcome: demonstrated, partially integrated or deferred (§5) | **Remaining** | Needed by Task 12 |

### 4.8 Task 11: Azure VM Dataset Integration (#116)

| # | Item | Status | Note |
|---|---|---|---|
| 1 | Stage 1 inspection (version, tables, timestamps, identity, resource fields, semantics) | Mostly done | Feasibility study; some points marked "needs data" |
| 2 | Recurrence, targets and evaluation options | Partly done | Study finds no observed memory and no status field |
| 3 | Record the go or stop decision | **Remaining** | Needed by Task 12 |
| 4 | Stage 2 integration | **Remaining, only on go** | |

### 4.9 Task 3 Follow-up: Peak Memory of the Alibaba GPU 2020 Build (no issue)

| # | Item | Status | Note |
|---|---|---|---|
| 1 | File the GitHub issue from `task3_followup_memory.md` | **Remaining** | |
| 2 | Step 1: release `prepared` frames before validation (`base.py`) | **Remaining** | Framework change; separate PR |
| 3 | Step 2: linkage and uniqueness validation without full copies | **Remaining** | Framework change |
| 4 | Step 3: adapter copies, view assembly, validity strings | **Remaining** | Target Part B stage at or below 14 GB |
| 5 | Step 4: optional deep-copy and non-finite check changes | **Remaining (optional)** | |
| 6 | Step 5: full build, B7 checks, `--verify`, two-build determinism | **Remaining** | |

### 4.10 Issue Housekeeping

| # | Item | Status |
|---|---|---|
| 1 | Close #87 (Task 6), #89 (Task 7) and #113 (Task 8) | **Remaining** |
| 2 | Close #75 (N06) and #67 (Issue 5) | **Remaining** |
| 3 | Remove `pr70_schema_followup_review.md` | **Remaining** |
| 4 | Update #120 to the Task 15 backend scope; create the Task 16 issue | **Remaining** |
