# Chapter 5 Source Map: Project Implementation

**Purpose:** for each Chapter 5 section, the code, notebooks, scripts, artifacts and measured outputs to use. Chapter 5 describes **how the system was built and what it produced**: modules, functions, execution steps and measured counts. The reasons behind each choice are in Chapter 4 and are referenced, not repeated. Test design and results belong in Chapter 6, and evaluation results in Chapter 7.

**Scope rules**
- Datasets: Google ClusterData 2019 (Kaggle subset) and Alibaba GPU Cluster Trace 2020. Alibaba 2018 and Azure VM code exists in `src/adapters/` but is out of scope.
- No old report draft, no traceability file, no full-trace Google analysis doc, no dropped Alibaba evidence doc.
- Task 13 and the REST API and frontend are written as implemented. Alibaba Task 7 is merged and run; its statements were checked through `pending_checks_after_task7.md` (30 Oct 2026).
- Every number is checked against code, committed config or real outputs.
- Measured outputs moved from Chapters 2 and 4 are now in the Chapter 5 text; their sources are listed in the rows below.
- Style: formal, paper-style prose; citations only for the two datasets.
- Line numbers are from the working tree on `docs/issue-17-final-report`.

---

## 5.1 Data Pipeline

### 5.1.1 Ingestion, Unit Normalization, and Dataset Adapters

**What the section says:** how raw data is loaded and mapped. Google: Notebook 01 reads the CSV, parses the nested request and usage fields, converts timestamps, and keeps the original values as `raw_*` columns. Alibaba: the source loader verifies and loads the six tables; the adapter joins them, builds identities, applies the fourteen rules, maps resources with units, and emits three outputs; the build script publishes them. Both pass through the adapter framework.

| Kind | Source |
|---|---|
| Google ingestion | `pipelines/google_subset/01_dataIngestion.ipynb`: cell 2 parses nested `resource_request`, `average_usage`, `maximum_usage` with `ast.literal_eval` into `raw_req_*`, `raw_avg_*`, `raw_peak_*`; cell 4 builds `event_time_us`, `usage_start_time_us`, `usage_end_time_us`; output `google_subset_observations_v1.parquet` |
| Alibaba loader | `src/sources/alibaba_gpu_2020.py` — `verify_table` (L183: size, SHA-256, line count, header), `load_table` (L343), `iter_table_chunks` (L376), `source_row_number`; `config/alibaba_gpu_2020_sources.json` |
| Alibaba adapter | `src/adapters/alibaba_gpu_2020.py` — `AlibabaGPU2020Adapter` (L1089): `prepare_sources` (joins with coverage counts, identity, timestamps via `_seconds_to_us` L400, rejection routing), `map_prepared_sources` (`_failed_rules`, `_assign_exclusion_reasons`, `_map_resources` L745, `_aggregate_role_resources` L780, `_assign_validity`), `build_multiview_metadata` |
| Framework | `src/adapters/base.py` — `adapt` (L153), `adapt_sources` (L413); `src/adapters/validation.py` — `validate_adapter_output` (L189), `validate_rejected_output` (L283), `validate_role_instance_linkage` (L402) |
| Units | `src/canonical/schema.py` — `ALLOWED_RESOURCE_UNITS` (L27); resource maps in the Alibaba adapter (L712–721); Google `ncu` / `normalized` |
| Build and publish | `scripts/build_alibaba_gpu_2020_canonical.py` — `run_adapter` (L138), `verify_output` (L327), `publish` (L397), `build` (L419); options `--out-dir`, `--raw-dir`, `--force`, `--allow-dirty`, `--keep-failed-output`, `--verify` |
| Google adapter | `src/adapters/google_subset.py` *(Task 13)* |
| Measured outputs | Source row counts: `config/alibaba_gpu_2020_sources.json` (loader line-count check). `role_occurrence` 1,254,108 (461,900 eligible), `instance` 7,410,783, rejected 121,824 (3,663 jobs, 6,942 roles, 111,219 instances), group-tag join (1,053,971 matched, 1,530 untagged, 1,061 unused): `data/processed/alibaba_gpu_v2020/count_report.md` and `metadata.json` (`join_coverage_counts`); committed copies in `reports/results/alibaba_gpu_2020/canonical/`, group-tag counts also recomputed from the raw tables |
| Design reference | Chapter 4, §4.1.1–4.1.3, §4.1.6 |

