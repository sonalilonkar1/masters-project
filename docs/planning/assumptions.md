# TraceAdvisor Project Assumptions

**Status:** Current. Updated 2026-10-17. It replaces the earlier v0 assumptions in this file and the generated `assumptions2.md` (section 7).

This document lists the working assumptions the project relies on, in one place. It does not define the contract. Where an assumption comes from a frozen design decision, the authoritative source is named, and that source wins if the two ever differ:
- `docs/design/canonical_workload_schema.md` (schema 0.2.0, "schema §")
- `docs/design/adapter_framework.md` ("framework §")
- `docs/design/canonical_schema_design_decisions.md` ("D-nn")
- `docs/planning/data_integration_tasks.md` (tasks, priorities and the six-day schedule)
- `docs/data/google_subset_pipeline_analysis.md` (Google findings "F-nn")

---

## 1. Project-level assumptions

| # | Assumption | Source |
|---|---|---|
| P-1 | Google Cluster Data 2019 (Kaggle subset) is the reference pipeline. Alibaba GPU 2020 is the required second full integration. Alibaba 2018 is optional. Azure is deferred future work | Schema §3; D-01 |
| P-2 | Raw datasets are never merged into one dataframe, and models are trained per dataset. A fitted Google model is never reused on another dataset | Schema §1 |
| P-3 | Each dataset keeps its own semantics. Google recurrence logic is not applied to Alibaba data, and no recurrence is invented for a dataset that lacks one | Schema §1, §5.3 |
| P-4 | CPU and memory are evaluated independently, with separate valid-row denominators | Schema §1, §12 |
| P-5 | Missing and unsupported values stay null. They are never filled with zero and never counted as non-violations | Schema §1, §9.2, §12 |
| P-6 | Every populated resource value carries an explicit unit; values keep their source scale | Schema §6.2 |
| P-7 | GPU fields are retained. GPU-resource recommendation and GPU-resource evaluation are out of scope; CPU and memory ML, Hybrid and final-test evaluation are required | Schema §6.4; D-20 |
| P-8 | Results from different datasets are never combined into one accuracy ranking, and CPU results are never compared numerically across Google and Alibaba GPU 2020 | Schema §13 |
| P-9 | Policies compared: Request, Mean, P90, P95, P99, ML-only and Hybrid. Hybrid starts from `max(ML prediction, P95)`, applied per resource | `data_integration_tasks.md`, Task 7 |
| P-10 | All selection uses train and validation only. Every decision is locked in a manifest before the test split is read, the final test runs exactly once, and nothing is tuned afterwards | `data_integration_tasks.md`, Tasks 6–7 |
| P-11 | Splits are chronological 70/15/15 on each dataset's ordering time | Schema §11 |

---

## 2. Google subset (reference pipeline)

These describe the current pipeline in `pipelines/google_subset/` (Notebooks 00–04) and its artifacts in `data/processed/google_subset_v1/`. They are not changed by the schema 0.2.0 work; any change goes through the Google correction (Task 9).

### 2.1 Ingest and units
- The input is 405,894 raw observation rows, each one machine and roughly one five-minute usage window.
- CPU stays in Google normalized compute units (`ncu`) and memory in Google normalized units (`normalized`). There is **no conversion** to cores or GB, and the unit is written into column names (`*_ncu`, `*_normalized`).
- A usage window's duration is a measurement window, not an execution runtime.

### 2.2 Execution reconstruction (Notebook 02)
- Candidate group: `candidate_instance_key = collection_id||instance_index` (242,946 groups).
- A new execution episode starts when the gap since the previous window in the same group is **more than five minutes**. The smallest positive gap observed is 25 minutes. A machine change alone does not start a new episode.
- `execution_id = candidate_instance_key||episode_<n>` (253,585 executions).
- Execution peaks sum usage across machines within each window, then take the maximum window.

### 2.3 Recurrence
- `recurrence_key = user_clean||logical_workload_name` (2,280 keys; 1,504 with more than one execution). `recurring_job_id` is kept as an alias.
- `user_clean` is `user`, or `unknown_user` when missing.
- `logical_workload_name` is `collection_logical_name`, falling back to `collection_name`, then to `unknown_job`.
- The rule assumes that the same user and logical name mean repeated runs of the same workload. It is a constructed key (`recurrence_key_origin = constructed`), not an official one.

