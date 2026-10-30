# Chapter 3 Source Map: Technology Descriptions

**Purpose:** for each Chapter 3 section, the code, configuration, design documents and results to read before writing it. The writing source is `docs/design/traceadvisor_system_guide.md`.

**Scope rules**
- Datasets: Google ClusterData 2019 (Kaggle subset) and Alibaba GPU Cluster Trace 2020. Alibaba 2018 is not in the report. Azure traces appear only as earlier baseline experiments.
- The old report draft and `REPORT_TRACEABILITY.md` are not sources.
- Task 13 (Google thin adapter), Alibaba Task 7 (ML, Hybrid, final test) and the presentation layer (REST API and web frontend) are written as implemented.
- Line numbers are from `docs/issue-17-final-report` at `0b07fed`.

---

## 3.1 Data Processing and Analysis Stack

**What the section says:** Python 3.12 with pandas and NumPy for tabular processing, PyArrow and Parquet for intermediate and final tables, Jupyter notebooks for the Google pipeline and command-line scripts for the Alibaba pipeline, Matplotlib and Seaborn for figures, and pytest for testing. Why each was chosen, briefly.

| Kind | Source |
|---|---|
| Writing source | System guide §2.1 (environment and key versions), §3 (layout) |
| Versions | `requirements-lock.txt`: pandas 2.3.3, numpy 2.5.4, pyarrow 23.0.1, matplotlib 3.11.2, seaborn 0.13.2, jupyterlab 4.6.5, pytest 9.2.0, scipy 1.18.1 |
| Minimum versions | `requirements.txt` |
| Code: usage | pandas and numpy throughout `src/` and all Google notebooks; pyarrow in `src/features/target_builder.py` and the Alibaba scripts; typed headerless loading in `src/sources/alibaba_gpu_2020.py` — `load_table` (L343), `iter_table_chunks` (L376) |
| Pipelines | `pipelines/google_subset/00–06_*.ipynb` (notebooks); `scripts/build_alibaba_gpu_2020_canonical.py`, `build_alibaba_gpu_2020_targets.py`, `run_alibaba_gpu_2020_baselines.py`, `run_alibaba_gpu_2020_ml.py` *(Task 7)* (scripts) |
| Tests | `pytest.ini` (`pythonpath = src`, `testpaths = tests`); 19 test files in `tests/` |

## 3.2 Machine Learning Libraries and Models

**What the section says:** scikit-learn and XGBoost; the model families compared on each dataset; tuning and time-aware cross-validation; the `log1p` target transform for Google; models saved with joblib. Describe the libraries and models only; the selection design belongs in Chapter 4 and the results in Chapter 7.

| Kind | Source |
|---|---|
| Writing source | System guide §9 (ML candidates and ranking) |
| Versions | `requirements-lock.txt`: scikit-learn 1.9.1, xgboost 3.4.1, joblib 1.6.0 |
| Google models | `pipelines/google_subset/05_evaluateRecommendations.ipynb`: `DecisionTreeRegressor`, `RandomForestRegressor`, `XGBRegressor` tuned with `GridSearchCV` over label-purged `TimeSeriesSplit` folds (`purged_time_series_folds`); `DummyRegressor(strategy="median")` as the floor; `log1p` targets, predictions `expm1` then clipped at 0; `GroupKFold` by `recurrence_key` reported as a robustness check only; models saved with joblib to `n05_locked_models/` |
| Alibaba models | Task 7 issue: `DummyRegressor` (`mean`/`median`), `DecisionTreeRegressor`, `RandomForestRegressor`, `HistGradientBoostingRegressor` (or `GradientBoostingRegressor`), `XGBRegressor`; each grid configuration fitted on train and scored on validation, no cross-validation search (issue L184); `scripts/run_alibaba_gpu_2020_ml.py` *(Task 7)* |
| Feature helpers | `src/features/ml_prep.py` — `validate_features` (L113), `purged_time_series_folds` (L359); `src/features/feature_config.py` |
| Design docs | `docs/planning/github_issues/task7_machine_learning_hybrid_and_final_test.md`; `canonical_schema_design_decisions.md` D-19 |
| Results | `reports/results/google_subset/tables/ml_validation_model_comparison.csv`, `n05_ml_metadata.json` |
| Tests | `tests/test_ml_prep.py` |