### 5.1.2 Execution Reconstruction and Dataset-Specific Temporal Features

**What the section says:** how runs are reconstructed and placed in time. Google: Notebook 02 builds execution episodes (`collection_id` + `instance_index`, new episode when the gap exceeds the five-minute window), Notebook 03 builds occurrences and point-in-time history, Notebook 04 applies the chronological split and builds next-occurrence targets. Alibaba: roles and instances are built inside the adapter; `build_targets` adds splits, history counts and split-isolated targets.

| Kind | Source |
|---|---|
| Google executions | `02_reconstructExecutions.ipynb` — Step 7 (episode boundaries: `gap_from_previous_us > OBSERVATION_WINDOW_US`, 5 min), Step 8 (execution ID), Step 9 (aggregate observations), Step 11 (attach workload identity); outputs `google_subset_executions_v1.parquet` |
| Google occurrences and history | `03_buildProfilesAndMetrics.ipynb` — cell 10 (occurrence key `recurrence_key||execution_start_time_us`, requests by complete sum), "Build Point-in-Time History", "Validate Point-in-Time History", "Validate Cold Starts"; output `job_profiles_google_subset_history_v1.parquet` |
| Google split and targets | `04_splitAndBaselines.ipynb` — "Freeze Chronological 70/15/15 Boundaries" (uses `src/features/split_utils.chronological_split`), "Next-Occurrence Target Construction"; outputs `{train,val,test}_occurrences.parquet`, `metadata.json` |
| Alibaba roles and instances | `src/adapters/alibaba_gpu_2020.py` — `_add_role_identity` (L261), `_add_instance_identity` (L295), `_inherit_parent_identity` (L351) |
| Alibaba targets | `src/features/target_builder.py` — `build_targets` (L245), `iter_resource_history` (L161), `write_target_tables` (L400); `scripts/build_alibaba_gpu_2020_targets.py` — `build` (L62) |
| Measured outputs | Google 253,585 executions (Notebook 02 output); 3,473 / 675 / 731 occurrences (Notebook 04 output). Alibaba 323,329 / 69,286 / 69,285 rows and target counts (`reports/results/alibaba_gpu_2020/alibaba_gpu_2020_results_tasks1_6.md` §4; targets `metadata.json` after Task 7) |
| Same-second targets | Alibaba: 2,006 train / 245 validation / 251 test rows whose next run of the same recurrence starts in the same whole second (`target_builder.py` L300–303, reported as `same_second_successor_rows` L343). Flagged and kept. Source for now: `alibaba_gpu_2020_results_tasks1_6.md` §4; verify from targets `metadata.json` after Task 7 |
| Design reference | Chapter 4, §4.1.4, §4.1.5, §4.1.7 |

### 5.1.3 Usage Aggregation and Resource Metrics

**What the section says:** exactly how the resource values used as targets are computed. Google: per observation, the canonical peak comes from `maximum_usage`; per occurrence, usage is summed across executions within each aligned window (`usage_start_time_us`, `usage_end_time_us`) only when every component is present, and the maximum over windows is the occurrence peak; requests are summed across executions, again only when complete. Alibaba: role memory peak = maximum of `max_mem` over eligible workers; role CPU = maximum of `cpu_usage` (lifetime average); a missing CPU value on any worker leaves role CPU null and partial; GPU fields carried but not evaluated.

| Kind | Source |
|---|---|
| Google peaks | `03_buildProfilesAndMetrics.ipynb` cell 6 (`window_totals` grouped by occurrence + window, `cpu_total` / `memory_total` summed only if all present; `occurrence_peak_cpu_ncu`, `occurrence_peak_memory_normalized` = max over windows) |
| Google requests and runtime | Same notebook, cell 10 (`complete_sum` of requests; `occurrence_runtime_sec`) |
| Alibaba resources | `src/adapters/alibaba_gpu_2020.py` — `ROLE_RESOURCE_MAP`, `INSTANCE_RESOURCE_MAP` (L712–721), `_aggregate_role_resources` (L780), `_role_validity` (L900) |
| Decision record | `canonical_schema_design_decisions.md` D-10, D-11, D-14, D-16 (1,224 eligible roles with missing CPU, 0.26%) |
| Design reference | Chapter 4, §4.1.1, §4.1.4 |

