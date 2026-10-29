# [P1] Task 7: Machine Learning, Hybrid Policies, and Final Test Evaluation

**Labels:** `area-implementation`, `priority-high`

**Owner:** Unassigned (suggested two-contributor split below)

**Priority:** Priority 1 · Required · Critical path (Alibaba GPU 2020 full pipeline)

---

## Objective

Complete the Alibaba GPU 2020 policy comparison under final-test discipline. Task 7 experiments with several regression model families for CPU and memory, selects each resource's model on validation, validates one fixed Hybrid rule, locks every decision in a decision manifest, and then performs the only final-test evaluation for all seven policies (Request, Mean, P90, P95, P99, the selected machine-learning model, and Hybrid).

The work runs in four phases, in this order:

1. **Candidate-model experiment and validation selection:** fit candidate models on train only and select the CPU and memory models independently on validation.
2. **Hybrid validation:** generate validation predictions from the selected models fitted on train only, and validate the fixed Hybrid rule with them.
3. **Lock and refit:** lock the selected models and the Hybrid rule, refit the selected models on train plus validation, save checksummed model artifacts, and write and commit the locked decision manifest.
4. **Final test:** after the manifest is locked, read the test targets for the first time, generate test predictions and recommendations, and score all seven policies (Request, Mean, P90, P95, P99, the selected machine-learning model, and Hybrid) exactly once.

The Phase 4 results are the only source of final Alibaba GPU 2020 numbers.

## What This Task Builds

- An Alibaba GPU 2020 feature configuration, separate from the Google configuration.
- A small, reproducible candidate-model experiment for CPU and memory.
- Independently selected CPU and memory models, refitted and saved as locked, checksummed artifacts.
- One fixed Hybrid rule, validated and locked.
- A committed, locked decision manifest.
- The single final-test evaluation of all seven policies (Request, Mean, P90, P95, P99, the selected machine-learning model, and Hybrid), with predictions, metrics, separate CPU and memory denominators, semantics labels and a run record.

## What This Task Does Not Build

- Baseline policies, history statistics or `min_runs` selection (Task 6).
- Splits, history counts or targets (Task 4).
- Evaluator or metric changes (Task 5).
- Artifact verification and reproduction (Task 8).
- Hybrid variants (Conservative, Balanced, Efficient); these require a separate issue.
- Classification models, including Naive Bayes.
- Any Google, Alibaba 2018 or Azure change.

## Current Project State

- **Existing ML code is Google v0 and notebook-based:**
  - `notebooks/subset/subset-05-ml-prediction.ipynb` trains `DecisionTreeRegressor`, `RandomForestRegressor` and `XGBRegressor` regressors, plus bucket classifiers (including Gaussian Naive Bayes) on binned targets.
  - `notebooks/subset/subset-06-final-recommender.ipynb` tunes Random Forest and XGBoost, selects by validation RMSE, and refits the selected models on the training split only.
  - The Hybrid rule in both notebooks is `max(ML prediction, baseline)` per resource.
  - Both notebooks call `build_aligned_matrices` and `get_available_features` with the test frame before model selection. Task 7 must not repeat this.
- **Shared ML helpers:** `src/features/ml_prep.py`:
  - `prepare_xy(df, feature_cols, target_col)` one-hot encodes categoricals and fills missing numeric values with 0;
  - `build_aligned_matrices(train_df, val_df, test_df, ...)` calls `prepare_xy` on the test frame and therefore reads the test target column;
  - `get_available_features(train_df, val_df, test_df, ...)` requires the test frame;
  - `validate_features(df, feature_cols, split_name, leaky_columns)` checks presence, leaky columns and merge artifacts.
