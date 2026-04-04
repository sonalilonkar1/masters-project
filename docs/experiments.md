# Experiments — ClusterData2019 (Cell A), 1 Day and 1 Week

## 1) Goal
Demonstrate “pre-execution advisory” behavior using trace-derived baselines:
- Baseline 0: as-is requests (current practice)
- Baseline 1: per-job percentile sizing (P95/P99) computed from history

We evaluate decision quality using:
- violation rate (risk proxy)
- waste/slack under recommendation (efficiency proxy)
- slack reduction relative to baseline0

Experiments are time-aware: recommendations for test runs use only prior history.

---

## 2) Dataset choice and rationale
We use Google ClusterData2019 (Cell A) because it provides:
- resource requests (CPU/mem)
- observed usage including maximum usage signals
- time fields to do chronological splitting
- job identity metadata (collection logical names)

We do not use full dataset exports because they are too large; we operate via BigQuery derived tables.

---

## 3) Pipeline overview
### Raw tables (public BigQuery)
- `clusterdata_2019_a.instance_usage` (maximum usage, average usage, start/end)
- `clusterdata_2019_a.instance_events` (resource_request)
- `clusterdata_2019_a.collection_events` (collection_name/logical_name/user)

### Derived tables (our project)
1) create usage slice (1d or 1w): `instance_usage_*`
2) get instance keys: `instances_in_*`
3) recover requests outside slice window: `instance_requests_anytime_*`
4) join meta: `collection_meta_*` / `collection_meta_anytime_*`
5) join into skinny: `borg_traces_*_skinny`
6) aggregate one row per instance: `borg_traces_*_jobmetrics`
7) export jobmetrics to GCS Parquet folders
8) run evaluator locally/Colab using GCS inputs

---

## 4) Exact BigQuery queries used (1-day example)
### 4.1 Define time window (microseconds)
We used:

- day_len = 86400 * 1,000,000
- min_start = MIN(start_time) from instance_usage
- T0 = min_start + 2 * day_len
- T1 = T0 + day_len

(For week: T1 = T0 + 7 * day_len)

### 4.2 Create 1-day usage slice
```sql
CREATE OR REPLACE TABLE `traceadvisor-295a.traceadvisor_eda.instance_usage_1d` AS
SELECT
  start_time, end_time, collection_id, instance_index,
  average_usage, maximum_usage
FROM `google.com:google-cluster-data.clusterdata_2019_a.instance_usage`
WHERE start_time >= @T0 AND start_time < @T1;
```

# 4.3 List instances in slice

```sql
CREATE OR REPLACE TABLE `traceadvisor-295a.traceadvisor_eda.instances_in_1d` AS
SELECT DISTINCT collection_id, instance_index
FROM `traceadvisor-295a.traceadvisor_eda.instance_usage_1d`;
```

# 4.4 Recover requests “anytime” (fix NULL requests)

Reason: request events may be outside the slice window.

```sql
CREATE OR REPLACE TABLE `traceadvisor-295a.traceadvisor_eda.instance_requests_anytime_1d` AS
SELECT
  e.collection_id,
  e.instance_index,
  ANY_VALUE(e.resource_request) AS resource_request,
  MIN(e.time) AS first_request_time
FROM `google.com:google-cluster-data.clusterdata_2019_a.instance_events` e
JOIN `traceadvisor-295a.traceadvisor_eda.instances_in_1d` s
USING (collection_id, instance_index)
WHERE e.resource_request IS NOT NULL
GROUP BY e.collection_id, e.instance_index;
```

# 4.5 Collection metadata for recurrence key

```sql
CREATE OR REPLACE TABLE `traceadvisor-295a.traceadvisor_eda.collection_meta_1d` AS
SELECT
  collection_id,
  ANY_VALUE(user) AS user,
  ANY_VALUE(collection_name) AS collection_name,
  ANY_VALUE(collection_logical_name) AS collection_logical_name
FROM `google.com:google-cluster-data.clusterdata_2019_a.collection_events`
GROUP BY collection_id;
```

# 4.6 Create skinny joined table

