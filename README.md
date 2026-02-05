# TraceAdvisor: Pre-Execution Resource Recommendations for Recurring Cluster Workloads

## Project Summary
TraceAdvisor is a pre-execution advisory system that uses historical cluster execution traces to recommend safe-minimum CPU, memory, and GPU requests for recurring batch and machine learning jobs. It summarizes job-level peak usage and variability to produce risk-aware recommendations that operate alongside existing schedulers. TraceAdvisor is evaluated offline using time-aware trace replay to measure fit (violation rate) and efficiency gains (slack reduction).

Abstract: see `docs/abstract/Project_Abstract.docx`.

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

## Problem
Users must choose CPU, memory, and GPU allocations before execution under uncertainty. The asymmetric risk (failures vs. wasted capacity) incentivizes conservative requests and persistent over-provisioning.

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

---

## Core Outputs / Deliverables
- Trace processing pipeline that converts raw events/utilization samples into a job-level dataset
- Per-execution metrics:
  - runtime
  - peak CPU / peak memory / peak GPU usage (conservative reconstruction)
  - slack (requested minus peak-used)
  - stability/variability indicators (history length, variance, retries, sampling sparsity)
- Pre-execution recommendation logic:
  - safe-minimum CPU/memory/GPU with stated coverage/risk (e.g., P95-style bound)
  - confidence tiers (high/medium/low history) and conservative fallback
- Offline trace replay evaluator comparing TraceAdvisor vs baselines
- CLI and/or dashboard demo showing recommendations, expected savings, and risk context
- Final report with results, tradeoffs, assumptions, and limitations

---

## System Overview
1. Trace ingestion (events and utilization samples)
2. Job-level reconstruction (execution boundaries, peaks, slack)
3. Recurring job grouping (identify stable recurring jobs/patterns)
4. Recommendation (safe-minimum based on historical peak bounds with safety margins)
5. Offline validation (time-aware replay: fit, slack reduction, violation rate)
6. Interface (CLI/API/dashboard for what-if and recommendation display)

---

## Phased Project Plan

### Phase 1 — Problem Statement, Scope, and Project Direction
- Finalize goals, scope boundaries, assumptions, success criteria
- Define what safe-minimum means and what risk/coverage level will be reported

### Phase 2 — Trace Processing and Job-Level Dataset Construction
- Build a reproducible pipeline from task/container traces to job-execution records
- Handle retries/speculation and sampling limitations conservatively
- Produce job-level dataset, data dictionary, and documented assumptions

### Phase 3 — Decision-Oriented Modeling and ML Pipeline
- Focus on peak/tail behavior (e.g., P90/P95/P99 bounds)
- Use submission-time features and historical summaries only (avoid leakage)
- Produce calibrated, decision-oriented predictions to improve decision quality

### Phase 4 — Baseline Decision Policies
- Empirical percentile plus fixed safety margin
- Heuristic job-class multiplier baseline
- ML point-prediction baseline plus global margin (no explicit uncertainty bounds)

### Phase 5 — Validation Methodology
- Chronological train/validation/test splits (time-aware)
- Trace replay: check whether observed peak fits within recommendation
- Report results by confidence tier (high/medium/low history)

### Phase 6 — Evaluation Metrics and Impact
- Slack reduction (percent)
- Violation rate (percent; peak exceeds recommendation)
- Risk–efficiency tradeoff curves
- Calibration checks (e.g., “95% bound” contains peaks about 95% of the time on future runs)
- Conservative cost/energy estimates reported as ranges with stated assumptions

### Phase 7 — Novelty, Practical Value, and Adoptability
- Provide pre-execution guidance without scheduler modification or invasive instrumentation
- Target recurring workloads and present explicit risk context
- Deliver a realistic workflow engineers can adopt

### Phase 8 — Assumptions and Limitations
- Recurring workloads and representative historical traces
- Offline replay does not model queueing/placement; sampling may miss instantaneous peaks
- Behavior drift, hardware variability, and correlation-based limits

---

## Evaluation
TraceAdvisor is evaluated by decision quality:
- Slack reduction: decrease over-provisioned CPU/memory/GPU versus original requests
- Safety: low violation rate (peak usage exceeding recommendation)
- Calibration: stated coverage levels align with observed outcomes on future runs
- Tradeoffs: savings versus risk at different coverage targets

---

## Two-Semester Execution Plan

### CMPE 295A (Spring 2026) — Formation + Working Prototype
Goal: end-to-end prototype using trace statistics, strong baselines, and early offline evaluation.

- Week 1: kickoff, roles, repo skeleton, initial scope
- Week 2: advisor alignment; finalize Phase 1 specification
- Week 3 (Feb 6): formation presentation, abstract submission, repo ready
- Weeks 4–6: Phase 2 mini-pipeline on a sample; job-level dataset v0.1
- Week 7 (Mar 6): Workbook 1 submission; pipeline design and early sample results
- Weeks 8–10: scale dataset v1; implement baseline policies and early replay evaluator
- Week 11 (Apr 10): Workbook 2 submission; dataset v1, baselines, preliminary metrics; individual design specs
- Weeks 12–13: stabilize prototype; final workbook and design spec submissions
- Weeks 14–15: advisor demo (early prototype), two report chapters, individual contributions
- Week 16 (May 15): project expo demo

