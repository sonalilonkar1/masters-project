# Chapter 5. Project Implementation

This chapter describes how the design of Chapter 4 was implemented and what each stage produced on the two datasets; the reasons behind the design are given in Chapter 4, testing in Chapter 6 and evaluation results in Chapter 7. The two pipelines share their core code but are run differently. The Google ClusterData 2019 pipeline [Wilkes 2019] is a sequence of seven Jupyter notebooks, numbered 00 to 06, that call shared modules for splitting, feature preparation, the Hybrid rule and evaluation. The Alibaba GPU 2020 pipeline [Alibaba 2020] is a sequence of command-line scripts, one per stage, each of which verifies its inputs, builds its outputs in a staging folder and publishes them only when every check passes.

## 5.1 Data Pipeline

### 5.1.1 Ingestion, Unit Normalization, and Dataset Adapters

The Google input is the Kaggle sample of ClusterData 2019, a single CSV file of 405,894 rows and 34 columns, which Notebook 00 reviews without modifying it and Notebook 01 ingests. Notebook 01 parses the serialized request and usage dictionaries into CPU and memory columns prefixed `raw_req_`, `raw_avg_` and `raw_peak_`, so that every value can be traced to its source field, converts timestamps to integer microseconds, and turns three event times holding the maximum 64-bit integer, a sentinel rather than a time, into missing values. The request is absent on 774 rows (0.19%) and the peak memory on 1.21% of rows; no value is filled and no row is dropped. Resource values keep the publisher's normalized scale, labelled `ncu` for CPU and `normalized` for memory (Section 4.1.1).

The Alibaba trace consists of six tables: jobs, tasks, instances, sensor measurements (3,033,232 rows), group tags (1,055,032 rows) and machine specifications (1,897 rows). The source loader verifies each table against `config/alibaba_gpu_2020_sources.json`, which records its size, SHA-256 hash, number of data lines and header, and stops at the first mismatch. It reads each table with explicit column types and adds a source row number, so that every canonical and rejected row can be traced to a line of the original file.

The Alibaba adapter implements the multi-table path of the adapter framework (Section 4.1.3) in two phases. The preparation phase joins the tables and records the coverage of each join: 1,530 of the 1,055,501 jobs have no group tag, and 4,825,741 instances have no sensor row, which later becomes the main cause of exclusion. Times are converted from seconds to integer microseconds, and a value that is not a whole number of microseconds raises an error. The mapping phase applies the fourteen eligibility rules of Section 4.1.6 in their fixed order, records the first rule each ineligible role fails, and maps resource values to canonical fields without filling, clipping or summation: CPU in percent of one virtual CPU (`percent_of_vcpu`) and memory in gigabytes, both per instance. GPU fields are not evaluated as targets; the GPU request and GPU type are used as ML features (Section 5.3.1).

The adapter produces the `role_occurrence` view used for evaluation, an `instance` view and a rejected output. Every source row of the job, task and instance tables appears in exactly one of them, and the counts are reconciled at each level before publication (Table 5.1). Of the 1,254,108 accepted role occurrences, 461,900 (36.8%) are eligible. Most exclusions are caused by missing sensor data (287,780 roles), failed jobs (282,027), partial sensor coverage (97,018) and incomplete jobs (87,980). A further 1,224 eligible roles lack a usable CPU value and are evaluated for memory only.

**Table 5.1** Reconciliation of the Alibaba canonical build

| Level | Source rows | Accepted | Rejected (no submission time) |
|---|---|---|---|
| Job | 1,055,501 | 1,051,838 | 3,663 |
| Role occurrence | 1,261,050 | 1,254,108 | 6,942 |
| Instance | 7,522,002 | 7,410,783 | 111,219 |

The Google adapter implements the single-table path. It maps the occurrences produced by Notebooks 02 and 03 under the Google capability profile, which declares CPU and memory as peaks, permits the combined CPU-or-memory metric and records that Google targets are not split-isolated; an acceptance test confirms that its output equals the canonical view used by the notebooks, so no Google result changes.

Before writing, both adapters pass the same framework checks: every required field is present with its declared type, units belong to the allowed set, each request shares a unit with its usage, no split label, target or recommendation column is present, and, for Alibaba, every instance links to exactly one role. The Alibaba build refuses to run from a working tree with uncommitted changes unless explicitly allowed, and records the code commit in its metadata.

