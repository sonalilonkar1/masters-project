# Canonical Workload Interface and Schema

**TraceAdvisor 295B — New Development Issue 2**  
**Schema version:** `0.2.0` (frozen design). The Python implementation is still `0.1.0`; see [section 2](#2-schema-version-and-implementation-status).

---

## 1. Purpose and scope

Provide one common semantic contract for adapters, ML preparation, policy logic, the shared evaluator, API, and UI without forcing Google-specific assumptions onto other datasets.

### Core rules
- Workload identity and recurrence identity are separate.
- Request, allocation, observation, peak, actual/target, and recommendation are separate semantics.
- CPU and memory support are independent.
- Missing and unsupported values remain null; they are never converted to zero.
- Every populated resource value carries an explicit unit. A request and the actual it is compared with use the same unit string.
- Shared field names do not imply identical semantics across datasets. Each dataset profile declares semantics, units, scope and aggregation ([sections 7](#7-resource-semantics), [8](#8-resource-scope-and-aggregation) and [10](#10-capability-metadata)).
- Average and peak are never interchanged. An average is never written to a `peak_*` field.
- Data quality, eligibility and dataset capability are three separate concepts ([section 9](#9-validity-missingness-and-exclusions)).
- Ineligible and invalid rows are kept in the output for audit; they are never silently deleted. Records that have no usable canonical time go to a separate rejected output instead of a validated view ([section 9.5](#95-alibaba-gpu-2020-rejected-output)); they are also never silently deleted.
- Timestamps are never inferred, carried forward or fabricated.
- Adapters map source data into canonical fields; they do not calculate historical percentiles, ML predictions, Hybrid decisions, confidence, evaluator metrics, splits, or next-occurrence targets. Google's precomputed targets are referenced from existing artifacts, not computed by an adapter.
- Shared evaluator code consumes canonical names, not raw dataset columns.
- Datasets are never merged into one training dataframe. Models are trained per dataset.

---

## 2. Schema version and implementation status

**Design status.** The canonical design in this document is **frozen as planned schema version 0.2.0**. No further design approval is required before implementation.

Version 0.2.0 **extends** 0.1.0. No existing field, flag, record level, unit or validation rule is removed or renamed.

**Implementation status.** This document does not modify code. The repository still implements 0.1.0:

| Component | Current state (0.1.0) | Required 0.2.0 change (later implementation) |
|---|---|---|
| `src/canonical/schema.py` | `SCHEMA_VERSION = "0.1.0"`; five record levels; 10 capability flags; nine allowed units; GPU fields not in the resource field list | Version bump; `role_occurrence`; `role_key`; new capability fields with defaults; units `percent_of_vcpu` and `percent_of_gpu`; GPU resource fields; per-resource validity, exclusion and target-status vocabularies; gate `peak_cpu` by `has_cpu_peak` |
| `src/adapters/validation.py` | Uniqueness rules for five levels; unknown levels are skipped without a check | Uniqueness rule for `role_occurrence`; vocabulary checks for scope, aggregation, exclusion reasons and target statuses |
| `config/dataset_capabilities.json` | Three profiles at 0.1.0 | Add the Alibaba GPU 2020 profile and the new fields; bump the version |
| `examples/canonical_records.jsonl` | Three example rows at 0.1.0 | Update to 0.2.0; add Alibaba GPU 2020 examples |
| Adapters | Alibaba 2018 and Azure adapters at 0.1.0; no Alibaba GPU 2020 adapter; `AdapterResult` has no rejected output | Implement the Alibaba GPU 2020 adapter; add the rejected output ([section 9.5](#95-alibaba-gpu-2020-rejected-output)) |
| Shared target builder | Not implemented for canonical data | Implement splits, history, targets and per-resource target statuses ([section 11](#11-splits-history-and-targets)) |
| Tests | 0.1.0 tests, including `test_capability_json_matches_python_registry` | Update together with schema code, configuration and examples, so the registry and JSON stay identical |

The schema code, JSON configuration and examples must move to 0.2.0 in one change. The full list of later work is in [section 14](#14-deferred-implementation-work-and-out-of-scope-items).

---

## 3. Dataset profiles

| Dataset | `dataset_id` | Source version | Status | Evaluation level | Recurrence | Resource limitations | Current project role |
|---|---|---|---|---|---|---|---|
| Google Cluster Data 2019, Kaggle subset | `google_clusterdata2019` | Kaggle subset; corrected artifacts in `data/processed/google_subset_v1` | Implemented (artifacts) | `occurrence` | Constructed by TraceAdvisor | No occurrence-level average CPU in the artifacts; normalized units | Reference pipeline |
| Alibaba GPU 2020 | `alibaba_gpu_v2020` | `cluster-trace-gpu-v2020`, full official tables | Design frozen; adapter to be implemented | `role_occurrence` (plus `instance` audit rows) | Official `group`, extended with the task role | **No CPU peak**; CPU is lifetime-average only; telemetry about day 19 to day 68.9 | Required second full integration |
| Alibaba Cluster Trace 2018 | `alibaba_clustertrace2018` | `cluster-trace-v2018` (`batch_task`, `batch_instance`) | Optional; 0.1.0 adapter exists | `instance` | None | No recurrence, so no next-occurrence targets | Optional integration demonstration |
| Azure public VM | `azure_public_vm_v2` (identifier retained) | The current sample matches the **V1 (2017)** release, not V2 | Deferred | — | None | No observed memory; allocation buckets only; no request | Deferred |

### Google Cluster Data 2019 (reference pipeline)
- Full-workload occurrence evaluation: requests and peaks are summed across the executions of an occurrence.
- Recurrence is constructed by the existing Google pipeline as `user||collection_logical_name`.
- The current Google artifacts remain unchanged by this schema update. `tests/test_google_canonical_contract.py` checks the canonical view of them.
- Known pipeline properties, tracked in the Google Subset Pipeline Analysis report and not changed here:
  - abnormal events (failed, evicted, lost, killed) are included and every row is `valid`;
  - targets can cross split boundaries (104 of the 330 validation targets fall in the test period);
  - the scored validation population is 329 occurrences.

### Alibaba GPU 2020 (required second full integration)
- The official `group` field is the workload grouping source (99.86% of accepted jobs; 1,530 jobs have none, 1,460 of them accepted).
- Evaluation is at task-role level: one row per task role per job ([section 4](#4-record-levels-and-terminology)).
- **Memory is the primary evaluated resource** (per-instance lifetime peak, GB).
- **CPU is lifetime-average usage only. No CPU peak is available.**
- GPU fields are retained. GPU recommendation and GPU evaluation are outside the current experiment scope ([section 6.4](#64-gpu-fields-and-gpu-scope)).
- Every result must report these limitations (details in `docs/data/alibaba_gpu_2020_evidence_and_limitations.md`, section 5):
  - selection bias: only successfully completed, fully observed workloads are evaluated;
  - 96.7% of eligible role-occurrences are single-instance; the 15,396 eligible multi-instance role-occurrences are reported as a labeled subgroup;
  - only about 50 of the 68.9 trace days have telemetry;
  - very large groups (one has 22,641 jobs; the median has 1): report occurrence-weighted results plus a group-weighted sensitivity result.
- Recommendations are per instance. The number of instances (`inst_num`) is not predicted.

### Alibaba Cluster Trace 2018 (optional)
- Optional integration demonstration with instance-level adapter output.
- No recurrence key is invented.
- No full next-occurrence experiment unless recurrence semantics are later approved.
- Must not be used to define the recurrence-based pipeline.

### Azure public VM (deferred)
- The existing `azure_public_vm_v2` profile and adapter are retained for compatibility.
- The current sample data matches the V1 (2017) release (core and memory values, subscription and deployment counts, and file count match V1). It must not be described as V2 data. Resolve the identity before any future Azure work.
- Azure capability flags stay unchanged and remain valid in 0.2.0, because every new schema field has a default.

Results across datasets are not directly comparable ([section 13](#13-cross-dataset-comparability)).

---

## 4. Record levels and terminology

### 4.1 Record levels
Retained from 0.1.0: `workload`, `occurrence`, `execution`, `instance`, `interval`.  
Added in 0.2.0: **`role_occurrence`**.

| Dataset | Evaluation rows | Supporting rows |
|---|---|---|
| Google | `occurrence` | — |
| Alibaba GPU 2020 | `role_occurrence` | `instance` audit rows (one per instance-table row, so every retry of an instance slot is its own row) |
| Alibaba 2018 | `instance` | — |
| Azure (deferred) | — | `instance` and `interval` (existing adapter) |

**Why Alibaba GPU 2020 needs `role_occurrence`:**
- One job submission is one workload occurrence.
- One job can contain several task roles (for example `worker` and `ps`).
- One evaluation row represents one task role within one job.
- Several task-role rows must not share one unique occurrence identifier.
- Using `occurrence` for these rows would misrepresent the evaluation unit as a full-workload occurrence, and it would conflict with the current uniqueness validation, which requires a unique `occurrence_id` per `occurrence` row.

Alibaba GPU 2020 role rows are **not** full-workload occurrence rows.

| Record level | Uniqueness key |
|---|---|
| `occurrence` | `occurrence_id` |
| `role_occurrence` | `role_key` |
| `instance` | `(instance_id, source_seq_no)` when `source_seq_no` is present, otherwise `instance_id` |
| `execution` | `(execution_id, start_time_us)` when `start_time_us` is present, otherwise `execution_id` |
| `interval` | `(instance_id, event_time_us)` |

The Alibaba GPU 2020 adapter does not emit `source_seq_no` on its instance rows, so `instance_id` alone is their uniqueness key ([section 5.4](#54-alibaba-gpu-2020-instance-identity)).

### 4.2 Terminology

| Term | Definition |
|---|---|
| **Workload** | The logical recurring workload when recurrence exists; otherwise the source job |
| **Occurrence** | One run of a workload; the unit by which history and targets advance |
| **Execution** | A source-level run unit below an occurrence |
| **Task** | One row of a source task table inside one job |
| **Task role** | A task name that has the same function across the occurrences of one workload |
| **Role occurrence** | One task role within one occurrence; the Alibaba GPU 2020 evaluation unit |
| **Instance** | One running copy of a task. For Alibaba GPU 2020, one instance-table row: one attempt of one instance slot |
| **Instance slot** | Alibaba GPU 2020 only: one `(job_name, task_name, inst_name)` position. A slot that is retried has several instance rows |
| **Interval** | A fixed time-window measurement row |

| Term | Google | Alibaba GPU 2020 | Alibaba 2018 |
|---|---|---|---|
| Workload | Logical recurrence identified by the Google recurrence key | Official `group` | Source job (`job_name`), because recurrence is unavailable |
| Occurrence | Executions of one recurrence that start at the same time | One job submission | Not applicable |
| Execution | Episode of `collection_id` and `instance_index`, split on a 5-minute gap | Source task (`job_name`, `task_name`) on instance rows | Source task (`job_name`, `task_name`) |
| Task | Not applicable | `(job_name, task_name)` | `(job_name, task_name)` |
| Task role | Not applicable | `task_name` within a `group` (`worker`, `ps`, `tensorflow`, …) | Not applicable: task names are DAG positions such as `M1`, not roles |
| Role occurrence | Not applicable | One `task_name` within one job | Not applicable |
| Instance | Not used | One attempt of an instance slot (one instance-table row) | One source instance or retry attempt (`seq_no`) |
| Interval | Not used | Not used: sensor values are lifetime summaries | Not used |

**Scope warning.** Google `occurrence` rows describe the full workload (summed across executions). Alibaba GPU 2020 `role_occurrence` rows describe what each instance of one role needs. They must not be compared as identical measurements.

---

## 5. Identity fields and keys

### 5.1 Field definitions

| Field | Definition |
|---|---|
| `workload_id` | Required, never null. The workload as defined in [section 4.2](#42-terminology) |
| `recurrence_key` | The key that history and next-occurrence targets group by, at the evaluation row's level. Null when recurrence is unavailable |
| `occurrence_key` | **Conceptual** key of one occurrence. It is not a separate canonical column; its value is stored in `occurrence_id` |
| `occurrence_id` | Canonical column holding the `occurrence_key` value. On `occurrence` rows it is unique; on `role_occurrence` rows it repeats across the roles of one job |
| `role_key` | Unique identity of a `role_occurrence` row. Also populated on Alibaba GPU 2020 `instance` audit rows, so each instance can be traced to its parent role-occurrence row |
| `execution_id` | Source sub-run identifier |
| `instance_id` | One instance or attempt. Unique per `instance` row |

### 5.2 Literal separators
Keys are stored as plain strings joined with a literal separator.

| Dataset | Literal separator | Evidence |
|---|---|---|
| Google | `\|\|` (two vertical bars) | Corrected artifacts, e.g. `recurrence_key = <user>\|\|<collection_logical_name>`, `execution_id = <collection_id>\|\|<instance_index>\|\|episode_<n>` |
| Alibaba GPU 2020 | `\|\|` (two vertical bars), used for every composite key | Chosen to match the reference pipeline |
| Alibaba 2018 | `\|` (one vertical bar) | Existing adapter (`execution_id = job_name\|task_name`); unchanged |

Any double-bar character (`‖`) used in other documents' explanatory examples is notation only, not the stored separator.

### 5.3 Key values by dataset

| Field | Google | Alibaba GPU 2020 | Alibaba GPU 2020, job without `group` | Alibaba 2018 |
|---|---|---|---|---|
| `workload_id` | Google recurrence key | `group` | `job_name` (fallback) | `job_name` |
| `recurrence_key` | `user\|\|collection_logical_name` | `group\|\|task_name` | Null | Null |
| `occurrence_key` (conceptual) | `recurrence_key\|\|execution_start_time_us` | `group\|\|job_name` | `job_name` | — |
| `occurrence_id` | `occurrence_key` | `occurrence_key` | `occurrence_key` | Null |
| `role_key` | Null | `group\|\|job_name\|\|task_name` | `job_name\|\|task_name` (fallback) | Null |
| `execution_id` | Reconstructed execution identifier (`collection_id\|\|instance_index\|\|episode_<n>`) | `job_name\|\|task_name` on instance rows; null on role rows | Same as grouped jobs | `job_name\|task_name` |
| `instance_id` | Null | `job_name\|\|task_name\|\|inst_name\|\|instance_attempt_index` on instance rows; null on role rows ([section 5.4](#54-alibaba-gpu-2020-instance-identity)) | Same as grouped jobs | `instance_name` |

**Why `recurrence_key` includes `task_name` for Alibaba GPU 2020.** Shared history and next-occurrence logic groups rows by `recurrence_key`. If the key were `group` alone, the history of a `worker` role would mix with the history of a `ps` role and other roles in the same group, and the "next occurrence" of a worker row could be a parameter-server row. Adding `task_name` keeps each role's history separate. This is supported by the data: 99.47% of repeated groups have the same task-role set in every job, and 99.72% of role-occurrences belong to roles present in every job of their group.

**Jobs without `group` (1,530 jobs; 1,460 accepted).**
- Counts from the full source tables (Task 3 source data checks, 2026-10-23): 1,530 jobs have no group-tag row. 70 of them have no submission time and are rejected whole (section 9.5); the other 1,460 accepted jobs use the fallback keys. Group coverage among accepted jobs is 99.8612%.
- The earlier figure of 469 was the difference between the job-table and group-tag row counts (1,055,501 − 1,055,032). It is not a job count, because 1,061 group-tag rows match no job.
- No official recurrence grouping is available, so these jobs cannot support recurrence-based prediction.
- The fallbacks in the table above keep `workload_id` and `role_key` non-null. A null `workload_id` would fail validation, and a null `role_key` would escape the uniqueness check.
- Every role row of these jobs has `exclusion_reason = no_recurrence_key`.
- The rows stay in the output for audit and are excluded from recurrence history and next-occurrence target construction.
- The fallback `role_key` (two parts) cannot collide with a grouped `role_key` (three parts).

**Alibaba 2018.** The existing adapter identity behavior is retained. No recurrence key is invented.

### 5.4 Alibaba GPU 2020 instance identity

```
instance_id = job_name||task_name||inst_name||instance_attempt_index
```

**Why the slot alone is not enough.** In the full official instance table (7,522,002 rows), `(job_name, task_name, inst_name)` repeats on 906,751 rows because failed or interrupted instances are retried in the same slot (231,632 slots have more than one row; 6,846,883 distinct slots). Every retry is kept as a separate instance row.

**Attempt index**
- `instance_attempt_index` is a deterministic, 1-based integer within the slot `(job_name, task_name, inst_name)`.
- Attempts are ordered by:
  1. instance start time, ascending, with null start times last;
  2. then `source_row_number`, ascending, as the tie-breaker.
- `source_row_number` is the data-line number in the checksum-verified, decompressed `pai_instance_table.csv`. The loader must preserve source file order.
- The same verified file therefore always produces the same `instance_id` values.

**Instance fields**

| Field | Kind | Definition |
|---|---|---|
| `instance_id` | Identity | As above. The uniqueness key of Alibaba GPU 2020 `instance` rows |
| `instance_slot_key` | Derived | `job_name\|\|task_name\|\|inst_name`. Groups the attempts of one slot |
| `instance_attempt_index` | Derived | Attempt number within the slot, as above |
| `worker_id` | Mapped, nullable | `worker_name`. Null when `worker_name` is missing. Used as the sensor join key and for the `multi_attempt_worker` rule |
| `source_row_number` | Provenance | Data-line number in the verified instance file |
| `source_inst_name`, `source_worker_name`, `source_status`, `source_machine` | Raw source values | Unchanged source values, with nulls preserved |

**Identity rules**
- `worker_name` and nullable timestamps are never placed directly in the identity key. `worker_name` is null on 331,057 rows and the instance start on 1,773,468 rows; a key built from them would need placeholder tokens. `worker_name` also does not separate every retry: one worker can occupy the same slot twice.
- The source `inst_id` column is not used as the row identity. It is a job-level value, equal to the job's `inst_id` on every instance row.
- A source row number alone is not used as the identity. It is opaque and meaningful only for one file export; it is kept as provenance.
- The Alibaba GPU 2020 adapter does not emit `source_seq_no` on instance rows, so `instance_id` alone is the uniqueness key under the existing validation rule. The attempt index is derived, so it is not stored in a `source_` column.
- Each retry stays a separate instance row. The `multi_attempt_worker` exclusion applies when the same non-null `worker_id` appears on more than one instance row of the role.

### 5.5 Alibaba GPU 2020 instance-row parent linkage
Instance rows inherit these fields from their parent role row, so every audit row can be joined to its role:

| Field | Grouped job | Job without `group` |
|---|---|---|
| `workload_id` | `group` | `job_name` (fallback) |
| `recurrence_key` | `group\|\|task_name` | Null |
| `occurrence_id` | `group\|\|job_name` | `job_name` |
| `role_key` | `group\|\|job_name\|\|task_name` | `job_name\|\|task_name` |

For jobs without `group`, the parent role row carries `exclusion_reason = no_recurrence_key`. The instance rows keep the same parent linkage.

---

## 6. Resource fields and units

### 6.1 Resource fields

| Class | Fields |
|---|---|
| Requested | `requested_cpu`, `requested_memory`, `requested_gpu` |
| Allocated | `allocated_cpu`, `allocated_memory` |
| Observed (average usage) | `observed_cpu`, `observed_memory`, `observed_gpu` |
| Peak | `peak_cpu`, `peak_memory`, `peak_gpu_memory` |
| Evaluator actuals | `actual_cpu`, `actual_memory` |
| Recommendations | `recommended_cpu`, `recommended_memory` |

- `observed_*` holds **average usage**; `peak_*` holds **peak usage**.
- Each populated resource field has `<field>_unit`.
- Shared field names do not imply identical semantics across datasets. The dataset profile declares each field's semantics ([section 7](#7-resource-semantics)), and each row declares its scope and aggregation ([section 8](#8-resource-scope-and-aggregation)).
- `requested_gpu`, `observed_gpu` and `peak_gpu_memory` are new in 0.2.0.

### 6.2 Units
Every populated value carries its own unit. The schema does not force one universal unit. Request and actual values used together by the evaluator must use matching unit strings.

| Unit | Meaning | Used by |
|---|---|---|
| `ncu` | Google normalized compute units | Google CPU |
| `normalized` | Google normalized memory | Google memory |
| `cpu_core` | CPU cores | — |
| `vcpu` | Virtual CPUs | Azure allocated CPU (deferred) |
| `gb` | Gigabytes | Alibaba GPU 2020 memory and GPU memory; Azure allocated memory (deferred) |
| `percent` | Percent utilization | Azure observed CPU (deferred) |
| **`percent_of_vcpu`** (new) | Percent of one vCPU: 100 = 1 vCPU, 600 = 6 vCPU | Alibaba GPU 2020 CPU request and usage |
| **`percent_of_gpu`** (new) | Percent of one GPU: 100 = 1 GPU | Alibaba GPU 2020 GPU request and GPU utilization (retained, not evaluated) |
| `alibaba_plan_cpu_100_per_core` | Alibaba 2018 CPU request (100 = 1 core) | Alibaba 2018 |
| `alibaba_cpu_usage_source_unit` | Alibaba 2018 CPU usage in source units | Alibaba 2018 |
| `alibaba_memory_source_normalized` | Alibaba 2018 normalized memory | Alibaba 2018 |

- A unit describes **scale, not meaning**. That Alibaba GPU 2020 CPU is a lifetime average is recorded in its semantics, not its unit.
- Alibaba GPU 2020 values keep the source scale and are not converted (for example to `vcpu`) in the adapter.
- Alibaba 2018 keeps its current source-specific units until that optional adapter is revised. Its CPU request and CPU usage use different unit strings. That is acceptable while Alibaba 2018 targets are unsupported, and must be unified before any Alibaba 2018 targets are enabled.

### 6.3 Dataset resource mappings

**Google** (unchanged; checked by `tests/test_google_canonical_contract.py`):
- `requested_cpu`, `requested_memory` → occurrence request sums (`ncu`, `normalized`)
- `peak_cpu`, `peak_memory` → occurrence full-workload peaks
- `actual_cpu` → `target_cpu_next_occurrence_peak_ncu`
- `actual_memory` → `target_memory_next_occurrence_peak_normalized`
- `observed_cpu`, `observed_memory` → not populated (no occurrence-level averages in the artifacts)

**Alibaba GPU 2020** (`role_occurrence` rows):

| Field | Source and rule | Unit |
|---|---|---|
| `requested_cpu` | Task `plan_cpu` (per instance) | `percent_of_vcpu` |
| `requested_memory` | Task `plan_mem` (per instance) | `gb` |
| `requested_gpu` | Task `plan_gpu` (per instance), retained | `percent_of_gpu` |
| `observed_cpu` | Maximum `cpu_usage` across the role's eligible workers; a lifetime average. Null if any eligible worker's `cpu_usage` is missing | `percent_of_vcpu` |
| `peak_cpu` | **Always null**: no CPU peak exists in the source | — |
| `observed_memory` | Maximum `avg_mem` across eligible workers, when available | `gb` |
| `peak_memory` | Maximum `max_mem` across eligible workers; a per-instance lifetime peak | `gb` |
| `observed_gpu` | Maximum `gpu_wrk_util` across eligible workers; retained, not evaluated | `percent_of_gpu` |
| `peak_gpu_memory` | Maximum `max_gpu_wrk_mem` across eligible workers; retained, not evaluated | `gb` |
| `actual_cpu` | The next eligible role-occurrence's `observed_cpu`; added by shared code | `percent_of_vcpu` |
| `actual_memory` | The next eligible role-occurrence's `peak_memory`; added by shared code | `gb` |

On `instance` audit rows the same fields hold each worker's own source values, without aggregation.

- **Alibaba GPU 2020 CPU results are average-usage sizing, not peak-safe sizing.**
- Missing CPU remains null. It removes the row from CPU-specific denominators but does not exclude it from memory evaluation.
- Memory is the primary evaluated resource.
- Any-resource violation metrics are suppressed because CPU peak is unsupported ([section 12](#12-evaluator-contract)).

**Alibaba 2018** (existing adapter, `instance` rows):
- `requested_cpu`, `requested_memory` → `plan_cpu`, `plan_mem`
- `observed_cpu`, `observed_memory` → `cpu_avg`, `mem_avg`
- `peak_cpu`, `peak_memory` → `cpu_max`, `mem_max`

**Azure (deferred, unchanged):** `allocated_cpu` → vCPU/core bucket; `allocated_memory` → memory-capacity bucket; `observed_cpu` → CPU utilization telemetry; `observed_memory` → null/unsupported.

### 6.4 GPU fields and GPU scope
- Alibaba GPU 2020 is a GPU workload dataset. GPU fields are **retained** as optional canonical fields so useful source information is not lost.
- Retained canonical fields: `requested_gpu`, `observed_gpu`, `peak_gpu_memory`.
- Retained source and provenance columns: `gpu_type` (task), `avg_gpu_wrk_mem` (sensor, lifetime average GPU memory in GB), `cap_gpu` (machine capacity), and `gpu_type_spec` (group table).
- Missing GPU values stay null. `plan_gpu` is null on 223,965 task rows; it is never filled with zero. GPU values never cause a row to be excluded.
- There is no GPU-memory request in the source, so `peak_gpu_memory` has no matching request.
- **The current TraceAdvisor experiment evaluates CPU and memory only.** GPU baseline selection, GPU next-occurrence targets, GPU recommendation and GPU violation metrics are outside the current version.
- Role-level GPU values use the same maximum-over-eligible-instances rule as CPU and memory, as descriptive values. Before GPU evaluation is added, GPU aggregation and GPU target semantics must be explicitly defined.

---

## 7. Resource semantics

Semantics are declared **per field** in the dataset profile, not as one value per resource.

| Profile field | Describes |
|---|---|
| `observed_cpu_semantics`, `peak_cpu_semantics` | Meaning of `observed_cpu` and `peak_cpu` |
| `observed_memory_semantics`, `peak_memory_semantics` | Meaning of `observed_memory` and `peak_memory` |
| `cpu_target_semantics`, `memory_target_semantics` | Meaning of `actual_cpu` and `actual_memory` |
| `time_semantics` | What `start_time_us` marks on evaluation rows |
| `instance_event_time_semantics` | What `event_time_us` marks on `instance` rows; null when the dataset does not populate it |
| `time_basis` | Row-level time origin (existing): `unix_epoch`, `trace_relative`, or `unknown` |

**Vocabulary**
- Observed and peak values: `window_peak`, `lifetime_peak`, `lifetime_average`, `instance_peak`, `instance_average`; null when the field is not populated.
- Targets: `next_occurrence_peak`, `next_occurrence_lifetime_average`, `next_occurrence_lifetime_peak`; null when targets are unsupported.
- Time: `first_execution_start`, `job_submission`, `instance_start`.
- Instance event time: `parent_job_submission`.

| Field | Google | Alibaba GPU 2020 | Alibaba 2018 |
|---|---|---|---|
| `observed_cpu_semantics` | Null (not populated) | `lifetime_average` | `instance_average` |
| `peak_cpu_semantics` | `window_peak` | Null (no CPU peak) | `instance_peak` |
| `observed_memory_semantics` | Null (not populated) | `lifetime_average` | `instance_average` |
| `peak_memory_semantics` | `window_peak` | `lifetime_peak` | `instance_peak` |
| `cpu_target_semantics` | `next_occurrence_peak` | `next_occurrence_lifetime_average` | Null |
| `memory_target_semantics` | `next_occurrence_peak` | `next_occurrence_lifetime_peak` | Null |
| `time_semantics` | `first_execution_start` | `job_submission` | `instance_start` |
| `instance_event_time_semantics` | Null | `parent_job_submission` | Null |
| `time_basis` | `trace_relative` | `trace_relative` | `trace_relative` |

- Google uses window-based full-workload peaks (aligned-window sum, then maximum).
- Alibaba GPU 2020 uses lifetime-average CPU and lifetime-peak memory.
- Alibaba 2018 uses its existing instance-level average and peak measurements.

### Time fields
`event_time_us`, `start_time_us`, `end_time_us`, `duration_sec`, `aggregation_window_sec`.

Canonical timestamps use microseconds. Source-relative traces may remain trace-relative as long as `time_basis` records that fact.

| Dataset | `start_time_us` | `end_time_us` | Extensions |
|---|---|---|---|
| Google | First execution start (`execution_start_time_us`) | Occurrence end (`occurrence_end_time_us`) | — |
| Alibaba GPU 2020 role rows | **Job submission** (seconds × 10⁶) | Job completion; null if unavailable | `launch_time_us`: first task launch, lifecycle metadata only |
| Alibaba 2018 | Instance start | Instance end; null when the source end is `0` or earlier than the start | — |

Alibaba GPU 2020 timestamps are shifted by a constant. Time-of-day features are valid only in UTC+8.

#### Alibaba GPU 2020 timestamp contract

| Row | `event_time_us` | `start_time_us` | `end_time_us` |
|---|---|---|---|
| `role_occurrence` | Not populated | Job submission | Job completion, or null if unavailable |
| `instance` | **Parent job submission, always** | The instance's own start, or null if unavailable | The instance's own end, or null if unavailable |

- On instance rows, `event_time_us` always holds the parent job's submission time, declared in the profile as `instance_event_time_semantics = parent_job_submission`. It is a recorded source time used to place the audit row in time. It is **not** an invented instance start time, and it is never copied into `start_time_us`.
- The instance's own start is null on 1,773,468 instance rows (Running, Interrupted, Waiting, Failed and Ready instances). Those rows keep a null `start_time_us` and remain valid audit rows through `event_time_us`.
- Task launch time and sensor data are never used as a substitute for a missing time. The sensor table has no timestamps, and task launch time has a different meaning from submission.
- Timestamps are never inferred, carried forward or fabricated.
- A job without a submission time has no usable canonical time. The whole job is sent to the rejected output ([section 9.5](#95-alibaba-gpu-2020-rejected-output)).

---

## 8. Resource scope and aggregation

Scope and aggregation are **row-level columns**, because one adapter can emit several record levels. Requests and measured values have separate aggregation columns.

| Column | Vocabulary |
|---|---|
| `resource_scope` | `full_workload`, `task_role_per_instance`, `instance`, `job_total` |
| `request_aggregation_method` | `sum_over_executions`, `none`, `descriptive_job_total` |
| `observed_aggregation_method` | `aligned_window_sum_then_maximum`, `maximum_over_instances`, `none` |

Average versus peak is semantics ([section 7](#7-resource-semantics)), not an aggregation method.

| Rows | `resource_scope` | `request_aggregation_method` | `observed_aggregation_method` |
|---|---|---|---|
| Google occurrence | `full_workload` | `sum_over_executions` | `aligned_window_sum_then_maximum` |
| Alibaba GPU 2020 role occurrence | `task_role_per_instance` | `none` (per-instance request inherited by every instance of the role) | `maximum_over_instances` (eligible instances only) |
| Alibaba GPU 2020 instance audit | `instance` | `none` | `none` |
| Alibaba 2018 instance | `instance` | `none` | `none` |

Alibaba GPU 2020 job totals (request × instance count) use `resource_scope = job_total` and `request_aggregation_method = descriptive_job_total`. They are extension values only, never evaluation targets.

Rules:
- Worker memory peaks must not be summed into the evaluated Alibaba GPU 2020 role value. Without a time-aligned series, such a sum is only an upper bound.
- Request and actual values in an evaluator comparison must have the same scope.
- For Alibaba GPU 2020, the per-instance request is compared with the role's actual, defined as the maximum over the role's eligible instances: the amount that each instance of the role needed.

---

## 9. Validity, missingness, and exclusions

### 9.1 Four separate concepts

| Concept | Representation | Meaning |
|---|---|---|
| Data quality | `validity_status` | Quality of the row's data: `valid`, `partial`, `invalid`, `unknown`, `unsupported` |
| Per-resource validity | `cpu_validity_status`, `memory_validity_status` | Quality of each resource's values, same vocabulary. Standardized from the Alibaba 2018 adapter's extension columns |
| Eligibility for history and targets | `exclusion_reason` | Null means eligible; otherwise the primary reason the row is not used |
| Dataset capability | The dataset profile ([section 10](#10-capability-metadata)) | What the dataset can provide at all |

- Validity describes data quality; exclusion describes eligibility. A row with clean data can be `valid` and still be excluded, for example a role of a failed job.
- `validity_status` has no "excluded" value.
- `partial` marks an incomplete resource observation, matching the Alibaba 2018 adapter precedent. `invalid` marks contradictory or impossible values.
- Row-level `validity_status`: `invalid` if any resource is invalid; otherwise `valid` if every populated resource is valid; otherwise `partial`.

### 9.2 Rules
- Missing values remain null. Null is never replaced with zero.
- Missing CPU does not automatically exclude a row from memory evaluation.
- An unsupported CPU peak is represented by a null `peak_cpu` and `has_cpu_peak = false`. A populated value is a validation error; no per-row marker is used.
- Invalid rows remain in the output for audit.
- Excluded rows remain in the output and are not used for recurrence history or next-occurrence targets.
- Retries and duplicate worker attempts are not silently collapsed. Each attempt remains a separately identifiable `instance` row ([section 5.4](#54-alibaba-gpu-2020-instance-identity)).
- Records without a usable canonical time are not placed in a validated view; they go to the rejected output ([section 9.5](#95-alibaba-gpu-2020-rejected-output)).
- Each row has **one primary exclusion reason**: the first failed rule in the documented rule order. This is the finalized design.

| Case | Representation |
|---|---|
| Missing CPU on a memory-eligible role | `observed_cpu` and `actual_cpu` null; `cpu_validity_status = partial`; `exclusion_reason` stays null; left out of CPU-specific denominators |
| Invalid CPU value (for example negative) | `cpu_validity_status = invalid`; CPU left out of CPU denominators; memory eligibility unaffected |
| Missing memory observation | Memory values null; the role carries `missing_sensor` or `partial_sensor_coverage` |
| Unsupported CPU peak | `peak_cpu` null; capability `has_cpu_peak = false` |
| Invalid memory | `memory_validity_status = invalid`; row `validity_status = invalid`; exclusion reason from rules 13–14 |
| Duplicate worker attempts | Every attempt kept as its own `instance` row; the role row is excluded as `multi_attempt_worker` |
| Final occurrence of a recurrence | Target null with target status `no_next_occurrence` ([section 11](#11-splits-history-and-targets)) |

### 9.3 Alibaba GPU 2020 exclusion rules (finalized order)
Rules are evaluated in this order. The first failed rule sets `exclusion_reason`.

| Order | `exclusion_reason` | Condition |
|---|---|---|
| 1 | `no_recurrence_key` | The job has no `group` |
| 2 | `job_failed` | Job status is `Failed` |
| 3 | `job_incomplete` | Job is not `Terminated`, or has no completion time |
| 4 | `task_not_terminated` | Task status is not `Terminated` |
| 5 | `missing_or_invalid_request` | `plan_cpu` or `plan_mem` is missing or not greater than 0 |
| 6 | `instance_failed` | Any instance of the role is `Failed` |
| 7 | `instance_interrupted` | Any instance of the role is `Interrupted` |
| 8 | `instance_incomplete` | Any instance of the role is otherwise not `Terminated` (for example `Running`, `Waiting`, `Ready`) |
| 9 | `missing_worker_name` | Any instance of the role has no `worker_name` |
| 10 | `multi_attempt_worker` | Any worker of the role has more than one attempt. The single sensor row per worker cannot be attributed to one attempt, so attempts are not merged |
| 11 | `missing_sensor` | No worker of the role has a sensor row |
| 12 | `partial_sensor_coverage` | Some, but not all, workers of the role have a sensor row |
| 13 | `invalid_memory_exceeds_capacity` | Any worker's `max_mem` exceeds the host's `cap_mem` |
| 14 | `invalid_resource` | Any worker's `max_mem` is below its `avg_mem`, or a memory value is negative |

- A sensor row with missing CPU still counts as sensor coverage (rules 11–12).
- `missing_worker_name` (rule 9) is a role-level rule. Every instance row without a `worker_name` in the source is `Waiting`, `Ready` or `Failed`, so the status rules 6 and 8 normally fire first. The metadata count for `missing_worker_name` as a primary reason can therefore be zero, even though missing worker values exist. The rule is kept so that a missing worker can never pass silently.
- Google has no exclusion rules at present; its `exclusion_reason` stays null.
- Alibaba 2018 exclusion rules are not defined in this version.

**Resulting Alibaba GPU 2020 population (verified):** 462,156 role-occurrences pass rules 1–9 and 11–14; 256 more are excluded as `multi_attempt_worker`; the final eligible population is **461,900**. Of these, 1,224 (0.26%) have missing CPU.

### 9.4 Instance audit rows
- Alibaba GPU 2020 `instance` rows carry `role_key` and the other parent fields ([section 5.5](#55-alibaba-gpu-2020-instance-row-parent-linkage)), so each instance can be traced to its parent `role_occurrence` row.
- Instance rows carry their own per-resource validity.
- Eligibility is decided at the role level. Instance rows have no independent primary exclusion reason; their `exclusion_reason` is not applicable, and a null value on an instance row does not mean "eligible".
- **Missing `worker_name`:** `worker_id` stays null and is never part of the identity key. The instance evidence remains available through the nullable `worker_id`, the raw `source_` columns, `source_status`, and the parent `role_key`.
- Instance rows do not receive splits, targets or history features.

### 9.5 Alibaba GPU 2020 rejected output
A job with no submission time has no usable canonical time.

- The **complete job** is rejected together with all of its role rows and instance rows, with `rejection_reason = missing_submission_time`. Instance rows that do have their own start time are rejected with their job, so no orphan instance rows are left in the instance audit view.
- Rejected records go to a **separate rejected output**. They are not passed into the validated `role_occurrence` or `instance` views.
- Their source rows are preserved (including `source_row_number` for instance rows), and the metadata reports rejected job, role and instance counts by reason.
- The rejected output is retained for audit only. It is not used for chronological splitting, history, target construction or evaluation.
- The rejected output has minimal checks:
  - identity fields present where possible;
  - `rejection_reason` present;
  - no zero-filling;
  - source traceability preserved.
- Together, the validated views and the rejected output account for every source row.

**Verified volume:** 3,663 jobs have no submission time, with 6,942 role rows and 111,219 instance rows. All 3,663 jobs are `Waiting`, and no `Terminated` job lacks a submission time. These records are already ineligible (`job_incomplete`, or `no_recurrence_key` when the job has no `group`), so **the eligible Alibaba GPU 2020 population of 461,900 does not change**.

---

## 10. Capability metadata

### 10.1 Existing flags (retained and still enforced)
`supports_cpu`, `supports_memory`, `supports_request`, `supports_recurrence`, `supports_targets`, `supports_ml`, `supports_observed_cpu`, `supports_observed_memory`, `supports_allocated_cpu`, `supports_allocated_memory`.

### 10.2 Fields added in 0.2.0
Every new field has a default, for backward compatibility. Azure stays valid through the defaults even though it is deferred.

| Field | Values | Purpose |
|---|---|---|
| `has_cpu_average`, `has_cpu_peak` | Boolean | Separate average CPU from peak CPU. `peak_cpu` is gated by `has_cpu_peak` |
| `has_memory_average`, `has_memory_peak` | Boolean | Same for memory |
| `recurrence_key_origin` | `constructed`, `official`, `official_with_role`, `none` | How `recurrence_key` is formed |
| Per-field semantics | See [section 7](#7-resource-semantics) | Meaning of each resource field and target |
| `cpu_unit`, `memory_unit` | See [section 6.2](#62-units) | Units used for request and actual |
| `time_semantics`, `telemetry_window` | See [section 7](#7-resource-semantics); window in trace days | Ordering time and usable telemetry window |
| `instance_event_time_semantics` | `parent_job_submission`, or null (default) | Meaning of `event_time_us` on instance rows |
| `supported_record_levels`, `evaluation_record_level` | See [section 4.1](#41-record-levels) | Levels a dataset emits and the level evaluated |
| `evaluation_mode` | `full_next_occurrence`, `next_occurrence_memory_peak_cpu_average`, `instance_request_versus_observed` | How the dataset is evaluated |
| `allowed_exclusion_reasons` | List | The dataset's exclusion vocabulary |
| `any_resource_metric_valid` | Boolean | Whether any-resource metrics may be reported |
| `target_split_isolation` | Boolean | Whether targets must lie in the same split as their row |

`recurrence_key_origin = official_with_role` for Alibaba GPU 2020: `group` is official, and TraceAdvisor adds `task_name` to form the role recurrence key.

**Consistency rules**
- `supports_observed_cpu` must agree with `has_cpu_average` or `has_cpu_peak`.
- `supports_observed_memory` must agree with `has_memory_average` or `has_memory_peak`.
- `supports_cpu = true` never implies that CPU peak is supported.

### 10.3 Profile values

| Field | Google | Alibaba GPU 2020 | Alibaba 2018 (optional) | Azure (deferred) |
|---|---|---|---|---|
| `supports_cpu` / `supports_memory` | true / true | true / true | true / true | true / true (memory capacity only) |
| `supports_request` | true | true | true | false |
| `supports_recurrence` | true | true | false | false |
| `supports_targets` | true | true | false | false |
| `supports_ml` | true | true | false | false |
| `supports_observed_cpu` / `supports_observed_memory` | true / true | true / true | true / true | true / false |
| `supports_allocated_cpu` / `supports_allocated_memory` | false / false | false / false | false / false | true / true |
| `has_cpu_average` / `has_cpu_peak` | false / true | **true / false** | true / true | Default |
| `has_memory_average` / `has_memory_peak` | false / true | true / true | true / true | Default |
| `recurrence_key_origin` | `constructed` | `official_with_role` | `none` | Default |
| `cpu_unit` / `memory_unit` | `ncu` / `normalized` | `percent_of_vcpu` / `gb` | Alibaba 2018 source units | Default |
| `supported_record_levels` | `occurrence` | `role_occurrence`, `instance` | `instance` | Default |
| `evaluation_record_level` | `occurrence` | `role_occurrence` | `instance` | Default |
| `evaluation_mode` | `full_next_occurrence` | `next_occurrence_memory_peak_cpu_average` (memory first) | `instance_request_versus_observed` | Default |
| `any_resource_metric_valid` | true | **false** | Not applicable (no targets) | Default |
| `target_split_isolation` | false (current artifacts) | **true** | Not applicable | Default |
| `telemetry_window` | Full 31-day subset | About day 19 to day 68.9 | Full trace | Default |
| `instance_event_time_semantics` | Null | `parent_job_submission` | Null | Default |

Google's occurrence artifacts contain no occurrence-level average CPU or memory, so `has_cpu_average` and `has_memory_average` are false for Google.

---

## 11. Splits, history, and targets

Adapters produce current-occurrence canonical values only. Shared downstream logic adds:
- `split`: `train`, `validation`, or `test`;
- `actual_cpu`, `actual_memory`;
- `cpu_target_status`, `memory_target_status`.

**Per-resource target status**

| Value | Meaning |
|---|---|
| `available` | The target value is present |
| `no_next_occurrence` | The row is the last eligible occurrence of its recurrence |
| `next_occurrence_in_other_split` | The next eligible occurrence lies in a different split, and the dataset requires split isolation |
| `next_occurrence_ineligible_resource` | The next eligible occurrence's value for this resource is missing or invalid (for example missing CPU) |
| `unsupported_resource` | The dataset cannot provide a target for this resource |

**Rules**
- Splits are chronological 70/15/15 on the profile's ordering time.
  - Google: by `execution_start_time_us`, group-preserving; no occurrence crosses a partition boundary.
  - Alibaba GPU 2020: by job submission, so every role row of one job falls in the same split. Splits operate only on eligible `role_occurrence` rows; instance audit rows and rejected records receive no split.
- History uses eligible prior occurrences only: null `exclusion_reason`, and the relevant resource valid.
- A prior occurrence is used only if it completed at or before the current occurrence's start (`end_time_us` ≤ current `start_time_us`).
- The next target is the next eligible occurrence within the same `recurrence_key`.
- Alibaba GPU 2020 uses split-isolated next-occurrence targets.
- Targets submitted at the same time as the current occurrence (the same second, for Alibaba GPU 2020) are flagged: 245 validation and 251 test targets.
- Completed failed jobs may be kept as a separate history feature (for example a count of earlier failed jobs in the same group), only when their completion time is known and at or before the current start. They never supply resource history or targets.
- Google's existing target behavior, in which targets can cross split boundaries, is recorded (`target_split_isolation = false`) and not changed in this schema update. Any change follows the Google Subset Pipeline Analysis report.
- Google targets are referenced from the existing artifacts, not recomputed by an adapter.

**Alibaba GPU 2020 split-isolated population:** 42,104 validation and 44,087 test rows, counted before the final 256-row `multi_attempt_worker` exclusion. The final counts may be slightly lower and will be produced by the implemented pipeline.

---

## 12. Evaluator contract

Canonical evaluator names (unchanged):
- `dataset_id`
- `workload_id`
- `policy_name`
- `actual_cpu`
- `actual_memory`
- `recommended_cpu`
- `recommended_memory`

Rules:
- A row may evaluate CPU only, memory only, or both. At least one actual/recommendation pair must be present.
- Actual and recommendation values must use matching unit strings, and the same scope ([section 8](#8-resource-scope-and-aggregation)).
- CPU and memory use separate valid-row denominators.
- Missing values remain unknown. They are never counted as non-violations.
- Unsupported resources are excluded from that resource's metrics.
- When `any_resource_metric_valid` is false, any-resource metrics are not reported. Alibaba GPU 2020 therefore produces no any-resource violation metric. The shared evaluator otherwise reports an `any_resource_violation_pct` of 100% by construction when one resource is null for every row, and a combination of a CPU average result with a memory peak result has no meaning.
- Alibaba GPU 2020 CPU results must be labeled as average-usage results and never presented as peak safety.
- Alibaba GPU 2020 baseline selection ranks memory first.

---

## 13. Cross-dataset comparability

- Google full-workload CPU peaks and Alibaba GPU 2020 lifetime-average CPU values are not equivalent measurements.
- Google and Alibaba GPU 2020 CPU results must never be compared numerically or combined into one accuracy ranking.
- Memory results also differ, in scope (full workload versus per instance of a role), aggregation and unit (`normalized` versus `gb`).
- The purpose of the second dataset is to demonstrate that TraceAdvisor adapts to a different workload and resource contract, not to claim that one dataset produces a universally better score.

---

## 14. Deferred implementation work and out-of-scope items

These are implementation or future-scope items, not open design questions.

| Item | Type |
|---|---|
| Update `src/canonical/schema.py` to 0.2.0 | Implementation |
| Update `src/adapters/validation.py` | Implementation |
| Update `config/dataset_capabilities.json` | Implementation |
| Implement the Alibaba GPU 2020 adapter, including the instance identity fields, the timestamp contract and the rejected output | Implementation |
| Add a rejected output to the adapter result, with its minimal checks | Implementation |
| Add shared target-builder support (splits, history, targets, target statuses) | Implementation |
| Update tests and `examples/canonical_records.jsonl` | Implementation |
| GPU recommendation and GPU evaluation (requires GPU aggregation and target semantics) | Future scope |
| Azure implementation, including resolving the V1/V2 identity | Future scope (deferred) |
| Full Alibaba 2018 upgrade to 0.2.0 fields, unit unification and status-based validity | Future scope (optional) |
| Multiple exclusion reasons per row | Future scope |
| Alibaba GPU 2020 job-level summary rows | Future scope |
| Any Google behavior change | Future scope (separate approval via the Google Subset Pipeline Analysis report) |
| Unit conversion for display (for example `percent_of_vcpu` to `vcpu`) | Future scope |
| Group-weighted sensitivity implementation | Implementation (evaluation stage) |

### Dataset-specific extensions and provenance
Adapters may preserve source metadata without making shared code depend on it. Row-level source values use the `source_` column prefix.

- **Alibaba GPU 2020:** task role, `instance_slot_key`, `instance_attempt_index`, `worker_id`, `source_row_number`, `source_inst_name`, `source_worker_name`, `source_status`, `source_machine`, host capacity (`cap_cpu`, `cap_mem`, `cap_gpu`), `gpu_type`, `gpu_type_spec`, `avg_gpu_wrk_mem`, workload tag, `launch_time_us`, instance count (`inst_num`), job totals.
- **Alibaba 2018:** DAG/task type, `instance_num`, machine ID, `seq_no`, `total_seq_no`.
- **Azure:** subscription ID, deployment ID, VM category, core-count bucket, memory-capacity bucket.
- **Google:** source collection and occurrence/history metadata.

Dataset-level provenance belongs in the adapter result metadata, not on every row:
- `source_version`;
- source file checksums;
- adapter name and version;
- `telemetry_window`;
- row counts per validity status and per exclusion reason;
- rejected job, role and instance counts per `rejection_reason`.

### Issue boundaries
**Issue 2 owns:** schema, field meanings, units, capability metadata, missing-value rules, validity and exclusion vocabulary, split and target columns, canonical evaluator names, validation.

**Issue 3 owns:** adapter interface and source-to-canonical mapping behavior (`adapter_framework.md`).

**Issue 4 owns:** the Alibaba GPU 2020 adapter and dataset integration (required); the Alibaba 2018 adapter (optional). Azure VM integration is deferred.

**Issue 5 owns:** final standardized baseline/ML/Hybrid recommendation output contract.

---

## 15. Final contract checklist

| # | Contract item | Section |
|---|---|---|
| 1 | Design frozen as 0.2.0; code still 0.1.0; no further approval needed | 2 |
| 2 | Google reference, Alibaba GPU 2020 required, Alibaba 2018 optional, Azure deferred (V1 data, `v2` identifier retained) | 3 |
| 3 | New record level `role_occurrence`; Alibaba GPU 2020 `instance` audit rows | 4.1 |
| 4 | Terms defined per dataset; Google full-workload and Alibaba role rows are different scopes | 4.2 |
| 5 | `occurrence_key` is conceptual and stored in `occurrence_id`; `role_key` is the unique role identity | 5.1 |
| 6 | Literal separators: `\|\|` for Google and Alibaba GPU 2020; `\|` for Alibaba 2018 | 5.2 |
| 7 | Alibaba GPU 2020 `recurrence_key = group\|\|task_name`; fallback keys and `no_recurrence_key` for the 1,530 jobs without `group` (1,460 accepted) | 5.3 |
| 8 | `observed_*` = average, `peak_*` = peak; Alibaba GPU 2020 `peak_cpu` always null | 6.1, 6.3 |
| 9 | Units `percent_of_vcpu`, `percent_of_gpu` and `gb` for Alibaba GPU 2020; Alibaba 2018 source units retained | 6.2 |
| 10 | GPU fields retained; GPU evaluation outside the current version | 6.4 |
| 11 | Semantics declared per field | 7 |
| 12 | `resource_scope`, `request_aggregation_method`, `observed_aggregation_method`; worker peaks never summed | 8 |
| 13 | Validity, per-resource validity, eligibility and capability kept separate; `partial` for incomplete resources | 9.1 |
| 14 | Fourteen ordered Alibaba GPU 2020 exclusion rules; one primary reason per row; 461,900 eligible | 9.3 |
| 15 | Instance rows inherit `workload_id`, `recurrence_key`, `occurrence_id` and `role_key`; no independent instance exclusion reason | 5.5, 9.4 |
| 15a | Alibaba GPU 2020 `instance_id = job_name\|\|task_name\|\|inst_name\|\|instance_attempt_index`; no `source_seq_no`; every retry kept | 5.4 |
| 15b | Instance `event_time_us` = parent job submission (`parent_job_submission`); no invented, inferred or substitute timestamps | 7 |
| 15c | `missing_worker_name` is role-level; `worker_id` null and outside the key | 9.3, 9.4 |
| 15d | Jobs without submission time go whole to the rejected output (`missing_submission_time`); eligible population unchanged | 9.5 |
| 16 | 10 existing flags kept; new fields with defaults; `official_with_role` | 10 |
| 17 | Per-resource target statuses; eligible history only; split-isolated Alibaba GPU 2020 targets | 11 |
| 18 | Separate CPU and memory denominators; no any-resource metric for Alibaba GPU 2020; CPU labeled as average | 12 |
| 19 | No numerical CPU comparison across Google and Alibaba GPU 2020 | 13 |
| 20 | Later implementation and future-scope items listed | 14 |
