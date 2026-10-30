# Chapter 5. Project Implementation

This chapter describes how the design of Chapter 4 was implemented and what each stage produced on the two datasets. Each section names the components that realize a design decision and reports the measured outputs on which later chapters rely; the reasons behind the design are given in Chapter 4 and are not repeated. Testing is described in Chapter 6 and evaluation results in Chapter 7.

The two pipelines share their core code but are run differently. The Google ClusterData 2019 pipeline [Wilkes 2019] is a sequence of seven Jupyter notebooks, numbered 00 to 06, that call shared modules for splitting, feature preparation, the Hybrid rule and evaluation. The Alibaba GPU 2020 pipeline [Alibaba 2020] is a sequence of command-line scripts, one per stage, each of which verifies its inputs, builds its outputs in a staging folder and publishes them only when every check passes. Values from the Alibaba ML and Hybrid stages, which were produced last, are marked *pending* in the tables of this chapter and are added from the final artifacts.

## 5.1 Data Pipeline

### 5.1.1 Ingestion, Unit Normalization, and Dataset Adapters

The Google input is the Kaggle sample of ClusterData 2019, a single CSV file of 405,894 rows and 34 columns. Notebook 00 reviews its quality without modifying it, and Notebook 01 ingests it. The request and usage fields are stored as serialized dictionaries, which Notebook 01 parses into CPU and memory columns prefixed `raw_req_`, `raw_avg_` and `raw_peak_`, so that every later value can be traced to its source field. Timestamps are converted to integer microseconds, and three event times that hold the maximum 64-bit integer, a sentinel rather than a time, become missing values. The request is absent on 774 rows (0.19%) and the peak memory on 1.21% of rows; these values remain missing, and no row is dropped. Resource values keep the publisher's normalized scale, labelled `ncu` for CPU and `normalized` for memory, because the normalization constants are not published (Section 4.1.1).

The Alibaba trace consists of six tables: jobs, tasks, instances, sensor measurements (3,033,232 rows), group tags (1,055,032 rows) and machine specifications (1,897 rows). The source loader verifies each table against a committed configuration file, `config/alibaba_gpu_2020_sources.json`, which records its size, SHA-256 hash, number of data lines and expected header, and stops at the first mismatch. It reads each table with explicit column types and adds a source row number that later stages carry forward, so that every canonical and rejected row can be traced to a line of the original file.

The Alibaba adapter implements the multi-table path of the adapter framework (Section 4.1.3) in two phases. The preparation phase joins the tables and records the coverage of each join: 1,530 of the 1,055,501 jobs have no group tag, and 4,825,741 instances have no sensor row, which later becomes the main cause of exclusion. Times are converted from seconds to integer microseconds, and a value that is not a whole number of microseconds raises an error rather than being rounded. The mapping phase applies the fourteen eligibility rules of Section 4.1.6 in their fixed order, records the first rule each ineligible role fails, maps resource values to canonical fields with their units, and aggregates instance values to roles (Section 5.1.3). Values are copied without filling, clipping or summation. CPU is expressed in percent of one virtual CPU (`percent_of_vcpu`) and memory in gigabytes, both per instance. GPU fields are not evaluated as targets; the GPU request and GPU type are used as features by the ML models (Section 5.3.1).

The adapter produces the `role_occurrence` view used for evaluation, an `instance` view and a rejected output. Every source row of the job, task and instance tables appears in exactly one of them, and the build reconciles the counts at each level before publication (Table 5.1). Of the 1,254,108 accepted role occurrences, 461,900 (36.8%) are eligible. Most exclusions are caused by missing sensor data (287,780 roles), failed jobs (282,027), partial sensor coverage (97,018) and incomplete jobs (87,980). A further 1,224 eligible roles lack a usable CPU value and are evaluated for memory only.

**Table 5.1** Reconciliation of the Alibaba canonical build

| Level | Source rows | Accepted | Rejected (no submission time) |
|---|---|---|---|
| Job | 1,055,501 | 1,051,838 | 3,663 |
| Role occurrence | 1,261,050 | 1,254,108 | 6,942 |
| Instance | 7,522,002 | 7,410,783 | 111,219 |

