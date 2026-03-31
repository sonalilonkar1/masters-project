# Evaluation Output Format (v0) — TraceAdvisor

This document defines the v0 output artifacts produced by the offline evaluator.
All methods (Baseline 0/1/2/3 and TraceAdvisor) must use the same output schema to ensure fair comparisons.

## Output Artifacts (minimum)

### 1) Per-execution results (recommended for debugging)
**File:** `reports/eval/per_execution_<method>_<split>.csv`

Purpose: record the recommendation, observed peak, and violation/slack outcomes for each execution. Useful for debugging anomalies and producing plots.

Required columns:
- `execution_id` — unique ID for a job execution/run
- `recurring_job_id` — stable recurring job grouping key
- `timestamp` — submission time or execution start time used for chronological ordering
- `confidence_tier` — {high, medium, low}

Observed (ground truth from traces):
- `peak_cpu`
- `peak_mem_gb`
- `peak_gpu` *(optional; include only if available in dataset)*

Requests (status quo):
- `req_cpu`
- `req_mem_gb`
- `req_gpu` *(optional)*

Recommendations (method output):
- `rec_cpu`
- `rec_mem_gb`
- `rec_gpu` *(optional)*

Slack values:
- `slack_req_cpu` = `req_cpu - peak_cpu`
- `slack_req_mem_gb` = `req_mem_gb - peak_mem_gb`
- `slack_req_gpu` *(optional)*
- `slack_rec_cpu` = `rec_cpu - peak_cpu`
- `slack_rec_mem_gb` = `rec_mem_gb - peak_mem_gb`
- `slack_rec_gpu` *(optional)*

Waste values (positive slack only):
- `waste_req_cpu` = `max(0, slack_req_cpu)`
- `waste_req_mem_gb` = `max(0, slack_req_mem_gb)`
- `waste_req_gpu` *(optional)*
- `waste_rec_cpu` = `max(0, slack_rec_cpu)`
- `waste_rec_mem_gb` = `max(0, slack_rec_mem_gb)`
- `waste_rec_gpu` *(optional)*

Under-provisioning (severity):
- `under_prov_cpu` = `max(0, peak_cpu - rec_cpu)`
- `under_prov_mem_gb` = `max(0, peak_mem_gb - rec_mem_gb)`
- `under_prov_gpu` *(optional)*

Violation indicators (binary):
- `viol_cpu` = `1` if `peak_cpu > rec_cpu` else `0`
- `viol_mem` = `1` if `peak_mem_gb > rec_mem_gb` else `0`
- `viol_gpu` *(optional)*
- `viol_any` = `1` if any resource violation else `0`

Utilization:
- `util_cpu` = `peak_cpu / rec_cpu` *(if rec_cpu > 0)*
- `util_mem` = `peak_mem_gb / rec_mem_gb` *(if rec_mem_gb > 0)*
- `util_gpu` *(optional)*

Optional columns *(helpful later, not required for v0)*:
- `n_history` — number of prior runs used for recommendation
- `coverage_target` — e.g., `0.95`
- `margin_param` — configured margin/headroom used for this method

> **Notes:**
> - For GPU: if GPU is not available in the dataset subset, omit GPU columns consistently across all outputs.
> - Keep memory consistently in GB to reduce confusion.

---

### 2) Method summary (overall + tier breakdown)
**File:** `reports/eval/summary_<split>.csv`

Purpose: one table per evaluation run summarizing decision-quality metrics for each method.

Each row corresponds to one (method, tier) combination.

Required columns:
- `split` — {validation, test}
- `method` — e.g., `baseline0_as_is`, `baseline1_percentile`, `baseline_p50`, `baseline_p90`, `baseline_p95`, `baseline_p99`, `traceadvisor`
- `tier` — {all, high, medium, low}
- `n_exec` — number of executions evaluated in that tier

Violation rates:
- `vr_any`
- `vr_cpu`
- `vr_mem`
- `vr_gpu` *(optional)*

Slack totals:
- `total_slack_req_cpu`
- `total_slack_req_mem_gb`
- `total_slack_req_gpu` *(optional)*
- `total_slack_rec_cpu`
- `total_slack_rec_mem_gb`
- `total_slack_rec_gpu` *(optional)*

Slack reduction (%):
- `slack_reduction_cpu_pct`
- `slack_reduction_mem_pct`
- `slack_reduction_gpu_pct` *(optional)*

Under-provisioning (aggregated):
- `avg_under_prov_cpu`
- `avg_under_prov_mem_gb`
- `avg_under_prov_gpu` *(optional)*

Utilization (aggregated):
- `avg_util_cpu`
- `avg_util_mem`
- `avg_util_gpu` *(optional)*

> **Calculation notes:** totals should use waste (positive slack only) when computing slack reduction:
> ```
> TotalSlack_req(r) = sum max(0, req - peak)
> TotalSlack_rec(r) = sum max(0, rec - peak)
> ```

> If `TotalSlack_req(r)` is negligible, `slack_reduction_r_pct` should be reported as NA.

---

### 3) Tradeoff sweep summary *(optional in v0, required later)*
**File:** `reports/eval/tradeoff_<method>_<split>.csv`

Purpose: support risk–efficiency tradeoff curves by sweeping percentile values.

Required columns:
- `method`
- `split`
- `tier` — {all, high, medium, low}
- `sweep_param_name` — e.g., `percentile`
- `sweep_param_value` — e.g., `0.50`, `0.90`, `0.95`, `0.99`
- `n_exec`
- `vr_any`
- `slack_reduction_cpu_pct`
- `slack_reduction_mem_pct`
- `slack_reduction_gpu_pct` *(optional)*

---

## Naming Conventions

Recommended method IDs:
- `baseline0_as_is`
- `baseline_p50`
- `baseline_p90`
- `baseline_p95`
- `baseline_p99`
- `traceadvisor_quantile_calibrated` *(or `traceadvisor_v1`)*

Recommended split IDs:
- `validation`
- `test`

Recommended directory:
- `reports/eval/`

---

## Minimal v0 success criteria

A v0 evaluation run is considered successful if it produces:
1. `reports/eval/summary_test.csv` with all required columns
2. At least one per-execution CSV for debugging *(recommended)*
