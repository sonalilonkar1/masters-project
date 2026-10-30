# TraceAdvisor: Pre-Execution Resource Recommendations for Recurring Cluster Workloads

CMPE 295B Master's Project — Final Report — Chapters 2–9 (DRAFT)

Shivani Jariwala, Meghana Koti, Sonali Lonkar, Sofia Silva — Advisor: Dan Harkey

> **Draft status note (remove before submission).** This draft covers Chapters 2–9 of the submitted Table of Contents. Chapter 1 is already submitted and is not repeated. Text in the form [TBD — …] is a placeholder for work that is not yet built or decided; each placeholder names the backlog issue, pull request, or open decision that will fill it. Every number in this draft that describes the Google pipeline comes from a saved artifact or notebook output listed in REPORT_TRACEABILITY.md. Numbers labeled "validation" come from the validation split only. No final-test result exists yet; final Google results will come only from the one-time final-test evaluation (backlog Issue 12). Status labels used throughout: **implemented** (merged on `main`), **in review** (open pull request), and **planned** (backlog item not yet built). Repository state described: `origin/main` at commit a0b3c77 (PR #70 and PR #72 merged); PR #61 still open.

## List of Figures (entries for Chapters 2–9)

- Figure 2.1. TraceAdvisor Google pipeline and its status, with artifact counts at each stage.

## List of Tables (entries for Chapters 2–9)

- Table 2.1. Implementation status of TraceAdvisor components.
- Table 5.1. Validation comparison of CPU and memory regression models (Notebook 05, PR #61, in review).
- Table 6.1. Chronological split summary (Notebook 04).
- Table 7.1. Validation comparison of baseline policies at the selected min_runs = 1 (Notebook 04).

# Chapter 2. Project Architecture

## 2.1 Introduction and System Overview

TraceAdvisor is an offline advisory system that turns historical cluster traces into pre-execution CPU and memory recommendations for recurring workloads. It runs beside a scheduler and does not modify it: the system reads a trace, reconstructs what each recurring workload used in the past, and recommends a CPU and memory allocation for the workload's next launch. Recommendations are evaluated by replaying the trace in chronological order, so that every recommendation uses only information that would have been available at submission time.

The 295B implementation is organized as a sequence of notebooks in `pipelines/google_subset/` that exchange versioned artifacts, plus shared Python modules in `src/evaluation/` and `src/features/`. The canonical modeling and evaluation unit is the **full-workload occurrence**: all executions of one recurring workload that start at the same time, identified by `occurrence_key = recurrence_key || execution_start_time_us`. The core policy comparison planned for 295B is Request, Mean, P90, P95, P99, ML-only, and Hybrid, all evaluated against the same targets by one shared evaluator.

Figure 2.1 shows the pipeline with the artifact counts produced at each stage, and Table 2.1 lists which components are implemented, in review, or planned.

![Figure 2.1](figures/fig_2_1_pipeline.png)

*Figure 2.1. TraceAdvisor Google pipeline and its status, with artifact counts at each stage. Solid boxes are implemented on `main`, the dashed box is in an open pull request (PR #61), and the dotted box is planned. Counts are read from the saved artifacts by `docs/project_report/scripts/make_report_artifacts.py`.*

*Table 2.1. Implementation status of TraceAdvisor components.*

| Component | Location | Status |
|---|---|---|
| Raw data quality review (N00) | `pipelines/google_subset/00_dataQualityReview.ipynb` | Implemented |
| Ingestion and canonical observations (N01) | `01_dataIngestion.ipynb` | Implemented |
| Execution reconstruction (N02) | `02_reconstructExecutions.ipynb` | Implemented |
| Occurrence aggregation and point-in-time history (N03) | `03_buildProfilesAndMetrics.ipynb` | Implemented |
| Chronological split, next-occurrence targets, Request/Mean/P90/P95/P99 baselines (N04) | `04_splitAndBaselines.ipynb` | Implemented |
| Shared metrics and evaluator | `src/evaluation/` | Implemented |
| Chronological split utility | `src/features/split_utils.py` | Implemented |
| ML feature contract, tuning, model lock, ML predictions (N05) | `05_evaluateRecommendations.ipynb`, `src/features/` | In review (PR #61) |
| External dataset semantics study, canonical schema (v0.1.0), adapter framework, Alibaba 2018 and Azure VM adapters | `docs/data/`, `src/canonical/`, `src/adapters/`, `config/` | Implemented (PR #70, merged) |
| Downstream history, profile, and ML-ready preparation for Alibaba and Azure VM | New Issue 4 (GitHub #66, open) | Planned |
| Proposed revision of the external-dataset scope (Alibaba GPU v2020 as the required second dataset; Azure deferred) | `docs/data/alibaba_dataset_selection_feasibility.md`, `docs/data/canonical_contract_decisions.md` (PR #72, merged as documentation) | Proposed design; not implemented; awaiting team acceptance |
| Hybrid construction and comparison of all seven policies through the shared evaluator (N06) | not yet created | Planned |
| Decision freeze and final decision manifest | backlog Issue 11 | Planned |
| One-time final-test evaluation | backlog Issue 12 | Planned |
| Explainability and failure analysis | backlog Issue 13 | Planned |
| Common recommendation output interface | New Issue 5 | Planned |
| Objective-driven Hybrid policy engine | New Issue 6 | Planned |
| Read-only API, UI simulation, UI–API integration and demo | New Issues 7, 8, 9 | Planned |
| Dataset-specific ML for Alibaba and Azure VM | Issues 06–08 (external datasets) | Planned (role of external datasets still to be confirmed; scope document Section 7) |

## 2.2 Architecture Subsystems

The architecture has six subsystems. Each owns one stage of the data's meaning, and later stages consume earlier artifacts without recomputing them.

### 2.2.1 Data Ingestion and Dataset Adapters

For Google, ingestion is implemented in Notebooks 00 and 01. Notebook 00 audits the raw Kaggle sample of Google ClusterData 2019 without changing it. Notebook 01 parses the dictionary-encoded resource fields, creates canonical timestamp and resource columns, and saves one row per instance observation (one `collection_id`, `instance_index`, `machine_id`, and usage window) (`google_subset_observations_v1.parquet`). No rows are filtered and no units are converted at this stage.

For other datasets, the revised 295B plan separates dataset-specific ingestion from shared logic through a canonical workload schema and per-dataset adapters (New Issues 1–4). This work is merged on `main` through PR #70, which adds a dataset semantics study for Alibaba Cluster Trace 2018 and the Azure VM trace, a canonical schema (version 0.1.0) with capability flags, an adapter base class with output validation, and Alibaba and Azure VM adapters. Adapters map source fields into canonical fields; they do not compute percentiles, ML predictions, Hybrid decisions, or evaluator metrics. The adapters stop at canonical source records: building history, profiles, and ML-ready inputs for Alibaba and Azure VM remains open under New Issue 4 (GitHub #66). A later documentation-only change (PR #72) proposes a different external-dataset scope (Section 3.3.2); it changes no code.

### 2.2.2 Execution Reconstruction and Occurrence Modeling

Notebook 02 groups raw observations into executions. A raw `collection_id + instance_index` group is treated only as a candidate; it is split into separate execution episodes wherever a time gap longer than one five-minute observation window occurs. Each execution is linked to a recurring workload through `recurrence_key = user || logical workload name`.

Notebook 03 then combines all executions of a recurrence that start at the same time into one **occurrence**. An occurrence's peak CPU and memory are computed by summing usage across parallel executions within each aligned usage window and taking the largest window total. This full-workload definition replaces the earlier practice of using the largest individual execution peak (backlog Issue 01).

### 2.2.3 Historical Features and Time-Ordered Data

For each occurrence, Notebook 03 builds a point-in-time history from earlier occurrences of the same recurrence that had fully completed by the current occurrence's start time. Notebook 04 then splits occurrences chronologically into training, validation, and test partitions without dividing any start-time group, and attaches a target to each occurrence: the full-workload CPU and memory peak of the next distinct occurrence of the same recurrence. A row therefore represents the state at the start of the current occurrence, and the target is what the next launch actually used.

### 2.2.4 Recommendation Engine

The recommendation engine produces CPU and memory recommendations for each occurrence under several policies:

- **Historical baselines (implemented, N04):** Request, Mean, P90, P95, and P99 of completed-occurrence history, with a minimum-history threshold (`min_runs`) and a fallback to the current request.
- **ML-only (in review, PR #61):** per-resource regression models that predict the next occurrence's peak.
- **Hybrid (planned, N06 and New Issue 6):** the revised plan's starting rule is HybridCPU = max(MLPredictedCPU, P95CPU) and HybridMemory = max(MLPredictedMemory, P95Memory). New Issue 6 extends this into an objective-driven policy engine with Conservative, Balanced, and Efficient objectives.

### 2.2.5 Shared Metrics and Evaluation Framework

All policies are scored by one shared evaluator (`src/evaluation/metrics.py` and `src/evaluation/evaluator.py`). The metric formulas (CPU, memory, and any-resource violation; bounded utilization; waste; shortfall) are defined once in `metrics.py`. The evaluator applies them to any table that names its actual and recommended columns, and reports valid-row denominators for each violation and utilization metric. The revised plan requires the same evaluator to be used for Google, Alibaba, and Azure VM.

### 2.2.6 Artifact Repository and Presentation Layer

Notebooks 01–05 write Parquet, CSV, JSON, and (for N05) serialized model files to `data/processed/google_subset_v1/`. These files are the handoff contract between stages; `metadata.json` (N04) and `ml_metadata.json` (N05) record the definitions and decisions used. Raw and processed data are not committed to the repository.

The presentation layer is planned. The revised plan defines a common recommendation output interface (New Issue 5), a read-only API over saved artifacts (New Issue 7), a UI for selecting a dataset and objective (New Issue 8), and an integrated end-to-end demo (New Issue 9). [TBD — presentation-layer architecture after New Issues 5–9.]

# Chapter 3. Technology Descriptions

## 3.1 Data Processing and Analysis Stack

The pipeline is written in Python and runs as Jupyter notebooks; the notebooks locate the repository root; Notebooks 00 and 01 also include Google Colab setup. Tabular processing uses pandas and NumPy, and intermediate artifacts are stored as Apache Parquet files through PyArrow. matplotlib is listed in `requirements.txt`; the pipeline notebooks produce tables rather than figures. Shared logic lives in importable modules under `src/`, and unit tests use pytest (configured by `pytest.ini`). The dependencies are listed in `requirements.txt`.

The versions recorded by Notebook 05 in `ml_metadata.json` are Python 3.12.15, pandas 2.3.3, NumPy 2.5.4, scikit-learn 1.9.1, and XGBoost 3.4.1. The data setup guide (`docs/data/subsetSetup.md`) records Python 3.12.4 as the environment used for the original subset setup. [TBD — final pinned environment and versions for the release (Issue 16).]

## 3.2 Machine Learning Libraries and Models

The ML stage (Notebook 05, in review in PR #61) uses scikit-learn and XGBoost:

- **Models:** Decision Tree, Random Forest, and XGBoost regressors, trained separately for CPU and for memory.
- **Model selection:** scikit-learn `GridSearchCV` with expanding-window `TimeSeriesSplit` folds that keep whole timestamp groups together and purge training labels that fall in the fold's validation block; `GroupKFold` grouped by `recurrence_key` is reported only as a robustness check.
- **Persistence:** locked models are saved as `joblib` files (`n05_locked_models/cpu_random_forest.joblib`, `memory_random_forest.joblib`).

Regression is the primary sizing method. The backlog keeps classification only as supporting analysis unless it is wired into policy logic. The current occurrence-level Notebook 05 contains regression only. [TBD — team to confirm whether any classification analysis will be reported.]

## 3.3 Dataset and Trace Sources

### 3.3.1 Primary Dataset: Google ClusterData 2019

The primary dataset is Google ClusterData 2019, the Borg cluster workload traces published by Google [6]. In the full traces, collection metadata, instance lifecycle events with resource requests, and windowed instance usage are stored in separate tables (CollectionEvents, InstanceEvents, and InstanceUsage), according to the team's analysis in `docs/data/google_clusterdata_2019_analysis.md`.

The 295B pipeline uses a publicly available Kaggle sample of these traces (`borg_traces_data.csv`; setup in `docs/data/subsetSetup.md`) [TBD — add the Kaggle sample to docs/references/References.md before citing it]. The sample has 405,894 rows and 34 columns. Each row joins event fields (`time`, `event`, `failed`) with usage-window fields (`start_time`, `end_time`, `average_usage`, `maximum_usage`) and request fields (`resource_request`). Interpreted as microseconds, the usage start times span about 31 days (30.9965 days in the Notebook 00 output). Processing the full ClusterData 2019 traces is not required to close the project if compute or storage makes it impractical; larger-scale validation can be a documented limitation (backlog, p. 20).

### 3.3.2 Validation Datasets: Azure Resource Central, Alibaba, ModServe, and Splitwise

The submitted Table of Contents names four external validation datasets. The backlog changed this scope after the TOC was submitted, and the change is not fully settled:

- **Active external datasets (revised plan):** Alibaba and Azure VM. In the revised plan, the original external-dataset issues (04 Resource Central, 04A Splitwise, 04B ModServe, 05 Alibaba) are "Replaced or pending": "Active work becomes New Issues 1 and 4 for Alibaba and Azure VM" (backlog, p. 21). The Azure VM track uses the public Azure VM trace (Azure Public Dataset V2). The semantics study merged with PR #70 (`docs/data/dataset_semantics_study_FINAL.md`) notes that this trace is used for the Azure VM / Resource Central [5] validation direction but is "not a direct export of the internal Resource Central service."
- **Alibaba Cluster Trace 2018** [8]: according to the semantics study (`docs/data/dataset_semantics_study_FINAL.md`), which cites the official documentation, the trace covers about 4,000 machines over 8 days, uses trace-relative timestamps in seconds, and follows a job → task → instance model with task-level planned resources and instance-level observed CPU and memory.
- **Azure VM trace**: according to the same study, the trace spans 30 days and contains VM metadata (including vCPU and memory-capacity buckets) and five-minute CPU utilization readings, but no observed memory time series. The repository labels this dataset Azure Public Dataset V2 (2019), but the later feasibility analysis (`docs/data/alibaba_dataset_selection_feasibility.md`, Section 8.1) reports that the sample data actually used is the 2017 V1 trace. It bases this on the core-count and memory bucket values, the subscription and deployment counts, and the mean CPU values in the first 10,001 VM-table rows, and notes that the Resource Central notebook on `main` loads a file from the 125-file V1 CPU-reading set. Both versions span 30 consecutive days according to that analysis. [TBD — confirm which Azure trace version the adapter targets, and add the confirmed Azure Public Dataset version to docs/references/References.md before citing it.]
- **Proposed scope change (PR #72, documentation only):** `docs/data/alibaba_dataset_selection_feasibility.md` and `docs/data/canonical_contract_decisions.md` recommend Alibaba GPU Cluster Trace v2020 [8] as the required full second-dataset integration, because its official `group` tag provides recurrence (reported to cover 99.86% of jobs). They keep Alibaba 2018 as an optional reduced adapter demonstration and defer Azure. Under that design, CPU would be evaluated only as a lifetime average (the trace has no CPU peak), and no any-resource metric would be reported. `canonical_contract_decisions.md` states that it is a design document only, that none of its decisions is implemented, and that it can become the basis for the schema and adapters once the team accepts it. This proposal differs from the revised backlog plan (Alibaba and Azure VM active). [TBD — team decision on the external-dataset scope (revised plan vs. the PR #72 proposal).]
- **Splitwise and ModServe:** the revised plan keeps them "outside the active external-dataset implementation until the team or advisor confirms that they are mandatory" (backlog, p. 31). The original issue list called them required. This conflict is open in the 295B scope document (Section 7). Earlier 295A experiments exist for both, but the backlog requires that stale 295A numbers not be reused without rerunning and validating them. [TBD — team/advisor decision on Splitwise and ModServe; if confirmed, describe their adapters here.]

## 3.4 Dataset Adapters and Unit Normalization

**Google (implemented).** Google trace resource values are kept in their native normalized units; no unit conversion is applied. CPU fields carry the suffix `_ncu` (for example `requested_cpu_ncu`) and memory fields the suffix `_normalized`. Timestamps are kept in microseconds. Notebook 01 maps the parsed raw values to six canonical columns (requested, average, and peak CPU and memory) and keeps the original `raw_*` columns for traceability.

**Canonical schema and adapters (implemented, PR #70 merged).** The canonical schema keeps workload identity and recurrence identity separate, and keeps request, allocation, observation, peak, actual, and recommendation as separate resource semantics. Every populated resource value carries an explicit unit field (for example `ncu`, `vcpu`, `percent`, `normalized`, `gb`); the schema does not force one unit, and the evaluator may compare only actual and recommended values in matching units. Missing and unsupported values stay null and are never converted to zero. Coarse capability flags (`supports_cpu`, `supports_memory`, `supports_request`, `supports_recurrence`, `supports_targets`, `supports_ml`) record what each dataset can support. Unit labels must come from an allowed set defined in `src/canonical/schema.py`. The set includes dataset-specific Alibaba 2018 labels (`alibaba_plan_cpu_100_per_core`, `alibaba_cpu_usage_source_unit`, `alibaba_memory_source_normalized`), so Alibaba source units are not relabeled as generic units. Validation enforces the capability flags: it rejects populated CPU or memory fields, including actual and recommended values, for an unsupported resource, and populated actual values when a dataset does not support targets. In the capability configuration (`config/dataset_capabilities.json`), Google supports all six; Alibaba 2018 supports CPU, memory, and request but not yet recurrence, targets, or ML; and Azure VM V2 supports CPU and memory capacity but not explicit request, observed memory, recurrence, targets, or ML.

## 3.5 Artifact Storage, Reproducibility, and Presentation Technologies

Artifacts are stored locally as Parquet (tables), CSV (comparison tables), JSON (metadata and the feature manifest), and joblib (locked models) under `data/processed/google_subset_v1/`. Raw and processed data are excluded from Git through `.gitignore`. Source code, documentation, and notebooks are versioned on GitHub; work is merged through pull requests, and status is tracked on the team's GitHub project board. Fixed random seeds (`random_state = 42`) are recorded in `ml_metadata.json`.

The presentation technologies have not been chosen. The backlog requires a read-only API and a UI that run from precomputed artifacts with deterministic local startup. [TBD — API and UI frameworks (New Issues 7–9).]

# Chapter 4. Project Design

## 4.1 Data Pipeline Design

The data pipeline follows five design rules, each enforced in the notebooks:

1. **Explicit identity hierarchy.** Raw observation (`observation_id`) → reconstructed execution (`execution_id`) → full-workload occurrence (`occurrence_key`) → recurring workload (`recurrence_key`). Each level is unique and validated before the next is built.
2. **Missing values stay missing.** No stage applies a global `dropna()` or fills a missing value with zero. Aggregations use strict sums and maxima: if any component is missing, the result is missing. CPU and memory keep separate validity counts, so missing memory never removes usable CPU data.
3. **Single ownership of each definition.** Notebook 03 is the only owner of occurrence peaks and historical profiles; Notebook 04 carries them forward and must not recompute them from execution rows. Notebook 05 reads Notebook 04's splits and targets and must not rebuild them.
4. **Point-in-time correctness.** History for an occurrence starting at time *t* includes only earlier occurrences of the same recurrence whose end time is at or before *t*.
5. **Validated handoffs.** Notebooks 02–05 reload their saved artifacts and check row counts, identifiers, and missingness; Notebook 01's output is checked when Notebook 02 loads it.

## 4.2 Recommendation Model Design

### 4.2.1 Historical Percentile Baselines

Request carries forward the current occurrence's total request as the recommendation for the next occurrence. Mean, P90, P95, and P99 use the corresponding statistic of the current occurrence's completed-occurrence history. A historical policy uses history for a resource only when that resource has at least `min_runs` valid completed occurrences and the statistic is available; otherwise it falls back to the current request. The candidate thresholds are `min_runs` ∈ {1, 3, 5, 10}.

The baseline policy and `min_runs` are selected on validation only, using a lexicographic, violation-first ranking: (1) lowest any-resource violation percentage, (2) lowest worst single-resource violation percentage, (3) lowest sum of CPU and memory violation percentages, (4) lower CPU waste, (5) lower memory waste, and (6) lower `min_runs`. Request is a selectable candidate.

### 4.2.2 Machine Learning Forecasting

The ML design (Notebook 05, in review in PR #61) predicts the next occurrence's full-workload peak separately for CPU and for memory. Its main design choices are:

- **Features:** only information available at the start of the current occurrence (Section 5.3.1). Current-occurrence outcomes, targets, baseline recommendations, and baseline flags are excluded by a leakage audit.
- **Target transform:** models are trained on `log1p(target)`; predictions are mapped back with `expm1` and clipped at zero. The transform is fixed, not learned.
- **Label-period rule:** a training label is used only if its target occurrence starts at or before the end of the period the model may learn from (the training end for model selection, the validation end for the final refit).
- **Pre-declared selection rules:** hyperparameters per model family by the lowest mean `log1p` RMSE across label-purged `TimeSeriesSplit` folds of the training rows; the final model per resource by the lowest validation `log1p` RMSE on the common validation population, with lower raw MAE as the tie-breaker. `GroupKFold` by `recurrence_key` is reported separately and not used for decisions.
- **Lock and refit:** the selected model class, hyperparameters, feature order, and transform are locked and the models are refit on training plus validation rows.

### 4.2.3 Hybrid Risk-Aware Layer

The Hybrid layer is planned. Its purpose is to combine a learned prediction with a conservative historical safeguard. The revised plan gives the starting rule HybridCPU = max(MLPredictedCPU, P95CPU) and HybridMemory = max(MLPredictedMemory, P95Memory) (backlog, p. 25). Notebook 05 already passes the P95 recommendation at the selected `min_runs` through as the safeguard input (`p95_cpu`, `p95_memory`). Under the team's notebook split, Hybrid recommendations are constructed in Notebook 06.

New Issue 6 extends the rule into an objective-driven policy engine: the user selects a Conservative, Balanced, or Efficient objective rather than a model or percentile; the engine chooses among the Request, Mean, percentile, ML-only, and Hybrid candidates available for the dataset, using criteria based on violation risk, utilization, waste, and shortfall; and the Hybrid rule and safety behavior are configurable and calibrated on validation data per dataset. [TBD — objective definitions, calibration procedure, and cold-start behavior (New Issue 6).]

## 4.3 Replay and Evaluation Framework Design

Evaluation is a chronological replay at the occurrence level:

- **Prediction-time convention.** Features and history are those available at the start of the current occurrence; the target is the next distinct occurrence of the same recurrence. The last occurrence of each recurrence has no target.
- **Chronological split.** Execution rows are split by start time, targeting 70/15/15 (actual 70.5/14.5/15.0%), using a utility that places split boundaries only between complete timestamp groups, so no occurrence crosses a boundary.
- **Targets before splitting.** Targets are built once on the complete occurrence table before splitting, so a target may point into a later split but always to a strictly later occurrence. Notebook 05's label-period rule prevents such cross-boundary labels from being used in training. It does not apply to model selection: the validation population used to select the ML models includes the same test-period targets (Section 5.3.3).
- **Common evaluation population.** All validation policies and `min_runs` candidates are scored on the same validation occurrences, namely those with both CPU and memory targets available. Policies may still differ in their valid metric denominators when a recommendation is missing or non-positive.
- **Final-test discipline.** All choices (baseline and `min_runs`, features, models and hyperparameters, Hybrid rules and thresholds, fallback behavior) are to be locked from training and validation data and recorded in a decision manifest (Issue 11, planned); only then will the untouched test split be evaluated, once (Issue 12, planned). So far, Notebook 04 does not score the test split, and Notebook 05 drops test target columns as soon as it loads them.

## 4.4 Artifact and Presentation Layer Design

Artifacts are the interface between stages. Notebook 04 writes the canonical occurrence artifacts (`train_occurrences.parquet`, `val_occurrences.parquet`, `test_occurrences.parquet`), execution-row compatibility artifacts, the validation comparison, and `metadata.json`. Notebook 05 writes a feature manifest, tuning and cross-validation tables, the validation model comparison, validation and test prediction files, `ml_metadata.json`, and the locked models.

For the product track, the revised plan defines one recommendation output contract for all datasets and policies (New Issue 5). Its fields cover the dataset, workload, occurrence, resource, policy, recommendation, model version, feature version, provenance, history count, confidence, fallback reason, capability status, validity status, and artifact version, with CPU and memory represented independently. The API (New Issue 7) and the UI (New Issues 8 and 9) consume this contract read-only and must not recompute evaluator metrics with separate formulas. [TBD — contract schema and API/UI design (New Issues 5–9).]

# Chapter 5. Project Implementation

## 5.1 Data Pipeline

### 5.1.1 Ingestion, Unit Normalization, and Dataset Adapters

Notebooks 00 and 01 load all 405,894 rows of the Kaggle sample without sampling. The audit produced the following findings, which shaped later stages:

- **Resource fields.** `resource_request` was missing or unparseable in 774 rows (0.19%); `maximum_usage` lacked a memory value in 4,927 rows (1.21%). No resource value was negative, and no peak was below the corresponding average. As a raw diagnostic only, peak CPU exceeded requested CPU in 203,459 rows and peak memory exceeded requested memory in 73,310 rows.
- **Memory request.** The request memory equals `assigned_memory` in 152,037 of the 405,120 rows with a request and differs in 253,083, so the two are treated as different quantities; the pipeline uses `resource_request` memory as the request.
- **Timestamps.** Three event times hold the 64-bit integer maximum and are converted to missing; thirteen event times fall after the last usage end and are kept. Usage windows last between 1 and 300 seconds (median 300 seconds). The event `time` field lies inside its row's usage window in only 1,506 of 405,894 rows (0.37%), so event time is not used for ordering; execution timing uses the usage-window fields.
- **Observation identity.** The key `collection_id`, `instance_index`, `machine_id`, `start_time`, `end_time` uniquely identifies all 405,894 rows, which become `observation_id`.

Notebook 01 saves `google_subset_observations_v1.parquet` with 405,894 rows, keeping both the `raw_*` values and the canonical columns `requested_cpu_ncu`, `requested_memory_normalized`, `average_cpu_ncu`, `average_memory_normalized`, `peak_cpu_ncu`, and `peak_memory_normalized`.

For external datasets, PR #70 (merged) implements `BaseDatasetAdapter`, whose `adapt()` method copies the source, applies the dataset mapping, checks that the caller's source was not mutated, and validates the result against the canonical schema. Validation also rejects duplicate canonical occurrence, execution, instance, and interval records (by their identifier keys). The review follow-up commit (d852630) added the following:

- **Alibaba 2018 adapter.** It produces instance-level canonical rows (`job_name` → `workload_id`, `plan_cpu`/`plan_mem` → requested CPU/memory, `cpu_avg`/`cpu_max` and `mem_avg`/`mem_max` → observed and peak CPU/memory) and does not populate a recurrence key. Each row carries dataset-specific unit labels and separate CPU and memory validity statuses (`cpu_validity_status`, `memory_validity_status`). Rows whose average exceeds their maximum are marked invalid and flagged (`source_cpu_avg_gt_max`, `source_memory_avg_gt_max`).
- **Azure VM adapter.** It supports a VM lifecycle and capacity view and a five-minute CPU interval view; observed memory is always null. The interval view raises an error if any CPU-reading VM ID is missing from the VM table, not only when there is no overlap at all. Open-ended capacity buckets such as `>24` are kept as a missing value with an open-ended flag and a lower bound instead of a fabricated number.

[TBD — whether canonical Alibaba or Azure VM artifacts will be generated and reported, and their downstream history and ML-ready preparation (New Issue 4, GitHub #66).]

### 5.1.2 Execution Reconstruction and Dataset-Specific Temporal Features

The 405,894 observations form 242,946 candidate `collection_id + instance_index` groups. These groups are not single executions: the largest contains 7,704 observations on 6,640 machines over two usage windows about 22 days apart. Notebook 02 sorts each group by time and measures the gap between each observation and the latest end time seen so far in its group. There are 10,639 positive gaps; the smallest is 25 minutes and the median is about 4 days. Because every positive gap exceeds one five-minute observation window, a gap larger than five minutes starts a new execution episode, and `execution_id = candidate_instance_key || episode_number`.

This produces 253,585 executions: 242,946 first episodes, 10,291 second, 340 third, and 8 fourth episodes. For each execution:

- the request is the maximum request per machine, summed across the execution's machines;
- the peak is the sum of machine peaks within each usage window, maximized over the execution's windows;
- start and end are the earliest usage start and latest usage end.

All sums and maxima are strict, so any missing component makes the result missing.

A merged analysis of the pipeline (`docs/data/google_subset_pipeline_analysis.md`, finding F8) identifies an open data-quality question in this aggregation. In 38,146 of 253,594 instance-windows, one instance appears on several machines, and all those machines carry identical peak values, which are summed. Keeping one row per instance and window instead would change the CPU peak of 1,159 of the 4,879 occurrences. The analysis describes the repeated rows as suspected but not proven duplicates; both counts were reproduced from the saved artifacts for this draft. [TBD — team decision on whether repeated instance-window rows are duplicates, and any resulting correction to Notebooks 02–03.]

Each execution is assigned `recurrence_key = user_clean || logical_workload_name`, where the logical name is `collection_logical_name` with `collection_name` as a fallback. This yields 2,280 recurrence keys; 1,504 have more than one execution and 776 have one. The most frequent key has 25,180 executions. The recurrence key is an inferred grouping, not a ground-truth job identifier in the dataset.

The temporal features differ by dataset. Google timestamps are in microseconds (Notebook 01) and usage is reported in windows of up to five minutes. According to the PR #70 documentation (`docs/data/dataset_semantics_study_FINAL.md`, `docs/data/external_dataset_integration.md`), Alibaba 2018 timestamps are relative seconds from the start of the trace, and Azure VM CPU readings use a five-minute cadence (`aggregation_window_sec = 300` in the canonical interval view).

### 5.1.3 Peak Usage and Resource Metrics

Notebook 03 builds the 4,879 full-workload occurrences. For each occurrence, it sums the observation-level peaks of all parallel executions within each aligned usage window and takes the largest window total as the occurrence peak; a window with any missing component is missing. The occurrence request is the strict sum of the execution requests, and the occurrence runtime is the latest end minus the earliest start. A regression check pins the largest occurrence (6,921 executions): its full-workload CPU peak is 91.877289, whereas the largest individual execution peak in it is 0.013275. Of the 4,879 occurrences, 73 have a missing request and 60 have a missing memory peak; no CPU peak is missing. No stage filters by lifecycle event: failed, evicted, lost, and killed records are aggregated with finished ones, and 2,584 of the 4,879 occurrences contain at least one FAIL, KILL, EVICT, or LOST row (`docs/data/google_subset_pipeline_analysis.md`, finding F7; count reproduced from the saved artifacts).

Historical profiles are then built per occurrence from prior completed occurrences of the same recurrence. For CPU peak, memory peak, and runtime, the profile stores the count of valid values and their mean, standard deviation, P50, P90, P95, and P99 (pandas `quantile`). Cold starts keep null statistics instead of imputed values. There are 2,280 cold-start occurrences, one per recurrence key. At the execution level, 80,801 rows are cold starts and 172,784 have history. Notebook 03 saves `job_profiles_google_subset_history_v1.parquet` (4,879 rows) and `job_metrics_v0.parquet` (253,585 rows).

## 5.2 Baseline Recommenders

Notebook 04 implements the baselines on the occurrence artifacts (Section 4.2.1). Before generating recommendations, it splits the data chronologically (Table 6.1 in Section 6.2) and builds next-occurrence targets. Of the 675 validation occurrences, 330 have a CPU target, 329 have a memory target, and the common validation population with both targets has 329 occurrences.

### 5.2.1 Request-As-Is

The Request policy recommends the current occurrence's total request (`occurrence_requested_cpu_ncu`, `occurrence_requested_memory_normalized`) for the next occurrence. It does not depend on `min_runs`, and Notebook 04 confirms that its validation metrics are identical across all four `min_runs` candidates.

### 5.2.2 Mean and Percentile Recommendations

Mean, P90, P95, and P99 use the Notebook 03 history statistics (renamed with an `occ_hist_` prefix in Notebook 04 and verified as exact copies). CPU and memory are handled independently, each with its own valid history count. The selected configuration, chosen on validation only, is P99 with `min_runs = 1` (`metadata.json`). Validation results are reported in Section 7.1.1.

### 5.2.3 Cold-Start Handling and Fallbacks

When a resource has fewer than `min_runs` valid completed occurrences, or the history statistic is missing, the historical policies fall back to the current occurrence request. On the 675 validation occurrences, the CPU fallback share is 35.4% at `min_runs = 1`, 56.0% at 3, 64.6% at 5, and 75.0% at 10; the memory fallback share is 35.9%, 56.9%, 65.2%, and 75.6%, respectively. In the common validation population, 26 occurrences have no prior history. If the request itself is missing, the recommendation is missing, and the shared evaluator records the row as unknown rather than as a non-violation (Section 6.4.3). [TBD — final cold-start and fallback behavior of the policy engine (New Issue 6) and its record in the decision manifest (Issue 11).]

## 5.3 Machine Learning Recommender

The ML recommender is implemented in Notebook 05 and in `src/features/feature_config.py` and `src/features/ml_prep.py` on the PR #61 branch, which is in review. The outputs described here come from the saved artifacts of that notebook.

### 5.3.1 Feature and Target Preparation

The feature manifest (`ml_feature_manifest.json`, mirrored in `OCCURRENCE_FEATURE_COLS`) has 24 features, all known at the start of the current occurrence:

- **current occurrence (5):** requested CPU and memory, number of parallel executions, and the number of distinct CPU and memory request values;
- **history (19):** the number of prior completed occurrences, and for CPU peak, memory peak, and runtime the valid count, mean, standard deviation, P90, P95, and P99.

The leakage audit rejects the current occurrence's peaks, end time, and runtime, every `target_*` column, every `rec_*` baseline recommendation, and every `uses_history_*` flag, and it passes on the training, validation, and test data. Missing values are preserved; the three model families handle `NaN` natively, so there is no imputation and no learned preprocessing.

The targets are Notebook 04's `target_cpu_next_occurrence_peak_ncu` and `target_memory_next_occurrence_peak_normalized`, read from `metadata.json`. CPU and memory rows are built independently. Under the label-period rule, there are 1,672 CPU and 1,649 memory training rows; 338 CPU labels are excluded because their target occurrence starts after the training period. A sensitivity variant uses all 2,010 CPU and 1,983 memory training labels but is not used for any decision.

### 5.3.2 Model Training and Selection

The hyperparameter grids contain 16 Decision Tree, 27 Random Forest, and 32 XGBoost combinations (`ml_metadata.json`). Tuning uses five label-purged `TimeSeriesSplit` folds of the training rows; the validation split is not used during tuning. In tuning, Random Forest had the lowest mean `log1p` RMSE for both resources (CPU 0.839, memory 0.471; `ml_cv_summary.csv`). `GroupKFold` means were close to these values (CPU 0.781, memory 0.442), but the fold-to-fold standard deviation was large (CPU 0.285, memory 0.188), so accuracy varies strongly across held-out groups of recurrences.

Applying the pre-declared validation rule, Notebook 05 selected **Random Forest for both CPU and memory**. The locked hyperparameters are 300 trees, `max_features = "sqrt"`, `min_samples_leaf = 10`, and `max_depth` 10 for CPU and 6 for memory. The locked models were refit on training plus validation rows whose target occurrence starts no later than the end of validation: 2,108 CPU rows and 2,082 memory rows. They then predicted all 731 test occurrences. The test prediction file contains `ml_pred_cpu`, `ml_pred_memory`, `p95_cpu`, and `p95_memory` and no target column; P95 inputs are missing for 2 test occurrences per resource. No test metric was computed.

### 5.3.3 Validation-Based Model Comparison

Table 5.1 compares the candidate models on the 329-occurrence common validation population. These are validation results from models trained on training-period labels; the "starting" rows use the fixed hyperparameters of an earlier subset notebook and the median reference is a constant predictor, and neither is selectable.

*Table 5.1. Validation comparison of CPU and memory regression models (Notebook 05, PR #61, in review). Source: `ml_validation_model_comparison.csv`. MAE, RMSE, and R² are on the raw scale (CPU in `_ncu` units, memory in normalized units); log1p metrics are on the transformed scale.*

| Resource | Variant | Model | Selectable | Train rows | Val. rows | MAE | RMSE | R² | log1p RMSE | log1p R² |
|---|---|---|---|---|---|---|---|---|---|---|
| CPU | tuned | Decision Tree | yes | 1672 | 329 | 2.852 | 9.686 | -0.032 | 0.891 | 0.053 |
| CPU | tuned | Random Forest | yes | 1672 | 329 | 2.824 | 9.559 | -0.005 | 0.850 | 0.137 |
| CPU | tuned | XGBoost | yes | 1672 | 329 | 2.851 | 9.600 | -0.014 | 0.860 | 0.117 |
| CPU | starting | Decision Tree | no | 1672 | 329 | 3.017 | 9.808 | -0.058 | 0.981 | -0.149 |
| CPU | starting | Random Forest | no | 1672 | 329 | 2.879 | 9.575 | -0.009 | 0.866 | 0.106 |
| CPU | starting | XGBoost | no | 1672 | 329 | 2.963 | 9.637 | -0.022 | 0.905 | 0.022 |
| CPU | reference | Median reference | no | 1672 | 329 | 2.756 | 9.914 | -0.081 | 1.048 | -0.310 |
| Memory | tuned | Decision Tree | yes | 1649 | 329 | 0.488 | 1.313 | 0.024 | 0.421 | 0.033 |
| Memory | tuned | Random Forest | yes | 1649 | 329 | 0.454 | 1.255 | 0.107 | 0.387 | 0.185 |
| Memory | tuned | XGBoost | yes | 1649 | 329 | 0.528 | 1.306 | 0.034 | 0.439 | -0.051 |
| Memory | starting | Decision Tree | no | 1649 | 329 | 0.656 | 1.600 | -0.451 | 0.539 | -0.583 |
| Memory | starting | Random Forest | no | 1649 | 329 | 0.496 | 1.278 | 0.075 | 0.415 | 0.061 |
| Memory | starting | XGBoost | no | 1649 | 329 | 0.626 | 2.071 | -1.429 | 0.484 | -0.277 |
| Memory | reference | Median reference | no | 1649 | 329 | 0.425 | 1.393 | -0.099 | 0.472 | -0.215 |

The selected Random Forest models have the lowest validation `log1p` RMSE for CPU (0.850) and memory (0.387). Point accuracy on the raw scale is weak: raw R² is −0.005 for CPU and 0.107 for memory, and the median reference has a lower raw MAE than every model for both resources. Because the final model was selected on the same 329 validation occurrences on which it is scored, these numbers are optimistic. The same 329 occurrences include the 104 whose targets fall in the test period (Section 6.2), so test-period outcomes also enter the ML model-selection score and Table 5.1. [TBD — rerun ML selection on the 225 pre-test-period occurrences or record the decision on target split isolation (Issue 11).] Policy-level metrics (violation, utilization, waste, shortfall) for ML-only and Hybrid have not been computed; they belong to Notebook 06. [TBD — ML-only and Hybrid validation policy comparison (Notebook 06; Issue 11).]

## 5.4 Hybrid Risk-Aware Recommender

The Hybrid recommender is planned and has not been implemented. Its inputs are ready in the Notebook 05 artifacts: `val_ml_predictions.parquet` (329 rows, with ML predictions, P95 inputs, and actual values for the common validation population) and `test_ml_predictions.parquet` (731 rows, without targets). Under the team's notebook split, Notebook 06 will construct Hybrid recommendations from `ml_pred_*` and `p95_*` and compare all seven policies through the shared evaluator. [TBD — Hybrid implementation, calibrated parameters, and validation evidence (Notebook 06; New Issue 6; Issue 11).]

## 5.5 Shared Metrics and Evaluation Framework

`src/evaluation/metrics.py` implements the official formulas, and `src/evaluation/evaluator.py` implements `RecommendationEvaluator`. Its `evaluate()` method takes a DataFrame and the names of the actual and recommended CPU and memory columns, checks that they exist, and returns a copy with per-row CPU, memory, and any-resource violation, bounded CPU and memory utilization, waste, and shortfall. Its `summarize()` method returns violation percentages, average utilization, waste, and shortfall, together with the valid denominator for each violation and utilization metric. Because the evaluator takes column names as arguments, it does not depend on dataset-specific identifier columns.

Notebook 04 uses the evaluator for all baseline validation comparisons. Notebook 05 uses it to re-score the Notebook 04 baselines and confirms that all five policies' validation metrics at `min_runs = 1` are reproduced exactly. The metric definitions are given in Section 6.4.

## 5.6 Artifact Storage and Developer-Facing Outputs

The Google pipeline writes the following artifacts to `data/processed/google_subset_v1/`:

- **N01:** `google_subset_observations_v1.parquet`
- **N02:** `google_subset_executions_v1.parquet`, `google_subset_observations_reconstructed_v1.parquet`
- **N03:** `job_profiles_google_subset_history_v1.parquet`, `job_metrics_v0.parquet`
- **N04:** `{train,val,test}_occurrences.parquet` (canonical), `{train,val,test}_features.parquet` (execution-row compatibility), `baseline_validation_comparison.csv`, `metadata.json`
- **N05 (PR #61):** `ml_feature_manifest.json`, `ml_tuning_results.csv`, `ml_cv_summary.csv`, `ml_validation_model_comparison.csv`, `val_ml_predictions.parquet`, `test_ml_predictions.parquet`, `ml_metadata.json`, `n05_locked_models/`

No developer-facing output, API, or UI exists yet. [TBD — common output contract (New Issue 5), read-only API (New Issue 7), and UI (New Issues 8 and 9).]

# Chapter 6. Testing and Verification

## 6.1 Data and Pipeline Correctness Checks

Correctness is checked by assertions inside each notebook and by reloading saved artifacts (Notebooks 02–05; Notebook 01's output is checked when Notebook 02 loads it):

- **N01:** all 405,894 observation IDs are unique before saving; Notebook 02 reloads the saved file and confirms 405,894 rows and no duplicate IDs.
- **N02:** every observation receives an execution ID (0 missing); all 253,585 execution IDs are unique; no runtime is negative; no execution spans more than one candidate group or episode number; and the saved observation and execution files reload with matching counts.
- **N03:** all 405,894 observations map to an execution (0 unmatched). An independent recomputation confirms the occurrence CPU and memory peaks, runtime boundaries, and request totals for all 4,879 occurrences. The point-in-time history check recomputes 87,822 historical metrics and confirms prior-occurrence counts, resource-specific counts, statistics, and missing-value handling. Cold starts have no non-null historical statistic, and all parallel executions of an occurrence share an identical profile.
- **N04:** the Notebook 03 history is adopted without recomputation (aliases are verified as exact copies), and the 6,921-execution regression case keeps its full-workload CPU peak of 91.877289.

## 6.2 Temporal Leakage and Split Integrity

The chronological split is implemented in `src/features/split_utils.py`. It sorts rows by time and ID, places boundaries only between complete timestamp groups, and raises an error if the partitions overlap in IDs or timestamps. Notebook 04 checks that no `occurrence_key` crosses a split boundary and that every target points to a strictly later occurrence (2,010 training, 330 validation, and 259 test targets checked). Table 6.1 summarizes the split.

*Table 6.1. Chronological split summary (Notebook 04). Execution rows and boundaries from `metadata.json`; occurrence and target counts from the saved occurrence artifacts. Times are the first and last occurrence start times in each split, as raw trace timestamps in seconds (microsecond timestamps divided by 10⁶).*

| Split | Execution rows | Execution share | Occurrences | Multi-execution occurrences | With CPU target | With memory target | First start (s) | Last start (s) |
|---|---|---|---|---|---|---|---|---|
| Train | 178,858 | 70.5% | 3,473 | 2,277 | 2,010 | 1,983 | 300 | 1,812,600 |
| Validation | 36,703 | 14.5% | 675 | 513 | 330 | 329 | 1,813,200 | 2,261,100 |
| Test | 38,024 | 15.0% | 731 | 517 | 259 | 259 | 2,262,600 | 2,678,400 |

Building targets before splitting has a measurable effect on the Notebook 04 validation scores (`docs/data/google_subset_pipeline_analysis.md`, findings F3–F4; reproduced for this draft). 104 of the 330 validation targets fall in the test period, and all 104 are in the 329-occurrence population on which the baselines are scored. Scored only on the 225 occurrences whose targets fall before the test period, P99 at `min_runs = 1` has an any-resource violation of 18.30%, versus 21.95% on all 329. The analysis reports that the selected policy (P99, `min_runs = 1`) is unchanged on that population. Training targets cross boundaries as well: 338 point past the end of the training period. [TBD — team decision on target split isolation for Notebook 04 before the decision freeze (Issue 11).]

Three further safeguards limit leakage in the ML stage (PR #61). The label-period rule excludes training labels whose target occurrence lies in a later period (338 CPU labels at the training boundary). Tuning folds purge labels that reach into each fold's validation block. The test artifact is loaded only after the models are locked, with its target and outcome columns dropped immediately. These safeguards cover training and tuning only. ML model selection is scored on the 329-occurrence validation population, which includes the 104 test-period targets.

Note for reviewers: the introduction of Notebook 04 states that targets are built "inside each frozen split so labels never cross split boundaries," but the implemented code and `metadata.json` build targets once before splitting and allow a target to point into a later split. This draft describes the implemented behavior. [TBD — align the Notebook 04 introduction text with its implementation.]

## 6.3 Model and Baseline Validation

Baseline selection uses validation only and is recorded in `metadata.json` (`baseline_selection_scope = validation_only`). Notebook 05 reproduces every Notebook 04 baseline validation metric exactly, which confirms that it reads the same artifacts Notebook 04 produced.

Unit tests are run with pytest. On `main` (a0b3c77), the suite has 82 tests in eight files:

- `tests/test_evaluation.py` (17) and `tests/test_split_utils.py` (7) cover bounded utilization, zero and non-finite recommendations, any-resource violation (including the unknown state), equality not counting as a violation, waste, shortfall, valid denominators, required-column checks, chronological ordering, ID disjointness, duplicate and missing-value rejection, and preservation of shared timestamps.
- PR #70 added 58 tests: canonical schema (14), adapter contract (10), Alibaba adapter (12), Azure VM adapter (15), external-adapter integration (2), and the Google canonical contract (5). The Google contract tests read the local Notebook 04 artifacts and metadata. On a copy of `main` without those artifacts, all 5 of them fail with missing-file errors (77 of 82 pass); they do not skip.

Run for this draft on 2026-10-16 with the local artifacts present, 81 tests passed and 1 failed. The failing test, `test_google_train_target_nulls_are_preserved`, expects 1,801 missing CPU targets in the training split, which equals the number of recurrence keys in that split. The artifact has 1,463. The difference of 338 is the number of training occurrences whose next occurrence lies after the training period (Section 6.2). The test assumes that targets stay within a split, while Notebook 04 builds them before splitting. This failure is an open item. [TBD — resolve the test/implementation mismatch together with the target split-isolation decision (Issues 11 and 16).]

On the PR #61 branch (open; based on an earlier `main`), `tests/test_ml_prep.py` adds tests for the feature-manifest leakage audit, missing-value preservation, the label-period rule, and purged time-series folds; the suite on that branch has 38 tests, all of which passed when run on 2026-10-15. [TBD — final test suite, clean-clone smoke test, and results (Issue 16).]

## 6.4 Replay Evaluation Metrics

All metrics are computed per row by `metrics.py` and summarized by `evaluator.py`. Here *a* is the actual value (the next occurrence's full-workload peak) and *r* is the recommendation, for CPU or memory.

### 6.4.1 Violation and Utilization

- **Violation:** a resource is violated when *a* > *r*. Equality is not a violation.
- **Any-resource violation:** 1 if either resource is definitely violated; 0 if both are valid non-violations; unknown otherwise.
- **Bounded utilization:** min(*a* / *r*, 1). It is undefined when either value is non-finite or *r* ≤ 10⁻¹².

Violation percentages and average utilization are computed over valid rows only.

### 6.4.2 Resource Waste

- **Waste:** max(*r* − *a*, 0), the recommended capacity left unused.
- **Shortfall:** max(*a* − *r*, 0), the amount by which usage exceeded the recommendation.

Average waste and shortfall are reported per resource in the same units as the resource.

### 6.4.3 Valid-Row Denominators and Missing-Value Handling

A violation is unknown (`NaN`) when either input is non-finite. An unknown result is never counted as a non-violation. The evaluator therefore reports separate valid counts for CPU, memory, and any-resource violation and for CPU and memory utilization. A zero recommendation is still a valid violation input, but it is excluded from utilization. For example, on the 329 common validation occurrences, the Request policy has 326 valid rows for each violation metric, 315 valid rows for CPU utilization, and 326 for memory utilization, because some current requests are missing (excluded from violation) or zero (excluded from utilization). Average waste and shortfall use pandas means, which skip missing rows; the evaluator does not report separate denominators for them.

# Chapter 7. Performance, Results, and Discussion

## 7.1 Google ClusterData 2019 Results

**No final Google result exists yet.** Under backlog Issue 12, the one-time final-test evaluation, run after every decision is frozen (Issue 11), is the only source of final Google report numbers. The tables below report **validation** results only. They were used to make design decisions and are optimistic as estimates of final performance.

### 7.1.1 Baseline Recommendation Results

Table 7.1 shows the validation comparison of the five baseline policies at the selected `min_runs = 1` on the 329-occurrence common validation population.

*Table 7.1. Validation comparison of baseline policies at the selected min_runs = 1 (Notebook 04). Source: `baseline_validation_comparison.csv`. Violation percentages use the valid denominators shown; "Valid n (any)" is the any-resource denominator. CPU in `_ncu` units, memory in normalized units.*

| Policy | CPU viol. % | Mem. viol. % | Any-resource viol. % | Valid n (any) | Avg CPU util. | Avg mem. util. | Avg CPU waste (NCU) | Avg mem. waste | Avg CPU shortfall (NCU) | Avg mem. shortfall |
|---|---|---|---|---|---|---|---|---|---|---|
| Request | 52.15 | 38.04 | 55.52 | 326 | 0.623 | 0.530 | 0.957 | 0.449 | 2.421 | 0.302 |
| Mean | 35.37 | 34.15 | 42.99 | 328 | 0.491 | 0.509 | 1.740 | 0.363 | 1.887 | 0.217 |
| P90 | 22.26 | 21.65 | 28.66 | 328 | 0.387 | 0.406 | 4.856 | 0.980 | 1.335 | 0.142 |
| P95 | 18.60 | 19.82 | 25.30 | 328 | 0.341 | 0.371 | 8.449 | 1.865 | 1.064 | 0.103 |
| P99 | 16.77 | 17.07 | 21.95 | 328 | 0.298 | 0.337 | 19.041 | 3.346 | 0.972 | 0.086 |

On validation, the policies form a largely monotone trade-off. Moving from Request through Mean, P90, and P95 to P99 lowers the any-resource violation percentage from 55.52% to 21.95%. Over the same sequence, average CPU utilization falls from 0.623 to 0.298, and average CPU waste rises from 0.957 to 19.041. The violation-first selection rule therefore selects P99. Across `min_runs` candidates, P99's any-resource violation is 21.95% at `min_runs = 1`, 22.39% at 3, 23.31% at 5, and 30.98% at 10. This rise coincides with a higher share of fallbacks to the request at larger `min_runs` (Section 5.2.3), and the Request policy has the highest violation of the five baselines.

These validation numbers include the 104 test-period targets described in Section 6.2. On the 225 occurrences whose targets fall before the test period, P99's any-resource violation is 18.30%.

Final-test baseline results: [TBD — final-test results from Issue 12.]

### 7.1.2 ML and Hybrid Recommendation Results

ML model-quality results on validation are given in Table 5.1 (Section 5.3.3). Policy-level results for ML-only and Hybrid (violation, utilization, waste, and shortfall, compared with Request, Mean, P90, P95, and P99 through the shared evaluator) have not yet been produced.

- Validation policy comparison including ML-only and Hybrid: [TBD — Notebook 06 validation comparison, frozen in Issue 11.]
- Final-test comparison of all seven policies: [TBD — final-test results from Issue 12.]

### 7.1.3 Feature Importance and Explainability

[TBD — feature importance or another model-specific explanation for the locked CPU and memory models, plus analysis of under-provisioned and largest-waste occurrences (Issue 13).]

## 7.2 Cross-Platform Validation Results

No cross-platform result exists yet. PR #70 (merged) documents the Alibaba 2018 and Azure VM semantics and implements canonical adapters, but no canonical external artifacts have been generated (a sample builder, `scripts/build_external_canonical_samples.py`, exists) and no history, profiles, or ML-ready inputs for these datasets have been produced; that work remains open under New Issue 4 (GitHub #66). The capability matrix (`docs/data/traceadvisor_external_dataset_capability_matrix.csv`) records that Alibaba has no explicit recurrence key, so next-occurrence targets are possible only after a derived recurrence rule is validated, and that Azure VM supports CPU-oriented validation but has no observed-memory target. Under the revised plan, each external dataset must run through its own data, feature, target, model, and policy artifacts, and the fitted Google model is not automatically reused for Alibaba or Azure VM. The PR #72 documentation proposes replacing this external-dataset scope with Alibaba GPU v2020 and deferring Azure (Section 3.3.2); that proposal is not implemented. The 295B scope document (Section 7) lists the role of the external datasets, and whether a CLI is still required alongside the API and UI, as open questions to confirm with the team.

[TBD — Alibaba and Azure VM results (New Issue 4; Issues 06–08 for external datasets), and the team/advisor decision on Splitwise and ModServe (scope document, Section 7).]

## 7.3 Discussion of Findings

The validation evidence supports four observations. They must be rechecked against the final-test results, and the validation metrics behind them include the test-period targets noted in Section 6.2:

1. **The occurrence definition changes the problem.** For the largest occurrence, the full-workload CPU peak (91.877289) is several orders of magnitude larger than the largest individual execution peak (0.013275). Treating an occurrence as one execution would understate the resources a recurring workload actually needs.
2. **Carrying forward the request is unsafe on this sample.** On validation, the Request policy violates at least one resource in 55.52% of valid occurrences, the highest of the five baselines.
3. **Tail percentiles trade waste for safety.** P99 has the lowest validation violation but also the lowest utilization and the highest waste. The best baseline under a violation-first objective is not the best under an efficiency objective, which motivates the planned objective-driven policy engine (New Issue 6).
4. **ML point accuracy is modest.** The selected Random Forest models improve on the starting hyperparameters and on a constant median in `log1p` RMSE, but their raw-scale R² is near zero for CPU and 0.107 for memory. ML predictions are therefore expected to be most useful in combination with a historical safeguard, which is the purpose of the planned Hybrid layer. Whether Hybrid improves the violation–waste trade-off is untested.

[TBD — discussion of final-test results, Hybrid and objective behavior, failure cases, and cross-platform findings (Issues 12, 13; New Issues 4 and 6).]

# Chapter 8. Operations, Reproducibility, and Future Deployment

## 8.1 Offline Artifact Workflow

TraceAdvisor operates offline. The raw sample is placed at `subset/borg_traces_data.csv`, the notebooks are run in order, and each notebook reads only the artifacts of earlier stages from `data/processed/google_subset_v1/`. Decisions travel with the artifacts: `metadata.json` records the occurrence key definition, split boundaries, target definition, `min_runs` basis, selected baseline, and test policy, and `ml_metadata.json` records the feature manifest, tuning grids, cross-validation scheme, selection rule, locked parameters, refit data, and library versions. The planned API and UI will read these precomputed artifacts and will not train or run models live. Live scheduler integration, online inference, autoscaling, authentication, cloud hosting, and a production multi-user backend are explicitly out of scope (backlog, p. 20).

## 8.2 Reproducibility and Repository Layout

The repository is organized as follows:

- `pipelines/google_subset/`: current Google pipeline notebooks (00–05)
- `src/evaluation/`: shared metrics and evaluator
- `src/features/`: split utility, feature configuration, ML preparation helpers
- `src/canonical/`, `src/adapters/`, `config/`, `examples/`: canonical schema, dataset adapters, dataset capability configuration, and example canonical records (PR #70)
- `scripts/`: helper scripts, including the external canonical sample builder (PR #70)
- `tests/`: pytest unit tests
- `docs/`: planning, data, evaluation, meeting, and reference documents
- `data/processed/google_subset_v1/`: generated artifacts (not committed)
- 295A-era material: `notebooks/`, `src/eval/`, `src/baselines/`, `reports/eval/`. This material is kept for background and is not part of the occurrence-level pipeline.

To reproduce the pipeline, install the dependencies (`pip install -r requirements.txt`), place the Kaggle sample at `subset/borg_traces_data.csv`, run Notebooks 00–04 (and Notebook 05 once PR #61 is merged), and run `pytest` (one known failure on `main`; Section 6.3). PR #61 adds `xgboost` to `requirements.txt`, which Notebook 05 needs. Randomness is fixed with `random_state = 42`.

Two reproducibility gaps remain open for Issue 16. First, the backlog requires that no final report or demo depend on untracked local files, but all artifacts are currently gitignored local files. Second, a clean-clone smoke test on a small fixture does not exist yet. [TBD — release manifest with artifact versions and paths, clean-clone smoke test, and final README/runbook (Issues 16 and 18).]

## 8.3 Interactive Developer Dashboard (Planned)

The dashboard is planned and has not been built. Under the revised plan:

- **New Issue 8 (UI simulation):** the user will select a dataset (Google, Alibaba, or Azure VM, when an artifact is available), a workload or occurrence, and a Conservative, Balanced, or Efficient objective. The UI is to show recommendations, violation risk, utilization, waste, and shortfall from saved outputs, explain the strategy and parameters chosen by the policy engine, and not duplicate evaluator formulas.
- **New Issue 7 (API):** a read-only API is to serve the common recommendation contract.
- **New Issue 9 (integration):** is to connect the UI to the API, demonstrate the Conservative, Balanced, Efficient, and fallback cases, and work without downloading a large raw trace at runtime.

The original backlog also lists an API/CLI and an interactive dashboard (Issues 14 and 15); whether a CLI is still required alongside the revised API and UI is an open question in the 295B scope document (Section 7).

[TBD — dashboard design, screenshots, and demo walkthrough (New Issues 7–9; Issue 18).]

# Chapter 9. Summary, Conclusions, and Recommendations

## 9.1 Summary

In 295B, the team rebuilt the TraceAdvisor Google pipeline around the full-workload occurrence. The implemented stages:

- audit and ingest a 405,894-row sample of Google ClusterData 2019 without dropping rows;
- reconstruct 253,585 executions with a gap-based episode rule and group them into 2,280 recurring workloads;
- aggregate 4,879 full-workload occurrences with aligned-window peaks and point-in-time history;
- split the occurrences chronologically and attach next-occurrence targets;
- select a historical baseline (P99, `min_runs = 1`) on validation only, through a shared evaluator that reports valid denominators.

An ML stage that tunes, selects, locks, and refits per-resource Random Forest models is in review (PR #61). A capability-aware canonical schema and adapter framework with Alibaba 2018 and Azure VM adapters is merged (PR #70); downstream preparation for those datasets remains open (New Issue 4), and a documentation-only proposal (PR #72) would change the external-dataset scope. Hybrid construction, the decision freeze, the final-test evaluation, explainability, the policy engine, and the product layer are planned.

## 9.2 Conclusions

From the evidence available now, three conclusions can be drawn:

- A correct occurrence definition matters: full-workload peaks can differ from individual execution peaks by orders of magnitude.
- A validation-only selection process has been implemented end to end for the baselines. Its validation scores, however, still include test-period targets (Section 6.2), so the evaluation is not yet fully leakage-safe.
- On validation, tail-percentile baselines reduce violations relative to carrying the request forward, at a substantial waste cost.

The project's central claims about final policy performance cannot yet be stated. [TBD — conclusions on final-test performance of Request, Mean, P90, P95, P99, ML-only, and Hybrid (Issue 12), and on cross-platform behavior (New Issue 4).]

## 9.3 Limitations and Recommendations for Further Research

Current limitations, each documented in the sources:

- **Data scale.** Results come from one Kaggle sample of about 31 days, not the full ClusterData 2019 traces.
- **Recurrence is inferred.** The `recurrence_key` (user and logical name) is a heuristic grouping, not a ground-truth job identifier. Most recurrences have few occurrences: the median is one occurrence per key.
- **Small validation population.** Model selection uses 329 validation occurrences, the same rows on which validation metrics are reported, so validation numbers are optimistic.
- **Missing data.** 73 occurrences lack a request and 60 lack a memory peak. These rows reduce valid denominators rather than being imputed.
- **Targets cross split boundaries.** 104 of the 329 scored validation targets lie in the test period, so the reported validation baseline metrics include test-period outcomes (Section 6.2).
- **Abnormal records are included.** 2,584 of 4,879 occurrences contain failed, killed, evicted, or lost records, and no filtering decision has been recorded.
- **Possible duplicate summing.** Repeated instance-window rows across machines are summed; treating them as duplicates would change the CPU peak of 1,159 occurrences (Section 5.1.2).
- **Episode rule.** The five-minute gap threshold is derived from this sample's observed gaps (minimum 25 minutes) and may need re-derivation on other data.
- **External datasets.** Alibaba 2018 lacks an explicit recurrence key and needs a validated workload-family rule and DAG-aware aggregation; Azure VM lacks observed memory, and the Azure trace version used is disputed (Section 3.3.2). The external-dataset scope itself is open (PR #72 proposal). Splitwise and ModServe are scope-pending.
- **Out of scope.** GPU recommendations, OpenStack integration, and live deployment are out of 295B scope (backlog, p. 20).

Recommendations for further work are as follows. Validate a recurrence rule for Alibaba before building next-occurrence targets, as the semantics study recommends. Evaluate whether the Hybrid safeguard should remain P95 or follow the validation-selected baseline. Test the approach on larger slices of ClusterData 2019. [TBD — further recommendations after Issues 12 and 13.]

# Glossary (draft entries)

- **Execution:** one continuous activity episode of a `collection_id + instance_index` group, split at gaps longer than five minutes (`execution_id`).
- **Occurrence:** all executions of one recurrence that start at the same time; the canonical modeling and evaluation unit (`occurrence_key = recurrence_key || execution_start_time_us`).
- **Recurrence key:** an inferred recurring-workload identity, `user_clean || logical_workload_name`.
- **Point-in-time history:** statistics over earlier occurrences of the same recurrence that had completed by the current occurrence's start.
- **Next-occurrence target:** the full-workload CPU and memory peak of the next distinct occurrence of the same recurrence.
- **min_runs:** the minimum number of valid completed prior occurrences needed before a historical policy uses history instead of the request.
- **Violation, utilization, waste, shortfall:** see Section 6.4.

# References cited in Chapters 2–9

Numbering follows `docs/references/References.md`.

[5] E. Cortez et al., "Resource Central: Understanding and Predicting Workloads for Improved Resource Management in Large Cloud Platforms," ACM SOSP, 2017.

[6] J. Wilkes et al., "Google Borg Cluster Traces (ClusterData2019)," dataset repository, 2019. https://github.com/google/cluster-data

[8] Alibaba Group, "Alibaba Cluster Trace Program," dataset repository, 2017–2025. https://github.com/alibaba/clusterdata

[TBD — references to add to docs/references/References.md before citing: the Kaggle Google 2019 cluster sample, the Azure Public Dataset version confirmed for the adapter (V1 or V2; Section 3.3.2), and any software citations required by the report template.]
