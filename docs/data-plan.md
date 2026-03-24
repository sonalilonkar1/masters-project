# Data Plan — TraceAdvisor

## 1) Purpose
This document defines how the TraceAdvisor team will access data, create subsets for development and evaluation, and produce standardized artifacts for Sprint 2+.

We follow a two-tier subset strategy:
1) Tiny subset (debug slice): fast end-to-end correctness validation
2) Reportable subset (~1 week): baseline evaluation results suitable for reporting

Raw and processed datasets are not committed to GitHub. Only scripts, documentation, and small sample files (if any) are committed.

---

## 2) Primary and Secondary Datasets

### Primary dataset (target for reported results)
Google Cluster Workload Traces (ClusterData2019 / Borg traces)
- Source: https://github.com/google/cluster-data
- Note: ClusterData2019 is very large; for reported results we will use either:
  - a prepared shared export (preferred for team consistency), or
  - BigQuery/export workflow (fallback if needed).

### Secondary dataset (optional validation)
Alibaba Cluster Trace Program
- Source: https://github.com/alibaba/clusterdata
- Use: optional validation after core results are demonstrated on the Google traces.

---

## 3) Data Access Strategy (Two-Tier Subsets)

### 3.1 Tiny subset (Debug Slice)
Goal: validate ingestion → reconstruction → peak/slack → evaluation quickly (minutes), and provide a stable artifact for Sprint 2 evaluation development.

We will use a small extracted Parquet dataset that contains job-level metrics needed for Baseline 0 and Baseline 1.

Tiny subset artifact:
- Location (Google Drive): Shareddrives/CMPE 295A_B/subset/
- File name: job_metrics_explore_tiny.parquet
- Contents (columns):
  - execution_id
  - recurring_job_id
  - time, start_time, end_time
  - req_cpu, req_mem
  - peak_cpu, peak_mem
  - avg_cpu, avg_mem
  - slack_cpu, slack_mem
  - viol_cpu, viol_mem, viol_any

Team instructions:
1) Download the Parquet file from the Drive location above.
2) Store it locally (not committed to git) at:
   data/raw/subsets/tiny/job_metrics_explore_tiny.parquet

Expected runtime target:
- < 15 minutes for baseline evaluation + summary outputs on the tiny subset.

---

### 3.2 Reportable subset (~1 week) — PLANNED
Goal: produce baseline results that are meaningful and reportable (Baseline 0 + P95/P99 + later ML baseline), aligned with advisor guidance.

Target window:
- ~7 days of data if feasible; otherwise 3–5 days with clear justification.

Access approach (preferred):
- A single “prepared export” created once and shared with the team via Drive to ensure everyone runs identical inputs.

Fallback:
- BigQuery-based export of only required fields for the chosen time window.

Minimum required information for reportable runs:
- Requested resources (CPU/memory/GPU if available)
- Observed utilization samples or job-level peaks (CPU/memory/GPU if available)
- Timing signals for chronological ordering (submission/start/end times)
- Stable identifiers to group recurring jobs

Team instructions (once created):
1) Download the shared export.
2) Store locally at:
   data/raw/subsets/week/<export files here>

---

## 4) Required Data Elements (v0)
For TraceAdvisor v0, we require:
1) Requested resources: CPU, memory (GPU optional in v0)
2) Peak resource usage: peak CPU, peak memory (peak GPU optional)
3) Chronological ordering: a timestamp column used for time-aware evaluation
4) Recurrence key: a stable identifier to group runs of the same recurring job

Notes:
- In early prototyping, CPU + memory are sufficient to demonstrate the core idea.
- GPU support will be included if usage/request signals are available in the selected dataset subset.

---

## 5) Standard Local Paths (Do not commit to GitHub)
All team members should use the same local paths:

Input subsets:
- Tiny: data/raw/subsets/tiny/job_metrics_explore_tiny.parquet
- Week: data/raw/subsets/week/...

Outputs:
- Evaluation summaries: reports/eval/summary_<split>.csv
- Per-execution outputs: reports/eval/per_execution_<method>_<split>.csv
- Figures: reports/figures/

Split names:
- tiny (debug)
- week (reportable)

---

## 6) Output Artifacts (What Sprint 2+ will produce)
Minimum Sprint 2 outputs on the tiny subset:
- reports/eval/summary_tiny.csv containing Baseline 0 and Baseline 1 rows
- Optional debugging outputs:
  - reports/eval/per_execution_baseline0_as_is_tiny.csv
  - reports/eval/per_execution_baseline1_p95_tiny.csv (and/or p99)

Reportable outputs (week subset):
- reports/eval/summary_week.csv (overall + confidence tier breakdown)
- Tradeoff artifacts (optional but preferred):
  - risk–efficiency curve plots for percentile/margin sweeps

---

## 7) Feasibility Guardrails (if week subset is too large)
Fallback options in order:
1) Reduce window to 3–5 days
2) Reduce columns to the minimum needed (requests + peaks + timestamps + job keys)
3) Use a prepared export shared via Drive (preferred for consistency)
4) Proceed CPU+memory only; keep GPU optional until feasible

---

## 8) Ownership and Updates
- Owner (data plan + subset coordination): Meghana Koti
- Tiny subset artifact creation: Sofia Silva, Sonali Lonkar


This document will be updated as the team finalizes the reportable week subset and export method.