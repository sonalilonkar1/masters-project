# TraceAdvisor Google Subset Pipeline Analysis

**Scope:** `pipelines/google_subset/`, notebooks 00 through 05.
**Method:** The findings come from parsing the notebook JSON, reading the saved files in `data/processed/google_subset_v1/` (read-only), checking git history, and recomputing results in memory. One file outside the directory was used: `src/evaluation/evaluator.py` was imported, not modified, to reproduce the Notebook 04 baseline selection exactly. No other repository files were changed in producing this analysis.
**Cell numbering:** Cell numbers are 0-based positions in each notebook's cell list. Markdown cells are counted.

---

## 1. Executive Summary

The Google subset pipeline has five working notebooks (00–04) and one empty placeholder (05). Together they turn the Kaggle Google Borg trace sample (405,894 rows) into four nested levels of data:

- observation records;
- reconstructed execution episodes (253,585);
- recurring workload families (2,280 recurrence keys);
- recurrence occurrences (4,879).

For each occurrence, the pipeline builds point-in-time historical profiles. It splits the data chronologically 70/15/15, builds next-occurrence CPU and memory targets, and generates Request, Mean, P90, P95 and P99 baseline recommendations. It then selects a baseline policy and a `min_runs` threshold using validation data only. The selected configuration is **P99 with `min_runs = 1`**, with a validation any-resource violation rate of 21.95%. The Request baseline's rate is 55.52%.

The main verified results are:

1. **Targets cross split boundaries.** Targets are built on the full occurrence table before split assignment. 104 of the 330 validation targets fall in the test period, and all 104 are in the 329-row validation population that is scored.
2. **Test-period targets affect the reported validation metrics, but not this run's selection.** Removing them leaves the selected policy unchanged (P99, `min_runs = 1`), while that policy's any-resource violation rate moves from 21.95% to 18.30%.
3. **Notebook 05 is a 0-byte file** in every commit, on every branch. It is not a valid notebook, and no test evaluation exists.
4. **Failed, evicted, lost and killed records are included** in executions, occurrence peaks, history and targets. No filtering decision is applied anywhere.
5. **Identical values are summed across machines.** In 38,146 instance-windows (15%), one instance appears on several machines, and every machine carries identical peak values. These values are summed. Removing the repeats would change the CPU peak of 1,159 of the 4,879 occurrences. Whether the repeated rows are true duplicates is suspected but not yet proven.
6. **Only CPU and memory are evaluated.** No notebook contains GPU handling.
7. **Shared vs specific logic.** The logic for history, targets, baselines and selection is dataset-agnostic in design. It is written against Google-specific column names, units, constants and assertions, so the pipeline cannot run on another dataset unchanged. The shared evaluator itself can be reused unchanged for any dataset that provides CPU and memory values.

---

## 2. Current Google Subset Pipeline

### 2.1 Execution order

The notebooks run strictly in sequence: **00 (optional, no outputs) → 01 → 02 → 03 → 04 → 05 (empty)**. Each notebook from 02 onward raises an error if the previous notebook's output is missing.

### 2.2 Inputs and outputs

All outputs are written to `data/processed/google_subset_v1/`.

| Notebook | Reads | Writes |
|---|---|---|
| 00_dataQualityReview | `subset/borg_traces_data.csv` (falls back to `data/raw/subset/`) | Nothing |
| 01_dataIngestion | The same CSV (three candidate paths) | `google_subset_observations_v1.parquet` |
| 02_reconstructExecutions | `google_subset_observations_v1.parquet` | `google_subset_executions_v1.parquet`, `google_subset_observations_reconstructed_v1.parquet` |
| 03_buildProfilesAndMetrics | Both Notebook 02 outputs | `job_profiles_google_subset_history_v1.parquet` (one row per occurrence), `job_metrics_v0.parquet` (one row per execution) |
| 04_splitAndBaselines | Both Notebook 03 outputs; imports `src.features.split_utils.chronological_split` and `src.evaluation.evaluator.RecommendationEvaluator` | `{train,val,test}_occurrences.parquet`, `{train,val,test}_features.parquet`, `baseline_validation_comparison.csv`, `metadata.json` |
| 05_evaluateRecommendations | — | — (the file is 0 bytes) |

### 2.3 Data flow