## 5.2 Baseline Recommenders

### 5.2.1 Request-As-Is

**What the section says:** the Request policy copies the canonical request into the recommendation columns for both resources; Alibaba scores and reports it but excludes it from selection.

| Kind | Source |
|---|---|
| Alibaba | `src/baselines/alibaba_gpu_2020.py` — `add_baseline_recommendations` (L247: `rec_{resource}_request`), `SELECTABLE_POLICIES`, `select_baseline` (L469) |
| Google | `04_splitAndBaselines.ipynb` — "Occurrence-Level Baseline Recommendations" |
| Measured result | Request vs P99@10 on validation: 4.74% vs 5.58% memory violation, 22.26 vs 8.94 GB memory waste, memory utilization 0.26 (`alibaba_gpu_2020_results_tasks1_6.md` §5.2) |

### 5.2.2 Mean and Percentile Recommendations

**What the section says:** how history statistics are computed (count, mean, P90, P95, P99 with linear interpolation) and turned into recommendations at each `min_runs`; the validation grid (4 policies × 4 thresholds, plus Request), the ranking order, the selected configuration, and the locked recommendations for all splits.

| Kind | Source |
|---|---|
| Alibaba statistics | `src/baselines/alibaba_gpu_2020.py` — `_resource_statistics` (L103; `np.percentile`, `PERCENTILE_METHOD = "linear"` L96), `compute_history_statistics` (L140), `attach_history_statistics` (L187) |
| Alibaba selection and lock | `build_validation_comparison` (L422), `select_baseline` (L469), `build_locked_recommendations` (L530), `build_sensitivity_tables` (L656); `scripts/run_alibaba_gpu_2020_baselines.py` — `verify_targets` (L92), `run` (L157); outputs `history_statistics.parquet`, `validation_comparison.csv`, `baseline_selection.json`, `recommendations_{train,validation,test}.parquet`, `sensitivity_validation.csv` |
| Google | `03_buildProfilesAndMetrics.ipynb` "Build Historical Resource Features" (pandas `quantile`, linear); `04_splitAndBaselines.ipynb` "Build Validation Candidates", "Evaluate All Validation Configurations", "Validation-Only Baseline Selection", "Generate Final Baselines" |
| Measured results | Google: P99 at `min_runs = 1` (`reports/results/google_subset/n04_metadata.json`, `tables/baseline_validation_comparison.csv`). Alibaba: P99 at `min_runs = 10` (`reports/results/alibaba_gpu_2020/alibaba_gpu_2020_results_tasks1_6.md`) |
| Design reference | Chapter 4, §4.2.1 |

### 5.2.3 Cold-Start Handling and Fallbacks

**What the section says:** what happens when history is short or absent: per-resource fallback to the request below `min_runs`, NaN statistics for empty history, `uses_history_*` flags, Hybrid falling back to ML when the baseline is missing, and how many rows each fallback affects.

| Kind | Source |
|---|---|
| Code | `add_baseline_recommendations` (L247: `use_history = (count >= min_runs) & statistic.notna()`); `_resource_statistics` (empty history → NaN); `src/policies/hybrid.py` — `hybrid_recommendation` (L22, `safeguard_missing`) |
| Google | `03_buildProfilesAndMetrics.ipynb` "Validate Cold Starts and Missing Values"; `06_finalPolicyComparison.ipynb` cell 8 ("Validation rows where Hybrid falls back to ML") |
| Google counts (measured 29 Oct 2026, locked environment, `{train,val,test}_occurrences.parquet`) | Rows with no prior completed occurrence: 1,801 / 239 / 240 of 3,473 / 675 / 731. On the evaluation population (both targets: 1,983 / 329 / 259), P99@1 uses history for CPU 1,372 / 303 / 250 and memory 1,368 / 301 / 250; the rest fall back to Request (CPU 611 / 26 / 9, memory 615 / 28 / 9). Request is itself missing on 23 / 3 / 2 of these rows, so P95 and P99 are missing on 7 / 1 / 0 (CPU) and 9 / 1 / 0 (memory). Validation rows where Hybrid falls back to ML: CPU 1, memory 1 (matches Notebook 06 cell 8 output) |
| How Table 5.3 is computed | Not saved in any output file; recompute with the locked environment (`~/venvs/traceadvisor-lock`) from `data/processed/google_subset_v1/{train,val,test}_occurrences.parquet`. Evaluated population = rows with both `target_cpu_next_occurrence_peak_ncu` and `target_memory_next_occurrence_peak_normalized` present. "From history" = `uses_history_{cpu,memory}_p99` true; "Request fallback" = false; "No value" = `rec_{cpu,memory}_p99` missing. Cold starts = `prior_completed_occurrence_count == 0` on all rows. Snippet below this table |
| Alibaba counts | Table 5.4 from `alibaba_gpu_v2020_targets/` and `alibaba_gpu_v2020_baselines/` with the snippet in `pending_checks_after_task7.md` Step 4 (run 30 Oct 2026, after the final test); Hybrid fallback 0 from `ml/metadata.json` and `final_test/run_record.json` |