### 5.1.2 Execution Reconstruction and Dataset-Specific Temporal Features

A row of the Google sample is one usage window of one task instance on one machine. Notebook 02 groups the windows by collection and instance index and starts a new execution whenever the gap after a window exceeds the five-minute observation window; the smallest positive gap in the sample is 25 minutes, so the rule is unambiguous. The result is 253,585 executions, each with a recurrence key formed from the user and the job's logical name [Wilkes 2019]; the sample contains 2,280 keys, of which 1,504 recur. Notebook 03 combines executions that share a key and a start time into 4,879 occurrences, 3,307 of which contain more than one execution.

Notebook 03 then builds the point-in-time history: for each occurrence, the count, mean, standard deviation and 90th, 95th and 99th percentiles, by linear interpolation, of the CPU peaks, memory peaks and runtimes of earlier occurrences of the same key that had completed by its start. An independent recomputation confirms these values for all 4,879 occurrences. Notebook 04 applies the shared `chronological_split` function to the executions ordered by start time; boundaries fall only between groups of equal start time, so no occurrence is divided, and the occurrences split into 3,473 training, 675 validation and 731 test rows. The target of each occurrence is the CPU and memory peak of the next occurrence of its key. Because that occurrence may fall in a later split (Section 4.1.7), its start time is kept so that training rows can be selected by label period (Section 5.3.1).

On Alibaba, a job with a group tag receives a recurrence key formed from the group and the task role name, an occurrence identifier formed from the group and the job name, and a role key combining all three. A job without a group tag keeps a role key but no recurrence key, so it remains auditable but is excluded by the first eligibility rule.

The shared function `build_targets` adds the time-dependent fields to the eligible role occurrences. It applies the same `chronological_split` function to submission times, so that all roles of a job share a split, and streams the point-in-time history: within each recurrence, rows are processed in order of start time, and a priority queue ordered by end time releases a run into the history once it has completed. Histories are thus built in O(n log n) time without a copy per row, and CPU and memory histories are kept separately, so a missing CPU value never removes a run from the memory history. For each row and resource, the target is the value of the next eligible occurrence of the same recurrence if it lies in the same split; otherwise a status records the reason. Rows whose next occurrence was submitted in the same whole second are flagged and kept. Before writing, the function checks that a target value is present exactly when its status is `available` and that no occurrence spans two splits (Table 5.2).

**Table 5.2** Split sizes and next-occurrence targets

| | Train | Validation | Test |
|---|---|---|---|
| **Google** occurrences | 3,473 | 675 | 731 |
| CPU target available | 2,010 | 330 | 259 |
| Memory target available | 1,983 | 329 | 259 |
| **Alibaba** role occurrences | 323,329 | 69,286 | 69,285 |
| Next occurrence in the same split | 220,832 | 42,069 | 44,053 |
| CPU target available | 220,299 | 41,913 | 44,045 |
| Memory target available | 220,832 | 42,069 | 44,053 |
| Next occurrence in a later split (no target) | 8,842 | 7,736 | 0 |
| Same-second successors (flagged, kept) | 2,006 | 245 | 251 |

The remaining Alibaba rows without a target are the last runs of their recurrences. The same-second successors are analysed separately in the sensitivity results of Chapter 7.

### 5.1.3 Usage Aggregation and Resource Metrics

Because the executions of a Google occurrence run in parallel, Notebook 03 computes the occurrence peak in two steps (Section 4.1.4): it sums the maximum-usage values of the windows that share the same aligned start and end times, and takes the maximum of these sums. A sum or maximum is computed only when all of its inputs exist, because a partial sum would understate the peak without indicating it. CPU peaks are complete for all 4,879 occurrences and memory peaks are missing for 60; requests, summed under the same rule, are missing for 73. The largest occurrence, with 6,921 executions, has a combined CPU peak of 91.88 normalized units, far above that of any single execution.

On Alibaba, each instance has at most one sensor row, which gives its lifetime average CPU, average memory and peak memory. Each role value is the maximum over the role's instances, or missing if any of them lacks the value; values are never summed, because the evaluation unit is the role per instance. The trace contains no CPU peak, so the CPU peak field is left empty and the evaluator labels every Alibaba CPU result as average-usage sizing.

## 5.2 Baseline Recommenders

### 5.2.1 Request-As-Is

