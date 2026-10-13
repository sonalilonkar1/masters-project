# TraceAdvisor External Dataset Semantics Study

## New Development Issue 1 — Alibaba and Azure VM Dataset Semantics

**Status:** COMPLETE FOR ISSUE 1  
**Purpose:** Document source semantics and capability boundaries before the canonical TraceAdvisor schema is frozen.

This issue is a semantics/feasibility study. It does **not** require the external-dataset recurrence rule, adapter implementation, model training, or final policy logic to be solved here. Those decisions belong to later issues.

---

## 1. Sources and samples inspected

### Alibaba Cluster Trace 2018
Samples:
- `batch_task_sample.csv` — 10,001 rows from `batch_task.csv`
- `batch_instance_sample.csv` — 10,001 rows from `batch_instance.csv`

Official documentation:
- Alibaba Cluster Trace 2018 documentation: https://github.com/alibaba/clusterdata/tree/master/cluster-trace-v2018
- The trace covers about 4,000 machines over 8 days and includes batch task and batch instance tables.
- Timestamps are relative seconds from the beginning of the trace period.
- Batch jobs follow a job → task → instance model, and task names encode DAG/dependency structure.
- `instance_num` is the number of instances belonging to a task.
- Memory fields are normalized/obfuscated source-native values.
- Actual instance CPU/memory values are provided in `batch_instance.csv`.

### Azure 2019 Public Dataset V2
Samples:
- `azure_vmtable_sample.csv` — 10,001 VM-table rows
- `azure_cpu_readings_sample.csv` — 10,001 CPU-reading rows

Official documentation:
- Azure Public Dataset V2: https://github.com/Azure/AzurePublicDataset/blob/master/AzurePublicDatasetV2.md
- The trace spans 30 consecutive days.
- It contains VM information plus 5-minute CPU-utilization readings.
- The VM table exposes encrypted subscription/deployment/VM IDs, VM lifecycle timestamps, CPU summaries, VM category, vCPU bucket, and memory-capacity bucket.

Important terminology note: this is the public Azure VM trace used for the Azure VM / Resource Central validation direction. It is **not** a direct export of the internal Resource Central service.

---

# 2. Alibaba 2018 semantics

## 2.1 Batch task table

Observed sample:

- Rows: **10,001**
- Unique jobs: **2,948**
- Unique `(job_name, task_name)` pairs: **10,001**
- Duplicate full rows: **0**
- Median tasks per sampled job: **2**
- Maximum sampled tasks in one job: **65**

Task status counts:

status
Terminated    9851
Running         64
Failed          62
Waiting         24

Missing values:

task_name        0
instance_num    24
job_name         0
task_type        0
status           0
start_time       0
end_time         0
plan_cpu        51
plan_mem        51

### Identity interpretation

- `job_name` identifies a submitted batch job.
- `task_name` identifies a task **within a job** and also carries DAG/dependency information.
- `instance_num` states how many parallel task instances are expected.
- Neither `job_name` nor `task_name` is documented as a recurring-workload identifier across separate job submissions.

Therefore:

**Alibaba has explicit job/task/instance identity, but no explicit TraceAdvisor-style recurrence key.**

## 2.2 Planned/requested resources

Sample ranges:

- `plan_cpu`: 5 to 700 source units
- `plan_mem`: 0.03 to 2.35 normalized source units
- `instance_num`: 1 to 42188

Missingness:
- `instance_num`: 24 rows
- `plan_cpu`: 51 rows
- `plan_mem`: 51 rows

The task-level plan applies per task instance, not automatically to the complete job.

A task-level planned contribution may require:

`instance_num × plan_cpu`

and similarly for memory.

However, a complete job is a DAG. Summing all task requests without considering which task stages overlap can overstate simultaneous demand. The adapter/integration stage must preserve this distinction.

## 2.3 Batch instance table

Observed sample:

- Rows: **10,001**
- Unique instance names: **10,001**
- Unique jobs: **67**
- Unique `(job_name, task_name)` pairs: **257**
- Duplicate instance names in sample: **0**

Statuses:

status
Terminated    9513
Running        488

Observed resource missingness:

cpu_avg     488
cpu_max     488
mem_avg    1011
mem_max    1016

Key missingness behavior:

- All **488 Running** rows in the sample have missing `cpu_avg` and `cpu_max`.
- All 488 Running rows also have missing memory outcomes.
- In addition, **528 Terminated rows** have missing `mem_max`.
- Missing memory is therefore not equivalent to “zero usage” and must remain unknown.

CPU summary:

           cpu_avg      cpu_max
