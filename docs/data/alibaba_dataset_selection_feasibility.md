# Alibaba and Azure Dataset Selection and TraceAdvisor Integration Feasibility

**Date:** 2026-10-15
This document records the dataset-selection and integration-feasibility analysis for the current TraceAdvisor project.
**Related reports:**
- Dataset Inspection and Integration Design report (`docs/data/dataset_inspection_and_integration_design.md`)
- Google Subset Pipeline Analysis report (`docs/data/google_subset_pipeline_analysis.md`)

### Labels used in this document

| Label | Meaning |
|---|---|
| **Verified** | Stated in official documentation, read in the TraceAdvisor repository, or measured on downloaded official data |
| **Design choice** | A recommendation adopted for the project |
| **Limitation** | A validity caveat that must accompany results |
| **Requires confirmation** | Not yet verifiable from the available evidence |

The Azure section additionally uses these evidence labels:

| Evidence label | Meaning |
|---|---|
| **[DOC]** | Official Azure documentation |
| **[REPO]** | The TraceAdvisor repository |
| **[HEAD]** | A partial download of the first rows of a raw file. Head rows show schema and encoding only, not distributions. |
| **[NEEDS DATA]** | Cannot be settled without the full raw data |

Nothing was implemented in producing this analysis.

---

## 1. Executive Decision

**Final dataset scope and roles**

| Dataset | Role in the project | Why |
|---|---|---|
| **Google subset 2019** | **Reference pipeline** | The existing TraceAdvisor pipeline: constructed recurrence, CPU and memory peaks, requests. Its known issues (abnormal events included, targets crossing split boundaries, machine duplication) are corrected separately, as recorded in the Google Subset Pipeline Analysis report. |
| **Alibaba GPU v2020** | **Required full second-dataset TraceAdvisor integration** | The only Alibaba trace with an **official recurrence tag** (`group`, covering 99.86% of jobs), discrete job submissions with status, per-instance requests, and a true memory peak in the same unit as the memory request (GB). |
| **Alibaba 2018** | **Optional reduced adapter-integration demonstration, if time permits** | It has CPU and memory requests and peaks per instance, and an adapter already exists on PR #70. But it has **no recurrence identity**, so it cannot support next-occurrence targets without an invented rule. It must not define the main recurrence design. |
| **Azure VM** | **Deferred from the current implementation phase** | No recurrence, no requests, no observed memory and no status. The existing repository work labeled V2 actually used the 2017 V1 trace. |
| Other Alibaba traces | Rejected for the current objective | Each lacks observed usage, requests, peaks, recurrence or history depth (section 7). There is **no Alibaba 2019 trace**. |

**Alibaba GPU v2020 design (design choice)**
- One occurrence is one job submission within an official `group`.
- One task role in that job is the evaluation and target unit, sized per instance.
- Memory is evaluated as a per-instance lifetime peak (GB).
- CPU is evaluated only as a lifetime average. There is no CPU peak, and any-resource metrics are not reported.
- History and targets use only successfully completed, resource-valid role-occurrences with complete sensor coverage for memory evaluation. The final eligible population is 461,900 role-occurrences.

**Final implementation order**

Google reference corrections → Alibaba GPU v2020 full pipeline → optional Alibaba 2018 adapter demonstration → Azure deferred

Results from different datasets are **not directly comparable**. Google measures full-workload scope; Alibaba GPU v2020 measures per instance of a task role.

---

## 2. TraceAdvisor Requirements

These requirements are verified from:
- the Google pipeline (`pipelines/google_subset/`);
- the shared evaluator (`src/evaluation/metrics.py`, `src/evaluation/evaluator.py`);
- the canonical schema on PR #70 (`src/canonical/schema.py`, `docs/data/canonical_workload_schema.md`).

| Requirement | Why it matters | Full next-occurrence pipeline | Reduced adapter demonstration |
|---|---|---|---|
| **Recurrence identity**, kept separate from job, task or instance IDs | History and next-occurrence targets are defined within a recurrence key. The schema allows `recurrence_key` only when it is "explicitly available or validated". | **Required** | Not required; `recurrence_key` stays null |
| **Discrete occurrences** with start and end times | History uses completed earlier occurrences (`end ≤ t`); targets use the next occurrence | **Required** | Instance or interval rows are enough |
| **Requested** CPU and memory known before execution | Request baseline; the pre-execution setting itself | Required | Useful for request-versus-observed rows |
| **Observed values with peak semantics** | Violations compare the peak with the recommendation. Averages understate under-provisioning. | Required per resource evaluated. An average-only resource must be labeled average-usage evaluation. | Observed values, labeled with their semantics |
| **Matching units** for actual and recommended values | `validate_evaluator_view` requires matching units | Required | Required |
| **Each resource independent; unknown kept as null** | Missing and unsupported values are never zero | Required | Required |
| **Chronological history and splits** | Point-in-time history needs several earlier completed occurrences, plus a 70/15/15 split | Required | Not required |
| **Status information** | Failed, running and cut-off runs must be distinguishable (a known gap in the Google pipeline) | Required for filtering | Recommended |
| **Evaluator compatibility** | The evaluator compares only CPU and memory. GPU would be a dataset-specific extension. Any-resource metrics are valid only when both resources have meaningful actuals. | Required | Required |

**Current repository state (verified)**
- **`main`:**
  - only the Google pipeline exists;
  - Notebook 05 is empty (0 bytes);
  - there is no `src/adapters` or `src/canonical`.
- **PR #70 (open, unmerged):**
  - `BaseDatasetAdapter` / `AdapterResult` framework;
  - canonical schema v0.1.0;
  - capability flags (`config/dataset_capabilities.json`);
  - `Alibaba2018Adapter` (instance level) and `AzureVMAdapter`;
  - `ReferenceOccurrenceAdapter` (a contract test adapter, not a production Google adapter);
  - tests.
  - Alibaba 2018 is registered with `supports_recurrence=False`, `supports_targets=False` and `supports_ml=False`.
- **PR #70 semantics study** (`dataset_semantics_study_FINAL.md`):
  - studied only Alibaba 2018 and Azure;
  - its Azure sample is actually the 2017 V1 trace (section 8.1);
  - Alibaba GPU v2020 and the 2023–2026 traces were not evaluated.
- **Alibaba GPU v2020:** nothing exists in the repository (no adapter, notebook, loader or capability entry).

---

## 3. Alibaba Dataset Landscape

The inventory comes from the official repository listing (`api.github.com/repos/alibaba/clusterdata/contents`) and the top-level README (verified).