The Request policy copies the canonical request of each resource into its recommendation and is evaluated with every other policy on both datasets. On Alibaba it is marked as not selectable, so only the history-based candidates are ranked (Section 4.2.1). When it was still selectable during development, it ranked first on Alibaba validation with a memory violation rate of 4.74% against 5.58% for P99 at `min_runs = 10`, but at an average memory waste of 22.26 GB per row against 8.94 GB; its average memory utilization of 0.26 means that the typical request was about four times the next run's peak. As the Hybrid safeguard, it would also have prevented Hybrid from ever recommending less than the user's request.

### 5.2.2 Mean and Percentile Recommendations

On Google, the history statistics are those computed in Notebook 03. On Alibaba, the baseline module computes them from the same history stream as `build_targets`, so both stages apply one history rule. Each row's current history is materialized as an array, its mean and 90th, 95th and 99th percentiles are computed with NumPy's linear interpolation, and the array is discarded, which keeps memory bounded where retaining every history would require about 176 million values per resource. The module checks that the number of values used for each row equals the history count written by `build_targets`.

For each threshold `min_runs` in {1, 3, 5, 10} and each history policy, the recommendation for a resource is the history statistic when the row has at least `min_runs` earlier values and the request otherwise, and a flag records which case applies. Every candidate is scored on a fixed validation population (Section 5.5), 329 occurrences on Google and 42,069 role occurrences from 9,712 recurrences on Alibaba, and ranked by the dataset's lexicographic order (Section 4.2.1). The selected configurations are P99 at `min_runs = 1` on Google and P99 at `min_runs = 10` on Alibaba.

On Google, the selection is stored in the Notebook 04 metadata and copied into the decision manifest (Section 5.6). On Alibaba, the baseline script writes its selection record, `baseline_selection.json`, before it opens the test table, and then reads only an explicit list of test columns that excludes every target, target status and the same-second flag. It recomputes the history statistics with the test rows included and checks that the training and validation statistics are unchanged, which confirms that no test row enters an earlier history, and writes the recommendations of all five policies at the selected `min_runs` for every split, labelled with their units and CPU semantics.

### 5.2.3 Cold-Start Handling and Fallbacks

A row has a cold start when its workload has no earlier completed run; every history policy then falls back to the request, as it does when the row has fewer than `min_runs` earlier values, and CPU and memory fall back independently. A row that lacks usable history for a resource is therefore exactly a row whose recommendation for that resource is the request.

On Google, 1,801 of the 3,473 training occurrences (51.9%), 239 of the 675 validation occurrences and 240 of the 731 test occurrences are cold starts. Far fewer reach evaluation, because many belong to workloads that never recur and therefore have no target (Table 5.3). Some Google requests are missing, so a fallback does not always produce a value; the evaluator counts such rows as unknown, not as successes (Section 4.3), and they are the only rows on which Hybrid lacks its safeguard.

**Table 5.3** Source of the selected Google baseline (P99, `min_runs = 1`) on the evaluation populations

| | Train | Validation | Test |
|---|---|---|---|
| Evaluated occurrences | 1,983 | 329 | 259 |
| From history (CPU / memory) | 1,372 / 1,368 | 303 / 301 | 250 / 250 |
| Request fallback (CPU / memory) | 611 / 615 | 26 / 28 | 9 / 9 |
| No value: fallback with missing request (CPU / memory) | 7 / 9 | 1 / 1 | 0 / 0 |

On Alibaba, the share of validation rows that fall back to the request rises with the threshold, from 7.6% at `min_runs = 1` to 16.4% at 3, 20.3% at 5 and 25.7% at 10, equally for CPU and memory, while the median validation row has 31 earlier completed runs. Requests are present on every eligible Alibaba row, so every fallback produces a value (Table 5.4).

**Table 5.4** Source of the selected Alibaba baseline (P99, `min_runs = 10`)

| | Train | Validation | Test |
|---|---|---|---|
| Rows with at least one available target | 220,832 | 42,069 | 44,053 |
| From history (CPU / memory) | 134,097 / 134,239 | 31,243 / 31,251 | 33,006 / 33,017 |
| Request fallback (CPU / memory) | 86,735 / 86,593 | 10,826 / 10,818 | 11,047 / 11,036 |
| No safeguard value, so Hybrid uses ML alone (CPU / memory) | 0 / 0 | 0 / 0 | 0 / 0 |

## 5.3 Machine Learning Recommender

### 5.3.1 Feature and Target Preparation