- **Google feature configuration:** `src/features/feature_config.py` (`FEATURE_COLS`, `TARGET_CPU = "peak_cpu"`, `TARGET_MEM = "peak_mem_gb"`, `LEAKY_COLUMNS`). It contains Google v0 fields that Alibaba GPU 2020 does not produce (for example `hist_std_peak_cpu`, `hist_cv_cpu`, `hist_confidence_tier`, `hist_stability`). It is not reused for Alibaba GPU 2020.
- **Dependencies:** `requirements.txt` lists `scikit-learn>=1.4.0` and `xgboost>=2.0.0` (added with the Google Notebook 05 work) and uses minimum-version (`>=`) constraints. `xgboost` is not yet installed in the current local project environments. The interpreter currently used for `pytest` has no scikit-learn, and `pytest` is not in `requirements.txt`.
- **Google pipeline:** `pipelines/google_subset/05_evaluateRecommendations.ipynb` is the Google ML notebook (feature contract, tuning, model lock, refit and test predictions without scoring). It is Google-only and is not reused by this task.
- **Inputs from earlier tasks:**
  - Task 4 split tables (history counts, targets, target statuses).
  - Task 6 locked selection record (selected baseline and `min_runs`), recommendation tables for all five baseline policies at the selected `min_runs` for train, validation and test, and point-in-time history statistics.
  - Task 5 evaluator.

## Alibaba GPU 2020 Resource Semantics

- The CPU target is `actual_cpu`: the next occurrence's lifetime-average CPU usage in `percent_of_vcpu`.
- The memory target is `actual_memory`: the next occurrence's peak memory in `gb`.
- The CPU model predicts average CPU usage, not CPU peaks. `peak_cpu` is null for Alibaba GPU 2020 and is never used.
- CPU results are labeled average-usage sizing and are never described as peak-safe provisioning.
- Memory is the primary resource.
- GPU is not a target. GPU type may be a feature only if it is a canonical pre-execution field.
- P90, P95 and P99 are Task 6 baseline policies, not machine-learning models.
- Any-resource metrics are suppressed.

## Relationship to PR #70 and Tasks 1–6

| Item | Relationship |
|---|---|
| PR #70 follow-up | Provides the Alibaba GPU 2020 profile used by the evaluator. Not modified |
| Tasks 1–3 | Indirect, through the Task 4 tables. Task 3 provides the canonical pre-execution fields used as features |
| Task 4 | Provides history counts, targets and target statuses. Consumed, not modified |
| Task 5 | Scores every policy. Consumed, not modified |
| Task 6 | Provides the locked selection record (selected baseline and `min_runs`); recommendations for all five baseline policies at the selected `min_runs` for train, validation and test, with the selected baseline marked; and point-in-time history statistics used as ML features. Task 6 may read test request and feature columns to produce baseline recommendations, but it does not read test targets, test target statuses, test actual resource values or test evaluation results, and it never calls the evaluator on test rows. Consumed, not modified |

**How the baselines are used:** the selected Task 6 baseline is the Hybrid input. All five baseline policies are also scored separately on the final test, alongside the selected machine-learning model and Hybrid.

## Scope

- Dataset: Alibaba GPU 2020 only.
- Resources: CPU and memory, modeled and selected independently. Memory is the primary resource.
- Models: regression models only.

## Dependencies

- **Task 6** merged: locked selection record, baseline recommendations and history statistics.
- Transitively Tasks 3, 4 and 5.
- Feature-configuration work can start on the Task 4 tables while Task 6 finishes.

## Parallel Work

- Feature-configuration work can run alongside the end of Task 6.
- Task 8 verification tooling can be prepared alongside this task.
- PR 2 code can be developed and reviewed on fixtures before PR 1 merges.
- Phases 1–4 run in order on real data; Phase 4 does not start until PR 1 merges and the manifest is committed.

### Suggested Ownership (one task, two PRs)