## 3.3 Dataset and Trace Sources

### 3.3.1 Primary Dataset: Google ClusterData 2019

**What the section says:** what the trace is (Borg cluster, 2019), the Kaggle sample used (405,894 rows, 34 columns, about 31 days), what it records (usage windows, requests, events, normalized CPU and memory), and its limits (a sample, not the full trace; no official recurrence tag).

| Kind | Source |
|---|---|
| Writing source | System guide §1 (datasets), §2.2 (Google data), §13 (sample size) |
| Design docs | `docs/data/subsetSetup.md`, `docs/data/google_subset_pipeline_analysis.md` |
| Code | `pipelines/google_subset/00_dataQualityReview.ipynb`, `01_dataIngestion.ipynb`; `scripts/verify_data_setup.py` — `verify_google_kaggle_subset` (L19) |
| Results | `reports/results/google_subset/googlepipeline_finalrun.md` |
| Reference | Kaggle sample: https://www.kaggle.com/datasets/derrickmwiti/google-2019-cluster-sample; `docs/references/References.md` |

### 3.3.2 Second Dataset: Alibaba GPU Cluster Trace 2020 *(proposed new title)*

**What the section says:** what the trace is (Alibaba PAI GPU cluster, 2020), the six official tables, why it was chosen (official `group` recurrence tag on 99.86% of jobs; memory peak in the same unit as the request; only such trace of the twelve Alibaba traces examined), and its limits (CPU only as a lifetime average; 36.8% of role-occurrences eligible; telemetry covers about day 19 to day 68.9).

| Kind | Source |
|---|---|
| Writing source | System guide §1, §2.3, §13 |
| Source tables | `config/alibaba_gpu_2020_sources.json`: `pai_job_table`, `pai_task_table`, `pai_instance_table`, `pai_sensor_table`, `pai_group_tag_table`, `pai_machine_spec`, with official URLs, SHA-256 checksums and sizes |
| Design docs | `docs/data/alibaba_dataset_selection_feasibility.md` (selection, L38 and L119), `docs/data/alibaba_gpu_2020_source_setup.md`, `docs/data/alibaba_gpu_2020_source_data_checks.md` |
| Code | `src/sources/alibaba_gpu_2020.py`; `scripts/verify_data_setup.py` — `verify_alibaba_gpu_2020` (L40) |
| Results | `docs/data/alibaba_gpu_2020_adapter_results.md`; `reports/results/alibaba_gpu_2020/alibaba_gpu_2020_results_tasks1_6.md` |

### 3.3.3 Earlier Baseline Traces: Azure Resource Central, Splitwise and ModServe *(proposed new subsection)*

**What the section says:** the three Azure traces used for baseline experiments before the TraceAdvisor design was fixed, what each showed (the same mean-versus-percentile trade-off), and why none was carried into the pipeline (no recurring jobs with per-job requests and usage). One short paragraph each.

| Kind | Source |
|---|---|
| Writing source | System guide §11 |
| Write-ups | `docs/baseline_experiments/resource-central/resource-central_experiment_pipeline.md`, `docs/baseline_experiments/modserve/modserve_experiment_pipeline.md` |
| Feasibility | `docs/data/azure_vm_traceadvisor_feasibility.md` (why Azure VM integration is deferred) |
| Outputs | `reports/eval/resource-central/`, `reports/eval/splitwise/`, `reports/eval/modserve/` |

## 3.4 Dataset Adapters and Unit Normalization

**What the section says:** how each dataset's raw values become canonical values with an explicit unit. Google: CPU in normalized compute units and memory normalized, kept as published, timestamps converted to microseconds, original `raw_*` columns kept. Alibaba: CPU in percent of one vCPU, memory in GB, GPU kept but not evaluated, timestamps from seconds to microseconds, no CPU peak. The schema's unit vocabulary and the rule that a request and its actual use the same unit. Technology view only; the adapter design is in Chapter 4 and its implementation in Chapter 5.