The 24 Google features are defined once, in a fixed order, in the shared feature configuration. Five describe the occurrence at submission: its CPU and memory requests, its number of executions and the number of distinct CPU and memory requests among them. The other nineteen describe its history: the number of earlier completed occurrences and the count, mean, standard deviation and 90th, 95th and 99th percentiles of earlier CPU peaks, memory peaks and runtimes. The configuration also lists the columns that may never be features and the forbidden prefixes `target_`, `rec_` and `uses_history_`; an audit function checks the list against these rules and writes it to `ml_feature_manifest.json`. Missing values are passed to the models, and targets are trained as log(1 + y) and transformed back with exp(y) − 1, clipped at zero. The label-period rule (Section 4.2.2) keeps 1,672 CPU and 1,649 memory training rows for model selection, and 2,108 and 2,082 rows for the final refit.

The 25 Alibaba features are defined in a separate configuration: the per-instance CPU, memory and GPU requests, the number of instances, the GPU type requested by the task, the GPU type specification and workload label from the group-tag table, the CPU and memory history counts, and the mean and 90th, 95th and 99th percentiles of earlier CPU and memory values, each statistic with a missing-value indicator added before any value is filled. Targets, current-run measurements, split, exclusion and validity fields, the same-second flag and all identifiers are excluded, and the shared `validate_features` function checks every table against this list. The three categorical fields are one-hot encoded with a column for missing values, the remaining missing values are set to zero, and the resulting 43 columns are aligned across splits and saved in `feature_order.json`. Each resource's model is trained only on rows with an available target for that resource, on the original scale of the target.

### 5.3.2 Model Training and Selection

On Google, Notebook 05 tunes a decision tree, a random forest and XGBoost for each resource, each with a fixed random seed, over grids of 16, 27 and 32 configurations, 150 in total across the two resources, and records every result. Tuning uses scikit-learn's `GridSearchCV` with five time-ordered folds from the project's `purged_time_series_folds` function, which keeps rows with equal start times in the same fold and removes from each fold's training data every row whose target starts in or after the fold's validation period; the score is RMSE on the log scale. The best configuration of each family is also scored with `GroupKFold` grouped by recurrence key, as a check that is not used for any decision. A `DummyRegressor` with the median strategy is reported as a reference and is not selectable.

Each tuned candidate is fitted on the training-period rows and scored on the 329 validation occurrences, and the lowest log-scale RMSE selects the random forest for both resources, with 300 trees, the square root of the number of features per split, a minimum leaf size of 10 and a maximum depth of 10 for CPU and 6 for memory. Validation predictions for ML and Hybrid come from these models, and test predictions from the models refitted with the validation rows and saved with joblib; Notebook 05 drops every test target column when it loads the test occurrences.

**Table 5.5** Google ML validation comparison (329 occurrences; models fitted on training-period rows)

| Resource | Model | RMSE (log scale) | RMSE | MAE |
|---|---|---|---|---|
| CPU | Random forest (selected) | 0.850 | 9.559 | 2.824 |
| CPU | XGBoost | 0.860 | 9.600 | 2.851 |
| CPU | Decision tree | 0.891 | 9.686 | 2.852 |
| CPU | Median reference | 1.048 | 9.914 | 2.756 |
| Memory | Random forest (selected) | 0.387 | 1.255 | 0.454 |
| Memory | Decision tree | 0.421 | 1.313 | 0.488 |
| Memory | XGBoost | 0.439 | 1.306 | 0.528 |
| Memory | Median reference | 0.472 | 1.393 | 0.425 |

On Alibaba, the ML script, `run_alibaba_gpu_2020_ml.py`, verifies the checksums of the target and baseline folders and reads only the training and validation tables. Its candidates, each with one fixed configuration and a fixed random seed, are a constant predictor (`DummyRegressor` with the mean strategy), a decision tree, a random forest with 100 trees, histogram-based gradient boosting, and XGBoost with 300 trees of depth 6, a learning rate of 0.05 and row and column subsampling of 0.8. Every candidate is fitted on the training rows and scored on the validation rows of each resource, with predictions clipped at zero, by RMSE, MAE and R² and, through the shared evaluator, violation rate and average shortfall. Each resource's model is selected by validation RMSE, then MAE, with violation rate and average shortfall used only to break remaining ties; the constant predictor is recorded but excluded from selection. Histogram-based gradient boosting, with scikit-learn's default 100 iterations, learning rate of 0.1 and 31 leaves per tree, is selected for both resources (Table 5.6). The selected models are refitted on the training and validation rows and saved, while validation results for ML and Hybrid use the models fitted on training rows only; the selections and every candidate's results are written to `model_selection.json` and `candidate_models.csv`.

