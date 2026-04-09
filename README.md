# TraceAdvisor: Pre-Execution Resource Recommendations for Recurring Cluster Workloads

**Project Workbook v2** - Updated March 9, 2026  
**Current Status**: Baseline implementation and evaluation complete. Ready for ML modeling phase (Semester B).

## Project Summary

TraceAdvisor is a trace-driven advisory system that generates pre-execution CPU, memory, and GPU recommendations for recurring cluster workloads. Using offline analysis of production traces, it identifies recurring jobs, computes risk-aware percentile-based resource envelopes (P90/P95/P99), and provides safe-minimum allocation guidance at job submission time—before resources enter the scheduler. The system operates as a non-intrusive advisory layer requiring no scheduler modification.

**Key Innovation**: Shifts inefficiency correction upstream from runtime scheduling to pre-execution submission time, reducing over-provisioning at the source rather than compensating for it at runtime.

---

## Quick Links

- **Project Board**: https://github.com/users/sonalilonkar1/projects/2
- **Meeting Logs**: [docs/meetings/](docs/meetings/)
- **References**: [docs/references/References.md](docs/references/References.md)
- **Planning & Assumptions**: [docs/planning/assumptions.md](docs/planning/assumptions.md)

---

## Why TraceAdvisor?

Cloud and AI workloads are consistently over-provisioned because users must choose resources before execution under asymmetric risk. Existing systems optimize scheduling and capacity after submission, but do not help users make better decisions at submission time. TraceAdvisor fills this gap by turning historical execution traces into actionable, risk-aware pre-execution recommendations without modifying schedulers.

---

## What's Novel Here

- **Pre-execution, user-facing** resource recommendations (not scheduler-side optimization at runtime)
- **Percentile-based (P90/P95/P99) peak modeling** for safety against rare tail events, not mean utilization
- **Decision-quality evaluation** (violation rate, under-provisioning, slack reduction) vs. prediction error
- **Time-aware chronological trace replay** preventing information leakage and mirroring real submission order
- **Workload-aware decomposition** inspired by modality-aware and phase-split serving (Splitwise/ModServe)
- **Explicit confidence tiers** reflecting workload stability and history availability
- **Lightweight operation** alongside existing schedulers without requiring deep integration

---

## System Architecture

**High-Level Pipeline** (See Chapter 5 & 7 of Project Workbook for detailed diagrams):

```
Raw Traces → Trace Processing → Job-Level Aggregation → Recurring Workload Grouping 
            ↓
Feature Engineering (Historical peaks, slack, variability)
            ↓
Model Training (Quantile estimation, percentile baselines, ML baselines)
            ↓
Risk-Aware Recommendation Engine (Select percentile level, apply safety margins)
            ↓
Time-Aware Offline Replay Evaluation (Chronological simulation)
            ↓
Artifact Repository & Dashboard (Visualization & decision support)
```

**Key Design Principles**:
- **Offline-First**: All processing and recommendation generation happens before deployment
- **Time-Aware**: Strictly chronological execution prevents data leakage and mimics real-world conditions
- **Recurrence-Focused**: Targets jobs that execute multiple times, where historical patterns are stable
- **Non-Intrusive**: Operates as advisory layer; doesn't require scheduler modification

---

## Baseline Strategies

TraceAdvisor compares against four comparison baselines and three state-of-the-art reference systems:

**Comparison Baselines** (Core TraceAdvisor variants):
1. **Baseline 0 (As-is Requests)**: Original user-submitted resource requests (status quo)
2. **Baseline 1 (Empirical Percentile)**: High-percentile (P90/P95/P99) of historical peaks + safety margin
3. **Baseline 2 (Heuristic Job-Class Multipliers)**: Rule-based workload classification with fixed multipliers
4. **Baseline 3 (ML Point Prediction)**: Regression model + global safety margin (linear/tree-based)

**State-of-the-Art References** (From literature):
- **Resource Central** (Azure VM workloads, 2017): P95-based CPU prediction
- **Splitwise** (LLM inference, 2023): Phase-split token demand modeling
- **ModServe** (Multimodal inference, 2025): Stage-aware (image/text) provisioning

See [docs/baseline_experiments/](docs/baseline_experiments/) for reproducible implementations of all baselines.

---

## Project Structure

### 📊 Data

