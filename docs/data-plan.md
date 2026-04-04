# Data Plan — TraceAdvisor (CMPE 295A)

## 1) Purpose
This document describes:
- which datasets we use (Google ClusterData2019 primary, Alibaba optional),
- how we extract manageable subsets (1 day and 1 week),
- how we address missing requests and data quality issues,
- where canonical experiment inputs live (BigQuery + GCS), and
- what artifacts are produced for evaluation.

We keep raw/processed trace data out of GitHub. Only code, docs, and small result summaries (CSV) are committed.

---

## 2) Primary dataset: Google ClusterData2019 (Cell A)
We use the Google ClusterData2019 traces as the primary dataset because it contains:
- job/collection metadata (names, logical names),
- instance-level resource requests,
- instance usage with maximum usage signals,
- timestamps needed for time-aware evaluation.

### Source
- BigQuery public dataset project: `google.com:google-cluster-data`
- Dataset used: `clusterdata_2019_a` (Cell A)

---

## 3) Why we use BigQuery and GCS
The raw ClusterData2019 dataset is extremely large. Exporting full raw tables is impractical.
We therefore:
1) store intermediate and derived tables in BigQuery (`traceadvisor-295a.traceadvisor_eda`)
2) export only compact, aggregated "jobmetrics" tables to GCS as Parquet for repeatable experiments.

This is the cheapest and most reproducible approach for a class project.

---

## 4) Derived tables (BigQuery)
All derived tables are created in:
- BigQuery project: `traceadvisor-295a`
- dataset: `traceadvisor_eda`

### Core input tables from Google dataset
- `google.com:google-cluster-data.clusterdata_2019_a.instance_usage`
- `google.com:google-cluster-data.clusterdata_2019_a.instance_events`
- `google.com:google-cluster-data.clusterdata_2019_a.collection_events`

### Derived tables we build
For both 1-day and 1-week subsets we build:

1) `instance_usage_1d` / `instance_usage_1w`  
   - Usage slice for a chosen window (start_time in range).
   - Contains `maximum_usage` and `average_usage`.

2) `instances_in_1d` / `instances_in_1w`  
   - Distinct (collection_id, instance_index) pairs appearing in the usage slice.

3) `instance_requests_anytime_1d` / `instance_requests_anytime_1w`  
   - Fixes missing requests by pulling `resource_request` from instance_events across time,
     but only for instances present in the slice.

4) `collection_meta_1d` (or `collection_meta_anytime_1w`)  
   - Collection name + logical name + user metadata used to define recurrence key.

5) `borg_traces_*_skinny`  
   - Joined table: usage + request + meta with flattened req/peak CPU/mem.
   - Still may contain multiple rows per instance (due to sampling).

6) `borg_traces_*_jobmetrics` (canonical experiment input)  
   - Aggregated to one row per instance execution:
     - peak values are aggregated with MAX
     - start/end times aggregated with MIN/MAX
   - This is what we export to GCS and load in Colab/Python.

---

## 5) Time window definition (1-day and 1-week)
We treat the trace timestamps as microseconds (based on observed magnitudes and span checks).

We define:
- day_len = 86400 * 1,000,000
- min_start = MIN(start_time) in `instance_usage`

We pick:
- T0 = min_start + 2 * day_len  (skip initial edge effects)
- 1-day: T1 = T0 + day_len
- 1-week: T1 = T0 + 7 * day_len

We filter usage rows by `start_time >= T0 AND start_time < T1`.

---

## 6) Subset-first strategy (Tiny vs Reportable)
### Tiny subset (fast debugging / correctness checks)
- **Selection method:** 1-day time window (time-based slice)
- **Time window:** `T0 = min_start + 2*day_len`, `T1 = T0 + 1*day_len` (microseconds)

