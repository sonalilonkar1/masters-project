
## Ingest / Reconstruction Assumptions
- CPU normalization factor to cores: 1.0
- Memory normalization factor to GB: 1.0
- execution_id = collection_id + '_' + instance_index
- execution start_time = min(start_time) per execution_id
- execution end_time = max(end_time) per execution_id
- runtime_sec = end_time - start_time

## Canonical Metrics Assumptions
- Canonical metrics file uses req_mem_gb and peak_mem_gb naming.
- duration in job_metrics_v0.parquet is computed as end_time - start_time in raw trace time units.
- recurrence_key is carried forward as the first observed key per execution_id.
- subset_clean.parquet may still contain req_mem and peak_mem as pre-canonical ingest names.
