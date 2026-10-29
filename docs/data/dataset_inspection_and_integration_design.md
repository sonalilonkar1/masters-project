# Dataset Inspection and Integration Design

**Status:** Inspection and documentation only. No source code, notebooks, schemas, adapters, configurations, tests or pipeline logic were modified during the inspection.
**Date:** 2026-10-15
**Repository state inspected:**
- `main` at `91470a3`.
- The unmerged branch `origin/feature/external-dataset-canonical-pipeline` (PR #70, head `69f3a42`), read through `git show` without checking it out.

**How this report is organized**

| Sections | Content |
|---|---|
| 1–2 | Why the inspection was needed and how evidence is labeled |
| 3 | What was inspected: repository and data inventory |
| 4 | What was verified: dataset-by-dataset findings, including what remains uncertain |
| 5 | Cross-dataset comparison of findings |
| 6–7 | Canonical-schema and adapter-design requirements identified by the inspection |
| 8 | Decisions emerging from the inspection |
| 9 | Unresolved questions |
| 10 | What the inspection enables next |

---

## 1. Purpose and Inspection Scope

### Why inspection is needed before schema and adapter design

The canonical schema and adapter framework must carry the real semantics of each source. The selected datasets differ in:
- recurrence identities;
- modeling units;
- timestamp units;
- request semantics;
- observed-resource semantics;
- peak definitions;
- aggregation rules;
- status vocabularies;
- missingness patterns.

Assuming Google's meanings elsewhere would break the schema in three concrete ways.

**1. Recurrence differs by source.**
- Google: TraceAdvisor *constructs* recurrence (`user‖collection_logical_name`).
- Alibaba GPU v2020: recurrence is *provided by the source* (`group`).
- Alibaba v2018: there is no official recurrence identity.

A schema that assumes one rule will either fabricate recurrence or reject valid data.

**2. "Peak" and aggregation mean different things.**
- Google: occurrence peaks are aligned-window *sums* across parallel executions.
- Alibaba GPU v2020: metrics are per-worker *lifetime* values, a lifetime maximum for memory and only a lifetime average for CPU.
- Alibaba v2018: per-instance peaks for both CPU and memory.

A single `peak_cpu` column without semantics metadata would mislabel averages as peaks.

**3. Units and status vocabularies differ.**
- Units: NCU, percent of a core, GB, normalized values.
- Status: FINISH/FAIL versus Terminated/Failed.

The schema needs explicit units and dataset-specific filtering rules.

### Inspection scope

| Dataset | Inspection role |
|---|---|
| Google Cluster subset 2019 | Existing reference pipeline (`pipelines/google_subset/`) |
| Alibaba GPU v2020 (PAI) | Required full integration target: recurrence, history, next-occurrence targets, baselines, evaluation |
| Alibaba v2018 | Optional reduced adapter demonstration, if time permits |
| Azure (any trace) | Outside the current implementation scope |

No source code, notebooks, adapters, schemas, configurations or tests were changed during the inspection.

---

## 2. Evidence and Verification Labels

| Label | Meaning |
|---|---|
| **[REPO]** | Evidence from a TraceAdvisor repository file or branch. The path is given; the branch is `main` unless marked PR #70. |
| **[LOCAL]** | A data file available locally under `data/` in this working copy. These files are git-ignored. |
| **[DOC]** | Official dataset documentation: Alibaba `clusterdata` READMEs and schemas, or the Kaggle page named in the repository |
| **[DL]** | Official data downloaded during the inspection into the session scratchpad and profiled with read-only scripts. The SHA-256 of the GPU v2020 `pai_job_table.csv`, `pai_group_tag_table.csv` and `pai_task_table.csv` matched the checksums published in the official README. |
| **[DL-HEAD]** | Only a prefix or head of a large file was inspected |
| **requires confirmation** | The fact could not be verified from the repository, the documentation or the downloaded data |

**How to interpret the labels**
- **Head rows are not necessarily random samples.** A file's first rows may be ordered by time, machine or ID.
- **Prefix counts must not be treated as full-dataset counts.** Every [DL-HEAD] number describes the downloaded prefix only.
- **Downloaded inspection files are not repository artifacts.** [DL] data lives in the session scratchpad. It is not committed and has no agreed repository path (section 3.5).
- **Verified facts, interpretations and unresolved questions are kept distinct:**
  - verified findings are in section 4;
  - requirements derived from them are in sections 6–7;
  - emerging decisions are in section 8;
  - open questions are in section 9.

---

## 3. Repository and Data Inventory

### 3.1 Google notebooks and pipeline modules [REPO]

| Path | Role |
|---|---|
| `pipelines/google_subset/00_dataQualityReview.ipynb` | Raw data quality review |
| `pipelines/google_subset/01_dataIngestion.ipynb` | Parsing, unit conversion, observation table |
| `pipelines/google_subset/02_reconstructExecutions.ipynb` | Episode reconstruction from `collection_id‖instance_index` with a 5-minute gap rule |
| `pipelines/google_subset/03_buildProfilesAndMetrics.ipynb` | Occurrences, aligned-window peaks, point-in-time history |
| `pipelines/google_subset/04_splitAndBaselines.ipynb` | Next-occurrence targets, chronological split, Request/Mean/P90/P95/P99 baselines, validation-only selection |
| `pipelines/google_subset/05_evaluateRecommendations.ipynb` | **Empty (0 bytes)** |
| `notebooks/subset/subset-0{1..6}-*.ipynb`, `notebooks/GoogleCluster2019/*`, `notebooks/Experiments_HistoryBasedBaselines.ipynb` | Earlier exploratory work; not part of the current reference pipeline |

A full cell-level analysis of the Google pipeline is in the **Google Subset Pipeline Analysis report** (`docs/data/google_subset_pipeline_analysis.md`, uncommitted). Its finding numbers (for example F7) are cited below for traceability.

### 3.2 Shared utilities, evaluator, metrics and data models [REPO]

| Path | Content |
|---|---|
| `src/evaluation/metrics.py`, `src/evaluation/evaluator.py` | Shared `RecommendationEvaluator`. Covers CPU and memory only and is NaN-aware. `any_resource_violation` returns NaN when one resource is unknown (`metrics.py:68–81`). |
| `src/features/feature_config.py` | Feature configuration |
| `src/features/ml_prep.py` | ML preparation |
| `src/features/split_utils.py` | `chronological_split` |
| `src/baselines/baseline1_percentile_margin.py`, `src/eval/evaluator_v0.py` | Older baseline and evaluator |
| `tests/test_evaluation.py`, `tests/test_split_utils.py` | Tests |
| PR #70: `src/canonical/schema.py` | Canonical schema v0.1.0: `RECORD_LEVELS`, resource value and unit pairs, `DatasetCapabilities` (10 boolean flags), `validate_canonical_frame`, `validate_evaluator_view` |
| PR #70: `config/dataset_capabilities.json` | Capability registry entries for `google_clusterdata2019`, `alibaba_clustertrace2018` and `azure_public_vm_v2` |
| PR #70: `src/adapters/validation.py` | `validate_adapter_output` |

**No production Google adapter exists** on either branch. The Google pipeline reads its own notebook outputs directly.

### 3.3 Existing Alibaba and Azure files [REPO]

| Path | Content |
|---|---|
| PR #70: `src/adapters/base.py` | `BaseDatasetAdapter.adapt()` and `AdapterResult` |
| PR #70: `src/adapters/reference.py` | `ReferenceOccurrenceAdapter`, a contract test adapter, **not** a production Google adapter |
| PR #70: `src/adapters/alibaba.py` | `Alibaba2018Adapter`: instance level, joins `batch_task` plans onto `batch_instance`; `recurrence_key` intentionally null |
| PR #70: `src/adapters/azure_vm.py` | `AzureVMAdapter` (VM-table and CPU-interval views) |
| PR #70: `tests/test_external_adapter_integration.py`, `tests/test_adapter_contract.py`, `tests/test_azure_vm_adapter.py` | Adapter tests |
| PR #70: `scripts/build_external_canonical_samples.py` | Builds canonical sample artifacts; loads whole headerless CSVs into memory |
| PR #70: `docs/data/old_dataset_semantics_alibaba2018_azure.md`, `traceadvisor_external_dataset_capability_matrix.csv` | Semantics study and capability matrix for Alibaba 2018 and Azure only, based on samples |
| PR #70: `docs/design/canonical_workload_schema.md`, `docs/design/adapter_framework.md` | Existing drafts of the schema and adapter framework documents (section 10) |
| `notebooks/resource-central/resource_central.ipynb` (`main`) | Existing Azure VM notebook (out of current scope) |
| `docs/data/alibaba_dataset_selection_feasibility.md` (uncommitted) | Dataset-selection analysis |
| **Alibaba GPU v2020** | **Nothing exists in the repository**: no adapter, loader, notebook or capability entry |

### 3.4 Data files available locally [LOCAL]

| Path | Content | Size |
|---|---|---|
| `data/raw/clusterdata2019_kaggle_subset.csv` | Google 2019 Kaggle subset: 405,894 rows × 34 columns | 328 MB |
| `data/processed/google_subset_v1/*.parquet`, `metadata.json`, `baseline_validation_comparison.csv` | Google pipeline outputs, notebooks 01–04 | ~131 MB total under `data/processed` |
| `data/processed/*_v0.parquet`, `*_v1.parquet`, `*_v2.*` | Older Google subset artifacts | — |
| `data/raw/azure/2023Dataset/`, `data/raw/azure/processed/` | Azure LLM inference data (out of scope) | — |
| `data/raw/azure/2021Dataset/` | Empty | — |
| `data/raw/subset/` | Empty | — |
| **Alibaba (any version)** | **Not present in the repository or locally under `data/`** | — |

### 3.5 Download instructions and expected paths

| Dataset | Official source | Repository instructions | Expected local path | Inspection download status |
|---|---|---|---|---|
| Google subset | Kaggle `derrickmwiti/google-2019-cluster-sample` [REPO `docs/data/subsetSetup.md:7–8`] | `scripts/verify_data_setup.py` checks `data/raw/clusterdata2019_kaggle_subset.csv` | Present | Local copy used |
| Alibaba GPU v2020 | `https://aliopentrace.oss-cn-beijing.aliyuncs.com/v2020GPUTraces/<table>.tar.gz`, 7 tables; backup at `github.com/qzweng/clusterdata-cluster-trace-gpu-v2020-data` [DOC `cluster-trace-gpu-v2020/data/README.md`]. Checksums are published in the README. | **None** | **Not defined.** A path such as `data/raw/alibaba_gpu_v2020/` is suggested but does not exist and is not a decision. | **Full** download of 6 tables [DL]. `pai_machine_metric` not downloaded. Job, task and group checksums matched. |
| Alibaba v2018 | `http://aliopentrace.oss-cn-beijing.aliyuncs.com/v2018Traces/<table>.tar.gz` [DOC `trace_2018.md`] | The PR #70 script takes `--alibaba-task` / `--alibaba-instance` paths | Not defined | **Full** `batch_task` [DL]; **first 3,783,610 rows** of `batch_instance` [DL-HEAD] |
| Azure (out of scope) | `https://github.com/Azure/AzurePublicDataset` (release assets) | — | — | Not part of this inspection |

**Alibaba GPU v2020 compressed table sizes [DOC]**

| Table | Compressed size |
|---|---|
| `pai_group_tag_table` | 53 MB |
| `pai_job_table` | 60 MB |
| `pai_task_table` | 34 MB |
| `pai_instance_table` | 663 MB |
| `pai_sensor_table` | 388 MB |
| `pai_machine_metric` | 198 MB |
| `pai_machine_spec` | 32 KB |

**Alibaba v2018 sizes [DOC]:** `batch_task` 125 MB and `batch_instance` 20 GB compressed; the full set is 48 GB compressed and 280 GB extracted.

### 3.6 Documentation inspected

| Dataset | Documents |
|---|---|
| Google | [REPO] `docs/data/google_clusterdata_2019_analysis.md`, `docs/data/subsetSetup.md`; the Google Subset Pipeline Analysis report; `data/processed/google_subset_v1/metadata.json` |
| Alibaba GPU v2020 | [DOC] `cluster-trace-gpu-v2020/README.md` and `cluster-trace-gpu-v2020/data/README.md`; upstream issues #114 (recurrence via `group`) and #151 (`inst_num` vs worker mismatches; CPU and memory overuse). Nothing in the repository. |
| Alibaba v2018 | [DOC] `cluster-trace-v2018/trace_2018.md`, `cluster-trace-v2018/schema.txt`; [REPO] PR #70 `old_dataset_semantics_alibaba2018_azure.md` |
| Canonical schema and adapters | [REPO] PR #70 `src/canonical/schema.py`, `src/adapters/*.py`, `config/dataset_capabilities.json`, `docs/design/canonical_workload_schema.md`, `docs/design/adapter_framework.md` |
| Azure (out of scope) | [DOC] `github.com/Azure/AzurePublicDataset` README; [REPO] PR #70 `src/adapters/azure_vm.py` (inventory only) |

---

## 4. Dataset-by-Dataset Inspection

Each subsection records verified findings with their evidence label. Items that could not be verified are marked **requires confirmation**. Points that need a design choice are marked **design question** and are collected in section 9.

## 4.1 Google Cluster subset 2019

### Dataset identity

| Item | Value | Evidence |
|---|---|---|
| Name and version | Google ClusterData 2019 (Borg), Kaggle sample | [REPO `docs/data/subsetSetup.md`] |
| Trace period | 31 days: `time` 0 to 2,678,400 s; `usage_end_time_us` maximum 2,678.7 s × 10⁶ | [LOCAL observations parquet] |
| Cells | 8 cells (`cluster` 1–8), 42,713–58,783 rows each | [LOCAL] |
| Local state | **Already a sample** (Kaggle subset). TraceAdvisor then **preprocesses** it into observations → executions → occurrences. | [LOCAL] |
| Raw file | `data/raw/clusterdata2019_kaggle_subset.csv`, 405,894 rows × 34 columns | [LOCAL] |
| Processed artifacts | `data/processed/google_subset_v1/{google_subset_observations_v1, google_subset_observations_reconstructed_v1, google_subset_executions_v1, job_profiles_google_subset_history_v1, train/val/test_occurrences, train/val/test_features}.parquet`, plus `metadata.json` | [LOCAL] |
| How the Kaggle sample was drawn from the full trace | **requires confirmation** | — |

### Modeling unit

| Level | Google meaning | Evidence |
|---|---|---|
| Raw observation | One instance event joined with one usage window (`time`, `event`, `start_time`, `end_time`, `average_usage`, `maximum_usage`, `resource_request`). 405,894 observations; `observation_id` unique. | [LOCAL] |
| Job | `collection_id` (a Borg collection) | Google Subset Pipeline Analysis report, section 3 |
| Execution | An episode of `collection_id‖instance_index`, split on a **5-minute gap**. **253,585 executions.** | [LOCAL executions parquet]; Google Subset Pipeline Analysis report, section 3.3 |
| Occurrence | `occurrence_key = recurrence_key‖execution_start_time_us`: executions of one recurrence starting at the same time. **4,879 occurrences.** | [LOCAL `metadata.json` `occurrence_key_definition`] |
| Grouping | Observations → executions (gap rule); executions → occurrences (shared start time); peaks aggregated over aligned windows across parallel executions | Google Subset Pipeline Analysis report, findings F8 and F9 |

### Identifiers and recurrence

| Item | Value | Evidence |
|---|---|---|
| Identifiers | `collection_id`, `instance_index`, `machine_id`, `alloc_collection_id`, `user`, `collection_name`, `collection_logical_name` | [LOCAL] |
| Recurrence key | `recurrence_key = user‖collection_logical_name` | [LOCAL executions parquet; `metadata.json`] |
| Official or inferred | **Inferred by TraceAdvisor**; not an official Google recurrence identifier | Google Subset Pipeline Analysis report |
| Recurrence coverage | 0 of 253,585 executions lack a key | [LOCAL] |
| Repetition | 2,280 keys. Keys with ≥ 2 occurrences: 653 (3,252 occurrences, 66.7%); ≥ 5: 145; ≥ 10: 52. | [LOCAL history parquet] |
| Target availability | 2,599 of 4,879 occurrences have a next-occurrence target | [LOCAL] |
| Next-occurrence defensibility | Yes, within the constructed key. Known caveats: targets are built before the split and cross split boundaries (findings F1–F4), and 9 overlapping occurrences exist (risk R9). | Google Subset Pipeline Analysis report |

### Time semantics

| Item | Value | Evidence |
|---|---|---|
| Raw time fields | `time`, `start_time`, `end_time` (µs) | [LOCAL] |
| Derived time fields | `event_time_us`, `usage_start_time_us`, `usage_end_time_us`, `execution_start_time_us`, `execution_end_time_us`, `occurrence_end_time_us` | [LOCAL] |
| Units | Microseconds from trace start | [LOCAL]; `metadata.json` |
| Sentinel timestamps | 3 rows have `time` = 2⁶³−1; their `event_time_us` is null | [LOCAL] |
| History ordering | History uses earlier occurrences with `end ≤ start` | `metadata.json` `history_rule` |
| Target ordering | `shift(-1)` within `recurrence_key`, ordered by start | `metadata.json` `target_definition` |
| Chronological split | **Feasible and implemented**: 70/15/15 by `execution_start_time_us`, group-preserving | `metadata.json` `split_boundaries` |
| Boundary details | Train ends at 1,812,600,000,000 µs; validation spans 1,813,200,000,000–2,261,100,000,000 µs; test starts at 2,262,600,000,000 µs | `metadata.json` `split_boundaries` |

### Resource semantics

Execution-level peaks and full-workload occurrence peaks are **different concepts** and are listed separately.

| Field | Meaning | Unit | Request / observed | Average / peak | Level | Aggregation | Missing |
|---|---|---|---|---|---|---|---|
| `requested_cpu_ncu` | CPU request | NCU (Google normalized compute units) | Request | — | Observation → execution → occurrence | Occurrence request carried through (`occurrence_cpu_request_nunique` tracked) | 774 null observations |
| `requested_memory_normalized` | Memory request | Normalized to the largest machine | Request | — | Same | Same | 774 null observations |
| `average_cpu_ncu`, `average_memory_normalized` | Mean usage in a window | NCU / normalized | Observed | **Average** | Window | — | 0 null |
| `peak_cpu_ncu` | Maximum CPU in a window; execution CPU peak | NCU | Observed | **Peak** (window maximum) | Window → execution | Maximum over the execution | 0 null |
| `peak_memory_normalized` | Maximum memory in a window; execution memory peak | Normalized | Observed | **Peak** | Window → execution | Maximum | 4,927 null observations |
| `occurrence_peak_cpu_ncu` / `occurrence_peak_memory_normalized` | Full-workload occurrence peak | NCU / normalized | Observed | **Peak of aligned-window sums** across parallel executions | Occurrence | Sum across executions per aligned window, then maximum | 0 / 60 null occurrences |
| GPU | — | — | — | — | — | — | **Not in the trace** |

### Status and filtering

| Item | Value | Evidence |
|---|---|---|
| Status fields | `event` (`instance_events_type`), plus `failed` (0/1) | [LOCAL] |
| Distribution | FINISH 92,867; FAIL 92,678; ENABLE 75,907; SCHEDULE 69,104; LOST 59,515; EVICT 14,756; KILL 951; others 116 | [LOCAL] |
| `failed` | 0: 313,216; 1: 92,678 | [LOCAL] |
| Current inclusion behavior | **No exclusion.** FAIL, LOST, EVICT and KILL records currently enter history and targets; 2,584 of 4,879 occurrences are affected. | Google Subset Pipeline Analysis report, finding F7 |
| Filtering implication | Any exclusion rule is dataset-specific (Google event vocabulary). Whether to change the current behavior is a **design question** (section 9). | — |

### Missingness and quality

| Check | Finding | Evidence |
|---|---|---|
| Duplicate observations | `observation_id` has no duplicates | [LOCAL] |
| Machine duplication | 38,146 of 253,594 instance windows span several machines with identical peaks. Summing them inflates 1,159 occurrence CPU peaks (cause suspected). | Google Subset Pipeline Analysis report, finding F8 |
| Missing requests | 774 null requests | [LOCAL] |
| Missing memory | 4,927 null memory peaks; 60 occurrences with a null memory peak | [LOCAL] |
| Impossible values | None found. 0 rows have CPU peak < average. Maximum `peak_cpu_ncu` 1.27; maximum `peak_memory_normalized` 0.224. | [LOCAL] |
| Unit-name inconsistencies | Inconsistent unit names across stages | Google Subset Pipeline Analysis report, finding F11 |
| Small validation population | 329 occurrences in the common validation population | `metadata.json` |

## 4.2 Alibaba GPU Cluster Trace v2020

### Dataset identity

| Item | Value | Evidence |
|---|---|---|
| Official name | `cluster-trace-gpu-v2020`, Alibaba PAI (Platform for Artificial Intelligence) | [DOC README] |
| Paper | NSDI '22, "MLaaS in the Wild" | [DOC] |
| Workload | Hybrid ML training and inference | [DOC] |
| Scale | More than 6,500 GPUs on about 1,800 machines; 1,897 machines in `pai_machine_spec` | [DOC]; [DL] |
| Period | "July and August of 2020". Job `start_time` ranges from 494,319 to 6,451,081 s, about **68.9 days**. | [DOC]; [DL] |
| Format | Headerless CSV; column names come from the README | [DL] |
| Local inspection status | **Not in the repository.** Profiled from the full official tables downloaded to the scratchpad. The data is raw and unfiltered. | [DL] |
| Checksums | Job, task and group tables matched the README checksums | [DL] |
| `pai_machine_metric` | **Not downloaded** | — |

| Table | Rows [DL] | Compressed size [DOC] |
|---|---|---|
| `pai_job_table` | 1,055,501 | 60 MB |
| `pai_task_table` | 1,261,050 | 34 MB |
| `pai_instance_table` | 7,522,002 | 663 MB |
| `pai_sensor_table` | 3,033,232 | 388 MB |
| `pai_group_tag_table` | 1,055,032 | 53 MB |
| `pai_machine_spec` | 1,897 | 32 KB |
| `pai_machine_metric` | not downloaded | 198 MB |

### Modeling hierarchy

| Level | Meaning | Identifiers | Evidence |
|---|---|---|---|
| Job | One user submission. `inst_id` is one-to-one with `job_name` ("treat … as `job_id`"); 0 duplicate `job_name`, 0 duplicate `inst_id`. | `job_name`, `inst_id`, `user` | [DOC]; [DL] |
| Task | A component of a job. One to four tasks per job (median 1). Holds the plan: `plan_cpu`, `plan_mem`, `plan_gpu`, `inst_num`. | `job_name`, `task_name` | [DOC]; [DL] |
| Task role | The role named by `task_name`, e.g. `tensorflow`, `worker`, `ps`, `PyTorchWorker`, `evaluator` | `task_name` | [DOC]; [DL] |
| Instance | A container of a task. **Inherits the task's plan.** | `inst_name`, `worker_name`, `machine` | [DOC] |
| Worker | The instance identity used to join usage (`worker_name`, "more detailed than `inst_name`") | `worker_name` | [DOC] |
| Sensor row | **One per worker** (0 duplicate `worker_name` in the sensor table). A lifetime aggregate of that worker. | `worker_name` (plus `job_name`, `task_name`, `machine`) | [DL] |

**Relationships:** job ← task (plan) ← instance (time, status, machine) ← sensor (usage), joined on `job_name`, `task_name` and `worker_name`.

**Occurrence unit (inspection finding):** one job submission within a `group` is the natural source-defined repetition unit [DOC `group` definition].

**Evaluation unit:** requires an explicit design decision. The inspection identifies task-role and worker-level alternatives, because plans are defined per task while usage observations are provided per worker.

**Aggregation:** the inspection identifies a resource-aggregation decision, because task plans are inherited by workers and sensor values are reported per worker. The appropriate aggregation method must be explicitly documented rather than assumed.

Supporting evidence [DL]:
- Jobs have one to four tasks.
- Plans are per task, and instances inherit them.
- Sensor rows are per worker.
- 19.3% of sensor-covered jobs have more than one worker (median 1, 99th percentile 43, maximum 559).

Worker-level data therefore cannot automatically be treated as job-level data.

### Identifiers and recurrence

| Item | Value | Evidence |
|---|---|---|
| Identifiers | `job_name`, `inst_id` (= job), `user`, `task_name`, `inst_name`, `worker_name`, `machine`, **`group`**, `workload` | [DOC] |
| Official meaning of `group` | "Instances with the same group tag are considered as repeated instances." It is a semantic tag derived from entry scripts, command-line parameters and data sources/sinks. Upstream issue #114 adds that jobs with the same group are "treated as recurring ones". | [DOC]; upstream issue #114 |
| Official or inferred | **Officially defined by the source** | [DOC] |
| Coverage | **99.86%** of jobs have a `group` row (1,530 of 1,055,501 jobs have no group-tag row; 1,061 group-tag rows match no job) | [DL] |
| Missing group keys | **1,530 jobs (0.14%)**; 1,460 of them accepted (corrected from 469 by the Task 3 source data checks, `docs/data/alibaba_gpu_2020_source_data_checks.md`) | [DL] |
| User consistency | 0 groups span more than one `user`; 0 user mismatches between the job and group tables | [DL] |
| Group sizes | 316,458 groups. Median 1, 90th percentile 3, 99th percentile 61, **maximum 22,641**. | [DL] |
| Repetition, all statuses | Groups with ≥ 2 jobs: 43,060 (780,573 jobs, 74.0%). ≥ 5: 21,971 (68.6%). ≥ 10: 12,891 (63.1%). | [DL] |
| Repetition, Terminated jobs only | ≥ 2: 32,695 groups (546,325 jobs). ≥ 5: 15,120 (499,327). ≥ 10: 10,218 (468,400). | [DL] |
| Repetition, Terminated + group + sensor | ≥ 2: 28,418 groups (432,455 jobs). **≥ 5: 13,551 groups (392,590 jobs).** ≥ 10: 9,531 groups (367,304 jobs). | [DL] |
| `workload` tag | Present for 9.7% of jobs (bert 54,800; ctr 27,054; nmt 10,326; …). A coarse label, **not a recurrence key**. | [DL]; [DOC "around 9%"] |
| Next-occurrence defensibility | Supported within `group`, for memory peak and CPU average. A few very large groups (maximum 22,641) will dominate unless handled; handling is a **design question**. | [DL] |

### Time semantics

| Item | Value | Evidence |
|---|---|---|
| Job times | `start_time` = **submission**; `end_time` = **completion** | [DOC] |
| Task times | `start_time` = **launch**; the gap from job submission is the scheduling wait | [DOC] |
| Instance times | `start_time` = launch; `end_time` = completion | [DOC] |
| Sensor timing | Sensor rows have **no** timestamps; timing is inherited through `worker_name` → instance | [DOC]; [DL] |
| Units | Seconds, shifted by a constant | [DOC] |
| Time-of-day limitation | Time of day and weekday are preserved only in UTC+8; dates, months and years are fake | [DOC] |
| Missing job times | `start_time` null for 3,663 jobs (all Waiting). `end_time` null for 296,420 (Failed 230,935; Running 61,867; Waiting 3,618). **Every Terminated job has an end time.** | [DL] |
| Missing instance times | `start_time` null for 1,773,468 (Running, Interrupted, Waiting, Failed, Ready); `end_time` null for 2,267,582 | [DL] |
| Invalid ordering | Job `end < start`: 0. Instance `end < start`: 0. | [DL] |
| History rule | Order occurrences within a group by job `start_time` (submission, the pre-execution instant). History uses earlier jobs completed by time t (`end_time ≤ t`). | [DOC] |
| Chronological split | **Feasible**: 68.9 days; splits by job submission time | [DL] |

### Resource semantics

| Field | Table | Meaning | Unit | Request / observed | Average / peak | Level | Aggregation note | Missing |
|---|---|---|---|---|---|---|---|---|
| `plan_cpu` | task | Requested CPU | Percent of one vCPU (600 = 6 vCPU) | **Request** | — | Task (inherited per instance) | Any job total (Σ `plan_cpu × inst_num`) is a **design question** | 18,454 null; 11 rows ≤ 0 |
| `plan_mem` | task | Requested main memory | **GB** | **Request** | — | Task (inherited per instance) | Same | 18,454 null |
| `plan_gpu` | task | Requested GPU | Percent of one GPU | **Request** | — | Task | Same | 223,965 null |
| `gpu_type` | task | Assigned GPU type (`MISC` = older generations) | Category | Allocation | — | Task | — | 217,738 null |
| `cpu_usage` | sensor | CPU used | Percent of one vCPU | **Observed** | **Lifetime average** ("taking the average of all data in the instance's lifetime"). **Not a CPU peak.** | Worker | Job-level combination is a **design question** | 5,829 null |
| `avg_mem` | sensor | Main memory used | GB | **Observed** | **Lifetime average** | Worker | Same | 1,217 null |
| `max_mem` | sensor | Main memory used | GB | **Observed** | **Lifetime maximum** | Worker | A sum of per-worker maxima is only an **upper bound**, not a concurrent job peak | 0 null |
| `gpu_wrk_util` | sensor | GPU used | Percent of one GPU | Observed | Lifetime average | Worker | — | 0 null |
| `avg_gpu_wrk_mem` | sensor | GPU memory used | GB | Observed | Lifetime average | Worker | — | 0 null |
| `max_gpu_wrk_mem` | sensor | GPU memory used | GB | Observed | Lifetime maximum | Worker | — | 0 null. A GPU-memory peak exists, but there is **no GPU-memory request**. |
| `cap_cpu`, `cap_mem`, `cap_gpu` | machine_spec | Machine capacity | Cores / GB / GPUs | Capacity | — | Machine | — | `cap_cpu` 64–96; `cap_mem` 384–512 |

**Key distinctions**
- `cpu_usage` is a lifetime average, not a CPU peak.
- `avg_mem` is a lifetime average; `max_mem` is a lifetime maximum.
- Task plans are inherited per instance, while sensor values are per worker.
- A sum of worker memory maxima is only an upper bound.

**Unit comparability** [DOC + DL]
- `plan_mem` and `max_mem` are both documented in GB and cross-referenced ("c.f. `plan_mem`").
- Per worker, `max_mem / plan_mem` has a median of 0.196 and a 90th percentile of 1.133. **12.0%** of worker rows have `max_mem > plan_mem`.
- `cpu_usage` and `plan_cpu` share the percent-of-vCPU unit. `cpu_usage > plan_cpu` for **15.4%** of worker rows.

### Status and filtering

| Table | Status distribution [DL] |
|---|---|
| Job | Terminated 732,355; Failed 256,555; Running 62,928; Waiting 3,663 |
| Task | Terminated 885,073; Failed 256,762; Running 115,501; Waiting 3,714 |
| Instance | Terminated 4,757,371; Failed 969,975; Running 809,664; **Interrupted 654,022**; Waiting 323,840; Ready 7,130 |

- **Official rule [DOC]:** "only 'Terminated' tasks are successful".
- **Candidate exclusions (inspection findings, not implemented rules; design question in section 9):**
  - Running and Waiting jobs, which are incomplete with no end time;
  - Failed jobs, for targets and history;
  - Interrupted, Ready and Waiting instances;
  - workers with no sensor row.
- **Status vocabulary:** dataset-specific. It differs from Google's FINISH/FAIL/EVICT/LOST/KILL.

### Missingness and quality

| Check | Finding | Evidence |
|---|---|---|
| Sensor coverage by instance | Only **40.2%** of instance rows have a sensor row. By instance status: Terminated 42.5%, Failed 44.6%, Running 33.2%, Waiting and Ready 0%. | [DL] |
| Sensor coverage by job | 79.3% of jobs have at least one sensor row | [DL] |
| Why workers lack sensors | Whether the remaining workers ever ran, or simply lack telemetry: **requires confirmation** | — |
| Null `worker_name` | 331,057 instance rows | [DL] |
| Null `machine` | 331,057 instance rows (the same count) | [DL] |
| Duplicate `worker_name` | 45,689 instance rows share a non-null `worker_name`, mostly Terminated (43,864) | [DL] |
| `inst_num` mismatch | 4.5% of tasks have **more** instance rows than `inst_num`; none have fewer | [DL] |
| Retry or rescheduling interpretation | The cause of extra rows: **requires confirmation**. Upstream issue #151 discusses `inst_num` versus worker mismatches. | [DOC issue #151] |
| `max_mem > cap_mem` | **5,322 sensor rows** exceed the host machine's `cap_mem` (maximum `max_mem` 2,757.6 GB vs a 512 GB maximum capacity) | [DL] |
| CPU capacity | 0 rows have `cpu_usage` above `cap_cpu × 100` | [DL] |
| `max_mem ≥ avg_mem` | Holds for all rows (0 violations); 0 negative values | [DL] |
| No CPU peak | CPU evaluation can only be against the lifetime average, which understates violations | [DOC] |
| Upstream evidence | Issue #151 reports CPU and memory overuse relative to requests, consistent with the 15.4% and 12.0% above | [DOC issue #151] |

## 4.3 Alibaba Cluster Trace v2018

### Dataset identity

| Item | Value | Evidence |
|---|---|---|
| Version | `cluster-trace-v2018` | [DOC `trace_2018.md`] |
| Workload types | Co-located online services (Sigma containers) and batch jobs (Fuxi) | [DOC] |
| Scale | About 4,000 machines; 8 days | [DOC] |
| Trace period (measured) | `batch_task.start_time` from 0 to 765,880 s (**8.86 days**) | [DL] |
| Sizes | 48 GB compressed / 280 GB extracted. `batch_task` 125 MB and `batch_instance` 20 GB compressed. | [DOC] |
| Files | Batch side: `batch_task`, `batch_instance`. Online side: `container_meta`, `container_usage`. Machines: `machine_meta`, `machine_usage`. | [DOC] |
| Download status | Not in the repository. **Full** `batch_task` (14,295,731 rows) [DL]; **first 3,783,610 rows** of `batch_instance` [DL-HEAD]. Raw data. | [DL]; [DL-HEAD] |

### Modeling unit

| Level | Meaning | Evidence |
|---|---|---|
| Job | `job_name` (`j_<n>`): one batch job made of a DAG of tasks. **4,201,014 jobs.** | [DL] |
| Task | `task_name`, unique within a job, encodes the DAG. Holds `plan_cpu`, `plan_mem`, `instance_num`. 0 duplicate `(job_name, task_name)`. 12 task types. | [DOC]; [DL] |
| DAG | Task dependencies are deduced from `task_name`; a task finishes only when all its instances complete | [DOC] |
| Instance | A `batch_instance` row: `instance_name`, `cpu_avg`, `cpu_max`, `mem_avg`, `mem_max` | [DOC] |
| Retries | `seq_no` / `total_seq_no` sequence numbers | [DOC] |
| Occurrence | **Undefined.** There is no recurrence identity and hence no repeated occurrence. The PR #70 adapter uses the **instance** level. | [REPO PR #70 `src/adapters/alibaba.py`] |
| Grouping | Instance ← task plan join (as in the PR #70 adapter). Any job-level value needs DAG-aware aggregation, because tasks run in sequence. | [DOC] |
| Online container side | Containers grouped by `app_du` (deploy unit), which are long-running services | [DOC] |

### Identifiers and recurrence

- **Job, task and instance identifiers:** `job_name`, `task_name`, `instance_name`, `machine_id` and `task_type` [DOC].
- **No user identity:** there is no user field [DOC].
- **No official recurrence key** [DOC]. Records without a key: 100%.
- **Template evidence only:** the PR #70 study found shared task-name/DAG signatures in sampled jobs (89.2%, and 64.0% for a richer signature). That is evidence of templates, not identity [REPO PR #70 `old_dataset_semantics_alibaba2018_azure.md`].
- **Next-occurrence targets are not currently defensible**, because any recurrence rule would be invented.

### Time semantics

- `start_time` and `end_time` are in seconds from trace start (0) [DOC].
- `batch_task` problems [DL]:
  - `end_time == 0` for 78,311 tasks;
  - `end < start` for 54,580 tasks.

  PR #70's adapter nulls these end times (`alibaba.py`, `valid_end`).
- **Short time span:** 8.86 days.
- **Chronological split:** possible but limited. The span is short for history depth plus three splits.

### Resource semantics

| Field | Table | Meaning | Unit | Request / observed | Average / peak | Level | Missing |
|---|---|---|---|---|---|---|---|
| `plan_cpu` | batch_task | CPU needed | 100 = 1 core | Request | — | Task | 61,857 null [DL] |
| `plan_mem` | batch_task | Memory needed | Normalized, documented range [0, 100] | Request | — | Task | 61,857 null. Observed range 0.02–17.17, median 0.30 [DL]. |
| `cpu_avg` | batch_instance | CPU used | 100 = 1 core | Observed | Average | Instance | 30,416 null [DL-HEAD] |
| `cpu_max` | batch_instance | CPU used | 100 = 1 core | Observed | **Peak** | Instance | 30,416 null [DL-HEAD] |
| `mem_avg` | batch_instance | Memory used | Normalized | Observed | Average | Instance | 295,680 null [DL-HEAD] |
| `mem_max` | batch_instance | Memory used | Normalized, [0, 100] | Observed | **Peak** | Instance | 397,419 null (10.5%) [DL-HEAD] |
| GPU | — | — | — | — | — | — | **Not in the trace** |

- **Invalid markers:** normalized values use −1 and 101 as invalid markers [DOC]. None were found in `plan_mem` [DL].
- **Normalization uncertainty:** whether `plan_mem` and `mem_max` share one normalization **requires confirmation**. Their documented descriptions differ slightly, and median `mem_max` is 0.05 vs median `plan_mem` 0.30.

### Status and quality

| Item | Finding | Evidence |
|---|---|---|
| Task status | Terminated 14,059,143 (98.3%); Running 129,354; Failed 83,276; Waiting 23,958 | [DL] |
| Instance status | Terminated, Running, Failed, Interrupted (215) | [DL-HEAD] |
| Retries | `total_seq_no > 1` in 0.06% of head rows | [DL-HEAD] |
| Peak below average | `mem_max < mem_avg` in **26,930** rows; `cpu_max < cpu_avg` in **1,345** rows | [DL-HEAD] |
| Missing memory peak | 10.5% of `mem_max` null in the head | [DL-HEAD] |
| Invalid time order | 54,580 tasks | [DL] |
| Candidate exclusions | Non-Terminated rows; invalid end times; −1 / 101 markers. These are dataset-specific (design question). | — |
| Partial-head limitation | Distributions across the full `batch_instance` (20 GB) are **not verified** | — |

---

## 5. Cross-Dataset Comparison Table

This table summarizes inspection findings only.

| Aspect | Google subset 2019 | Alibaba GPU v2020 | Alibaba v2018 |
|---|---|---|---|
| Recurrence key | **Partially supported**: constructed `user‖collection_logical_name` (inferred; 0 missing) | **Supported**: official `group` (99.86% coverage) | **Unsupported** |
| Occurrence definition | **Supported**: `recurrence_key‖execution_start_time_us` | **Requires adapter logic**: job submission within `group`; evaluation unit is a design question | **Unsupported** (instance rows only) |
| Next-occurrence support | **Supported**, with caveats (targets cross split boundaries) | **Supported** for memory peak and CPU average; requires adapter logic | **Unsupported** |
| CPU request | **Supported** (`requested_cpu_ncu`) | **Supported** (`plan_cpu`, per task) | **Supported** (`plan_cpu`, per task) |
| CPU observed value | **Supported** | **Supported** (`cpu_usage`) | **Supported** (`cpu_avg`, `cpu_max`) |
| CPU semantics | Peak: aligned-window sum, then maximum | **Lifetime average only, no peak** | Per-instance average and peak |
| Memory request | **Supported** (normalized) | **Supported** (`plan_mem`, GB) | **Supported** (normalized) |
| Memory observed value | **Supported** | **Supported** (`max_mem`, `avg_mem`) | **Supported** (`mem_avg`, `mem_max`) |
| Memory semantics | Peak: aligned-window sum, then maximum | Per-worker lifetime maximum, GB | Per-instance average and maximum, normalized |
| GPU support | **Unsupported** | **Partially supported**: request, average utilization, maximum GPU memory; no GPU-memory request | **Unsupported** |
| Timestamp units | µs from trace start | s, constant offset | s from trace start |
| Status | **Supported** (`event`, `failed`) | **Supported** (job, task, instance `status`) | **Supported** (task, instance `status`) |
| Missingness | Low (774 requests; 60 occurrence memory peaks) | High in instances and sensors (40.2% of instances, 79.3% of jobs have sensors) | Moderate (10.5% `mem_max` null in head; full table not verified) |
| Chronological split feasibility | **Supported** (31 days, implemented) | **Supported** (68.9 days) | **Partially supported** (8.86 days) |
| Supported record levels | Occurrence, execution | Occurrence, instance | Instance |
| Unresolved questions | Status filtering policy | Evaluation unit, aggregation, filtering rules, occurrence time, large groups, CPU unit | Demonstration scope; memory normalization |

---

## 6. Verified Canonical Contract Requirements

These are **requirements identified by the inspection, not an implemented schema.** Each is backed by at least one dataset in section 4.

### 6.1 Required common fields

| Field | Why it is required | Google source | Alibaba GPU v2020 source | Alibaba v2018 source |
|---|---|---|---|---|
| `dataset_id` | Separates datasets; no merged training | Constant | Constant | Constant |
| `source_version` | Records the trace version and sample identity (e.g. Kaggle sample vs full; v2020 table checksums). **Missing from PR #70's schema.** | `clusterdata2019_kaggle` | `gpu-v2020` | `v2018` |
| `record_level` | Units differ: occurrence vs instance | `occurrence` | `occurrence` (job) plus `instance` (worker) | `instance` |
| `workload_id` / `job_id` (plus task and instance identity) | Source job identity | `collection_id` | `job_name` (= `inst_id`) | `job_name` |
| `execution_id` | Sub-unit identity | `execution_id` | Worker or task (**design question**) | `job_name|task_name` |
| `recurrence_key` | History and targets. **Nullable**, gated by capability. | Constructed key | `group` | Null |
| `recurrence_key_origin` | Distinguishes `constructed` / `official` / `none` | `constructed` | `official` | `none` |
| `occurrence_key` | Unit for targets | `recurrence_key‖start` | `group‖job_name` or `group‖start` (**design question**) | Null |
| `start_time_us`, `end_time_us` | History rule `end ≤ t`, ordering, splits | µs | s × 10⁶ | s × 10⁶ |
| `time_basis` | Time origin | `trace_relative` | `trace_relative` (constant offset; time of day preserved) | `trace_relative` |
| `status_raw`, `status_normalized` | Filtering. The raw vocabulary differs by dataset; normalized values could be `success` / `failed` / `incomplete` / `unknown`. | `event` | `status` | `status` |
| `requested_cpu`, `requested_memory` + `_unit` | Request baseline | NCU / normalized | Percent of vCPU / GB | Percent of core / normalized |
| `observed_*` resource fields + `_unit` | Actuals | Section 4.1 | Section 4.2 | Section 4.3 |
| `validity_status` | Partial vs valid rows | — | — | — |
| `adapter_name`, `adapter_version`, source file paths and checksums | Adapter and source provenance | — | — | — |

### 6.2 Optional fields

| Field | Present in |
|---|---|
| `requested_gpu` (+ unit) | Alibaba GPU v2020 (`plan_gpu`) |
| `observed_gpu_avg`, `peak_gpu_memory`, `avg_gpu_memory` | Alibaba GPU v2020 |
| `gpu_type` | Alibaba GPU v2020 |
| `peak_cpu` | Google, Alibaba v2018 (**null** for Alibaba GPU v2020) |
| `avg_cpu` | All three |
| `peak_memory` | All three (Alibaba GPU v2020 per worker) |
| `avg_memory` | All three |
| **`resource_semantics`** per field, e.g. `cpu_observed_semantics ∈ {window_peak_sum, lifetime_avg, instance_max}` | Needed because Alibaba GPU v2020 CPU is an average while Google CPU is a summed peak |
| **`aggregation_method`** per occurrence value, e.g. `aligned_window_sum_max`, `sum_of_worker_max_upper_bound`, `max_of_worker_max` | Needed because Google sums across executions while Alibaba GPU v2020 has no time-aligned per-worker series |
| Lifecycle: `submit_time_us`, `launch_time_us`, `wait_time_sec` | Alibaba GPU v2020 (job vs task times) |
| Retry: `retry_seq_no`, `total_seq_no` | Alibaba v2018 (`seq_no`) |
| `machine_id`, machine capacity (`cap_cpu`, `cap_mem`, `cap_gpu`) | All three; capacity for Alibaba GPU v2020 validity checks |
| `task_role` (`ps`, `worker`, `evaluator`, …) | Alibaba GPU v2020 |
| `workload_tag` | Alibaba GPU v2020 (`workload`, 9.7%) |
| `execution_count` per occurrence | Google, Alibaba GPU v2020 |
| `has_sensor` / `telemetry_coverage` | Alibaba GPU v2020 (40.2% instance coverage) |

### 6.3 Capability metadata

PR #70's `DatasetCapabilities` has 10 boolean flags. The inspection shows the capability metadata must also represent:
- recurrence support and recurrence origin;
- next-occurrence target support;
- CPU and memory requests;
- CPU peak and CPU average;
- memory peak and memory average;
- GPU signals;
- status;
- units;
- supported record levels;
- evaluation mode;
- any-resource metric validity.

**These fields are identified requirements; they are not implemented.**

| Flag | Google | Alibaba GPU v2020 | Alibaba v2018 |
|---|---|---|---|
| `has_recurrence_key` | true | true | false |
| `recurrence_key_origin` | constructed | official | none |
| `supports_next_occurrence_target` | true | true | false |
| `has_cpu_request` | true | true | true |
| `has_memory_request` | true | true | true |
| `has_cpu_peak` | true | **false** | true (instance) |
| `has_cpu_average` | true | true | true |
| `has_memory_peak` | true | true | true (instance) |
| `has_memory_average` | true | true | true |
| `has_gpu_signal` | false | true | false |
| `has_status` | true | true | true |
| `cpu_unit` / `memory_unit` | ncu / normalized | pct_vcpu / gb | pct_core / normalized |
| `supported_record_levels` | occurrence, execution | occurrence, instance | instance |
| `evaluation_mode` | full_next_occurrence | next_occurrence_memory_peak_cpu_avg | instance_request_vs_observed |
| `any_resource_metric_valid` | true | **false** | true (instance) |

**Capability by evaluation type (inspection findings)**

| Capability | Google subset 2019 | Alibaba GPU v2020 | Alibaba v2018 |
|---|---|---|---|
| Recurrence-based history | Yes (constructed key) | **Yes (official `group`)** | No |
| Next-occurrence prediction | Yes | **Yes** (memory peak; CPU average) | No |
| CPU peak evaluation | Yes | **No** | Instance level only (current instance, not next occurrence) |
| CPU average-usage evaluation | Possible (`average_cpu_ncu`) but not used | **Yes**, the only CPU signal | Instance level only |
| Memory peak evaluation | Yes | **Yes** (`max_mem`, GB) | Instance level only |
| Request-versus-observed comparison | Yes | Yes (CPU request vs average; memory request vs peak) | Yes, instance level |
| Full resource evaluation (CPU peak + memory peak, next-occurrence) | **Yes** | **No** (CPU peak missing) | **No** |
| Reduced evaluation only | — | Memory full, plus reduced CPU-average evaluation | **Yes** |

**Why unsupported capabilities must not be fabricated**
1. **Wrong conclusions.** Relabeling Alibaba GPU v2020 `cpu_usage`, an average, as a peak would make CPU violation rates look far lower than they are. Averages always understate peaks.
2. **Evaluator artifacts.** If one resource's actual value is null for every row, the shared evaluator yields an `any_resource_violation_pct` of 100% by construction (`metrics.py:68–81`, `evaluator.py:162–218`). Filling the null with 0 would instead create false "no violation" results.
3. **Leakage and invalid targets.** Inventing a recurrence rule for Alibaba v2018 would produce next-occurrence numbers that look comparable to Google's but measure something else.
4. **Schema enforcement depends on truthful flags.** PR #70's `validate_canonical_frame` rejects populated fields that a capability profile marks unsupported. That protection only works if the flags are truthful.

---

## 7. Adapter Design Implications

### 7.1 Per-dataset adapter responsibilities

| Responsibility | Google subset 2019 | Alibaba GPU v2020 | Alibaba v2018 (optional) |
|---|---|---|---|
| Raw loading | One CSV (34 columns); the reference notebooks parse it | Six CSVs (instance 2.0 GB, sensor 1.1 GB uncompressed); columnar or chunked reader | `batch_task` (0.8 GB) plus `batch_instance` (20 GB compressed), needing chunked or streamed reading |
| Headerless parsing | Not needed (header present) | Column names from the README; pass the schema explicitly | Column names from `schema.txt` |
| Joins | Within notebooks (observations → executions → occurrences) | Job ← group; job ← task ← instance ← sensor ← machine spec | Instance ← task plan |
| Field renaming | To canonical names | `plan_*` → `requested_*`; `max_mem` → `peak_memory`; `cpu_usage` → `avg_cpu` (**never** `peak_cpu`) | `plan_*` → `requested_*`; `cpu_max` / `mem_max` → `peak_*` |
| Timestamp normalization | µs, unchanged | s × 10⁶; keep the time-of-day note | s × 10⁶; null `end == 0` and `end < start` |
| Resource-unit tagging | Tag NCU / normalized; no conversion | Tag pct_vcpu and GB. Any CPU conversion to vCPU (÷100) must apply **identically** to requests and actuals. | Tag pct_core and normalized; no cross-dataset conversion |
| Status mapping and flags | Flag FAIL, LOST, EVICT, KILL (policy is a design question; currently none excluded) | Flag non-Terminated jobs; Interrupted, Ready and Waiting instances; workers without sensors; `max_mem > cap_mem` (5,322 rows); duplicate `worker_name` rows | Flag non-Terminated rows; `mem_max < mem_avg`; `cpu_max < cpu_avg`; invalid ends |
| Recurrence construction or preservation | Construct `user‖collection_logical_name`, provenance `constructed` | **Preserve** `group`, provenance `official`; null for the 1,530 jobs without one (1,460 accepted) | Leave null |
| Occurrence construction | `recurrence_key‖execution_start_time_us` | One per job, ordered by job `start_time` within `group` | None |
| Resource aggregation | Aligned-window sum across executions, then maximum (existing notebook 03 logic) | Worker → job or role aggregation (**design question**). A plain sum of per-worker maxima is only an upper bound. | None at instance level |
| Missing-value preservation | Keep nulls (774 requests, 60 memory peaks) | Keep `peak_cpu` null for every row; keep `max_mem` null where there is no sensor | Keep nulls (10.5% `mem_max` in head) |
| Capability metadata | Profile and provenance (section 6) | Profile with `has_cpu_peak=false` and `any_resource_metric_valid=false` | Profile with `has_recurrence_key=false` |
| Validation | Shared validators (PR #70) | Shared validators, plus join coverage, unit tags and capacity bounds | Shared validators |
| Provenance | Source version (Kaggle sample) | Source version and table checksums | Source version; full vs head download |

### 7.2 Adapter logic versus shared TraceAdvisor modules

#### Dataset-specific adapter logic

- raw file format and file layout, including headerless parsing;
- joins across source tables;
- timestamp conversion;
- unit conversion and unit tagging;
- status vocabulary mapping and exclusion flags;
- recurrence handling: construction (Google) or preservation (Alibaba GPU v2020);
- occurrence construction: Google episodes; Alibaba GPU v2020 job assembly;
- resource aggregation from executions or workers to occurrences;
- dataset-specific quality checks (e.g. `max_mem > cap_mem`);
- provenance: source version and checksums.

#### Shared TraceAdvisor logic

- canonical validation (`validate_canonical_frame`, `validate_adapter_output`, `validate_evaluator_view`);
- capability registry and capability-gated validation;
- point-in-time history over canonical occurrences (`end ≤ t`);
- next-occurrence targets (`shift(-1)` within `recurrence_key`), only where recurrence is supported;
- chronological splitting (`split_utils.chronological_split`);
- Request/Mean/P90/P95/P99 baselines and validation-only selection;
- ML and Hybrid policies, trained **per dataset** only;
- evaluation and metrics, with a reporting rule that suppresses any-resource metrics when the capability says so;
- artifact validation.

**Warning:** Google's episode reconstruction and aligned-window summing are **Google-specific**. They must not become shared logic, and they must not automatically be applied to Alibaba.

---

## 8. Decisions Emerging from the Inspection

This section records the integration direction suggested by the inspection evidence. It describes intended dataset roles, **not implementation status**.

| Dataset | Decision | Pipeline scope | Reason |
|---|---|---|---|
| Google subset 2019 | **Retain** | Existing reference pipeline | Current project baseline. Its open issues (Google Subset Pipeline Analysis report, findings F1–F8: targets crossing splits, abnormal events included, machine duplication) stay tracked separately. |
| Alibaba GPU v2020 | **Retain** | Full second-dataset integration | Official `group` recurrence (99.86% coverage; 13,551 groups with ≥ 5 Terminated, sensor-covered jobs); memory peak in GB comparable to the GB request. CPU is average-only and must be labeled so. |
| Alibaba v2018 | **Optional** | Reduced adapter demonstration | A useful integration case (adapter on PR #70; instance-level CPU and memory request vs peak), but no recurrence and an 8.86-day span |
| Azure | **Defer** | No implementation now | Outside the current fixed scope |

---

## 9. Open Questions Identified During Inspection

The questions in this section record uncertainties identified during the inspection process. They explain why the canonical schema and adapter framework require explicit design decisions. They are retained for traceability and should not be interpreted as additional dataset-selection options.

**Question categories**

| Category | Meaning |
|---|---|
| Answered by inspection | The evidence settles it |
| Design decision | Requires an explicit project choice |
| Data verification | Needs further checking of data or documentation |
| Alibaba 2018 only | Relevant only to the optional Alibaba v2018 demonstration |
| Repository or data management | Concerns paths, storage or documentation in the repository |

No question in this list is relevant only to deferred Azure work.

| # | Question | Category | Status and evidence |
|---|---|---|---|
| 1 | Is Alibaba GPU v2020 `group` coverage sufficient? | Answered by inspection | **Yes.** 99.86% of jobs [DL]. |
| 2 | How many groups have repeated jobs? | Answered by inspection | 43,060 groups with ≥ 2 jobs, covering 74.0% of jobs [DL] |
| 3 | How many groups have enough occurrences for history features? | Answered by inspection (for one definition); the threshold is a design decision | 13,551 groups (392,590 jobs) with ≥ 5 Terminated, sensor-covered jobs; 9,531 with ≥ 10 [DL]. The `min_runs` threshold remains a pipeline decision. |
| 4 | Are `max_mem` and `plan_mem` directly comparable? | Answered by inspection; the invalid-value rule is a design decision | **Documented yes (both GB)** [DOC]. Data consistent (median ratio 0.196) [DL]. 5,322 `max_mem > cap_mem` rows show some values are invalid, so a rule is needed. |
| 5 | Is `cpu_usage` definitely a lifetime average? | Answered by inspection (documentation) | **Documented yes** ("taking the average of all data in the instance's lifetime") [DOC]. Cannot be checked further from the data, because no time series is released. |
| 6 | **Evaluation unit for Alibaba GPU v2020:** is the occurrence value per job (aggregated over workers) or per task role (per worker, matching the inherited plan)? | Design decision | **Open.** Determines `record_level`, `occurrence_key` and the aggregation rule. 19.3% of jobs have more than one worker. |
| 7 | **Worker → job aggregation:** with no per-worker time series, a job's memory "peak" can only be Σ `max_mem` (an upper bound) or a per-role maximum. Which is used, and how is it labeled? | Design decision | **Open.** Requires an `aggregation_method` field in the schema. |
| 8 | Exact filtering rules (Alibaba GPU v2020): <br>• Terminated-only for targets? For history? <br>• Exclude workers without sensors? <br>• Exclude `max_mem > cap_mem`? <br>• How to treat the 45,689 duplicate `worker_name` rows and the 331,057 null `worker_name` rows? | Design decision | **Open** [DL] |
| 9 | Exact filtering rules (Google): keep or exclude FAIL, LOST, EVICT and KILL? | Design decision | **Open** (Google Subset Pipeline Analysis report, finding F7). Must be decided per dataset, not shared. |
| 10 | Occurrence time for Alibaba GPU v2020: job submission (`job.start_time`) or first task launch? | Design decision | **Open.** Submission matches the pre-execution decision point [DOC]. |
| 11 | Large-group handling: one group has 22,641 jobs and the 99th percentile is 61. Cap, weight or leave as is? | Design decision | **Open** [DL] |
| 12 | CPU unit for Alibaba GPU v2020 in the canonical layer: keep pct_vcpu or convert to vCPU? | Design decision | **Open.** Either works if request and actual match (`validate_evaluator_view`). |
| 13 | Which Alibaba v2018 capabilities will be demonstrated if it is included? Proposed: instance-level CPU and memory request-vs-peak through the canonical contract only, with no history or targets. | Alibaba 2018 only (scope) | **Open** |
| 14 | Alibaba v2018: do `plan_mem` and `mem_max` share one normalization? | Alibaba 2018 only; data verification | **Requires confirmation.** Documentation wording differs; medians 0.30 vs 0.05. |
| 15 | Should PR #70's `DatasetCapabilities` be extended (section 6.3 flags) or replaced, and should `source_version`, `recurrence_key_origin` and the semantics fields become required? | Design decision | **Open** |
| 16 | Where will Alibaba raw data live (e.g. `data/raw/alibaba_gpu_v2020/`), and how will downloads and checksums be documented in the repository? | Repository or data management | **Open** |

Data-verification items also recorded in section 4, all **requires confirmation**:
- why many Alibaba GPU v2020 workers lack sensor rows;
- the cause of extra instance rows beyond `inst_num`;
- how the Google Kaggle sample was drawn;
- full-table Alibaba v2018 instance distributions.

---

## 10. What the Inspection Enables Next

The inspection identifies:
- the **canonical fields** required across datasets (section 6.1) and the optional fields (section 6.2);
- the **resource semantics** each dataset actually provides, including which values are peaks and which are averages (section 4);
- the **aggregation requirements** created by per-task plans and per-worker usage in Alibaba GPU v2020, and by aligned-window summing in Google (sections 4.2, 6.2 and 7.1);
- the **dataset capabilities** that the capability metadata must express (section 6.3);
- the **adapter responsibilities** and the boundary between adapter logic and shared modules (section 7);
- the **validation requirements**: units, nulls, capability gating, join coverage, capacity bounds and provenance (sections 6 and 7);
- the **remaining design questions** (section 9).

**This inspection document does not implement the schema or the adapter framework.**

**Next documentation steps**
1. **Canonical workload schema.** The schema is documented in the existing `docs/design/canonical_workload_schema.md` (PR #70, schema v0.1.0), which should be revised rather than duplicated. Three design questions change the shape of the schema and need explicit decisions first:
   - the evaluation unit for Alibaba GPU v2020 (question 6);
   - the worker → job aggregation method and its labeling (question 7);
   - whether to extend or replace PR #70's capability model (question 15).
2. **Adapter framework.** The adapter framework should be documented **after** the canonical workload schema, in the existing `docs/design/adapter_framework.md`, because its interface depends on the canonical contract. It also depends on whether `BaseDatasetAdapter` gains a multi-table preparation step and chunked loading, which the Alibaba GPU v2020 and Alibaba v2018 table sizes in section 3.5 require.
