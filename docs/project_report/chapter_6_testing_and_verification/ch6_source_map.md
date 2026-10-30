# Chapter 6 Source Map: Testing and Verification

Purpose: identify what Chapter 6 can substantiate about implementation, correctness checks, validation, and final evaluation. This is a source map, not the chapter. Explain design in Chapter 4, implementation in Chapter 5, and comparative results in Chapter 7; Chapter 6 should explain verification methods and their limits.

Review basis: repository at `a85ddf80659419cf72ac751951842d57937f9cc8`, inspected 30 October 2026. Scope is the current Google ClusterData2019 Kaggle-subset pipeline and Alibaba GPU 2020 pipeline. Alibaba 2018, Azure, and older experiments are not evidence of completion of these pipelines. No implementation, test, notebook, or other report file was changed for this review.

Evidence conventions:

- Complete means the named implementation exists with relevant verification coverage in source. It does not mean that all tests or the full pipeline were rerun during this review. Partial identifies implementation or verification gaps; Missing identifies an absent component.
- Test references establish that checks are implemented. The attempted `python3 -m pytest -q -p no:cacheprovider` could not start because the active Python has no `pytest`. The previously recorded locked interpreter was unavailable. No current pass totals are asserted, and the prior source map's uncorroborated suite totals are removed.
- Notebook cells below use zero-based positions in the notebook JSON `cells` array, including Markdown cells, not execution counters. Saved outputs establish a recorded execution, not a fresh execution or authentication of every local artifact.
- Paths are relative to the repository root. Python references use `path:line` and name the function or test. JSON/CSV artifacts are identified by exact path and key/row because line positions depend on formatting.

## 6.1 Data and Pipeline Correctness Checks

### 1. Implementation status: Partial

Canonical validation and both dataset pipelines are implemented, with substantial unit/integration check coverage and saved data-validation evidence. Google canonical mapping exists in contract tests rather than a production thin adapter. Independent end-to-end Alibaba final verification and fresh-environment reproduction are not established as complete.

### 2. Verified implementation details

- Canonical validation checks identity, record levels, timestamps, units, resource semantics, validity, and profile-dependent fields. Adapter validation adds uniqueness, recurrence-key rules, rejection handling, and parent linkage.
- Google ingestion validates parsed resources/timestamps and observation identity. Reconstruction divides candidate instances into temporal episodes, creates execution identifiers, and constructs recurrence identities. Occurrence profiles aggregate aligned usage windows and requests, rather than substituting individual-execution maxima for workload totals.
- Google Notebook 03 independently recomputes historical statistics, occurrence peaks/runtime, and request totals, checks cold-start null statistics, and reloads saved artifacts for comparison.
- Alibaba verifies official source identity using checksums, size, line counts, and expected headers; joins source tables with key/linkage checks; builds accepted role/instance views and rejected records; and reports exclusions separately from resource validity.
- Alibaba role resource values are maxima across sensor-covered workers, never sums. A missing field on a covered worker makes that role field null. Missing observations are not silently turned into zero usage.
- The canonical build verifier checks manifest membership, file hashes, Parquet readability, row counts, and ordered columns. This is narrower than independently re-validating every semantic invariant of the whole final pipeline.

### 3. Supporting file paths and functions

| Source | Implemented responsibility |
|---|---|
| `src/canonical/schema.py:378`, `validate_canonical_frame`; `:574`, `validate_evaluator_view` | Canonical and evaluation contracts |
| `src/adapters/validation.py:189`, `validate_adapter_output`; `:283`, `validate_rejected_output`; `:402`, `validate_role_instance_linkage` | Adapter output and parent/child integrity |
| `src/sources/alibaba_gpu_2020.py:183`, `verify_table`; `:225`, `verify_sources`; `:343`, `load_table`; `config/alibaba_gpu_2020_sources.json` | Source verification and loading |
| `src/adapters/alibaba_gpu_2020.py:1121`, `prepare_sources`; `:1263`, `map_prepared_sources`; `:780`, `_aggregate_role_resources`; `:929`, `_assign_validity` | Alibaba mapping, aggregation, and validity |
| `scripts/build_alibaba_gpu_2020_canonical.py:196`, `reconciliation`; `:327`, `verify_output` | Count reconciliation and artifact verification |
| `pipelines/google_subset/00_dataQualityReview.ipynb`, cells 2 and 7; `pipelines/google_subset/01_dataIngestion.ipynb`, cells 3, 5, and 21 | Raw-data audit, ingestion checks, saved observation identity |
| `pipelines/google_subset/02_reconstructExecutions.ipynb`, cells 8, 13, 17, 18, 22, and 24 | Gap/episode analysis, execution reconstruction, recurrence construction, reload assertions |
| `pipelines/google_subset/03_buildProfilesAndMetrics.ipynb`, cells 6, 10, 26, 28, 30, 32, and 37 | Window/occurrence aggregation and independent recomputation |

### 4. Supporting tests and validation evidence