| Directory | Release / paper | Collection period (documented) | Workload type | Scale | Project role |
|---|---|---|---|---|---|
| `cluster-trace-v2017` | 2017 | 24-hour window; usage disclosed for **12 consecutive hours** | Online services and batch, co-located | ~1,300 machines | Rejected |
| `cluster-trace-v2018` | 2018 | **8 days** | Online containers (Sigma) and batch DAG jobs (Fuxi) | ~4,000 machines; 48 GB compressed / 280 GB extracted | **Optional reduced demonstration** |
| `cluster-trace-gpu-v2020` | NSDI '22 | **July–August 2020** (~68.9 days measured) | AI/ML training and inference on GPUs (PAI) | 6,500+ GPUs, ~1,800 machines; ~1.4 GB compressed | **Required full integration** |
| `cluster-trace-microservices-v2021` | SoCC '21 | 12 hours | Online microservices | 20,000+ microservices | Rejected |
| `cluster-trace-microservices-v2022` | 2022 | 13 days (~2 TB) | Online microservices | 28,000+ microservices, 470,000+ containers | Rejected |
| `cluster-trace-microarchitecture-v2022` | ICPP '22 | Not checked | Microarchitectural counters (latency-critical and batch) | — | Rejected |
| `cluster-trace-gpu-v2023` | ATC '23 | Not documented | GPU-sharing pod specifications (scheduler-simulator input) | 8,152 pods, 1,523 nodes | Rejected |
| `cluster-trace-gpu-v2025` | NSDI '25 | Not documented | Long-running DLRM inference, GPU-disaggregated | 156 services, 23,871 instances | Rejected |
| `cluster-trace-gpu-v2026` | OSDI '26 | **~6 months** (`day=0..184`) | Training, online and offline inference, dev (ASI) | Up to 155,410 GPUs; pod table 352 GB compressed | Rejected (at most a limited CPU-only study) |
| `cluster-trace-v2026-GenAI` | 2026 | Not documented (timestamps anonymized) | Stable-diffusion serving | Container-level metrics | Rejected |
| `cluster-trace-v2026-maas` | ATC '26 | **~6 months** daily; **1 week** at 5-minute resolution | LLM inference (online and offline) | 100,000+ GPUs; ~15 GB compressed | Rejected |
| `cluster-trace-v2026-spot-gpu` | ASPLOS '26 | Not documented | High-priority and spot AI jobs | 4,278 GPU nodes | Rejected |

**There is no `cluster-trace-v2019` directory, and the README lists no 2019 release (verified).**

Only two of the twelve traces contain both a resource request and an observed resource **peak** for the same unit: **v2018** and **GPU v2020**. Only **GPU v2020** also has an officially documented recurrence identifier. In upstream issue #114 the maintainer confirmed that "job instances with the same `group` id are treated as recurring ones".

---

## 4. Alibaba Dataset Comparison

