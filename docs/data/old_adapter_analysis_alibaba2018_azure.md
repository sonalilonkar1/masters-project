# Alibaba and Azure VM Canonical Integration

> Old reference document. This file preserves the earlier PR #70 adapter analysis for Alibaba 2018 and Azure. It is not the current adapter framework or Alibaba GPU 2020 integration plan. Current adapter responsibilities are defined in:
> - docs/design/adapter_framework.md
> - docs/design/canonical_workload_schema.md
> - docs/design/canonical_schema_design_decisions.md
>
> - It describes the earlier adapter scope, which covered Alibaba 2018 and Azure.
> - Alibaba GPU 2020 is now the required second integration.
> - Azure is deferred.
> - The current adapter framework document (`docs/design/adapter_framework.md`) is authoritative.

**TraceAdvisor 295B — New Development Issue 4**

## Goal

Integrate Alibaba Cluster Trace 2018 and Azure Public Dataset V2 through the
shared adapter/canonical interface without inventing unsupported semantics.

## Alibaba 2018

### Input tables
- `batch_task.csv`
- `batch_instance.csv`

### Canonical modeling view
Current adapter output is **instance-level**.

Mappings:

| Alibaba | Canonical |
|---|---|
| `job_name` | `workload_id` |
| `job_name + task_name` | `execution_id` |
| `instance_name` | `instance_id` |
| task `start_time/end_time` source semantics | trace-relative canonical time |
| `plan_cpu` | `requested_cpu` |
| `plan_mem` | `requested_memory` |
| `cpu_avg` | `observed_cpu` |
| `cpu_max` | `peak_cpu` |
| `mem_avg` | `observed_memory` |
| `mem_max` | `peak_memory` |

Recurrence is **not** populated. `job_name` is not silently promoted to a
recurrence key.

Task plan metadata is left-joined onto instance observations. An unmatched
instance remains in the artifact with null request fields and partial validity.

Running/incomplete rows with missing outcomes remain partial and null; they are
not converted to zero.

Dataset-specific extensions preserve status, task type, machine, retry sequence,
declared instance count, and whether task plan metadata matched.

### Important limitation
This adapter does not yet construct a full-workload concurrent job peak across
DAG stages. That is a downstream/history-target design question. Issue 4
integrates source semantics; it does not invent a recurrence or job-level target.

## Azure VM V2

Two canonical views are supported.

### VM lifecycle/capacity view

Mappings:

| Azure VM table | Canonical |
|---|---|
| `deployment_id` | `workload_id` |
| `vm_id` | `execution_id`, `instance_id` |
| `vm_created/vm_deleted` | trace-relative start/end |
| core-count bucket | `allocated_cpu` (`vcpu`) |
| memory bucket | `allocated_memory` (`gb`) |
| lifetime `avg_cpu` | `observed_cpu` (`percent`) |
| lifetime `max_cpu` | `peak_cpu` (`percent`) |

The VM-table CPU summaries are post-observation lifetime outcomes. They must not
be used as pre-execution features for the same VM.

Equal create/delete timestamps are preserved rather than rewritten.

### Five-minute CPU interval view

CPU readings are joined to VM metadata by `vm_id`.

Mappings:

| CPU reading / VM metadata | Canonical |
|---|---|
| `deployment_id` | `workload_id` |
| `vm_id` | `execution_id`, `instance_id` |
| `timestamp` | `event_time_us` |
| 5-minute cadence | `aggregation_window_sec = 300` |
| `avg_cpu` | `observed_cpu` (`percent`) |
| `max_cpu` | `peak_cpu` (`percent`) |
| core bucket | `allocated_cpu` (`vcpu`) |
| memory bucket | `allocated_memory` (`gb`) |

Observed memory is always null/unsupported for this selected trace.

The adapter requires CPU-reading VM IDs to overlap the supplied VM table.
Zero-overlap samples fail clearly rather than fabricating deployment metadata.

## Generated artifacts

`scripts/build_external_canonical_samples.py` can create:

- `alibaba2018_instances_canonical.parquet`
- `azure_vm_lifecycle_canonical.parquet`
- `azure_vm_cpu_intervals_canonical.parquet` when VM IDs overlap

Each artifact has a sidecar `.metadata.json`.

## Current Issue-4 boundary

Completed here:
- production Alibaba adapter;
- production Azure VM adapter;
- canonical field mapping;
- capability-aware missing/unsupported behavior;
- provenance extensions;
- reload tests;
- artifact builder.

Carried forward:
- validated Alibaba recurrence/workload-family rule;
- Alibaba full-workload DAG concurrency target construction;
- Azure recurrence, if ever justified;
- dataset-specific historical profiles/ML targets after those semantics are frozen.

These open questions must remain explicit rather than being solved by guessing.