**Table 5.6** Alibaba ML validation comparison (models fitted on training rows; CPU in percent of one vCPU on 41,913 rows, memory in GB on 42,069 rows)

| Resource | Model | Settings | RMSE | MAE | Selected |
|---|---|---|---|---|---|
| CPU | Histogram gradient boosting | 100 iterations, learning rate 0.1, 31 leaves | 412.94 | 135.72 | Yes |
| CPU | XGBoost | 300 trees, depth 6, learning rate 0.05, subsampling 0.8 | 415.04 | 134.48 | |
| CPU | Random forest | 100 trees | 425.97 | 134.67 | |
| CPU | Decision tree | No depth limit | 519.17 | 167.49 | |
| CPU | Mean reference | Constant | 858.95 | 566.23 | Not selectable |
| Memory | Histogram gradient boosting | 100 iterations, learning rate 0.1, 31 leaves | 8.98 | 3.14 | Yes |
| Memory | XGBoost | 300 trees, depth 6, learning rate 0.05, subsampling 0.8 | 9.09 | 3.22 | |
| Memory | Random forest | 100 trees | 9.16 | 3.21 | |
| Memory | Decision tree | No depth limit | 10.34 | 3.62 | |
| Memory | Mean reference | Constant | 13.28 | 9.23 | Not selectable |

### 5.3.3 Validation-Based Model Comparison

On Google, tuning improved every model family over its starting configuration, and the random forest was the best tuned candidate for both resources on every accuracy measure (Table 5.5). The median reference has a lower MAE than every tuned model but a much higher log-scale error and RMSE: it predicts the typical occurrence well and fails on the large ones, which matter most for sizing. The grouped cross-validation gave similar mean errors to the time-ordered folds but a spread about five times larger (± 0.285 against ± 0.054 for CPU), so accuracy on unseen workloads depends strongly on which workloads are held out.

On Alibaba, the three ensemble models are within about 3% of one another in RMSE, and the decision tree without a depth limit is clearly the weakest learner (Table 5.6). Every model beats the constant predictor on MAE, and the selected models reach an R² of 0.76 for CPU and 0.53 for memory. The constant predictor nevertheless has the lowest violation rate of all candidates, 11.97% for CPU and 24.79% for memory against 41.91% and 47.76% for the selected models, because the mean of a heavy-tailed target lies above most of its values; a violation-first ranking would therefore have selected it (Section 4.2.2).

## 5.4 Hybrid Safeguard Recommender

The Hybrid rule of Section 4.2.3 is implemented once, in the shared function `hybrid_recommendation`, which returns the Hybrid recommendation for one resource together with a flag for rows whose safeguard is missing. It requires its two inputs to have the same shape and, when they are pandas Series, the same index, so that a prediction can never be paired with another row's safeguard, and it requires finite, non-negative predictions. The combination uses NumPy's `fmax`, which ignores a missing safeguard, so such a row receives the ML prediction.

On Google, Notebook 06 uses the P95 recommendation at `min_runs = 1` as the safeguard, which is missing on one validation row per resource and on no test row (Section 5.2.3), and also computes the supplementary `Hybrid_P99` variant, which is not used in any decision. The Alibaba ML script uses the locked recommendation of the selected baseline, P99 at `min_runs = 10`, joined to the validation rows by role key with a one-to-one check, and scores the five baselines, ML and Hybrid together on the 42,069 validation rows in `validation_policy_comparison.csv`. The number of rows on which Hybrid falls back to the ML prediction is recorded in the script's `metadata.json` and in the final-test run record; it is zero on both validation and test, because the safeguard falls back to the request, which every eligible row has (Table 5.4).

## 5.5 Shared Metrics and Evaluation Framework

The metrics of Section 4.3 are implemented as vectorized NumPy functions that return one value per row, or a missing value when either input is missing or not finite. A violation is one when the actual value exceeds the recommendation; the combined violation is one when either resource is violated, zero only when both are known and neither is violated, and missing otherwise. Utilization is capped at one and is missing when the recommendation is below 10⁻¹², and waste and shortfall are the positive parts of the difference between recommendation and actual value in each direction. No function fills or drops missing values.