```sql
CREATE OR REPLACE TABLE `traceadvisor-295a.traceadvisor_eda.borg_traces_1d_skinny` AS
SELECT
  u.start_time,
  u.end_time,
  u.collection_id,
  u.instance_index,
  COALESCE(c.collection_logical_name, c.collection_name, CAST(u.collection_id AS STRING)) AS recurring_job_id,
  r.resource_request.cpus   AS req_cpu,
  r.resource_request.memory AS req_mem,
  u.maximum_usage.cpus      AS peak_cpu,
  u.maximum_usage.memory    AS peak_mem,
  u.average_usage.cpus      AS avg_cpu,
  u.average_usage.memory    AS avg_mem
FROM `traceadvisor-295a.traceadvisor_eda.instance_usage_1d` u
LEFT JOIN `traceadvisor-295a.traceadvisor_eda.instance_requests_anytime_1d` r
USING (collection_id, instance_index)
LEFT JOIN `traceadvisor-295a.traceadvisor_eda.collection_meta_1d` c
USING (collection_id);
```

# 4.7 Aggregate to one row per instance (canonical jobmetrics)

Reason: skinny table has repeated rows (~81 samples per instance). Experiments require 1 row per execution.

```sql
CREATE OR REPLACE TABLE `traceadvisor-295a.traceadvisor_eda.borg_traces_1d_jobmetrics` AS
SELECT
  recurring_job_id,
  collection_id,
  instance_index,
  MIN(start_time) AS start_time,
  MAX(end_time) AS end_time,
  ANY_VALUE(req_cpu) AS req_cpu,
  ANY_VALUE(req_mem) AS req_mem,
  MAX(peak_cpu) AS peak_cpu,
  MAX(peak_mem) AS peak_mem,
  AVG(avg_cpu) AS avg_cpu,
  AVG(avg_mem) AS avg_mem
FROM `traceadvisor-295a.traceadvisor_eda.borg_traces_1d_skinny`
WHERE req_cpu IS NOT NULL AND req_mem IS NOT NULL
  AND peak_cpu IS NOT NULL AND peak_mem IS NOT NULL
  AND start_time IS NOT NULL AND end_time IS NOT NULL
GROUP BY recurring_job_id, collection_id, instance_index;
```

> We run the analogous queries for 1-week using `instance_usage_1w`, etc.

# 5) Experiments (methods)

## Baseline 0 — as-is requests

Recommendation:

- `rec_cpu = req_cpu`
- `rec_mem = req_mem`

## Baseline 1 — percentile sizing (P95 / P99)

For each `recurring_job_id`:

- compute P95 (or P99) of `peak_cpu` and `peak_mem` from TRAIN history only
- apply to TEST
- cold-start fallback: if history unavailable or insufficient, fallback to original request

We use a minimum history threshold (default `min_history=3`; we tested `min_history=5` and results were similar).

# 6) Time-aware split

We sort by `start_time` and compute:

```text
split_t = min_start + split_ratio * (max_start - min_start)
```

Default `split_ratio = 0.7`

- Train: `start_time < split_t`
- Test: `start_time >= split_t`

This prevents leakage (no future runs used for quantiles).

# 7) Metrics

For each method on TEST:

## Violation

- `viol_cpu = (peak_cpu > rec_cpu)`
- `viol_mem = (peak_mem > rec_mem)`
- `viol_any = viol_cpu OR viol_mem`

## Waste (positive slack only)

- `waste_cpu = sum(max(0, rec_cpu - peak_cpu))`
- `waste_mem = sum(max(0, rec_mem - peak_mem))`

## Slack reduction (%) relative to baseline0

- `slack_reduction_cpu = (waste_cpu_baseline0 - waste_cpu_method) / waste_cpu_baseline0`
- `slack_reduction_mem = (waste_mem_baseline0 - waste_mem_method) / waste_mem_baseline0`

Note: CPU slack reduction can be negative if baseline0 requests are CPU-underprovisioned (method increases CPU headroom to reduce risk).

# 8) Outputs

Generated by `src/eval/evaluator_v0.py`:

## Per-execution CSVs (not committed)

- `reports/eval/per_execution_baseline0_as_is_<split>.csv`
- `reports/eval/per_execution_baseline1_p95_<split>.csv`
- `reports/eval/per_execution_baseline1_p99_<split>.csv`

## Summary CSVs (committed)

- `reports/eval/summary_1d.csv`
- `reports/eval/summary_1w.csv`

Summary includes overall `tier=all` and tier breakdown (`high` / `medium` / `low`) for baseline1 methods.

# 9) Reproducibility

See `docs/runbook.md` for exact commands to:

- export jobmetrics tables to GCS
- run evaluator locally against GCS folder inputs