```
Raw CSV: one row per machine and 5-minute usage window, with lifecycle event fields attached
  │
  ├─ N01 → observations                  key: observation_id
  │
  ├─ N02 → observations + execution_id   (episode reconstruction)
  │        executions                    key: execution_id; grouped by recurrence_key
  │
  ├─ N03 → occurrences                   key: occurrence_key = recurrence_key || start time
  │        (peaks from observation windows; requests summed across executions)
  │        + point-in-time history per occurrence
  │        job_metrics = executions + their occurrence's history
  │
  └─ N04 → chronological split of execution rows → frozen time boundaries
           → occurrence table → next-occurrence targets → occurrence split assignment
           → baselines → validation-only selection
           → occurrence files (canonical) + execution files (compatibility)
```

Notebook 03 needs both Notebook 02 outputs, because it computes occurrence peaks from observation windows rather than from execution rows. Notebook 04 needs both Notebook 03 outputs, because it splits on execution rows and models on occurrence rows.

### 2.4 Key quantities

| Quantity | Value | Source |
|---|---|---|
| Raw observation rows | 405,894 | N01 cell 21 output |
| Candidate `collection_id + instance_index` groups | 242,946 | N01 markdown cell 10 |
| Reconstructed executions | 253,585 | `metadata.json` `split_boundaries.total_rows` |
| Recurrence keys | 2,280 (1,504 with more than one execution) | N02 markdown cell 28 |
| Occurrences | 4,879 (3,307 with more than one execution) | N04 cell 16 output |
| Execution rows per split | 178,858 / 36,703 / 38,024 | `metadata.json` |
| Occurrences per split | 3,473 / 675 / 731 | N04 cell 22 output |
| Occurrences with a next-occurrence target | 2,010 / 330 / 259 | N04 cell 25 output |
| Validation population that is scored | 329 | N04 cell 34; `metadata.json` |
| Occurrences missing a CPU / memory peak | 0 / 60 | Saved occurrence files |
| Occurrences missing a CPU / memory request | 73 / 73 | Saved occurrence files |
| Split boundaries (execution start, µs) | train ≤ 1812600000000; validation 1813200000000–2261100000000; test ≥ 2262600000000 | `metadata.json` `split_boundaries` |

---

## 3. Notebook-by-Notebook Analysis

### 3.1 00_dataQualityReview (9 cells)

**Purpose:** An exploratory audit only. It writes no files.

| Cell | Behavior |
|---|---|
| 0 | Finds the repository root (via a Colab path or by walking up to a folder named `masters-project`) and loads the full CSV. |
| 1 | `parse_nested` uses `ast.literal_eval` to read `resource_request`, `average_usage`, `maximum_usage` and `random_sample_usage`. It extracts `raw_req_*`, `raw_avg_*` and `raw_peak_*`. |
| 2 | Summarizes value distributions, negative values, peak vs average, peak vs request, possible timestamp units and usage-window lengths. |
| 4 | Detects `INT64_MAX` sentinel values in `time`, and event times later than the trace end. |
| 5–6 | Counts events and failures, and how complete the resource fields are for each event type. |
| 7 | Checks key uniqueness for the observation key and the candidate execution key. |
| 8 | Compares the requested memory with `assigned_memory`. |

### 3.2 01_dataIngestion (22 cells)

**Purpose:** Produce a validated, observation-level table with consistent column names.

| Cell | Variable / function | Behavior |
|---|---|---|
| 0 | `REPO_ROOT`, `RAW_CSV_PATH` | Finds the repository; the fallback path is hard-coded to `/Users/meghanakoti/masterproject/masters-project`. Loads the CSV. |
| 2 | `parse_nested`, `get_nested_value` | Same parsing as N00 cell 1. Requires the dictionary keys `cpus` and `memory`. |
| 3 | — | Raises an error on negative resources, peak below average, or zero or negative usage-window lengths. |
| 4 | `INT64_MAX`, `event_time_us`, `usage_start_time_us`, `usage_end_time_us` | Sets the sentinel to missing and creates the microsecond timestamp columns. |
| 7–12 | — | Audits events, failures and candidate groups. Filters nothing. |
| 13 | — | Confirms that `collection_id, instance_index, machine_id, start_time, end_time` uniquely identifies every row. |
| 16–18 | — | Finds multi-machine windows with identical values, and `time = 0` on those rows. |
| 21 | `CANONICAL_RESOURCE_MAP`, `OBSERVATION_KEY_COLUMNS` | Renames resources to `requested/average/peak_{cpu_ncu, memory_normalized}`. Builds `observation_id` as the `‖`-joined observation key. Saves **every** row; no events are filtered out. |

### 3.3 02_reconstructExecutions (29 cells)