Definition of done for 295A:
- Job-level dataset pipeline (Phase 2) with documented assumptions
- Percentile-based safe-minimum recommendations (Phase 4) with confidence tiers
- Offline trace replay evaluator with initial metrics (Phase 6 initial)
- Basic CLI/dashboard demo for advisor and expo

### CMPE 295B (Fall 2026) — Modeling + Calibration + Full Evaluation + Final Report
Goal: tail-aware modeling, calibrated risk, full comparison vs baselines, final demo and report.

- Week 1: confirm 295A artifacts; lock evaluation protocol
- Week 2: time-aware split and hardened replay evaluator
- Week 3: finalize baselines; first tradeoff curves
- Week 4: quantile/tail modeling v1 for peak CPU/memory (and GPU if feasible)
- Week 5: feature engineering and ablations; leakage checks
- Week 6: calibration layer (coverage validation and conservative adjustment)
- Week 7: decision policy (risk thresholds, margins, candidate configs, cold-start fallback)
- Week 8: integrated demo v2 (model, policy, interface)
- Week 9: full evaluation vs baselines (Phase 6)
- Week 10: robustness and sensitivity (drift inflation, P90 vs P95 vs P99)
- Week 11: optional Alibaba validation or deep-dive error analysis
- Week 12: novelty/adoptability write-up and final demo script
- Week 13: assumptions/limitations and polish
- Week 14: final report integration and presentation rehearsal
- Week 15: final submission and final demo

---

## Team Communication and Meetings
- Team sync: 2x/week (30–45 min)
- Advisor sync: 1x/week
- Meeting logs: `docs/meeting-logs/`
- Task tracking: GitHub Issues/Projects

---

## Planned Repository Structure
- docs/ — abstract, formation materials, meeting logs, design specs
- data/ — local data (ignored in git)
- scripts/ — data extraction and dataset build scripts
- src/ — feature engineering, models, recommendation policies, evaluation
- app/ — CLI or dashboard (Streamlit/Flask)
- reports/ — figures, tables, results summaries

---

## Selected References

1. Chowdhury et al., “A Deep Dive into the Google Cluster Workload Traces: Analyzing the Application Failure Characteristics and User Behaviors,” arXiv:2308.02358, 2023.  
   https://arxiv.org/pdf/2308.02358

2. Zhang et al., “The Elasticity and Plasticity in Semi-Containerized Co-locating Cloud Workload: A View from Alibaba Trace,” ACM EuroSys, 2018.  
   https://www.semanticscholar.org/reader/54ddd67944520f249b906ba4e817188686eae94d

3. You et al., “Analysis of Large-Scale Multi-Tenant GPU Clusters for DNN Training Workloads,” USENIX ATC, 2019.

4. Wilkes et al., “Google Cluster Data (2019),” dataset repository.  
   https://github.com/google/cluster-data

5. Alibaba Cluster Trace (2018), dataset repository.  
   https://github.com/alibaba/clusterdata

6. Deng et al., “GoCJ: Google Cloud Jobs Dataset for Distributed and Cloud Computing Infrastructures,” MDPI Data, 2018.

7. Kumar et al., “Analysis and Clustering of Workload in Google Cluster Trace based on Resource Usage,” arXiv:1501.01426, 2015.  
   https://arxiv.org/pdf/1501.01426

8. Sundaresan et al., “A Tail Latency SLO Guaranteed Task Scheduling Scheme for User-Facing Services,” IEEE, 2025.  
   https://ieeexplore.ieee.org/document/10891045

9. Sharma et al., “JADE: Tail-Latency-SLO-Aware Job Resource Allocation and Scheduling,” IEEE, 2020.  
   https://ieeexplore.ieee.org/document/9302789

10. Shen et al., “TailGuard: Tail Latency SLO Guaranteed Task Scheduling,” IEEE, 2023.  
    https://ieeexplore.ieee.org/document/10272394

11. Chen et al., “QoS-Based Pricing and Scheduling of Batch Jobs in OpenStack Clouds,” 2015.  
    https://arxiv.org/pdf/1504.07283

12. Kosaian et al., “On the Potential of Execution Traces for Batch Processing Workload Optimization in Public Clouds,” NSDI 2022 (arXiv:2111.08759).  
    https://arxiv.org/pdf/2111.08759

13. Chowdhury et al., “Eva: Cost-Efficient Cloud-Based Cluster Scheduling,” SIGMOD 2025 (arXiv:2503.07437).  
    https://arxiv.org/pdf/2503.07437

14. Bhattacharyya et al., “Scavenger: A Cloud Service for Optimizing Cost and Performance of ML Training,” 2023.  
    https://ieeexplore.ieee.org/document/10171474

15. Yadwadkar et al., “CherryPick: Adaptively Unearthing the Best Cloud Configurations for Big Data Analytics,” NSDI 2017.  
    https://www.usenix.org/conference/nsdi17/technical-sessions/presentation/alipourfard

16. Nagaraj et al., “Improving Resource Utilization in Data Centers using an LSTM-based Prediction Model,” IEEE, 2019.  
    https://ieeexplore.ieee.org/document/8891022

17. Tighter et al., “Machine Learning Based Prediction and Classification of Computational Jobs in Cloud Computing Centers,” arXiv:1903.03759, 2019.  
    https://arxiv.org/pdf/1903.03759

License: MIT (see LICENSE).
