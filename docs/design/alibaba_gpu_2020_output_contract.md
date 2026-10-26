# Alibaba GPU 2020 Output Contract: Task 3 Artifacts for Tasks 4, 6, 7 and 8

**Task:** 3 (#79), Alibaba GPU 2020 adapter and canonical artifacts
**Schema version:** `0.2.0` (`canonical_workload_schema.md`)
**Status:** Design frozen. Part A and Part B steps B1–B6 are implemented and verified on the full tables (`docs/data/alibaba_gpu_2020_adapter_results.md`); the adapter design is in `docs/design/alibaba_gpu_2020_adapter_design.md`. The build script (B7) and its artifacts are next.
**Decision IDs:** D-01 to D-24 are the schema design decisions in `docs/design/canonical_schema_design_decisions.md`; each is named where it is first cited.

---

## 1. Purpose and scope

This document is the contract between Task 3 and the tasks that use its output:

| Task | Uses |
|---|---|
| Task 4, shared splits, history and targets | Eligible `role_occurrence` rows |
| Task 6, baselines and validation evaluation | Eligible `role_occurrence` rows (through the Task 4 tables) |
| Task 7, ML, Hybrid and final test | The Task 4 tables, and the pre-execution fields listed in §8.2 |
| Task 8 (plan Task 11a), final verification | All three artifacts, `metadata.json` and `count_report.md` |

It describes how Alibaba GPU 2020 fills the canonical schema. Field meanings, vocabularies and validation rules are defined in `canonical_workload_schema.md` and `adapter_framework.md`; this document points to them and does not redefine them.

**Not in Task 3 output:** splits, history features, `actual_cpu`, `actual_memory`, target statuses (Task 4); recommendations and metrics (Tasks 5–7); job totals (not emitted, design §6); GPU evaluation (schema §6.4).

---

## 2. Source to output

```
six source tables (Task 2 loader) ─► Part A prepare_sources ─► Part B map_prepared_sources
   ─► adapt_sources (validation) ─► role_occurrence · instance · rejected · metadata.json · count_report.md
```

Jobs, tasks, instances, sensor summaries, group tags and machine specs are combined with left joins only: a lookup never adds a row, and an unmatched value stays null. The joins and every step are described in the adapter design (`docs/design/alibaba_gpu_2020_adapter_design.md`).

---

## 3. Artifacts and storage

| File | Content | Rows |
|---|---|---|
| `role_occurrence.parquet` | The evaluation view: one row per task role per accepted job | 1,254,108 |
| `instance.parquet` | The audit view: one row per accepted instance-table row (every retry is its own row) | 7,410,783 |
| `rejected.parquet` | Every rejected job, role and instance row (§6) | 121,824 |
| `metadata.json` | Adapter metadata and provenance (§7) | — |
| `count_report.md` | Counts per rule and reason, and every difference from the design figures, explained | — |

- **Location:** `data/processed/alibaba_gpu_v2020/`.
- **Not committed:** `.gitignore` ignores `data/processed/*` and `*.parquet`, so every file here is local only. They are rebuilt with `scripts/build_alibaba_gpu_2020_canonical.py` (design step B7) from the checksum-verified source tables.
- **Committed record:** this document (contract) and the measured results (`docs/data/alibaba_gpu_2020_adapter_results.md`). Task 8 adds an artifact manifest with paths, checksums, row counts, code commit and generating commands.
- **Format:** Parquet (`pyarrow>=10.0.0`, in `requirements.txt`).

---

## 4. `role_occurrence` view

**One row per** `(job_name, task_name)` of an accepted job. **Unique key:** `role_key`. `record_level = role_occurrence`.

### 4.1 Columns

| Group | Column | Type | Null | Value |
|---|---|---|---|---|
| Core | `schema_version` | string | No | `0.2.0` |
| | `dataset_id` | string | No | `alibaba_gpu_v2020` |
| | `record_level` | string | No | `role_occurrence` |
| | `time_basis` | string | No | `trace_relative` |
| Identity (schema §5.3) | `workload_id` | string | No | `group`; `job_name` when the job has no group |
| | `recurrence_key` | string | Yes | `group\|\|task_name`; null when the job has no group |
| | `occurrence_id` | string | No | `group\|\|job_name`; `job_name` when the job has no group. Repeats across the roles of one job |
| | `role_key` | string | No | `group\|\|job_name\|\|task_name`; `job_name\|\|task_name` when the job has no group |
| | `execution_id`, `instance_id` | string | Always null | Instance-level only |
| Time (schema §7) | `start_time_us` | Int64 | No | Job submission, µs, trace-relative |
| | `end_time_us` | Int64 | Yes | Job completion; null when the source has none |
| | `event_time_us` | — | Not present | Instance rows only |
| Requests (schema §6.3) | `requested_cpu` | float | Yes | Task `plan_cpu`, per instance, `percent_of_vcpu` |
| | `requested_memory` | float | Yes | Task `plan_mem`, per instance, `gb` |
| | `requested_gpu` | float | Yes | Task `plan_gpu`, per instance, `percent_of_gpu`; descriptive only |
| Observed and peak (schema §6.3; excluded-role resource values decision) | `observed_cpu` | float | Yes | Maximum `cpu_usage` over the role's instances with sensor rows; lifetime average; null if any of them lacks CPU. `percent_of_vcpu` |
| | `peak_cpu` | float | **Always null** | No CPU peak in the source (`has_cpu_peak = false`) |
| | `observed_memory` | float | Yes | Maximum `avg_mem`, `gb` |
| | `peak_memory` | float | Yes | Maximum `max_mem`, `gb`. **The primary evaluated value** |
| | `observed_gpu` | float | Yes | Maximum `gpu_wrk_util`, `percent_of_gpu`; descriptive only |
| | `peak_gpu_memory` | float | Yes | Maximum `max_gpu_wrk_mem`, `gb`; descriptive only |
| | `<field>_unit` | string | No, except `peak_cpu_unit`, which is always null | A constant unit on every row (B3 decision), also where the value is null. The schema requires a unit wherever a value is populated |
| Scope (schema §8) | `resource_scope` | string | No | `task_role_per_instance` |
| | `request_aggregation_method` | string | No | `none` |
| | `observed_aggregation_method` | string | No | `maximum_over_instances` |
| Quality (schema §9) | `validity_status`, `cpu_validity_status`, `memory_validity_status` | string | No | `valid`, `partial`, `invalid` |
| | `exclusion_reason` | string | Yes | Null means eligible; otherwise the first failed rule (§4.2) |
| Extensions (schema §14; extension column names decision) | `job_name`, `task_name` (the task role) | string | No | Source values |
| | `inst_num` | float | No | Task instance count |
| | `gpu_type` | string | Yes | Task GPU type |
| | `gpu_type_spec`, `workload` | string | Yes | Group-tag values; null when the job has no group-tag row |
| | `launch_time_us` | Int64 | Yes | First task launch; lifecycle metadata only |
| | `source_job_status`, `source_task_status` | string | Yes | Raw job and task statuses |

`actual_cpu`, `actual_memory`, `split` and target statuses are never populated by the adapter; `validate_adapter_output` rejects them (`TARGET_BUILDER_COLUMNS`).

**Excluded-role resource values (approved):** on every role, observed and peak values are the maximum over the role's instances that have sensor rows. For eligible roles that is every worker, as in schema §6.3. Roles excluded by rules 1–12 (791,696, 387,608 of them with sensor data) keep these values for audit, with validity computed from them (`partial` where sensor coverage is incomplete); a role with no sensor rows has null values. Retries do not change the maximum, because every attempt of a worker carries the same sensor row.

### 4.2 Eligibility

Exclusion rules are evaluated in the order of schema §9.3. The first failed rule sets `exclusion_reason`:

`no_recurrence_key`, `job_failed`, `job_incomplete`, `task_not_terminated`, `missing_or_invalid_request`, `instance_failed`, `instance_interrupted`, `instance_incomplete`, `missing_worker_name`, `multi_attempt_worker`, `missing_sensor`, `partial_sensor_coverage`, `invalid_memory_exceeds_capacity`, `invalid_resource`.

- **Eligible row:** `exclusion_reason` is null. Design figure: **461,900** eligible roles; 1,224 of them have missing CPU (schema §9.3).
- Excluded rows stay in the view for audit. They are never used for history or targets.
- Missing CPU on an eligible role: `observed_cpu` null, `cpu_validity_status = partial`, still eligible for memory.
- Eligibility comes only from `exclusion_reason`. Validity is data quality and never decides eligibility: an excluded role can be `valid`.

---

## 5. `instance` view

**One row per** accepted instance-table row (one attempt of one instance slot). **Unique key:** `instance_id`. `record_level = instance`. An audit view only.

| Group | Column | Value |
|---|---|---|
| Core | `schema_version`, `dataset_id`, `record_level`, `time_basis` | As on roles, with `record_level = instance` |
| Identity (schema §5.4) | `instance_id` | `job_name\|\|task_name\|\|inst_name\|\|instance_attempt_index` |
| | `instance_slot_key` | `job_name\|\|task_name\|\|inst_name` |
| | `instance_attempt_index` | 1-based within the slot: own start ascending, nulls last, then `source_row_number` |
| | `execution_id` | `job_name\|\|task_name` |
| | `worker_id` | `worker_name`; null when missing |
| Parent (schema §5.5) | `workload_id`, `recurrence_key`, `occurrence_id`, `role_key` | Copied from the parent role, never recomputed |
| Time | `event_time_us` | Parent job submission, always present |
| | `start_time_us`, `end_time_us` | The instance's own times, or null. Never filled from another time |
| Resources | Usage fields only: `observed_cpu`, `observed_memory`, `peak_memory`, `observed_gpu`, `peak_gpu_memory`, `peak_cpu` (always null), each with its unit | Each worker's own source values, no aggregation. `resource_scope = instance`, both aggregation methods `none`. Requests are not on instance rows: they belong to the parent role and are read through `role_key` |
| Quality | `validity_status`, `cpu_validity_status`, `memory_validity_status` | Per instance |
| | `exclusion_reason` | Present and always null. Not applicable: eligibility is decided at the role (schema §9.4), so a null here does not mean eligible; use the parent role's `exclusion_reason` through `role_key` |
| Provenance | `source_row_number` | Data-line number in the verified `pai_instance_table.csv` |
| | `source_inst_name`, `source_worker_name`, `source_status`, `source_machine` | Raw source values |
| Extensions (extension column names decision) | `job_name`, `task_name`, `cap_cpu`, `cap_mem`, `cap_gpu`, `machine_gpu_type` (host GPU type), `avg_gpu_wrk_mem` | Source values; capacity columns null for the 331,057 unplaced instances |

- No `source_seq_no`: `instance_id` alone is the key.
- Every accepted instance links to exactly one accepted role (0 orphans, §9).
- All attempts of a retried worker carry that worker's single sensor row. Such roles are excluded as `multi_attempt_worker`, so these values are never evaluated.

---

## 6. Rejected output

A job without a submission time has no usable canonical time, so it is rejected whole: the job row, all its role rows and all its instance rows (schema §9.5, D-23 Rejected output for jobs without a submission time).

| Column | Value |
|---|---|
| `rejection_level` | `job`, `role_occurrence` or `instance` |
| `rejection_reason` | `missing_submission_time` (the only reason) |
| Source and prepared columns | The row's own values, unchanged and never zero-filled. A column that a level does not have is null |

| Level | Traced by | Rows |
|---|---|---|
| `job` | `job_name`; `job_source_row_number` | 3,663 |
| `role_occurrence` | `(job_name, task_name)`, `role_key`; `task_source_row_number` | 6,942 |
| `instance` | `source_row_number` (an instance-file line), `instance_id` | 111,219 |

- Audit only. It is never split, used for history or targets, or evaluated.
- No rejected key appears in either view.
- Dtypes (rejected-output dtypes decision): each column has its dtype from the source frame, with nullable `boolean` for flags, so combining the levels never leaves an `object` column. Values are unchanged.

---

## 7. `metadata.json`

Filled by `build_multiview_metadata` (`adapter_framework.md` §6) and its Alibaba GPU 2020 override (design step B6).

| Field | Content |
|---|---|
| `schema_version`, `adapter_name`, `adapter_version`, `dataset_id` | Identity of the output |
| `capabilities` | The `alibaba_gpu_v2020` profile (schema §10.3) |
| `primary_view` | `role_occurrence` |
| `source_version`, `source_files`, `source_checksums` | `cluster-trace-gpu-v2020`, file paths and SHA-256 values from the Task 2 manifest |
| `source_row_counts`, `canonical_row_counts` | Per source table and per view |
| `validity_counts`, `cpu_validity_counts`, `memory_validity_counts` | Counts per status |
| `exclusion_reason_counts` | Counts per reason, in rule order, every reason including zeros; `<null>` (eligible) last |
| `rejection_counts` | Per level and reason |
| `join_coverage_counts` | Per join: driving matched, unmatched and null-key rows; lookup rows used and unused. Taken from the adapter's own Part A counts |
| `telemetry_window` | The profile string, `About day 19 to day 68.9`; in provenance, a mapping such as `{"description": "About day 19 to day 68.9", "start_day": 19, "end_day": 68.9}` |
| `eligibility_summary` (B6) | `accepted_roles` (the denominator); roles passing every rule except `multi_attempt_worker`; eligible roles; eligible roles with missing CPU |

---

## 8. Rules for consumers

### 8.1 What each task may read

| Task | May read | Must not |
|---|---|---|
| 4 | `role_occurrence` rows with a null `exclusion_reason` | Read `instance` or rejected rows; assign splits or targets to excluded rows |
| 6 | The Task 4 train and validation tables | Read `instance` or rejected rows; reinterpret request fields |
| 7 | The Task 4 tables and the pre-execution fields (§8.2) | Read test targets before the decision manifest is locked |
| 8 | Everything in §3 | Change any artifact |

All tasks: never change an identity, time, resource or quality column; use canonical names, not `source_` columns, in shared code.

### 8.2 Fields known before execution

These describe a role at submission and may be used as features. Anything observed during or after the run may not.

| Known at submission | Observed after submission (not features) |
|---|---|
| `start_time_us` (submission), `workload_id`, `recurrence_key`, `task_name` | `end_time_us`, `launch_time_us` |
| `requested_cpu`, `requested_memory`, `requested_gpu`, `inst_num` | `observed_*`, `peak_*` |
| `gpu_type` (task), `gpu_type_spec`, `workload` (group tag) | Statuses, validity and `exclusion_reason` |

GPU type is therefore available as a pre-execution field (`gpu_type`, `gpu_type_spec`). Whether Task 7 uses it is a Task 7 decision.

### 8.3 Time, units and comparison

- Times are integer µs, trace-relative (`time_basis = trace_relative`). Time-of-day features are meaningful only in UTC+8 (schema §7).
- Splits use `start_time_us` (job submission). Every role of one job shares that time, so they fall in the same split.
- History may use a prior occurrence only if its `end_time_us` is at or before the current `start_time_us`. A null `end_time_us` is never usable as history.
- The request and the actual it is compared with use the same unit and scope: per instance of the role. `peak_memory` (GB) is the primary target. CPU (`observed_cpu`, `percent_of_vcpu`) is a lifetime average, never a peak, and results must say so.
- CPU denominators use rows with non-null `observed_cpu` and `cpu_validity_status` not `invalid`. Memory denominators use rows with non-null `peak_memory` and `memory_validity_status` not `invalid`. `partial` alone never removes a populated value.
- Dataset-specific: for Alibaba GPU 2020, row `validity_status` equals `memory_validity_status` (measured 2026-10-25). CPU is either valid or not populated, so it never changes a row's status. Other datasets must not assume this.
- No any-resource metric (`any_resource_metric_valid = false`).
- Never compare Alibaba GPU 2020 and Google CPU values numerically (schema §13).

---

## 9. Guarantees

Each of these is checked in the adapter and fails the build if violated.

| Guarantee | Checked by |
|---|---|
| `role_key` unique on roles; `instance_id` unique on instances | A2 and A3 guards; per-view validation |
| Every instance links to one role of the same accepted or rejected set, with equal identity fields and `event_time_us` = parent `start_time_us` | A7 `_check_linkage`; `adapt_sources` again on the views |
| No missing value is zero-filled; no time is inferred, carried forward or substituted | A1, A5 and A6 rules and tests |
| Every source row is accounted for: views + rejected = source, at task, instance and job level | Results doc; `count_report.md` |
| `peak_cpu` never populated | Profile `has_cpu_peak = false`, per-view validation |
| `recurrence_key` null only with `exclusion_reason = no_recurrence_key` | Per-view validation |
| No split or target column populated | `validate_adapter_output` |

---

## 10. Known source conditions

These are properties of the source data, kept as they are, and reported with every result.

| Condition | Rows | Handling |
|---|---|---|
| Jobs without `group` | 1,530 (1,460 accepted) | Fallback identity; roles excluded as `no_recurrence_key` |
| Jobs without a submission time | 3,663 (all `Waiting`) | Rejected whole |
| Instances without `worker_name` and machine | 331,057 | `worker_id` null; roles excluded by an earlier rule |
| Accepted instances without their own start time | 1,673,976 | `start_time_us` null; placed in time by `event_time_us` |
| Retried slots | 231,632 slots, 906,751 rows | Each attempt its own row; roles with a retried worker excluded as `multi_attempt_worker` |
| Tasks without instance rows | 130 | All in rejected jobs; no accepted role lacks instances |
| Telemetry only for about day 19 to day 68.9 | — | Roles outside it have no sensor rows (`missing_sensor`) |
| Selection bias, single-instance roles (96.7%), very large groups | — | Reporting limitations, schema §3 |

---

## 11. Measured results

Full figures are in `docs/data/alibaba_gpu_2020_adapter_results.md`. Headline figures:

| Figure | Value |
|---|---|
| `role_occurrence` / `instance` / rejected rows | 1,254,108 / 7,410,783 / 121,824 |
| Eligible roles | 461,900 (1,224 with missing CPU) |
| Roles passing every rule except `multi_attempt_worker` | 462,156 |
| Eligible roles by row validity | 461,564 `valid`, 336 `partial`, 0 `invalid` |
| Linkage (accepted and rejected) | 0 orphans, 0 mismatches |

Artifact checksums and the code commit are added by the build (B7).

---

## 12. Open items

| Item | Status |
|---|---|
| Artifact manifest format | Open, Task 8 (its decision D-1) |

All Task 3 design decisions are recorded in the adapter design §6.