**Table 5.3 snippet** (Google, selected baseline P99 at `min_runs = 1`):

```python
import pandas as pd
D = "data/processed/google_subset_v1"
for split in ["train", "val", "test"]:
    d = pd.read_parquet(f"{D}/{split}_occurrences.parquet")
    pop = d[d.target_cpu_next_occurrence_peak_ncu.notna() & d.target_memory_next_occurrence_peak_normalized.notna()]
    print(split, "rows", len(d), "cold starts", int((d.prior_completed_occurrence_count == 0).sum()),
          "| evaluated", len(pop),
          "history cpu/mem", int(pop.uses_history_cpu_p99.sum()), int(pop.uses_history_memory_p99.sum()),
          "request cpu/mem", int((~pop.uses_history_cpu_p99).sum()), int((~pop.uses_history_memory_p99).sum()),
          "no value cpu/mem", int(pop.rec_cpu_p99.isna().sum()), int(pop.rec_memory_p99.isna().sum()))
```

Expected output (29 Oct 2026): train 3473 / 1801 / 1983 / 1372 1368 / 611 615 / 7 9; val 675 / 239 / 329 / 303 301 / 26 28 / 1 1; test 731 / 240 / 259 / 250 250 / 9 9 / 0 0.

## 5.3 Machine Learning Recommender

### 5.3.1 Feature and Target Preparation

**What the section says:** the feature lists and how matrices are built. Google: the 24 `OCCURRENCE_FEATURE_COLS`, the leaky-column and leaky-prefix lists, NaN kept, `log1p` targets, label-period row selection. Alibaba: requests, history counts and Task 6 statistics, missing indicators then zero fill, per-resource training rows, saved feature order.

| Kind | Source |
|---|---|
| Google | `src/features/feature_config.py` — `OCCURRENCE_FEATURE_COLS` (L147); `src/features/ml_prep.py` — `audit_occurrence_feature_manifest` (L239), `build_occurrence_feature_matrix` (L312), `select_label_period_rows` (L331); `data/processed/google_subset_v1/ml_feature_manifest.json` (committed copy: `reports/results/google_subset/ml_feature_manifest.json`) |
| Alibaba | `ml_prep.prepare_xy` (L27), `validate_features` (L113); `src/features/alibaba_gpu_2020_feature_config.py`, `alibaba_gpu_2020_ml_prep.py`; `reports/results/alibaba_gpu_2020/ml/feature_order.json` (43 columns) |
| Design reference | Chapter 4, §4.2.2 |

### 5.3.2 Model Training and Selection

**What the section says:** candidate grids, tuning procedure, selection rule, selected models and hyperparameters, refit, and locked model artifacts.

| Kind | Source |
|---|---|
| Google | `05_evaluateRecommendations.ipynb` cells 16–20 (`GridSearchCV` with `purged_time_series_folds`, `GroupKFold` robustness); `reports/results/google_subset/n05_ml_metadata.json` (`tuning.param_grids`, `selection_rule`, `selected_models`, `refit`); `decision_manifest.json` (`ml_locked_params`: Random Forest for CPU and memory, `n_estimators = 300`, `max_features = "sqrt"`, `min_samples_leaf = 10`, `max_depth` 10 (CPU) / 6 (memory), `random_state = 42`) |
| Google tuning record | `reports/results/google_subset/tables/ml_tuning_results.csv` (150 rows: 75 configurations per resource) |
| Alibaba | `scripts/run_alibaba_gpu_2020_ml.py`; `src/models/alibaba_gpu_2020_candidates.py`, `alibaba_gpu_2020_select.py`; `reports/results/alibaba_gpu_2020/ml/model_selection.json` |
| Design reference | Chapter 4, §4.2.2 |