- `tests/test_canonical_schema.py`, `tests/test_adapter_contract.py`, and `tests/test_multiview_adapter_framework.py` implement schema/framework acceptance and rejection cases.
- `tests/test_google_canonical_contract.py:155`, `test_real_google_occurrence_artifact_fits_canonical_schema`, maps actual N04 artifacts to the schema; `:279`, `test_google_metadata_matches_canonical_contract`; `:325`, `test_google_target_nulls_match_global_final_occurrences`. This is a test-local mapping, not a separately implemented Google adapter. Artifact availability affects these checks; the first explicitly asserts that each split artifact exists.
- `tests/test_alibaba_gpu_2020_adapter.py:245` covers preserved row counts/order; `:1133` covers linkage; `:1287` covers exclusion reasons; `:1425` checks maximum rather than sum; `:1440` checks missing-field null propagation; `:1531` checks resource validity; `:1617` checks both canonical views. Also inspect `tests/test_alibaba_gpu_2020_loader.py` and `tests/test_build_alibaba_gpu_2020_canonical.py`.
- Saved Google Notebook 00 cell 7 records 405,894 raw rows and unique observation keys, with no duplicate observation keys. Notebook 01 cells 3 and 5 record validation and peak-versus-average checks. Notebook 02 cell 22 records 253,585 execution IDs with no missing execution IDs or recurrence keys.
- Saved Google Notebook 03 cell 26 records independent checks of 4,879 occurrences and 87,822 historical statistic values, including resource-specific counts and missing values. These are notebook output counts, not pytest totals.
- `reports/results/alibaba_gpu_2020/canonical/count_report.md` and `reports/results/alibaba_gpu_2020/canonical/metadata.json` preserve the build's counts, reconciliation, exclusions, and provenance. `reports/results/alibaba_gpu_2020/targets/metadata.json` preserves split/target counts and explains differences from pre-exclusion reference populations.
- The official full-data loader check is explicitly conditional: `tests/test_alibaba_gpu_2020_loader.py:415`, `test_real_tables_verify_and_load`, requires `TRACEADVISOR_FULL_DATA_TESTS=1` and downloaded official tables. Its current execution status was not established.

### 5. Dataset-specific differences

Google uses constructed recurrence identities and reconstructed workload occurrences from sampled usage windows. CPU is measured in NCU and memory in normalized units. Alibaba uses official group identity combined with task role, job-submission chronology, and lifetime sensor summaries; requests and measured maxima are scoped to an instance of a task role. CPU is percent of vCPU and memory is GB. Their aggregation levels and units prevent direct numerical comparison of waste or usage.

### 6. Missing evidence or unresolved issues

- A production Google thin adapter is missing in the inspected source. `docs/planning/github_issues/task13_google_subset_thin_adapter.md` describes planned work; it cannot establish completion.
- `docs/planning/github_issues/task8_alibaba_gpu_2020_final_verification.md` is a plan for an independent verification script/report and fresh-environment reproduction. Its checklist is not execution evidence. Its older statements that checksum tooling does not exist are superseded by the implemented build/runner verification functions.
- No fresh test results or full-data rebuild were obtained. Google local artifact hash differences are documented in 6.3 below.

### 7. Recommended content for the final report

Describe source audits, identity/row reconciliation, semantic schema validation, independent resource recomputation, and null handling. Attribute recorded outcomes to the saved notebooks/build artifacts. State the Google adapter and independent Alibaba verification gaps explicitly. Do not describe the REST API, frontend, or planning tasks as completed verification. Refer to Chapters 4 and 5 for design and implementation detail.

## 6.2 Temporal Leakage and Split Integrity

### 1. Implementation status: Partial

Chronological splits, point-in-time histories, feature restrictions, and final-test gates exist. Alibaba successor targets are split-isolated. Google validation targets cross into the test period, so strict test-period isolation cannot be claimed.

### 2. Verified implementation details

- The shared splitter deterministically sorts identifiers within timestamps, preserves complete timestamp groups, approximates 70/15/15 row fractions, checks disjoint identifiers, and requires strict start-time ordering across partitions. It does not guarantee that execution lifetimes cannot overlap across a boundary.
- Google histories require both predecessor start strictly earlier than current start and predecessor completion at or before current start. Simultaneous starts are combined into the occurrence modeling unit and cannot enter each other's histories.
- Alibaba histories follow deterministic recurrence/start/occurrence/role ordering. A heap releases only predecessors completed by the current submission time. The current row is yielded before insertion. A previously ordered zero-duration tied run can contribute to a later tied row; an overlapping unfinished run cannot. Histories may use eligible completed predecessors from earlier or current splits, independently for CPU and memory.
- Alibaba targets use the immediate eligible successor without skipping a successor whose resource is missing. Cross-split successors receive `next_occurrence_in_other_split` and null targets. Excluded rows receive no derived split/target values.
- Google builds global next-occurrence targets before assigning occurrence rows to splits. Its capability profile deliberately has `target_split_isolation: false`. Feature/label separation does not remove test-period outcomes already attached to validation rows.
- Google ML training uses target-start-time cutoffs, purged expanding time folds, and a feature manifest. The refit also applies a target-start cutoff. These controls do not repair test-period validation labels, and target-start cutoffs do not prove that a target execution's complete measurement was available by that cutoff.
- Alibaba baseline generation locks validation selection before reading an allow-list of test feature/request columns. Its ML selection runner never opens the test table. Final scoring verifies the lock before target access and logs an attempt before loading test rows.