count  9513.000000  9513.000000
mean     52.620414   120.098812
std      36.277955   118.776978
min       0.000000     5.000000
50%      48.000000    92.000000
95%     100.000000   244.000000
99%     155.000000   730.000000
max     232.000000   846.000000

Memory summary:

           mem_avg      mem_max
count  8990.000000  8985.000000
mean      0.075189     0.100913
std       0.109542     0.156677
min       0.000000     0.000000
50%       0.040000     0.050000
95%       0.280000     0.520000
99%       0.660000     0.860000
max       0.920000     1.010000

The sample also contains a few rows where reported averages are slightly larger than reported maxima:
- CPU `avg > max`: **3**
- Memory `avg > max`: **75**

Those should be treated as source-data quality anomalies and checked/filtered by explicit validation logic rather than silently corrected.

## 2.4 Retry semantics

The instance schema includes:
- `seq_no`
- `total_seq_no`

The first 10,001-row sample happens to contain only:

- `seq_no = 1`
- `total_seq_no = 1`

Therefore this sample does not empirically exercise retry behavior, even though the schema supports it.

Adapter/integration code must preserve these fields so later sampling/full processing can distinguish retries from separate logical instances.

## 2.5 Task-to-instance join evidence

The independently sampled task and instance files overlap on only two `(job_name, task_name)` pairs, which is expected because the samples were taken independently.

One matched task, `j_5287 / M1`, declares **665 instances** in the task sample, and **654** of those rows happen to occur in the independently cut instance sample.

This confirms the intended job/task/instance hierarchy while also showing why row-count equality cannot be inferred from two independent head samples.

## 2.6 Alibaba recurrence feasibility

The trace does not provide an explicit recurrence ID.

Nevertheless, structural repetition is common in the task sample:

- Jobs in a repeated task-name/DAG signature: **2,630 / 2,948 (89.2%)**
- Jobs in a repeated richer signature using task structure + type + sampled resource-plan pattern: **1,888 / 2,948 (64.0%)**

This is evidence of repeated **workload templates/families**, not proof of recurring identity.

### Issue-1 decision

- `job_name` must **not** automatically become `recurrence_key`.
- The canonical interface should allow a source workload ID without requiring recurrence.
- A derived Alibaba workload-family / recurrence rule can be investigated during adapter/integration work.
- Until validated, next-occurrence prediction must be marked unsupported/experimental rather than silently inferred.

## 2.7 Alibaba history and target feasibility

**Point-in-time history:** feasible.

Historical outcomes can be built from prior completed jobs/tasks/instances once a modeling unit is selected. Running/incomplete records must not contribute completed outcomes.

**Observed CPU:** supported by `cpu_avg` / `cpu_max`.

**Observed memory:** supported by `mem_avg` / `mem_max`, with material missingness that requires resource-specific validity counts.

**Next-occurrence CPU/memory target:** conditionally feasible only after a defensible recurrence/workload-family rule is selected and validated.

**Full CPU + memory TraceAdvisor path:** potentially supported.

---

# 3. Azure VM V2 semantics

## 3.1 VM table

Observed sample:

- Rows / unique VMs: **10,001 / 10,001**
- Unique subscriptions: **93**
- Unique deployments: **668**
- Duplicate VM IDs: **0**
- Missing values: **0**

The observed identity hierarchy is:

`subscription_id -> deployment_id -> vm_id`

Deployment-size sample summary:

count    668.000000
mean      14.971557
std       57.621633
min        1.000000
25%        2.000000
50%        4.000000
75%        9.000000
max      997.000000

Each sampled deployment belongs to one subscription.

### Interpretation

- `vm_id` is the natural VM identity.
- `deployment_id` is a strong grouping field for VMs deployed together.
- `subscription_id` is a higher-level tenant/account grouping.
- None is documented as a recurring logical job identifier.

## 3.2 Allocation/capacity fields

The VM table exposes:
- `vm_core_count_bucket`
- `vm_memory_bucket`

Observed sampled core-count buckets:

vm_core_count_bucket
1    5984
2    2964
4     741
8     312

Observed sampled memory buckets:

vm_memory_bucket
0.75      115
1.75     5869
3.50     2955
4.00        2
7.00      722
14.00     211
28.00      19
56.00     108

These are allocation/capacity descriptors.

They must **not** be interpreted as observed resource consumption.

## 3.3 CPU outcomes

VM-table CPU summaries are complete in this 10,001-row sample.

            max_cpu       avg_cpu   p95_max_cpu
count  10001.000000  10001.000000  10001.000000
mean      85.735045     16.883676     55.258890
std       25.522352     17.710087     36.326916
min        0.070878      0.061226      0.070878
50%       98.643656      7.455383     46.894224
95%      100.000000     51.373354     99.359790
99%      100.000000     63.758400     99.752480
max      100.000000     98.965915    100.000000