The Google adapter implements the single-table path. It maps the occurrences produced by Notebooks 02 and 03 into the canonical form under the Google capability profile, which declares CPU and memory as peaks, permits the combined CPU-or-memory metric and records that Google targets are not split-isolated. An acceptance test confirms that its output equals the canonical view used by the notebooks, so the integration leaves all Google results unchanged.

Before any output is written, both adapters pass the same framework checks. These confirm that every required field is present with its declared type, that units belong to the allowed set and that each request shares a unit with its usage, that no split label, target or recommendation column is present, and, for Alibaba, that every instance links to exactly one role. The Alibaba build script refuses to run from a working tree with uncommitted changes unless explicitly allowed, and records the code commit in the output metadata.

### 5.1.2 Execution Reconstruction and Dataset-Specific Temporal Features

A row of the Google sample is one usage window of one task instance on one machine. Notebook 02 groups the windows by collection and instance index and starts a new execution whenever the gap after the previous window exceeds the five-minute observation window. In this sample the smallest positive gap is 25 minutes, so the rule separates windows unambiguously. The result is 253,585 executions. Each execution receives a recurrence key formed from the user and the job's logical name [Wilkes 2019]; the sample contains 2,280 keys, of which 1,504 recur. Notebook 03 combines executions that share a recurrence key and a start time into 4,879 occurrences, 3,307 of which contain more than one execution.

Notebook 03 then builds the point-in-time history. For each occurrence it collects the earlier occurrences of the same key that had completed at or before its start, and computes the count, mean, standard deviation and 90th, 95th and 99th percentiles of their CPU peaks, memory peaks and runtimes, using linear interpolation. An independent recomputation confirms the counts and statistics for all 4,879 occurrences. Notebook 04 applies the shared `chronological_split` function to the executions, ordered by start time; because boundaries fall only between groups of equal start time, no occurrence is divided, and the occurrences split into 3,473 training, 675 validation and 731 test rows. The target of each occurrence is the CPU and memory peak of the next occurrence of the same key. Because Google targets may fall in a later split (Section 4.1.7), the target's start time is retained so that training rows can be selected by label period (Section 5.3.1).

On Alibaba, the adapter builds identities from the source fields. For a job with a group tag, the recurrence key combines the group and the task role name, the occurrence identifier combines the group and the job name, and the role key combines all three. A job without a group tag keeps a role key but no recurrence key, so it remains auditable but is excluded by the first eligibility rule.

The shared function `build_targets` adds the time-dependent fields to the eligible role occurrences. It applies the same `chronological_split` function to submission times, so that all roles of a job fall in one split, and streams the point-in-time history: within each recurrence, rows are processed in order of start time, and a priority queue ordered by end time releases a run into the history once it has completed. Histories are thus built in O(n log n) time without storing a copy for each row, and CPU and memory histories are kept separately, so a missing CPU value never removes a run from the memory history. For each row and resource, the target is the value of the immediately next eligible occurrence of the same recurrence, accepted only if it lies in the same split; otherwise a status records the reason. Rows whose next occurrence was submitted in the same whole second are flagged and kept. Before writing, the function verifies that a target value is present exactly when its status is `available`, and that no occurrence spans two splits. Table 5.2 summarizes the split tables of both datasets.

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

Because the executions of a Google occurrence run in parallel, Notebook 03 computes the occurrence peak in two steps (Section 4.1.4). It first sums the maximum-usage values of all windows that share the same aligned start and end times, and then takes the maximum of these sums over the occurrence's time windows. A sum is computed only when every window in the group has a value, and the maximum only when every sum exists; otherwise the peak is missing, because a partial sum would understate the peak without indicating it. CPU peaks are complete for all 4,879 occurrences, and memory peaks are missing for 60. Requests are summed across executions under the same rule, which leaves 73 occurrences without a request. The largest occurrence, with 6,921 executions, has a combined CPU peak of 91.88 normalized units, far above that of any single execution.

