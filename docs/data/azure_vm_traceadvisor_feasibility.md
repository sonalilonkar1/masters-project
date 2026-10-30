# Azure VM Trace — TraceAdvisor Inclusion Feasibility

**Question:** Should the Azure VM workload dataset be included in TraceAdvisor alongside the Google subset and the Alibaba datasets? If so, in what role?

**Short answer:** Include Azure **later**, after Alibaba GPU v2020. Its role would be a **CPU-only, non-recurrence evaluation**, and secondarily a **portability demonstration** of the adapter architecture. It is **not** a candidate for a second full CPU-and-memory, next-occurrence TraceAdvisor pipeline.

**Scope:** Analysis only. No source files, notebooks, schemas or configurations were modified. This report is the only file created in the repository.

---

## 0. Evidence used and how it is labeled

| Label | Meaning |
|---|---|
| **[DOC]** | Official Azure documentation in `github.com/Azure/AzurePublicDataset` (master): `README.md`, `AzurePublicDatasetV1.md`, `AzurePublicDatasetV2.md`, `AzurePublicDatasetLinksV2.txt`, the release asset `schema.csv`, the official analysis notebook `analysis/Azure 2019 Public Dataset V2 - Trace Analysis.ipynb`, and the official whole-workload summary files `azure2019_data_{category,cores,memory,lifetime,deployment,cpu}.txt`. |
| **[REPO]** | The TraceAdvisor repository: `main` at `91470a3`, and the unmerged branch `origin/feature/external-dataset-canonical-pipeline` (PR #70, head `69f3a42`). |
| **[HEAD]** | A partial byte-range download of the first compressed bytes of the raw files, stored only in the session scratchpad and not in the repository: V2 `vmtable.csv.gz` (first 18,283 rows), V1 `vmtable.csv.gz` (first 18,410 rows), the first rows of V2 CPU-readings file 1 of 195, and the complete small V2 `deployments` (~33.2K rows) and `subscriptions` (6,687 rows) tables. **Head rows are not a random sample.** For example, the `Unknown` VM category is 91% of the V2 head but only 6% of the whole workload [DOC]. Head results show schema and encoding only, not distributions. |
| **[NEEDS DATA]** | A conclusion that cannot be settled until the full raw data is downloaded and inspected (see §8). |

Files read in the repository:
- `src/adapters/azure_vm.py`, `src/adapters/base.py`, `src/adapters/validation.py`, `src/canonical/schema.py`, `config/dataset_capabilities.json`, `tests/test_azure_vm_adapter.py`, `scripts/build_external_canonical_samples.py`, `docs/data/old_dataset_semantics_alibaba2018_azure.md` (formerly `dataset_semantics_study_FINAL.md`) and `docs/data/traceadvisor_external_dataset_capability_matrix.csv`, all on PR #70.
- `src/evaluation/metrics.py` and `src/evaluation/evaluator.py`, the shared evaluator on `main`.
- `notebooks/resource-central/resource_central.ipynb`, `docs/baseline_experiments/resource-central/resource-central_experiment_pipeline.md` and `reports/eval/resource-central/tables/resource_central_baseline_metadata.csv`, the existing Azure work on `main`.
- `docs/data/alibaba_dataset_selection_feasibility.md` and `docs/data/google_subset_pipeline_analysis.md`, the previous analyses (uncommitted).

---

## 1. Dataset identity and source

### 1.1 Which Azure trace is being considered

The repository refers to the Azure VM dataset as the **Azure Public Dataset V2 (2019 VM trace)**:
- PR #70 names the adapter and capability profile `azure_public_vm_v2`.
- The semantics study is titled "Azure 2019 Public Dataset V2".
- The adapter docstring reads "Azure 2019 Public Dataset V2 adapter".

**Critical finding: the data actually used in the repository is the 2017 V1 trace, not V2.** [REPO + HEAD, confirmed]

| Evidence | V1 (2017) | V2 (2019) | PR #70 sample (`old_dataset_semantics_alibaba2018_azure.md` §3.1–3.3) |
|---|---|---|---|
| Distinct core-count values (head) | `1, 2, 4, 8` | `2, 4, 8, 24, >24` | `1, 2, 4, 8` |
| Distinct memory values (head) | `0.75, 1.75, 3.5, 4, 7, 14, 28, 56` | `2, 4, 8, 32, 64, >64` | `0.75, 1.75, 3.50, 4.00, 7.00, 14.00, 28.00, 56.00` |
| First 10,001 rows: subscriptions / deployments | **93 / 668** | 1,065 / 4,154 | **93 / 668** |
| First 10,001 rows: mean `max_cpu` / mean `avg_cpu` | **85.735 / 16.884** | 55.482 / 15.342 | **85.735045 / 16.883676** |
| CPU-reading file count | 125 | 195 | — |

- The PR #70 sample statistics match the first 10,001 rows of the **V1** `vmtable` exactly.
- Separately, the Resource Central notebook on `main` loads `vm_cpu_readings-file-1-of-125.csv.gz`. Only V1 has 125 CPU files, and its companion document says "We use the Azure 2017 VM workload trace". Its data directory is named `2021Dataset`, which describes neither version.

**Consequence:** Every Azure claim in PR #70 was checked against 2017 data, including the bucket values, the "allocated vCPU" mapping and the unit labels. V2 uses a **different encoding**: range buckets with open-ended top buckets `>24` and `>64`. The team must decide explicitly which version is "the Azure dataset" before any adapter work continues (§8, check A1).

### 1.2 Official source and characteristics [DOC]

| Property | V2 (2019), the intended target | V1 (2017), the data actually used so far |
|---|---|---|
| Source | `github.com/Azure/AzurePublicDataset`, `AzurePublicDatasetV2.md`; files are GitHub Release assets under `dataset-v2/` | Same repository, `AzurePublicDatasetV1.md`, `dataset-v1/` |
| What it is | "A representative subset of the first-party Azure VM workload in one geographical region" | Same |
| Collection period | 30 consecutive days in 2019. **The calendar month is not documented.** | 30 consecutive days in 2017 |
| Size | 235 GB raw, 156 GB compressed, 198 files | 117 GB raw, 78.5 GB compressed, 128 files |
| VMs / subscriptions | 2,695,548 / 6,687 | 2,013,767 / 5,958 |
| CPU readings | 1,942,780,023, every 5 minutes | 1,246,539,221, every 5 minutes |
| Tables | `vmtable` (437 MB compressed), `vm_cpu_readings` (195 files, ~856 MB compressed each), `deployments`, `subscriptions`, and bucket-definition files listed in `schema.csv` | `vmtable`, `vm_cpu_readings` (125 files), `deployments`, `subscriptions` |
| Memory telemetry | **None.** Only a memory-size bucket per VM. | **None.** Only a memory size per VM. |
| Time encoding | Seconds from trace start (0). Readings every 300 s. | Same |
| Associated paper | Resource Central (SOSP '17) | Resource Central (SOSP '17) |
| License | CC-BY. The repository-wide `LICENSE` is cited by the Packing 2020 page; V2's page does not restate it ([NEEDS DATA] to confirm). | Same |

**V2 `vmtable` schema** [DOC: `schema.csv`, confirmed by HEAD]:

`vm id`, `subscription id`, `deployment id`, `timestamp vm created`, `timestamp vm deleted`, `max cpu`, `avg cpu`, `p95 max cpu`, `vm category`, `vm virtual core count bucket` (STRING), `vm memory (gb) bucket` (STRING)

**V2 CPU-readings schema:** `timestamp`, `vm id`, `min cpu`, `max cpu`, `avg cpu`. The HEAD confirms this column order; the first rows have `timestamp = 0`.

### 1.3 Workload type

This is a **general-purpose IaaS cloud VM workload**: Microsoft's own first-party services running on Azure VMs. It is not batch jobs, not an AI/GPU workload and not serverless.

Each VM carries a category label. In the whole 2019 workload [DOC `azure2019_data_category.txt`], the shares are:
- `Delay-insensitive`: 51%
- `Interactive`: 43%
- `Unknown`: 6%

V1 spells the third label `Unkown` in the raw data [HEAD].

The workload mixes very short and very long VM lifetimes. For the whole 2019 workload [DOC `azure2019_data_lifetime.txt`, hours]:
- 63.6% of VMs live at most 1 hour.
- About 8% live longer than 100 hours (the cumulative distribution reaches 91.8% at the 100-hour bucket).

Deployment sizes [DOC `azure2019_data_deployment.txt`]: 47% of deployments contain exactly **one** VM, and 79% contain at most 5.

Other Azure traces in the same repository are not VM resource traces and are out of scope:
- Functions 2019/2021 (serverless invocations)
- Packing 2020 (VM *requests* with no usage)
- LLM inference 2023/2024 and LMM 2025 (token counts)
- VM Noise 2024 (benchmarks on 12 long-lived plus 43,617 short-lived VMs of two SKUs)
- Copilot 2026 (agent sessions)

Packing 2020 deserves one note: it has requested resources (core and memory in fractional machine units) and lifetimes, but **no observed usage**. It therefore cannot support actual-versus-recommended evaluation.

### 1.4 Age relative to the other datasets

| Dataset | Collected |
|---|---|
| Azure V1 | 2017 |
| Alibaba v2018 | 2018 |
| Google ClusterData 2019 (source of the Google subset) | May 2019 |
| **Azure V2** | **2019 (month undocumented)** |
| Alibaba GPU v2020 | July–August 2020 |

Azure V2 is **contemporaneous with** the Google subset and **older than** Alibaba GPU v2020. Azure V1, the version actually used in the repository so far, is the oldest of all. Azure adds no recency advantage.

---

## 2. TraceAdvisor semantic requirements

### 2.1 Requirements table

| Requirement | Available? | Azure field/table | Confidence | Consequence |
|---|---|---|---|---|
| Workload or application identity | **Partial** | `subscription id` (tenant), `deployment id` (VMs deployed together, using a definition that is "different than Azure" [DOC]) | High [DOC] | There is a grouping key but no application or service name. Neither field is documented as a workload identity. |
| Recurrence identity or a defensible workload-family key | **No** | None documented. Possible proxies: `subscription id`, `deployment id`, subscription plus deployment shape. | High that none is documented [DOC]. Whether a proxy is defensible is [NEEDS DATA]. | A next-occurrence target would need an invented rule (§3.2). |
| Discrete workload occurrences | **No (only VMs)** | One `vmtable` row per VM | High | A VM is a resource container with a lifetime, not a run of a job. |
| Execution start and end times | **Yes, for the VM** | `timestamp vm created`, `timestamp vm deleted` (seconds from trace start) | High [DOC]. Censoring at the trace edges is [NEEDS DATA]. | This is VM lifetime, not job execution time. In the HEAD, 1,014 of 18,283 V2 rows have create = delete; the official notebook treats these as 300 s. |
| Request or allocated CPU | **Allocated, bucketed** | `vm virtual core count bucket`: `2, 4, 8, 24, >24` in V2 (exact core counts in V1) | High on existence. **Whether a bucket label means an exact value or a range is [NEEDS DATA]** (bucket-definition file). | This is the VM size the tenant chose, not a per-workload request. The top bucket is open-ended. |
| Request or allocated memory | **Allocated, bucketed** | `vm memory (gb) bucket`: `2, 4, 8, 32, 64, >64` in V2 (exact GB in V1) | Same as CPU | The jump from 8 to 32 strongly suggests labels are range bounds (V2 HEAD shows 4-core VMs in bucket `32`). The value is an inexact capacity. |
| Observed CPU usage or CPU peak | **Yes** | Per VM over its lifetime: `max cpu`, `avg cpu`, `p95 max cpu`. Every 5 minutes: `min cpu`, `max cpu`, `avg cpu`. | High [DOC]. The utilization basis (percent of the VM's own cores) is implied by Resource Central but not stated on the V2 page. | This is the strongest part of the dataset: true CPU peaks at 5-minute granularity. |
| Observed memory usage or memory peak | **No** | — | High [DOC] | Memory recommendations cannot be evaluated. Memory must remain **unknown**, never zero. |
| Completion/status information | **No** | — | High [DOC] | Failed, evicted or killed VMs cannot be separated from normal ones. Contrast Google's event types and GPU v2020's `status`. |
| Repeated executions suitable for historical profiles | **Within one VM: yes. Across VMs: unproven.** | 5-minute readings of the same `vm id`; multiple VMs per subscription or deployment | Within a VM: high. Across VMs: [NEEDS DATA] | Supports *temporal* history (a VM's own past) and *population* history (a subscription's earlier VMs). Neither is recurrence history. |
| Enough time span for chronological splits | **Yes, with caveats** | 30 days | High | Enough for 70/15/15 by time. Long-lived VMs cross split boundaries, so the split unit must be chosen carefully (§3). |
| Resource units that can be compared consistently | **CPU: only as percent. Memory: no.** | CPU in percent; allocation in core and GB buckets | Medium | `observed_cpu` (percent) and `allocated_cpu` (cores) cannot be compared without multiplying by an inexact bucket value. Recommendations and actuals must stay in the same unit (percent of VM, or cores when the bucket is exact). |

### 2.2 VM, instance, execution, occurrence — the distinction that matters

| Concept | Meaning in Google (reference pipeline) | Meaning in Azure V2 |
|---|---|---|
| **Long-lived VM** | No equivalent. Google tasks run *on* machines. | A VM can live from minutes to all 30 days, running whatever service the tenant deployed, possibly many logical tasks over time. Its resource needs are not tied to "one run". |
| **VM instance** | — | One `vm id` = one VM lifetime from create to delete. This is the closest analogue of a Google *instance*, but it is a **container**, not a unit of work. |
| **Workload execution** | An episode reconstructed from `collection_id‖instance_index` with a 5-minute gap rule, i.e. one run of a job's task. | **Not observable.** Nothing marks when a service inside a VM starts or finishes a unit of work. A VM's lifetime is a provisioning decision, not an execution. |
| **Repeated occurrence** | The same `user‖collection_logical_name` submitted again later. The pipeline reconstructs this, and the identity is the job's logical name. | **Not observable.** A new VM in the same subscription or deployment might run the same service, a different tier, or something unrelated. Nothing in the trace tells which. |

**Therefore `vm id` is an instance identity, not a recurrence identity.** The same holds for `deployment id` and `subscription id`:
- A deployment is a *set of VMs created together*. Deployment sizes are mostly 1 (47%), so it often equals a single VM.
- A subscription is a *billing tenant* that can host many unrelated services.

Using any of the three as `recurrence_key` would be an invented assumption. PR #70's semantics study §3.6 reached the same conclusion: "This is useful workload-pattern evidence, but does not prove repeated deployments are the same recurring workload."

---

## 3. Compatibility with the current TraceAdvisor pipeline

### 3.1 Stage-by-stage classification

Classes:
- **U** — reusable unchanged
- **C** — reusable conceptually, but needs an Azure-specific implementation
- **NA** — not applicable
- **X** — unsupported by Azure

| Stage | Class | Reason |
|---|---|---|
| Ingestion | **C** | Headerless gzip CSVs. `vmtable` must be joined with 195 CPU files (~856 MB compressed each). This needs chunked or streaming ingestion and VM-ID-targeted sampling. PR #70's `prepare_cpu_intervals` exists but loads everything into memory, and its sample is V1. |
| Identity construction | **C** | `subscription → deployment → vm` hierarchy. Encrypted IDs are base64 strings that are consistent across tables [DOC]. A join test is required (§8, A4). |
| Execution reconstruction | **NA** | There is no task-event stream and no episodes to rebuild. The Google gap-based episode logic does not apply. A VM lifetime comes directly from `vmtable`. |
| Occurrence construction | **X** | No discrete workload occurrences exist (§2.2). |
| Recurrence-key construction | **X** | No documented key exists. Any key would be invented. |
| Historical profile creation | **C** | The point-in-time principle (use only data with time ≤ t) carries over. History must be defined as (a) the VM's own earlier 5-minute windows, or (b) earlier **completed** VMs in the same subscription. Neither is the Google per-recurrence profile. |
| Next-occurrence target construction | **X** | No recurrence means no "next". See §3.2. |
| Chronological splitting | **C** | `chronological_split` assumes one timestamp per row. Interval rows split cleanly by `event_time_us`. VM rows must be split by `vm created` or by window time. Long-lived VMs cross boundaries, so splits must be by time window rather than by VM. |
| Request/Mean/P90/P95/P99 baselines | **C (Request: X)** | Mean, P90, P95 and P99 over CPU history are fine. The **Request** baseline has no request to use. An "Allocation" baseline (100% of the VM's cores, i.e. recommend the full size) is the honest substitute and must be named as such. |
| ML feature generation | **C** | Lagged and rolling 5-minute CPU statistics, VM category, size buckets, and subscription history from earlier completed VMs. The lifetime fields `max cpu`, `avg cpu` and `p95 max cpu` **leak** if used for the same VM. PR #70's adapter docstring already flags this. |
| Hybrid recommendations | **C** | The ML-versus-percentile switch logic transfers, but on CPU only. |
| Shared evaluator | **U for CPU, X for memory, with one trap** | `RecommendationEvaluator` is NaN-aware. CPU metrics work unchanged. With memory all-NaN, `any_resource_violation` is 1 when CPU violates and NaN otherwise. `summarize()` then averages over non-NaN rows only, so **`any_resource_violation_pct` is 100% by construction** (`metrics.py:68–81`, `evaluator.py:162–218`). Azure reports must show CPU metrics only and suppress or flag any-resource metrics. |
| Metadata and artifact validation | **C** | `validate_canonical_frame` and `validate_adapter_output` work as they are. The metadata must also record the trace version (V1 or V2), the bucket semantics, the CPU unit basis, the modeling mode and the split unit. |

### 3.2 Can Azure support a legitimate next-occurrence target?

**No.** The Google target is `groupby(recurrence_key).shift(-1)` over occurrences, which needs two things:
1. a key that identifies *the same logical workload*;
2. discrete runs of it.

Azure provides neither (§2.2). Every way of manufacturing one is an invented assumption:

| Invented construction | Why it is invalid |
|---|---|
| `recurrence_key = deployment_id`, next VM in the deployment as the "next occurrence" | VMs in a deployment are created *together*, i.e. concurrently, not in sequence. Most deployments have a single VM. |
| `recurrence_key = subscription_id` | A subscription is a tenant hosting many unrelated services. The "next VM" may be a different service. |
| `subscription‖core bucket‖memory bucket‖category` signature | Same size and category does not mean the same workload. PR #70 found 39.5% of sampled deployments share a signature, but that sample was V1 and the overlap proves nothing about identity. |
| Cutting a long-lived VM into daily windows and calling each window an "occurrence" | A window is a time slice of one continuous run, not a repetition. Calling it a next-occurrence result would overstate what was evaluated. |
| Treating the VM's own lifetime `max cpu` as its "next occurrence" target | This is the current VM's own outcome; it is leakage, not a forecast. |

**What is valid instead.** Each option below must be named for what it is, never "next-occurrence":

| Valid evaluation mode | History | Target | Split | What it measures |
|---|---|---|---|---|
| **A. Within-VM temporal rightsizing (interval replay)** | The VM's own 5-minute readings up to time t | Peak `max cpu` over the next horizon H (e.g. 1 h or 1 day) of the **same** VM | By window time | "Given how this VM behaved so far, what CPU should it be sized at for the next H?" This is the closest honest analogue of TraceAdvisor's question. |
| **B. Cold-start, population-history prediction** | Lifetime summaries of **completed** VMs in the same subscription (deleted ≤ t) | The new VM's lifetime `p95 max cpu` or `max cpu` | By `vm created` | Resource Central-style prediction: "What will a new VM in this subscription need?" This is a tenant-level prior, not recurrence. |
| **C. Allocation-versus-observed (descriptive)** | None | None (no recommendation) | None | How much of the allocated CPU is used: a description of over-provisioning, not a recommender evaluation. |

**Caution about the existing repository result.** The Resource Central notebook on `main` (cell 7) computes per-VM `mean_cpu` and `p95_cpu` from `nrows=100000` of one CPU file.
- The metadata shows `cpu_rows_loaded = 100000`, `n_vms = 100000`, and the printed sample shows `n_samples = 1`.
- So each VM has **one** 5-minute reading. "P95" is that reading's `max cpu`, "mean" is its `avg cpu`, and the reported `bucket_accuracy = 0.8711` compares two statistics of the same 5-minute window.
- This is neither history-based prediction nor a recommendation evaluation. It should not be cited as Azure evidence for TraceAdvisor without being re-run with real per-VM history (mode A or B).

---

## 4. Canonical adapter fit

### 4.1 What exists (PR #70, unmerged)

- **Interface:** `BaseDatasetAdapter.adapt(source: DataFrame) -> AdapterResult(canonical, metadata)`, which calls `to_canonical()` and then validates.
- **Schema:** `RECORD_LEVELS` already includes `"interval"` and `"instance"`. Resource value and unit columns are paired. `validate_canonical_frame` refuses to populate fields the capability profile says are unsupported. `validate_evaluator_view` requires at least one actual/recommended pair per row and matching units.
- **Capability profile `AZURE_VM_CAPABILITIES`:** `supports_cpu=True`, `supports_memory=True`, `supports_request=False`, `supports_recurrence=False`, `supports_targets=False`, `supports_ml=False`, `supports_observed_cpu=True`, `supports_observed_memory=False`, `supports_allocated_cpu=True`, `supports_allocated_memory=True`.
- **`AzureVMAdapter`:** two views, `adapt_vm_table` (`record_level="instance"`) and `adapt_cpu_readings` (`record_level="interval"`, `aggregation_window_sec=300`). Observed and peak memory are always NaN. `recurrence_key` is never set.

### 4.2 Issues found in the current Azure adapter

| # | Finding | Evidence | Status |
|---|---|---|---|
| 1 | Built and tested against **V1** data, but labeled V2 | §1.1 table | **Confirmed** |
| 2 | `pd.to_numeric(vm_core_count_bucket, errors="coerce")` turns V2's `">24"` and `">64"` into NaN, so those rows silently become `partial`. These are the largest VMs. | `azure_vm.py` (`allocated_cpu` / `allocated_memory` lines); V2 HEAD shows `>24` and `>64` values | **Confirmed against the V2 encoding.** Effect size [NEEDS DATA]. |
| 3 | Bucket labels are written as exact values (`allocated_cpu=4`, unit `vcpu`; `allocated_memory=32`, unit `gb`). If buckets are ranges, these overstate precision. | V2 buckets `2,4,8,32,64` | **Suspected.** The bucket-definition file must be checked (§8, A3). |
| 4 | `observed_cpu` and `peak_cpu` are in `percent` while `allocated_cpu` is in `vcpu`. Building `recommended_cpu` in vCPU against `actual_cpu` in percent would be blocked by `validate_evaluator_view` (good), but the conversion rule is not defined anywhere. | `azure_vm.py`; `schema.py` `validate_evaluator_view` | **Confirmed gap** |
| 5 | `supports_memory=True` while `supports_observed_memory=False`. The flag means "memory capacity is known", but a reader may take it as "memory can be evaluated". | `schema.py` `AZURE_VM_CAPABILITIES` | **Confirmed ambiguity** |
| 6 | `adapt_vm_table` does not go through `BaseDatasetAdapter.adapt()`; it calls `validate_adapter_output` itself. Multi-table preparation (`prepare_cpu_intervals`) is also outside the base contract. | `azure_vm.py` | Confirmed. Acceptable, but shows the base interface is single-table. |
| 7 | `test_azure_empty_vm_table_rejected` is defined twice in `tests/test_azure_vm_adapter.py`; the second definition shadows the first. | Test file | Confirmed, harmless |
| 8 | The ingestion script `read_headerless_csv` loads entire files into memory. That is not viable for 195 × ~856 MB compressed CPU files. | `scripts/build_external_canonical_samples.py` | Confirmed for full-scale use |

### 4.3 Proposed Azure V2 canonical mapping

These mappings are proposed only and have not been implemented. **Nothing is fabricated:** where Azure has no source, the field stays null and the capability flag stays false.

| Canonical field | Azure source field | Unit | Transformation | Missing/unsupported behavior |
|---|---|---|---|---|
| `schema_version` | — | — | Constant `0.1.0` | — |
| `dataset_id` | — | — | Constant. Should **name the version**, e.g. `azure_public_vm_v2_2019` vs `azure_public_vm_v1_2017`. | — |
| `record_level` | — | — | `instance` (VM-lifetime view) or `interval` (5-minute view) | — |
| `workload_id` | `deployment id` (or `subscription id`; choose and document) | — | Cast to string | Rows with a null ID are rejected by the schema |
| `execution_id` / `instance_id` | `vm id` | — | Cast to string | — |
| `recurrence_key` | **None** | — | — | **Must stay absent or null.** The schema rejects it under `supports_recurrence=False`. |
| `occurrence_key` | **None** | — | — | Absent |
| `time_basis` | — | — | `trace_relative` | — |
| `start_time_us` / `end_time_us` | `timestamp vm created` / `timestamp vm deleted` | µs from trace start | × 1,000,000. **Do not** rewrite create = delete; keep a flag. | Censoring at trace start or end must be flagged, not imputed ([NEEDS DATA] on how it is encoded) |
| `event_time_us` | readings `timestamp` | µs from trace start | × 1,000,000 | — |
| `aggregation_window_sec` | — | s | Constant 300 | — |
| `requested_cpu` / `requested_memory` | **None** | — | — | **Null.** `supports_request=False`. Allocation must never be relabeled as a request. |
| `allocated_cpu` | `vm virtual core count bucket` | vCPU **bucket** | Parse with the official bucket-definition file. If buckets are ranges, keep `allocated_cpu_bucket_low` / `_high` extension columns, and populate `allocated_cpu` only when the bucket is an exact value. | `>24`: set the lower bound 24 and leave the upper bound null. Never coerce to NaN silently; never pick a guessed number. |
| `allocated_memory` | `vm memory (gb) bucket` | GB **bucket** | Same as CPU | Same; `>64` is open-ended |
| `observed_cpu` | interval `avg cpu` (interval view) or lifetime `avg cpu` (VM view) | percent of the VM's cores (basis to be confirmed) | Numeric; check the range is 0–100 | NaN stays NaN |
| `peak_cpu` | interval `max cpu` (interval view) or lifetime `max cpu` (VM view) | percent | Numeric | NaN stays NaN |
| *extension* `source_p95_max_cpu`, `source_min_cpu` | lifetime `p95 max cpu`, interval `min cpu` | percent | Pass-through | — |
| `observed_memory` / `peak_memory` | **None** | — | — | **Null**, never 0. `supports_observed_memory=False`. |
| `actual_cpu` (evaluator view) | Mode A: max of `max cpu` over the horizon. Mode B: the target VM's lifetime `p95 max cpu` or `max cpu` | percent | Built in an Azure-specific target step, not in the adapter | — |
| `actual_memory` (evaluator view) | **None** | — | — | Null. The evaluator then yields NaN memory metrics; any-resource metrics must be suppressed. |
| *extension* `source_vm_category` | `vm category` | — | Pass-through. Normalize V1's `Unkown` to `Unknown` and keep the raw value. | — |
| `validity_status` | — | — | `valid` / `partial` from completeness | — |

### 4.4 Is the current interface sufficient?

- **For parsing: mostly yes.** `to_canonical` plus validation and capability flags already prevent fabricated fields.
- **For Azure as a TraceAdvisor dataset: no.** The parser alone is not enough. Azure needs:
  1. **A new modeling mode, not just a new parser.** The pipeline's target and history layers assume `occurrence` rows with a `recurrence_key`. Azure needs an `interval` (temporal-horizon) mode and optionally a `population_history` mode, each with its own target builder and leakage rules. These belong in the dataset-specific layer, like Google's reconstruction, not in the shared evaluator.
  2. **More expressive capability flags:**
     - the modeling mode;
     - "allocation is bucketed";
     - the CPU unit basis;
     - `supports_memory_evaluation` as a separate flag from "memory capacity known";
     - the trace version.
  3. **A multi-table, chunked ingestion contract.** This could be an optional `prepare(...)` hook on the base class, plus streaming support.
  4. **CPU-only evaluator reporting.** Either the evaluator already has a CPU-only summary path, or the Azure report layer must drop or annotate the any-resource fields.

**Which evaluation Azure should support:**
- snapshot/interval CPU evaluation (mode A): yes;
- population-history cold-start (mode B): optional;
- allocation-versus-observed CPU description (mode C): yes;
- **recurrence-based targets: no.**

---

## 5. Comparison with the Alibaba alternatives

Facts for the Alibaba datasets come from `docs/data/alibaba_dataset_selection_feasibility.md` (official Alibaba documentation).

| Criterion | **Azure V2 (2019)** | Alibaba v2018 | Alibaba GPU v2020 | Alibaba GPU v2026 (previously analyzed) |
|---|---|---|---|---|
| Workload relevance to TraceAdvisor | **Medium.** Long-lived IaaS VMs, not repeatable jobs. | High: batch DAG jobs plus online containers | **High: recurring ML training and inference jobs** | Medium: hourly pod usage |
| Recurrence support | **None** | None documented; signature-derived only | **Official `group` tag** | None |
| Request-versus-observed evaluation | **No request.** Allocation-versus-observed CPU only. | Yes (`plan_cpu` / `plan_mem` vs `cpu_max` / `mem_max`) | Yes (`plan_cpu` / `plan_mem` vs `cpu_usage` / `max_mem`) | CPU only, relative to request |
| CPU support | **Strong**: lifetime max/avg/p95 plus 5-minute min/max/avg | Strong: `cpu_avg`, `cpu_max` | **Weak**: lifetime average only, no peak | Hourly utilization, no peak |
| Memory support | **None observed.** Bucketed capacity only. | Yes, on a normalized 0–100 scale | **Yes**: `max_mem` in GB, `plan_mem` in GB | No memory request |
| Next-occurrence feasibility | **Not feasible without an invented rule** | Only with an invented rule | **Feasible** (official recurrence) | Not feasible |
| Chronological evaluation feasibility | Yes: 30 days | Weak: 8 days | Yes: ~2 months | Limited |
| Adapter effort | **Medium–high.** The adapter exists but targets V1; the V2 bucket encoding, 156 GB of streaming ingestion and a new modeling mode are all needed. | **Low**: the adapter exists | Medium: new adapter, identifier quirks | High: 352 GB main table |
| Risk of overclaiming | **High** if presented as next-occurrence or CPU+memory. Low if presented as CPU-only temporal evaluation. | High if presented as recurrence | Low to medium (the CPU peak is missing) | High |
| Usefulness for demonstrating the adapter architecture | **High.** It is the most structurally different source: interval telemetry, bucketed allocation, no request, no memory. It exercises the capability flags hardest. | High, and the cheapest | Medium: closest to Google in shape | Low |
| **Classification** | **Separate non-recurrence evaluation (CPU-only), plus a secondary adapter demo** | Adapter-integration demonstration only | **Full second pipeline candidate** | Limited CPU-only study, if ever |

---

## 6. Research and project relevance

**Does Azure add a different perspective, or does it duplicate Alibaba v2018?**

Azure partly duplicates v2018's role. Both are "adapter works, recurrence unsupported" datasets. But Azure adds three things v2018 does not:

1. **A different workload class.** It is IaaS VMs with long and variable lifetimes, sized by the tenant, rather than scheduler-managed batch tasks. This tests whether TraceAdvisor's history-based sizing idea holds outside job schedulers.
2. **Dense time-series telemetry.** 5-minute readings over up to 30 days per VM. This is the only dataset among the four where *temporal* history within one entity is rich, which enables evaluation mode A.
3. **Direct comparability with the most-cited related work.** It is the Resource Central dataset, so the related-work comparison in the thesis can be grounded on the same data.

| Question | Assessment |
|---|---|
| Does it improve the research motivation? | **Somewhat.** It provides real evidence of CPU over-allocation in a major public cloud: whole-workload average CPU is low [DOC `azure2019_data_cpu.txt`]. The motivation is already well supported by Google, though. |
| Does it help demonstrate portability across heterogeneous datasets? | **Yes, strongly.** This is its best contribution. It is the most heterogeneous schema of the four. |
| Does it provide more recent evidence? | **No.** V2 is 2019, the same age as Google; V1 is 2017. |
| Does it support the CPU/memory recommendation claims? | **CPU only.** It cannot support any memory claim. |
| Would adding it increase scope without a valid new result? | **Yes, if** it is attempted as a next-occurrence pipeline, since that result would not be valid. **No, if** it is scoped as a CPU-only temporal evaluation with explicitly different semantics. |

---

## 7. Final recommendation

**Include Azure later**, after Alibaba GPU v2020:
- **Primary role:** a CPU-only, non-recurrence evaluation.
- **Secondary role:** an adapter-portability demonstration.

Do not implement it now. Do not present it as a recurrence or next-occurrence pipeline.

### 7.1 Recommended dataset order

| Order | Dataset | Role |
|---|---|---|
| 1 | **Google subset** | Current reference pipeline. Its known issues must be resolved first (see `google_subset_pipeline_analysis.md`). |
| 2 | **Alibaba v2018** | Adapter-integration demonstration. The cheapest step, because the adapter already exists on PR #70. |
| 3 | **Alibaba GPU v2020** | **Full second TraceAdvisor pipeline** (official recurrence; CPU average and memory peak). |
| 4 | **Azure VM V2** | CPU-only, non-recurrence temporal evaluation, plus a portability demonstration of the most heterogeneous schema. |

### 7.2 By objective

| Objective | Best dataset | Azure's role |
|---|---|---|
| Demonstrating adapter integration | Alibaba v2018 (cheapest). Azure is the strongest heterogeneity test. | **Yes**, once the V1/V2 issue and bucket parsing are fixed |
| Running a valid recurrence/next-occurrence pipeline | Google; then Alibaba GPU v2020 | **None.** Azure cannot do this without invented assumptions. |
| Evaluating request-versus-observed recommendations | Google; GPU v2020; v2018 | **None for "request".** Azure supports **allocation**-versus-observed **CPU** only. |
| Adding a recent or practically relevant workload dataset | GPU v2020 (most recent feasible) | **Practically relevant, but not recent.** It is a real public-cloud VM workload from 2019. |

---

## 8. Required pre-implementation checks

All checks run on the **full** downloaded data, not the head rows.

### A. Version and encoding

1. **Trace version.** Decide V1 (2017) or V2 (2019). If V2, re-download and confirm the distinct `vm virtual core count bucket` values (expected `2, 4, 8, 24, >24`) and `vm memory (gb) bucket` values (expected `2, 4, 8, 32, 64, >64`) over all 2,695,548 rows. Rebuild PR #70's samples from V2.
2. **Row and file counts.** `vmtable` should have 2,695,548 rows and 6,687 subscriptions. CPU readings should total 1,942,780,023 rows across all 195 files. Record any discrepancy.
3. **Bucket semantics.** Obtain `vm_virtual_core_bucket_definition.csv` and `vm_memory_bucket_definition.csv`, which `schema.csv` lists but `AzurePublicDatasetLinksV2.txt` does not link. Determine whether each label is an exact value or a range bound. If the files cannot be found, ask the dataset maintainers (`azurepublicdataset@service.microsoft.com`).
4. **Join integrity.** Check the share of CPU-reading `vm id` values present in `vmtable`, the share of `vmtable` VMs with at least one reading, that `vm id` is unique in `vmtable`, and that each `deployment id` maps to exactly one `subscription id` over the full table.

### B. Timestamps and lifecycle

5. **Coverage.** `timestamp` should be in [0, 2,592,000) s and a multiple of 300. Measure the readings-per-VM distribution and the gaps within a VM (missing 5-minute windows).
6. **Lifecycle consistency.** Readings should fall within [`created`, `deleted` + 300]. Count VMs with readings outside their lifetime.
7. **Censoring.** Count VMs with `created = 0` (alive at trace start) and VMs whose `deleted` equals the last trace timestamp (alive at trace end). Determine how still-running VMs are encoded. Report these separately; never treat a censored lifetime as complete.
8. **Zero-length lifetimes.** Count create = delete (1,014 of 18,283 in the HEAD) and confirm they have at most one reading.

### C. Values and units

9. **CPU range and consistency.** Values should satisfy 0 ≤ `min` ≤ `avg` ≤ `max` ≤ 100 in the readings, and `avg` ≤ `p95 max` ≤ `max` in `vmtable`. Count violations and NaNs.
10. **Lifetime summary vs readings.** For each VM, recompute max of readings `max cpu` and mean of readings `avg cpu`, and compare them with `vmtable` `max cpu` / `avg cpu`. Confirm what `p95 max cpu` is (P95 of the 5-minute maxima). This also validates the unit basis.
11. **CPU unit basis.** Confirm that utilization is a percentage of the VM's own cores, using the Resource Central paper and the maintainers. This determines whether a percentage recommendation can be converted to cores.
12. **Missingness.** Count null or empty values per column, per table. Confirm memory has no observed field anywhere in the V2 release.

### D. Workload repetition and identity (decides whether mode B is viable)

13. **Repeated-VM frequency.** Distribution of VMs per subscription and per deployment over time. Share of subscriptions with ≥ 2 and ≥ 5 **non-overlapping** (sequential) VMs.
14. **Sequential vs concurrent.** Within a deployment, how often are VMs created within 5 minutes of each other (concurrent) versus later (sequential)?
15. **Behavioral stability across VMs.** Within a subscription, plus size and category, measure the spread of lifetime `p95 max cpu` across sequential VMs. If it is no tighter than across random VMs from the same category, population history adds nothing.
16. **Same workload across multiple executions.** Confirm that **no** field identifies one logical workload across VMs. The expected answer is that none does, which is why recurrence stays unsupported. Record this explicitly in the metadata.

### E. Modeling-unit and split checks

17. **Temporal history depth.** For mode A, the share of VMs with ≥ k days of readings (e.g. k = 1, 3, 7), which decides the horizon H and the minimum history.
18. **Boundary crossing.** The share of VMs alive across the train/validation and validation/test cut times. This decides whether evaluation is per window or per VM.
19. **Request/usage relationship.** Distribution of `max cpu` (percent of allocation) by core bucket. This is descriptive only, and must be labeled allocation, not request.
20. **Category balance.** `Interactive` / `Delay-insensitive` / `Unknown` shares in the full data, compared with the official 43 / 51 / 6.

---

## Closing

**Decision:** Azure VM V2 should be included **later**, after Alibaba GPU v2020, as a **CPU-only, non-recurrence evaluation** and a **heterogeneous-schema adapter demonstration**. It must not be built as a next-occurrence pipeline and must not be used for any memory claim.

**Recommended role:** The portability-and-CPU-sizing dataset. It shows that TraceAdvisor's canonical contract, capability flags, history-based baselines and shared CPU evaluation carry over to an IaaS VM workload that has no requests, no recurrence and no memory telemetry, with every unsupported field kept unknown.

**Before or after Alibaba GPU v2020:** **After.** GPU v2020 is the only alternative that supports a valid second next-occurrence pipeline with memory. Azure should not take implementation time away from it.

**Prerequisite discovered in this analysis:** The existing Azure work, both PR #70's adapter samples and the Resource Central notebook, uses **V1 (2017)** data while labeled V2. The Resource Central "P95 vs mean" result uses one 5-minute reading per VM. Both must be corrected or re-labeled before any Azure result is reported.

**Claims we can make if Azure is included:**
- Canonical-schema portability to an interval-telemetry, allocation-bucketed, request-less, memory-less source.
- History-based CPU sizing (Mean/P90/P95/P99/ML/Hybrid) evaluated on future CPU windows of the same VM (mode A).
- Optionally, a subscription-prior cold-start result (mode B), named as such.
- Descriptive CPU over-allocation evidence in a production public-cloud VM workload.

**Claims we cannot make:**
- Next-occurrence prediction, or recurrence, on Azure.
- Any memory recommendation, memory violation or memory waste result.
- Request-versus-observed results. Azure has allocation, not requests.
- Any-resource (CPU or memory) violation rates; on Azure these equal 100% by construction.
- Newer workload evidence than Google 2019.
- Comparability of Azure numbers with Google or Alibaba numbers as if they were the same task, unit or target.
- Any statement about outcome or status (failed, evicted) VMs.

## Sources

- Azure Public Dataset repository: https://github.com/Azure/AzurePublicDataset (`README.md`, `AzurePublicDatasetV1.md`, `AzurePublicDatasetV2.md`, `AzurePublicDatasetLinksV2.txt`, `AzureTracesForPacking2020.md`, `AzureVMNoiseDataset2024.md`, and `analysis/Azure 2019 Public Dataset V2 - Trace Analysis.ipynb`)
- V2 release assets: `schema.csv`, `azure2019_data_*.txt`, and the head bytes of `trace_data_vmtable_vmtable.csv.gz` and `trace_data_vm_cpu_readings_vm_cpu_readings-file-1-of-195.csv.gz`
- V1 release asset: the head bytes of `dataset-v1/trace_data_vmtable_vmtable.csv.gz`
- Cortez et al., "Resource Central: Understanding and Predicting Workloads for Improved Resource Management in Large Cloud Platforms", SOSP 2017
- TraceAdvisor: `main@91470a3` and `origin/feature/external-dataset-canonical-pipeline@69f3a42` (PR #70)