### 3. Supporting file paths and functions

| Source | Check/control |
|---|---|
| `src/features/split_utils.py:8`, `chronological_split` | Timestamp-group boundaries, disjoint identifiers, chronology |
| `src/features/target_builder.py:161`, `iter_resource_history`; `:245`, `build_targets` | Completion-aware histories, immediate successors, status/value invariants, split isolation |
| `src/features/ml_prep.py:239`, `audit_occurrence_feature_manifest`; `:331`, `select_label_period_rows`; `:359`, `purged_time_series_folds`; `src/features/feature_config.py:179` | Google feature exclusions and temporal training-label checks |
| `scripts/run_alibaba_gpu_2020_baselines.py:67`, `TEST_ALLOWED_COLUMNS`; `:157`, `run`; `:258`, `assert_frame_equal` | Restricted test columns and invariance of earlier histories after adding test rows |
| `scripts/run_alibaba_gpu_2020_ml.py:117`, `run`; `src/features/alibaba_gpu_2020_ml_prep.py:126`, `build_feature_matrices` | Train/validation-only preparation and selection |
| `scripts/run_alibaba_gpu_2020_final_test.py:109`, `_verify_pr1_lock`; `:183`, `_check_pr1_build`; `:216`, `_append_run_log`; `:240`, `run` | Checksum/build verification, attempt logging, duplicate-run refusal, documented defect-rerun handling |
| `pipelines/google_subset/03_buildProfilesAndMetrics.ipynb`, cells 21, 22, and 26 | Strict earlier-start/completion history and independent oracle |
| `pipelines/google_subset/04_splitAndBaselines.ipynb`, cells 12, 13, 16, 22, and 26 | Split integrity, global successor construction, target chronology |
| `pipelines/google_subset/05_evaluateRecommendations.ipynb`, cells 10, 18, 28, and 30 | Training cutoff, purged CV, refit cutoff, test feature allow-list |
| `pipelines/google_subset/06_finalPolicyComparison.ipynb`, cells 15, 17, and 19 | Target-period sensitivity, frozen manifest, final-test gates |
| `config/dataset_capabilities.json` | Google isolation false versus Alibaba isolation true |

### 4. Supporting tests and validation evidence

- `tests/test_split_utils.py:137`, `test_shared_timestamps_are_not_split`, plus chronology and identifier-disjointness tests in the same file.
- `tests/test_target_builder.py:208` checks completion boundaries, overlap, nulls, and resource independence; `:233` checks cross-split history versus isolated targets; `:251` checks deterministic ties/zero-duration predecessors; `:313` compares to an independent brute-force oracle; `:353` checks that later-split measurements cannot change earlier features/targets.
- `tests/test_ml_prep.py:139` and `:154` check label-safe folds and timestamp groups. `tests/test_run_alibaba_gpu_2020_ml.py:67` instruments reads to verify that selection never reads test; `:175` checks refusal to replace an already tested lock.
- `tests/test_run_alibaba_gpu_2020_final_test.py:60`, `:67`, `:74`, and `:86` cover dirty/other-commit locks, pre-read logging, and refusal of a second run into a different output directory; `:104` covers logged defect reruns; `:288` covers the PR1-to-PR2 flow.
- Saved Google Notebook 06 cell 15 explicitly records **104 of 329 common validation occurrences** with successor targets starting in the test period. `reports/results/google_subset/tables/validation_policy_comparison_target_period_sensitivity.csv` evaluates the remaining **225** and labels every row `result_status: preliminary`.
- `reports/results/google_subset/decision_manifest.json` and `reports/results/google_subset/final_test_run_metadata.json` document a final freeze and recorded scoring run. The currently saved Notebook 06 cell 19 output says final evaluation was disabled for that saved notebook execution; the final-run claim therefore rests on the separate run metadata and result artifacts.
- `reports/results/alibaba_gpu_2020/ml/final_test_runs.jsonl` and `reports/results/alibaba_gpu_2020/final_test/run_record.json` document the recorded final attempt; the run record reports `prior_runs: 0` and no defect-rerun reason. These records support that recorded lock/run, not a universal guarantee that data were never accessed elsewhere.

### 5. Dataset-specific differences

Google forbids equal-start histories and allows successor labels across split boundaries. Alibaba permits deterministic completed zero-duration predecessors at tied submissions and isolates successor labels by split. Both support completed historical observations from earlier partitions; this is online historical context, not a frozen training-only history. Alibaba's test-target access restrictions are enforced by scripts; Google's final scoring controls live in notebooks.