- **Contributor 1 (PR 1):** feature configuration, leakage checks, CPU and memory candidate-model experiments, validation model selection, train-only validation predictions, refitting, and locked model artifacts.
- **Contributor 2 (PR 1 and PR 2):** Hybrid construction and validation, decision-manifest writing, final-test implementation, final-test run record, final evaluation tables, and candidate-model integration testing.
- **Dependencies between contributors:**
  - Hybrid validation on real data needs Contributor 1's train-only validation predictions. It can be built and tested earlier against fixture predictions with the same columns.
  - The manifest needs Contributor 1's selected models, refitted artifacts and checksums, and Contributor 2's Hybrid validation results. It is written last in PR 1.
  - Contributor 2 may develop final-test code on fixtures before PR 1 merges, but real final-test execution waits for the locked manifest from PR 1.

## Blocks

- **Task 8:** final verification starts only after the Phase 4 final test completes.

## Files in Scope

- New Alibaba GPU 2020 feature configuration beside `src/features/feature_config.py` (file name to confirm). `feature_config.py` itself is not modified.
- New Alibaba GPU 2020 ML, Hybrid, manifest and final-test code (location to confirm).
- New tests for the above.
- `src/features/ml_prep.py`: reused without modification. Only `prepare_xy` and `validate_features` are used in Phases 1–3; `build_aligned_matrices` and `get_available_features` are not used before Phase 4.
- `requirements.txt`: already lists `xgboost>=2.0.0`; not modified by this task unless a version change is required for reproducibility (Decision D-1).
- The committed decision manifest (location to confirm).

## Detailed Implementation Tasks

### Phase 1: Candidate-Model Experiment and Validation Selection

#### Features

- [ ] Define a separate Alibaba GPU 2020 feature configuration. Do not copy Google `FEATURE_COLS` entries that Tasks 3, 4 and 6 do not produce.
- [ ] Features may use only:
  - canonical pre-execution request fields (`requested_cpu`, `requested_memory`);
  - GPU type, only if it is available as a canonical pre-execution field (to confirm against the Task 3 output);
  - Task 4 history counts;
  - Task 6 point-in-time history statistics;
  - other pre-execution fields only if explicitly approved and recorded in the feature configuration.
- [ ] Never use as a feature:
  - `actual_cpu`, `actual_memory`;
  - `cpu_target_status`, `memory_target_status`;
  - current observed resource values (observed and peak CPU and memory of the current occurrence);
  - the current occurrence's `end_time_us`;
  - `split`, `exclusion_reason`;
  - CPU and memory validity-status columns;
  - same-second target flags;
  - any column derived from target or future-occurrence information.
- [ ] Pass this exclusion list as the `leaky_columns` argument to `validate_features` for the Alibaba GPU 2020 feature list.
- [ ] Missing features: add a missing-indicator column for each history statistic before zero fill, then apply `prepare_xy`'s zero fill, so zero and missing are distinguishable. Document both in the feature configuration.

#### Matrices and Feature Order

- [ ] Build train and validation matrices with `prepare_xy` only. Do not call `build_aligned_matrices` or `get_available_features` in Phases 1–3, because both take the test frame and `build_aligned_matrices` reads the test target column.
- [ ] Save the training feature-column list and the encoded feature order.
- [ ] Reindex validation matrices to the saved training order. Phase 4 reindexes test matrices to the same saved order.
- [ ] Phases 1–3 never read test targets, and PR 1 code never reads the test table.

#### Targets and Training Rows

- [ ] CPU model target: `actual_cpu`, trained only on rows with `cpu_target_status = available`.
- [ ] Memory model target: `actual_memory`, trained only on rows with `memory_target_status = available`.
- [ ] A row with an available memory target and an unavailable CPU target is used for memory training only. Missing CPU targets never remove rows from memory training.

#### Candidate Models

The best model is not known in advance. No model family is preselected; the final model per resource is chosen by validation performance, not by name.