| Criterion | Alibaba 2018 | **Alibaba GPU v2020** | Alibaba GPU v2026 | Alibaba MaaS v2026 |
|---|---|---|---|---|
| Workload type | Batch DAG jobs and online containers | ML training and inference (GPU) | Training, inference, dev (GPU) | LLM inference, online and offline |
| Hierarchy | Job → task → instance (batch); `app_du` → container (online) | Job → task (role) → instance (worker) | Workload → pod, one row per hour | App → instance, one segment per day; 5-minute intervals for one week |
| Identifiers | `job_name`, `task_name`, `instance_name`, `machine_id`; `app_du` | `job_name`, `inst_id` (= job), `user`, `task_name`, `inst_name`, `worker_name`, `machine`, **`group`**, `workload` | `pod_id`, `workload_id` (nullable), `server_id` | `instance_id`, `app_id`, `model_id`, `base_id` |
| Recurrence | **None documented** | **Official `group`** (README; issue #114) | None (`workload_id` not documented as recurrence) | None (`app_id` is a long-running service) |
| Discrete occurrences | Jobs, but no recurrence to repeat them | **Job submissions within `group`** | Pod-hour intervals | Instance-day intervals |
| CPU request | `plan_cpu` per task, 100 = 1 core | `plan_cpu` per task, inherited per instance, 600 = 6 vCPU | `cpu_request_cores` | **None** |
| Memory request | `plan_mem`, normalized [0, 100] | `plan_mem`, **GB** | **None** | **None** |
| Observed CPU | `cpu_avg`, **`cpu_max`** per instance | `cpu_usage` = **lifetime average**, percent of one vCPU (issue #125) | `avg_cpu_request_util`, hourly average relative to request | `cpu_usage`, mean cores |
| Observed memory | `mem_avg`, **`mem_max`**, normalized | `avg_mem`, **`max_mem` (lifetime maximum, GB)** | `avg_memory_util` (denominator undocumented) | `mem_usage`, mean GiB |
| Peak availability | CPU and memory, per instance | **Memory only** | None | None (maximum of 5-minute means possible for one week) |
| GPU signals | None | `plan_gpu`, `gpu_wrk_util` (average), `max_gpu_wrk_mem` (maximum), `gpu_type` | `gpu_request`, `gpu_mem_request`, `avg_gpu_sm_util`, `avg_gpu_mem_gib` | `gpu_count`, `gpu_mem_alloc`, `sm_util`, `gpu_mem_util` |
| Status | Task and instance `status`; `seq_no` / `total_seq_no` | Job, task and instance `status`; only Terminated is success | `state_public` per hour | None |
| Timestamps | Seconds from trace start | Seconds with a constant offset (time of day preserved in UTC+8) | Day and hour partitions | Relative seconds and days |
| Next-occurrence support | **None without an invented recurrence rule** | **Memory peak; CPU average only** | None (intervals, no peaks) | None (long-running, no peaks) |
| Evaluator compatibility | CPU and memory, per current instance | Memory peak metrics; CPU average-usage metrics; **no any-resource metric** | CPU average relative to request, hourly | No Request baseline possible |
| Existing TraceAdvisor work | Adapter, tests and semantics study (PR #70) | None | None | None |
| Implementation difficulty | Low for the demonstration; high for a full pipeline | Medium | High | Medium–High, with limited value |
| **Final project role** | **Optional reduced demonstration** | **Required full integration** | Rejected | Rejected |

---

## 5. Alibaba GPU v2020 Detailed Feasibility

All facts in this section are **verified**, unless labeled otherwise. They come from:
- the official README;
- the full official tables downloaded for inspection (job, task and group checksums matched the README);
- gating checks run on the full official tables (role-set stability, eligibility population, duplicate worker attempts, resource validity and split-isolated targets).

### 5.1 Dataset identity

| Item | Value |
|---|---|
| Name | `cluster-trace-gpu-v2020`, Alibaba PAI; NSDI '22 "MLaaS in the Wild" |
| Period | July–August 2020. Job submission times span **68.9 days**. |
| Workload | Hybrid AI/ML training (parameter-server/worker roles) and inference (evaluator role) |
| Scale | More than 6,500 GPUs on about 1,800 machines (1,897 machines in `pai_machine_spec`) |
| Download | `https://aliopentrace.oss-cn-beijing.aliyuncs.com/v2020GPUTraces/<table>.tar.gz`; backup at `github.com/qzweng/clusterdata-cluster-trace-gpu-v2020-data` |
| Integrity | The README publishes SHA-256 checksums. Job, task and group tables matched. |
| Format | Headerless CSV; column names come from the README |
| Local state | Not in the repository. A local path (for example `data/raw/alibaba_gpu_v2020/`) is not yet defined. |

**Tables**

| Table | Rows | Compressed size | Content |
|---|---|---|---|
| `pai_job_table` | 1,055,501 | 60 MB | Job submission: `job_name`, `inst_id`, `user`, `status`, `start_time`, `end_time` |
| `pai_task_table` | 1,261,050 | 34 MB | Task role: `task_name`, `inst_num`, `status`, times, `plan_cpu`, `plan_mem`, `plan_gpu`, `gpu_type` |
| `pai_instance_table` | 7,522,002 | 663 MB | Instance: `inst_name`, `worker_name`, `status`, times, `machine` |
| `pai_sensor_table` | 3,033,232 | 388 MB | Per-worker lifetime usage |
| `pai_group_tag_table` | 1,055,032 | 53 MB | `group`, `workload`, `gpu_type_spec`, `user` |
| `pai_machine_spec` | 1,897 | 32 KB | `cap_cpu` (64–96), `cap_mem` (384–512 GB), `cap_gpu` (0–8) |
| `pai_machine_metric` | not downloaded | 198 MB | Machine-level averages per instance lifetime |

### 5.2 Modeling unit (design choice)

- **One occurrence is one job submission within an official `group`.**
  - `recurrence_key = group`.
  - `occurrence_key = group‖job_name`. `job_name` is unique, so this key is unambiguous even when two jobs are submitted in the same second.
- **The evaluation and target unit is one task role in that job, sized per instance.**
  - `role_key = occurrence_key‖task_name`.
  - The role recurrence is `group‖task_name`.
- **Worker replicas are not separate recurrence occurrences.** They run in parallel within one job.
- `workload` (tagged on 9.7% of jobs, e.g. bert, ctr, nmt) and `worker_name` are **not** recurrence keys.

**Supporting facts (verified)**
- `job_name` and `inst_id` are one-to-one, with 0 duplicates.
- Jobs have 1–4 tasks (median 1); 81.32% of eligible jobs are single-task.
- Only 19.3% of sensor-covered jobs have more than one worker.
- Plans are specified per task and inherited per instance; sensor rows are per worker.

### 5.3 Recurrence (verified)

| Measure | Value |
|---|---|
| Jobs with a `group` | **99.86%**; 469 jobs (0.04%) have none |
| Groups spanning more than one user | 0 |
| Number of groups | 316,458. Median size 1, 99th percentile 61, maximum 22,641. |
| Groups with ≥ 2 jobs (all statuses) | 43,060, covering 74.0% of jobs |
| Repeated groups with identical task-role sets across jobs | **99.47%**. 99.72% of role-occurrences belong to roles present in every job of their group. |

### 5.4 Resource semantics

| Field | Meaning | Unit | Request or observed | Semantics | Use in TraceAdvisor |
|---|---|---|---|---|---|
| `plan_cpu` | CPU requested per instance | Percent of one vCPU (600 = 6 vCPU) | Request | — | `requested_cpu` |
| `plan_mem` | Memory requested per instance | GB | Request | — | `requested_memory` |
| `plan_gpu` | GPU requested per instance | Percent of one GPU | Request | — | Optional `requested_gpu` |
| `cpu_usage` | CPU used per worker | Percent of one vCPU | Observed | **Lifetime average** | CPU actual = maximum across the role's workers. **Not a peak.** |
| `avg_mem` | Memory used per worker | GB | Observed | Lifetime average | `observed_memory_avg` |
| `max_mem` | Memory used per worker | GB | Observed | **Lifetime maximum** | Memory actual = maximum across the role's eligible workers |
| `gpu_wrk_util`, `avg_gpu_wrk_mem`, `max_gpu_wrk_mem` | GPU use and GPU memory | Percent / GB | Observed | Average / average / maximum | Optional; not evaluated by the shared evaluator. There is no GPU-memory request. |
| `cap_cpu`, `cap_mem`, `cap_gpu` | Machine capacity | Cores / GB / GPUs | Capacity | — | Validity checks only |

**Design choices and limitations**
- **Memory.** The role memory actual is the maximum `max_mem` across eligible workers.
  - It is a **per-instance role peak, not total job memory**.
  - Per-worker maxima are never summed into a job peak. Without a time series, that sum is only an upper bound.
  - Job totals (`plan × inst_num`) are kept as descriptive values only.
- **CPU.** There is **no CPU peak**. CPU results must be labeled **average-usage evaluation**:
  - allowed: average exceedance, average utilization, waste and shortfall;
  - never claimed: CPU peak safety.
- **Any-resource metrics are not valid for this dataset.** With an average-based CPU actual, the combined metric would be meaningless. Baseline selection ranks memory first.
- **Unit comparability (verified).**
  - `plan_mem` and `max_mem` are both GB. The median per-worker ratio is 0.196, and 12.0% of workers exceed their memory request.
  - `cpu_usage` exceeds `plan_cpu` for 15.4% of worker rows, even on averages.

### 5.5 Time semantics

| Field | Source | Use (design choice) |
|---|---|---|
| Occurrence time | Job `start_time` (**submission**) | Ordering within a group and chronological splits |
| Occurrence end | Job `end_time` (**completion**) | History eligibility: an earlier occurrence counts only if its end time is at or before the current submission time |
| Launch time | Earliest task `start_time` | Lifecycle metadata only (wait time = launch − submission) |

**Verified facts and limitations**
- Times are in seconds, shifted by a constant. Time of day and weekday are preserved only in UTC+8; dates are fake.
- Every Terminated job has an end time, and job `end < start` occurs 0 times.
- Job start is null for 3,663 Waiting jobs. Job end is null for 296,420 jobs (Failed 230,935; Running 61,867; Waiting 3,618).
- Several jobs in a group can share a submission second. They are ordered by `job_name` and are not each other's history.

### 5.6 Gating results (verified)

| Result | Value |
|---|---|
| `group` coverage | 99.86% of jobs |
| Stable role sets | 99.47% of repeated groups |
| Role-occurrences passing the initial eligibility checks | **462,156** of 1,261,050 (36.65%), from 456,665 jobs in 132,906 groups |
| Excluded as `multi_attempt_worker` | **256** (about 0.06%) |
| **Final eligible population** | **461,900 role-occurrences** |
| Role recurrences with at least five eligible role-occurrences | **10,815** (7,645 with at least ten) |
| Single-instance share of eligible role-occurrences | **96.7%** |
| Multi-instance roles with full sensor coverage | **About 8.5%** (15,631 of 183,407); 15,396 eligible multi-instance role-occurrences remain |
| Single-instance roles with full sensor coverage | 67.1% |
| Resource-invalid role-occurrences | **512 (about 0.11%)**, all `max_mem` above host `cap_mem` |
| Missing CPU on otherwise memory-valid role-occurrences | **1,224 (about 0.26%)** |
| Sensor coverage | 0% before day 17; about 95% from **day 19** onward. Usable window is **about 50 days**. |
| Split-isolated rows | **42,104 validation** and **44,087 test** rows, about 9,700 groups each. These were calculated **before** the final 256-row `multi_attempt_worker` exclusion and may decrease slightly. Split isolation removed 7,742 validation rows. |
| Same-second targets | 245 validation and 251 test targets submitted in the same second as the current job |

**Whole-table data quality, before filtering**

| Item | Value |
|---|---|
| Job status | Terminated 732,355; Failed 256,555; Running 62,928; Waiting 3,663 |
| Task status | Terminated 885,073; Failed 256,762; Running 115,501; Waiting 3,714 |
| Instance status | Terminated 4,757,371; Failed 969,975; Running 809,664; Interrupted 654,022; Waiting 323,840; Ready 7,130 |
| Sensor coverage | 40.2% of instance rows; 79.3% of jobs |
| Null `worker_name` instance rows | 331,057 |
| Duplicate `worker_name` (non-null) | 45,689 rows across 19,102 names. Each name has one job, task and machine, but 99.99% have more than one `inst_name` and 98.69% more than one start time. These are **separate attempts**, not copies. |
| Tasks with more instance rows than `inst_num` | 4.5% (none have fewer) |
| `max_mem` above host capacity | 5,322 sensor rows (maximum 2,757.6 GB against a 512 GB maximum capacity) |
| Request nulls | `plan_cpu` / `plan_mem` null for 18,454 tasks; `plan_cpu ≤ 0` for 11 |

### 5.7 Filtering and limitations

**Eligibility (design choice).** History values and next-occurrence targets use only role-occurrences meeting all of these:
- the job is Terminated, has a completion time and has a `group`;
- the task is Terminated with a valid positive request;
- every instance is Terminated and has a `worker_name`;
- every worker has exactly one attempt;
- every worker has a sensor row (**complete sensor coverage for memory evaluation**);
- memory values are valid.

**Handling rules**

| Situation | Handling |
|---|---|
| Failed or incomplete job, task or instance | Ineligible; kept with `validity_status` and an `exclusion_reason` |
| Missing or partial sensor coverage | Ineligible for memory evaluation. Not zero-filled. Not relaxed to increase the sample size. |
| Worker with several attempts | Not silently merged, because the single sensor row cannot be assigned to one attempt. Excluded as `exclusion_reason = multi_attempt_worker`. |
| Invalid memory (`max_mem` above `cap_mem`, `max_mem` below `avg_mem`, negative) | Ineligible; kept for audit |
| Missing CPU on a memory-valid row | Stays eligible for memory. CPU stays null and is excluded from CPU-specific denominators. |
| Earlier failed jobs | May be counted as history features only if their completion time is at or before the current submission time |
| Any excluded record | Never silently deleted and never filled with zero |

**Limitations to report with every Alibaba GPU v2020 result**
1. **Selection bias.** Failed or incomplete jobs are excluded, and some failures may be caused by under-provisioning or out-of-memory kills. Results apply to successfully completed, fully observed workloads, not to every submitted workload. Report the number and share of failed jobs per group.
2. **Reduced multi-instance coverage.** 96.7% of eligible role-occurrences are single-instance. Report the 15,396 multi-instance role-occurrences as a separately labeled subgroup.
3. **Shortened telemetry window.** About the later 50 days of the 68.9-day trace are usable.
4. **Concurrent same-second targets.** These should be flagged.
5. **No CPU peak.** CPU results are lifetime-average usage only.
6. **Large groups.** One group has 22,641 jobs. Report occurrence-weighted metrics plus a group-weighted sensitivity result.

**Open item (requires confirmation):** whether the trace license (`cluster-trace-gpu-v2020/LICENSE`, not yet read) permits the intended research use and redistribution of derived files.

---

## 6. Alibaba v2018 Feasibility

**Role: optional reduced adapter and canonical-contract demonstration, if time permits.**
- It is **not** a full recurrence-based TraceAdvisor pipeline.
- It must **not** determine the main canonical recurrence design.

| Item | Verified detail |
|---|---|
| Release and period | 2018; 8 days. `batch_task.start_time` spans 0–765,880 s (8.86 days). |
| Scale and size | ~4,000 machines. 48 GB compressed / 280 GB extracted. `batch_task` is 125 MB compressed (14,295,731 rows); `batch_instance` is 20 GB compressed. |
| Hierarchy | Job (`j_<n>`, 4,201,014 jobs) → task (DAG encoded in `task_name`; 12 task types) → instance (with `seq_no` / `total_seq_no` retries). Online containers are grouped by `app_du`, which are long-running services with no occurrences. |
| Identifiers | `job_name`, `task_name`, `instance_name`, `machine_id`, `task_type`. **No user field.** Each `job_name` identifies a single job, not a repeated workload. |
| Requests | `plan_cpu` (100 = 1 core) and `plan_mem` (normalized, documented range [0, 100]) per task. 61,857 null. Observed `plan_mem` range 0.02–17.17, median 0.30. |
| Observed values | `cpu_avg`, `cpu_max` (100 = 1 core) and `mem_avg`, `mem_max` (normalized) per instance. **True CPU and memory peaks.** |
| Status | Task status: Terminated 14,059,143 (98.3%); Running 129,354; Failed 83,276; Waiting 23,958. Instance status also includes Interrupted. |
| Recurrence | **None official.** The PR #70 study found shared task-name/DAG signatures in 89.2% of sampled jobs (64.0% for a richer signature). That is evidence of **templates, not identity**: identical DAG shapes are common across unrelated jobs. |
| Next-occurrence target | **Not possible without inventing a recurrence rule** |
| Time quality | `end_time == 0` for 78,311 tasks; `end < start` for 54,580 tasks. The PR #70 adapter nulls these end times. |
| Instance quality (first 3.78 M rows only) | `mem_max` null 10.5%; `mem_max < mem_avg` in 26,930 rows; `cpu_max < cpu_avg` in 1,345 rows; retries (`total_seq_no > 1`) 0.06%. The full table is **not verified**. |
| Complications | DAG concurrency (tasks run in sequence; job-level values need DAG-aware aggregation); retries; normalized memory scale; −1 / 101 invalid markers (none found in `plan_mem`); 280 GB extracted size if processed in full |
| Requires confirmation | Whether `plan_mem` and `mem_max` share one normalization: their documented descriptions differ, and the medians are 0.30 vs 0.05 |

**What it can demonstrate**
- The canonical schema and adapter framework on a second, structurally different source.
- Instance-level request-versus-observed CPU and memory peaks for the **current** instance.
- Capability flags that disable recurrence and targets.

**Eligibility if included (design choice):** Terminated instances with a valid end time, `cpu_max ≥ cpu_avg` and `mem_max ≥ mem_avg`. Other rows are flagged with an exclusion reason.

---

## 7. Other Alibaba Datasets

All are rejected for the current TraceAdvisor objective. The decisive missing semantics are verified from each official README and table header.

| Dataset | Decisive missing semantics |
|---|---|
| GPU v2023 | **No observed usage.** Pod requests (`cpu_milli`, `memory_mib`, `num_gpu`, `gpu_milli`) and lifecycle times only; scheduler-simulator input (`openb_pod_list_default.csv`). |
| GPU v2025 | **No observed usage.** Requests and limits only (`cpu_request`, `memory_request` GiB, …). Long-running inference instances (`disaggregated_DLRM_trace.csv`). |
| Spot-GPU v2026 | **No usage and no memory field.** Only `cpu_request`, `gpu_request`, `worker_num`, `submit_time`, `duration` (`job_info_df.csv`). |
| GenAI v2026 | **No requests and no CPU.** Container memory utilization in percent, GPU duty cycle, GPU memory bytes, keyed by a hashed container IP; serving-latency metrics. |
| Microservices v2021 / v2022 | **No requests.** Utilization only, normalized (min–max in v2022). Long-running stateless services; 12 hours / 13 days (~2 TB). |
| Microarchitecture v2022 | Hardware counters (instructions, cycles, LLC misses). Requests only as ratios of node capacity. No CPU or memory peak outcomes. |
| v2017 | Superseded by v2018. Usage covers only 12 hours, which is too short for recurrence history. Container usage is reported as a percentage of the request. |
| GPU v2026 | **No memory request; no peaks; interval-only.** Identity: `workload_id` is "stable … when source owner/workload metadata is available; otherwise null", and is not documented as recurrence. One row per pod per hour, averages only. CPU is observable only as an hourly average (`avg_cpu_request_util × cpu_request_cores`). The `avg_memory_util` denominator is undocumented. Pod table is 352 GB compressed. At most a limited CPU-only interval study. |
| MaaS v2026 | **No CPU or memory requests; no peaks; long-running services.** Means only (`cpu_usage` cores, `mem_usage` GiB); `app_id` is a service identity. Its strongest signal, GPU memory allocated vs used (`gpu_mem_alloc`, `gpu_mem_util`), is outside the CPU/memory evaluator. Possibly interesting for future GPU-memory work. |

Newer traces were not preferred merely for being newer. None of the 2026 traces provides the request-plus-peak semantics TraceAdvisor's evaluation requires.

---

## 8. Azure VM Feasibility

> **Deferred from the current implementation phase.** Azure is not a current integration target. This section preserves the analysis for a possible later phase.

**Files read:**
- On PR #70: `src/adapters/azure_vm.py`, `base.py`, `validation.py`, `src/canonical/schema.py`, `config/dataset_capabilities.json`, `tests/test_azure_vm_adapter.py`, `scripts/build_external_canonical_samples.py`, `docs/data/dataset_semantics_study_FINAL.md` and the capability matrix CSV.
- On `main`: `src/evaluation/metrics.py`, `evaluator.py`, and the Resource Central notebook, documentation and metadata.

**[HEAD] downloads** (session scratchpad only):
- V2 `vmtable` (first 18,283 rows) and V1 `vmtable` (first 18,410 rows);
- the first rows of V2 CPU-readings file 1 of 195;
- the full V2 `deployments` (~33.2K rows) and `subscriptions` (6,687 rows) tables.

Head rows are not a random sample. For example, `Unknown` is 91% of the V2 head but 6% of the whole workload [DOC].

### 8.1 V1 versus V2 identity issue

The repository calls its Azure dataset **Azure Public Dataset V2 (2019)**:
- the PR #70 profile is `azure_public_vm_v2`;
- the semantics study is titled "Azure 2019 Public Dataset V2";
- the adapter docstring reads "Azure 2019 Public Dataset V2 adapter".

**Verified [REPO + HEAD]: the data actually used is the 2017 V1 trace.**

| Evidence | V1 (2017) | V2 (2019) | PR #70 sample |
|---|---|---|---|
| Distinct core-count values (head) | `1, 2, 4, 8` | `2, 4, 8, 24, >24` | `1, 2, 4, 8` |
| Distinct memory values (head) | `0.75, 1.75, 3.5, 4, 7, 14, 28, 56` | `2, 4, 8, 32, 64, >64` | `0.75, 1.75, 3.50, 4.00, 7.00, 14.00, 28.00, 56.00` |
| First 10,001 rows: subscriptions / deployments | **93 / 668** | 1,065 / 4,154 | **93 / 668** |
| First 10,001 rows: mean `max_cpu` / mean `avg_cpu` | **85.735 / 16.884** | 55.482 / 15.342 | **85.735045 / 16.883676** |
| CPU-reading file count | 125 | 195 | — |

- The Resource Central notebook on `main` also uses V1:
  - it loads `vm_cpu_readings-file-1-of-125.csv.gz`, and only V1 has 125 files;
  - its companion document says "We use the Azure 2017 VM workload trace";
  - its data directory is named `2021Dataset`.
- **V1 evidence must not be treated as V2 evidence.** V2 uses range buckets with open-ended top buckets (`>24`, `>64`).

### 8.2 V1 and V2 characteristics [DOC]

| Property | V2 (2019) | V1 (2017) |
|---|---|---|
| Source | `github.com/Azure/AzurePublicDataset`, `AzurePublicDatasetV2.md`, release assets under `dataset-v2/` | `AzurePublicDatasetV1.md`, `dataset-v1/` |
| Content | "A representative subset of the first-party Azure VM workload in one geographical region" | Same |
| Period | 30 consecutive days in 2019 (month undocumented) | 30 consecutive days in 2017 |
| Size | 235 GB raw, 156 GB compressed, 198 files | 117 GB raw, 78.5 GB compressed, 128 files |
| VMs / subscriptions | 2,695,548 / 6,687 | 2,013,767 / 5,958 |
| CPU readings | 1,942,780,023, every 5 minutes | 1,246,539,221, every 5 minutes |
| Tables | `vmtable` (437 MB compressed), `vm_cpu_readings` (195 files, ~856 MB compressed each), `deployments`, `subscriptions`, bucket-definition files listed in `schema.csv` | `vmtable`, `vm_cpu_readings` (125 files), `deployments`, `subscriptions` |
| Memory telemetry | **None**; memory-size bucket only | **None**; memory size only |
| Time encoding | Seconds from 0; readings every 300 s | Same |
| Paper | Resource Central (SOSP '17) | Same |
| License | CC-BY per the repository `LICENSE`; V2 page does not restate it [NEEDS DATA] | Same |

- **V2 `vmtable` schema** [DOC `schema.csv`, confirmed by HEAD]: `vm id`, `subscription id`, `deployment id`, `timestamp vm created`, `timestamp vm deleted`, `max cpu`, `avg cpu`, `p95 max cpu`, `vm category`, `vm virtual core count bucket` (string), `vm memory (gb) bucket` (string).
- **CPU readings:** `timestamp`, `vm id`, `min cpu`, `max cpu`, `avg cpu`.

**Workload [DOC]**
- General-purpose IaaS VMs running Microsoft first-party services.
- VM categories: Delay-insensitive 51%, Interactive 43%, Unknown 6%. V1 spells the last one `Unkown`.
- 63.6% of VMs live at most 1 hour; about 8% live more than 100 hours.
- 47% of deployments have one VM, and 79% have at most five.
- Age: V2 is contemporaneous with the Google 2019 subset and older than Alibaba GPU v2020; V1 is the oldest of all. **Azure adds no recency advantage.**

**Other Azure traces are out of scope:**
- Functions 2019/2021 (serverless);
- Packing 2020 (requests and lifetimes in fractional machine units, **no usage**);
- LLM 2023/2024 and LMM 2025 (tokens);
- VM Noise 2024 (benchmarks);
- Copilot 2026 (agent sessions).

### 8.3 Azure against TraceAdvisor requirements

| Requirement | Available? | Azure field | Consequence |
|---|---|---|---|
| Workload identity | Partial | `subscription id` (tenant), `deployment id` (VMs deployed together) | Neither is documented as a workload identity |
| Recurrence identity | **No** | None. Proxies would be invented. | No legitimate next-occurrence target |
| Discrete workload occurrences | **No** | One row per VM | A VM is a resource container with a lifetime, not a job run |
| Start and end | VM lifetime | `timestamp vm created` / `deleted` | 1,014 of 18,283 V2 head rows have create = delete. Censoring at the trace edges is [NEEDS DATA]. |
| CPU request | **Allocated, bucketed** | `2, 4, 8, 24, >24` (V2) | The tenant's VM size, not a request. Top bucket is open-ended. Exact-vs-range meaning is [NEEDS DATA]. |
| Memory request | **Allocated, bucketed** | `2, 4, 8, 32, 64, >64` (V2) | The jump from 8 to 32 suggests range bounds |
| Observed CPU | **Yes; true peaks** | Lifetime `max`, `avg`, `p95 max`; 5-minute `min`, `max`, `avg` | Strongest part of the dataset. Utilization basis (percent of the VM's cores) is implied, not stated. |
| Observed memory | **No** | — | No memory evaluation; memory stays unknown, never zero |
| Status | **No** | — | Failed or evicted VMs cannot be separated |
| History | Within a VM: yes. Across VMs: unproven. | 5-minute readings; VMs per subscription | Temporal or population history, never recurrence history |
| Time span | 30 days | — | Long-lived VMs cross split boundaries |
| Units | CPU in percent; allocation in buckets | — | Percent and cores cannot be compared without an inexact bucket value |

**VM versus workload versus execution**

| Concept | Google reference | Azure V2 |
|---|---|---|
| Long-lived VM | No equivalent | Lives minutes to 30 days and may run many logical tasks |
| VM instance | — | One `vm id`: a **container**, not a unit of work |
| Workload execution | An episode of `collection_id‖instance_index` | **Not observable** |
| Repeated occurrence | Same `user‖collection_logical_name` later | **Not observable** |

`vm id`, `deployment id` and `subscription id` are **not recurrence keys**:
- a deployment is a set of VMs created together, often just one;
- a subscription is a billing tenant hosting many unrelated services.

PR #70's study reached the same conclusion: shared deployment shapes "do not prove repeated deployments are the same recurring workload".

### 8.4 Why Azure cannot support a legitimate next-occurrence target

| Invented construction | Why it is invalid |
|---|---|
| `deployment_id` as recurrence | Deployment VMs are concurrent, not sequential; most deployments have one VM |
| `subscription_id` as recurrence | A tenant hosts unrelated services |
| Subscription + size + category signature | Same shape does not mean same workload. PR #70's 39.5% shared-signature figure was measured on V1 data. |
| Daily windows of one VM as "occurrences" | A time slice of one run is not a repetition |
| The VM's own lifetime `max cpu` as its target | The VM's own outcome; leakage, not a forecast |

**Valid CPU-only alternatives** (never to be called next-occurrence):

| Mode | History | Target | Measures |
|---|---|---|---|
| Within-VM temporal rightsizing (interval replay) | The VM's own 5-minute readings up to t | Peak `max cpu` of the same VM over the next horizon | Closest honest analogue of TraceAdvisor's question |
| Cold-start population history | Completed VMs in the same subscription | New VM's lifetime `p95 max cpu` or `max cpu` | Resource Central-style tenant prior, not recurrence |
| Allocation versus observed | None | None | Descriptive over-provisioning only |

**Existing repository result (verified).** The Resource Central notebook on `main` (cell 7) loads `nrows=100000` from one V1 CPU file.
- The metadata shows `cpu_rows_loaded = 100000`, `n_vms = 100000`, and the sample output shows `n_samples = 1`. So each VM has **one** 5-minute reading.
- Its "P95 vs mean" `bucket_accuracy = 0.8711` compares two statistics of the same reading.
- It is not history-based prediction and must not be cited as TraceAdvisor evidence.

### 8.5 Shared evaluator and adapter limitations

**Shared evaluator (verified)**
- CPU metrics work unchanged.
- With memory all-NaN, `any_resource_violation` is 1 when CPU violates and NaN otherwise. So `any_resource_violation_pct` is **100% by construction** (`metrics.py:68–81`, `evaluator.py:162–218`).
- Azure reports would need CPU-only metrics.

**PR #70 `AzureVMAdapter` (verified)**
- **Views:** `adapt_vm_table` (`record_level="instance"`) and `adapt_cpu_readings` (`record_level="interval"`, 300 s).
- **Capability profile:** `supports_request=False`, `supports_recurrence=False`, `supports_observed_memory=False`, `supports_allocated_cpu/memory=True`.

| Adapter issue | Status |
|---|---|
| Built and tested on V1 data, labeled V2 | Confirmed |
| `pd.to_numeric(errors="coerce")` turns V2 `>24` / `>64` into NaN, silently marking the largest VMs `partial` | Confirmed against V2 encoding; effect size [NEEDS DATA] |
| Bucket labels written as exact values (`vcpu`, `gb`) | Suspected overstatement; depends on bucket definitions |
| `observed_cpu` in percent vs `allocated_cpu` in vCPU; no conversion rule defined | Confirmed gap |
| `supports_memory=True` with `supports_observed_memory=False` reads ambiguously | Confirmed |
| `adapt_vm_table` bypasses `BaseDatasetAdapter.adapt()`; multi-table preparation is outside the base contract | Confirmed |
| `test_azure_empty_vm_table_rejected` defined twice | Confirmed, harmless |
| `read_headerless_csv` loads whole files; not viable for 195 × ~856 MB files | Confirmed |

**Proposed Azure V2 canonical mapping (not implemented; nothing fabricated)**

| Canonical field | Azure source | Rule |
|---|---|---|
| `dataset_id` | — | Name the version, e.g. `azure_public_vm_v2_2019` vs `azure_public_vm_v1_2017` |
| `record_level` | — | `instance` (VM lifetime) or `interval` (5-minute) |
| `workload_id` | `deployment id` or `subscription id` (choose and document) | — |
| `execution_id` / `instance_id` | `vm id` | — |
| `recurrence_key`, `occurrence_key` | **None** | Absent or null |
| `start_time_us`, `end_time_us`, `event_time_us` | Created, deleted and readings timestamps × 10⁶ | Keep create = delete as a flag; flag censoring |
| `requested_cpu` / `requested_memory` | **None** | Null. Allocation is never relabeled as a request. |
| `allocated_cpu` / `allocated_memory` | Core / memory buckets | Parse with the official bucket-definition files. Keep low/high bounds if buckets are ranges. Never coerce `>24` / `>64` to NaN, and never guess a value. |
| `observed_cpu`, `peak_cpu` | `avg cpu`, `max cpu` (interval or lifetime) | Percent; NaN stays NaN |
| `observed_memory` / `peak_memory` | **None** | Null, never 0 |
| Extensions | `p95 max cpu`, `min cpu`, `vm category` | Pass-through; normalize V1 `Unkown` and keep the raw value |

**Interface sufficiency**
- For parsing, the current interface is mostly sufficient.
- As a TraceAdvisor dataset, Azure would also need:
  - a new interval or population-history modeling mode with its own target builder and leakage rules;
  - richer capability flags (modeling mode, bucketed allocation, CPU unit basis, memory evaluation separate from memory capacity, trace version);
  - multi-table chunked ingestion;
  - CPU-only reporting.

### 8.6 Azure relevance and the conditions for a later phase

**What Azure would add:**
- a different workload class (IaaS VMs);
- dense 5-minute CPU telemetry;
- direct grounding for Resource Central related work;
- the strongest heterogeneous-schema test of the adapter design.

**What it does not add:**
- recency;
- memory evidence;
- request-versus-observed results;
- a valid next-occurrence result.

**Claims a later phase could make**
- schema portability to a request-less, memory-less, interval-telemetry source;
- history-based CPU sizing on future windows of the same VM;
- optionally, a subscription-prior cold-start result, named as such;
- descriptive CPU over-allocation evidence.

**Claims it could not make**
- next-occurrence prediction or recurrence;
- any memory result;
- request-versus-observed results;
- any-resource violation rates;
- newer evidence than Google 2019;
- numerical comparability with Google or Alibaba;
- any statement about failed or evicted VMs.

**Required checks before any future Azure adapter work** (all on full data, not head rows)

| Check group | Checks |
|---|---|
| Version and encoding | Decide V1 or V2. For V2, confirm bucket values over all 2,695,548 rows and rebuild PR #70's samples. Confirm row counts (2,695,548 VMs; 6,687 subscriptions; 1,942,780,023 readings in 195 files). Obtain `vm_virtual_core_bucket_definition.csv` and `vm_memory_bucket_definition.csv` (listed in `schema.csv` but not linked; maintainers: `azurepublicdataset@service.microsoft.com`). Check join integrity: reading IDs in `vmtable`, VMs with readings, unique `vm id`, one subscription per deployment. |
| Timestamps and lifecycle | Timestamps within [0, 2,592,000) and multiples of 300. Readings per VM and gaps. Readings within the VM lifetime. Censoring at trace start and end. Zero-length lifetimes. |
| Values and units | 0 ≤ `min` ≤ `avg` ≤ `max` ≤ 100. Lifetime summaries match readings, and the meaning of `p95 max cpu`. Utilization basis. Missingness per column. Confirm no observed memory anywhere. |
| Workload repetition and identity | VMs per subscription and deployment over time. Sequential vs concurrent creation. Behavioral stability across sequential VMs. Confirm that no field identifies one logical workload. |
| Modeling unit and splits | Temporal history depth per VM. VMs crossing split boundaries. `max cpu` by core bucket (labeled allocation). Category balance vs the official 43 / 51 / 6. |

---

## 9. Cross-Dataset Capability Matrix

| Aspect | Google subset 2019 | Alibaba GPU v2020 | Alibaba 2018 | Azure V2 |
|---|---|---|---|---|
| Recurrence | Constructed by TraceAdvisor: `user‖collection_logical_name` | **Official `group`** | None | None |
| Occurrence definition | Executions of one recurrence starting at the same time | One job submission; task role is the evaluation unit | None (instance rows) | None (VM lifetimes and 5-minute intervals) |
| Resource scope | Full workload (summed across executions) | Per instance of a task role | Per instance | Per VM or per interval |
| CPU semantics | Peak (aligned-window sum, then maximum), normalized compute units | **Lifetime average only**, percent of one vCPU | Instance average and peak, 100 = 1 core | Lifetime and 5-minute peak and average, percent |
| Memory semantics | Peak (aligned-window sum, then maximum), normalized | **Per-instance lifetime peak**, GB | Instance average and peak, normalized | **None** |
| Requests | CPU and memory | CPU and memory per instance (plus GPU) | CPU and memory per task | None (bucketed allocation only) |
| Status | Yes (`event`, `failed`) | Yes (job, task, instance) | Yes (task, instance) | No |
| Next-occurrence support | CPU and memory peaks | Memory peak; CPU average | No | No |
| Evaluation mode | Full next-occurrence | Next-occurrence memory peak plus CPU average; no any-resource metric | Instance request versus observed | CPU-only interval or population (if ever) |
| Missingness | Low (774 null requests; 60 null occurrence memory peaks) | Telemetry starts around day 19; 40.2% of instances have sensors; 0.26% missing CPU in eligible rows | `mem_max` null 10.5% in head rows | No memory at all; bucket semantics unknown |
| Time span | 31 days (May 2019) | 68.9 days (about 50 usable) | 8.86 days | 30 days |
| **Final project role** | **Reference pipeline** | **Required full integration** | **Optional reduced demonstration** | **Deferred** |

Results across these datasets are **not directly comparable**. Each answers a related question at a different scope, unit or semantics.

---

## 10. Adapter and Shared-Pipeline Implications

### 10.1 What carries over from the Google pipeline

| Reusable conceptually | Not reusable unchanged (Google-specific) |
|---|---|
| Completed-history rule (`end ≤ t`); next-occurrence shift within a recurrence key; Request/Mean/P90/P95/P99 baselines; validation-only selection; chronological 70/15/15 splits | Episode reconstruction (5-minute gap rule); aligned-window peak sums across executions; start-time-equality occurrences; Google constants and assertions; the any-resource-first selection objective (invalid for Alibaba GPU v2020) |

Alibaba GPU v2020 differs in kind from Google:
- Google's recurrence had to be *constructed*, and its occurrences *inferred*.
- In Alibaba GPU v2020 the recurrence tag is *provided by the source*, and an occurrence is a *submitted job* with its own ID and lifecycle.

This lowers semantic risk, but the Google occurrence code must not be reused as-is.

### 10.2 Shared modules

- **Canonical validation:** `validate_canonical_frame`, `validate_adapter_output`, `validate_evaluator_view`; capability-gated rejection of unsupported fields.
- **Capability metadata:** PR #70's 10 flags, extended (design choice) with:
  - `recurrence_key_origin`, `resource_scope`, `aggregation_method`;
  - `has_cpu_peak`, `has_cpu_average`, `has_memory_peak`, `has_memory_average`, `has_gpu_signal`, `has_status`;
  - `cpu_observed_semantics`, `memory_observed_semantics`;
  - units, `time_semantics`, `telemetry_window`;
  - `supported_record_levels`, `evaluation_mode`, `any_resource_metric_valid`.
- **Chronological splitting** (`split_utils.chronological_split`), with the split-isolated target rule for Alibaba GPU v2020.
- **Point-in-time history** over canonical occurrences.
- **Target construction**, only where `supports_targets` is true.
- **Baselines** and validation-only selection, with a dataset-specific objective (memory first for Alibaba GPU v2020).
- **Evaluator and reporting.** The evaluator needs no code change. It needs a reporting rule that suppresses any-resource metrics when `any_resource_metric_valid` is false, and labels average-based CPU metrics as such.
- **ML and Hybrid policies,** trained per dataset only. There is no merged training dataframe.

### 10.3 Dataset-specific adapter logic

| Responsibility | Alibaba GPU v2020 | Alibaba 2018 (optional) |
|---|---|---|
| Raw file loading | Six headerless CSVs (instance table 2.0 GB, sensor table 1.1 GB uncompressed); explicit schema; columnar or chunked reading; checksum provenance | `batch_task` (0.8 GB) plus `batch_instance` (20 GB compressed); chunked or streamed |
| Multi-table preparation | Job ← group; job ← task (plan) ← instance (status, worker) ← sensor (usage) ← machine spec (capacity) | Instance ← task plan join (as in the PR #70 adapter) |
| Field mapping | `plan_*` → `requested_*`; `max_mem` → `peak_memory`; `cpu_usage` → `observed_cpu_avg` (never `peak_cpu`) | `plan_*` → `requested_*`; `cpu_max` / `mem_max` → `peak_*` |
| Timestamp normalization | Seconds × 10⁶; submission as occurrence time; UTC+8 note | Seconds × 10⁶; null `end == 0` and `end < start` |
| Unit tagging | `pct_vcpu`, `gb` (identical for request and actual) | `pct_core`, `normalized` |
| Recurrence interpretation | Preserve `group` (`recurrence_key_origin = official`); null for the 469 jobs without one | None |
| Occurrence construction | Job within group; role rows `group‖job_name‖task_name` | None |
| Resource aggregation | Maximum across eligible workers per role; job totals descriptive only | None (instance level) |
| Status rules | Eligibility and exclusion reasons as in section 5.7 | Terminated only; value-consistency checks |
| Missingness | Null CPU stays null; no zero-filling; keep excluded rows for audit | Null values stay null |

**Base-interface implications.** The current `BaseDatasetAdapter.adapt(source)` is single-table and in-memory. Alibaba GPU v2020 needs:
- an explicit multi-table preparation step;
- chunked or columnar loading;
- exclusion-reason output.

These are framework changes, to be recorded in the existing `adapter_framework.md`.

---

## 11. Final Recommendation and Implementation Order

1. **Correct and freeze the Google reference behavior separately**, following the Google Subset Pipeline Analysis report. This document does not change the Google pipeline.
2. **Integrate Alibaba GPU v2020 as the full second pipeline.**
3. **Use the canonical schema and adapter framework for Alibaba GPU v2020** (future implementation work). Update the existing `canonical_workload_schema.md` and `adapter_framework.md` in place, coordinating with the PR #70 author. Do not create duplicate schema or framework documents.
4. **Evaluate memory as the primary resource** (per-instance lifetime peak, GB).
5. **Evaluate CPU only as lifetime-average usage**, and never claim CPU peak safety.
6. **Do not report any-resource metrics for Alibaba GPU v2020.**
7. **Add Alibaba 2018 only as an optional reduced adapter demonstration.** Do not use it to define the main recurrence design.
8. **Defer Azure.** Resolve the V1/V2 identity issue before any future Azure work.

Throughout:
- keep datasets separate, with no merged training data;
- keep missing values unknown, never zero;
- report every Alibaba GPU v2020 result with the selection-bias, multi-instance, telemetry-window and CPU-average limitations.

---

## 12. Sources and Evidence

### Alibaba (official)

- [Alibaba clusterdata repository (README and directory listing)](https://github.com/alibaba/clusterdata/tree/master)
- [cluster-trace-v2018 documentation](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-v2018/trace_2018.md) and [schema](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-v2018/schema.txt)
- [cluster-trace-gpu-v2020 README](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-gpu-v2020/README.md) and the data download page (`cluster-trace-gpu-v2020/data/README.md`)
- [cluster-trace-gpu-v2023 README](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-gpu-v2023/README.md)
- [cluster-trace-gpu-v2025 README](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-gpu-v2025/README.md)
- [cluster-trace-gpu-v2026 README](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-gpu-v2026/README.md) and [schema](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-gpu-v2026/docs/schema.md)
- [cluster-trace-v2026-maas README](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-v2026-maas/README.md) and [schema](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-v2026-maas/docs/schema.md)
- [cluster-trace-v2026-spot-gpu README](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-v2026-spot-gpu/README.md)
- [cluster-trace-v2026-GenAI README](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-v2026-GenAI/README.md)
- [cluster-trace-v2017 documentation](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-v2017/trace_201708.md)
- Microservices [v2021](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-microservices-v2021/README.md) / [v2022](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-microservices-v2022/README.md); [microarchitecture v2022](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-microarchitecture-v2022/README.md)
- Upstream issues:
  - [#114 (recurrence via `group`)](https://github.com/alibaba/clusterdata/issues/114)
  - [#125 (`cpu_usage` meaning)](https://github.com/alibaba/clusterdata/issues/125)
  - [#151 (CPU overuse; identifiers)](https://github.com/alibaba/clusterdata/issues/151)
  - [#182 (per-instance sensor metrics)](https://github.com/alibaba/clusterdata/issues/182)
- Downloaded official data used for verification (session scratchpad, not the repository):
  - all GPU v2020 tables except `pai_machine_metric`;
  - v2018 `batch_task` (full) and the first 3,783,610 rows of `batch_instance`.

### Azure (official)

- Azure Public Dataset repository: https://github.com/Azure/AzurePublicDataset (`README.md`, `AzurePublicDatasetV1.md`, `AzurePublicDatasetV2.md`, `AzurePublicDatasetLinksV2.txt`, `AzureTracesForPacking2020.md`, `AzureVMNoiseDataset2024.md`, `analysis/Azure 2019 Public Dataset V2 - Trace Analysis.ipynb`)
- V2 release assets: `schema.csv`, `azure2019_data_*.txt`, and the head bytes of `trace_data_vmtable_vmtable.csv.gz` and `trace_data_vm_cpu_readings_vm_cpu_readings-file-1-of-195.csv.gz`
- V1 release asset: the head bytes of `dataset-v1/trace_data_vmtable_vmtable.csv.gz`
- Cortez et al., "Resource Central: Understanding and Predicting Workloads for Improved Resource Management in Large Cloud Platforms", SOSP 2017

### TraceAdvisor repository

- `main@91470a3`:
  - `pipelines/google_subset/`
  - `src/evaluation/metrics.py`, `src/evaluation/evaluator.py`
  - `src/features/split_utils.py`
  - `notebooks/resource-central/resource_central.ipynb`
  - `reports/eval/resource-central/tables/resource_central_baseline_metadata.csv`
- `origin/feature/external-dataset-canonical-pipeline@69f3a42` (PR #70):
  - `src/canonical/schema.py`
  - `src/adapters/{base,validation,reference,alibaba,azure_vm}.py`
  - `config/dataset_capabilities.json`
  - `tests/test_azure_vm_adapter.py`
  - `scripts/build_external_canonical_samples.py`
  - `docs/data/{canonical_workload_schema,adapter_framework,dataset_semantics_study_FINAL}.md`
  - `docs/data/traceadvisor_external_dataset_capability_matrix.csv`
- Related reports:
  - `docs/data/dataset_inspection_and_integration_design.md`
  - `docs/data/google_subset_pipeline_analysis.md`