### 6. Missing evidence or unresolved issues

The Google validation set contains test-period labels used in validation comparisons and model selection. Describe this as a test-period target leakage/test-isolation limitation, even though training features exclude future outcomes and the final scoring operation is gated. The preliminary 225-row sensitivity reports impact; it is not a replacement selection run, a repaired split, or proof of an uncontaminated final holdout. Training-label cutoffs based on target start also leave label-completion availability unverified. Full artifact authentication is limited by the hash differences in 6.3.

### 7. Recommended content for the final report

Explain split checks separately from history eligibility, target isolation, model-input exclusions, and final-run controls. State “104 of 329 common validation occurrences,” not 104 of 330. Present the 225-occurrence analysis as preliminary sensitivity evidence. Avoid claiming that all Google test-period information was excluded from selection or that chronological start ordering eliminates all lifetime overlap.

## 6.3 Model and Baseline Validation

### 1. Implementation status: Partial

Baseline, model, Hybrid, selection, refit, and final-scoring implementations and saved results exist for both datasets. Strict Google test isolation and authentication of the current local artifacts remain incomplete; fresh model/test reproduction was not performed.

### 2. Verified implementation details

- Both pipelines report Request, historical Mean, P90, P95, and P99, using a `min_runs` grid of 1, 3, 5, and 10 with request fallback when usable history is insufficient. History sufficiency is resource-specific.
- Google baseline selection ranks validation rows by combined violation, maximum and sum of resource violation rates, then waste and deterministic tie-breakers. Its selection pool copies the full comparison, including Request. Alibaba excludes Request from selectable policies and uses memory violation/waste before CPU violation/waste and deterministic tie-breakers.
- Google tunes decision tree, random forest, and XGBoost using purged time CV on log1p targets, records grouped-CV robustness results without using those for decisions, and selects per resource by validation log-scale RMSE with raw MAE tie-break. Its historical-median reference is a comparison floor. Locked selected models are refitted with the validation-end target-start cutoff.
- Alibaba records dummy mean, decision tree, random forest, histogram gradient boosting, and XGBoost. The dummy is a non-selectable floor. Candidates train on training rows with available resource targets; per-resource validation selection orders raw RMSE, MAE, violation, shortfall, and model name. Selected models are refitted on train plus validation. Validation policy metrics use train-only models, not refitted models. This is a fixed candidate comparison, not Google's hyperparameter-grid/purged-CV procedure.
- Hybrid is `max(ML, safeguard)` per resource, with ML fallback and a flag when the safeguard is missing. The shared function rejects non-finite/negative ML, infinite/negative safeguards, shape mismatch, and mismatched Series indices.
- Google Hybrid uses fixed P95 even though P99 is the selected baseline. `Hybrid_P99` is supplementary. Alibaba Hybrid uses the selected Task 6 baseline; the saved selection is P99 at `min_runs=10`.

### 3. Supporting file paths and functions

| Source | Responsibility |
|---|---|
| `src/baselines/alibaba_gpu_2020.py:103`, `_resource_statistics`; `:140`, `compute_history_statistics`; `:187`, `attach_history_statistics`; `:247`, `add_baseline_recommendations`; `:469`, `select_baseline` | Statistics, history-count consistency, fallback, selection |
| `src/models/alibaba_gpu_2020_candidates.py:14`, `build_candidate_models` | Fixed model candidates |
| `src/models/alibaba_gpu_2020_select.py:44`, `MODEL_SELECTION_ORDER`; `:53`, `NON_SELECTABLE_MODELS`; `:125`, `compare_and_select`; `:216`, `evaluate_validation_policies`; `:287`, `refit_on_train_plus_validation` | Per-resource model validation, Hybrid, and refit |
| `src/policies/hybrid.py:22`, `hybrid_recommendation` | Shared Hybrid rule and safeguards |
| `src/models/alibaba_gpu_2020_final_test.py:55`, `validate_locked_manifest`; `:91`, `prepare_locked_test_features`; `:280`, `evaluate_final_test` | Locked final evaluation |
| `pipelines/google_subset/04_splitAndBaselines.ipynb`, cells 37, 38, and 41 | Validation candidates, request invariance, baseline ranking |
| `pipelines/google_subset/05_evaluateRecommendations.ipynb`, cells 16, 18, 20, 22, 23, 28, and 33 | Grids, purged/grouped CV, validation models, selection, refit metadata |
| `pipelines/google_subset/06_finalPolicyComparison.ipynb`, cells 8, 10, 17, and 19 | P95 Hybrid, validation replay consistency, lock, final scoring |

### 4. Supporting tests and validation evidence