- **[data/](data/)** - Local dataset storage
  - **raw/** - Raw trace files from various sources
    - `tiny/` - Tiny subset for quick testing
    - `week/` - Week-scale subset for experiments
  - **processed/** - Cleaned and processed data
    - `tiny/` - Processed tiny subset
    - `week/` - Processed week-scale data

**Data Documentation**:
- [docs/data/data-plan.md](docs/data/data-plan.md) - Data collection and preparation strategy
- [docs/data/data_adapter_initial_spec.md](docs/data/data_adapter_initial_spec.md) - Data adapter specifications
- [docs/data/google_clusterdata_2019_analysis.md](docs/data/google_clusterdata_2019_analysis.md) - ClusterData 2019 analysis
- [docs/data/subsetSetup.md](docs/data/subsetSetup.md) - Setup instructions for data subsets

---

### 📔 Notebooks

#### Google Cluster Data 2019 (ClusterData)
- [notebooks/GoogleCluster2019/Experiments_1DayData.ipynb](notebooks/GoogleCluster2019/Experiments_1DayData.ipynb) - 1-day experiment evaluation
- [notebooks/GoogleCluster2019/Experiments_1WeekData.ipynb](notebooks/GoogleCluster2019/Experiments_1WeekData.ipynb) - 1-week experiment evaluation

#### Modserve Experiments
- [notebooks/modserve/01_modserve_trace_eda.ipynb](notebooks/modserve/01_modserve_trace_eda.ipynb) - Exploratory data analysis of modserve traces
- [notebooks/modserve/02_modserve_5min_windows_and_baselines.ipynb](notebooks/modserve/02_modserve_5min_windows_and_baselines.ipynb) - 5-minute window analysis and baseline computation
- [notebooks/modserve/03_modserve_replay_evaluation.ipynb](notebooks/modserve/03_modserve_replay_evaluation.ipynb) - Replay evaluation and performance metrics

#### Subset Analysis
- [notebooks/subset/subset.ipynb](notebooks/subset/subset.ipynb) - Full subset analysis pipeline
- [notebooks/subset/subsetv0.ipynb](notebooks/subset/subsetv0.ipynb) - Initial subset version
- [notebooks/subset/subsetv1.ipynb](notebooks/subset/subsetv1.ipynb) - Updated subset version

---

### 🧪 Experiments & Baselines

**Baseline Documentation**:
- [docs/baseline_experiments/GoogleCluster2019/](docs/baseline_experiments/GoogleCluster2019/)
  - `experiments.md` - ClusterData 2019 baseline setup
  - `runbook.md` - Reproducible execution guide
- [docs/baseline_experiments/modserve/](docs/baseline_experiments/modserve/)
  - `modserve_experiment_pipeline.md` - Modserve baseline pipeline
- [docs/baseline_experiments/resource-central/](docs/baseline_experiments/resource-central/) - Resource-central baseline setup
- [docs/baseline_experiments/splitwise/](docs/baseline_experiments/splitwise/) - Splitwise baseline setup

**Implementation**:
- [src/baselines/](src/baselines/) - Baseline implementations
  - `baseline1_percentile_margin.py` - Percentile margin baseline recommender

---

### 📈 Evaluation

**Evaluation Documentation**:
- [docs/evaluation/evaluation_metrics_v0.md](docs/evaluation/evaluation_metrics_v0.md) - Evaluation metrics definition
- [docs/evaluation/evaluation_output_format.md](docs/evaluation/evaluation_output_format.md) - Output format specifications

**Evaluation Code**:
- [src/eval/evaluator_v0.py](src/eval/evaluator_v0.py) - Core evaluation logic and metrics computation

**Evaluation Results**:

- **[reports/eval/GoogleCluster2019/](reports/eval/GoogleCluster2019/)** - ClusterData 2019 Evaluation
  - **Kaggle Subset** (1.3M rows): P95 achieves **29.2% any-resource violation** (vs 40.1% as-is), 1.01 utilization
  - **1-Day Slice** (745K executions): P95 reduces violations from **92.7% → 30.9%**, P99 to 25.7%
  - **1-Week Slice** (5.5M executions): P95 reduces violations from **94.6% → 22.9%**, P99 to 16.1%
  - Files: `per_execution_baseline*.csv` (per-job metrics), `summary_*.csv` (aggregate stats)
  
- **[reports/eval/modserve/](reports/eval/modserve/)** - Multimodal LLM Inference (Azure)
  - **Fixed Monolith**: 95.3% SLO-safe but 3.5× over-provisioned
  - **Fixed Decoupled (P95 stage-wise)**: 94.7% SLO-safe, slightly better efficiency
  - **Reactive Decoupled**: 5% over-provisioned but only 71.5% SLO-safe (too reactive)
  - **tables/** - Summary metrics: `daily_summary.csv`, `burst_day_summary.csv`, `test_baseline_summary.csv`
  - **figures/** - Visualizations; **logs/** - Experiment logs

- **[reports/eval/resource-central/](reports/eval/resource-central/)** - Azure VM CPU (2017)
  - Bucket analysis: P95 captures high-utilization VMs better than mean estimates
  - 87.1% overall accuracy in utilization range prediction
  
- **[reports/eval/splitwise/](reports/eval/splitwise/)** - LLM Token Demand
  - **Code Workload** (decode-heavy): P95 achieves 100% tail coverage at 11% utilization
  - **Conversation Workload** (balanced): Even median baseline achieves 100% coverage
  - Trade-off: 100% coverage requires 10-12× headroom over mean; 50% coverage sufficient at 1.5× mean

---

### 📚 Documentation

**Main Documentation Folder**: [docs/](docs/)

- **[docs/abstract/](docs/abstract/)** - Project summary and abstract
- **[docs/baseline_experiments/](docs/baseline_experiments/)** - Baseline experiment specifications and runbooks
- **[docs/data/](docs/data/)** - Data specifications and setup guides
  - Data plan, adapter specs, source analysis, subset instructions
- **[docs/evaluation/](docs/evaluation/)** - Evaluation methodology and output formats
- **[docs/meetings/](docs/meetings/)** - Team and advisor meeting notes with decisions and updates
- **[docs/planning/](docs/planning/)** - Project planning documents and assumptions
- **[docs/references/](docs/references/)** - References, citations, and related work

---

### 💻 Source Code

- [scripts/](scripts/) - Data processing and utility scripts
  - `verify_data_setup.py` - Data validation utilities
- [src/baselines/](src/baselines/) - Baseline recommender implementations
- [src/eval/](src/eval/) - Evaluation framework and metrics

---

## Team & Advisor

**Advisor**: Dr. Gheorghi Guzun  
**Last Updated**: March 9, 2026

**Team Structure** (Current Semester A Assignments):

| Team Member | Primary Role | Semester A Deliverables |
|---|---|---|
| **Meghana Koti** (M1) | Data & Trace Pipeline | Data access, canonical jobmetrics, percentile baseline logic, Google/Azure dataset preparation, Splitwise baseline experiments |
| **Sofia Silva** (M2) | Recurrence, Baselines & Workload Characterization | Recurring-job grouping, confidence-tier rules, workload profiling, Resource Central baseline experiments |
| **Sonali Lonkar** (M3) | Modeling, Calibration & Evaluation | Evaluation protocol, BigQuery datasets (1-day/1-week slices), reproducibility setup, ModServe baseline experiments |
| **Shivani Jariwala** (M4) | Product Integration & Decision-Support Interface | CLI/UI workflow, presentation layer, demo packaging, user-facing integration |

---

## Implementation Status (Semester A)

### ✅ Completed
- **Environment & Repository**: Python setup, notebook infrastructure, reproducibility documentation
- **Data Pipeline**: Trace normalization, execution-level aggregation, time-aware dataset construction
- **Google ClusterData 2019 Prototype**: Full pipeline including Kaggle subset, 1-day, and 1-week experiments
- **Baseline Implementation**:
  - **Comparison Baselines**: As-is (Request), Mean, P90, P95, P99 percentile-based
  - **Azure Reference Baselines**: Resource Central (VM CPU), Splitwise (LLM tokens), ModServe (multimodal)
- **Evaluation Framework**: Chronological trace replay, violation metrics, utilization analysis
- **Results from Baselines**:
  - **Google Cluster**: P95 reduces violations from 40.1% (as-is) to 29.2%, with manageable overhead
  - **Splitwise**: Fixed P95 achieves 100% tail coverage at 11-12% utilization (decode-heavy workloads)
  - **ModServe**: Fixed Monolith 95%+ SLO-safe but wasteful; Reactive Decoupled efficient but under-provisioned (71.5% SLO-safe)

### 🔄 In Progress
- **ML Baselines**: Learning-based demand prediction for Google cluster and Azure datasets
- **TraceAdvisor Method**: Final learned recommender combining percentile reasoning with workload-aware features
- **Dashboard/CLI**: User-facing interface for recommendations and what-if analysis

### 📋 Next Milestones (Semester B)
- Refine ML baselines and learned TraceAdvisor method
- Reproduce Resource Central baseline (Azure VM-level)
- Extend Splitwise and ModServe to learned baselines
- Finalize dashboard and CLI interface
- Complete final report and presentation

---

## Project Scope

- **Pre-execution resource planning** (recommendations before job submission)
- **Recurring batch and machine learning jobs** (where historical runs exist)
- **Trace-driven learning** from production cluster workload traces
- **Job-level peak usage modeling** (tail/peak-oriented, P90/P95/P99—not only averages)
- **Multi-resource recommendations** (CPU, memory, GPU simultaneously)
- **Offline evaluation** via time-aware trace replay preventing data leakage
- **Lightweight adoption** alongside existing schedulers (no scheduler modification required)

---

## Data Sources

**Primary Dataset**:
- **Google Cluster Workload Traces (ClusterData 2019 / Borg traces)**  
  https://github.com/google/cluster-data

**Azure Production & Evaluation Datasets**:
- **Resource Central (2017)** - Azure VM container orchestration workload telemetry. Historical CPU utilization baseline.  
  https://github.com/Azure/AzurePublicDataset
- **ModServe (2025)** - Azure multimodal LLM inference service traces (image + text processing with separate resource patterns)
- **Splitwise (2023)** - Azure LLM token-based inference traces (prompt-heavy and decode-heavy phases)

**Additional Reference Datasets**:
- **Alibaba Cluster Trace (2018)** - Alternative production cluster reference  
  https://github.com/alibaba/clusterdata

All datasets are publicly available. See [docs/data/data-plan.md](docs/data/data-plan.md) for detailed descriptions and acquisition instructions.

### Setup Instructions

The full dataset is not included in this repository due to its large size. See [docs/data/subsetSetup.md](docs/data/subsetSetup.md) for subset setup instructions and [scripts/verify_data_setup.py](scripts/verify_data_setup.py) for data validation.

---

## Getting Started

### 📖 Documentation & Planning
1. **Project Workbook**: Full technical documentation (Chapter 1-9)
2. **Assumptions & Planning**: [docs/planning/assumptions.md](docs/planning/assumptions.md)
3. **Meeting Notes**: [docs/meetings/](docs/meetings/) - decisions, updates, weekly progress
4. **References**: [docs/references/References.md](docs/references/References.md) - full bibliography and related work

### 🚀 Running Experiments
1. **Data Setup**: Follow [docs/data/subsetSetup.md](docs/data/subsetSetup.md)
2. **Verify Installation**: `python scripts/verify_data_setup.py`
3. **Google Cluster Experiments**:
   - [notebooks/GoogleCluster2019/Experiments_1DayData.ipynb](notebooks/GoogleCluster2019/Experiments_1DayData.ipynb) - 1-day baseline evaluation
   - [notebooks/GoogleCluster2019/Experiments_1WeekData.ipynb](notebooks/GoogleCluster2019/Experiments_1WeekData.ipynb) - 1-week baseline evaluation
4. **Azure Baseline Experiments**:
   - Modserve: [notebooks/modserve/](notebooks/modserve/) - EDA, baselines, replay evaluation
   - Splitwise & Resource Central: Check [docs/baseline_experiments/](docs/baseline_experiments/)
5. **Review Results**: [reports/eval/](reports/eval/) contains all baseline evaluation outputs

### 💡 Understanding Baselines
See [docs/baseline_experiments/GoogleCluster2019/runbook.md](docs/baseline_experiments/GoogleCluster2019/runbook.md) for step-by-step baseline reproduction and **Chapter 3 (Baseline Approaches)** of the Project Workbook for detailed baseline rationale and design decisions.

---

## Research Foundation

TraceAdvisor synthesizes three consistent research findings into a unified advisory system:

1. **Over-provisioning is Measurable at Scale**: Google Cluster traces show ~50% average utilization; Azure studies confirm underutilization across platforms
2. **Historical Traces Are Predictive**: Production workloads exhibit stable, repeating patterns; Accordia reports 80%+ of batch workloads are recurring  
3. **Percentile-Based Reasoning is Safe**: P95/P99 peaks reliably bound tail events; percentile-guided downsizing (Azure studies) reduces cost without compromising safety

**Gap Addressed**: Existing systems (Resource Central, Splitwise, ModServe) operate at runtime or require online optimization. TraceAdvisor fills the gap with a **lightweight, offline, user-facing** advisory system producing **safe-minimum pre-execution recommendations** for recurring jobs.

For full literature review, see [docs/references/References.md](docs/references/References.md) and **Chapter 1 (Literature Search & State of the Art)** in the Project Workbook.

---

## Key References

- Chowdhury et al., "A Deep Dive into the Google Cluster Workload Traces…," arXiv 2023
- Jeon et al., "Analysis of Large-Scale Multi-Tenant GPU Clusters for DNN Training Workloads," USENIX ATC 2019
- Sandholm et al., "QoS-Based Pricing and Scheduling of Batch Jobs in OpenStack Clouds," arXiv 2015
- Scheinert et al., "On the Potential of Execution Traces for Batch Processing Workload Optimization…," arXiv 2021
- Wilkes et al., Google ClusterData2019 dataset repository

---

## License

MIT License (see [LICENSE])
