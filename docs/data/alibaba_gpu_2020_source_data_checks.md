# Task 3 (#79) Source Data Checks: Alibaba GPU 2020

**Date:** 2026-10-23
**Design step:** Part A, A0 (`docs/design/alibaba_gpu_2020_adapter_design.md` §2.5)
**Data:** `data/raw/alibaba_gpu_2020/` (gitignored). All 18 official SHA-256 values verified; sizes and line counts match the Task 2 manifest.
**Method:** read-only scripts, not committed. Each table is read with its official header, `quoting=QUOTE_NONE`, and only empty fields treated as missing.
**For the report:** cite this document for **data validation** (the source tables match the design). Cite `docs/data/alibaba_gpu_2020_adapter_results.md` for **pipeline validation** (the adapter's output on these tables is correct).
**Decision IDs:** D-01 to D-24 are the schema design decisions in `docs/design/canonical_schema_design_decisions.md`; each is named where it is first cited.

**Result: the data matches the frozen design. No source anomaly needs a new decision. One count is corrected (jobs without `group`).**

---

## 1. Source tables

| Table | Rows |
|---|---|
| `pai_job_table` | 1,055,501 |
| `pai_task_table` | 1,261,050 |
| `pai_instance_table` | 7,522,002 |
| `pai_sensor_table` | 3,033,232 |
| `pai_group_tag_table` | 1,055,032 |
| `pai_machine_spec` | 1,897 |

## 2. Results

| # | Check | Expected | Result | Outcome |
|---|---|---|---|---|
| 1 | Duplicate sensor keys `(job_name, task_name, worker_name)` | 0 (D-17 Eligibility and exclusion rules) | 0; no null key parts | D-17 holds. No decision needed |
| 2 | Duplicate join keys: `job_name` (job), `(job_name, task_name)` (task), `inst_id` (group tag), `machine` (machine spec) | 0 each | 0 / 0 / 0 / 0; no null keys | Every A1 lookup is unique and adds no rows (see §3.4) |
| 3 | Instances with no task row; tasks with no job row; jobs with no task rows | Not covered | 0 / 0 / 0 | No decision needed (see §3.2) |
| 4 | Null `job_name`, `task_name` or `inst_name` in the instance table | Not covered | 0 | No decision needed |
| 5 | Jobs without `group` | 469 (schema §5.3, before correction) | 1,530 in total; 1,460 accepted | 469 corrected (see §3.1) |
| 6 | Jobs without a submission time / their task rows / their instance rows | 3,663 / 6,942 / 111,219 (D-23 Rejected output for jobs without a submission time) | 3,663 / 6,942 / 111,219 | Exact match |
| 7 | `end_time < start_time` on jobs / instances | Not covered | 0 / 0 | No decision needed |
| 8 | Negative task requests (`inst_num`, `plan_cpu`, `plan_mem`, `plan_gpu`) and sensor values | Probably 0 | 0 in every column | No decision needed |
| 9 | Instances with no machine-spec match | Not covered | 0 unmatched; 331,057 instances have no machine | No decision needed (see §3.3) |

## 3. Findings

### 3.1 Jobs without `group`

| Count | Value |
|---|---|
| Jobs with no group-tag row | 1,530 |
| Jobs with a group-tag row but a null `group` | 0 |
| Of the 1,530, jobs without a submission time (rejected whole) | 70 |
| Accepted jobs using the fallback identity | 1,460 |
| Role rows using the fallback identity (from A2 on the full tables) | 1,888 (100 in rejected jobs; 1,788 accepted) |
| Role rows using the grouped identity | 1,259,162 |
| Instance rows of the fallback roles, inheriting a null `recurrence_key` (from A4 on the full tables) | 12,810 |
| Group coverage, all jobs | 99.8550% |
| Group coverage, accepted jobs | 99.8612% |
| Group-tag rows that match no job | 1,061 |

The earlier figure of 469 was the job-table row count minus the group-tag row count (1,055,501 − 1,055,032). It is not a job count, because 1,061 group-tag rows match no job. The "99.86%" figure in the documents is correct. The figure is corrected in every design and planning document (§5).

### 3.2 Tasks with no instance rows

130 tasks have no instance rows. All 130 are `Waiting`, have a null `inst_num`, and belong to jobs without a submission time, so whole-job rejection (D-23) already removes them. No new rule is needed.

### 3.3 Instances without a machine

| Count | Value |
|---|---|
| Instances with a null `machine` | 331,057 (`Waiting` 323,840; `Ready` 7,130; `Failed` 87) |
| Of these, also null `worker_name` | 331,057 (the same rows) |
| Non-null machines missing from `pai_machine_spec` | 0 |

Machine specifications are missing only for unplaced instances, which have no machine at all. Every non-null machine matches the specification table. These rows are kept as a known source condition (D-24 Missing `worker_name`, schema §5.4), and no additional rule is needed at this stage.

### 3.4 Source keys and `source_row_number`

| Key | Table | Result |
|---|---|---|
| `job_name` | Job | Unique and non-null on all 1,055,501 rows |
| `(job_name, task_name)` | Task | Unique and non-null on all 1,261,050 rows |
| `(job_name, task_name, worker_name)` | Sensor | Unique and non-null on all 3,033,232 rows |
| `inst_id` | Group tag | Unique and non-null on all 1,055,032 rows |
| `machine` | Machine spec | Unique and non-null on all 1,897 rows |

- **`source_row_number` is mandatory only on the instance table.** It is the instance audit identity and the attempt-order tie-breaker (schema §5.4, D-21 Instance identity, framework §9.2), and is required in `rejected_required_columns["instance"]`. Schema §9.5 requires it for rejected instance rows only.
- **Job and task row numbers are optional.** Each rejected job row is traced by `job_name` and each rejected role row by `(job_name, task_name)`, which are unique and non-null in their source tables (above). When present, they are kept as `job_source_row_number` and `task_source_row_number` (design §4.1).
- The Task 2 loader adds `source_row_number` to every loaded table (`src/sources/alibaba_gpu_2020.py`), so these optional columns are present on the full-data run.

### 3.5 Consistency of duplicated source columns

These checks justify the columns that A1 drops (design §4.1).

| Check | Result |
|---|---|
| Sensor `machine` vs instance `machine`, on the 3,027,318 instance rows with a sensor row | 0 differences; 0 nulls |
| Sensor `inst_id` vs instance `inst_id`, same rows | 0 differences; 0 nulls |
| Instance `inst_id` vs job `inst_id`, all 7,522,002 instance rows | 0 differences (confirms schema §5.4: a job-level value) |
| Group-tag `user` vs job `user`, on the 1,053,971 matched jobs | Equal wherever both are present; 1 group-tag row has a null `user`. The job `user` has no nulls |

### 3.6 Lookup rows that no driving row uses

Left joins from the driving table ignore lookup rows that nothing points at. They are reported in the two-way join coverage (design §4.1), not silently lost.

| Lookup | Unused rows | Breakdown |
|---|---|---|
| Group tag | 1,061 | Tag rows whose `inst_id` matches no job (§3.1) |
| Task (by instances) | 130 | Tasks with no instance rows; all are removed by whole-job rejection (§3.2) |
| Sensor | 13,883, across 2,978 jobs | 8,713 belong to jobs not in the job table; 116 to `Waiting` jobs without a submission time; the rest belong to existing jobs, including 3,397 rows whose job and task have instance rows but under a different `worker_name` |

The sensor table adds columns only (design §4.1), and rules 11–12 count sensor coverage per worker of the instance table, so unused sensor rows cannot change eligibility.

### 3.7 Retried instance slots

| Count | Value |
|---|---|
| Instance rows | 7,522,002 |
| Distinct slots `(job_name, task_name, inst_name)` | 6,846,883 |
| Slots with more than one row (retried) | **231,632** |
| Rows in retried slots | 906,751 |
| Largest attempt index | 338 |
| Unique `instance_id` after A3 | 7,522,002 |

- The design stated 231,258 retried slots. The corrected value, 231,632, is confirmed independently from the raw `pai_instance_table.csv` by counting the slot key `(job_name, task_name, inst_name)` over all rows, including the 331,057 rows with a missing `worker_name` (`sort | uniq -c`, without the adapter). The A3 implementation gives the same result.
- The earlier figure matches a count restricted to rows that have a `worker_name` (231,259 retried slots, 905,967 rows), so it was most likely taken with null-worker rows dropped, while 906,751 was taken on all rows.
- Adding `worker_name` to the slot leaves exactly 1 repeated key (2 rows), as D-21 states.
- Corrected in schema §5.4, D-21 and design §6.

### 3.8 Null timestamps (from A5)

Counts on all rows, before rejection routing. Conversion is exact seconds × 1,000,000 into nullable `Int64`; every source time is a whole number of seconds, and nothing is filled or inferred.

| Frame | Column | Source | Null rows |
|---|---|---|---|
| Roles | `start_time_us` | Job submission | 6,942 (roles of jobs without a submission time) |
| Roles | `end_time_us` | Job completion | 324,028 |
| Roles | `launch_time_us` | Task start | 3,714 |
| Instances | `event_time_us` | Parent job submission | 111,219 (instances of jobs without a submission time) |
| Instances | `start_time_us` | Own start | 1,773,468 |
| Instances | `end_time_us` | Own end | 2,267,582 |

Reconciled in A6, after rejection routing:

| Instance rows | Without an own start | With an own start | Total |
|---|---|---|---|
| Accepted | 1,673,976 | 5,736,807 | 7,410,783 |
| Rejected (whole job, `missing_submission_time`) | 99,492 | 11,727 | 111,219 |
| Total | 1,773,468 | 5,748,534 | 7,522,002 |

The 11,727 rejected rows with their own start are rejected with their job (schema §9.5).

## 4. Missing values for Part B

The design already handles these: a missing resource gives `validity_status = partial` (D-15 Validity, eligibility and capability are separate, schema §9.1). No decision is needed.

| Table | Column | Null rows |
|---|---|---|
| Task | `inst_num` | 130 (the §3.2 tasks) |
| Task | `plan_cpu`, `plan_mem` | 18,454 each |
| Task | `plan_gpu` | 223,965 |
| Sensor | `cpu_usage` | 5,829 |
| Sensor | `avg_mem` | 1,217 |
| Sensor | `read`, `write`, `read_count`, `write_count` | 3 each |
| Sensor | `gpu_wrk_util`, `max_mem`, `avg_gpu_wrk_mem`, `max_gpu_wrk_mem` | 0 |

## 5. Effect on the plan

- Decision gate: no source anomaly needs a new decision. The excluded-role resource values, extension column names and rejected-output dtypes decisions were approved on 2026-10-24 (design §6).
- Expected counts: jobs without `group` are now 1,530 in total and 1,460 accepted (design §2).
- Rejection counts (3,663 / 6,942 / 111,219) are confirmed for the three-level reconciliation (design §4.6).
- A1 join specification (design §4.1): `source_row_number` required only on instances (§3.4); dropped columns justified by §3.5; unused lookup rows reported through two-way join coverage (§3.6).
- Corrected: the 469 figure in schema §3, §5.3 and the §15 checklist, D-05 Jobs without `group` in `canonical_schema_design_decisions.md`, `assumptions.md`, `dataset_inspection_and_integration_design.md` and `alibaba_dataset_selection_feasibility.md`.