### 2.4 Occurrences
- `occurrence_key = recurrence_key||execution_start_time_us`; executions of one recurrence that start at the same time form one occurrence (4,879 occurrences). `occurrence_id` is an alias of `occurrence_key`.
- Occurrence peaks are full-workload values: CPU and memory are summed across parallel executions within each aligned window, and the largest window total is the peak. A missing component leaves the peak unknown (NaN).
- Occurrence requests are summed across executions.

### 2.5 History
- History is point-in-time: it uses only earlier occurrences of the same `recurrence_key` whose end time is at or before the current occurrence's start (Notebook 03).
- History counts are per resource (`hist_peak_cpu_count`, `hist_peak_memory_count`) and count completed occurrences, not execution rows. Missing memory history never removes usable CPU history.
- Historical statistics: mean, standard deviation, P90, P95 and P99 of past occurrence peaks.

### 2.6 Splits, baselines and targets (Notebook 04)
- The chronological split is 70/15/15 on `execution_start_time_us`. It preserves groups, so no `occurrence_key` crosses a boundary (3,473 / 675 / 731 occurrences).
- A historical policy uses history only when at least `min_runs` valid completed occurrences exist for that resource; otherwise it falls back to the current occurrence's request. Candidates are `min_runs` 1, 3, 5 and 10.
- The target is the next occurrence's full-workload CPU and memory peak within the same `recurrence_key` (`target_cpu_next_occurrence_peak_ncu`, `target_memory_next_occurrence_peak_normalized`). The last occurrence of a recurrence has no target.
- The current validation selection is P99 with `min_runs = 1`, over a common population of 329 validation occurrences. It is a **preliminary** result.

### 2.7 Known limitations, recorded and not yet corrected
- **Targets cross splits (F1, F3, F5).** Targets are built before split assignment, so 104 of the 330 validation targets fall in the test period (`target_split_isolation = false`). The correction is Task 9.
- **Abnormal runs are included (F7).** Failed, evicted, lost and killed records are kept, every row is treated as `valid`, and there is no completion flag.
- **Possible double counting (F8).** Identical values repeated across machines are summed. This may overstate peaks and requests for about a quarter of occurrences.
- **Mixed runtime units (F11):** seconds in history, microseconds in occurrences.
- **Unused size (F12).** The next occurrence's execution count is saved but not used.
- **Notebook 05 is empty (F6).**
- **Known test failure.** `test_google_train_target_nulls_are_preserved` fails on the local artifacts (1,463 vs 1,801). It is a separate Google issue.

---

## 3. Alibaba GPU 2020 (required second integration)

Defined by the frozen design; summarized here so the assumptions are in one place.

| Area | Assumption | Source |
|---|---|---|
| Source | Full official `cluster-trace-gpu-v2020` tables, checksum-verified. `source_row_number` is the data-line number in the decompressed instance file, and the loader preserves file order | Framework §5, §9.2; D-21 |
| Workload and recurrence | `workload_id = group`; `recurrence_key = group||task_name` (`official_with_role`). The 1,530 jobs without `group` (1,460 accepted) use fallback keys and are excluded as `no_recurrence_key` | Schema §5.3; D-04, D-05 |
| Evaluation unit | One `role_occurrence` row per task role per job, plus `instance` audit rows (one per instance-table row, every retry kept) | Schema §4.1; D-03 |
| Time | Role rows are ordered by job submission. Instance rows carry the parent submission in `event_time_us`. Timestamps are never inferred or substituted. Jobs without a submission time go whole to the rejected output | Schema §7, §9.5; D-22, D-23 |
| Memory | Primary resource: per-instance lifetime peak in GB, the maximum over the role's eligible workers; worker peaks are never summed | Schema §6.3, §8; D-11 |
| CPU | Lifetime-average usage in `percent_of_vcpu`, the maximum over eligible workers. **No CPU peak exists**, so `peak_cpu` is always null and CPU results are average-usage sizing, not peak-safe sizing. Missing CPU on any eligible worker makes the role's CPU null without affecting memory | Schema §6.3, §9.2; D-10, D-16 |
| Eligibility | 14 ordered exclusion rules with one primary reason per row; 461,900 eligible role-occurrences. Excluded rows stay in the output for audit | Schema §9.3; D-17 |
| Targets | Next eligible role-occurrence within `recurrence_key`, split-isolated (`target_split_isolation = true`); about 42,104 validation and 44,087 test rows before the final 256-row exclusion | Schema §11; D-18 |
| Reporting | Memory first; no any-resource metric; the selection bias, the roughly 50-day telemetry window, and the mostly single-instance roles are reported as limitations | Schema §3, §12; D-19 |