- `tests/test_alibaba_gpu_2020_baselines.py:52`, `:64`, `:110`, `:135`, `:196`, `:207`, and `:247` cover count agreement, mismatch rejection, fallback, resource independence, common population, ranking, and non-selectable Request. Runner coverage is in `tests/test_run_alibaba_gpu_2020_baselines.py`.
- `tests/test_hybrid.py:8`, `:15`, `:22`, `:45`, and `:50` cover max/fallback behavior, never-below-input property, invalid values, and index alignment. The violation monotonicity implication applies to matching actuals and comparable valid rows; missing safeguards can change denominators.
- `tests/test_alibaba_gpu_2020_candidates.py`, `tests/test_alibaba_gpu_2020_ml_prep.py`, `tests/test_alibaba_gpu_2020_select.py:65`, `:79`, `:97`, `:107`, and `:120` cover candidates, dummy exclusion, seven-policy comparison, and train-only/refit distinction. Final evaluation is covered by `tests/test_alibaba_gpu_2020_final_test.py` and `tests/test_run_alibaba_gpu_2020_final_test.py`.
- Google saved Notebook 06 cell 10 reports reproduction of N04 baseline validation metrics. Cell 8 records one missing-P95 fallback for CPU and one for memory on validation; do not attribute Alibaba's zero-fallback record to Google.
- Google saved selection/validation evidence: `reports/results/google_subset/n04_metadata.json`, `reports/results/google_subset/n05_ml_metadata.json`, `reports/results/google_subset/tables/ml_tuning_results.csv`, `reports/results/google_subset/tables/ml_cv_summary.csv`, `reports/results/google_subset/tables/ml_validation_model_comparison.csv`, and `reports/results/google_subset/tables/validation_policy_comparison.csv`. Metadata selects random forests for both resources; the final manifest locks P99, `min_runs=1`, and the fixed P95 Hybrid.
- Alibaba saved evidence: `reports/results/alibaba_gpu_2020/baselines/baseline_selection.json`, `reports/results/alibaba_gpu_2020/ml/candidate_models.csv`, `reports/results/alibaba_gpu_2020/ml/model_selection.json`, `reports/results/alibaba_gpu_2020/ml/metadata.json`, and `reports/results/alibaba_gpu_2020/ml/validation_policy_comparison.csv`. Model selection records histogram gradient boosting for both resources.
- Final evaluation evidence is separate from preliminary validation: `reports/results/google_subset/tables/final_test_policy_comparison.csv` and `reports/results/google_subset/final_test_run_metadata.json`; `reports/results/alibaba_gpu_2020/final_test/final_test_policy_comparison.csv` and `reports/results/alibaba_gpu_2020/final_test/run_record.json`. These record seven policies on 259 Google common occurrences and 44,053 Alibaba role occurrences, respectively.
- Preserved result cross-check: the saved Google final table has Hybrid any-resource violation 12.36% versus P95 17.37%; Alibaba's final table has Hybrid CPU/memory violation 3.77%/3.15% versus P99 6.45%/3.44% (rounded). These support a sanity check of the max rule, not a claim of fresh evaluation. Alibaba `reports/results/alibaba_gpu_2020/final_test/run_record.json` records zero safeguard-missing rows for each resource.

### 5. Dataset-specific differences

Google and Alibaba use different validation objectives, candidate procedures, target scales, feature preprocessing, and safeguards. Google occurrence features preserve NaNs (`src/features/ml_prep.py:312`, `build_occurrence_feature_matrix`). Alibaba adds missing-history indicators, one-hot encodes categories, fills numeric missing values with zero through `prepare_xy` (`src/features/ml_prep.py:27`), and aligns validation/test to the training schema (`src/features/alibaba_gpu_2020_ml_prep.py:126`). Model-input imputation is distinct from scoring-target eligibility and must not be described as zero-filling missing actual usage.

### 6. Missing evidence or unresolved issues

Google artifact reproducibility audit: SHA-256 was recomputed against `reports/results/google_subset/decision_manifest.json` during this review. The manifest itself hashes to `0669ca5c3cdec70a1013c886fbce4c0efc3746b936b7b0748f106523d40fa775`, matching the digest recorded in `reports/results/google_subset/final_test_run_metadata.json`.

| Current local path | Comparison to the committed final-run manifest |
|---|---|
| `data/processed/google_subset_v1/val_occurrences.parquet` | Mismatch |
| `data/processed/google_subset_v1/test_occurrences.parquet` | Mismatch |
| `data/processed/google_subset_v1/ml_metadata.json` | Mismatch |
| `data/processed/google_subset_v1/val_ml_predictions.parquet` | Mismatch |
| `data/processed/google_subset_v1/test_ml_predictions.parquet` | Mismatch |
| `data/processed/google_subset_v1/n05_locked_models/cpu_random_forest.joblib` | Mismatch |
| `data/processed/google_subset_v1/n05_locked_models/memory_random_forest.joblib` | Mismatch |
| `data/processed/google_subset_v1/metadata.json` | Match |
| `data/processed/google_subset_v1/baseline_validation_comparison.csv` | Match |
| `data/processed/google_subset_v1/ml_feature_manifest.json` | Match |
| `src/evaluation/evaluator.py`, `src/evaluation/metrics.py`, `src/policies/hybrid.py` | Each matches |