| Kind | Source |
|---|---|
| Writing source | System guide §5.2 (core rules), §5.5 (resources and units), §6.1 |
| Code: units | `src/canonical/schema.py` — `ALLOWED_RESOURCE_UNITS` (L27), `GOOGLE_CAPABILITIES` (L266, `cpu_unit = "ncu"`), `ALIBABA_GPU_2020_CAPABILITIES` (L325, `cpu_unit = "percent_of_vcpu"`) |
| Code: Alibaba mapping | `src/adapters/alibaba_gpu_2020.py` — resource maps (L712–721: `plan_cpu`, `plan_mem`, `cpu_usage`, `avg_mem`, `max_mem`, GPU fields), `_seconds_to_us` (L400), `_map_resources` (L745) |
| Code: Google mapping | `pipelines/google_subset/01_dataIngestion.ipynb`; `src/adapters/google_subset.py` *(Task 13)* |
| Profiles config | `config/dataset_capabilities.json` |
| Design docs | `docs/design/canonical_workload_schema.md` (units section), `docs/design/adapter_framework.md`, `docs/design/alibaba_gpu_2020_adapter_design.md` |
| Tests | `tests/test_canonical_schema.py`, `tests/test_alibaba_gpu_2020_adapter.py` |

## 3.5 Artifact Storage, Reproducibility, and Presentation Technologies

**What the section says:** Parquet for tables, JSON for metadata and the decision manifest, CSV for result tables, SHA-256 checksum files, staging folders with atomic publish, Git for code and documents (raw and intermediate data stay local), the locked environment, and the presentation technologies (REST API and web frontend, kept general).

| Kind | Source |
|---|---|
| Writing source | System guide §2.1, §7.2 (last paragraph), §10.2 |
| Code: checksums and publish | `scripts/build_alibaba_gpu_2020_canonical.py` — `verify_output` (L327), `publish` (L397); `scripts/run_alibaba_gpu_2020_baselines.py` — `verify_targets` (L92); `src/sources/alibaba_gpu_2020.py` — `verify_sources` (L225) |
| Code: manifest | `pipelines/google_subset/06_finalPolicyComparison.ipynb` (hashlib, subprocess for the code commit, decision manifest) |
| Artifacts | `reports/results/google_subset/decision_manifest.json`, `final_test_run_metadata.json`; `.gitignore` (`data/` not committed) |
| Environment | `requirements-lock.txt` (committed in `02184f2`) |
| Presentation | REST API and web frontend: no code or stack yet; written in general terms |

---

## Check against the code

| # | Item | Finding | Effect on Chapter 3 |
|---|---|---|---|
| 1 | 3.3.2 title | The table of contents calls Azure, Splitwise and ModServe "Validation Datasets", but they were never run through the pipeline (system guide §11) | Retitle 3.3.2 to the Alibaba GPU 2020 dataset and add 3.3.3 for the earlier Azure baseline traces |
| 2 | Splitwise write-up | `docs/baseline_experiments/splitwise/` is empty; only outputs exist in `reports/eval/splitwise/` | 3.3.3 relies on system guide §11 for Splitwise |
| 3 | `gcsfs` | Listed in `requirements.txt`; its only user was the removed 295A evaluator, so nothing imports it now | Leave out of 3.1 |
| 4 | Google `DummyRegressor` | Notebook 05 uses `DummyRegressor(strategy="median")` as a floor alongside the three tuned models | Resolved: 3.2 describes it as a constant predictor (median on Google, mean or median on Alibaba) |
| 5 | Presentation stack | No API or frontend framework chosen yet | Keep 3.5 general; add framework names once decided |
| 6 | Google units | Google CPU and memory are normalized by the trace publisher, so waste is not in cores or GB | State this in 3.3.1 and 3.4; it is why results are not compared across datasets |
| 7 | Group-tag coverage (3.3.2) | Recomputed from the raw tables with `load_table` and the adapter's missing-group rule: 1,530 of 1,055,501 jobs untagged (99.855%); 1,061 tag rows match no job. Matches `data/processed/alibaba_gpu_v2020/metadata.json` (`join_coverage_counts.job_group_tag`) | 99.86% is correct; the row-count difference is not the untagged count |