| Candidate | Role | Starting hyperparameter grid (recorded in the manifest) |
|---|---|---|
| `DummyRegressor` | Sanity baseline; every selected model must be compared with it | `strategy` [`mean`, `median`] |
| `DecisionTreeRegressor` | Candidate | `max_depth` [6, 8, 12], `min_samples_leaf` [5, 10] |
| `RandomForestRegressor` | Candidate | `n_estimators` [100, 200], `max_depth` [10, 16], `min_samples_leaf` [5] (subset-06 grid) |
| `HistGradientBoostingRegressor` (or `GradientBoostingRegressor`) | Candidate | `max_iter` [100, 200], `learning_rate` [0.05, 0.1], `max_leaf_nodes` [31] |
| `XGBRegressor` | Optional candidate, only if Decision D-1 conditions are met | `n_estimators` [200, 400], `max_depth` [4, 6], `learning_rate` [0.05, 0.1] |

- [ ] Use one fixed random seed for every candidate that accepts one.
- [ ] **Naive Bayes is excluded.** It is a classification algorithm; using it would require binning continuous CPU and memory targets and would change the prediction problem from regression to classification.
- [ ] **Negative predictions:** gradient-boosting models and XGBoost can predict negative values. Apply one documented fixed rule to every candidate before evaluator use: negative predictions are clipped to 0, and the number of clipped predictions per model and resource is recorded. Decision Tree, Random Forest and Dummy predictions are averages of non-negative targets and are not affected.

#### Validation-Only Selection

- [ ] For each resource independently, fit every candidate configuration (family × hyperparameters) on train only and score it on validation only.
- [ ] Select the model family and hyperparameters per resource using validation only. No cross-validation search on train is used for selection; `TimeSeriesSplit` or `GroupKFold` on train may be reported as diagnostics only.
- [ ] Primary consideration: under-provisioning behavior, measured with the Task 5 evaluator on the ML-only recommendation (Decision D-2 gives the full order).
- [ ] Supporting metrics: RMSE and MAE.
- [ ] Interpret and report memory first, because memory is the primary Alibaba GPU 2020 resource.
- [ ] Report every candidate's validation results, including `DummyRegressor`.
- [ ] Record the selected model family, hyperparameters, feature list, feature order, training row count, random seed and library versions per resource.

### Phase 2: Hybrid Validation

- [ ] Generate validation predictions from the selected models **fitted on train only**. Never use validation predictions from refitted models, because those predictions are in-sample.
- [ ] Use one fixed Hybrid rule, constructed separately for CPU and memory:

  ```text
  Hybrid recommendation (per resource) = max(ML prediction, selected Task 6 baseline recommendation)
  ```

- [ ] The selected baseline is the policy marked in the Task 6 recommendation tables, at the selected `min_runs`.
- [ ] The rule has no tunable parameters and no variants. Future Hybrid variants require a separate issue.
- [ ] Score the selected ML-only policy and Hybrid on validation with the Task 5 evaluator, on the Task 6 common validation population, alongside all five Task 6 baseline policies at the selected `min_runs`, so the validation tables cover all seven policies (Request, Mean, P90, P95, P99, the selected machine-learning model, and Hybrid).

### Phase 3: Lock, Refit and Decision Manifest

- [ ] Lock the selected models (family and hyperparameters per resource) and the Hybrid rule.
- [ ] Refit the selected models on train plus validation, using rows with available targets. Validation targets are split-isolated, so no test-period outcome enters the refit.
- [ ] Save the refitted models as locked artifacts (`joblib`; Decision D-5) with the saved training column list and order, hyperparameters, training row counts per resource, random seeds, library versions and a SHA-256 checksum per artifact.
- [ ] Save the train-only selected models' validation predictions.
- [ ] Write one locked decision manifest **before any test target or target status is read and before the evaluator is called on test rows**, containing:
  - the Task 6 selection record reference and checksum;
  - the selected baseline and `min_runs`;
  - the feature list and saved training column order;
  - the selected model family per resource;
  - hyperparameters per resource;
  - model artifact paths and checksums;
  - the Hybrid rule;
  - the negative-prediction rule;
  - the evaluation population rule;
  - the dataset profile;
  - random seeds;
  - library versions, including the XGBoost version if used;
  - the code commit;
  - the lock timestamp.
