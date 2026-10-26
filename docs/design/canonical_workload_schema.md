# Canonical Workload Interface and Schema

**TraceAdvisor 295B — New Development Issue 2**  
**Schema version:** `0.2.0`, implemented in `src/canonical/schema.py`. Implementation status is in [section 2](#2-schema-version-and-implementation-status).

---

## 1. Purpose and scope

One semantic contract shared by adapters, ML preparation, policy logic, the shared evaluator, the API and the UI, without forcing Google-specific assumptions onto other datasets.

### Where the schema sits

```
source tables ──► dataset adapter ──► validated views ──► shared target builder ──► policies ──► shared evaluator
                  (map, identify,     (role_occurrence,   (split, actual_cpu,        (baseline,    (canonical names
                   validate, exclude)  occurrence,         actual_memory,             ML, Hybrid)   only)
                       │               instance)           target statuses)
                       ├──► rejected output (no usable canonical time)
                       └──► metadata (provenance, counts, coverage)
```

| Layer | Owns | Never does |
|---|---|---|
| Adapter | Identity keys, resource values and units, scope, validity, `exclusion_reason`, rejected output, metadata ([`adapter_framework.md`](adapter_framework.md)) | Splits, targets, history, percentiles, predictions, metrics |
| Shared target builder | `split`, `actual_cpu`, `actual_memory`, per-resource target statuses ([section 11](#11-splits-history-and-targets)) | Reading raw source columns |
| Evaluator | Metrics over canonical names ([section 12](#12-evaluator-contract)) | Reading raw source columns |

Datasets are never merged into one training dataframe; models are trained per dataset. Google's precomputed targets are referenced from existing artifacts, not computed by an adapter.

### Core rules
These hold everywhere and are not repeated in later sections.

- **Identity.** Workload identity and recurrence identity are separate ([section 5](#5-identity-fields-and-keys)).
- **Values.** Request, allocation, observation, peak, actual and recommendation are separate semantics. Average and peak are never interchanged. CPU and memory support are independent. Every populated value carries an explicit unit, and a request and its actual use the same unit string. Shared field names do not imply identical semantics; each profile declares semantics, units, scope and aggregation ([sections 7](#7-resource-semantics), [8](#8-resource-scope-and-aggregation), [10](#10-capability-metadata)).
- **Missing data.** Missing and unsupported values stay null and are never zero-filled. Timestamps are never inferred, carried forward, substituted or fabricated.
- **Quality and eligibility.** Data quality, eligibility and dataset capability are separate concepts ([section 9](#9-validity-missingness-and-exclusions)). Invalid and excluded rows stay in the output for audit. Records without a usable canonical time go to a separate rejected output ([section 9.5](#95-alibaba-gpu-2020-rejected-output)). Nothing is silently deleted.

---

## 2. Schema version and implementation status

Version 0.2.0 **extends** 0.1.0: no existing field, flag, record level, unit or validation rule is removed or renamed. The design is frozen.

| Component | Status |
|---|---|
| `src/canonical/schema.py`, `src/adapters/validation.py`, `config/dataset_capabilities.json`, `examples/canonical_records.jsonl` | At 0.2.0: `role_occurrence`, `role_key`, new capability fields, units, GPU fields, validity, exclusion and target-status vocabularies, `peak_cpu` gated by `has_cpu_peak`. The registry and JSON are kept identical by `test_capability_json_matches_python_registry` |
| Rejected output on the adapter result | Implemented ([`adapter_framework.md`](adapter_framework.md)) |
| Alibaba GPU 2020 adapter | Task 3 (#79); contract in `alibaba_gpu_2020_output_contract.md` |
| Shared target builder | Not yet implemented ([section 11](#11-splits-history-and-targets)) |
| Alibaba 2018 and Azure adapters | Unchanged at 0.1.0 behaviour |

---

## 3. Dataset profiles

| Dataset | `dataset_id` | Source version | Evaluation level | Recurrence | Resource limitations | Project role |
|---|---|---|---|---|---|---|
| Google Cluster Data 2019, Kaggle subset | `google_clusterdata2019` | Kaggle subset; artifacts in `data/processed/google_subset_v1` | `occurrence` | Constructed by TraceAdvisor | No occurrence-level average CPU; normalized units | Reference pipeline |
| Alibaba GPU 2020 | `alibaba_gpu_v2020` | `cluster-trace-gpu-v2020`, full official tables | `role_occurrence` (plus `instance` audit rows) | Official `group`, extended with the task role | **No CPU peak**; CPU is lifetime-average only; telemetry about day 19 to day 68.9 | Required second full integration |
| Alibaba Cluster Trace 2018 | `alibaba_clustertrace2018` | `cluster-trace-v2018` (`batch_task`, `batch_instance`) | `instance` | None | No recurrence, so no targets | Optional demonstration |
| Azure public VM | `azure_public_vm_v2` (identifier retained) | The sample matches the **V1 (2017)** release, not V2 | — | None | No observed memory; allocation buckets only; no request | Deferred |

**Google.** Full-workload occurrence evaluation (requests and peaks summed across executions). Recurrence is `user||collection_logical_name`. The artifacts are unchanged by this schema and checked by `tests/test_google_canonical_contract.py`. Known pipeline properties are tracked in the Google Subset Pipeline Analysis report.

**Alibaba GPU 2020.**
- Evaluation is one row per task role per job. **Memory (per-instance lifetime peak, GB) is the primary evaluated resource. CPU is lifetime-average only.** GPU fields are retained but not evaluated ([section 6.4](#64-gpu-fields-and-gpu-scope)).
- Recommendations are per instance; the instance count (`inst_num`) is not predicted.
- Every result must report the dataset's limitations (selection bias towards completed, fully observed workloads; mostly single-instance roles; about 50 of 68.9 days with telemetry; very large groups, so a group-weighted sensitivity result is reported too). Details: `docs/data/alibaba_gpu_2020_evidence_and_limitations.md` §5.

**Alibaba 2018.** Instance-level output; no recurrence key is invented; not used to define the recurrence pipeline.

**Azure.** Profile and adapter retained for compatibility and still valid at 0.2.0 through the field defaults. The data must not be described as V2; resolve its identity before any Azure work.

Results across datasets are not directly comparable ([section 13](#13-cross-dataset-comparability)).

---

## 4. Record levels and terminology

### 4.1 Record levels
Retained from 0.1.0: `workload`, `occurrence`, `execution`, `instance`, `interval`. Added in 0.2.0: **`role_occurrence`**.

| Dataset | Evaluation rows | Supporting rows |
|---|---|---|
| Google | `occurrence` | — |
| Alibaba GPU 2020 | `role_occurrence` | `instance` audit rows (one per instance-table row; every retry is its own row) |
| Alibaba 2018 | `instance` | — |
| Azure (deferred) | — | `instance` and `interval` |

**Why `role_occurrence`.** One Alibaba GPU 2020 job (one occurrence) can contain several task roles (`worker`, `ps`, …), and each role is evaluated separately. These rows share one `occurrence_id`, so they cannot be `occurrence` rows, which must have a unique `occurrence_id`, and they are not full-workload measurements.

| Record level | Uniqueness key |
|---|---|
| `occurrence` | `occurrence_id` |
| `role_occurrence` | `role_key` |
| `instance` | `(instance_id, source_seq_no)` when `source_seq_no` is present, otherwise `instance_id` |
| `execution` | `(execution_id, start_time_us)` when `start_time_us` is present, otherwise `execution_id` |
| `interval` | `(instance_id, event_time_us)` |

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
| **Instance slot** | Alibaba GPU 2020 only: one `(job_name, task_name, inst_name)` position; a retried slot has several instance rows |
| **Interval** | A fixed time-window measurement row |

| Term | Google | Alibaba GPU 2020 | Alibaba 2018 |
|---|---|---|---|
| Workload | Logical recurrence (Google recurrence key) | Official `group` | Source job (`job_name`) |
| Occurrence | Executions of one recurrence that start at the same time | One job submission | Not applicable |
| Execution | Episode of `collection_id` and `instance_index`, split on a 5-minute gap | Source task (`job_name`, `task_name`) on instance rows | Source task (`job_name`, `task_name`) |
| Task | Not applicable | `(job_name, task_name)` | `(job_name, task_name)` |
| Task role | Not applicable | `task_name` within a `group` | Not applicable: task names are DAG positions such as `M1` |
| Role occurrence | Not applicable | One `task_name` within one job | Not applicable |
| Instance | Not used | One attempt of an instance slot | One source instance or retry attempt (`seq_no`) |
| Interval | Not used | Not used: sensor values are lifetime summaries | Not used |

**Scope warning.** Google `occurrence` rows describe the full workload; Alibaba GPU 2020 `role_occurrence` rows describe what each instance of one role needs. They are not the same measurement.

---

## 5. Identity fields and keys

### 5.1 Field definitions

| Field | Definition |
|---|---|
| `workload_id` | Required, never null. The workload as defined in [section 4.2](#42-terminology) |
| `recurrence_key` | The key that history and next-occurrence targets group by, at the evaluation row's level. Null when recurrence is unavailable |
| `occurrence_key` | **Conceptual** key of one occurrence. Not a separate column; its value is stored in `occurrence_id` |
| `occurrence_id` | Holds the `occurrence_key` value. Unique on `occurrence` rows; repeats across the roles of one job on `role_occurrence` rows |
| `role_key` | Unique identity of a `role_occurrence` row. Also populated on Alibaba GPU 2020 `instance` rows to link each instance to its role |
| `execution_id` | Source sub-run identifier |
| `instance_id` | One instance or attempt. Unique per `instance` row |

### 5.2 Literal separators
Composite keys are plain strings joined with a literal separator: `||` (two vertical bars) for Google and Alibaba GPU 2020, and `|` (one bar) for the existing Alibaba 2018 adapter. A `‖` character in other documents is notation only.

### 5.3 Key values by dataset

| Field | Google | Alibaba GPU 2020 | Alibaba GPU 2020, job without `group` | Alibaba 2018 |
|---|---|---|---|---|
| `workload_id` | Google recurrence key | `group` | `job_name` (fallback) | `job_name` |
| `recurrence_key` | `user\|\|collection_logical_name` | `group\|\|task_name` | Null | Null |
| `occurrence_key` (conceptual) | `recurrence_key\|\|execution_start_time_us` | `group\|\|job_name` | `job_name` | — |
| `occurrence_id` | `occurrence_key` | `occurrence_key` | `occurrence_key` | Null |
| `role_key` | Null | `group\|\|job_name\|\|task_name` | `job_name\|\|task_name` (fallback) | Null |
| `execution_id` | `collection_id\|\|instance_index\|\|episode_<n>` | `job_name\|\|task_name` on instance rows; null on role rows | Same | `job_name\|task_name` |
| `instance_id` | Null | [Section 5.4](#54-alibaba-gpu-2020-instance-identity) on instance rows; null on role rows | Same | `instance_name` |

**Why `recurrence_key` includes `task_name`.** History and targets group by `recurrence_key`. With `group` alone, a `worker` role's history would mix with the `ps` role's, and a worker row's "next occurrence" could be a parameter-server row. Evidence: design decision D-04.

**Jobs without `group`** (1,530 jobs, 1,460 of them accepted; `docs/data/alibaba_gpu_2020_source_data_checks.md`):
- the fallback keys above keep `workload_id` and `role_key` non-null, and a two-part fallback `role_key` cannot collide with a three-part grouped one;
- every role row has `exclusion_reason = no_recurrence_key`, so it stays for audit but is never used for history or targets.

### 5.4 Alibaba GPU 2020 instance identity

```
instance_id = job_name||task_name||inst_name||instance_attempt_index
```

The slot alone is not unique: retried slots repeat it (231,632 slots, 906,751 rows of 7,522,002). Every retry is kept as its own row.

**Attempt index.** A deterministic, 1-based integer within the slot, ordered by instance start time (nulls last), then by `source_row_number`. `source_row_number` is the data-line number in the checksum-verified, decompressed `pai_instance_table.csv`, and the loader preserves file order, so the same file always produces the same `instance_id` values.

| Field | Kind | Definition |
|---|---|---|
| `instance_id` | Identity | As above; the uniqueness key (the adapter emits no `source_seq_no`) |
| `instance_slot_key` | Derived | `job_name\|\|task_name\|\|inst_name` |
| `instance_attempt_index` | Derived | Attempt number within the slot; derived, so not a `source_` column |
| `worker_id` | Mapped, nullable | `worker_name`; null when missing. The sensor join key and the input to `multi_attempt_worker` |
| `source_row_number` | Provenance | Data-line number in the verified instance file |
| `source_inst_name`, `source_worker_name`, `source_status`, `source_machine` | Raw source values | Unchanged, nulls preserved |

**What is not used as identity**
- `worker_name` and nullable timestamps: null on 331,057 and 1,773,468 rows, and one worker can occupy a slot twice.
- The source `inst_id`: it is a job-level value.
- The source row number alone: it is meaningful only for one file export, so it is kept as provenance.

### 5.5 Alibaba GPU 2020 instance-row parent linkage
Instance rows carry their parent role row's `workload_id`, `recurrence_key`, `occurrence_id` and `role_key`, with the values in [section 5.3](#53-key-values-by-dataset), including the fallbacks for jobs without `group`. Every audit row can therefore be joined to its role.

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

`observed_*` holds **average usage** and `peak_*` holds **peak usage**. Each populated field has `<field>_unit`. The GPU fields are new in 0.2.0.

### 6.2 Units
The schema does not force one universal unit.

| Unit | Meaning | Used by |
|---|---|---|
| `ncu` | Google normalized compute units | Google CPU |
| `normalized` | Google normalized memory | Google memory |
| `cpu_core` | CPU cores | — |
| `vcpu` | Virtual CPUs | Azure allocated CPU (deferred) |
| `gb` | Gigabytes | Alibaba GPU 2020 memory and GPU memory; Azure allocated memory |
| `percent` | Percent utilization | Azure observed CPU (deferred) |
| **`percent_of_vcpu`** (new) | Percent of one vCPU: 100 = 1 vCPU | Alibaba GPU 2020 CPU request and usage |
| **`percent_of_gpu`** (new) | Percent of one GPU: 100 = 1 GPU | Alibaba GPU 2020 GPU request and utilization |
| `alibaba_plan_cpu_100_per_core` | Alibaba 2018 CPU request (100 = 1 core) | Alibaba 2018 |
| `alibaba_cpu_usage_source_unit` | Alibaba 2018 CPU usage in source units | Alibaba 2018 |
| `alibaba_memory_source_normalized` | Alibaba 2018 normalized memory | Alibaba 2018 |

- A unit describes **scale, not meaning**; "lifetime average" is semantics ([section 7](#7-resource-semantics)).
- Alibaba GPU 2020 values keep the source scale; the adapter does not convert them.
- Alibaba 2018 CPU request and usage use different unit strings. That is acceptable while it has no targets and must be unified before any are enabled.

### 6.3 Dataset resource mappings

**Google** (unchanged; checked by `tests/test_google_canonical_contract.py`): requests are occurrence request sums (`ncu`, `normalized`); `peak_cpu`, `peak_memory` are full-workload peaks; `actual_cpu` and `actual_memory` come from `target_cpu_next_occurrence_peak_ncu` and `target_memory_next_occurrence_peak_normalized`; `observed_*` are not populated.

**Alibaba GPU 2020** (`role_occurrence` rows):

| Field | Source and rule | Unit |
|---|---|---|
| `requested_cpu` | Task `plan_cpu` (per instance) | `percent_of_vcpu` |
| `requested_memory` | Task `plan_mem` (per instance) | `gb` |
| `requested_gpu` | Task `plan_gpu` (per instance), retained | `percent_of_gpu` |
| `observed_cpu` | Maximum `cpu_usage` across the role's eligible workers; a lifetime average | `percent_of_vcpu` |
| `peak_cpu` | **Always null**: no CPU peak exists in the source | — |
| `observed_memory` | Maximum `avg_mem` across eligible workers | `gb` |
| `peak_memory` | Maximum `max_mem` across eligible workers; a per-instance lifetime peak | `gb` |
| `observed_gpu` | Maximum `gpu_wrk_util` across eligible workers; retained, not evaluated | `percent_of_gpu` |
| `peak_gpu_memory` | Maximum `max_gpu_wrk_mem` across eligible workers; retained, not evaluated | `gb` |
| `actual_cpu` | The next eligible role-occurrence's `observed_cpu`; added by shared code | `percent_of_vcpu` |
| `actual_memory` | The next eligible role-occurrence's `peak_memory`; added by shared code | `gb` |

"Eligible workers" means the role's sensor-covered instances. The adapter computes the maximum for every accepted role, eligible or not; an eligible role has a sensor row on every instance, so for it this is every worker. A role value is null if any covered instance's value is missing. On `instance` rows the same fields hold each worker's own source values, without aggregation.

**Alibaba GPU 2020 CPU results are average-usage sizing, not peak-safe sizing.**

**Alibaba 2018** (existing adapter, `instance` rows): requests from `plan_cpu`, `plan_mem`; `observed_*` from `cpu_avg`, `mem_avg`; `peak_*` from `cpu_max`, `mem_max`.

**Azure** (deferred, unchanged): `allocated_cpu` and `allocated_memory` from capacity buckets; `observed_cpu` from CPU utilization; `observed_memory` unsupported.

### 6.4 GPU fields and GPU scope
- Alibaba GPU 2020 GPU fields are **retained** so source information is not lost: canonical `requested_gpu`, `observed_gpu`, `peak_gpu_memory`; source columns `gpu_type`, `avg_gpu_wrk_mem`, `cap_gpu`, `gpu_type_spec`.
- Role-level GPU values use the same maximum rule as CPU and memory, as descriptive values. `plan_gpu` is null on 223,965 task rows. GPU values never cause an exclusion. There is no GPU-memory request, so `peak_gpu_memory` has no matching request.
- **The current experiment evaluates CPU and memory only.** GPU baselines, targets, recommendations and metrics need GPU aggregation and target semantics defined first.

---

## 7. Resource semantics

Semantics are declared **per field** in the dataset profile.

| Profile field | Describes |
|---|---|
| `observed_cpu_semantics`, `peak_cpu_semantics` | Meaning of `observed_cpu` and `peak_cpu` |
| `observed_memory_semantics`, `peak_memory_semantics` | Meaning of `observed_memory` and `peak_memory` |
| `cpu_target_semantics`, `memory_target_semantics` | Meaning of `actual_cpu` and `actual_memory` |
| `time_semantics` | What `start_time_us` marks on evaluation rows |
| `instance_event_time_semantics` | What `event_time_us` marks on `instance` rows; null when not populated |
| `time_basis` | Row-level time origin (existing): `unix_epoch`, `trace_relative`, `unknown` |

**Vocabulary**
- Observed and peak values: `window_peak`, `lifetime_peak`, `lifetime_average`, `instance_peak`, `instance_average`; null when not populated.
- Targets: `next_occurrence_peak`, `next_occurrence_lifetime_average`, `next_occurrence_lifetime_peak`; null when unsupported.
- Time: `first_execution_start`, `job_submission`, `instance_start`. Instance event time: `parent_job_submission`.

| Field | Google | Alibaba GPU 2020 | Alibaba 2018 |
|---|---|---|---|
| `observed_cpu_semantics` | Null | `lifetime_average` | `instance_average` |
| `peak_cpu_semantics` | `window_peak` | Null (no CPU peak) | `instance_peak` |
| `observed_memory_semantics` | Null | `lifetime_average` | `instance_average` |
| `peak_memory_semantics` | `window_peak` | `lifetime_peak` | `instance_peak` |
| `cpu_target_semantics` | `next_occurrence_peak` | `next_occurrence_lifetime_average` | Null |
| `memory_target_semantics` | `next_occurrence_peak` | `next_occurrence_lifetime_peak` | Null |
| `time_semantics` | `first_execution_start` | `job_submission` | `instance_start` |
| `instance_event_time_semantics` | Null | `parent_job_submission` | Null |
| `time_basis` | `trace_relative` | `trace_relative` | `trace_relative` |

### Time fields
`event_time_us`, `start_time_us`, `end_time_us`, `duration_sec`, `aggregation_window_sec`. Timestamps are in microseconds; trace-relative sources stay trace-relative and say so in `time_basis`.

| Rows | `event_time_us` | `start_time_us` | `end_time_us` |
|---|---|---|---|
| Google `occurrence` | — | First execution start | Occurrence end |
| Alibaba GPU 2020 `role_occurrence` | Not populated | **Job submission** (seconds × 10⁶) | Job completion, or null |
| Alibaba GPU 2020 `instance` | **Parent job submission, always** | The instance's own start, or null | The instance's own end, or null |
| Alibaba 2018 `instance` | — | Instance start | Instance end; null when the source end is `0` or before the start |

#### Alibaba GPU 2020 timestamp contract
- Instance `event_time_us` is a recorded source time (`instance_event_time_semantics = parent_job_submission`) that places the audit row in time. It is not an instance start and is never copied into `start_time_us`. Instances without their own start (1,773,468 rows) keep a null `start_time_us`.
- Task launch time and sensor data are never used as substitutes; `launch_time_us` is lifecycle metadata only.
- A job without a submission time goes whole to the rejected output ([section 9.5](#95-alibaba-gpu-2020-rejected-output)).
- Timestamps are shifted by a constant; time-of-day features are valid only in UTC+8.

---

## 8. Resource scope and aggregation

Scope and aggregation are **row-level columns**, because one adapter can emit several record levels. Requests and measured values have separate aggregation columns. Average versus peak is semantics ([section 7](#7-resource-semantics)), not an aggregation method.

| Column | Vocabulary |
|---|---|
| `resource_scope` | `full_workload`, `task_role_per_instance`, `instance`, `job_total` |
| `request_aggregation_method` | `sum_over_executions`, `none`, `descriptive_job_total` |
| `observed_aggregation_method` | `aligned_window_sum_then_maximum`, `maximum_over_instances`, `none` |

| Rows | `resource_scope` | `request_aggregation_method` | `observed_aggregation_method` |
|---|---|---|---|
| Google occurrence | `full_workload` | `sum_over_executions` | `aligned_window_sum_then_maximum` |
| Alibaba GPU 2020 role occurrence | `task_role_per_instance` | `none` (per-instance request inherited by every instance of the role) | `maximum_over_instances` (sensor-covered instances; every instance for an eligible role) |
| Alibaba GPU 2020 instance audit | `instance` | `none` | `none` |
| Alibaba 2018 instance | `instance` | `none` | `none` |

Alibaba GPU 2020 job totals (request × instance count) use `resource_scope = job_total` and `request_aggregation_method = descriptive_job_total`. They are extension values only, never evaluation targets.

Rules:
- Worker memory peaks are never summed into the Alibaba GPU 2020 role value: without a time-aligned series, a sum is only an upper bound.
- Request and actual values in an evaluator comparison must have the same scope.
- For Alibaba GPU 2020, the per-instance request is compared with the role's actual, the maximum over the role's instances (all sensor-covered, since only eligible roles are compared): the amount each instance of the role needed.

---

## 9. Validity, missingness, and exclusions

### 9.1 Four separate concepts

| Concept | Representation | Meaning |
|---|---|---|
| Data quality | `validity_status` | Quality of the row's data: `valid`, `partial`, `invalid`, `unknown`, `unsupported` |
| Per-resource validity | `cpu_validity_status`, `memory_validity_status` | Quality of each resource's values, same vocabulary (standardized from the Alibaba 2018 adapter) |
| Eligibility for history and targets | `exclusion_reason` | Null means eligible; otherwise the primary reason the row is not used |
| Dataset capability | The dataset profile ([section 10](#10-capability-metadata)) | What the dataset can provide at all |

- Validity is data quality; exclusion is eligibility. A `valid` row can still be excluded, for example a role of a failed job. `validity_status` has no "excluded" value.
- `partial` marks an incomplete resource observation; `invalid` marks contradictory or impossible values.
- Row `validity_status`: `invalid` if any resource is invalid; otherwise `valid` if every populated resource is valid; otherwise `partial`.

### 9.2 Rules
- Missing CPU does not exclude a row from memory evaluation.
- An unsupported CPU peak is a null `peak_cpu` with `has_cpu_peak = false`; a populated value is a validation error.
- Excluded rows are never used for recurrence history or next-occurrence targets.
- Each row has **one primary exclusion reason**: the first failed rule in the documented order.

| Case | Representation |
|---|---|
| Missing CPU on a memory-eligible role | `observed_cpu` and `actual_cpu` null; `cpu_validity_status = partial`; `exclusion_reason` stays null; left out of CPU-specific denominators |
| Invalid CPU value (for example negative) | `cpu_validity_status = invalid`; left out of CPU denominators; memory eligibility unaffected |
| Missing memory observation (no sensor row) | Memory values null; the role carries `missing_sensor` or `partial_sensor_coverage` |
| Average memory missing, peak present (null `avg_mem`) | `observed_memory` null; `peak_memory` kept; `memory_validity_status = partial`; the role stays eligible, because peak memory is the evaluated value (336 of the 461,900 eligible roles) |
| Unsupported CPU peak | `peak_cpu` null; capability `has_cpu_peak = false` |
| Invalid memory | `memory_validity_status = invalid`; row `validity_status = invalid`; rules 13–14 make the row ineligible, but the recorded reason is the first failed rule, which may be earlier (512 of 1,981 memory-invalid roles have rule 13 as their reason) |
| Duplicate worker attempts | Every attempt kept as its own `instance` row ([section 5.4](#54-alibaba-gpu-2020-instance-identity)); the role row is excluded as `multi_attempt_worker` |
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
| 10 | `multi_attempt_worker` | The same non-null `worker_id` appears on more than one instance row of the role. The single sensor row per worker cannot be attributed to one attempt |
| 11 | `missing_sensor` | No worker of the role has a sensor row |
| 12 | `partial_sensor_coverage` | Some, but not all, workers of the role have a sensor row |
| 13 | `invalid_memory_exceeds_capacity` | Any worker's `max_mem` exceeds the host's `cap_mem` |
| 14 | `invalid_resource` | Any worker's `max_mem` is below its `avg_mem`, or a memory value is negative |

- A sensor row with missing CPU still counts as coverage (rules 11–12).
- Rule 9 is role-level. Every instance without a `worker_name` is `Waiting`, `Ready` or `Failed`, so rules 6 and 8 normally fire first and its count can be zero. It is kept so a missing worker can never pass silently.
- Google has no exclusion rules; Alibaba 2018 rules are not defined in this version.

**Resulting population (verified):** 462,156 role-occurrences pass rules 1–9 and 11–14; rule 10 removes 256 more, leaving **461,900 eligible**, of which 1,224 (0.26%) have missing CPU. Full counts: `docs/data/alibaba_gpu_2020_adapter_results.md`.

### 9.4 Instance audit rows
- Eligibility is decided at the role level. Instance rows have no primary exclusion reason of their own: their `exclusion_reason` is not applicable, and null there does not mean "eligible".
- Instance rows carry their own per-resource validity and the parent linkage of [section 5.5](#55-alibaba-gpu-2020-instance-row-parent-linkage). A missing `worker_name` leaves `worker_id` null; the evidence stays in `source_` columns, `source_status` and `role_key`.
- Instance rows receive no splits, targets or history features.

### 9.5 Alibaba GPU 2020 rejected output
- A job with no submission time has no usable canonical time. The **complete job**, with all its role and instance rows, goes to a **separate rejected output** with `rejection_reason = missing_submission_time`, so no orphan instance rows remain in the instance view.
- Source rows are preserved, including `source_row_number`, and the metadata reports rejected job, role and instance counts by reason.
- The rejected output is for audit only: no splitting, history, targets or evaluation.
- Minimal checks: identity fields present where possible, `rejection_reason` present, no zero-filling, source traceability preserved.
- Validated views plus the rejected output account for every source row.

**Verified volume:** 3,663 jobs (all `Waiting`), 6,942 role rows and 111,219 instance rows. They are already ineligible, so the eligible population is unchanged.

---

## 10. Capability metadata

### 10.1 Existing flags (retained and still enforced)
`supports_cpu`, `supports_memory`, `supports_request`, `supports_recurrence`, `supports_targets`, `supports_ml`, `supports_observed_cpu`, `supports_observed_memory`, `supports_allocated_cpu`, `supports_allocated_memory`.

### 10.2 Fields added in 0.2.0
Every new field has a default, so older profiles (including Azure) stay valid.

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

`official_with_role` (Alibaba GPU 2020): `group` is official, and TraceAdvisor adds `task_name`.

**Consistency rules**
- `supports_observed_cpu` must agree with `has_cpu_average` or `has_cpu_peak`; the same holds for memory.
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

Google's artifacts have no occurrence-level averages, so its `has_*_average` flags are false.

---

## 11. Splits, history, and targets

Shared downstream logic, not the adapter, adds `split` (`train`, `validation`, `test`), `actual_cpu`, `actual_memory`, `cpu_target_status` and `memory_target_status`.

| Target status | Meaning |
|---|---|
| `available` | The target value is present |
| `no_next_occurrence` | The row is the last eligible occurrence of its recurrence |
| `next_occurrence_in_other_split` | The next eligible occurrence lies in a different split, and the dataset requires split isolation |
| `next_occurrence_ineligible_resource` | The next eligible occurrence's value for this resource is missing or invalid (for example missing CPU) |
| `unsupported_resource` | The dataset cannot provide a target for this resource |

**Rules**
- Splits are chronological 70/15/15 on the profile's ordering time.
  - Google: by `execution_start_time_us`, group-preserving.
  - Alibaba GPU 2020: by job submission, so every role of one job falls in the same split. Only eligible `role_occurrence` rows are split; instance and rejected rows are not.
- History uses eligible prior occurrences only (null `exclusion_reason`, resource valid) that completed at or before the current start (`end_time_us` ≤ current `start_time_us`).
- The target is the next eligible occurrence with the same `recurrence_key`. Alibaba GPU 2020 targets are split-isolated.
- Targets submitted in the same second as the current occurrence are flagged (245 validation and 251 test targets for Alibaba GPU 2020).
- Completed failed jobs may feed a separate history feature (for example a count of earlier failures in the group) when their completion time is known and at or before the current start. They never supply resource history or targets.
- Google's existing targets can cross split boundaries (`target_split_isolation = false`); that is recorded, not changed here. Google targets come from the existing artifacts.

**Alibaba GPU 2020 split-isolated population:** 42,104 validation and 44,087 test rows, counted before the final 256-row `multi_attempt_worker` exclusion. Final counts come from the target builder.

---

## 12. Evaluator contract

Canonical evaluator names (unchanged): `dataset_id`, `workload_id`, `policy_name`, `actual_cpu`, `actual_memory`, `recommended_cpu`, `recommended_memory`.

- A row may evaluate CPU only, memory only, or both; at least one actual/recommendation pair must be present.
- Actual and recommendation must use matching unit strings and the same scope ([section 8](#8-resource-scope-and-aggregation)).
- CPU and memory use separate valid-row denominators. Missing values remain unknown and are never counted as non-violations. Unsupported resources are left out of that resource's metrics.
- When `any_resource_metric_valid` is false, any-resource metrics are not reported. For Alibaba GPU 2020, combining a CPU-average result with a memory-peak result has no meaning.
- Alibaba GPU 2020 CPU results are labeled as average-usage results, never as peak safety. Baseline selection ranks memory first.

---

## 13. Cross-dataset comparability

- Google full-workload CPU peaks and Alibaba GPU 2020 lifetime-average CPU are not equivalent. Their CPU results are never compared numerically or combined into one ranking.
- Memory results also differ in scope (full workload versus per instance of a role), aggregation and unit (`normalized` versus `gb`).
- The second dataset shows that TraceAdvisor adapts to a different workload and resource contract, not that one dataset scores better.

---

## 14. Deferred implementation work and out-of-scope items

These are implementation or future-scope items, not open design questions.

| Item | Type |
|---|---|
| Shared target builder (splits, history, targets, target statuses) | Implementation (Task 4) |
| Group-weighted sensitivity | Implementation (evaluation stage) |
| GPU recommendation and evaluation (needs GPU aggregation and target semantics) | Future scope |
| Azure, including the V1/V2 identity | Future scope (deferred) |
| Alibaba 2018 upgrade to 0.2.0 fields, unit unification and status-based validity | Future scope (optional) |
| Multiple exclusion reasons per row | Future scope |
| Alibaba GPU 2020 job-level summary rows | Future scope |
| Any Google behavior change | Future scope (via the Google Subset Pipeline Analysis report) |
| Unit conversion for display (for example `percent_of_vcpu` to `vcpu`) | Future scope |

### Dataset-specific extensions and provenance
Adapters may keep source metadata without shared code depending on it; row-level source values use the `source_` prefix.

- **Alibaba GPU 2020:** task role, `instance_slot_key`, `instance_attempt_index`, `worker_id`, `source_row_number`, `source_inst_name`, `source_worker_name`, `source_status`, `source_machine`, host capacity (`cap_cpu`, `cap_mem`, `cap_gpu`), `gpu_type`, `gpu_type_spec`, `avg_gpu_wrk_mem`, workload tag, `launch_time_us`, `inst_num`, job totals.
- **Alibaba 2018:** DAG/task type, `instance_num`, machine ID, `seq_no`, `total_seq_no`.
- **Azure:** subscription ID, deployment ID, VM category, core-count bucket, memory-capacity bucket.
- **Google:** source collection and occurrence/history metadata.

Dataset-level provenance and counts belong in the adapter result metadata, not on every row; the required keys are in `adapter_framework.md` §6.

### Issue boundaries
- **Issue 2:** schema, field meanings, units, capability metadata, missing-value rules, validity and exclusion vocabulary, split and target columns, evaluator names, validation.
- **Issue 3:** adapter interface and source-to-canonical mapping behavior (`adapter_framework.md`).
- **Issue 4:** the Alibaba GPU 2020 adapter (required) and the Alibaba 2018 adapter (optional); Azure deferred.
- **Issue 5:** the standardized baseline/ML/Hybrid recommendation output contract.

---

## 15. Final contract checklist

| # | Contract item | Section |
|---|---|---|
| 1 | Schema 0.2.0 frozen and implemented; target builder still to come | 2 |
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
| 20 | Remaining implementation and future-scope items listed | 14 |