The mismatches prevent authenticating these current local artifacts as the exact frozen final-run inputs. They do not by themselves prove corruption, numerical disagreement, or an invalid original run. Regeneration, versions, and value-level equivalence need investigation; no such explanation was verified here. The gate in Google Notebook 06 cell 19 would reject mismatching frozen inputs. Do not rerun or retune the final test merely to replace this evidence.

The Google validation target leakage remains a model-selection limitation (6.2). Older notebooks under `notebooks/GoogleCluster2019/` and `notebooks/subset/` are preliminary/historical experiments, not substitutes for current pipeline validation. Alibaba Task 8 remains planned, and no new training, fresh-environment reproduction, or pytest run was completed in this review.

### 7. Recommended content for the final report

Explain validation-only selection as implemented, distinguish candidate tuning from selected-model refit and final scoring, and disclose the Google test-period selection limitation. Describe the two Hybrid safeguards explicitly. Use saved final tables as recorded outcomes with provenance qualifications; reserve comparative interpretation for Chapter 7. Do not state that current local files reproduce the frozen Google final run or that all verification tasks have passed.

## 6.4 Replay Evaluation Metrics

### 1. Implementation status: Partial

The shared replay evaluator and dataset-specific metric contracts are implemented with unit/contract tests. Independent verification of the complete saved evaluation and all exported denominator fields is incomplete.

### 2. Verified implementation details

The evaluator compares recorded next-occurrence actual values against policy recommendations, calculates row-level violations/utilization/waste/shortfall, and summarizes valid rows. This is offline resource replay; it is not a scheduler simulation or a measurement of runtime, latency, energy, or SLA outcomes. Optional capability profiles control supported resources, units, scope, combined-metric reporting, and CPU labeling. Profile metadata is returned separately from numeric summaries.

### 3. Supporting file paths and functions

- `src/evaluation/evaluator.py:84`, `evaluate`; `:302`, `summarize`; `:475`, `summary_metadata`; `:538`, `_validate_profile_view`; `:645`, `evaluate_canonical`.
- `src/evaluation/metrics.py:16` through `:222`: violation, combined violation, bounded utilization, waste, and shortfall functions.
- `config/dataset_capabilities.json`; `docs/evaluation/evaluation_metrics_v0.md`; `docs/evaluation/evaluation_output_format.md`; `docs/design/alibaba_gpu_2020_output_contract.md`. The executable code is authoritative where older prose differs.
- Google integration: `pipelines/google_subset/06_finalPolicyComparison.ipynb`, cell 10. Alibaba integration: `src/baselines/alibaba_gpu_2020.py:339`, `evaluate_policy`; `src/models/alibaba_gpu_2020_final_test.py:214`, `_score_policy`.

### 4. Supporting tests and validation evidence

`tests/test_evaluation.py` implements hand-computed formula/summary cases. `tests/test_evaluator_contract.py` implements profile, units, scopes, resource masking, missing-value, denominator, metadata, and input-preservation checks. Google Notebook 06 cell 10 records exact baseline-summary reproduction from N04. Saved validation/final CSVs in `reports/results/google_subset/tables/` and `reports/results/alibaba_gpu_2020/` demonstrate recorded outputs; individual metric evidence is mapped below. No fresh test execution is claimed.

### 5. Dataset-specific differences

Google uses `RecommendationEvaluator()` without a profile in Notebook 06 and evaluates occurrences with both targets. Alibaba uses its capability profile, evaluates rows with an available CPU or memory target, labels CPU `average_usage`, identifies memory as primary, and suppresses combined any-resource metrics. No GPU recommendation metric is implemented in this CPU/memory evaluator, despite Alibaba's dataset name.

### 6. Missing evidence or unresolved issues

Shared formulas do not make resource semantics, units, populations, or export fields identical. Profile-only waste/shortfall denominator fields are not universally exported. The Google leakage/hash limitations and uncompleted independent Alibaba verification constrain claims of fully verified evaluation.

### 7. Recommended content for the final report

Introduce offline replay, explain that common functions operate under different dataset contracts, and organize the metric checks under the three exact subheadings below. Refer to Chapter 4 for design/formulas and Chapter 7 for result interpretation.

### 6.4.1 Violation and Utilization

#### 1. Implementation status: Complete

Formula implementation and relevant test coverage exist; current test execution and complete artifact reproduction remain unverified.

#### 2. Verified implementation details