- [ ] Commit the manifest, or store it as a versioned artifact, before final-test execution. It is read-only after it is written.

### Phase 4: Final Test

- [ ] Verify the manifest checksum. Phase 4 reads the manifest without modifying it.
- [ ] Load the test target and evaluation columns for the first time. Task 6 may already have produced test recommendations, but it must not have loaded test targets or called the evaluator on test rows.
- [ ] Reindex test features to the saved training column order.
- [ ] Generate ML test predictions with the refitted locked models, apply the negative-prediction rule, and generate Hybrid test recommendations with the locked rule and the selected Task 6 baseline.
- [ ] Use the Task 6 test recommendations for Request, Mean, P90, P95 and P99.
- [ ] Freeze the test evaluation population with the same rule as validation.
- [ ] Call the Task 5 evaluator on test rows exactly once for all seven policies (Request, Mean, P90, P95, P99, the selected machine-learning model, and Hybrid), with the Alibaba GPU 2020 profile.
- [ ] Record metrics, separate CPU and memory denominators, the average-usage CPU label, memory-primary metadata and confirmation that any-resource metrics were suppressed.
- [ ] Report same-second, multi-instance and group-weighted sensitivity for the test results, using the methods fixed in Task 6.
- [ ] No change to models, features, the Hybrid rule, the baseline policy or `min_runs` is allowed after test results are seen.
- [ ] Write a final-test run record keyed by the manifest checksum and the code commit. A second run with the same manifest checksum and code commit is refused.
- [ ] A rerun is allowed only for a documented code defect and requires a new corrective code commit; the manifest and every locked decision stay unchanged. The rerun gets a new run ID, the original outputs are preserved and never overwritten, and the defect, the fix and both result sets are recorded in the final metadata (Decision D-6).

### Outputs

**Prediction format (both PRs):** one row per (`role_key`, `policy_name`) for all seven policies (Request, Mean, P90, P95, P99, the selected machine-learning model, and Hybrid), using the canonical evaluator names `dataset_id`, `workload_id`, `policy_name`, `actual_cpu`, `actual_memory`, `recommended_cpu`, `recommended_memory`, with unit columns. ML-only rows hold the ML predictions after the negative-prediction rule; Hybrid rows also keep both inputs (ML prediction and selected baseline recommendation) in separate columns (names to confirm).

**PR 1 outputs (Phases 1–3; the test table is never read):**

- [ ] **Validation predictions:** ML-only and Hybrid validation predictions, from the train-only models.
- [ ] **Candidate-experiment table:** every candidate configuration per resource with validation metrics, including `DummyRegressor`.
- [ ] **Validation evaluation tables:** all seven policies, memory first.
- [ ] **Selected models:** the selected CPU and memory model per resource.
- [ ] **Locked decision manifest** and its checksum.
- [ ] **Model artifacts:** the locked CPU and memory models refitted on train plus validation, with checksums and metadata.

**PR 2 outputs (Phase 4; after the manifest is locked):**

- [ ] **Test predictions:** ML-only and Hybrid test predictions, from the refitted locked models.
- [ ] **Final-test evaluation tables:** all seven policies, memory first.
- [ ] **Sensitivity results:** same-second, multi-instance and group-weighted.
- [ ] **Final-test metadata:** population size, denominators, labels, run ID, run timestamp, manifest checksum and code commit.
- [ ] **Final-test run record**, keyed by manifest checksum and code commit, including any documented reruns.

## Required Tests

### Leakage and Test-Data Boundary

