# Canonical Contract Decision

**Date:** 2026-10-15
**Sources:**
- Dataset Inspection and Integration Design report (`docs/data/dataset_inspection_and_integration_design.md`)
- Google Subset Pipeline Analysis report (`docs/data/google_subset_pipeline_analysis.md`)
- The gating checks on the full official Alibaba GPU v2020 tables, summarized in section 7

**How to read this document:**
- **Verified** marks facts measured on data or stated in official documentation.
- **Recommended** marks design choices.
- **Limitation** marks validity caveats.
- **Future work** marks steps not yet done.

## 1. Executive Decision

**Scope:**
- Google subset 2019 remains the reference pipeline.
- Alibaba GPU v2020 is the required full second-dataset integration.
- Alibaba 2018 is an optional reduced adapter demonstration.
- Azure is deferred.

**Recommended Alibaba GPU v2020 design:**
- An occurrence is one job submission within an official `group`.
- Each task role in that job is evaluated per instance.
- History and next-occurrence targets come only from successfully completed, resource-valid role-occurrences with **complete sensor coverage for memory evaluation**. CPU may remain missing on such rows and is then excluded from CPU-specific denominators; missing CPU does not make a role ineligible for memory evaluation.
- Memory is evaluated as a true per-instance lifetime peak.
- CPU is evaluated only as a lifetime average.

**Eligible population (verified):**
- 462,156 role-occurrences pass the eligibility checks before the multi-attempt-worker exclusion.
- 256 role-occurrences are then excluded with `exclusion_reason = multi_attempt_worker`.
- The **final eligible population is 461,900 role-occurrences**.

**Readiness:** the inspection and gating checks support this design. It is ready to become the basis for the canonical schema and adapter framework once the team accepts it.

## 2. Why This Design Fits TraceAdvisor

TraceAdvisor predicts how much CPU and memory the **next run of a recurring workload** will need, before that run starts. Alibaba GPU v2020 supports this directly.

**The trace provides recurrence (verified).**
- The official `group` tag marks jobs with the same entry script, parameters and data sources as repeated runs.
- It covers 99.86% of jobs.
- TraceAdvisor does not need to invent a recurrence rule.

**The job is the occurrence.**
- A user submits a job, and `group` repeats at job level.
- So one job submission is one occurrence.

**The task role is the evaluation unit.**
- Users request resources per task role, such as `worker`, `ps` or `tensorflow`.
- Every instance of that role inherits the same request.
- So the useful question is: "What should each instance of this role request in the next run of this group?"
- Worker replicas inside one job run in parallel; they are not repeated occurrences.

**Google and Alibaba measure at different scopes.**
- Google occurrences sum requests and peaks across all executions of a workload, i.e. full-workload scope (verified: 97.9% and 99.9% of multi-execution occurrences).
- Alibaba GPU v2020 measures per instance of a role.
- Results from the two datasets are therefore **not directly comparable**.

## 3. Final Recommended Contract

| Area | Recommended rule | Reason or limitation |
|---|---|---|
| Recurrence | `recurrence_key = group`; role recurrence = `group‖task_name` | Official tag. 99.47% of repeated groups have stable role sets. |
| Occurrence | One job submission; `occurrence_key = group‖job_name` | `job_name` is unique, so jobs submitted in the same second stay distinct |
| Evaluation unit | One task role per occurrence, sized per instance; `role_key = occurrence_key‖task_name` | Requests are specified per task and inherited per instance. `inst_num` (how many instances) is out of scope. |
| Timestamps | Order and split by **job submission** time. History requires an earlier job's **completion time ≤ the current submission time**. Task launch is lifecycle metadata only. | The recommendation is made at submission. Times are shifted by a constant, so time-of-day features are valid only in UTC+8. |
| CPU | Request = task `plan_cpu`. Actual = maximum `cpu_usage` across the role's workers: a **lifetime average**. `peak_cpu` is null. | **There is no CPU peak signal.** CPU results never claim peak safety. |
| Memory | Request = task `plan_mem` (GB). Actual = maximum `max_mem` across the role's eligible workers: a **per-instance lifetime peak** (GB). | Not total job memory. Worker maxima are never summed into a job peak; that would only be an upper bound. Job totals are descriptive only. |
| Filtering | History and targets use only successfully completed, resource-valid role-occurrences with one attempt per worker and complete sensor coverage for memory evaluation. CPU may remain missing and is excluded from CPU-specific denominators (section 5). | Creates selection bias and reduces multi-instance roles. Final eligible population: 461,900 role-occurrences (section 5). |
| Missing values | Never filled with zero. Missing CPU stays null and is excluded from CPU denominators. Ineligible rows are kept with `validity_status` and `exclusion_reason`. | 0.26% of eligible role-occurrences have missing CPU on some worker |
| Split isolation | A row is scored in a split only if its next-occurrence target is in the **same** split | Validation never uses test-period outcomes. This leaves 42,104 validation and 44,087 test rows. Those counts were calculated before the final 256-row `multi_attempt_worker` exclusion and may decrease slightly. |
| Telemetry scope | Results apply to roles with complete telemetry, inside the usable window (about day 19 to day 68.9) | Not every submitted workload |
| Metrics | CPU: average exceedance, average utilization, waste and shortfall. Memory: full peak metrics. **No any-resource metric.** Baseline selection ranks memory first. | An average-based CPU result combined with a memory peak result would be meaningless |
| Large groups | Keep all groups. Report occurrence-weighted metrics plus a group-weighted sensitivity result. | One group has 22,641 jobs; the median group has 1 |