**Purpose:** Split each candidate group into execution episodes and assign each execution to a recurring workload family.

| Cell | Variable / function | Behavior |
|---|---|---|
| 5 | — | Converts timestamps to numbers and drops rows without usage intervals. N01 guarantees there are none. |
| 7 | `candidate_instance_key` | Builds `collection_id‖instance_index`. |
| 8 | `previous_max_usage_end_us`, `gap_from_previous_us` | Measures the gap from the running maximum of earlier window ends within each candidate group. |
| 13 | `OBSERVATION_WINDOW_US = 5 * 60 * 1_000_000` | Starts a new episode when the gap exceeds 5 minutes. Sets `execution_id = candidate‖episode_N`. The smallest positive gap observed is 25 minutes. |
| 15 | `execution_lookup` | Reloads the observation file and merges the execution IDs back in one-to-one. |
| 17 | `strict_sum`, `strict_max`, `machine_requests`, `machine_windows`, `window_totals` | For each execution, the request is the maximum per machine, summed across machines. The peak is the maximum per machine and window, summed across machines, then the maximum over windows. Any missing part makes the result NaN. Runtime = last window end − first window start. |
| 22 | `user_clean`, `logical_workload_name`, `recurrence_key`, `recurring_job_id` | Builds `recurrence_key = user ‖ (collection_logical_name ?? collection_name)`. If the user or name columns are missing, the defaults are `unknown_user` and `unknown_job`. |
| 24 | `EXECUTIONS_PATH`, `RECONSTRUCTED_OBSERVATIONS_PATH` | Saves both files and checks them. |

### 3.4 03_buildProfilesAndMetrics (39 cells)

**Purpose:** Build occurrence-level peaks, requests and runtimes, then point-in-time historical profiles.

| Cell | Variable / function | Behavior |
|---|---|---|
| 4 | — | Attaches `recurrence_key` and `execution_start_time_us` to each observation (many-to-one). |
| 6 | `window_keys`, `window_totals`, `occurrence_resource_peaks` | Groups observations by `(recurrence_key, execution_start_time_us, usage_start_time_us, usage_end_time_us)` and sums the peaks, keeping NaN if any part is missing. The occurrence peak is the maximum of these window totals. |
| 8 | — | Hard-coded check: exactly one occurrence has 6,921 executions, with CPU 91.877289 and memory 0.481828. |
| 10 | `complete_sum`, `occurrences`, `occurrence_key` | The occurrence request is a strict sum across executions; the end time is the latest execution end; runtime is recorded in **seconds**. `occurrence_key = recurrence_key‖execution_start_time_us`. Asserts that every runtime is greater than 0. |
| 14 | — | Asserts `runtime_sec > 0` and `usage_end_time_us > usage_start_time_us`. |
| 21 | `profile_fields`, `historical_profiles` | An `iterrows` loop with quadratic cost. For each occurrence starting at time `t`, eligible history is earlier occurrences of the same key with `start < t` and `occurrence_end_time_us ≤ t`. It computes the count, mean, standard deviation, P50, P90, P95 and P99 for CPU peak, memory peak and runtime, with a separate count for each resource. Cold starts are left as NaN. History is built over all occurrences at once, with no split. |
| 22, 26, 28 | — | Checks the history counts, statistics and cold-start handling again, using the same filter rule as cell 21. |
| 24 | `job_metrics` | Attaches the occurrence history to every execution row. |
| 30, 32 | — | Recomputes the occurrence peaks, runtime and requests a second way and compares them. |
| 35, 37 | `PROFILE_OUTPUT_PATH`, `METRICS_OUTPUT_PATH` | Saves both files, reloads them and checks them. |

### 3.5 04_splitAndBaselines (53 cells)

**Purpose:** Split chronologically, build the occurrence table and next-occurrence targets, compute the baselines, and select one using validation only.

