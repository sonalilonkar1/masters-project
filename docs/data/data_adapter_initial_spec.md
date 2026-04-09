# data_adapter_spec.md

This document defines the canonical internal schema used by TraceAdvisor and how different source datasets should be mapped into it. The purpose of the adapter layer is to isolate dataset-specific extraction logic from the baseline, profiling, and evaluation modules.

## Goal

TraceAdvisor should operate on a standardized execution-level dataset regardless of whether the source data comes from:
- the current Kaggle prototype dataset, or
- the Google ClusterData 2019 traces

This prevents the main logic from depending on source-specific field names or table structures.

## Canonical internal schema

Each row in the canonical dataset represents one execution unit used for baseline recommendation and offline evaluation.

### Required fields

- `execution_id`  
  Unique identifier for one execution/run.

- `recurring_job_id`  
  Stable grouping key used to identify repeated executions of the same logical workload.

- `timestamp`  
  Chronological timestamp used for time-aware replay, historical lookback, and leakage-safe evaluation.

- `req_cpu`  
  Requested CPU for the execution.

- `req_mem`  
  Requested memory for the execution.

- `peak_cpu`  
  Observed peak CPU usage for the execution.

- `peak_mem`  
  Observed peak memory usage for the execution.

### Recommended optional fields

- `confidence_tier`
- `n_history`
- `priority`
- `scheduling_class`
- `user`
- `source_dataset`
- `split`

These are not required for baseline computation itself, but are useful for evaluation, debugging, stratification, and later model extensions.

## Adapter design principle

The adapter must:
1. extract raw source fields
2. transform them into the canonical schema
3. output a clean execution-level table

The rest of the pipeline must consume only canonical columns.

---

## Mapping: Kaggle prototype dataset -> canonical schema

Because the Kaggle dataset structure depends on the chosen subset, the exact mapping may vary slightly. The general expectation is:

- `execution_id` <- existing job/run identifier, or generated row ID if no stable execution key exists
- `recurring_job_id` <- existing workload/job group field if present, otherwise derived grouping field
- `timestamp` <- submission time, start time, or trace order field
- `req_cpu` <- CPU request column
- `req_mem` <- memory request column
- `peak_cpu` <- CPU peak or observed max CPU column
- `peak_mem` <- memory peak or observed max memory column

### Kaggle adapter requirement
If any of these fields do not exist directly, the Kaggle adapter should document how they are approximated.

---

## Mapping: Google ClusterData 2019 -> canonical schema

The Google traces are split across multiple tables and require joins plus aggregation.

### Source tables used in v0
- `collection_events`
- `instance_events`
- `instance_usage`

### Canonical field mapping

#### `req_cpu`
From:
- `instance_events.resource_request.cpu`

#### `req_mem`
From:
- `instance_events.resource_request.memory`

#### `peak_cpu`
Derived from:
- `max(instance_usage.maximum_usage.cpu)` across all measurement windows belonging to the same execution

#### `peak_mem`
Derived from:
- `max(instance_usage.maximum_usage.memory)` across all measurement windows belonging to the same execution

#### `recurring_job_id`
From:
- `collection_events.collection_logical_name`

This is the preferred grouping key because it is intended to normalize repeated executions of the same logical workload.

#### `timestamp`
Preferred prototype rule:
- first `SCHEDULE` timestamp for the execution if available
- otherwise first `SUBMIT` timestamp

This field must support strict chronological ordering.

#### `execution_id`
Preferred rule:
- construct using `collection_id`, `instance_index`, and a run boundary such as run start time

Example concept:
- `execution_id = collection_id + instance_index + run_start_time`

This is necessary because the same instance may be restarted without receiving a new base identifier.

---

## Execution granularity

The adapter must output one row per execution-level unit.

For the prototype, execution may be defined at the instance-run level:
- one instance across one continuous lifecycle segment

This is preferable to leaving data at the 5-minute window level, because the baseline and evaluation logic operate on one request and one peak per execution.

---

## Aggregation rules for Google traces

### Usage aggregation
The Google trace reports resource usage in non-overlapping measurement windows, typically about 5 minutes long.

To produce execution-level peaks:

- `peak_cpu = max(window maximum CPU usage)`
- `peak_mem = max(window maximum memory usage)`

across all windows belonging to the same execution.

### Event aggregation
Execution timestamp should be taken from the chosen start event for that run.

If multiple request records exist due to updates, the adapter should document whether it:
- uses the initial request for the run, or
- uses the most recent request before execution

For v0, using the request associated with the start of the run is acceptable as long as the rule is applied consistently.

---

## Out-of-scope fields for v0

The following dataset features are intentionally excluded from the initial adapter:

- GPU metrics
- alloc sets
- machine constraints
- machine attributes
- page cache metrics
- CPU usage histograms
- tail CPU usage distributions
- CPI / MAI counters

These may be added later, but they are not required for the percentile-baseline prototype.

---

## Output of the adapter

The adapter should produce a clean table with canonical columns only, such as:

- `execution_id`
- `recurring_job_id`
- `timestamp`
- `req_cpu`
- `req_mem`
- `peak_cpu`
- `peak_mem`

Optionally:
- `priority`
- `scheduling_class`
- `user`
- `source_dataset`

This output can then be saved as CSV or Parquet and used by:
- recurring job profiling
- percentile baseline generation
- evaluation metrics computation
- summary reporting

---

## Validation checks for the adapter

Before using adapter output in the baseline pipeline, validate:

1. `execution_id` is unique
2. `timestamp` is non-null and sortable
3. `req_cpu`, `req_mem`, `peak_cpu`, `peak_mem` are numeric
4. `peak_cpu >= 0` and `peak_mem >= 0`
5. `recurring_job_id` is populated for most rows
6. no future records are used when computing historical statistics

---

## Design intent

The adapter layer is meant to absorb source-dataset complexity so that the rest of TraceAdvisor remains stable.

If implemented correctly:
- the current Kaggle prototype will still be useful
- switching to Google ClusterData 2019 will mostly involve adapter work rather than core logic rework