On Alibaba, each instance has at most one sensor row, which gives its lifetime average CPU, average memory and peak memory. The adapter sets each role value to the maximum over the role's instances that have a sensor row, or to missing if any of them lacks the value; values are never summed, because the evaluation unit is the role per instance. The role's memory peak is therefore the largest per-instance peak among its workers, and its CPU value the largest lifetime average. The trace contains no CPU peak, so the CPU peak field is left empty, and the evaluator labels every Alibaba CPU result as average-usage sizing.

## 5.2 Baseline Recommenders

### 5.2.1 Request-As-Is

The Request policy copies the canonical request of each resource into its recommendation columns. It is evaluated alongside every other policy on both datasets. On Alibaba, the validation comparison marks it as not selectable, so the selection function ranks only the history-based candidates (Section 4.2.1).

The effect of this exclusion is measurable. When Request was still selectable during development, it ranked first on Alibaba validation, with a memory violation rate of 4.74% against 5.58% for the best history-based candidate, P99 at `min_runs = 10`. It achieved this rate by reserving far more memory: its average memory waste was 22.26 GB per row against 8.94 GB, and its average memory utilization of 0.26 means that the typical request was about four times the next run's peak. As the Hybrid safeguard, it would also have prevented Hybrid from ever recommending less than the user's request.

### 5.2.2 Mean and Percentile Recommendations

On Google, the history statistics are those computed in Notebook 03. On Alibaba, the baseline module computes them from the same history stream as `build_targets`, so the two stages cannot apply different history rules. For each row and resource, the current history is materialized as an array, its mean and 90th, 95th and 99th percentiles are computed with NumPy's linear interpolation, and the array is discarded, which keeps memory bounded where retaining every history would require about 176 million values per resource. The module checks that the number of values used for each row equals the history count written by `build_targets`.

For each threshold `min_runs` in {1, 3, 5, 10} and each history policy, the recommendation for a resource is the history statistic when the row has at least `min_runs` earlier values, and the request otherwise. A flag records which case applies to each row and resource. Every candidate is scored by the shared evaluator on a fixed validation population (Section 5.5) of 329 occurrences on Google and 42,069 role occurrences from 9,712 recurrences on Alibaba, and ranked by the dataset's lexicographic order (Section 4.2.1). The selected configurations are P99 at `min_runs = 1` on Google and P99 at `min_runs = 10` on Alibaba.

On Google, the selection is stored in the Notebook 04 metadata and later copied into the decision manifest (Section 5.6). On Alibaba, the baseline script writes its selection record, `baseline_selection.json`, before it opens the test table, and then reads only an explicit list of test columns that excludes every target, target status and the same-second flag. It recomputes the history statistics with the test rows included and checks that the training and validation statistics are unchanged, which confirms that no test row enters an earlier history. Finally, it writes the recommendations of all five policies at the selected `min_runs` for every split, labelled with their units and CPU semantics and free of any target or current-run measurement.

### 5.2.3 Cold-Start Handling and Fallbacks

A row has a cold start when its workload has no earlier completed run; every history statistic is then missing and every history policy falls back to the request. A row with fewer than `min_runs` earlier values falls back in the same way, and CPU and memory fall back independently. A row that lacks usable history for a resource is therefore exactly a row whose recommendation for that resource is the request.

On Google, 1,801 of the 3,473 training occurrences (51.9%), 239 of the 675 validation occurrences and 240 of the 731 test occurrences are cold starts. Far fewer reach evaluation, because many belong to workloads that never recur and therefore have no target. Table 5.3 shows how the selected baseline obtains its recommendations on the evaluation populations. Some Google requests are missing, so a fallback does not always produce a value; such rows are counted as unknown by the evaluator, not as successes (Section 4.3), and they are the only rows on which Hybrid lacks its safeguard.

**Table 5.3** Source of the selected Google baseline (P99, `min_runs = 1`) on the evaluation populations