| Cell | Variable / function | Behavior |
|---|---|---|
| 3 | `MIN_RUNS_CANDIDATES = [1, 3, 5, 10]` | Defines the paths and the `min_runs` values to test. |
| 5 | `validate_base_schema`, `validate_occurrence_profile_schema` | Checks for the required Google-named columns. |
| 7 | `derived_occurrence_key` | Rebuilds the occurrence key using an `int64` cast of the start time, and merges the occurrence profiles onto the execution rows. |
| 12 | `chronological_split(...)` | Splits the **execution rows** 70/15/15, keeping rows with the same start time together. |
| 13 | `TRAIN_END_TIME`, `VAL_START_TIME`, `VAL_END_TIME`, `TEST_START_TIME` | Freezes the split boundaries. |
| 16 | `build_occurrence_table`, `add_next_occurrence_targets`, `TARGET_*_COL` | Builds one row per occurrence, and builds targets on the **full, unsplit** occurrence table. |
| 17 | `KNOWN_OCCURRENCE_EXECUTION_COUNT = 6921`, `KNOWN_FULL_WORKLOAD_CPU_PEAK = 91.877289`, `KNOWN_LARGEST_INDIVIDUAL_CPU_PEAK = 0.013275` | Regression check with dataset-specific values. |
| 19–20 | `HISTORY_ALIAS_MAP` | Copies `hist_*` to `occ_hist_*`. Asserts `occ_hist_peak_cpu_count == prior_completed_occurrence_count` for every row. |
| 22 | `split_occurrences_by_frozen_boundaries` | Assigns occurrences to splits by start time, using the global boundary variables. |
| 26 | — | Asserts only that each target's time is later than its occurrence's start. |
| 28 | `add_baseline_recommendations`, `CPU_BASELINE_COLUMNS`, `MEMORY_BASELINE_COLUMNS` | Request = the current occurrence's request. Mean/P90/P95/P99 use the history statistic when that resource's count is at least `min_runs` and the value is present; otherwise they fall back to the request. |
| 34 | `validation_common_mask`, `COMMON_EVAL_REQUIRED` | The scored population is every validation row with both targets present: 329 rows. There is no time-based filter. |
| 37 | `BASELINE_POLICIES`, `evaluator.evaluate`, `evaluator.summarize` | Scores 5 policies × 4 `min_runs` values against the target columns. |
| 41 | `selection_sort_columns`, `SELECTED_MIN_RUNS`, `SELECTED_BASELINE_POLICY` | Ranks the results in this order: any-resource violation %, worst single-resource %, sum of CPU and memory %, CPU waste, memory waste, `min_runs`, policy name. |
| 43 | — | Generates the selected recommendations for train, validation and test. Test is not scored. |
| 45 | `merge_occurrence_annotations` | Copies occurrence annotations back onto the execution rows. |
| 48–51 | `metadata`, `make_json_serializable` | Writes the metadata and all files, then checks them. |

### 3.6 05_evaluateRecommendations

The file is 0 bytes. Git history shows it was 0 bytes in every commit that touched it: `88eee56` on main ("Add Google subset pipeline from data quality review through recommendation evaluation"), `0345cf4` on `datapipeline3-Sofia`, and the revert `1d3a8c5`. Zero bytes is not valid notebook JSON, so it cannot be loaded as a notebook. The repository gives no evidence on whether it was left empty on purpose.

---

## 4. Confirmed Findings

Each finding lists the notebook and cell, the variable or function involved, the exact behavior, why it matters, and its status.

### F1. Targets are built before split assignment

- **Location:** N04 cells 12–13 (boundaries), 16 (targets), 22 (split assignment).
- **Variables / functions:** `add_next_occurrence_targets(all_occurrences)`; `split_occurrences_by_frozen_boundaries`.
- **Behavior:** The boundaries are frozen first. Targets are then computed on the full occurrence table, and occurrences are assigned to splits afterwards. No target is ever compared with a boundary; cell 26 checks only that the target time is later than the occurrence start.
- **Why it matters:** A row's label can come from a later split.
- **Status:** Confirmed.

### F2. `shift(-1)` is grouped by `recurrence_key` and ordered chronologically

- **Location:** N04 cell 16, `add_next_occurrence_targets`.
- **Behavior:** The function runs `sort_values(["recurrence_key", "execution_start_time_us"], kind="mergesort")`, then `groupby("recurrence_key", sort=False)[col].shift(-1)`. There are no ties within a key, because `build_occurrence_table` raises an error if `occurrence_key` is duplicated. Recomputing the shift from the saved files reproduces `target_next_occurrence_start_time_us` exactly.
- **Caveat:** "Next" is defined by start time. In 9 cases (7 train, 1 validation, 1 test), the next occurrence starts before the current one has ended.
- **Status:** Confirmed.

### F3. Validation targets fall in the test period

- **Location:** N04 cells 16 and 34; the saved `val_occurrences.parquet`.
- **Evidence:**