---

## 4. Alibaba 2018 and Azure

- **Alibaba Cluster Trace 2018 (optional):**
  - instance-level output from the existing 0.1.0 adapter;
  - no recurrence key is invented, so no next-occurrence result is claimed;
  - attempted only after the complete Alibaba GPU 2020 result (Task 8).
- **Azure public VM (deferred):**
  - the `azure_public_vm_v2` identifier is kept, but the sample data matches the V1 (2017) release and must not be described as V2;
  - there is no observed memory;
  - no Azure implementation happens in the current schedule (Task 10).

---

## 5. Evaluation assumptions

- **Comparing like with like.** Actual and recommended values must use the same unit string and the same scope (schema §8, §12).
- **Any-resource metrics** are reported only where the dataset profile allows them. For Alibaba GPU 2020 they are not reported.
- **Intermediate versus final results.** Validation results (baselines, ML, Hybrid) are intermediate. Final numbers come only from the single locked final test of each dataset.

---

## 6. Confirmed implementation choices

These choices for the PR #70 schema follow-up were left open by the design documents and confirmed on 2026-10-17. The evidence for each is in `docs/planning/github_issues/pr70_schema_followup_review.md` §8.2:
- `telemetry_window` is a string;
- Alibaba 2018 `cpu_unit` is null, because its CPU request and usage use different units; its `memory_unit` is `alibaba_memory_source_normalized`;
- a null `supported_record_levels` means no restriction; an empty `allowed_exclusion_reasons` means every `exclusion_reason` must be null;
- defaults: `recurrence_key_origin = none`, `any_resource_metric_valid = true`, `target_split_isolation = false`;
- non-null `role_key` and `instance_id` on instance rows are enforced only for profiles that declare `role_occurrence`; Alibaba 2018 and Azure behavior is unchanged.

---

## 7. Superseded v0 assumptions

The earlier version of this file (v0) and `assumptions2.md` described the Sprint 1–2 pipeline. They are replaced as follows.

| v0 assumption | Current position |
|---|---|
| `recurring_job_id = user_clean||collection_logical_name`, with `unknown_user` / `unknown_job` fallbacks | Kept as `recurrence_key`, with `collection_name` as an additional fallback before `unknown_job` (section 2.3). `recurring_job_id` remains an alias |
| Confidence tiers (`cold_start`, `high`, `medium`, `low`) from run count and peak stability | Not produced by the current Google notebooks. History sufficiency is handled by the resource-specific history counts and `min_runs` (section 2.6). Legacy references remain in `src/eval/evaluator_v0.py` and `src/features/feature_config.py` (`hist_confidence_tier`) |
| `n_history = groupby(recurrence_key).cumcount()` over executions | Replaced by point-in-time, per-resource counts of completed prior occurrences (section 2.5) |
| `job_metrics_v0.parquet` (execution level) and `job_profiles_confidence_v0.parquet` (job level) | Execution features remain in `job_metrics_v0.parquet`; occurrence history comes from `job_profiles_google_subset_history_v1.parquet`; split artifacts are `{train,val,test}_occurrences.parquet` |
| CPU and memory "normalization factor to cores / GB = 1.0"; `req_mem_gb` / `peak_mem_gb` naming | Values stay in Google `ncu` and `normalized` units and are not converted (section 2.1) |
| `execution_id = collection_id + '_' + instance_index`, start = min, end = max | Replaced by gap-based episodes: `collection_id||instance_index||episode_<n>` (section 2.2) |
| `recurrence_key` carried forward as the first observed key per execution | Still how identity is attached in Notebook 02 (first value per `execution_id`) |
| Fixed, hand-chosen thresholds | Replaced by validation-only selection of the baseline and `min_runs` |

`assumptions2.md` was written automatically by `notebooks/subset/subset-04-sprint2.ipynb` (it appends to `docs/planning/assumptions2.md`). Rerunning that old notebook recreates the file; the notebook itself has not been changed.