| | Train | Validation | Test |
|---|---|---|---|
| Evaluated occurrences | 1,983 | 329 | 259 |
| From history (CPU / memory) | 1,372 / 1,368 | 303 / 301 | 250 / 250 |
| Request fallback (CPU / memory) | 611 / 615 | 26 / 28 | 9 / 9 |
| No value: fallback with missing request (CPU / memory) | 7 / 9 | 1 / 1 | 0 / 0 |

On Alibaba, the share of validation rows that fall back to the request rises with the threshold, from 7.6% at `min_runs = 1` to 16.4% at 3, 20.3% at 5 and 25.7% at 10, equally for CPU and memory. The selected threshold therefore sizes about a quarter of the validation rows from the request, while the median validation row has 31 earlier completed runs. Requests are always present on eligible Alibaba rows, so every fallback produces a value. Table 5.4 gives the counts for every split.

**Table 5.4** Source of the selected Alibaba baseline (P99, `min_runs = 10`)

| | Train | Validation | Test |
|---|---|---|---|
| Rows with at least one available target | pending | 42,069 | pending |
| From history (CPU / memory) | pending | pending | pending |
| Request fallback (CPU / memory) | pending | pending | pending |
| Rows where Hybrid uses ML alone | pending | pending | pending |

## 5.3 Machine Learning Recommender

### 5.3.1 Feature and Target Preparation

The 24 Google features are defined once, in a fixed order, in the shared feature configuration. Five describe the occurrence at submission: its CPU and memory requests, its number of executions and the number of distinct CPU and memory requests among them. The other nineteen describe its history: the number of earlier completed occurrences and the count, mean, standard deviation and 90th, 95th and 99th percentiles of earlier CPU peaks, memory peaks and runtimes. The configuration also lists the columns that may never be features and three forbidden prefixes, `target_`, `rec_` and `uses_history_`, which exclude any target, baseline recommendation or baseline flag. An audit function checks the list against these rules and writes it, with its order and type, to `ml_feature_manifest.json`. Missing values are preserved and passed to the models, no other preprocessing is fitted, and targets are trained as log(1 + y) and transformed back with exp(y) − 1, clipped at zero. The label-period rule (Section 4.2.2) keeps 1,672 CPU and 1,649 memory training rows for model selection, and 2,108 and 2,082 rows from the training and validation sets for the final refit.

The Alibaba features are defined in a separate configuration. They consist of the per-instance CPU, memory and GPU requests, the number of instances, the GPU type requested by the task, the GPU type specification and workload label from the group-tag table, the CPU and memory history counts, and the mean and 90th, 95th and 99th percentiles of earlier CPU and memory values. A missing-value indicator is added for each of the eight history statistics before any value is filled, so that absent history remains distinguishable from zero usage. Targets, current-run measurements, split, exclusion and validity fields, the same-second flag and all identifiers, including job and task names, are excluded, and the shared `validate_features` function checks both tables against this list. The three categorical fields are one-hot encoded with a column for missing values, the remaining missing values are set to zero, the validation matrix is aligned to the training columns, and the column order is saved in `feature_order.json`. Each resource's model is trained only on rows with an available target for that resource, on the original scale of the target.

### 5.3.2 Model Training and Selection

On Google, Notebook 05 tunes a decision tree, a random forest and XGBoost for each resource, each with a fixed random seed. The grids contain 16 decision-tree, 27 random-forest and 32 XGBoost configurations, 150 in total across the two resources, and every result is recorded. Tuning uses scikit-learn's `GridSearchCV` with five time-ordered folds from the project's `purged_time_series_folds` function, which keeps rows with equal start times in the same fold and removes from each fold's training data every row whose target starts at or after the fold's validation period. The score is RMSE on the log scale. As a robustness check, the best configuration of each family is also scored with `GroupKFold` grouped by recurrence key; this result is not used for any decision. A `DummyRegressor` with the median strategy is reported as a reference floor and is not selectable.

