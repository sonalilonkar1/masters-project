# Resource Central Baseline Experiment Pipeline

## 1. Purpose

This document describes the baseline experiment pipeline used for the Resource Central–based phase of TraceAdvisor. The purpose of this phase is to establish a clear, reproducible evaluation framework using a production Azure VM workload trace to study resource over-provisioning and demand estimation.

The current phase focuses on:
- extracting per-VM historical usage behavior,
- computing statistical summaries (mean, percentiles),
- comparing mean-based vs percentile-based provisioning strategies,
- evaluating how well these estimates capture actual demand.

This baseline phase creates a historical-demand estimation foundation that later TraceAdvisor models can build upon.

---

## 2. Why Resource Central was chosen

Resource Central was chosen because it provides real production evidence that VM resource usage is stable over time for recurring workloads, enabling accurate prediction of future demand using historical statistics.

The paper shows that:
- many Azure VMs are consistently underutilized,
- simple statistics like P95 usage outperform mean-based estimates for safe provisioning,
- historical behavior can reduce waste without sacrificing reliability.

This makes Resource Central highly relevant to TraceAdvisor because it:
- validates history-based resource prediction,
- aligns with risk-aware provisioning (P95/P99),
- provides a strong baseline for comparison.

---

## 3. Dataset used

We use the Azure 2017 VM workload trace, which contains production telemetry for virtual machines, deployments, and subscriptions.

The following files are used in this pipeline:

- `vm_cpu_readings-file-1-of-125.csv.gz`  
  - time-series CPU utilization data per VM  
  - used to compute mean and percentile statistics  

- `vmtable.csv.gz`  
  - VM metadata (VM IDs, configurations, mappings)  
  - used to group and identify individual VMs  

- `deployment.csv.gz`  
  - deployment-level metadata  
  - provides context for VM grouping and structure  

- `subscriptions.csv.gz`  
  - subscription-level metadata  
  - used for higher-level grouping and filtering  

These datasets are combined to construct a per-VM view of CPU usage over time, enabling historical demand analysis and statistical summary computation.

### Dataset characteristics

- large-scale production Azure trace  
- multi-file, compressed (`.csv.gz`) format  
- time-series CPU readings across many VMs  
- hierarchical structure:
  - subscription → deployment → VM  

This structure allows analysis at the VM level while preserving higher-level organizational context.

---

## 4. What this phase is trying to reproduce

This phase does not reproduce the full Resource Central system (e.g., cluster scheduler or migration policies).

Instead, it reproduces the core TraceAdvisor-relevant idea:

### 4.1 Historical demand estimation
- mean CPU usage per VM
- percentile CPU usage per VM (P90, P95, P99)

### 4.2 Safe vs naive provisioning comparison
- mean-based provisioning (naive baseline)
- P95-based provisioning (risk-aware baseline)

### 4.3 Demand classification
- bucketize VM usage levels
- compare whether mean and P95 fall into the same demand category

This quantifies how often mean underestimates real demand.

---

## 5. High-level pipeline
Raw Azure VM trace
- cleaning and parsing
- per-VM grouping
- statistical summary computation (mean, percentiles)
- bucketization of demand levels
- comparison of mean vs P95 estimates
- metric computation and output generation

---

## 6. Notebook structure

The implementation is organized into one notebook:

**Notebook:** `resource_central.ipynb`

**Purpose:**
- load Azure VM data
- compute per-VM CPU statistics
- compare mean vs percentile estimates
- generate evaluation metrics and outputs

**Main outputs:**
- per-VM summary dataset
- bucket comparison metrics
- confusion matrix
- report-ready figures

---

## 7. Data preparation pipeline

### 7.1 Data cleaning
- load Azure VM dataset
- ensure CPU usage is numeric
- remove invalid or missing values
- group data by VM ID

### 7.2 Per-VM aggregation

For each VM:
- mean CPU usage
- P90 CPU
- P95 CPU
- P99 CPU

---

## 8. Demand estimation formulation

For each VM:

**Mean baseline:**
- average CPU usage

**P95 baseline:**
- 95th percentile CPU usage

**Interpretation:**
- mean → efficient but risky
- P95 → safer but more conservative

---

## 9. Demand bucketization

VMs are grouped into usage buckets (e.g., low / medium / high) based on CPU levels.

Each VM gets:
- bucket based on mean
- bucket based on P95

This enables classification-style comparison and confusion matrix analysis.

---

## 10. Baseline comparison

### 10.1 Mean baseline
- uses average CPU
- expected to underestimate peak demand

### 10.2 P95 baseline
- uses high-percentile CPU
- expected to capture peak demand more safely

---

## 11. Evaluation procedure

For each VM:
1. compute mean and percentile statistics
2. assign demand buckets
3. compare mean-based vs P95-based bucket
4. compute dataset-level metrics

---

## 12. Evaluation metrics

### 12.1 P95 vs Mean gap
- average difference between P95 and mean
- median difference

### 12.2 Bucket accuracy
- fraction of VMs where mean bucket equals P95 bucket

### 12.3 Bucket precision / recall
- how well mean predicts higher-demand buckets

### 12.4 Confusion matrix
- distribution of misclassification across buckets

### 12.5 Support
- number of VMs per bucket

---

## 13. Main outputs

### Tables
- `resource_central_per_vm_summary.parquet`
- `resource_central_bucket_metrics.csv`
- `resource_central_vm_level_results.csv`
- `resource_central_confusion_matrix.csv`
- `resource_central_baseline_metadata.csv`

### Figures
- mean vs P95 CPU comparison plot
- distribution of (P95 − mean)
- bucket comparison visualization

---

## 14. What this phase does and does not do

### This phase does
- use real Azure VM workload data
- compute historical CPU statistics
- compare mean vs percentile provisioning
- quantify underestimation behavior
- generate reproducible outputs

### This phase does not yet do
- time-aware replay evaluation
- dynamic workload modeling
- scheduling or migration logic
- predictive modeling

---

## 15. Relevance to TraceAdvisor

This Resource Central phase supports TraceAdvisor in three ways:

1. **Historical baseline foundation**  
   Establishes that past usage can predict future demand  

2. **Risk-aware provisioning insight**  
   Shows why percentile-based estimates (P95/P99) are necessary  

3. **Simple baseline for comparison**  
   Provides a strong reference point before introducing learning-based models  

---

## 16. Next step after this baseline phase

The next phase will:
- incorporate time-aware behavior
- move from static summaries to prediction
- integrate with replay-based evaluation
- compare against ModServe baselines

---

## 17. One-sentence summary

The Resource Central experiment pipeline analyzes Azure VM workloads by comparing mean and percentile-based demand estimates, demonstrating how historical high-percentile usage provides a safer baseline for resource provisioning than average-based methods.