| Split | Occurrences | With target | Target starts after `TRAIN_END_TIME` | Target starts at or after `TEST_START_TIME` |
|---|---|---|---|---|
| Train | 3,473 | 2,010 | 338 | 128 |
| Validation | 675 | 330 | 330 | 104 |
| Test | 731 | 259 | 259 | 259 |

- **Detail:** All 104 validation rows with test-period targets are in the 329-row scored population.
- **Why it matters:** Validation scores include outcomes observed during the test period. Training labels include outcomes from the validation and test periods.
- **Status:** Confirmed.

### F4. Test-period outcomes enter the validation score but do not change this run's selection

- **Location:** N04 cells 28, 34, 37 and 41.
- **Method:** The code of cells 28 and 41 was run unchanged in memory, with the real `RecommendationEvaluator`. The full-population result reproduces `baseline_validation_comparison.csv` exactly.

| Validation population | n | Selected | P99 / `min_runs = 1` any-resource violation |
|---|---|---|---|
| As in N04 | 329 | P99, `min_runs = 1` | 21.95% |
| Targets inside the validation period only | 225 | P99, `min_runs = 1` | 18.30% |
| Targets inside the test period only | 104 | P99, `min_runs = 1` | 29.81% |

- **Other routes for leakage were checked, and none exist:**
  - No train or validation occurrence ends at or after `TEST_START_TIME`.
  - History requires `occurrence_end_time_us ≤ t` (N03 cell 21).
  - Recommendations use only history and the current request (N04 cell 28).
  - Test recommendations are generated (cell 43) but never scored.
- **Why it matters:** The reported validation metrics are contaminated. The selection is unaffected in this run, but nothing guarantees that on other data.
- **Status:** Confirmed.

### F5. The notebook's description of target isolation contradicts itself

- **Location:** N04 markdown cell 0, markdown cell 24, and cell 48 (`metadata["target_split_isolation"]`).
- **Evidence:** Cell 0 says targets are built "inside each frozen split so labels never cross split boundaries". Cell 24 and the metadata say "Labels may cross split boundaries". The code matches cells 24 and 48.
- **Status:** Confirmed.

### F6. Notebook 05 is empty and not a valid notebook

- **Evidence:** See section 3.6.
- **Status:** Confirmed. Whether this was intentional is unknown.

### F7. Failed, evicted, lost, killed and possibly incomplete records are included everywhere

- **Location:** N01 cell 21 (saves all rows); N02 cell 5 (drops only rows with missing usage intervals); N02 cell 17 and N03 cell 6 (aggregate all observations).
- **No status information is carried forward:** The execution table has no event or status column, and N04 never refers to events.
- **Event mix in the observations:**

| Event | Rows |
|---|---|
| FINISH | 92,867 |
| FAIL | 92,678 (equal to the count of `failed = 1`) |
| ENABLE | 75,907 |
| SCHEDULE | 69,104 |
| LOST | 59,515 |
| EVICT | 14,756 |
| KILL | 951 |
| Other | 116 |

- **Spread:**
  - 2,584 of 4,879 occurrences contain at least one FAIL, KILL, EVICT or LOST row.
  - 137 of the 329 scored validation rows have a target occurrence that contains such rows.
- **No completion flag:**
  - One occurrence ends exactly at the trace's last window end (2678700000000), so it may have been cut off while still running.
  - One occurrence starts at the trace's first window (300000000), so it may have started earlier.
  - Both are treated as complete.
- **Why it matters:** History and targets mix completed and abnormal runs without any recorded decision to do so.
- **Status:** Confirmed.

### F8. Identical values are summed across machines

- **Location:** N02 cell 17 (`machine_windows`, `window_totals`, `machine_requests`, using `strict_sum`); N03 cell 6 (`window_totals`).
- **Evidence:**
  - 38,146 of 253,594 instance-windows (15%) span more than one machine, with up to 6,566 machines for a single instance.
  - In 100% of these windows, every machine has the identical peak CPU and peak memory.
  - These windows contain 190,446 of the 405,894 observation rows.
  - Applying N03's rule to the observations reproduces the saved occurrence peaks exactly. Keeping one row per (collection, instance, window) would change the CPU peak of 1,159 occurrences.
  - Among those, the current value is larger than the one-row-per-window value by 1.29× at the median, 5.01× at the 90th percentile, 95× at the 99th percentile, and 551× at most.
  - Requests are summed across machines the same way, for the 38,143 executions that span more than one machine.
