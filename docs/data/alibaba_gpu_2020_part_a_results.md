# Task 3 (#79) Part A Results: Alibaba GPU 2020

**Date:** 2026-10-24
**Plan steps:** Part A, S1 and A1–A8 (`docs/planning/task3_implementation_plan.md` §5, §9)
**Code:** `AlibabaGPU2020Adapter.prepare_sources` in `src/adapters/alibaba_gpu_2020.py`; tests in `tests/test_alibaba_gpu_2020_adapter.py` (116 tests, all passing)
**Output contract:** `docs/design/alibaba_gpu_2020_output_contract.md` (what Tasks 4, 6, 7 and 8 rely on). This file records the measured Part A figures.
**Data:** `data/raw/alibaba_gpu_2020/` (gitignored), verified as in the source data checks report (`docs/data/alibaba_gpu_2020_source_data_checks.md`)
**Method:** all six tables loaded with their official headers, `quoting=QUOTE_NONE`, only empty fields treated as missing, and a 1-based `source_row_number` added to each table, as the Task 2 loader does; then one `prepare_sources` call. The run scripts are read-only and not committed.
**For the report:** cite this document for **pipeline validation** (the adapter's output on the full tables is correct). Cite `docs/data/alibaba_gpu_2020_source_data_checks.md` for **data validation** (the source tables match the design).
**Decision IDs:** D-01 to D-24 are the schema design decisions in `docs/design/canonical_schema_design_decisions.md`; each is named where it is first cited.

**Result: Part A is complete. Every reconciliation holds exactly, linkage passes on accepted and rejected rows, and the source data raised no case that needed a new decision. The three Part B decisions (excluded-role resource values, extension column names, rejected-output dtypes) were approved afterwards (2026-10-24).**

---

## 1. Prepared frames

`prepare_sources` returns four frames. Their columns follow plan §4.3.

| Frame | Rows | Columns | Memory (deep) | Accepted | Rejected |
|---|---|---|---|---|---|
| `jobs` | 1,055,501 | 12 | 0.23 GB | 1,051,838 | 3,663 |
| `roles` | 1,261,050 | 31 | 0.82 GB | 1,254,108 | 6,942 |
| `instances` | 7,522,002 | 41 | 9.34 GB | 7,410,783 | 111,219 |
| `rejected` | 121,824 | 64 | 0.18 GB | — | 3,663 `job` + 6,942 `role_occurrence` + 111,219 `instance` |

- Each of `jobs`, `roles` and `instances` has one row per source row of its table, in source order. No row is dropped, added or duplicated by a join.
- `roles` and `instances` also carry `time_basis = trace_relative` (A5).
- The only rejection reason is `missing_submission_time` (121,824 rows). All 3,663 rejected jobs are `Waiting`.

## 2. Row reconciliation (plan §5.6)

| Level | Reconciliation | Holds |
|---|---|---|
| Task table | 1,261,050 = 1,254,108 accepted roles + 6,942 rejected `role_occurrence` rows | Yes |
| Instance table | 7,522,002 = 7,410,783 accepted instances + 111,219 rejected `instance` rows | Yes |
| Job table | 1,055,501 = 1,051,838 distinct accepted `job_name` + 3,663 rejected `job` rows | Yes |

- 0 accepted `role_key` and 0 accepted `instance_id` values appear in the rejected output.
- 0 accepted roles have a null `start_time_us`; 0 accepted instances have a null `event_time_us`.

## 3. Join coverage

These are the values stored in `adapter.join_coverage_counts`, which Part B adds to the metadata (B6). `driving_unmatched` includes the rows with a null key.

| Join | Driving matched | Driving unmatched | Of which null key | Lookup used | Lookup unused |
|---|---|---|---|---|---|
| `job_group_tag` (job ← group tag on `inst_id`) | 1,053,971 | 1,530 | 0 | 1,053,971 | 1,061 |
| `task_job` (task ← job on `job_name`) | 1,261,050 | 0 | 0 | 1,055,501 | 0 |
| `instance_task` (instance ← task on `job_name`, `task_name`) | 7,522,002 | 0 | 0 | 1,260,920 | 130 |
| `instance_sensor` (instance ← sensor on `job_name`, `task_name`, `worker_name`) | 3,027,318 | 4,494,684 | 331,057 | 3,019,349 | 13,883 |
| `instance_machine_spec` (instance ← machine spec on `machine`) | 7,190,945 | 331,057 | 331,057 | 1,897 | 0 |

- **Group tag:** the 1,530 jobs without a tag row use fallback identity (1,460 of them accepted).
- **Tasks:** 130 tasks have no instance rows (checks report §3.2).
- **Sensor rows on retried workers:** 3,027,318 matched instance rows use 3,019,349 sensor rows, because every attempt of a retried worker carries that worker's single sensor row. That accounts for the 7,969 extra matches. Sensor rows are never aggregated (D-17 Eligibility and exclusion rules); Part B rule 10 excludes these roles.
- **Machine spec:** the only unmatched rows are the 331,057 instances with no machine, which are the same rows with no `worker_name` (check 9).

## 4. Identity, time and linkage

| Check | Result |
|---|---|
| `role_key` unique | Yes, on all 1,261,050 roles |
| Fallback roles (null `recurrence_key`) | 1,888 (1,788 accepted, 100 rejected) |
| `instance_id` unique | Yes, on all 7,522,002 instances |
| Distinct slots / retried slots / rows in retried slots | 6,846,883 / 231,632 / 906,751; largest attempt index 338 |
| Instances with a parent role (`has_parent_role`) | All |
| Inherited identity (A4) | 0 differences from the parent. 12,810 instances inherit a null `recurrence_key` |
| Timestamp dtypes | `Int64` for every `*_time_us` column; `instance_attempt_index` and `source_row_number` are `int64` |
| Null times after A5 (all rows) | Roles: `start_time_us` 6,942; `end_time_us` 324,028; `launch_time_us` 3,714. Instances: `event_time_us` 111,219; `start_time_us` 1,773,468; `end_time_us` 2,267,582 |
| Accepted instances without their own start time | 1,673,976 (99,492 more are rejected) |
| **Linkage (A7), accepted** | 1,254,108 roles / 7,410,783 instances. Passed: 0 orphans, 0 identity mismatches, 0 event-time mismatches |
| **Linkage (A7), rejected** | 6,942 roles / 111,219 instances. Passed: 0 orphans, 0 identity mismatches, 0 non-null `start_time_us` / `event_time_us` |
| Instances whose parent is on the other side of the rejection split | 0 |

## 5. Decisions

- **Source anomalies** (duplicate sensor keys, orphans, end before start, negative values, missing host capacity): none found, so no decision was needed (plan §7, checks report §2).
- **Excluded-role resource values, extension column names, rejected-output dtypes:** approved on 2026-10-24 (plan §7).

## 6. What Part B can rely on

- Part B reads only these four frames and never changes an identity, time, join or routing column (plan §4.1).
- Only rows with `is_rejected = False` go into the views. The `rejected` frame is already checked with `validate_rejected_output` and `rejected_required_columns`.
- Values from a join are present only when the match flag (`has_group_tag`, `has_job`, `has_parent_role`, `has_sensor`, `has_machine_spec`) is true. Unmatched values are null, never zero.
- The machine spec's `gpu_type` is `machine_gpu_type`; the task `gpu_type` is unchanged on roles.
- `launch_time_us` is an extension column only and never replaces `start_time_us`.
- In the `rejected` frame, `concat` widened 8 columns to `object`, such as bool flags that are null on other levels. Values are unchanged; the B5 rejected output should set its own dtypes.
- **Memory:** `instances` takes 9.34 GB. The B7 build script should load only the needed columns and remove the extra deep copy in the default `BaseDatasetAdapter.prepare_sources` if memory runs out (plan §10).
- **Linkage on the final views:** `adapt_sources` runs it again on accepted rows only. The rejected-set check stays in `prepare_sources`.

## 7. Reproducing

1. Load the six tables as in **Method** above, each with a 1-based `source_row_number`.
2. Call `AlibabaGPU2020Adapter().prepare_sources(sources)`.
3. Compare the frames with §1–§4. The call takes about 2.5 minutes including loading.
4. Read the join coverage from `adapter.join_coverage_counts`.
