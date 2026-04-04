# TraceAdvisor: Pre-Execution Resource Recommendations for Recurring Cluster Workloads

## Project Summary
TraceAdvisor is a pre-execution advisory system that uses historical cluster execution traces to recommend safe-minimum CPU, memory, and GPU requests for recurring batch and machine learning jobs. It summarizes job-level peak usage and variability to produce risk-aware recommendations that operate alongside existing schedulers. TraceAdvisor is evaluated offline using time-aware trace replay to measure fit (violation rate) and efficiency gains (slack reduction).

Abstract: see `docs/abstract/Project_Abstract.docx`.

---

## Important Links
- Project board (GitHub Projects): https://github.com/users/sonalilonkar1/projects/2
- Meeting logs folder: `docs/meetings/`
- References/Zotero export: `docs/references/`
- **Getting Started**: See [Experiments Guide](docs/experiments.md) and [Runbook](docs/runbook.md) for reproducible pipeline

---

## Why TraceAdvisor?
Cloud and AI workloads are consistently over-provisioned because users must choose resources before execution under asymmetric risk. Existing systems optimize scheduling and capacity after submission, but do not help users make better decisions at submission time. TraceAdvisor fills this gap by turning historical execution traces into actionable, risk-aware pre-execution recommendations without modifying schedulers.

---

## What’s Novel Here
- Pre-execution, user-facing resource recommendations (not scheduler-side optimization)
- Tail- and peak-oriented modeling for safety, not mean utilization
- Decision-quality evaluation (violation rate and slack reduction), not prediction error
- Time-aware trace replay that mirrors real submission order
- Explicit risk/coverage reporting to support conservative adoption

---
```md
## Workflow

+------------+
| Raw Traces |
+------------+
      |
      v
+-------------------------+
| Job-Level Reconstruction|
+-------------------------+
      |
      v
+---------------------+
| Historical Summaries|
+---------------------+
      |
      v
+-----------------------------+
| Safe-Minimum Recommendation |
+-----------------------------+
      |
      v
+------------------------------+
| Time-Aware Trace Replay Eval |
+------------------------------+
      |
      v
+---------------------+
| CLI / Dashboard     |
+---------------------+
```
---

## Team & Advisor
Advisor: Dr. Gheorghi Guzun

Team Members (4):
- Sofia Silva: Trace Pipeline
- Meghana Koti: Recurrence + Baselines (Slack Analysis)
- Sonali Lonkar: Quantile Modeling + Calibration + Evaluation
- Shivani Jariwala: Decision Support Interface

---

## Scope

- Pre-execution resource planning (recommendations before job submission)
- Recurring batch and machine learning jobs (where historical runs exist)
- Trace-driven learning from Google Cluster Workload Traces (ClusterData2019)
- Job-level summaries of peak usage and variability (tail/peak-oriented, not only averages)
- Offline evaluation via time-aware trace replay
- Lightweight adoption alongside schedulers (no scheduler modification)

---

## Data
Primary dataset:
- Google Cluster Workload Traces (ClusterData2019 / Borg traces)  
  https://github.com/google/cluster-data

Optional validation dataset:
- Alibaba Cluster Trace Program (2018)  
  https://github.com/alibaba/clusterdata

### Subset Setup
- The dataset is not included in this repository due to its large size.
- Subset setup instructions: `docs/subsetSetup.md`

---
Quick Start

To reproduce the baseline experiments and evaluation:

1. **Prerequisites**: BigQuery access (`traceadvisor-295a` project) and GCS access (`traceadvisor-exports-295a`)
2. **BigQuery derivation**: See `docs/experiments.md` for SQL and data preparation
3. **Local/Colab execution**: Follow `docs/runbook.md` for step-by-step instructions
4. **Python dependencies**: `pip install -U pandas numpy pyarrow gcsfs google-cloud-storage google-cloud-bigquery`

---

## 295A Sprint Plan 
- Sprint 1–2: subset-first data plan, repo scaffolding, evaluation metric definitions
- Sprint 3–4: job-level dataset v0.1 → v1 (subset), recurrence grouping, sanity checks
- ✅ Sprint 5–6: baseline recommenders + offline replay evaluation + initial tradeoff curves
- Sprint 7: demo-ready TraceAdvisor v1 (baseline/statistics-based) + reproducible runbook

(Full sprint/issue breakdown is tracked in the GitHub Project board. Latest: Sprint 2 baseline experiments and evaluation framework complete
### New Documentation
- **`docs/experiments.md`** — Complete pipeline documentation covering BigQuery-based trace derivation, dataset rationale, and experiments on 1-day/1-week Google ClusterData2019 subsets
- **`docs/runbook.md`** — Reproducible instructions for: BigQuery queries, GCS exports, baseline execution, and evaluation output generation

### Evaluation Results
- Baseline experiments (baseline0 "as-is" vs baseline1 "percentile sizing") on 1-day and 1-week subsets
- Results in `reports/eval/`: summary statistics and per-execution metrics
- Decision quality metrics: violation rate (safety) and slack (efficiency proxy)

---

## 295A Sprint Plan 
- Sprint 1–2: subset-first data plan, repo scaffolding, evaluation metric definitions
- Sprint 3–4: job-level dataset v0.1 → v1 (subset), recurrence grouping, sanity checks
- Sprint 5–6: baseline recommenders + offline replay evaluation + initial tradeoff curves
- Sprint 7: demo-ready TraceAdvisor v1 (baseline/statistics-based) + reproducible runbook

(Full sprint/issue breakdown is tracked in the GitHub Project board.)

## Meetings & Task Tracking
- Team sync: 2x/week (1 hour)
- Advisor sync: 1x/week
- Meeting logs: `docs/meetings/`
- Task tracking: GitHub Issues + GitHub Projects (board)

## Repository Structure 
- `docs/` — documentation and resources
  - `experiments.md` — experiments guide and BigQuery pipeline for trace derivation
  - `runbook.md` — reproducible step-by-step instructions for local/Colab execution
  - `data-plan.md` — data acquisition and processing strategy
  - `evaluation_metrics_v0.md` — evaluation metric definitions
  - `subsetSetup.md` — instructions for setting up dataset subsets
  - `meetings/` — advisor and team meeting notes
  - `references/` — bibliography and external links
- `scripts/` — ingestion and dataset build utilities
- `src/` — core recommendation and evaluation modules
  - `baselines/` — baseline recommender implementations (e.g., percentile-based sizing)
  - `eval/` — evaluation framework and metrics computation
- `reports/` — evaluation results and figures
  - `eval/` — summary CSVs and per-execution traces
- `data/` — local dataset caches (gitignored for size)
- `app/` — CLI or dashboard (in development)

## Key References
(Full list in `docs/references/`.)
- Chowdhury et al., “A Deep Dive into the Google Cluster Workload Traces…,” arXiv 2023.
- Jeon et al., “Analysis of Large-Scale Multi-Tenant GPU Clusters for DNN Training Workloads,” USENIX ATC 2019.
- Sandholm et al., “QoS-Based Pricing and Scheduling of Batch Jobs in OpenStack Clouds,” arXiv 2015.
- Scheinert et al., “On the Potential of Execution Traces for Batch Processing Workload Optimization…,” arXiv 2021.
- Wilkes et al., Google ClusterData2019 dataset repository.

## License
MIT License (see `LICENSE`).