- [ ] Feature leakage: no entry from the exclusion list appears in the feature matrix, and `validate_features` rejects it if added.
- [ ] Target and target-status columns are excluded from features.
- [ ] Current observed values, the current `end_time_us`, same-second flags, `split`, `exclusion_reason` and validity-status columns are excluded from features.
- [ ] No test target or target-status column is accessed before Phase 4 (asserted by giving Phases 1–3 no test frame and checking that the Phase 4 entry point is the only reader of test target columns).
- [ ] Phases 1–3 never call `build_aligned_matrices` or `get_available_features`.
- [ ] The saved feature-column order is reused, and test features are reindexed to it.

### Training Rows and Models

- [ ] Training rows per resource are exactly those with an available target.
- [ ] Missing CPU targets do not remove rows from memory training.
- [ ] Each supported regression family (Dummy, Decision Tree, Random Forest, the chosen gradient-boosting family, and XGBoost if included) trains and predicts on a fixture.
- [ ] CPU and memory models are selected independently.
- [ ] Hyperparameters are selected on validation only.
- [ ] The `DummyRegressor` comparison is reported for both resources.
- [ ] The negative-prediction rule is applied and its count recorded.
- [ ] If XGBoost is included: installation from `requirements.txt` succeeds in a clean environment, and an XGBoost model reloads and reproduces its predictions.

### Hybrid and Manifest

- [ ] Hybrid validation uses predictions from models fitted on train only.
- [ ] The Hybrid recommendation equals `max(ML prediction, selected Task 6 baseline recommendation)` per resource.
- [ ] No Hybrid variant exists.
- [ ] The final-test step refuses to run if the manifest is missing or its checksum does not match.
- [ ] Locked models reload and reproduce their saved predictions.

### Final Test and Evaluation Contract

- [ ] Final-test outputs contain exactly seven policies (Request, Mean, P90, P95, P99, the selected machine-learning model, and Hybrid).
- [ ] Evaluator output contains no any-resource metric.
- [ ] CPU results carry the average-usage label.
- [ ] Memory-primary metadata is present.
- [ ] CPU and memory denominators are reported separately.
- [ ] A second final-test run with the same manifest checksum and code commit is refused.
- [ ] A documented defect rerun with a new code commit and an unchanged manifest gets a new run ID and does not overwrite the original outputs.
- [ ] A rerun is refused if the manifest checksum differs from the locked manifest.

### Regression and Environment

- [ ] The Google configuration in `src/features/feature_config.py` and existing tests are unchanged.
- [ ] Tests run in an environment created from `requirements.txt` plus `pytest`.

## Acceptance Criteria

1. Candidate models (Dummy, Decision Tree, Random Forest, a gradient-boosting family, and XGBoost only if Decision D-1 conditions are met) are trained on train only, and the CPU and memory models are selected independently by validation performance, not by model name.
2. Naive Bayes and other classification models are not used.
3. PR 1 never reads the test table, and no task reads test targets or target statuses before the manifest is locked.
4. The fixed Hybrid rule `max(ML prediction, selected Task 6 baseline recommendation)` is validated with train-only predictions, locked before test targets are read, and used unchanged on test.
5. Selected models are refitted on train plus validation and saved as checksummed locked artifacts.
6. The decision manifest is committed before the final test and is unchanged afterwards.
7. Task 7 performs the only final-test evaluation, which runs exactly once for all seven policies (Request, Mean, P90, P95, P99, the selected machine-learning model, and Hybrid) and is the only source of final Alibaba GPU 2020 numbers.
8. Memory is reported first; CPU is labeled average-usage sizing and is never described as peak-safe provisioning; no GPU or any-resource metric appears.
9. CPU and memory denominators are reported separately in every table.
10. If XGBoost is included, its version is recorded and its installation, reload and reproducibility tests pass; otherwise the exclusion is documented as a limitation.

## Expected Outputs

- Alibaba GPU 2020 feature configuration and saved training column order.
- Candidate-model experiment code and the candidate-experiment table (location to confirm).
- Train-only selected models' validation predictions.
- Refitted, checksummed locked model artifacts.
- The committed decision manifest.
- Validation evaluation tables for all seven policies.
- Final-test prediction and evaluation tables for all seven policies (Request, Mean, P90, P95, P99, the selected machine-learning model, and Hybrid), with sensitivity outputs.
- Final-test run record and metadata.
- No `requirements.txt` change is expected; `xgboost>=2.0.0` is already listed.

