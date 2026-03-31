# Initial Analysis of Google ClusterData 2019 for TraceAdvisor

This note captures the initial analysis of the Google ClusterData 2019 traces from the perspective of the TraceAdvisor prototype. The goal is not to fully process the dataset yet, but to identify which parts of the trace map to the fields required by our baseline and evaluation pipeline.

## Why this analysis is needed

The prototype currently uses a smaller Kaggle dataset to accelerate implementation. However, the intended larger-scale dataset is Google ClusterData 2019, which is more complex and is primarily accessed through BigQuery.

To avoid rework, we need to understand how the Google trace tables can be transformed into the canonical execution-level schema used by TraceAdvisor.

## Key observation

The Google traces are not stored as one row per job execution with direct request and peak columns. Instead, they are split across multiple event and usage tables. This means the prototype logic should not depend on raw dataset-specific columns. Instead, both the Kaggle dataset and the Google traces should be transformed into a shared internal schema.

## Canonical schema required by TraceAdvisor

The current prototype is built around the following execution-level fields:

- `execution_id`
- `recurring_job_id`
- `timestamp`
- `req_cpu`
- `req_mem`
- `peak_cpu`
- `peak_mem`

This schema is sufficient for:
- historical profiling of recurring jobs
- percentile-based baselines such as P50/P90/P95/P99
- time-aware offline evaluation
- slack and violation metric computation

## Relevant Google trace tables for v0

For the initial prototype, only a subset of the Google trace tables is necessary.

### 1. CollectionEvents
This table provides collection-level metadata such as:
- `collection_id`
- `collection_logical_name`
- `user`
- `priority`
- `scheduling_class`
- collection lifecycle events

This table is most useful for defining recurring workload identity.

### 2. InstanceEvents
This table provides instance-level lifecycle and request information such as:
- `collection_id`
- `instance_index`
- `time`
- `resource_request`
- `machine_id`
- event type

This table is the main source for resource requests.

### 3. InstanceUsage
This table provides windowed resource usage measurements such as:
- `start_time`
- `end_time`
- `collection_id`
- `instance_index`
- `maximum_usage`
- `average_usage`
- CPU distribution fields

This table is the main source for observed usage peaks.

## Mapping from Google traces to TraceAdvisor fields

### Requested resources
Requested CPU and memory can be obtained from:

- `InstanceEvents.resource_request.cpu`
- `InstanceEvents.resource_request.memory`

These correspond to the requested instance resource limits used for scheduling.

### Peak resource usage
Observed peak CPU and memory can be obtained from:

- `InstanceUsage.maximum_usage.cpu`
- `InstanceUsage.maximum_usage.memory`

Since usage is reported per measurement window, execution-level peak must be computed by aggregating across all windows belonging to the same execution:

- `peak_cpu = max(maximum_usage.cpu over all windows in the execution)`
- `peak_mem = max(maximum_usage.memory over all windows in the execution)`

This means the prototype does not need to reconstruct peaks from CPU histograms for v0 if `maximum_usage` is available.

### Timestamp
A single chronological timestamp is needed for leakage-safe replay and historical baselines.

A practical prototype choice is:
- use the first `SCHEDULE` time for an execution if available
- otherwise use `SUBMIT` time as fallback

This timestamp should be consistent across the pipeline and used for sorting past versus future executions.

### Recurring job identity
The best candidate for grouping repeated executions of the same logical workload is:

- `CollectionEvents.collection_logical_name`

The trace documentation states that `collection_logical_name` is designed to normalize different executions of the same program, including cases where raw collection names change due to auto-generated suffixes.

Therefore, for the prototype:

- `recurring_job_id = collection_logical_name`

This is a better grouping key than raw collection name.

### Execution identity
The traces distinguish collections and instances, but the same instance may be restarted without receiving a new collection ID or instance index. Therefore:

- `collection_id + instance_index` alone is not always a sufficient execution identifier

A more accurate execution identifier should include a run boundary, such as:

- `execution_id = collection_id + instance_index + run_start_time`

For the prototype, execution segmentation may be approximated first, but the final pipeline should treat restarts and reschedules as distinct executions where possible.

## Important simplifications for v0

To avoid overcomplicating the prototype, the following parts of the dataset should be deferred:

- alloc sets
- machine attributes
- machine constraints
- GPU metrics
- CPU histogram distributions
- advanced scheduler metadata beyond what is needed for grouping or filtering

For v0, the prototype can focus on:

- request values from `InstanceEvents.resource_request`
- peak values from `InstanceUsage.maximum_usage`
- recurring grouping from `collection_logical_name`

This is sufficient for implementing warm-start profiling, percentile-based baselines, and offline evaluation.

## Expected impact on implementation

Moving from Kaggle to Google ClusterData 2019 will require some dataset-adapter work, but should not require rewriting the core baseline or evaluation logic if the prototype uses a canonical internal schema.

What will change later:
- reading from BigQuery instead of a simple CSV
- joining multiple tables
- aggregating windowed usage into execution-level peaks
- constructing execution boundaries more carefully

What should remain unchanged:
- baseline logic
- percentile computation
- confidence tier logic
- evaluation metrics
- output table format

## Conclusion

The Google ClusterData 2019 traces are more complex than the Kaggle prototype dataset, but they still support the TraceAdvisor prototype well. The required fields for the current baseline and evaluation plan can be derived primarily from:

- `CollectionEvents`
- `InstanceEvents`
- `InstanceUsage`

As long as TraceAdvisor standardizes all inputs into a canonical execution-level schema, the current Kaggle-based implementation should serve as a useful prototype rather than wasted effort.
