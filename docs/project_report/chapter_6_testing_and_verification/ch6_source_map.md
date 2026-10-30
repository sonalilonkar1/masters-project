# Chapter 6 Source Map: Testing and Verification

**Purpose:** for each Chapter 6 section, the tests, notebook checks, script checks and outputs to use. Chapter 6 describes **how the implementation was verified**: what each check tests, how, and what it found. Design reasons are in Chapter 4 and implementation in Chapter 5; refer to them, do not repeat them. Evaluation results belong in Chapter 7.

**Scope rules**
- Datasets: Google ClusterData 2019 (Kaggle subset) and Alibaba GPU Cluster Trace 2020. Tests for the Alibaba 2018 and Azure VM adapters exist but are out of scope (see the test inventory).
- Google thin adapter and the REST API and frontend are written as implemented.
- **[Task 7]** marks anything that depends on Alibaba Task 7 (PR #99 and PR2). Write it as implemented, leave numbers as *pending*, and add every such sentence to `pending_checks_after_task7.md` when the chapter is written.
- Every number checked against code, committed outputs or a test run. Style: formal prose, no bold lead-ins, citations only for the two datasets.

---

## Test inventory (run 29 Oct 2026, locked environment `~/venvs/traceadvisor-lock`)

`pytest -q`: **665 passed, 1 skipped** (666 collected, 28 s). The skipped test is `tests/test_alibaba_gpu_2020_loader.py:415`, which runs only with `TRACEADVISOR_FULL_DATA_TESTS=1` and the official tables downloaded.

| Area | Test file | Tests collected |
|---|---|---|
| Canonical schema | `test_canonical_schema.py` | 88 |
| Adapter framework | `test_adapter_contract.py`, `test_multiview_adapter_framework.py` | 30, 29 |
| Google canonical contract | `test_google_canonical_contract.py` | 5 |
| Google thin adapter | `test_google_subset_adapter.py` | Task 13 (written as implemented) |
| Alibaba GPU 2020 source loader | `test_alibaba_gpu_2020_loader.py` | 46 (1 skipped) |
| Alibaba GPU 2020 adapter | `test_alibaba_gpu_2020_adapter.py` | 181 |
| Alibaba canonical build script | `test_build_alibaba_gpu_2020_canonical.py` | 32 |
| Split helper | `test_split_utils.py` | 7 |
| Target builder | `test_target_builder.py`, `test_build_alibaba_gpu_2020_targets.py` | 65, 14 |
| Baselines | `test_alibaba_gpu_2020_baselines.py`, `test_run_alibaba_gpu_2020_baselines.py` | 22, 6 |
| ML preparation (Google) | `test_ml_prep.py` | 14 |
| Hybrid rule | `test_hybrid.py` | 10 |
| Metrics and evaluator | `test_evaluation.py`, `test_evaluator_contract.py` | 17, 58 |
| **[Task 7]** Alibaba ML | `test_alibaba_gpu_2020_candidates.py`, `test_alibaba_gpu_2020_ml_prep.py`, `test_alibaba_gpu_2020_select.py`, `test_run_alibaba_gpu_2020_ml.py` (in PR #99), final-test tests (PR2) | pending |
| Out of scope | `test_alibaba_adapter.py` (Alibaba 2018), `test_azure_vm_adapter.py`, `test_external_adapter_integration.py` | 25, 15, 2 |

In-scope total today: 624 collected (623 passed, 1 skipped). **[Task 7]** recount after Task 7 merges.

---

## 6.1 Data and Pipeline Correctness Checks

**What the section says:** how the data stages were verified: source integrity, reconciliation of every row, independent recomputation of derived values, and unit tests of the adapters and schema.

| Kind | Source |
|---|---|
| Google raw-data review | `pipelines/google_subset/00_dataQualityReview.ipynb` (405,894 rows × 34 columns; nested-field audit; 3 sentinel timestamps; no duplicate observation keys) |
| Google ingestion checks | `01_dataIngestion.ipynb` cells 3, 5 (resource and timestamp validation; peak ≥ average on all rows with both values), cell 21 (unique observation IDs) |
| Google reconstruction checks | `02_reconstructExecutions.ipynb` Steps 2, 7, 10, 11 (minimum positive gap 25 min > 5-min window; unique execution IDs; no negative runtimes; no missing recurrence keys) |
| Google independent recomputation | `03_buildProfilesAndMetrics.ipynb` cell 26 (point-in-time history: 4,879 occurrences, 87,822 historical metrics checked), cell 28 (cold starts have no statistics), cell 30 (occurrence CPU and memory peaks recomputed), cell 32 (request totals recomputed), cell 37 (saved artifacts re-read and compared) |
| Alibaba source integrity | `src/sources/alibaba_gpu_2020.py` `verify_table` (size, SHA-256, line count, header); `config/alibaba_gpu_2020_sources.json`; loader tests |
| Alibaba reconciliation | `reports/results/alibaba_gpu_2020/canonical/count_report.md` (source = accepted + rejected at job, role and instance level; expected-versus-actual table, all differences 0) |
| Alibaba output verification | `scripts/build_alibaba_gpu_2020_canonical.py --verify` (files, hashes, row counts, columns against the output contract) |
| Framework validation | `src/adapters/validation.py` `validate_adapter_output`, `validate_rejected_output`, `validate_role_instance_linkage`; tests in `test_adapter_contract.py`, `test_multiview_adapter_framework.py`, `test_alibaba_gpu_2020_adapter.py` |
| Google adapter acceptance | `test_google_subset_adapter.py`: adapter view equals the notebook canonical view (written as implemented) |
| Design reference | Chapter 4 §4.1; Chapter 5 §5.1 |

## 6.2 Temporal Leakage and Split Integrity

**What the section says:** the checks that no future or test information reaches a recommendation, model or selection, and what they found.

| Check | Source |
|---|---|
| Split boundaries between timestamp groups; no occurrence crosses a split | `src/features/split_utils.py` `chronological_split`; `test_split_utils.py`; Google `04_splitAndBaselines.ipynb` cell 13; Alibaba `target_builder.py` L331 (`An occurrence spans multiple splits`) |
| Target chronology and status/value invariant | Google Notebook 04 cell 26 (target chronology checks, 2,010 / 330 / 259 targets); Alibaba `target_builder.py` L329; `test_target_builder.py` |
| Point-in-time history (completed before start) | Google Notebook 03 cell 26; Alibaba `iter_resource_history` and `attach_history_statistics` count check (`src/baselines/alibaba_gpu_2020.py`) |
| Test rows never enter earlier histories | `scripts/run_alibaba_gpu_2020_baselines.py` L258 (`assert_frame_equal` of train and validation statistics with and without test rows) |
| Test read only after the lock, with an allow-list | Alibaba baselines: `baseline_selection.json` written before `test.parquet` is opened; `TEST_ALLOWED_COLUMNS` (L67); `test_run_alibaba_gpu_2020_baselines.py`. Google: Notebook 04 cell 43 ("Test performance has not been evaluated"); Notebook 05 cell 30 (explicit column list, assertion that no leaky or `target_` column is loaded); `n05_ml_metadata.json` `test_metrics_computed: false` |
| Feature leakage checks | Google `audit_occurrence_feature_manifest` (`ml_prep.py` L239), `OCCURRENCE_LEAKY_COLUMNS` and prefixes; Alibaba `validate_features` (`ml_prep.py` L113) with `ALIBABA_GPU_2020_LEAKY_COLUMNS` **[Task 7]** |
| Purged folds | `purged_time_series_folds` in `ml_prep.py`; Notebook 05 cells 16–20 |
| One-time final test | Google Notebook 06 cell 19 gates (manifest final, clean tree, same commit, notebook code hash, input SHA-256, refusal if a result exists); `decision_manifest.json`, `final_test_run_metadata.json`. **[Task 7]** Alibaba PR2 gates |
| Known limitation found | Google targets cross the validation/test boundary: 104 of 330 validation CPU targets start in the test period (recomputed 29 Oct from `val_occurrences.parquet`); measured by the target-period sensitivity (225 occurrences), Chapter 7 |
| Design reference | Chapter 4 §4.1.7, §4.3 |

## 6.3 Model and Baseline Validation

**What the section says:** how the baseline and ML implementations were checked: baseline statistics against independent computation, `min_runs` fallback behaviour, the Hybrid rule's properties, and model-selection reproducibility.

| Kind | Source |
|---|---|
| Baseline statistics and fallback | `test_alibaba_gpu_2020_baselines.py` (statistics, `min_runs` fallback, Request not selectable, ranking order); Google Notebook 04 cell 38 ("Request baseline is invariant across min_runs"), cell 48 (same occurrence IDs for every candidate) |
| Hybrid rule | `test_hybrid.py` (10): max rule, missing-safeguard fallback and flag, index alignment, rejection of negative or non-finite inputs |
| Hybrid never more violations than its safeguard | Check on results: Google final test Hybrid 12.36% any-resource violation vs P95 17.37% (`final_test_policy_comparison.csv`); **[Task 7]** Alibaba |
| Google model selection | `n05_ml_metadata.json` (grids, selection rule, locked parameters); `tables/ml_tuning_results.csv` (150 rows); `tables/ml_cv_summary.csv` (time-ordered vs grouped folds); `test_ml_prep.py` |
| Google ML reference floor | `ml_validation_model_comparison.csv`: median reference beaten on log-scale RMSE and RMSE, not on MAE |
| **[Task 7]** Alibaba model selection | `candidate_models.csv`, `model_selection.json`; Task 7 tests; whether the constant predictor can be selected (checklist D5) |
| Design reference | Chapter 4 §4.2; Chapter 5 §5.2–5.4 |

## 6.4 Replay Evaluation Metrics

### 6.4.1 Violation and Utilization · 6.4.2 Resource Waste · 6.4.3 Valid-Row Denominators and Missing-Value Handling

**What the section says:** how the metric functions and the evaluator were verified: hand-computed cases, NaN propagation, the three-valued combined violation, utilization cap and epsilon, separate denominators, profile masking and labels. Formulas are defined in Chapter 4 §4.3; here, only how they were tested.

| Kind | Source |
|---|---|
| Metric functions | `src/evaluation/metrics.py`; `test_evaluation.py` (17) |
| Evaluator contract | `src/evaluation/evaluator.py`; `test_evaluator_contract.py` (58): per-resource denominators, combined metric suppressed for Alibaba, `average_usage` CPU label, masking of unsupported resources, input not modified |
| Denominators in practice | Google: Notebook 04 cell 35 (Request denominators 326 of 329 because 3 requests are missing); `baseline_validation_comparison.csv` `valid_*_count` columns. Alibaba: memory 42,069 and CPU 41,913 on validation |
| Design reference | Chapter 4 §4.3; Chapter 5 §5.5 |

---

## Check against the code

| # | Item | Finding | Effect on Chapter 6 |
|---|---|---|---|
| 1 | Test counts | 665 passed, 1 skipped; 624 in scope | Report in-scope counts; name the skipped full-data test |
| 2 | Test counts differ from earlier notes | `test_hybrid.py` collects 10 and `test_evaluator_contract.py` 58 (parametrized cases), not 6 and 32 | Use collected counts |
| 3 | Out-of-scope tests | Alibaba 2018 and Azure VM tests pass but are not part of the evaluated system | Mention once, exclude from totals |
| 4 | Google cross-split targets | 104 of 330 validation targets in the test period | Report as a finding of the leakage checks |
| 5 | **[Task 7]** | ML tests, final-test gates, Alibaba Hybrid check | Leave as *pending*; add to the checklist |
