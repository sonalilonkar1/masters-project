# Task 6 (#87) Review: PR #97 — Alibaba GPU 2020 Baselines and `min_runs` Selection

**Branch:** PR #97 head (commit `af82838`, based on `main` at `d29d244`, the PR #96 merge)
**Status:** Review notes only; no fixes applied.
**Tests on branch:** the 24 new tests pass. Full suite: 647 passed, 1 skipped (`tests/test_ml_prep.py` not run locally because `sklearn` isn't installed).
**Full-data run:** during this review, the Task 4 tables were built locally from the shared Task 3 data (built from `c2ae87f`) with `scripts/build_alibaba_gpu_2020_targets.py`, and the PR's `scripts/run_alibaba_gpu_2020_baselines.py` was run on them at `af82838`. It finished in about 126 s with 2.2 GB peak memory. Result: **Request selected at `min_runs = 1`**; validation population 42,069 rows; 245 same-second rows; 889 multi-instance rows. The outputs were written to a scratch folder only.

**Verdict:** the calculations are correct. History statistics come from the shared `iter_resource_history` and match the Task 4 counts; Request fallback is per resource; every candidate is scored by the shared evaluator on one validation population; selection is memory-first and uses validation only; the selection record is written before test is opened; test is never scored. The problems are one design issue in the selection (D1: Request can be selected, and on the real data it is), two #87 requirements that are not fully met (I1, I2), and two smaller hardening fixes (I3, I4). D1 and I1–I4 should be fixed in this PR before merge. D1 comes from a gap in issue #87, so #87 and the Task 8 issue also need small wording edits (W1).

**Sections:**
1. Fix list
2. Design issue: Request can be selected
3. PR issues: the PR does not fully do what the issue asks
4. Issue wording: changes to #87 and the Task 8 issue for D1
5. What the PR achieves
6. Detailed checks

---

## 1. Fix list

| # | Kind | Finding | Severity | Fix in | When |
|---|---|---|---|---|---|
| D1 | Design issue | Request is a selection candidate; on the real data it is selected at `min_runs = 1`, so Hybrid cannot right-size and `min_runs` is not chosen by validation | High | `select_baseline` and `build_validation_comparison` in `src/baselines/alibaba_gpu_2020.py`; script selection record; #87 §6; one test | Before merge (this PR) |
| I1 | PR issue | Test is read with "everything except six columns", so the future-derived `next_occurrence_same_second` is loaded | Medium | `scripts/run_alibaba_gpu_2020_baselines.py` (51–54, 105–108); one test | Before merge |
| I2 | PR issue | The "CPU is average usage, not peak" label is missing from every output file | Medium | `src/baselines/alibaba_gpu_2020.py` (387–414, 469–515, 560–584); script (179–244); tests | Before merge |
| I3 | PR issue | Same-second and multi-instance sensitivity cuts are skipped silently, and recorded as 0 rows, if their column is missing | Low | `src/baselines/alibaba_gpu_2020.py` (610–617); one test | Before merge |
| I4 | PR issue | The lock-order test does not check that the selection record exists when test is read | Low | `tests/test_run_alibaba_gpu_2020_baselines.py` (95–117) | Before merge |
| W1 | Issue wording | #87 does not define the selection candidates; add that Request is reported but not selectable (also in the Task 8 issue and the task plan) | — | Issue #87 and Task 8 issue on GitHub; `docs/planning/data_integration_tasks.md` | Now, with D1; no code change |

Every finding below uses the same layout: **What the code does now, Why it is a problem, Fix, Where, Tests, Affects.**

---

## 2. Design issue

### D1. Request is a selection candidate, so the locked baseline can be Request at an arbitrary `min_runs` (High)

| | |
|---|---|
| **What the code does now** | `build_validation_comparison` scores every policy at every `min_runs` in `[1, 3, 5, 10]`, giving 20 rows, and `select_baseline` ranks all 20 with the D-2 order. Request is one of the candidates. Request does not use history, so its four rows (Request@1, @3, @5, @10) have identical metrics; if Request is best on the four metrics, the `min_runs` tie-break always gives **Request, `min_runs = 1`**. |
| **This happens on the real data** | The full-data run selects **Request at `min_runs = 1`**. Validation results (42,069 rows; memory waste in GB, CPU waste in `percent_of_vcpu`), in selection order: |

| Rank | Candidate | Memory violation % | Avg memory waste | Avg memory shortfall | CPU violation % | Avg CPU waste |
|---|---|---|---|---|---|---|
| 1–4 | Request @ 1, 3, 5, 10 (identical) | 4.74 | 22.26 | 0.83 | 15.52 | 430.1 |
| 5 | P99 @ 10 (best history candidate) | 5.58 | 8.94 | 0.42 | 6.62 | 295.0 |
| 6 | P99 @ 5 | 6.10 | 7.69 | 0.36 | 6.46 | 278.1 |
| 7 | P99 @ 3 | 6.77 | 6.88 | 0.34 | 6.65 | 266.3 |
| 9 | P99 @ 1 | 8.74 | 5.51 | 0.34 | 8.67 | 245.0 |

Request wins only on memory violation rate (by 0.84 points). P99@10 is better on every other metric: 60% less memory waste, half the memory shortfall, less than half the CPU violation rate.

| | |
|---|---|
| **Why it is a problem** | (1) **Hybrid can no longer right-size.** Task 7 (#89) builds Hybrid as `max(ML prediction, selected baseline)`. With Request as the baseline, Hybrid is at least the current request on every row: it can only add to the request, never reduce it, so it cannot save memory. The project plan starts Hybrid from a history percentile, `max(ML, P95)` (`docs/planning/assumptions.md` P-9; `docs/planning/295b_scope_and_done.md`). (2) **Request is the status quo, not a sizing policy.** It is the reference the other policies are compared against; the selection is meant to choose which history policy and how much history to use. (3) **`min_runs` is not chosen by validation.** The locked `min_runs` is used to build Mean, P90, P95 and P99 for every split, and Task 7 scores all five baselines on test at it and may not change it. With Request@1, every history baseline is reported at `min_runs = 1`, its worst setting on validation (P99: 8.74% memory violation at 1 against 5.58% at 10; P95: 11.90% against 8.46%; P90: 16.10% against 12.40%; Mean: 46.52% against 39.90%). |
| **Fix (recommended)** | Keep scoring and reporting Request in every table, but **do not let it be selected**. `select_baseline` ranks only the 16 history candidates (Mean, P90, P95, P99 × `min_runs` 1, 3, 5, 10) with the unchanged D-2 order. Add a column `selection_candidate` (`False` for Request, `True` otherwise) to `validation_comparison.csv`, and record the candidate policies in `baseline_selection.json`. Add one sentence to #87 §6: "Request is scored and reported as the status-quo reference but is not a selection candidate; the selected baseline and `min_runs` come from Mean, P90, P95 and P99." On the real data this selects **P99 at `min_runs = 10`**. |
| **Why this fix** | It removes all three problems at once: Hybrid starts from a history policy, as the project plan intends; `min_runs` always comes from a real validation comparison, with no special case or tie-break; and the agreed D-2 sort order is kept unchanged. |
| **Where** | `select_baseline` in `src/baselines/alibaba_gpu_2020.py` (428–462); `build_validation_comparison` (387–414); `selection_record` in the script (179–190); issue #87 §6 |
| **Tests** | A comparison where Request has the lowest memory violation: the selection is the best history candidate, never Request. Request rows are still present in the comparison, with `selection_candidate = False`. |
| **Affects** | Task 7 (Hybrid input; final-test baselines at the selected `min_runs`), Task 8 (verifies the selection record) |

**Fix in this PR.** The selection logic is new code in this PR, nothing is merged yet, and Task 7 consumes the locked selection directly; fixing it afterwards would mean rerunning Task 6 and changing Task 7's inputs. The non-code step is the wording edit to #87 and the Task 8 issue (W1). Google Notebook 04 also lets Request be selected; that is outside this PR (Google changes belong to Task 10).

---

## 3. PR issues

### I1. Test is read with "everything except six columns" (Medium)

| | |
|---|---|
| **What the code does now** | `_test_feature_columns` takes every column name in `test.parquet` and removes the six in `TEST_FORBIDDEN_COLUMNS` (`actual_cpu`, `actual_memory`, `actual_cpu_unit`, `actual_memory_unit`, `cpu_target_status`, `memory_target_status`). Everything else is loaded, including `next_occurrence_same_second`. |
| **Why it is a problem** | `next_occurrence_same_second` is built by Task 4 from the **next** run of each test row (whether it starts in the same second). It is information about the test future, and it is one of the target-side columns Task 4 lists in `DERIVED_COLUMNS`. #87 allows only "feature, request, split, and history-input columns" for test. Nothing uses the column today, and `build_locked_recommendations` drops it from the output, but it is in memory during the run. Because the list names what to exclude, any target-side column Task 4 adds later would also be loaded without anyone noticing. |
| **Confirmed on the real data** | The full-data `test.parquet` has 56 columns; the PR reads 50 of them. Besides `next_occurrence_same_second`, these include current-run outcome columns that are not history inputs and are not needed for recommendations, such as `observed_memory`, `observed_gpu`, `peak_gpu_memory`, `source_job_status` and `source_task_status`. |
| **Fix** | Read test with an explicit list of allowed columns: identity (`dataset_id`, `workload_id`, `record_level`, `role_key`, `occurrence_id`, `recurrence_key`, `split`); `start_time_us`, `end_time_us`; `requested_cpu`, `requested_memory` and their unit columns; the history inputs already in `HISTORY_INPUT_COLUMNS` (`observed_cpu`, `peak_memory`, `cpu_validity_status`, `memory_validity_status`, `exclusion_reason`); `cpu_history_count`, `memory_history_count`. Fail if any of them is missing. Keep the existing check that no forbidden column was read. |
| **Where** | `scripts/run_alibaba_gpu_2020_baselines.py` lines 51–54 and 105–108 |
| **Tests** | Extend `test_test_split_is_read_with_column_selection_after_lock`: the columns read from `test.parquet` equal the allowed list and do not include `next_occurrence_same_second`. |
| **Affects** | Task 7 (relies on Task 6 not having seen test outcomes), Task 8 (verifies leakage controls) |

### I2. The "CPU is average usage, not peak" label is missing from every output file (Medium)

| | |
|---|---|
| **What the code does now** | The evaluator marks CPU results in two ways: each evaluated row gets `cpu_usage_label = "average_usage"`, and `summary_metadata()` returns `cpu_result_semantics = "average_usage"`, `primary_resource = "memory"` and `any_resource_metric_reported = false`. The PR keeps only the numbers from `summarize()` and never calls `summary_metadata()`. Result per file: **`validation_comparison.csv`** has `policy`, `min_runs`, the counts and `cpu_violation_pct`, `memory_violation_pct`, utilization, waste, shortfall, and no label. **`sensitivity_validation.csv`**: the same. **`baseline_selection.json`**: `validation_metrics` holds `cpu_violation_pct` etc. with no label. **`recommendations_{train,validation,test}.parquet`**: `rec_cpu_request` … `rec_cpu_p99`, `rec_cpu_selected` with only `recommended_cpu_unit = percent_of_vcpu`. **`metadata.json`**: the three values are typed into the script as fixed text, not taken from the evaluator. |
| **Why it is a problem** | On this dataset CPU is the lifetime **average** of each run, and the peak is not available. So `cpu_violation_pct = 2` means "the next run's average CPU was above the recommendation in 2% of rows". It does not mean the CPU recommendation is safe at peak: a run whose average stays below the recommendation can still go far above it for short periods. Memory is the real peak (`max_mem`). In the CSV and the recommendation tables the CPU and memory columns look the same, so a reader or Task 7 has nothing in the file saying the CPU numbers are not peak-safe. #87 requires "CPU recommendations must be labeled as average-usage sizing" and, in §5, that `cpu_usage_label` and the `summary_metadata()` fields are carried into the validation outputs. Task 7 (#89) says the label must appear "everywhere". The fixed text in `metadata.json` is a second problem: it would still say `average_usage` if the profile or evaluator changed, so it is not evidence of what the evaluator actually did. |
| **Fix** | (a) In `build_validation_comparison` and `_score_subset`, call `evaluator.summary_metadata(evaluated)` after `summarize()` and add `cpu_result_semantics`, `primary_resource` and `any_resource_metric_reported` to each row, plus `cpu_usage_label` from the evaluated frame. (b) Add the same three fields to `baseline_selection.json`, next to `validation_metrics`. (c) In `build_locked_recommendations`, add `cpu_usage_label = "average_usage"` to every recommendation table, set from the profile (`has_cpu_average` and not `has_cpu_peak`), because the evaluator is not run on test. (d) In `metadata.json`, take the three values from the selected candidate's row instead of fixed text. Also add the Task 4 input folder and file names (relative to the repo) under `source_artifacts`; #87 §9 asks for paths as well as checksums. |
| **Where** | `src/baselines/alibaba_gpu_2020.py` lines 387–414, 469–515 and 560–584; `scripts/run_alibaba_gpu_2020_baselines.py` lines 179–190 and 223–244 |
| **Tests** | Every row of the validation comparison and the sensitivity table has `cpu_usage_label = average_usage`, `cpu_result_semantics = average_usage`, `primary_resource = memory` and `any_resource_metric_reported = False`. All three recommendation tables have `cpu_usage_label = average_usage`. `baseline_selection.json` and `metadata.json` contain the three fields, and `metadata.json` contains the input paths. |
| **Affects** | Task 7 (reads these files and must label CPU results), Task 8 (verifies semantics and metadata), the final report |

### I3. Sensitivity cuts are skipped silently if their column is missing (Low)

| | |
|---|---|
| **What the code does now** | `build_sensitivity_tables` adds the same-second cuts only `if "next_occurrence_same_second" in recommended.columns`, and the multi-instance cut only `if "inst_num" in recommended.columns`. `_counts` in the script then reads the row counts of those cuts, and returns 0 when the cut is absent. |
| **Why it is a problem** | Both cuts are required (#87 §8, acceptance criterion 12). If a column were missing, the cut would disappear with no error and `metadata.json` would record `same_second_rows: 0` or `multi_instance_rows: 0`, which looks like a real count. Both columns exist in the current Task 4 tables, so today's output is correct; this protects against a later input change. |
| **Fix** | Raise `ValueError` if either column is missing, as `freeze_common_validation_population` already does for `split` and the target statuses. |
| **Where** | `src/baselines/alibaba_gpu_2020.py` lines 610–617 |
| **Tests** | Dropping either column from the validation population raises. |
| **Affects** | Task 8 (verifies sensitivity tables and counts) |

### I4. The lock-order test does not check the lock (Low)

| | |
|---|---|
| **What the code does now** | `test_test_split_is_read_with_column_selection_after_lock` records the `read_parquet` calls and checks that `train.parquet` and `validation.parquet` are read before `test.parquet`. The code itself is in the right order (script lines 191–199). |
| **Why it is a problem** | The rule in #87 is that the **selection record is written** before test is read (§6, acceptance criterion 4). Reading train first does not prove that: if someone moved the `baseline_selection.json` write after the test read, this test would still pass. It is the main leakage control of the task. |
| **Fix** | Record the staging folder by wrapping `runner.tempfile.mkdtemp`, and in the `read_parquet` wrapper assert that `<staging>/baselines/baseline_selection.json` exists when `test.parquet` is read. |
| **Where** | `tests/test_run_alibaba_gpu_2020_baselines.py` lines 95–117 |
| **Tests** | This is the test. |
| **Affects** | Task 8 |

---

## 4. Issue wording

### W1. Selection candidates are not defined in #87 (edit on GitHub; no code change)

D1 is a design gap in issue #87, not the author's mistake: #87 says "rank policy and `min_runs` candidates" and gives the D-2 sort order, but never says which policies are candidates, so the PR ranked all five. The canonical schema docs (`canonical_schema_design_decisions.md` D-19, `canonical_workload_schema.md` §12) only say "baseline selection ranks memory first", which stays true after the fix, so they need no change. The D-2 sort order is unchanged; only the candidate set is defined.

| # | Where | Current text | Change to | Why |
|---|---|---|---|---|
| W1.1 | #87 §6 Validation-Only Memory-First Selection | "Rank policy and `min_runs` candidates using validation results only." | "Rank policy and `min_runs` candidates using validation results only. Candidates are Mean, P90, P95 and P99 at each `min_runs`. Request is scored and reported as the status-quo reference but is not a selection candidate." | D1 |
| W1.2 | #87 Decisions, D-2 | "Sort order: `memory_violation_pct`, `average_memory_waste`, `cpu_violation_pct`, `average_cpu_waste`, `min_runs`, and policy name." | Add: "Applied to the Mean, P90, P95 and P99 candidates only; Request is not selectable, because Hybrid is `max(ML, selected baseline)` and could never reduce the request." | Records the reason next to the decision |
| W1.3 | #87 Acceptance Criteria 3 | "Exactly one baseline policy and one `min_runs` value are recorded in a locked selection record." | "Exactly one history baseline policy (Mean, P90, P95 or P99) and one `min_runs` value are recorded in a locked selection record." | D1 |
| W1.4 | #87 Required Tests | — | Add: "Request is never selected, even when it has the lowest validation memory violation." | Test for D1 |
| W1.5 | Task 8 issue (`docs/planning/github_issues/task8_alibaba_gpu_2020_final_verification.md` §5) and its GitHub copy | "The selected policy and `min_runs` match the validation comparison under the documented sort order." | "…match the validation comparison under the documented sort order, among the selection candidates (Mean, P90, P95, P99; Request excluded)." | Otherwise Task 8 would expect Request@1 and flag the corrected selection as wrong |
| W1.6 | `docs/planning/data_integration_tasks.md`, Task 6 (line 457) | "memory-first choice of the baseline and `min_runs`, using train and validation only; test is never read." | "memory-first choice of the baseline (Mean, P90, P95 or P99; Request is reported as the reference) and `min_runs`, using train and validation only; test is never read." | Keeps the plan consistent with #87 |

Task 7 (#89) needs no change: it refers only to "the selected Task 6 baseline".

---

## 5. What the PR achieves

**Before the PR:** baselines existed only in Google Notebook 04. Task 4 provided the Alibaba GPU 2020 split tables and `iter_resource_history`, and Task 5 the profile-aware evaluator, but nothing produced Alibaba baselines or a locked selection.

**After the PR:**
- **Module** `src/baselines/alibaba_gpu_2020.py`: point-in-time Mean, P90, P95 and P99 per resource, streamed from `iter_resource_history` and checked against the Task 4 history counts; Request, Mean, P90, P95 and P99 recommendations with per-resource Request fallback; a common validation population; scoring through the shared evaluator; memory-first selection; locked recommendations; sensitivity tables.
- **Script** `scripts/run_alibaba_gpu_2020_baselines.py`: checks the Task 4 `SHA256SUMS`, selects on train + validation only, writes the selection record before opening test, reads test with column selection, checks that adding test does not change train or validation statistics, and publishes the outputs with `SHA256SUMS` through a staging folder.
- **Outputs:** `baseline_selection.json`, `validation_comparison.csv`, `sensitivity_validation.csv`, `history_statistics.parquet`, `recommendations_{train,validation,test}.parquet`, `metadata.json`, `SHA256SUMS`.
- **Tests:** 18 module tests and 6 script tests.

---

## 6. Detailed checks

### 6.1 PR against issue #87
| Requirement | Met? | Where / evidence |
|---|---|---|
| Task 4 tables read after the checksum check | Yes | `verify_targets` (script 80–98) |
| Test read with column selection after the lock; no targets or statuses | Partly | Column selection and lock order are correct; allowed columns: I1 |
| Only eligible rows; no rejected or `instance` rows | Yes | `iter_resource_history` filters `exclusion_reason`; only Task 4 split tables are read |
| History through `iter_resource_history`; train + validation for validation, all partitions for test | Yes | Module 125–169; script 165–166, 204–206 |
| Each history processed as it arrives; only statistics kept | Yes | `_resource_statistics` (88–114) |
| Statistic counts equal Task 4 history counts | Yes | `attach_history_statistics` raises on mismatch (172–206) |
| CPU from `observed_cpu`, memory from `peak_memory`, computed independently | Yes | `RESOURCE_SOURCE_FIELD`; separate snapshots per resource |
| Request uses `requested_cpu` and `requested_memory` only | Yes | `REQUEST_FIELD`; no job-total fields read |
| History used only when count ≥ `min_runs` and statistic non-null; otherwise Request | Yes | `add_baseline_recommendations` (232–264) |
| Missing request on an eligible row is an input error | Yes | `_require_requests` (213–229) |
| Units `percent_of_vcpu` and `gb`; scope `task_role_per_instance` | Yes | 63–67, 314–320, 490–492 |
| One common validation population, frozen before scoring | Yes | `freeze_common_validation_population` (339–361) |
| Scored with the shared evaluator and the Alibaba profile; no metric code reimplemented | Yes | `evaluate_policy` → `evaluate_canonical`; `summarize` |
| Separate CPU and memory denominators; shortfall recorded | Yes | `_SUMMARY_KEYS` (370–384) |
| No any-resource or GPU metrics | Yes | Not in `_SUMMARY_KEYS`; suppressed by the evaluator |
| CPU labeled average-usage; `cpu_usage_label` and `summary_metadata()` fields in outputs | No | I2 |
| Sort order as in D-2; ascending; NaN last | Yes | `SELECTION_SORT_ORDER` (71–78); `select_baseline` (428–462) |
| Exactly one policy and one `min_runs` chosen on validation | Partly | One of each is recorded, but Request can be selected and then `min_runs` is not chosen by validation: D1 |
| Selection record written before any test read; includes policy, `min_runs`, sort order, population, timestamp, commit | Yes | Script 179–193 (test: I4) |
| All five policies at the selected `min_runs` for every split; selected policy marked | Yes | `build_locked_recommendations` (469–515) |
| Evaluator never called on test | Yes | Only `build_locked_recommendations` runs on test |
| Same-second, multi-instance, occurrence- and group-weighted sensitivity; selection unchanged | Yes | `build_sensitivity_tables` (587–623); missing columns: I3 |
| History statistics kept for Task 7 | Yes | `history_statistics.parquet` |
| Metadata: checksums, Task 3 and Task 4 commits, profile, units, semantics, grid, sort order, selection, counts, code commit | Partly | Script 223–244; input paths missing and semantics written as fixed text: I2 |

### 6.2 Tests against issue #87's test list
| Required test | Covered by |
|---|---|
| History uses only eligible prior runs completed by the current start; counts equal Task 4 | `test_history_counts_equal_task4_counts`, `test_attach_history_statistics_rejects_count_mismatch` |
| Below `min_runs` falls back to Request per resource | `test_below_min_runs_falls_back_to_request_per_resource` |
| Null statistic triggers Request fallback | `test_null_statistic_triggers_request_fallback`, `test_empty_history_yields_nan_statistics` |
| Missing CPU never removes memory history or recommendations | `test_missing_cpu_never_changes_memory_recommendation` |
| Request equals canonical requests; missing request is an input error | `test_request_policy_equals_canonical_requests`, `test_missing_request_on_eligible_row_is_input_error` |
| CPU from average usage, memory from peak memory | `test_cpu_uses_observed_cpu_and_memory_uses_peak_memory` |
| Average-usage CPU label, memory primary, no any-resource metric | `test_evaluation_reports_average_cpu_memory_primary_and_no_any_resource` (evaluator output only, not the written files: I2) |
| Units and scope | `test_recommendation_units_and_scope_match_profile` |
| Same validation population for every candidate | `test_every_candidate_uses_the_same_validation_population` |
| Memory-first, deterministic selection | `test_selection_is_deterministic_and_memory_first`, `test_selection_sort_order_prefers_lower_memory_violation`, `test_selection_ignores_candidates_without_a_valid_denominator` (no test where Request has the lowest memory violation: D1) |
| No test targets loaded; test not scored | `test_test_recommendations_carry_no_targets_or_metrics`, `test_locked_recommendations_do_not_require_or_produce_test_targets` |
| Test recommendations only after the selection record is written | `test_test_split_is_read_with_column_selection_after_lock` (checks read order only: I4) |
| All policies at the selected `min_runs`; selected policy marked | `test_locked_recommendations_cover_all_policies_and_mark_selected` |
| Rerun reproduces the comparison and selection | `test_rerun_with_force_reproduces_selection` |
| Sensitivity outputs reproducible | `test_sensitivity_tables_are_reproducible_and_cover_expected_cuts` |
| Existing Google tests unchanged and passing | Full suite run on the branch |

Also covered: end-to-end artifacts, missing manifest and tampered checksum rejected. Tests to add or change are listed under D1 and I1–I4.