### 5.3.3 Validation-Based Model Comparison

**What the section says:** the validation comparison of all candidates per resource, including the constant predictor, and the effect of tuning and of the label-period rule.

| Kind | Source |
|---|---|
| Google | `reports/results/google_subset/tables/ml_validation_model_comparison.csv`; `reports/results/google_subset/tables/ml_cv_summary.csv` (time-ordered and `GroupKFold` mean and spread: RF CPU 0.839 ± 0.054 vs 0.781 ± 0.285); Notebook 05 cell 26 summary |
| Alibaba | `reports/results/alibaba_gpu_2020/ml/candidate_models.csv` (Table 5.6) |

## 5.4 Hybrid Safeguard Recommender *(retitle from "Hybrid Risk-Aware Recommender")*

**What the section says:** how Hybrid is computed: the shared function, the safeguard inputs per dataset, validation predictions from train-only models, the fallback flag, the supplementary Google `Hybrid_P99` variant.

| Kind | Source |
|---|---|
| Code | `src/policies/hybrid.py` — `hybrid_recommendation` (L22: input checks, `np.fmax`, `safeguard_missing`) |
| Google | `06_finalPolicyComparison.ipynb` cell 8 (`hybrid`, `hybrid_p99`); `decision_manifest.json` (`hybrid_rule`, `hybrid_fallback`, `supplementary_policies`) |
| Alibaba | `reports/results/alibaba_gpu_2020/ml/validation_policy_comparison.csv`, `ml/metadata.json` |
| Tests | `tests/test_hybrid.py` (6 tests) |
| Design reference | Chapter 4, §4.2.3 |

## 5.5 Shared Metrics and Evaluation Framework

**What the section says:** how the metrics and evaluator are implemented: vectorized NumPy metric functions returning NaN for unknown, the evaluator's `evaluate` / `evaluate_canonical` / `summarize` / `summary_metadata`, profile masking of unsupported resources, the frozen common population, and how both pipelines call it.

| Kind | Source |
|---|---|
| Metrics | `src/evaluation/metrics.py` — `cpu_violation` (L16), `memory_violation` (L42), `any_resource_violation` (L68), `bounded_utilization` (L118), `waste` (L189), `shortfall` (L222) |
| Evaluator | `src/evaluation/evaluator.py` — `RecommendationEvaluator` (L31), `_mask_unsupported_resources` (L59), `evaluate` (L84), `summarize` (L302), `summary_metadata` (L475), `_validate_profile_view` (L538), `evaluate_canonical` (L645) |
| Common population | Alibaba `freeze_common_validation_population` (L374); Google Notebook 04 metadata `common_validation_population` (329 occurrences) |
| Callers | Google Notebooks 04–06 (`RecommendationEvaluator()`); Alibaba `evaluate_policy` (L339) with `ALIBABA_GPU_2020_CAPABILITIES` |
| Tests | `tests/test_evaluation.py` (17), `tests/test_evaluator_contract.py` (32) |
| Design reference | Chapter 4, §4.3 |

## 5.6 Artifact Storage and Developer-Facing Outputs

**What the section says:** the artifact layout per stage, checksum and metadata files, staging and publish, the decision manifest and final-test run record, the committed results folders, the locked environment, and the REST API and frontend that read them.