- **Clarification:** The 6,921-execution regression case is a different situation. Its executions are 6,921 distinct instances, each on one machine, in a single window. Its total is a sum across instances, not a repeat of one instance's values.
- **Why it matters:** If the repeated rows are duplicates, occurrence peaks, requests, history and targets are overstated for roughly a quarter of occurrences.
- **Status:** The pattern and its magnitude are confirmed. That the rows are duplicates is suspected, but strongly supported.

### F9. N02 and N03 compute window totals the same way, through duplicated code

- **Location:** N02 cell 17, N03 cells 6 and 30.
- **Behavior:** N01 cell 21 guarantees one observation per (instance, machine, window). N02's per-machine `max` therefore changes nothing, and N02 and N03 produce the same sums. The logic is written three times in different forms.
- **Status:** Confirmed.

### F10. The pipeline evaluates only CPU and memory

- **Location:** N04 cells 33 and 37.
- **Behavior:** No code cell in N01–N04 refers to GPU. The evaluator is called with exactly `actual_cpu_col`, `actual_memory_col`, `recommended_cpu_col` and `recommended_memory_col`.
- **Status:** Confirmed.

### F11. Units are inconsistent across stages

- **Location:** N03 cell 10 (`occurrence_runtime_sec`, with `hist_runtime_*` computed in seconds); N04 cell 16 (`occurrence_runtime_us`).
- **Behavior:** Runtime history is in seconds while the occurrence runtime is in microseconds, and both appear in the saved occurrence files. Resource units are written into column names (`*_ncu`, `*_normalized`).
- **Status:** Confirmed.

### F12. Next-occurrence size is saved but never used