Each tuned candidate is fitted on the training-period rows and scored on the 329 validation occurrences, and the model with the lowest log-scale RMSE is selected for each resource. The random forest is selected for both resources, with 300 trees, the square root of the number of features per split, a minimum leaf size of 10 and a maximum depth of 10 for CPU and 6 for memory. The selected models are refitted and saved with joblib. Validation predictions for ML and Hybrid come from the models fitted on training-period rows, and test predictions from the refitted models; Notebook 05 drops every test target column when it loads the test occurrences.

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

On Alibaba, the ML script, `run_alibaba_gpu_2020_ml.py`, verifies the checksums of the target and baseline folders and reads only the training and validation tables. Its candidates are a constant predictor (`DummyRegressor` with the mean strategy), a decision tree, a random forest with 100 trees, histogram-based gradient boosting, and XGBoost with 300 trees of depth 6, a learning rate of 0.05 and row and column subsampling of 0.8, all with a fixed random seed. Every candidate is fitted on the training rows and scored on the validation rows of each resource, with predictions clipped at zero, using RMSE, MAE and R² and, through the shared evaluator, the violation rate and average shortfall. The CPU and memory models are selected independently, using the selection order recorded with the result. The selected models are refitted on the training and validation rows and saved, while validation results for ML and Hybrid use the models fitted on training rows only. The selections are written to `model_selection.json` and the results of every candidate to `candidate_models.csv`.

**Table 5.6** Alibaba ML validation comparison

| Resource | Model | Settings | RMSE | MAE | Selected |
|---|---|---|---|---|---|
| CPU | pending | pending | pending | pending | pending |
| Memory | pending | pending | pending | pending | pending |

### 5.3.3 Validation-Based Model Comparison

On Google, tuning improved every model family over its starting configuration, and the random forest was the best tuned candidate for both resources on every accuracy measure (Table 5.5). The median reference has a lower MAE than every tuned model but a much higher log-scale error and RMSE: it predicts the typical occurrence well and fails on the large ones, which dominate RMSE and matter most for sizing. On the selection criterion the forest's advantage is clear, 0.850 against 1.048 for CPU and 0.387 against 0.472 for memory. The grouped cross-validation gave similar mean errors to the time-ordered folds but a spread about five times larger (± 0.285 against ± 0.054 for CPU), which shows that accuracy on unseen workloads depends strongly on which workloads are held out. The Alibaba comparison of all candidates, including the constant predictor, is given in Table 5.6.

## 5.4 Hybrid Safeguard Recommender

The Hybrid rule of Section 4.2.3 is implemented once, in the shared function `hybrid_recommendation`. The function takes the ML predictions and safeguard recommendations for one resource and returns the Hybrid recommendation together with a flag for rows whose safeguard is missing. It requires the two inputs to have the same shape and, when they are pandas Series, the same index, so that a prediction can never be paired with another row's safeguard; ML predictions must be finite and non-negative. The combination uses NumPy's `fmax`, which returns the larger value and ignores a missing safeguard, so a row without a safeguard receives the ML prediction.

On Google, Notebook 06 applies the function with the P95 recommendation at `min_runs = 1` as the safeguard. The safeguard is missing on one validation row per resource and on no test row (Section 5.2.3). The notebook also computes the supplementary `Hybrid_P99` variant, which is reported but not used in any decision. The Alibaba ML script applies the same function to each resource, with the locked recommendation of the selected baseline, P99 at `min_runs = 10`, as the safeguard. The safeguard is joined to the validation rows by role key with a one-to-one check, and the five baselines, ML and Hybrid are scored together on the 42,069 validation rows and written to `validation_policy_comparison.csv`.

## 5.5 Shared Metrics and Evaluation Framework

The metrics of Section 4.3 are implemented as vectorized NumPy functions that return one value per row, or a missing value when either input is missing or not finite. The violation functions return one when the actual value exceeds the recommendation; the combined violation returns one when either resource is violated, zero only when both are known and neither is violated, and a missing value otherwise. Utilization is capped at one and is missing when the recommendation is below 10⁻¹². Waste and shortfall are the positive parts of the difference between recommendation and actual value in each direction. No function fills or drops missing values.

