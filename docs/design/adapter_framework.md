# TraceAdvisor Dataset Adapter Framework

**New Development Issue 3**  
**Canonical contract:** schema version `0.2.0`, frozen design (`docs/design/canonical_workload_schema.md`), implemented in `src/canonical/schema.py` and `src/adapters/`; see [section 2](#2-implementation-status).

**Scope update (29 Oct 2026):** the framework was first planned for Alibaba GPU 2020, Alibaba 2018 and Azure VM. The current project scope is **Google (Kaggle subset) and Alibaba GPU 2020**. Azure VM was dropped from integration because it does not describe recurring jobs with per-job requests and usage (`docs/data/azure_vm_traceadvisor_feasibility.md`). Alibaba 2018 is out of the current scope and may be added later if time permits. Their sections are kept below for reference.

**Decision record:** `docs/design/canonical_schema_design_decisions.md`.

---

## 1. Goal and scope

Separate dataset-specific ingestion and transformation from shared TraceAdvisor logic.

| Dataset | Adapter | Status |
|---|---|---|
| Google Cluster Data 2019 (Kaggle subset) | Thin `GoogleSubsetAdapter` (Task 13) that maps the Google occurrence artifacts; precomputed targets are attached outside the adapter. Until it lands, the contract view in `tests/test_google_canonical_contract.py` does this mapping | In scope: reference pipeline |
| Alibaba GPU 2020 | `AlibabaGPU2020Adapter` (`src/adapters/alibaba_gpu_2020.py`), implemented in Task 3 | In scope: second full integration |
| Alibaba Cluster Trace 2018 | `Alibaba2018Adapter` (`src/adapters/alibaba.py`, updated to 0.2.0) | Out of current scope; may be added if time permits |
| Azure public VM | `AzureVMAdapter` (`src/adapters/azure_vm.py`, 0.1.0) | Dropped from integration; code retained unchanged. Its sample data matches the V1 (2017) release despite the `azure_public_vm_v2` identifier |

---

## 2. Implementation status

The 0.2.0 framework contract described in this document is implemented.

| Area | Status |
|---|---|
| `BaseDatasetAdapter`, `AdapterResult` (`src/adapters/base.py`) | Implemented: single-view `adapt()` and multi-source `adapt_sources()` (`prepare_sources`, `map_prepared_sources`), per-view validation, separate rejected output, provenance and count metadata ([sections 4](#4-adapter-contract)–[6](#6-adapter-metadata-and-provenance)) |
| Validation (`src/adapters/validation.py`) | Implemented: the base checks ([section 7.1](#71-base-checks)) and the 0.2.0 checks ([section 7.2](#72-checks-added-for-020)), plus `validate_rejected_output` and `validate_role_instance_linkage` |
| Source loading | Implemented for Alibaba GPU 2020 in `src/sources/alibaba_gpu_2020.py` (checksum verification, typed headerless loading, column lists, chunked reads) |
| Alibaba GPU 2020 adapter | Implemented (Task 3) |
| Shared target builder | Implemented outside the adapters in `src/features/target_builder.py` (Task 4) |
| Google adapter | Thin adapter (Task 13), see [section 9.1](#91-google-cluster-data-2019-reference) |

---|---|---|
| `BaseDatasetAdapter` (`src/adapters/base.py`) | `adapt(source)` takes one in-memory DataFrame; metadata has name, version, dataset ID, row counts, capabilities; no rejected output | Formal multi-table preparation step; per-view adaptation; a separate rejected output; provenance, exclusion-count and rejection-count metadata ([sections 4](#4-adapter-contract)–[6](#6-adapter-metadata-and-provenance)) |
| `validate_adapter_output` (`src/adapters/validation.py`) | Checks listed in [section 7.1](#71-current-checks-010) | Checks listed in [section 7.2](#72-checks-required-for-020) |
| Multi-table preparation | Adapter-specific only: Alibaba 2018 `prepare_source` / `adapt_tables`; Azure `prepare_cpu_intervals` / `adapt_cpu_readings` | Part of the base contract |
| Loading | `scripts/build_external_canonical_samples.py` reads whole files with `pd.read_csv` | Columnar loading with explicit column lists and schemas ([section 5](#5-source-loading)) |
| Alibaba GPU 2020 adapter | Not implemented | Implement ([section 9.2](#92-alibaba-gpu-2020-required)) |
| Shared target builder | Not implemented for canonical data | Implement outside the adapters ([section 8](#8-adapter-boundaries)) |

Schema code, validators, JSON configuration, examples, adapters and tests move to 0.2.0 in a later implementation change. No further design approval is needed.

---

## 3. Adapter responsibilities

### Adapters own
- raw source column names and file layout, including headerless parsing with explicit schemas;
- source parsing and strict numeric conversion;
- joins across source tables;
- timestamp conversion to microseconds;
- verified unit mapping and unit tagging (no cross-dataset conversion);
- status vocabulary mapping;
- dataset-specific eligibility rules and `exclusion_reason` assignment;
- routing records without a usable canonical time to the rejected output, with `rejection_reason`;
- recurrence construction or preservation (`recurrence_key`, `recurrence_key_origin`);
- occurrence and role construction;
- resource aggregation from instances or executions to the evaluation level, with `resource_scope`, `request_aggregation_method` and `observed_aggregation_method`;
- per-resource validity (`cpu_validity_status`, `memory_validity_status`) and row `validity_status`;
- source-specific ID construction, using the documented literal separators;
- `source_`-prefixed traceability columns;
- dataset-level provenance metadata.

### Adapters do not own
- splits;
- next-occurrence targets (`actual_cpu`, `actual_memory`) and target statuses;
- point-in-time history features;
- historical percentile policies;
- ML predictions;
- Hybrid policy decisions;
- violation/utilization/waste/shortfall metrics;
- evaluator summaries;
- final-test decisions.

Google's precomputed targets are referenced from the existing artifacts, not computed by an adapter.

---

## 4. Adapter contract

Every production adapter subclasses `BaseDatasetAdapter` and provides:
- `capabilities`: the dataset profile;
- `to_canonical(source)`: mapping from one prepared frame to canonical rows;
- optional adapter-specific metadata (`build_metadata` override).

### 4.1 `adapt()`
`BaseDatasetAdapter.adapt()`:
1. rejects a source that is not a DataFrame;
2. copies the source and invokes `to_canonical` on the copy;
3. verifies a DataFrame is returned;
4. verifies the caller-owned source was not mutated;
5. validates the canonical result with `validate_adapter_output`;
6. returns `AdapterResult(canonical, metadata)`.

### 4.2 Multi-table preparation
Datasets with several source tables use an explicit preparation step before `adapt()`:

```
named source tables → prepare_<view>(...) → one prepared frame → adapt() → AdapterResult
```

- Preparation performs joins and checks join coverage. It never fabricates missing values: unmatched rows keep null fields and a match flag.
- Preparation must not mutate its inputs.
- The existing Alibaba 2018 `prepare_source(task_df, instance_df)` and `adapt_tables(...)` follow this pattern and are the reference for it.

### 4.3 One validated frame per view
- An adapter that emits several record levels produces **one canonical frame per view**.
- **Every view passes through `adapt()`** (or an equivalent path that includes the source-mutation check and `validate_adapter_output`).
- Alibaba GPU 2020 has two views:
  - `role_occurrence`: the evaluation rows;
  - `instance`: the audit rows.
- Both Alibaba GPU 2020 views contain only records with usable canonical time values ([section 4.4](#44-rejected-output)).
- **Existing exception, to be retired.** The Azure `adapt_vm_table` builds its frame directly and calls `validate_adapter_output`, skipping `adapt()`'s source-mutation check. This is the pattern not to follow. Azure is deferred, so it is left unchanged for now.

### 4.4 Rejected output
- Records that have no usable canonical time cannot pass `validate_canonical_frame`, which requires an event or start time on every row. They are routed to a **separate rejected output** before the views are adapted.
- The rejected output is separate from the validated canonical frames. It is retained for audit and is **not used by shared downstream processing**: no chronological splitting, history, target construction or evaluation.
- Every rejected record carries a `rejection_reason`.
- The rejected output has minimal checks:
  - identity fields present where possible;
  - `rejection_reason` present;
  - no zero-filling;
  - source traceability preserved.
- Every source row is traceable either to a validated output view or to the rejected output.
- Rejection does not replace exclusion. Ineligible records that have a usable time stay in the validated views with an `exclusion_reason`.

---

## 5. Source loading

- **Columnar loading is required now.** Read only the needed columns, with explicit column names and data types. Headerless official tables use the documented schema.
- **Alibaba GPU 2020:** the full official tables fit in memory once columns are selected. The instance table is 2.0 GB and the sensor table 1.1 GB uncompressed, and the gating checks ran on the full tables this way.
- **Chunked or streamed loading** is needed only for Alibaba 2018 `batch_instance` (20 GB compressed). It is deferred with the optional Alibaba 2018 work.
- Loaders record source file paths and checksums for provenance ([section 6](#6-adapter-metadata-and-provenance)).
- The current `read_headerless_csv` helper loads whole files and is suitable only for samples.

---

## 6. Adapter metadata and provenance

`AdapterResult.metadata` must include:
- adapter name and version;
- `dataset_id`;
- `schema_version`;
- capabilities;
- source and canonical row counts;
- `source_version`;
- source file paths and checksums;
- `telemetry_window`;
- row counts per `validity_status`, per-resource validity status and `exclusion_reason`;
- rejected job, role and instance counts per `rejection_reason`;
- join-coverage counts for multi-table preparation.

Dataset-level provenance belongs in metadata, not on every row. Row-level raw values use `source_`-prefixed columns. Shared code must not depend on `source_` columns.

---

## 7. Validation

No validation helper fills missing values with zero.

### 7.1 Base checks
`validate_adapter_output()` enforces:
- unique canonical columns;
- record uniqueness per record level;
- exactly one expected dataset ID;
- finite resource values when populated;
- then `validate_canonical_frame()`:
  - required columns;
  - record-level, time-basis and validity vocabularies;
  - non-null `workload_id`;
  - a start or event time;
  - end time at or after start;
  - non-negative numeric resource values;
  - a unit from the allowed list whenever a value is populated;
  - capability restrictions (populated unsupported fields are rejected);
  - preservation of null/unsupported values.

**Uniqueness keys:**

| Record level | Key |
|---|---|
| `occurrence` | `occurrence_id` |
| `instance` | `(instance_id, source_seq_no)`, or `instance_id` |
| `execution` | `(execution_id, start_time_us)`, or `execution_id` |
| `interval` | `(instance_id, event_time_us)` |

Rows with a null key are not checked. Record levels without a rule are skipped.

The Alibaba GPU 2020 adapter does not emit `source_seq_no` on instance rows, so its `instance_id` is checked alone under the existing rule. No change to the instance uniqueness rule or to the time rule of `validate_canonical_frame` is needed.

### 7.2 Checks added for 0.2.0
All checks in this table are implemented in `src/adapters/validation.py`.

| Check | Reason |
|---|---|
| Uniqueness rule for `role_occurrence` on `role_key` | Without it, duplicate role rows pass silently |
| Record level is in the profile's `supported_record_levels` | Prevents role rows being emitted as full-workload occurrences |
| `peak_cpu` null when `has_cpu_peak = false` (and the equivalents for average CPU and memory) | The 0.1.0 flag `supports_observed_cpu` gates average and peak together |
| `exclusion_reason` is null or in the profile's `allowed_exclusion_reasons` | Exclusions must use the dataset vocabulary |
| `cpu_validity_status` and `memory_validity_status` use the validity vocabulary | Standard per-resource validity |
| `resource_scope`, `request_aggregation_method`, `observed_aggregation_method` use their vocabularies | Explicit scope and aggregation |
| Units include `percent_of_vcpu` and `percent_of_gpu`; GPU fields are in the resource field list | New Alibaba GPU 2020 units and retained GPU fields |
| `recurrence_key` null exactly when `recurrence_key_origin = none`, or on rows excluded as `no_recurrence_key` | Recurrence is never invented |
| Non-null `workload_id` and `role_key` on every Alibaba GPU 2020 row, including jobs without `group` | The fallback keys must keep validation working |
| Adapter output contains no `split`, `actual_*` or target-status values | Those belong to shared code (Google artifacts excepted) |
| Alibaba GPU 2020 instance rows have `event_time_us` populated, and `workload_id`, `occurrence_id` and `role_key` equal to their parent role row's values | Audit rows must be placeable in time and joinable to their role |
| Rejected output passes its minimal checks ([section 4.4](#44-rejected-output)) | Rejected records stay auditable |

---

## 8. Adapter boundaries

| Stage | Owner |
|---|---|
| Loading, joining, mapping, eligibility, aggregation to the evaluation level | Adapter |
| Canonical validation, capability gating | Shared (`validate_canonical_frame`, `validate_adapter_output`) |
| Routing records without a usable canonical time to the rejected output | Adapter |
| Chronological splits; history (eligible prior occurrences completed at or before the current start); next-occurrence targets within `recurrence_key`; `cpu_target_status` and `memory_target_status`; split isolation. Operates only on eligible evaluation rows; never on instance audit rows or rejected records | Shared target builder |
| Baselines, ML, Hybrid, evaluator, reporting (including any-resource suppression) | Shared |

Google episode reconstruction and aligned-window summing are Google-specific. They must not become shared logic or be applied to other datasets.

---

## 9. Dataset adapters

### 9.1 Google Cluster Data 2019 (reference)
- **Task 13:** a thin `GoogleSubsetAdapter` performs the mapping below through `adapt()`, validated against `GOOGLE_CAPABILITIES`; a helper outside the adapter attaches the precomputed targets. Its output plus targets must equal the contract view (`tests/test_google_canonical_contract.py`). Details: system guide §6.6 and `docs/planning/github_issues/task13_google_subset_thin_adapter.md`.
- No production adapter is needed. The canonical view maps the corrected occurrence artifacts directly:
  - `workload_id` and `recurrence_key` ← `recurrence_key`;
  - `occurrence_id` ← `occurrence_key`;
  - `start_time_us` ← `execution_start_time_us`;
  - requests, peaks and the precomputed next-occurrence targets.
- All rows are `valid`, and `exclusion_reason` stays null.
- Key separator: `||`.
- Google behavior is unchanged by this framework.

### 9.2 Alibaba GPU 2020 (required)
- **Source tables:**
  - `pai_job_table`;
  - `pai_task_table`;
  - `pai_instance_table`;
  - `pai_sensor_table`;
  - `pai_group_tag_table`;
  - `pai_machine_spec`.
- **Preparation:** job ← group; job ← task (plan) ← instance (status, worker) ← sensor (usage) ← machine specification (capacity). Sensor rows join on `job_name`, `task_name` and `worker_name`.
- **Outputs:**
  - a validated `role_occurrence` view (evaluation rows);
  - a validated `instance` view (audit rows, one per instance-table row, so every retry is its own row);
  - a separate rejected output for jobs without a submission time ([section 4.4](#44-rejected-output)).
  - Both validated views contain only records with usable canonical time values.
- **Role identity:** `workload_id = group`, `recurrence_key = group||task_name` (`official_with_role`), `occurrence_id = group||job_name`, `role_key = group||job_name||task_name`.
- **Jobs without `group`:** fallback `workload_id = job_name`, `occurrence_id = job_name`, `role_key = job_name||task_name`, `recurrence_key` null, role-level `exclusion_reason = no_recurrence_key`.
- **Instance identity:**
  - `instance_id = job_name||task_name||inst_name||instance_attempt_index`;
  - `instance_attempt_index` is a deterministic 1-based index within the slot `(job_name, task_name, inst_name)`, ordered by instance start time ascending with null times last, then by `source_row_number`;
  - `source_row_number` is the data-line number in the checksum-verified, decompressed instance file. **The loader must preserve source file order**;
  - additional fields: `instance_slot_key` (`job_name||task_name||inst_name`), `instance_attempt_index`, nullable `worker_id` (from `worker_name`), `source_row_number`, and raw `source_inst_name`, `source_worker_name`, `source_status`, `source_machine`;
  - `worker_name` and nullable timestamps are never placed in the key; the source `inst_id` (job-level) and a source row number alone are never used as the identity;
  - the adapter **must not emit `source_seq_no`** on instance rows, so `instance_id` is the uniqueness key.
- **Instance parent linkage:** instance rows inherit `workload_id`, `recurrence_key`, `occurrence_id` and `role_key` from their parent role row, including the fallback values for jobs without `group`.
- **Time:**
  - role rows: `start_time_us` = job submission; `end_time_us` = job completion, or null (seconds × 10⁶); `launch_time_us` as an extension;
  - instance rows: `event_time_us` = parent job submission, always (`instance_event_time_semantics = parent_job_submission`); `start_time_us` and `end_time_us` = the instance's own times, or null;
  - the parent submission time is a recorded source time used to place the audit row; it is not an invented instance start;
  - task launch time and sensor data are never used as substitutes; timestamps are never inferred, carried forward or fabricated.
- **Rejection:** a job without a submission time is rejected whole (role rows and all instance rows) with `rejection_reason = missing_submission_time`. No orphan instance rows remain in the instance view. Verified volume: 3,663 jobs, 6,942 role rows, 111,219 instance rows, all from `Waiting` jobs and already ineligible, so the eligible population (461,900) is unchanged.
- **Missing `worker_name`:** `worker_id` stays null and is outside the key. `missing_worker_name` is a role-level rule. Instance rows have no independent primary exclusion reason; the evidence remains in `worker_id`, the raw `source_` columns, `source_status` and `role_key`. Status rules can fire first, so the `missing_worker_name` count can be zero.
- **Downstream:** chronological splits operate only on eligible `role_occurrence` rows. Instance audit rows do not receive splits, targets or history features.
- **Resources:**
  - per-instance requests: `plan_cpu` in `percent_of_vcpu`; `plan_mem` in `gb`; `plan_gpu` in `percent_of_gpu`, retained;
  - role values are the maximum over the role's sensor-covered instances (every instance for an eligible role), computed for every accepted role;
  - `observed_cpu` is a lifetime average and is null if any covered worker's CPU is missing;
  - `peak_cpu` is always null;
  - `peak_memory` is from `max_mem`;
  - GPU values are retained and not evaluated;
  - worker peaks are never summed.
- **Eligibility:** the 14 ordered exclusion rules, with one primary reason per row. Ineligible rows are kept.
- **Validity:** missing CPU gives `cpu_validity_status = partial` and doesn't affect memory eligibility.
- **Eligibility, retries:** every retry stays a separate instance row; `multi_attempt_worker` applies when the same non-null `worker_id` appears on more than one instance row of the role.
- **Provenance:** source version `cluster-trace-gpu-v2020`, table checksums, telemetry window (about day 19 to day 68.9), rejected counts by reason.

Field-level definitions are in `canonical_workload_schema.md` §5–§9.

### 9.3 Alibaba Cluster Trace 2018 (optional, out of current scope)
> Not part of the current project scope; may be added later if time permits. The adapter was updated to schema 0.2.0 (PR #92). The notes below describe the earlier 0.1.0 design and are kept for reference.

- Existing `Alibaba2018Adapter` at 0.1.0, unchanged:
  - `prepare_source` joins `batch_task` plan rows onto `batch_instance` rows (many-to-one) and adds `task_metadata_matched`;
  - duplicate `(job_name, task_name)` plan rows are rejected;
  - output is `instance` rows with `workload_id = job_name`, `execution_id = job_name|task_name`, `instance_id = instance_name`;
  - no recurrence key;
  - source-specific units;
  - `cpu_validity_status` and `memory_validity_status` (`partial` when incomplete, `invalid` when the average exceeds the maximum);
  - `source_` columns, including `seq_no`.
- **Known gaps, deferred with the optional work:**
  - validity ignores the source `status`;
  - CPU request and CPU usage use different unit strings;
  - chunked loading is needed for the full `batch_instance`.

### 9.4 Azure public VM (dropped from integration)
> Dropped because the trace does not describe recurring jobs with per-job requests and usage (`docs/data/azure_vm_traceadvisor_feasibility.md`). The adapter code is retained unchanged; a future CPU-only portability check is possible.

- The existing `AzureVMAdapter` is retained unchanged:
  - `adapt_cpu_readings` goes through `adapt()`;
  - `adapt_vm_table` validates directly ([section 4.3](#43-one-validated-frame-per-view));
  - open-ended capacity buckets such as `>24` keep a null value, an open-ended flag and a lower bound;
  - observed memory is never populated.
- The data is V1 (2017). Resolve the V1/V2 identity before any future Azure work.

---

## 10. Reference adapter

`ReferenceOccurrenceAdapter` exists only to exercise the framework contract. It is not a production Google, Alibaba, or Azure adapter.

---

## 11. Issue boundary

- **Issue 3** ends with the shared adapter framework and contract tests: the base contract, multi-table preparation, per-view validation, the rejected output, metadata, and the 0.2.0 validation checks.
- **Issue 4** implements the Alibaba GPU 2020 adapter and canonical integration artifacts (required), and optionally upgrades the Alibaba 2018 adapter. Azure VM integration is deferred.
