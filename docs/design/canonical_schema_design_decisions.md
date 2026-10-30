# Canonical Schema and Adapter Framework: Design Decision Record

**Date:** 2026-10-16
**Status:** Final. The design is frozen as canonical schema version 0.2.0.
**Specification:** `docs/design/canonical_workload_schema.md`. Section numbers below (§) refer to that document.

This document records **what was decided and why**. Field lists, vocabularies and per-dataset values are defined only in the specification and are not repeated here.

**Evidence base:**
- **Documents:**
  - `docs/data/alibaba_dataset_selection_feasibility.md`
  - `docs/data/dataset_inspection_and_integration_design.md`
  - `docs/data/alibaba_gpu_2020_evidence_and_limitations.md`
  - `docs/data/google_subset_pipeline_analysis.md`
- **Code (PR #70, merged into `main` at `a0b3c77`):**
  - `src/canonical/schema.py`
  - `src/adapters/base.py`, `src/adapters/validation.py`, `src/adapters/alibaba.py`
  - `config/dataset_capabilities.json`
  - `tests/test_google_canonical_contract.py`
- **Data checks:** the full official Alibaba GPU 2020 job, task and instance tables (instance-table uniqueness, retries, null `worker_name`, null times).

The adapter-side contract is in `docs/design/adapter_framework.md`.

---

## 1. Implementation status

- The design is final. No further design approval is needed before implementation.
- The Python code still implements version 0.1.0. Schema code, validators, the capability registry and JSON configuration, examples, adapters and tests will be updated in a later implementation change (§2, §14).
- The schema code, JSON configuration and examples must move to 0.2.0 together, because `test_capability_json_matches_python_registry` requires the registry and JSON file to match.

---

## 2. Decisions

### D-01. Dataset scope
**Decision.**
- Google Cluster Data 2019 (Kaggle subset) is the reference dataset.
- Alibaba GPU 2020 is the required second full integration.
- Alibaba Cluster Trace 2018 is an optional reduced demonstration.
- Azure VM is deferred (§3).

**Rationale.**
- Alibaba GPU 2020 is the only candidate with an official recurrence tag (`group`, 99.86% of jobs) and a memory peak in the same unit as the memory request.
- Alibaba 2018 has no recurrence, so it can only demonstrate instance-level request versus observed values.
- The Azure sample is V1 (2017) data despite its `v2` identifier, and has no observed memory.

**Consequence.**
- Existing dataset identifiers are kept so PR #70 tests keep passing.
- The Azure profile stays valid through defaults and is not extended.
- The Azure data must not be described as V2.

### D-02. Extend PR #70; don't replace it
**Decision.** Version 0.2.0 adds to 0.1.0 without removing or renaming any field, flag, record level, unit or validation rule. Every new capability field has a default (§2, §10).

**Rationale.**
- PR #70's core rules are correct and already tested: null never zero, a unit on every value, CPU and memory independent, capability-gated validation.
- Defaults keep the deferred Azure profile valid without new work.

### D-03. New record level `role_occurrence`
**Decision.**
- Alibaba GPU 2020 evaluation rows use a new record level, `role_occurrence`, unique on `role_key`.
- Each instance-table row is kept as its own `instance` audit row, so every retry of an instance slot is a separate row (§4.1, D-21).

**Rationale.**
- One job is one occurrence, but a job can have several task roles, and requests are set per role.
- Using `occurrence` for role rows would either duplicate `occurrence_id`, which the current uniqueness validation rejects, or change what `occurrence_id` means.
- It would also present per-role values as full-workload occurrences.

**Rejected alternatives.**
- `occurrence` with a job-level `occurrence_id`: fails validation.
- `occurrence` with a role-level `occurrence_id`: gives one column two meanings across datasets.

### D-04. Workload and recurrence identity for Alibaba GPU 2020
**Decision.**
- `workload_id = group`.
- `recurrence_key = group||task_name`, with origin `official_with_role`.
- `occurrence_id = group||job_name`.
- `role_key = group||job_name||task_name` (§5.3).

**Rationale.**
- Shared history and next-occurrence logic groups rows by `recurrence_key`. With `group` alone, `worker` and `ps` histories would mix, and a worker row's "next occurrence" could be a parameter-server row.
- Role sets are stable: 99.47% of repeated groups have the same task-role set in every job, and 99.72% of role-occurrences belong to roles present in every job of their group.
- `official_with_role` records that `group` is official and that TraceAdvisor adds `task_name`.

### D-05. Jobs without `group`
**Decision.**
- The 1,530 jobs without `group` (1,460 accepted; schema §5.3) use fallback keys: `workload_id = job_name`, `occurrence_id = job_name`, `role_key = job_name||task_name`, `recurrence_key` null.
- Every role row of these jobs gets `exclusion_reason = no_recurrence_key` (§5.3).

**Rationale.**
- A null `workload_id` fails existing validation, and a null `role_key` would escape the uniqueness check.
- These jobs have no official recurrence grouping, so they can't support recurrence-based prediction. They remain in the output for audit only.
- The two-part fallback `role_key` cannot collide with a three-part grouped key.

### D-06. `occurrence_key` is conceptual
**Decision.**
- `occurrence_key` names the concept and is stored in the canonical `occurrence_id` column.
- `role_key` is the unique role-occurrence identity (§5.1).

**Rationale.** It avoids adding a second column with the same value, and keeps the merged Google contract view unchanged.

### D-07. Literal key separators
**Decision.**
- Google and Alibaba GPU 2020 join composite keys with `||`.
- Alibaba 2018 keeps its existing `|`.
- The `‖` character in explanatory text is notation only (§5.2).

**Rationale.**
- `||` is what the Google artifacts actually store, for example `occurrence_key` and `execution_id = <collection_id>||<instance_index>||episode_<n>`.
- Matching the reference pipeline avoids a third convention.
- Alibaba 2018 is optional and unchanged.

### D-08. Instance rows inherit their parent linkage
**Decision.**
- Alibaba GPU 2020 `instance` rows inherit `workload_id`, `recurrence_key`, `occurrence_id` and `role_key` from their parent role row (§5.5, §9.4).
- Grouped jobs: `workload_id = group`, `recurrence_key = group||task_name`.
- Jobs without `group`: `workload_id = job_name`, `recurrence_key` null, `occurrence_id = job_name`, `role_key = job_name||task_name`; the parent role row carries `exclusion_reason = no_recurrence_key`.
- Eligibility is decided at the role level. Instance rows have no independent primary exclusion reason, and a null `exclusion_reason` on an instance row does not mean "eligible".
- Instance rows receive no splits, targets or history features.

**Rationale.**
- Exclusions such as `multi_attempt_worker` are decided on the role row from instance evidence, so each attempt must be traceable to its role row.
- Inheriting the same values keeps `recurrence_key` null exactly when the role has no recurrence, and keeps every audit row joinable.

### D-09. Reuse existing field names
**Decision.**
- `observed_*` means average usage and `peak_*` means peak usage.
- No new names such as `observed_cpu_avg` or `occurrence_time_us` are introduced. `start_time_us` carries the profile's ordering time (§6.1, §7).

**Rationale.**
- Fields outside the schema's resource list escape unit, non-negativity and capability checks.
- The Alibaba 2018 adapter already maps `cpu_avg` to `observed_cpu`.

### D-10. Alibaba GPU 2020 CPU is average-only
**Decision.**
- `observed_cpu` is the maximum `cpu_usage` across the role's eligible workers, a lifetime average.
- `peak_cpu` is always null, with `has_cpu_peak = false`.
- CPU results are labeled average-usage sizing, never peak-safe sizing (§6.3, §12).

**Rationale.**
- The source has no CPU peak.
- Relabeling an average as a peak would understate CPU violations.
- Separate `has_cpu_average` and `has_cpu_peak` flags are needed, because the 0.1.0 flag `supports_observed_cpu` gates average and peak together.

### D-11. Alibaba GPU 2020 memory is the maximum over eligible workers
**Decision.**
- `peak_memory` is the maximum `max_mem` across the role's eligible workers, in GB.
- `actual_memory` is the next eligible role-occurrence's `peak_memory`.
- Memory is the primary evaluated resource. Worker peaks are never summed (§6.3, §8).

**Rationale.**
- Requests are per instance and inherited by every instance of a role.
- The maximum across workers answers "what does each instance of this role need".
- Without a time-aligned series, a sum of worker peaks is only an upper bound, not a job peak.

### D-12. Units
**Decision.**
- Alibaba GPU 2020 CPU uses `percent_of_vcpu` (100 = 1 vCPU) for both request and usage.
- Memory uses `gb`.
- GPU request and utilization use `percent_of_gpu`.
- Values are not converted in the adapter. Google and Alibaba 2018 units are unchanged (§6.2).

**Rationale.**
- A unit describes scale, not meaning: "lifetime average" is recorded in semantics, not the unit.
- Keeping the source scale preserves traceability.
- One unit string on request and actual satisfies evaluator unit matching.
- `vcpu` already denotes Azure allocated capacity.

### D-13. Per-field semantics
**Decision.**
- Semantics are declared per field in the profile: observed and peak CPU, observed and peak memory, the CPU and memory targets, and time (§7).

**Rationale.** One value per resource can't describe Alibaba 2018, where `observed_cpu` is an average and `peak_cpu` is a peak.

### D-14. Explicit scope and two aggregation columns
**Decision.**
- Rows carry `resource_scope`, `request_aggregation_method` and `observed_aggregation_method` (§8).

**Rationale.**
- One adapter emits several record levels, so these are row-level columns.
- Requests and measurements aggregate differently. Google sums requests over executions but takes aligned-window sum then maximum for peaks. Alibaba GPU 2020 doesn't aggregate requests but takes the maximum over instances for observations.
- One column would misdescribe one of them.
- Making scope explicit is what keeps full-workload and per-instance values from being compared as the same thing.

### D-15. Validity, eligibility and capability are separate
**Decision.**
- **Data quality:** `validity_status`, plus the standard per-resource `cpu_validity_status` and `memory_validity_status`. Incomplete resources use `partial`.
- **Eligibility:** `exclusion_reason`, where null means eligible.
- **Capability:** the dataset profile (§9.1).

**Rationale.**
- A row can have clean data and still be ineligible, for example a role of a failed job.
- `partial` matches the existing Alibaba 2018 adapter.
- Keeping these concepts apart is what lets missing CPU coexist with valid memory evaluation.

### D-16. Missing values
**Decision.**
- Missing values stay null and are never filled with zero.
- On Alibaba GPU 2020, missing CPU on any eligible worker makes the role's `observed_cpu` null with `cpu_validity_status = partial`. The row stays eligible for memory and is left out of CPU-specific denominators.
- Invalid CPU values mark only CPU as invalid (§9.2).

**Rationale.**
- Taking the maximum over the remaining workers would silently understate CPU.
- Excluding the row would lose a valid memory observation. This affects 1,224 of the 461,900 eligible role-occurrences (0.26%).

### D-17. Alibaba GPU 2020 eligibility and exclusion rules
**Decision.**
- Fourteen ordered rules, from `no_recurrence_key` through `invalid_resource` (§9.3).
- Each row gets one primary reason: the first failed rule.
- Excluded and invalid rows stay in the output for audit and are never used for history or targets.

**Rationale.**
- Rules are ordered job → task → instance → attempt → sensor → memory, so the reason names the most basic failure.
- One reason per row gives deterministic counts.
- `multi_attempt_worker` is required because the sensor table has one row per worker, which can't be attributed to one of several attempts; attempts are separate runs, not copies.
- Full sensor coverage is mandatory for memory, because a partial maximum would be an unlabeled lower bound.
- Status rules come before `missing_worker_name`, so its primary-reason count can be zero even though missing worker values exist (D-24).

**Result (verified).**
- 462,156 role-occurrences pass every rule except `multi_attempt_worker`.
- That rule excludes 256 more.
- The final eligible population is **461,900**.

### D-18. Splits, history and split-isolated targets
**Decision.**
- **Adapters** produce current-occurrence values only.
- **Shared code** adds `split`, `actual_cpu`, `actual_memory`, and the per-resource `cpu_target_status` and `memory_target_status`.
- **History** uses eligible prior occurrences completed at or before the current start.
- **Targets** come from the next eligible occurrence within `recurrence_key`.
- **Alibaba GPU 2020** uses split-isolated targets (`target_split_isolation = true`) (§11).

**Rationale.**
- Splitting and targeting are shared logic, not dataset mapping.
- Per-resource status is needed because a row's next occurrence can have valid memory but missing CPU.
- Split isolation keeps validation from using test-period outcomes. It leaves 42,104 validation and 44,087 test rows, counted before the 256-row `multi_attempt_worker` exclusion.

**Google.**
- Google's existing targets cross split boundaries (104 of 330 validation targets fall in the test period).
- This is recorded as `target_split_isolation = false` and not changed here.
- Google targets are referenced from the existing artifacts, not recomputed.

### D-19. Evaluator and comparability
**Decision.**
- CPU and memory use separate denominators, and missing values are never counted as non-violations.
- Alibaba GPU 2020 reports no any-resource metric (`any_resource_metric_valid = false`), and baseline selection ranks memory first.
- **Baseline candidates (Alibaba GPU 2020):** Request is scored and reported as the status-quo reference but cannot be selected. The baseline and `min_runs` are selected from Mean, P90, P95 and P99 only. Selected: P99 at `min_runs = 10`.
- **ML model selection (Alibaba GPU 2020; Task 7, PR #99, confirm when merged):** CPU and memory models are selected independently on validation, accuracy first: RMSE, then MAE, then violation %, then average shortfall, then model name. A mean `DummyRegressor` is reported as a reference.
- **Hybrid (Alibaba GPU 2020; Task 7, PR #99, confirm when merged):** `max(ML prediction, selected baseline)` per resource, with negative predictions clipped to zero. Google uses `max(ML prediction, P95)` (`docs/planning/assumptions.md` P-9).
- CPU results are never compared numerically across Google and Alibaba GPU 2020 (§12, §13).

**Rationale.**
- With one resource null, the shared evaluator reports any-resource violation as 100% by construction.
- Combining an average-based CPU result with a peak-based memory result has no meaning.
- The second dataset demonstrates adaptation to a different workload and resource contract, not a better or worse score on the same task.
- **Request is not selectable** because, as the Hybrid baseline, it would stop Hybrid from ever recommending less than the current request, and its identical rows would fix `min_runs` at 1 instead of choosing it on validation. On the validation data Request has a lower memory violation rate than P99 at `min_runs = 10` (4.74% against 5.58%) but 2.5 times the memory waste (22.26 GB against 8.94 GB).
- **ML selection is accuracy-first** because the ML model's job is to predict usage accurately, and the Hybrid rule is what keeps violations low. Ranking violation first rewards over-prediction and selects the mean `DummyRegressor`, which has no predictive skill.

### D-20. GPU fields retained; GPU evaluation deferred
**Decision.**
- `requested_gpu`, `observed_gpu` and `peak_gpu_memory` are retained as optional canonical fields, along with the GPU source and provenance columns (§6.4).
- GPU baseline selection, targets, recommendations and violation metrics are outside the current experiment.

**Rationale.**
- Alibaba GPU 2020 is a GPU workload dataset, and dropping its GPU data would lose information.
- The current TraceAdvisor experiment evaluates CPU and memory.
- GPU evaluation needs its own aggregation and target semantics first, and there is no GPU-memory request to compare against.

**What is deferred.** Only GPU *evaluation*. GPU fields are preserved.

### D-21. Alibaba GPU 2020 instance identity
**Decision.**
- `instance_id = job_name||task_name||inst_name||instance_attempt_index` (§5.4).
- `instance_attempt_index` is a deterministic 1-based index within the slot `(job_name, task_name, inst_name)`. Attempts are ordered by instance start time ascending, null times last, with `source_row_number` as the tie-breaker.
- `source_row_number` is the data-line number in the checksum-verified, decompressed instance file. The loader must preserve source file order.
- Added fields: `instance_slot_key`, `instance_attempt_index`, nullable `worker_id` (from `worker_name`), `source_row_number`, and raw `source_inst_name`, `source_worker_name`, `source_status`, `source_machine`.
- The adapter does not emit `source_seq_no` on these rows, so `instance_id` is the uniqueness key under the existing validation rule.
- Every retry stays a separate instance row. `multi_attempt_worker` applies when the same non-null worker appears on more than one instance row of the role.

**Rationale.**
- `(job_name, task_name, inst_name)` repeats on 906,751 of 7,522,002 rows, because 231,632 slots are retried (corrected from 231,258; see `docs/data/alibaba_gpu_2020_source_data_checks.md` §3.7).
- An attempt index is unique by construction, separates retries, is reproducible from the verified file, and needs no change to the validator.
- `source_row_number` keeps every row traceable to its raw line.

**Rejected alternatives.**
- The slot alone: not unique.
- Adding `worker_name`: null on 331,057 rows, and 2 duplicate rows remain.
- Nullable values (`worker_name`, instance start) in the key: they need placeholder tokens, and the instance start is null on 1,773,468 rows.
- The source `inst_id`: a job-level value, equal to the job's `inst_id` on every row.
- A source row number alone: opaque, and meaningful only for one file export.
- Storing the derived attempt number in `source_seq_no`: labels a derived value as raw.

### D-22. Alibaba GPU 2020 timestamp contract
**Decision.**
- Role rows: `start_time_us` = job submission; `end_time_us` = job completion, or null (§7).
- Instance rows: `event_time_us` = parent job submission, always; `start_time_us` and `end_time_us` = the instance's own times, or null.
- Profile field `instance_event_time_semantics = parent_job_submission`.
- Task launch time and sensor time are never substitutes. Timestamps are never inferred, carried forward or fabricated.

**Rationale.**
- The parent submission time is a recorded source time used to place the audit row. It is not an invented instance start, and it is never copied into `start_time_us`.
- 1,673,976 instance rows have no own start but a parent submission; they stay valid audit rows through `event_time_us`.
- The sensor table has no timestamps, and task launch time means something different from submission.

**Rejected alternative.** Relaxing the validator so excluded rows may lack a time: it weakens an invariant that shared code relies on.

### D-23. Rejected output for jobs without a submission time
**Decision.**
- A job with no submission time is rejected whole, with all its role rows and instance rows, as `rejection_reason = missing_submission_time` (§9.5).
- Rejected records go to a separate rejected output, not to the validated `role_occurrence` or `instance` views. No orphan instance rows remain in the audit view.
- The rejected output is kept for audit only, with minimal checks: identity fields where possible, a reason present, no zero-filling, source traceability.
- It is not used for chronological splitting, history, target construction or evaluation.
- Metadata reports rejected job, role and instance counts by reason. Every source row is traceable to a validated view or to the rejected output.

**Rationale.**
- These records have no usable canonical time, so they cannot pass `validate_canonical_frame`.
- Rejecting the whole job keeps parent and child rows together.
- The volume is 3,663 jobs, 6,942 role rows and 111,219 instance rows. All are `Waiting` jobs and already ineligible, so the eligible population of 461,900 is unchanged.

### D-24. Missing `worker_name`
**Decision.**
- `worker_id` stays null when `worker_name` is missing, and is not part of the identity key.
- `missing_worker_name` is a role-level exclusion rule (rule 9).
- Instance rows have no independent primary exclusion reason. The evidence remains in the nullable `worker_id`, the raw `source_` columns, `source_status` and the parent `role_key` (§9.3, §9.4).

**Rationale.**
- All 331,057 instance rows without `worker_name` are `Waiting`, `Ready` or `Failed`, so status rules 6 and 8 normally fire first. The `missing_worker_name` count can therefore be zero; the rule is kept so that a missing worker can never pass silently.

---

## 3. Unchanged by this decision record

- **Google.** Behavior and artifacts are unchanged: full-workload occurrences, constructed recurrence, all rows `valid`, targets crossing splits. Any change follows the Google Subset Pipeline Analysis report.
- **Alibaba 2018.** The adapter's identity, units and validity behavior stay at 0.1.0. A full upgrade happens only if the optional demonstration is scheduled.
- **Azure.** Profile and adapter are unchanged and deferred.

## 4. Implementation and future scope

Listed in full in §14 of the specification. In summary:
- **Implementation:**
  - schema code, validators, JSON configuration and examples;
  - the Alibaba GPU 2020 adapter, including the instance identity fields, the timestamp contract and the rejected output;
  - a rejected output in the adapter result, with its minimal checks;
  - the shared target builder;
  - tests;
  - the group-weighted sensitivity result.
- **Future scope:**
  - GPU evaluation;
  - Azure;
  - the full Alibaba 2018 upgrade;
  - multiple exclusion reasons per row;
  - job-level summary rows;
  - display unit conversion;
  - any Google behavior change.