These fields summarize behavior over the VM lifetime.

### Leakage implication

`max_cpu`, `avg_cpu`, and `p95_max_cpu` of the **current VM** are post-observation information.

They can serve as:
- labels/outcomes, or
- historical information from earlier completed VMs,

but they must not be used as pre-execution features for that same VM.

## 3.4 Five-minute CPU readings

Observed CPU sample:

- Rows: **10,001**
- Unique VMs: **10,001**
- Missing values: **0**
- Unique timestamps in this specific `head` sample: **1**
- Sample timestamp value: **0**

CPU-reading summary:

            min_cpu       max_cpu       avg_cpu
count  10001.000000  10001.000000  10001.000000
mean       6.208330     18.877939      9.738580
std       11.373378     21.962038     14.550347
min        0.000000      0.029242      0.006424
50%        3.302464      9.427300      5.197999
95%       23.960385     64.927737     40.514948
99%       65.435253     97.084161     83.643263
max       99.177634     99.296543     99.243405

Validation checks in the sample:
- `min_cpu > avg_cpu`: **0**
- `avg_cpu > max_cpu`: **0**
- values below 0: **0**
- values above 100: **0**

### Sampling limitation

All rows in this 10,001-row `head` sample are at timestamp 0. Therefore this sample verifies the CPU-reading schema and value ranges, but **does not empirically show the five-minute cadence for one VM over time**.

Likewise, this CPU head sample shares zero VM IDs with the independently sampled first 10,001 VM-table rows. That does **not** indicate incompatible IDs; it only means two independent head samples are not a join test.

The official Azure V2 documentation defines:
- 5-minute VM CPU utilization readings,
- encrypted VM IDs shared across the trace,
- timestamps in seconds at five-minute cadence.

A later integration test should deliberately sample the same VM IDs across the two files.

## 3.5 Azure memory capability

The selected Azure VM trace provides VM memory **capacity/bucket**, but no observed memory-utilization time series equivalent to the CPU readings.

Therefore:

- allocation/capacity memory: supported
- observed memory consumption: unsupported
- observed memory peak target: unsupported
- Google-style memory recommendation evaluation: unsupported for this trace

Unavailable memory outcomes must remain null/unsupported, not zero.

## 3.6 Azure recurrence feasibility

No explicit recurring application/job identity is provided.

Potential signals include:
- subscription,
- deployment,
- deployment shape,
- chronology.

Sample evidence:
- subscriptions with at least 2 deployments: **58**
- subscriptions with at least 5 deployments: **33**
- deployments belonging to a repeated same-subscription deployment-shape signature: **264 / 668 (39.5%)**

This is useful workload-pattern evidence, but does not prove repeated deployments are the same recurring workload.

### Issue-1 decision

For Azure VM:
- CPU history/replay validation is clearly feasible.
- A deployment/VM time-series replay experiment is safer than inventing a recurrence key.
- Next-occurrence semantics should remain unsupported unless a later adapter study validates a recurrence rule.
- Observed memory must remain unsupported.

---

# 4. Capability matrix

| Capability                            | Google             | Alibaba 2018                                | Azure VM V2                                              |
|:--------------------------------------|:-------------------|:--------------------------------------------|:---------------------------------------------------------|
| Workload/job identity                 | Yes                | Yes: job_name                               | Partial: deployment_id                                   |
| Execution/instance identity           | Yes                | Yes: instance_name                          | Yes: vm_id                                               |
| Start/end timestamps                  | Yes                | Yes                                         | Yes                                                      |
| Parallel workload structure           | Yes                | Yes: task DAG + instances                   | Yes: deployment -> VMs                                   |
| Requested/planned CPU                 | Yes                | Yes: plan_cpu per task instance             | Partial: allocated vCPU bucket                           |
| Requested/planned memory              | Yes                | Yes: plan_mem per task instance             | Partial: memory-capacity bucket                          |
| Observed CPU                          | Yes                | Yes: cpu_avg/cpu_max                        | Yes: 5-minute CPU readings                               |
| Observed memory                       | Yes                | Yes: mem_avg/mem_max                        | No in selected VM trace                                  |
| Explicit recurrence key               | Derived by project | No                                          | No                                                       |
| Point-in-time history                 | Yes                | Yes with completed instances/jobs           | Yes for CPU replay/history                               |
| Next-occurrence CPU target            | Yes                | Possible only after derived recurrence rule | Not canonical without recurrence; replay target feasible |
| Next-occurrence memory target         | Yes                | Possible only after derived recurrence rule | No observed-memory target                                |
| Full CPU+memory TraceAdvisor pipeline | Yes                | Potentially yes                             | No                                                       |
| CPU-only TraceAdvisor validation      | Yes                | Yes                                         | Yes                                                      |