The `RecommendationEvaluator` class applies these functions to a table of recommendations and targets. Its `evaluate` method returns row-level metrics without modifying its input, and `summarize` aggregates them over the rows on which each metric is defined, reporting every rate with its denominator. Constructed with a capability profile, the evaluator masks unsupported resources as unknown, computes the combined violation only where the profile permits it, and labels CPU results as `average_usage` where the dataset has no CPU peak; `summary_metadata` returns these labels, the units and the reason for any suppressed metric. The evaluator contains no ranking or selection logic.

Each pipeline fixes its evaluation population before any policy is scored. On Google, it consists of the occurrences with both targets, 329 in validation and 259 in test, and Notebook 04 confirms that every candidate is scored on the same occurrence identifiers. On Alibaba, the function `freeze_common_validation_population` selects the 42,069 validation rows with at least one available target, reading only validation target statuses; memory is scored on all of them and CPU on the 41,913 with a CPU target. Notebook 06 additionally scores a Google sensitivity population whose targets fall within the validation period (Section 4.1.7). The Alibaba baseline and ML scripts call the evaluator with the Alibaba profile, and the baseline script also produces the sensitivity results of Section 4.3: same-second successors excluded and alone, multi-instance roles, and equal weighting of recurrences. The implementation is covered by unit and contract tests, which are presented in Chapter 6.

## 5.6 Artifact Storage and Developer-Facing Outputs

Each stage writes its outputs to its own folder under `data/processed/`, and later stages read only from these folders (Table 5.7).

**Table 5.7** Main artifacts by stage

| Stage | Google (`google_subset_v1/`) | Alibaba |
|---|---|---|
| Canonical data | Observation table | `alibaba_gpu_v2020/`: three views, metadata, count report |
| Splits and targets | Occurrence tables per split | `alibaba_gpu_v2020_targets/` |
| Baselines | Validation comparison | `alibaba_gpu_v2020_baselines/`: selection record, locked recommendations |
| ML and decisions | Feature manifest, locked models, predictions, `decision_manifest.json` | `alibaba_gpu_v2020_ml/`: feature order, candidate comparison, locked models, `decision_manifest.json` |
| Final test | Policy comparison, row-level results, run record | Final-test outputs pending |

The Alibaba outputs are protected at every stage. Each output folder contains a `SHA256SUMS` file, and each script re-hashes its input folder against that file before reading it. Outputs are written to a staging folder and installed by two renames, the previous output being restored if the second rename fails, so a destination always holds a complete output; a build also refuses to replace an existing output unless explicitly forced. A verification mode of the canonical build script lets a team member who downloads a shared build confirm that its files, hashes, row counts and columns match the published one.

The Google pipeline enforces integrity at the final test. When Notebook 06 freezes the decisions, it writes `decision_manifest.json` with the locked decisions, the Git commit, a flag confirming a clean working tree, a hash of the notebook's code, the library versions and the SHA-256 hashes of thirteen inputs, including the split tables, ML predictions, locked models and the evaluator, metric and Hybrid source files. Before it reads any test target, the final-test cell checks that the manifest has final status, that the current commit and notebook code match the frozen ones, that no other file has uncommitted changes and that every input hash matches, and it refuses to run if a final-test result already exists. It then scores the seven policies on the 259 evaluated test occurrences and writes a run record containing the hash of the manifest it used.

The Alibaba ML script writes its decision manifest after selection and refit, before the test table has been opened. The manifest records the baseline selection and the hash of its record, the checksums of the input folders, the selected models with their hyperparameters and file hashes, the feature list and order, the Hybrid and clipping rules, the model selection order, the random seed, the library versions, the result semantics and the code commit. The one-time Alibaba final test reads this manifest before it opens the test table.

Raw and processed data remain outside version control because of their size, while the final results of each dataset, including the decision manifests and run records, are committed under `reports/results/`. All final runs use the locked environment of `requirements-lock.txt` (Table 3.1). The REST API reads the published recommendation and result files and serves them as JSON, organized by dataset, workload and policy and labelled with their units; the web frontend presents them to developers. Neither component runs a pipeline stage or modifies an artifact (Section 4.4).