## 4. Alibaba GPU v2020 Data Contract

| Field group | Canonical fields | Source and semantics |
|---|---|---|
| Identifiers | `dataset_id = alibaba_gpu_v2020`; `job_id`; `task_role`; `worker_id`; `machine_id` | `job_name` (= `inst_id`), `task_name`, `worker_name`, `machine` |
| Recurrence | `recurrence_key`; `recurrence_key_origin = official`; `role_recurrence_key` | `group`; `group‖task_name` |
| Occurrence and role keys | `occurrence_key`; `role_key`; `record_level = occurrence` (one row per role), plus an `instance`-level audit table | `group‖job_name`; `occurrence_key‖task_name` |
| Time | `occurrence_time_us` (submission), `occurrence_end_time_us` (completion), `launch_time_us` (first task launch), `time_semantics = submission` | Seconds × 10⁶, trace-relative |
| Requests | `requested_cpu`, `requested_memory`, optional `requested_gpu`; descriptive `requested_total_cpu` and `requested_total_memory` | `plan_cpu`, `plan_mem`, `plan_gpu` per instance; totals = sum of plan × `inst_num` |
| Observed resources | `observed_cpu_avg`, `peak_memory`, `observed_memory_avg`; `peak_cpu = null`; optional `observed_gpu_avg`, `peak_gpu_memory` | Maximum across the role's eligible workers of `cpu_usage`, `max_mem`, `avg_mem`, `gpu_wrk_util`, `max_gpu_wrk_mem` |
| Units | `cpu_unit = pct_vcpu` (600 = 6 vCPU); `memory_unit = gb` | Same unit for request and actual |
| Status | `status_raw`; `status_normalized` | Job, task and instance `status`. Only `Terminated` means success. |
| Validity | `validity_status`; `exclusion_reason` | See section 5 |
| Provenance | `source_version = cluster-trace-gpu-v2020`; source file checksums; adapter name and version; `telemetry_window` | Checksums of the job, task and group files matched the official README |
| Capability metadata | Keep PR #70's 10 existing flags and add: <br>• `recurrence_key_origin`, `resource_scope = per_instance_role`, `aggregation_method = max_over_instances`<br>• `has_cpu_peak = false`, `has_cpu_average = true`, `has_memory_peak = true`, `has_memory_average = true`, `has_gpu_signal = true`, `has_status = true`<br>• `cpu_observed_semantics = lifetime_average`, `memory_observed_semantics = lifetime_peak`<br>• `cpu_unit`, `memory_unit`, `time_semantics`, `telemetry_window`<br>• `supported_record_levels`, `evaluation_mode = next_occurrence_memory_peak_cpu_avg`, `any_resource_metric_valid = false` | **Recommended:** extend PR #70's capability model rather than replace it; bump the schema version to 0.2.0. `supports_cpu = true` must not be read as "CPU peak supported". |

The same capability fields are filled for Google 2019 (`constructed`, `full_workload`, `aligned_window_sum_then_max`, `has_cpu_peak = true`) and for Alibaba 2018 (`none`, `per_instance`, `instance_request_vs_observed`).

## 5. Filtering and Evaluation Population