| Kind | Source |
|---|---|
| Layout | `data/processed/alibaba_gpu_v2020/`, `alibaba_gpu_v2020_targets/`, `alibaba_gpu_v2020_baselines/`, `alibaba_gpu_v2020_ml/`, `alibaba_gpu_v2020_final_test/`; `data/processed/google_subset_v1/`; file lists below |
| Google files (`google_subset_v1/`) | `google_subset_observations_v1.parquet`, `google_subset_executions_v1.parquet`, `job_profiles_google_subset_history_v1.parquet`, `{train,val,test}_occurrences.parquet`, `metadata.json`, `baseline_validation_comparison.csv`, `ml_feature_manifest.json`, `ml_tuning_results.csv`, `ml_cv_summary.csv`, `ml_validation_model_comparison.csv`, `n05_locked_models/`, `{val,test}_ml_predictions.parquet`, `validation_policy_comparison.csv`, `decision_manifest.json`, `final_test_policy_comparison.csv`, `final_test_row_level.parquet`, `final_test_run_metadata.json` |
| Alibaba files | Canonical: `role_occurrence.parquet`, `instance.parquet`, `rejected.parquet`, `metadata.json`, `count_report.md`, `SHA256SUMS`. Targets: `{train,validation,test}.parquet`, `metadata.json`, `SHA256SUMS`. Baselines: `history_statistics.parquet`, `validation_comparison.csv`, `baseline_selection.json`, `recommendations_{train,validation,test}.parquet`, `sensitivity_validation.csv`, `metadata.json`, `SHA256SUMS`. ML: `decision_manifest.json`, `model_selection.json`, `candidate_models.csv`, `validation_policy_comparison.csv`, `feature_order.json`, `cpu_model.joblib`, `memory_model.joblib`, `validation_ml_hybrid_predictions.parquet`, `metadata.json`, `SHA256SUMS`, `final_test_runs.jsonl` (written by the final test). Final test: `final_test_policy_comparison.csv`, `final_test_sensitivity.csv`, `final_test_predictions.parquet`, `run_record.json`, `metadata.json`, `SHA256SUMS` |
| Integrity | `scripts/build_alibaba_gpu_2020_canonical.py` — `verify_output` (L327), `publish` (L397), `build_info` (L163); `SHA256SUMS` in every Alibaba output folder |
| Google lock | `06_finalPolicyComparison.ipynb` cells 17 and 19 (manifest from a clean committed tree, input SHA-256, notebook code hash, refusal checks); `reports/results/google_subset/decision_manifest.json`, `final_test_run_metadata.json` |
| Committed results | `reports/results/google_subset/` (report, manifest, run metadata, five tables); `reports/results/alibaba_gpu_2020/` |
| Environment | `requirements-lock.txt` (Python 3.12, pandas 2.3.3, scikit-learn 1.9.1, xgboost 3.4.1, …) |
| Presentation | REST API and web frontend: no code yet; keep general |
| Design reference | Chapter 4, §4.4 |

---

## Check against the code

| # | Item | Finding | Effect on Chapter 5 |
|---|---|---|---|
| 1 | Section title 5.4 | Table of contents says "Hybrid Risk-Aware Recommender" | Retitle to "Hybrid Safeguard Recommender", matching §4.2.3 |
| 2 | Google peak computation | Sum within each aligned window only when every component is present, then maximum over windows; requests summed only when complete (Notebook 03 cells 6 and 10) | State precisely in 5.1.3 |
| 3 | Cold-start and fallback counts | Google computed (see 5.2.3). Fallback to Request and lack of usable history are the same rows, so they are counted once. Alibaba recomputed 30 Oct 2026 | Google counts in 5.2.3; Alibaba in Table 5.4 |
| 4 | Google `DummyRegressor` | `strategy="median"` | Use in 5.3.2 |
| 5 | Tests | 19 test files, 665 passing and 1 skipped (last run 29 Oct 2026). Alibaba 2018 and Azure tests exist for out-of-scope adapters | One coverage sentence in 5.5; file and test counts go to Chapter 6 |
| 6 | Alibaba ML, Hybrid, final test | Merged and run 30 Oct 2026 | Numbers and settings filled from the artifacts (`pending_checks_after_task7.md` Step 4) |
| 8 | Google locked decisions | Checked in `decision_manifest.json` `decisions`: P99, `baseline_min_runs = 1`, Random Forest for both resources with the settings above, Hybrid = max(ML, P95) with fallback to ML, `Hybrid_P99` supplementary | Take values from the manifest |
| 7 | Overlap with Chapter 4 | Chapter 4 explains why; Chapter 5 must say how and how much | Refer back to Chapter 4 sections instead of repeating rationale |
