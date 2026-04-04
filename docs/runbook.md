
# Runbook — TraceAdvisor (Sprint 2)

This runbook provides step-by-step instructions to reproduce:
- 1-day and 1-week dataset derivation (BigQuery)
- GCS exports (Parquet)
- baseline experiments (local/Colab)
- evaluation outputs (summary CSVs)

---

## 1) Prerequisites

### Tools
- Python 3.11 (local) or Google Colab
- BigQuery access to the project: `traceadvisor-295a`
- GCS bucket access: `traceadvisor-exports-295a`
- `gcloud` installed (optional but recommended)

### Python dependencies (local)
Install into your environment:

```bash
pip install -U pandas numpy pyarrow gcsfs google-cloud-storage
```

If using BigQuery directly from Python:

```bash
pip install -U google-cloud-bigquery google-cloud-bigquery-storage
```

### Authentication

Local:

```bash
gcloud auth login
gcloud auth application-default login
gcloud auth application-default set-quota-project traceadvisor-295a
```

Colab:

```python
from google.colab import auth
auth.authenticate_user()
```

## 2) Dataset choice

Primary dataset: Google ClusterData2019 (Cell A)

BigQuery dataset:

```text
google.com:google-cluster-data.clusterdata_2019_a
```

Derived tables are created in:

```text
traceadvisor-295a.traceadvisor_eda
```

## 3) Create 1-day / 1-week windows

We use microseconds:

```text
day_len = 86400 * 1,000,000
min_start = MIN(start_time) from instance_usage
T0 = min_start + 2 * day_len
1-day: T1 = T0 + day_len
1-week: T1 = T0 + 7 * day_len
```

## 4) BigQuery build steps (1-day)

Run these in BigQuery UI or via `bq`.

### 4.1 Create `instance_usage_1d`

```sql
CREATE OR REPLACE TABLE `traceadvisor-295a.traceadvisor_eda.instance_usage_1d` AS
SELECT start_time, end_time, collection_id, instance_index, average_usage, maximum_usage
FROM `google.com:google-cluster-data.clusterdata_2019_a.instance_usage`
WHERE start_time >= @T0 AND start_time < @T1;
```

### 4.2 Instances in slice

```sql
CREATE OR REPLACE TABLE `traceadvisor-295a.traceadvisor_eda.instances_in_1d` AS
SELECT DISTINCT collection_id, instance_index
FROM `traceadvisor-295a.traceadvisor_eda.instance_usage_1d`;
```

### 4.3 Recover requests anytime

Reason: request events may be outside the slice window. Without this, `req_cpu` / `req_mem` will be `NULL` for many rows.

```sql
CREATE OR REPLACE TABLE `traceadvisor-295a.traceadvisor_eda.instance_requests_anytime_1d` AS
SELECT e.collection_id, e.instance_index,
       ANY_VALUE(e.resource_request) AS resource_request,
       MIN(e.time) AS first_request_time
FROM `google.com:google-cluster-data.clusterdata_2019_a.instance_events` e
JOIN `traceadvisor-295a.traceadvisor_eda.instances_in_1d` s
USING (collection_id, instance_index)
WHERE e.resource_request IS NOT NULL
GROUP BY e.collection_id, e.instance_index;
```

### 4.4 Collection meta

```sql
CREATE OR REPLACE TABLE `traceadvisor-295a.traceadvisor_eda.collection_meta_1d` AS
SELECT collection_id,
       ANY_VALUE(user) AS user,
       ANY_VALUE(collection_name) AS collection_name,
       ANY_VALUE(collection_logical_name) AS collection_logical_name
FROM `google.com:google-cluster-data.clusterdata_2019_a.collection_events`
GROUP BY collection_id;
```

### 4.5 Build `borg_traces_1d_skinny`

```sql
CREATE OR REPLACE TABLE `traceadvisor-295a.traceadvisor_eda.borg_traces_1d_skinny` AS
SELECT
  u.start_time, u.end_time, u.collection_id, u.instance_index,
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

### 4.6 Aggregate `borg_traces_1d_jobmetrics` (canonical)

Important: skinny has multiple rows per instance (~81 samples/instance). Aggregate to 1 row per execution.

```sql
CREATE OR REPLACE TABLE `traceadvisor-295a.traceadvisor_eda.borg_traces_1d_jobmetrics` AS
SELECT
  recurring_job_id, collection_id, instance_index,
  MIN(start_time) AS start_time,
  MAX(end_time)   AS end_time,
  ANY_VALUE(req_cpu) AS req_cpu,
  ANY_VALUE(req_mem) AS req_mem,
  MAX(peak_cpu) AS peak_cpu,
  MAX(peak_mem) AS peak_mem,
  AVG(avg_cpu)  AS avg_cpu,
  AVG(avg_mem)  AS avg_mem
FROM `traceadvisor-295a.traceadvisor_eda.borg_traces_1d_skinny`
WHERE req_cpu IS NOT NULL AND req_mem IS NOT NULL
  AND peak_cpu IS NOT NULL AND peak_mem IS NOT NULL
  AND start_time IS NOT NULL AND end_time IS NOT NULL
GROUP BY recurring_job_id, collection_id, instance_index;
```

## 5) Repeat for 1-week

Repeat the same steps, changing `instance_usage_1d` → `instance_usage_1w`, etc.
Use `T1 = T0 + 7 * day_len`.

Output tables:

- `borg_traces_1w_jobmetrics`

## 6) Export jobmetrics to GCS (Parquet dataset folders)

### 6.1 1-day export

```sql
EXPORT DATA OPTIONS(
  uri='gs://traceadvisor-exports-295a/clusterdata2019/1d_jobmetrics/000000000000.parquet',
  format='PARQUET',
  overwrite=true
) AS
SELECT * FROM `traceadvisor-295a.traceadvisor_eda.borg_traces_1d_jobmetrics`;
```

### 6.2 1-week export

```sql
EXPORT DATA OPTIONS(
  uri='gs://traceadvisor-exports-295a/clusterdata2019/1w_jobmetrics/000000000000.parquet',
  format='PARQUET',
  overwrite=true
) AS
SELECT * FROM `traceadvisor-295a.traceadvisor_eda.borg_traces_1w_jobmetrics`;
```

Note: BigQuery may shard into multiple files in the destination folder. We read the folder URI.

## 7) Run evaluator locally (Issue #11/#12)

### 7.1 1-day

```bash
python -m src.eval.evaluator_v0 \
  --input "gs://traceadvisor-exports-295a/clusterdata2019/1d_jobmetrics/" \
  --split "1d" \
  --out_dir "reports/eval" \
  --min_history 5
```

### 7.2 1-week

```bash
python -m src.eval.evaluator_v0 \
  --input "gs://traceadvisor-exports-295a/clusterdata2019/1w_jobmetrics/" \
  --split "1w" \
  --out_dir "reports/eval" \
  --min_history 5
```

Outputs:

- `reports/eval/summary_1d.csv`
- `reports/eval/summary_1w.csv`
- per-execution CSVs (ignored by git)

## 8) GitHub guidance (avoid large files)

Do not commit:

- parquet datasets
- `per_execution_*.csv`

Commit:

- code in `src/`
- docs in `docs/`
- summary CSVs in `reports/eval/`

Recommended `.gitignore`:

```gitignore
reports/eval/per_execution_*.csv
data/
*.parquet
```