The `RecommendationEvaluator` class applies these functions to a table of recommendations and targets. Its `evaluate` method returns row-level metrics without modifying its input, and `summarize` aggregates each metric over the rows on which it is defined, reporting every rate with its denominator. Constructed with a capability profile, the evaluator masks unsupported resources as unknown, computes the combined violation only where the profile permits it and labels CPU results as `average_usage` where the dataset has no CPU peak; `summary_metadata` returns these labels, the units and the reason for any suppressed metric. The evaluator contains no ranking or selection logic.

Each pipeline fixes its evaluation population before any policy is scored. On Google, it consists of the occurrences with both targets, 329 in validation and 259 in test; Notebook 04 confirms that every candidate is scored on the same occurrence identifiers, and Notebook 06 additionally scores a sensitivity population whose targets fall within the validation period (Section 4.1.7). On Alibaba, the function `freeze_common_validation_population` selects the 42,069 validation rows with at least one available target, reading only validation target statuses; memory is scored on all of them and CPU on the 41,913 with a CPU target. The Alibaba baseline script produces the sensitivity results of Section 4.3 on validation, namely same-second successors excluded and alone, multi-instance roles and equal weighting of recurrences, and the final-test script repeats them for all seven policies on the test set. The tests of this implementation are presented in Chapter 6.

## 5.6 Artifact Storage and Developer-Facing Outputs

Each stage writes its outputs to its own folder under `data/processed/`, and later stages read only from these folders (Table 5.7).

**Table 5.7** Main artifacts by stage

| Stage | Google (`google_subset_v1/`) | Alibaba |
|---|---|---|
| Canonical data | Observation table | `alibaba_gpu_v2020/`: three views, metadata, count report |
| Splits and targets | Occurrence tables per split | `alibaba_gpu_v2020_targets/` |
| Baselines | Validation comparison | `alibaba_gpu_v2020_baselines/`: selection record, locked recommendations |
| ML and decisions | Feature manifest, locked models, predictions, `decision_manifest.json` | `alibaba_gpu_v2020_ml/`: feature order, candidate comparison, locked models, `decision_manifest.json` |
| Final test | Policy comparison, row-level results, run record | `alibaba_gpu_v2020_final_test/`: policy comparison, sensitivity results, row-level predictions, run record |

Every Alibaba output folder contains a `SHA256SUMS` file, and each script re-hashes its input folders against these files before reading them. Outputs are written to a staging folder and installed by two renames, the previous output being restored if the second rename fails, so a destination always holds a complete output, and an existing output is replaced only when explicitly forced. A verification mode of the canonical build script lets a team member who downloads a shared build confirm that it matches the published one.

On Google, Notebook 06 freezes the decisions in `decision_manifest.json` together with the Git commit, a flag confirming a clean working tree, a hash of the notebook's code, the library versions and the SHA-256 hashes of thirteen inputs, including the split tables, ML predictions, locked models and the evaluator, metric and Hybrid source files. Before it reads any test target, the final-test cell checks that the manifest has final status, that the commit and notebook code match the frozen ones, that no other file has uncommitted changes and that every input hash matches, and it refuses to run if a final-test result already exists. It then scores the seven policies on the 259 test occurrences and writes a run record containing the hash of the manifest.

On Alibaba, the ML script writes its decision manifest after selection and refit, before the test table has been opened. It records the baseline selection and the hash of its record, the input checksums, the selected models with their hyperparameters and file hashes, the feature list and order, the Hybrid and clipping rules, the selection order, the random seed, the library versions, the result semantics and the code commit. The final-test script, `run_alibaba_gpu_2020_final_test.py`, opens the test table only after it has verified every input against the manifest, confirmed that the manifest was built from a clean working tree at the current commit and logged the run, and it refuses a second run for the same manifest whatever output folder is requested (Section 6.2). It then loads the locked models without refitting, scores the seven policies on the 44,053 test rows with at least one available target, and writes the comparison, the sensitivity results, row-level predictions and a run record.

Raw and processed data remain outside version control because of their size, while the final results of each dataset, including the decision manifests and run records, are committed under `reports/results/`, and all final runs use the locked environment of `requirements-lock.txt` (Table 3.1). The REST API serves the published recommendation and result files as JSON, organized by dataset, workload and policy and labelled with their units, and the web frontend presents them to developers; neither component runs a pipeline stage or modifies an artifact (Section 4.4).