- CPU/memory violation is 1 when finite actual usage strictly exceeds a finite recommendation, 0 otherwise, and NaN if either input is non-finite. Equality is not a violation. A zero recommendation can still produce a valid violation.
- Combined violation is three-valued: 1 if either resource definitely violates, 0 if both are known non-violations, otherwise NaN. It is reported only when enabled and both resources are evaluated.
- Utilization is `min(actual / recommendation, 1)` for finite inputs and recommendation greater than epsilon (default `1e-12`); otherwise NaN. It is bounded above at 1; the metric function itself does not add a lower clamp. Canonical/profile validation supplies separate non-negative-resource checks.
- Summary violation rates are percentages. Mean utilization is a ratio, not a percentage or a ratio of aggregate resource totals.

#### 3. Supporting file paths and functions

`src/evaluation/metrics.py:16`, `cpu_violation`; `:42`, `memory_violation`; `:68`, `any_resource_violation`; `:118`, `bounded_utilization`; `:159`, `cpu_utilization`; `:174`, `memory_utilization`. Integration and reporting gates: `src/evaluation/evaluator.py:84`, `evaluate`; `:302`, `summarize`; `:475`, `summary_metadata`.

#### 4. Supporting tests and validation evidence

- `tests/test_evaluation.py:16` checks capped utilization; `:27` zero-recommendation NaN; `:50` equality; `:65`/`:79` CPU/memory violations; `:93`/`:102` valid zero-recommendation violations; `:265` non-finite inputs; `:285` unknown combined states.
- `tests/test_evaluator_contract.py:21` checks single-resource scoring; `:210` Alibaba combined-metric suppression; `:307` invalid units; `:334` scope mismatch; `:390` average-CPU labels.
- `reports/results/alibaba_gpu_2020/final_test/final_test_policy_comparison.csv` records `cpu_result_semantics: average_usage`, `primary_resource: memory`, and `any_resource_metric_reported: False`. Google `reports/results/google_subset/tables/final_test_policy_comparison.csv` contains combined violation and resource utilization fields.

#### 5. Dataset-specific differences

Google targets full-workload window-derived CPU/memory peaks, so it reports combined violation. Alibaba CPU is lifetime average, not a CPU peak or peak-safety guarantee; memory is lifetime peak at per-instance task-role scope. Alibaba's mixed semantics prohibit combined any-resource reporting. These are sizing indicators, not observed service-level violations.

#### 6. Missing evidence or unresolved issues

No current execution of the cited tests was obtained. Canonical checks must not be assumed for Google's unprofiled evaluator call merely because profile-aware validation exists. Saved final rates are recorded evidence with the provenance limits in 6.2–6.3.

#### 7. Recommended content for the final report

Describe hand-calculated equality, exceedance, zero, non-finite, and combined-unknown cases. Explain utilization capping/epsilon and the difference between percentage violation and ratio utilization. Qualify Alibaba CPU and suppress its combined metric consistently.

### 6.4.2 Resource Waste

#### 1. Implementation status: Complete

Waste and shortfall calculation and edge-case checks exist. Exported denominator coverage and full-run reproduction limitations are recorded separately.

#### 2. Verified implementation details

Waste is `max(recommendation - actual, 0)`; shortfall is `max(actual - recommendation, 0)`. Both return NaN if either input is non-finite. Summary means omit NaNs; there is no duration weighting, normalization by requests, cross-resource sum, or conversion to monetary cost. A finite zero recommendation gives valid waste/shortfall values even when utilization is undefined.

#### 3. Supporting file paths and functions

`src/evaluation/metrics.py:189`, `waste`; `:222`, `shortfall`; `src/evaluation/evaluator.py:84`, `evaluate`; `:302`, `summarize`. Policy integration: `pipelines/google_subset/06_finalPolicyComparison.ipynb`, cell 10; `src/models/alibaba_gpu_2020_select.py:216`, `evaluate_validation_policies`; `src/models/alibaba_gpu_2020_final_test.py:214`, `_score_policy`.

#### 4. Supporting tests and validation evidence

`tests/test_evaluation.py:156`, `test_waste`; `:167`, `test_shortfall`; `:222`, `test_evaluator_summary`. `tests/test_evaluator_contract.py:494` checks propagation of non-finite values; `:505` checks exclusion from summary means; `:749` checks valid-pair counts. Saved average waste/shortfall fields exist in `reports/results/google_subset/tables/final_test_policy_comparison.csv` and `reports/results/alibaba_gpu_2020/final_test/final_test_policy_comparison.csv`.

#### 5. Dataset-specific differences

Google waste uses NCU and normalized memory at full-workload scope. Alibaba uses percent of vCPU and GB at per-instance task-role scope, comparing CPU lifetime average and memory lifetime peak. Therefore neither CPU nor memory waste is directly comparable numerically across datasets; these fields are not resource-time integrals.

#### 6. Missing evidence or unresolved issues

These formulas do not establish measured cluster-wide capacity savings, energy savings, lower cost, or reduced execution time. Means can have policy/resource-specific valid populations. Explicit waste/shortfall counts exist in the profiled evaluator but are not preserved in all runner exports (6.4.3).

#### 7. Recommended content for the final report

Explain unused recommended capacity separately from unmet demand, verify positive/zero/NaN examples, and name the units/scope. Keep waste distinct from violation and avoid interpreting it as time-weighted operational savings.