- **Location:** N04 cell 16, `TARGET_OCCURRENCE_SIZE_COL = "target_next_occurrence_execution_count"`; cell 28 (Request uses the current occurrence's request).
- **Behavior:** The target is the *total* of the next occurrence, whose number of executions can differ from the current occurrence's. No check or normalization uses the saved count.
- **Status:** Confirmed.

---

## 5. Evaluation and Leakage Risks

| # | Risk | Evidence | Effect | Status |
|---|---|---|---|---|
| R1 | Validation targets in the test period | F3, F4 | Validation metrics include test-period outcomes; the selection was unchanged in this run. | Confirmed |
| R2 | Training targets in later periods | F3: 338 training targets after `TRAIN_END_TIME` | Any model trained on training rows learns from labels observed in the validation or test periods. N04 itself does not train on them. | Confirmed |
| R3 | No test evaluation exists | F6 | No final, held-out results exist. | Confirmed |
| R4 | Summing across machines may inflate values | F8 | Peaks, requests, history and targets may be overstated for 1,159 occurrences. | Pattern confirmed; cause suspected |
| R5 | Abnormal runs are included | F7 | History and targets mix FINISH runs with FAIL, EVICT, LOST and KILL runs. | Confirmed |
| R6 | Occurrence sizes differ | F12 | The total being predicted can change with the number of executions, not just with workload behavior. | Confirmed |
| R7 | Small scored validation population | 329 of 675 validation occurrences | Differences between configurations are small relative to the sample (P99 at `min_runs` 1 vs 3: 21.95% vs 22.39%). | Confirmed |
| R8 | Execution-level files repeat occurrence targets | N04 cell 45; up to 6,921 rows share one target | Training on execution rows would weight large occurrences heavily. | Confirmed |
| R9 | Overlapping occurrences | F2: 9 cases | The "next" occurrence may run at the same time as the current one. | Confirmed |
| R10 | Possibly cut-off occurrences at the trace edges | F7: one at each edge | Small, but untracked. | Confirmed |

---

## 6. Shared Versus Google-Specific Components

### 6.1 Dataset-agnostic in logic

| Component | Location | Dependency on Google |
|---|---|---|
| Point-in-time history (`end ≤ t`, count, mean, std, percentiles) | N03 cell 21 | Inline loop; column names come from `profile_fields` |
| `_single_value_or_nan`, `_strict_sum` | N04 cell 16 | None |
| `add_next_occurrence_targets` | N04 cell 16 | Column names in the global `TARGET_*_COL` variables |
| `split_occurrences_by_frozen_boundaries` | N04 cell 22 | Reads the global boundary variables |
| `add_baseline_recommendations` | N04 cell 28 | Column names in global variables |
| Evaluation loop | N04 cell 37 | Column names in `BASELINE_POLICIES` |
| Lexicographic selection | N04 cell 41 | Uses only the evaluator's summary keys |
| `merge_occurrence_annotations` | N04 cell 45 | `OCCURRENCE_ANNOTATION_COLUMNS` uses Google column names |
| `make_json_serializable` | N04 cell 47 | None |
| `complete_sum`, `normalize_for_comparison` | N03 cells 10, 37 | None |
| `chronological_split` (outside this directory) | Imported in N04 cell 12 | Configured through `time_col` and `id_col` |
| `RecommendationEvaluator` (outside this directory) | Imported in N04 cell 33 | None; column names are passed in as arguments |

### 6.2 Google-specific

| Component | Location |
|---|---|
| CSV layout, dictionary-string parsing with `cpus`/`memory` keys | N00 cell 1, N01 cell 2 |
| `INT64_MAX` sentinel; microsecond timestamps | N01 cell 4 |
| Validation errors raised for peak below average and zero-length windows | N01 cell 3 |
| `collection_id + instance_index` candidate key; 5-minute gap rule for episodes | N02 cells 7, 8, 13 |
| Summing across machines for requests and peaks | N02 cell 17 |
| Recurrence key from `user` and `collection_logical_name` / `collection_name`, with `unknown_*` defaults | N02 cell 22 |
| Exact start-time equality defining an occurrence | N03 cells 6, 10 |
| Peak totals over exactly aligned `(usage_start, usage_end)` windows | N03 cell 6 |
| Hard-coded regression values (6,921; 91.877289; 0.481828; 0.013275) | N03 cell 8, N04 cell 17 |
| Assertion that CPU history count equals the prior-occurrence count everywhere | N04 cell 20 |
| `int64` cast of the start time inside the occurrence key | N04 cell 7 |
| Units in column names (`*_ncu`, `*_normalized`, `*_us`) | N01 cell 21 onward |
| Required-column lists in the schema validators | N04 cell 5 |
| Paths and version labels (`google_subset_v1`, `*_v1`, `job_metrics_v0`); Colab Shared Drive path | All notebooks |

### 6.3 Duplicated logic

| Logic | Locations |
|---|---|
| Finding the repository root (three variants) | By folder name: N00, N01, N02, N04. By `.git`: N03. With a hard-coded local fallback: N01 cell 0. |
| `parse_nested` and the memory-vs-assigned comparison | N00 cells 1 and 8; N01 cells 2 and 6 |
| Window totals | N02 cell 17; N03 cells 6 and 30 |
| Occurrence request sums | N03 cells 10 and 32; N04 cell 16 (fallback) |
| History columns stored twice (`hist_*` and `occ_hist_*`) | N04 cells 16 and 19 |

---

## 7. Adapter Interface Boundary

The natural boundary sits at the occurrence table that Notebook 03 produces in cell 10, together with the mapping from execution rows to occurrences.

**Adapter side (dataset-specific):**
- Notebook 01: parsing, sentinels, units, observation identity.
- Notebook 02: execution identity, recurrence identity.
- Notebook 03 cells 6 and 10: occurrence peaks, requests, end times.

**Shared side (dataset-agnostic in logic):**
- Notebook 03 cell 21: history.
- Notebook 04 cells 12–43: splitting, targets, baselines, evaluation and selection.

Execution rows must still cross the boundary, because Notebook 04 cell 12 runs `chronological_split` on execution rows, and cells 7 and 45 relate executions to occurrences.

---

## 8. Required Canonical Input Contract

This contract describes what the shared side consumes today. It is written in the code's current column names, and the constraint column notes where each rule is enforced.

### 8.1 Occurrence table (one row per occurrence)

| Field (current name) | Type | Constraint as currently enforced or assumed |
|---|---|---|
| `occurrence_key` | string | Unique and non-null. Currently `recurrence_key‖start`, checked in N04 cell 7. |
| `recurrence_key` | string | Non-null. Missing identity currently falls back silently to `unknown_user‖unknown_job` (N02 cell 22). |
| `execution_start_time_us` (occurrence start) | integer | Non-null and castable to `int64` (N04 cell 7). Unique within each `recurrence_key`. Used for ordering, splits and targets. |
| `occurrence_end_time_us` | integer | ≥ start. Runtime must be strictly positive (N03 cells 10, 14). Used for the history cutoff `end ≤ t`. |
| `occurrence_execution_count` | integer | ≥ 1. |
| `occurrence_requested_cpu_ncu` | float | NaN allowed. Same unit as the CPU peak. |
| `occurrence_requested_memory_normalized` | float | NaN allowed. Same unit as the memory peak. |
| `occurrence_peak_cpu_ncu` | float | Must never be NaN (N04 cell 20). Meaning: the maximum over time of total concurrent usage. |
| `occurrence_peak_memory_normalized` | float | NaN allowed. Same meaning as the CPU peak. |

### 8.2 Execution table (one row per execution)

| Field | Type | Constraint as currently enforced |
|---|---|---|
| `execution_id` | string | Unique and non-null (N04 cell 5). |
| `occurrence_key` | string | Must map to exactly one occurrence row (N04 cell 7). |
| `recurrence_key` | string | Must match the occurrence row (N04 cell 7). |
| `execution_start_time_us` | integer | Equal to its occurrence's start; this is how occurrences are defined. |
| `execution_end_time_us` | integer | ≥ start (N04 cell 5). |

### 8.3 Information the current contract does not carry

- The status of each run or occurrence: completed, failed, evicted, killed, lost, running, or cut off at the trace edge.
- Declared units for time and for each resource.
- A third resource, such as GPU or GPU memory.
- How an occurrence peak was aggregated: from aligned windows, from per-instance summaries, or otherwise.

### 8.4 Rules that would fail or behave differently on another dataset

| Category | Rule | Location |
|---|---|---|
| Hard-coded values | Exactly one occurrence with 6,921 executions, with CPU 91.877289, memory 0.481828 and largest individual CPU 0.013275 | N03 cell 8, N04 cell 17 |
| Assertion | CPU history count equals the prior-occurrence count for every row | N04 cell 20 |
| Assertion | Runtime greater than 0; usage end strictly after usage start | N03 cells 10, 14 |
| Validation errors raised | Peak below average; zero-length windows | N01 cell 3 |
| Input format | Dictionary strings with `cpus` and `memory` keys | N01 cell 2 |
| Time units | Microseconds; divisors `1_000_000`, `60_000_000`, `86_400_000_000`; 5-minute gap | N02 cells 10, 13; N03 cell 10 |
| Identifiers | `collection_id`, `instance_index`, `machine_id`, `user`, `collection_logical_name`, `collection_name` | N01 cell 21; N02 cells 7, 22 |
| Key construction | `int64` cast of the start time | N04 cell 7 |
| Aggregation | Occurrence defined by exact start-time equality | N03 cells 6, 10 |
| Aggregation | Peaks summed over exactly aligned windows | N03 cell 6 |
| Aggregation | Requests and peaks summed across machines | N02 cell 17 |
| Column names | `*_ncu`, `*_normalized` and `TARGET_*_COL` names written throughout | N03, N04 |

### 8.5 Reusing the shared evaluator

The shared evaluator can be reused unchanged for any dataset that provides CPU and memory actuals and recommendations in matching units, because column names are passed in as arguments. It cannot evaluate a third resource. If a dataset lacks one of the two resources, the any-resource violation becomes unknown for rows that do not violate the other resource. The real obstacle to reusing the pipeline is the Google-specific code around the evaluator (section 8.4), not the evaluator itself.

---

## 9. Open Questions

1. Are the repeated rows in multi-machine instance-windows duplicates, or real parallel usage? (F8)
2. What does `event` on a usage row mean? N01 markdown cell 19 notes that event fields may be recorded at a different grain from usage. Should FAIL, EVICT, LOST and KILL records be excluded, kept, or flagged? (F7)
3. Are targets meant to cross split boundaries? N04 cell 0 and cells 24/48 disagree. (F3, F5)
4. Should the target be the next occurrence's total, or a value normalized for occurrence size? (F12)
5. How should overlapping occurrences and occurrences cut off at the trace edges be handled? (F2, F7)
6. What was Notebook 05 meant to contain? (F6)
7. Which Alibaba trace is the intended second dataset? Its timestamp units, peak fields, status fields and window structure have not been checked against the contract in section 8.

---

## 10. Recommended Next Analysis Step

Resolve open questions 1 and 2 on the Google data before freezing the canonical contract, because both change the occurrence values the contract would standardize. The step is read-only and has two parts:

1. **Trace the repeated rows.** Take a sample of the 38,146 multi-machine instance-windows and trace them back to the raw CSV. Examine their `time`, `event`, `failed` and `machine_id` patterns to decide whether they are duplicates.
2. **Measure the impact.** Compute, in memory, how occurrence peaks, requests, next-occurrence targets, the validation metrics and the N04 cell 41 selection would change under each candidate rule:
   - keeping one row per instance-window;
   - excluding FAIL, EVICT, LOST and KILL records;
   - both rules together.