## Data Leakage Controls

- Features use only canonical pre-execution fields, Task 4 history counts and Task 6 point-in-time history statistics.
- Targets, target statuses, current observed values, the current end time, same-second flags, `split`, exclusion and validity columns are excluded from features.
- Phases 1–3 do not read test targets and do not use helpers that take the test frame.
- Task 6 reads test request and feature columns only. Task 7 Phase 4 reads test target and target-status columns for the first time, after the manifest is locked.
- Model and hyperparameter selection uses validation only.
- Hybrid validation uses train-only models, so validation predictions are never in-sample.
- The refit uses train and validation only; split-isolated targets keep test-period outcomes out.
- Task 7 calls the evaluator on test rows exactly once for all seven policies.
- The manifest lock, the run record and the no-overwrite rerun rule prevent post-test tuning and silent replacement of results.

## Schema and Adapter Boundaries

- Reads canonical, Task 4 and Task 6 columns only; writes evaluator outputs with canonical names.
- No change to the schema, profiles, adapters, target builder, baselines or evaluator.

## Unresolved Decisions

| ID | Decision | Recommendation |
|---|---|---|
| D-1 | Whether XGBoost is a candidate | Optional. Include it only if it is reproducibly installable. `requirements.txt` already lists `xgboost>=2.0.0`; record the installed version in the manifest, and test installation, reload and reproducibility. Negative predictions use the fixed clipping rule. If it cannot be supported within the project timeline, exclude it and document the exclusion as a limitation |
| D-2 | Validation selection order per resource | Primary: under-provisioning on the ML-only recommendation (`{resource}_violation_pct`, then `average_{resource}_shortfall`, from the Task 5 evaluator). Supporting: RMSE, then MAE. Final tie-break: model family name, then hyperparameters. Memory results are interpreted first |
| D-3 | Missing feature handling | Decided: zero fill plus a missing indicator per history statistic |
| D-4 | Hybrid rule | Decided: one fixed rule, `max(ML prediction, selected Task 6 baseline recommendation)` per resource. Variants require a separate issue |
| D-5 | Model artifact format and location | `joblib` (installed with scikit-learn); location to confirm |
| D-6 | Rerun procedure after a real defect | A second run with the same manifest checksum and code commit is refused. A documented defect rerun requires a new corrective code commit; the manifest and locked decisions stay unchanged. The run record is keyed by manifest checksum and code commit; the rerun gets a new run ID; original outputs are preserved; the defect, the fix and both result sets are recorded |
| D-7 | Gradient-boosting family | `HistGradientBoostingRegressor` by default; `GradientBoostingRegressor` only if the histogram-based model cannot be used |
| D-8 | Negative-prediction rule | Clip negative predictions to 0 before evaluator use, for every candidate; record the count |

## Risks

- Short histories may limit ML gains over the Task 6 baselines; the `DummyRegressor` comparison shows whether any model learns a useful signal.
- Violation-first selection can favor models that over-predict; shortfall, RMSE, MAE and waste must be reported alongside.
- The candidate grid multiplies training time across two resources; grids are kept small.
- XGBoost is a native dependency listed in `requirements.txt` but not yet installed in the current local environments; it may be excluded if installation or reproducibility cannot be confirmed.
- The interpreter currently used for `pytest` has no scikit-learn, and `pytest` is not in `requirements.txt`; Task 7 tests fail until the test environment is built from `requirements.txt` plus `pytest`.
- Reusing `ml_prep.py` helpers that take the test frame would leak test targets; only `prepare_xy` and `validate_features` are used before Phase 4.
- Refitting on train plus validation means the test model is not the exact model that was validated; this is intended and recorded.
- Average CPU sizing is not peak-safe and must be labeled everywhere.