### 6.4.3 Valid-Row Denominators and Missing-Value Handling

#### 1. Implementation status: Partial

Metric-specific eligibility and missing-value handling are implemented and tested in source. Explicit denominator export is incomplete across the two pipelines, and independent reconstruction of every saved denominator was not performed.

#### 2. Verified implementation details

- Violation denominators count known finite actual/recommendation pairs. Utilization denominators additionally require recommendation greater than epsilon. Zero or tiny recommendations may therefore contribute to violation, waste, and shortfall but not utilization.
- Unknowns remain NaN and are excluded from metric means. Empty valid populations produce NaN, not a zero score. Combined violation can be known from one definitely violating resource even if the other is unknown.
- `row_count` is the evaluated policy population, not a universal metric denominator. Each resource/policy can have a different valid count. Unsupported resources are masked before profiled scoring and have zero valid counts.
- `summarize` always supplies the evaluated resource violation/utilization counts; combined counts are omitted when combined reporting is suppressed. Explicit CPU/memory waste/shortfall counts are added only when a capability profile is present.
- Google selects a common population with both targets but does not require every policy recommendation to be present. Alibaba admits an available target in either resource and scores each resource on its own valid rows. Missing CPU does not discard a usable memory target.
- Missing-history preprocessing for ML is distinct from metric handling: Google's occurrence matrix preserves NaNs; Alibaba fills model-input values with zero plus missingness indicators. Neither rule authorizes replacing unavailable scoring targets with zero.

#### 3. Supporting file paths and functions

`src/evaluation/evaluator.py:59`, `_mask_unsupported_resources`; `:302`, `summarize`; `:475`, `summary_metadata`; `src/evaluation/metrics.py:68`, `any_resource_violation`; `:118`, `bounded_utilization`. Alibaba target status/value invariant: `src/features/target_builder.py:245`, `build_targets`; final population: `src/models/alibaba_gpu_2020_final_test.py:123`, `_final_population`. Export subsets: `src/models/alibaba_gpu_2020_select.py` `_VAL_SUMMARY_KEYS` and `src/models/alibaba_gpu_2020_final_test.py:214`, `_score_policy`. Google population/evaluation: `pipelines/google_subset/06_finalPolicyComparison.ipynb`, cells 6, 10, and 19.

#### 4. Supporting tests and validation evidence

- `tests/test_evaluation.py:299`, `test_summary_returns_valid_denominator_counts`; `:339`, `test_nonfinite_recommendation_is_not_counted_as_non_violation`.
- `tests/test_evaluator_contract.py:77` checks null single-resource columns; `:425` unsupported resources; `:505` non-finite waste/shortfall means; `:734` masking/count metadata; `:749` waste counts; `:771` legacy unprofiled numeric summaries.
- Google `reports/results/google_subset/tables/baseline_validation_comparison.csv` records 329 common validation occurrences, with Request violation denominators of 326. The three missing Request recommendations do not remove these rows from other policies. The final table records 259 common occurrences; Request has 257 valid CPU/memory violation pairs and 254 valid CPU utilization values.
- Alibaba `reports/results/alibaba_gpu_2020/ml/validation_policy_comparison.csv` records 42,069 rows, with 41,913 valid CPU and 42,069 valid memory violation pairs. Its final comparison records 44,053 rows, with 44,045 valid CPU and 44,053 valid memory violation pairs. These are inspected saved CSV values, not newly recomputed target populations.
- Inspect the CSV headers: the Google final summary does not export explicit waste/shortfall counts because it uses an unprofiled evaluator. Alibaba's final/model validation comparison exports select summary keys and also omits those explicit counts, although its profiled evaluator can calculate them.

#### 5. Dataset-specific differences

Google's common population requires both next-occurrence targets, but missing recommendations/zero allocations still produce different metric denominators. Alibaba's resource-specific eligibility retains memory evidence when CPU is missing. Combined denominators are meaningful for Google only under its three-valued rule; Alibaba suppresses combined metrics entirely. Profile support for counts must be distinguished from actual CSV export coverage.

#### 6. Missing evidence or unresolved issues

The CSVs alone do not expose every waste/shortfall denominator; use the corresponding frozen row-level outputs for a complete independent audit when available and authenticated. Current Google local artifacts cannot yet be treated as authenticated frozen inputs (6.3). No fresh full-data denominator audit or pytest execution was completed. The Table of Contents is compatible with the implementation, provided this subsection explains these differences rather than asserting identical cross-dataset eligibility or export fields.

#### 7. Recommended content for the final report

Explain why row counts, violation counts, utilization counts, and waste/shortfall counts differ. Use the saved examples with explicit provenance, preserve unknown outcomes, and distinguish unavailable measurements from numerical zero. State which denominators are actually exported and which require authenticated row-level reconstruction. Do not describe missing values as valid non-violations or claim complete independent denominator verification.