**Recommended eligibility rules.** A role-occurrence is used for history values and next-occurrence targets only if every rule passes. A failing rule records the reason shown.

| Rule | `exclusion_reason` if it fails |
|---|---|
| Job is `Terminated`, has a completion time and has a `group` | `job_failed`, `job_incomplete`, `no_recurrence_key` |
| Task is `Terminated` with `plan_cpu` > 0 and `plan_mem` > 0 | `task_not_terminated`, `missing_or_invalid_request` |
| Every instance of the role is `Terminated` and has a `worker_name` | `instance_failed`, `instance_interrupted`, `instance_incomplete`, `missing_worker_name` |
| Every worker has exactly one attempt | `multi_attempt_worker` |
| Every worker of the role has a sensor row (complete sensor coverage for memory evaluation). A sensor row with missing CPU still counts; CPU stays null and is excluded from CPU-specific denominators. | `missing_sensor`, `partial_sensor_coverage` |
| Memory is valid: `max_mem ≤` host `cap_mem`, `max_mem ≥ avg_mem`, no negative values | `invalid_memory_exceeds_capacity`, `invalid_resource` |

**What "fully observed" means**
- **Memory evaluation** requires complete sensor coverage and valid memory observations. This is a hard rule. Relaxing it would turn the memory peak into an unlabeled lower bound, so it is not relaxed to increase sample size.
- **CPU may be missing** on some otherwise memory-valid rows: 1,224 role-occurrences (0.26%).
  - Such a row stays eligible for memory.
  - Its CPU actual stays null, and the row is excluded from CPU-specific denominators.
  - Alibaba GPU v2020 CPU results always mean lifetime-average CPU usage, never CPU peak safety.

**Multi-attempt workers**
- The same `worker_name` can appear on several instance rows. These are separate attempts on the same machine, each with a different instance name and start time; they are not copied rows (verified).
- The sensor table holds only one row per worker, so that row cannot be assigned reliably to one attempt.
- Attempts are therefore not merged. The role-occurrence is excluded as `multi_attempt_worker`.

**Failed jobs as history features.** Counts of earlier failed jobs in the same group may be used as history features, but only when their completion time is at or before the current submission time.

**Audit.** Every excluded or invalid record stays in the canonical output with its `validity_status` and `exclusion_reason`. Nothing is silently deleted or filled with zero.

**Resulting eligible population (verified)**

| Stage | Role-occurrences |
|---|---|
| Passing all eligibility checks except the multi-attempt-worker rule | 462,156 |
| Excluded as `multi_attempt_worker` | 256 |
| **Final eligible population** | **461,900** |

### Limitations that must be reported with every Alibaba GPU v2020 result

1. **Selection bias.**
   - Failed and incomplete jobs are excluded from history and targets.
   - Some failures may be caused by under-provisioning or out-of-memory kills, exactly what TraceAdvisor aims to prevent.
   - Results apply to **successfully completed workloads with complete telemetry**, not to every submitted workload.
   - Report the number and share of failed jobs per group.
2. **Multi-instance roles are strongly reduced.**
   - Only about 8.5% of multi-instance roles have full sensor coverage.
   - 96.7% of eligible role-occurrences are single-instance.
   - Report the 15,396 eligible multi-instance role-occurrences as a separately labeled subgroup. Make claims about distributed training only from that subgroup.
3. **Shortened telemetry window.**
   - Sensor coverage begins mainly around day 19.
   - Only about the later 50 days of the 68.9-day trace are usable.
4. **Concurrent targets.** 245 validation and 251 test targets were submitted in the same second as the current job. These should be flagged.

## 6. Google and Alibaba Differences

This document **does not change the Google pipeline**. Google's known issues (abnormal events included; targets that cross split boundaries) remain tracked in the Google Subset Pipeline Analysis report. Any change to Google needs separate team approval.

| Aspect | Google subset 2019 | Alibaba GPU v2020 |
|---|---|---|
| Recurrence source | Constructed by TraceAdvisor: `user‖collection_logical_name` | Official source tag: `group` |
| Occurrence definition | Executions of one recurrence starting at the same time | One job submission |
| Resource scope | Full workload: requests and peaks summed across executions | Per instance of a task role |
| CPU semantics | Peak: aligned-window sum, then maximum (normalized compute units) | Lifetime average only (percent of one vCPU); no CPU peak |
| Memory semantics | Peak: aligned-window sum, then maximum (normalized) | Per-instance lifetime peak (GB) |
| Next-occurrence target support | CPU and memory peaks | Memory peak; CPU average |
| Timing | First execution start | Job submission |
| Filtering | None at present: failed, evicted, lost and killed records included | Successfully completed, fully observed, resource-valid role-occurrences only |
| Evaluation limitations | Small validation population (329 occurrences); targets cross splits | No CPU peak; no any-resource metric; selection bias; mostly single-instance; about 50-day window |