---

# 5. Canonical-schema implications

The Issue-1 study directly motivates a capability-aware common schema.

## 5.1 Separate identity concepts

The canonical interface should distinguish at least:

- `dataset_id`
- `source_workload_id`
- `source_execution_id`
- `source_instance_id`
- `occurrence_id` when a dataset can define one
- `recurrence_key` only when available or defensibly derived

A workload ID and a recurrence ID are **not the same concept**.

## 5.2 Resource fields must be independently optional

Candidate capability flags:

- `supports_cpu`
- `supports_memory_capacity`
- `supports_observed_cpu`
- `supports_observed_memory`
- `supports_request_cpu`
- `supports_request_memory`
- `supports_recurrence`
- `supports_next_occurrence_target`
- `supports_ml`

Possible fields should distinguish semantics such as:

- requested CPU
- allocated CPU
- observed CPU
- requested memory
- allocated memory
- observed memory

Do not collapse allocation and observed consumption into one field.

## 5.3 Missing and unsupported values

Rules:

1. Source-missing observations remain null.
2. Unsupported capabilities remain null/unsupported.
3. Missing/unsupported fields must never be silently converted to zero.
4. CPU and memory validity must be tracked independently.
5. Source anomalies should be surfaced by validators instead of silently repaired.

---

# 6. Dataset-specific extensions

## Alibaba extensions likely needed

- task/DAG identity
- task type
- instance count
- machine ID
- retry sequence (`seq_no`, `total_seq_no`)
- workload-family/recurrence derivation metadata if later used

## Azure extensions likely needed

- subscription ID
- deployment ID
- VM category
- VM core-count bucket
- VM memory-capacity bucket
- replay/window metadata
- explicit marker that observed memory is unavailable

---

# 7. Feasibility decision by dataset

## Google
Canonical full CPU+memory TraceAdvisor path remains the reference implementation.

## Alibaba
**Feasible for further full-pipeline integration**, with two caveats:
1. recurrence is not explicit and must be derived/validated if next-occurrence prediction is required;
2. job-level concurrent resource aggregation must respect task DAG/timing rather than naïvely sum all tasks.

## Azure VM
**Feasible for CPU-oriented TraceAdvisor validation/replay.**

Not supported from the selected trace:
- observed-memory target
- full Google-style CPU+memory parity
- explicit next-occurrence recurrence without an additional validated rule

This limitation is informative and should be represented through capability metadata rather than hidden.

---

# 8. Issue-1 acceptance checklist

- [x] Workload/job/task/execution/instance identifiers documented.
- [x] Timestamp and execution-window semantics documented.
- [x] Aggregation cadence documented where available.
- [x] CPU request/allocation/observed fields documented.
- [x] Memory request/allocation/observed fields documented.
- [x] Units/source-native semantics and value ranges reviewed.
- [x] Missing values and sample anomalies documented.
- [x] Duplicate behavior checked in supplied samples.
- [x] Point-in-time history feasibility documented per dataset.
- [x] Next-occurrence feasibility documented per dataset.
- [x] Full CPU/memory pipeline feasibility documented.
- [x] Dataset-specific extension fields identified.
- [x] Google / Alibaba / Azure capability matrix produced.
- [x] Canonical-schema implications documented.

---

# 9. Open questions carried forward

These do **not** block completion of the semantics-study issue. They become explicit design/integration questions for later issues.

### Alibaba
- What derived workload-family signature, if any, is strong enough to serve as recurrence?
- How should concurrent DAG stages be aggregated into full-workload occurrence resources?
- How should retries be folded into one logical instance/occurrence when retry rows are encountered?

### Azure
- Should the modeling unit be VM, deployment, or a time-windowed deployment?
- Should Azure remain history/replay-based rather than use next-occurrence recurrence?
- During adapter integration, perform an intentional same-VM join between VM-table and CPU-reading samples instead of comparing independent head samples.

---

# 10. Final Issue-1 conclusion

New Development Issue 1 has achieved its purpose: the source semantics, capability boundaries, feasibility, and canonical-schema implications are understood well enough to begin **New Development Issue 2 — Define Canonical Workload Interface and Schema**.

The key architectural outcome is that the canonical TraceAdvisor interface must be **capability-aware** rather than assuming Google semantics for every dataset.

In particular:

- recurrence must be optional;
- CPU and memory support must be independent;
- request/allocation/observed resource concepts must remain distinct;
- unsupported resources must remain unknown;
- dataset-specific adapters must preserve source-native semantics.