**Tables needed (BigQuery derived):**
- `traceadvisor-295a.traceadvisor_eda.instance_usage_1d`
- `traceadvisor-295a.traceadvisor_eda.instances_in_1d`
- `traceadvisor-295a.traceadvisor_eda.instance_requests_anytime_1d`
- `traceadvisor-295a.traceadvisor_eda.collection_meta_1d`
- `traceadvisor-295a.traceadvisor_eda.borg_traces_1d_skinny`
- `traceadvisor-295a.traceadvisor_eda.borg_traces_1d_jobmetrics` (canonical input)

**Expected size (rough):**
- `borg_traces_1d_jobmetrics`: ~300–400 MB Parquet export (observed ~335 MB)

**How to load (Colab/local):**
```python
pd.read_parquet("gs://traceadvisor-exports-295a/clusterdata2019/1d_jobmetrics/")
```

### Reportable subset (~1 week for baseline results)
- **Selection method:** 7-day time window (time-based slice)
- **Time window:** `T0 = min_start + 2*day_len`, `T1 = T0 + 7*day_len`

**Tables needed (BigQuery derived):**
- `traceadvisor-295a.traceadvisor_eda.instance_usage_1w`
- `traceadvisor-295a.traceadvisor_eda.instances_in_1w`
- `traceadvisor-295a.traceadvisor_eda.instance_requests_anytime_1w`
- `traceadvisor-295a.traceadvisor_eda.collection_meta_1w` (or anytime meta)
- `traceadvisor-295a.traceadvisor_eda.borg_traces_1w_skinny`
- `traceadvisor-295a.traceadvisor_eda.borg_traces_1w_jobmetrics` (canonical input)

**Expected size (rough):**
- `borg_traces_1w_jobmetrics`: ~2–5 GB Parquet export (depends on shard count; confirm in GCS)

**How to load (Colab/local):**
```python
pd.read_parquet("gs://traceadvisor-exports-295a/clusterdata2019/1w_jobmetrics/")
```

### Why this strategy works for evaluation
Percentile baselines (P95/P99) require enough history. The week subset yields more recurring jobs with `n_hist >= 5`, enabling stable per-job percentiles; the tiny subset is primarily for pipeline correctness and quick iteration.

---

## 7) Canonical recurrence key (recurring_job_id)
We define a stable recurrence key using collection metadata:

recurring_job_id =
  COALESCE(collection_logical_name, collection_name, CAST(collection_id AS STRING))

This matches our project intent: group recurring workloads by stable logical name when available.

---

## 8) Data quality rules (why we filter NULLs)
### Why requests can be NULL in a slice
In ClusterData2019, usage events may fall in the 1-day window even if the corresponding
request event was recorded outside that window. If we only join on events within the same day,
many rows have NULL `req_cpu/req_mem`.

### Our fix
We construct `instance_requests_anytime_*` by joining the slice’s instances into instance_events
without applying the 1-day filter. That recovers requests for most instances.

### Filtering
For evaluation, a run must have:
- req_cpu, req_mem not NULL (recommendation is undefined otherwise)
- peak_cpu, peak_mem not NULL (violation/waste are undefined otherwise)
- start_time not NULL (needed for time-aware splits)

We drop rows failing any of the above.

---

## 9) GCS exports (repeatable inputs)
We export the canonical jobmetrics tables to GCS as Parquet datasets:

- 1-day jobmetrics:
  `gs://traceadvisor-exports-295a/clusterdata2019/1d_jobmetrics/`

- 1-week jobmetrics:
  `gs://traceadvisor-exports-295a/clusterdata2019/1w_jobmetrics/`

These folder URIs work reliably with pandas/pyarrow.

---

## 10) What is committed to GitHub vs not
### Not committed
- Raw data
- BigQuery exports (parquet)
- Per-execution evaluation CSVs (can be large)

### Committed
- Code (`src/`)
- Docs (`docs/`)
- Small summaries:
  - `reports/eval/summary_1d.csv`
  - `reports/eval/summary_1w.csv`

---

## 11) Optional dataset (future validation)
Alibaba cluster traces may be used later for generalization.
Not required for 295A baseline results.