**Consequence.** Alibaba GPU v2020 results show that TraceAdvisor generalizes to a second recurring workload. They are not a higher or lower score on the same task as Google, and **CPU results must never be compared numerically** across the two datasets.

## 7. Evidence from Inspection and Gating Checks

All findings below are **verified** on the full official Alibaba GPU v2020 tables (1,055,501 jobs; 1,261,050 role-occurrences), unless noted.

| Finding | Result |
|---|---|
| `group` coverage | 99.86% of jobs. No group spans more than one user. |
| Role-set stability | 99.47% of repeated groups have identical task-role sets across jobs |
| Eligible role-occurrences | 462,156 of 1,261,050 (36.65%), from 456,665 jobs in 132,906 groups, pass the eligibility checks **before** the multi-attempt-worker exclusion. 256 are then excluded as `multi_attempt_worker`, leaving a **final eligible population of 461,900**. |
| Repeated eligible occurrences | **10,815 role recurrences have at least five eligible role-occurrences** (7,645 have at least ten) |
| Full sensor coverage | 67.1% of single-instance roles but only **about 8.5% of multi-instance roles** |
| Single-instance share | **96.7%** of eligible role-occurrences |
| Multi-attempt workers | 19,102 duplicated worker names: 0% differ in job, task or machine; 99.99% differ in instance name. They affect **256 role-occurrences (about 0.06%)**. |
| Resource-invalid rows | **512 (about 0.11%)**, all `max_mem` above host capacity |
| Missing CPU in eligible rows | 1,224 (0.26%) |
| Telemetry window | 0% coverage before day 17, about 95% from **day 19**, leaving about **50 usable days** |
| Unit comparability | `plan_mem` and `max_mem` are both GB. 12.0% of workers exceed their memory request, and 15.4% exceed their CPU request on average usage. |
| Split-isolated population | **42,104 validation** and **44,087 test** rows across about 9,700 groups each. Split isolation removes 7,742 validation rows (15.5% of validation rows with a target). These counts predate the final 256-row `multi_attempt_worker` exclusion and may decrease slightly. |

The split-isolated counts (42,104 validation and 44,087 test rows) were calculated **before** the final 256-row `multi_attempt_worker` exclusion. Final counts may decrease slightly after that exclusion. The exclusion removes 0.06% of the eligible role-occurrences, either directly or by changing which occurrence is the next target, so the decrease is expected to be small. The exact final counts will be produced by the implemented pipeline.

## 8. Final Recommendation for the Project

- **Accept** the Alibaba GPU v2020 design described in sections 3–5.
- **Use** it as the basis for the canonical schema and adapter framework.
- **Keep Alibaba 2018** as an optional reduced integration demonstration.
  - It shows instance-level request versus observed CPU and memory peaks.
  - It has no recurrence identity and must **not** be used to define the main recurrence-based pipeline.
- **Defer Azure.**
- **Update the existing PR #70 documents in place.** PR #70 is an open branch owned by another contributor, so these edits need coordination with its author.

## 9. Next Steps

All of these are **future work**:

1. Use this contract as the design baseline.
2. Update the existing `docs/data/canonical_workload_schema.md` in place, as schema v0.2.0.
3. Update the existing `docs/data/adapter_framework.md` in place. Add multi-table preparation, chunked loading, exclusion-reason output and provenance.
4. Implement the Alibaba GPU v2020 adapter.
5. Add canonical validation tests.
6. Run the shared history, target, recommendation and evaluation pipeline on Alibaba GPU v2020, with memory-first baseline selection and no any-resource metric.
7. Add Alibaba 2018 only if time permits.

Do not create a separate `canonical_schema.md` or a second adapter framework document while the PR #70 files are retained.

## Implementation Status

This is a design document only. No schemas, adapters, notebooks, Python files, configurations or tests were changed, and none of the decisions above is implemented.