## Pull-Request Boundary

Two PRs:

1. **PR 1:** feature configuration, leakage checks, candidate regression models, CPU and memory model selection, Hybrid construction and validation, refitting on train plus validation, and tests. No `requirements.txt` change is expected, because `xgboost>=2.0.0` is already listed. PR 1 code never reads the test table. PR 1 produces only:
   - validation ML and Hybrid predictions (from train-only models);
   - the candidate-experiment table;
   - validation evaluation tables;
   - the selected models;
   - the locked decision manifest;
   - locked model artifacts and their checksums.
2. **PR 2:** final-test execution and tests only. PR 2 code may be developed and reviewed using fixtures before PR 1 merges. Real final-test execution waits until PR 1 merges and the manifest is committed. PR 2 produces only:
   - test ML and Hybrid predictions;
   - final-test evaluation tables;
   - sensitivity results;
   - final-test metadata;
   - the final-test run record.

   PR 2:
   - reads the manifest without modifying it;
   - does not tune or retrain models;
   - does not change the Hybrid rule, baseline policy or `min_runs`;
   - performs the only final-test scoring;
   - refuses a second run with the same manifest checksum and code commit;
   - for a documented defect rerun, requires a new corrective code commit with the manifest unchanged, assigns a new run ID and never overwrites original outputs.

No baseline, evaluator, target-builder, adapter or Google code in either PR.

## Handoff

- **Task 8, from PR 1:**
  - the committed decision manifest and its checksum;
  - locked model artifacts and their checksums;
  - the feature configuration and the saved training feature-column order;
  - references and checksums for the Task 6 baseline recommendations used;
  - the candidate-experiment table;
  - ML-only and Hybrid validation predictions from train-only models;
  - validation evaluation tables for all seven policies;
  - code commit, library versions, random seeds and environment information.
- **Task 8, from PR 2:**
  - ML-only and Hybrid test predictions from the refitted locked models;
  - final-test evaluation tables for all seven policies (Request, Mean, P90, P95, P99, the selected machine-learning model, and Hybrid);
  - separate CPU and memory denominators, the average-usage CPU label, memory-primary metadata and confirmation that any-resource metrics were suppressed;
  - same-second, multi-instance and group-weighted sensitivity results;
  - the final-test run record (keyed by manifest checksum and code commit) and any documented reruns;
  - final-test metadata.
- **Task 12:** verified final Alibaba GPU 2020 results, after Task 8.

## Not in This Issue

- Baseline policies, history statistics and `min_runs` selection (Task 6).
- Splits, history counts and targets (Task 4).
- Evaluator changes (Task 5).
- Artifact verification and reproduction (Task 8).
- Hybrid variants (separate future issue).
- Naive Bayes and other classification models.
- Google ML, Hybrid or final evaluation (Task 10).
- Alibaba 2018 (Task 9) or Azure (Task 11) work.
- GPU-resource targets or evaluation (out of scope).

## References

- `notebooks/subset/subset-05-ml-prediction.ipynb` (regression models, bucket classifiers, Hybrid rule)
- `notebooks/subset/subset-06-final-recommender.ipynb` (tuning grids, validation selection, refit)
- `src/features/ml_prep.py` (`prepare_xy`, `build_aligned_matrices`, `get_available_features`, `validate_features`)
- `src/features/feature_config.py`
- `requirements.txt`, `pytest.ini`
- `docs/planning/github_issues/task6_baselines_and_min_runs.md`
- `docs/design/canonical_workload_schema.md` §11, §12, §13
- `docs/data/alibaba_gpu_2020_evidence_and_limitations.md` §5
- `docs/planning/data_integration_tasks.md` Task 4 and Task 7 (earlier numbering)
- Note: no Task 4 or Task 5 issue file currently exists in `docs/planning/`; the Task 5 evaluator issue should be referenced from wherever it now lives.
