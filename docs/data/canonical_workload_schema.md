# Canonical Workload Interface and Schema

**TraceAdvisor 295B — New Development Issue 2**  
**Schema version:** `0.1.0`

## Goal
Provide one common semantic contract for adapters, ML preparation, policy logic, the shared evaluator, API, and UI without forcing Google-specific assumptions onto Alibaba or Azure VM.

## Core rules
- Workload identity and recurrence identity are separate.
- Request, allocation, observation, peak, actual/target, and recommendation are separate semantics.
- CPU and memory support are independent.
- Missing and unsupported values remain null; they are never converted to zero.
- Every populated resource value carries an explicit unit.
- Adapters map source data into canonical fields; they do not calculate historical percentiles, ML predictions, Hybrid decisions, confidence, or evaluator metrics.
- Shared evaluator code consumes canonical names, not raw dataset columns.

## Required row fields
| Field | Meaning |
|---|---|
| `schema_version` | Canonical contract version |
| `dataset_id` | Stable dataset ID |
| `record_level` | `workload`, `occurrence`, `execution`, `instance`, or `interval` |
| `workload_id` | Dataset-valid workload/job/deployment identifier |
| `time_basis` | `unix_epoch`, `trace_relative`, or `unknown` |
| `validity_status` | `valid`, `partial`, `invalid`, `unknown`, or `unsupported` |

Every row must additionally contain `event_time_us` or `start_time_us`.

## Optional identity fields
`execution_id`, `instance_id`, `occurrence_id`, `recurrence_key`.

`recurrence_key` is populated only when recurrence is explicitly available or validated. It stays null for current Alibaba/Azure semantics.

## Time fields
`event_time_us`, `start_time_us`, `end_time_us`, `duration_sec`, `aggregation_window_sec`.

Canonical timestamps use microseconds. Source-relative traces may remain trace-relative as long as `time_basis` records that fact.

## Resource semantic classes
Requested: `requested_cpu`, `requested_memory`  
Allocated: `allocated_cpu`, `allocated_memory`  
Observed: `observed_cpu`, `observed_memory`  
Peak: `peak_cpu`, `peak_memory`  
Evaluator actuals: `actual_cpu`, `actual_memory`  
Recommendations: `recommended_cpu`, `recommended_memory`

Each populated resource field has `<field>_unit`.

Examples of explicit units: `ncu`, `cpu_core`, `vcpu`, `percent`, `normalized`, `gb`.

The schema does not force one universal unit. The evaluator must only compare actual and recommended values expressed in matching units.

## Capability flags
Required coarse flags:
- `supports_cpu`
- `supports_memory`
- `supports_request`
- `supports_recurrence`
- `supports_targets`
- `supports_ml`

Fine-grained flags:
- `supports_observed_cpu`
- `supports_observed_memory`
- `supports_allocated_cpu`
- `supports_allocated_memory`

### Current interpretation
| Capability | Google | Alibaba 2018 | Azure VM V2 |
|---|---:|---:|---:|
| CPU signal | Yes | Yes | Yes |
| Memory signal | Yes | Yes | Yes, capacity only |
| Explicit request | Yes | Yes | No |
| Observed CPU | Yes | Yes | Yes |
| Observed memory | Yes | Yes | No |
| Validated recurrence | Yes | No | No |
| Canonical next-occurrence target | Yes | Not yet | Not yet |
| ML-ready under current contract | Yes | Not yet | Not yet |

## Canonical mapping examples

### Google
- `workload_id` → corrected `recurrence_key`
- `execution_id` → corrected `execution_id`
- `occurrence_id` → corrected `occurrence_key`
- `recurrence_key` → corrected `recurrence_key`
- `actual_cpu` for evaluator → `target_cpu_next_occurrence_peak_ncu`
- `actual_memory` for evaluator → `target_memory_next_occurrence_peak_normalized`

The canonical layer references the corrected Google artifacts; it does not rebuild occurrence aggregation or targets.

### Alibaba
- `workload_id` → `job_name`
- `execution_id` → task identity (`job_name + task_name`)
- `instance_id` → `instance_name`
- `recurrence_key` → null until a recurrence rule is validated
- request and observed CPU/memory may be represented with source-native/verified units

### Azure VM
- `workload_id` → `deployment_id`
- `execution_id` / `instance_id` → `vm_id`
- `recurrence_key` → null
- `allocated_cpu` → vCPU/core bucket
- `allocated_memory` → memory-capacity bucket
- `observed_cpu` → CPU utilization telemetry
- `observed_memory` → null/unsupported

## Shared evaluator view
Canonical evaluator names:
- `dataset_id`
- `workload_id`
- `policy_name`
- `actual_cpu`
- `actual_memory`
- `recommended_cpu`
- `recommended_memory`

A row may evaluate CPU only, memory only, or both. At least one actual/recommendation pair must be valid. Matching unit columns are required for populated evaluator pairs.

## Dataset-specific extensions
Adapters may preserve source metadata without making shared code depend on it.

Alibaba examples: DAG/task type, `instance_num`, machine ID, `seq_no`, `total_seq_no`.  
Azure examples: subscription ID, deployment ID, VM category, core-count bucket, memory-capacity bucket.  
Google examples: source collection and occurrence/history metadata.

## Issue boundaries
**Issue 2 owns:** schema, field meanings, units, capability flags, missing-value rules, canonical evaluator names, validation.

**Issue 3 owns:** adapter interface and source-to-canonical mapping behavior.

**Issue 4 owns:** Alibaba/Azure adapter implementation and dataset integration.

**Issue 5 owns:** final standardized baseline/ML/Hybrid recommendation output contract.
