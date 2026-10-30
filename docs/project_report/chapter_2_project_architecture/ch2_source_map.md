# Chapter 2 Source Map: Project Architecture

**Purpose:** for each Chapter 2 section, the code, design documents, results and tests to read before writing it. The writing source is `docs/design/traceadvisor_system_guide.md` (29 Oct 2026); everything else here is what backs it.

**Scope rules**
- Datasets: Google ClusterData 2019 (Kaggle subset) and Alibaba GPU 2020. Alibaba 2018 is not in the report.
- The old report draft and `REPORT_TRACEABILITY.md` are not sources.
- Line numbers are from `docs/issue-17-final-report` at `6b6d0b0`.
- Task 13 (Google thin adapter) is written as complete from its issue text and the system guide; paths marked *(planned)* come from that issue. Task 7 (Alibaba ML, Hybrid, final test) is merged (PRs #98, #102) and run (30 Oct 2026); its sources are the code and `reports/results/alibaba_gpu_2020/`.

---

## 2.1 Introduction and System Overview

**What the section says:** the problem (requests far from actual use; recurring jobs make history useful), what TraceAdvisor produces (a pre-execution CPU and memory recommendation per recurring workload), the seven policies, the two datasets, and the overall shape of the system (batch, offline; dataset-specific work up to the canonical views, shared logic after them).

| Kind | Source |
|---|---|
| Writing source | System guide §1 (problem, policies, datasets), §4.1 (system overview diagram) |
| Design docs | `docs/planning/295b_scope_and_done.md` (scope); `docs/design/canonical_schema_design_decisions.md` D-01 (dataset choice) |
| Dataset choice | `docs/data/dataset_inspection_and_integration_design.md`, `docs/data/alibaba_dataset_selection_feasibility.md` |
| Code | None needed for this section |
| Figure | System guide §4.1 Mermaid flowchart → Figure 2.1 (System overview) |

---

## 2.2 Architecture Subsystems

**Intro paragraph:** the layers and what each one owns and never does (system guide §4.2 table). Optional figure: core class diagram (system guide §4.3).

### 2.2.1 Data Ingestion and Dataset Adapters

**What the section says:** ingestion verifies and loads raw tables; the adapter maps them into canonical views (identity, units, eligibility, aggregation, validity, rejected output, provenance). The canonical schema and the dataset capability profile are the contract between the two. Two adapter paths: `adapt()` (one table, one view) and `adapt_sources()` (several tables, several views).

| Kind | Source |
|---|---|
| Writing source | System guide §4.2, §5.1–5.2, §6.1–6.4 |
| Code: schema | `src/canonical/schema.py` — `SCHEMA_VERSION` (L8), `DatasetCapabilities` (L127), `GOOGLE_CAPABILITIES` (L266), `ALIBABA_GPU_2020_CAPABILITIES` (L325), `validate_canonical_frame` (L378) |
| Code: profiles config | `config/dataset_capabilities.json` |
| Code: ingestion | `src/sources/alibaba_gpu_2020.py` — `verify_sources` (L225), `load_table` (L343); `config/alibaba_gpu_2020_sources.json` (checksums). Google: `pipelines/google_subset/01_dataIngestion.ipynb` |
| Code: adapter framework | `src/adapters/base.py` — `AdapterResult` (L40), `BaseDatasetAdapter` (L119), `adapt` (L153), `prepare_sources` (L191), `map_prepared_sources` (L201), `adapt_sources` (L413) |
| Code: shared checks | `src/adapters/validation.py` — `validate_adapter_output` (L189), `validate_rejected_output` (L283), `validate_role_instance_linkage` (L402) |
| Code: Alibaba adapter | `src/adapters/alibaba_gpu_2020.py` — `AlibabaGPU2020Adapter` (L1089) |
| Code: Google adapter | `src/adapters/google_subset.py` — `GoogleSubsetAdapter`, `attach_google_precomputed_targets` *(planned)*; `tests/test_google_subset_adapter.py` *(planned)*, `tests/test_google_canonical_contract.py` |
| Google adapter design | `docs/planning/github_issues/task13_google_subset_thin_adapter.md`; system guide §6.6 |
| Design docs | `docs/design/canonical_workload_schema.md`, `docs/design/adapter_framework.md`, `docs/design/alibaba_gpu_2020_adapter_design.md`, `docs/design/alibaba_gpu_2020_output_contract.md` |
| Results | `docs/data/alibaba_gpu_2020_adapter_results.md` (counts: 1,254,108 role occurrences, 461,900 eligible, 7,410,783 instances, 121,824 rejected) |
| Tests | `tests/test_canonical_schema.py`, `tests/test_adapter_contract.py`, `tests/test_multiview_adapter_framework.py`, `tests/test_alibaba_gpu_2020_loader.py`, `tests/test_alibaba_gpu_2020_adapter.py` |
| Figures | System guide §5.1 (where the schema sits), §6.3 (`adapt_sources` flow) |

### 2.2.2 Execution Reconstruction and Occurrence Modeling

**What the section says:** how each dataset gets from source rows to the evaluation row. Google: window observations → execution episodes → occurrences (all executions of a recurring workload with the same start time, summed). Alibaba: the official `group` tag gives recurrence; the evaluation row is the `role_occurrence` (one task role within one job, per instance). Record levels and identity fields.

| Kind | Source |
|---|---|
| Writing source | System guide §5.3 (record levels), §5.4 (identity), §7.1 (Google Notebooks 02–03) |
| Code: Google | `pipelines/google_subset/02_reconstructExecutions.ipynb` (episodes, 5-minute gap split), `03_buildProfilesAndMetrics.ipynb` (occurrences, aligned-window sums) |
| Code: Alibaba | `src/adapters/alibaba_gpu_2020.py` — `_add_role_identity` (L261), `_add_instance_identity` (L295), `_aggregate_role_resources` (L780), `_add_resource_scope` (L818) |
| Design docs | `docs/data/google_subset_pipeline_analysis.md` (Notebooks 00–05), `docs/design/canonical_workload_schema.md` (record levels), `docs/design/alibaba_gpu_2020_adapter_design.md` |
| Results | `reports/results/google_subset/googlepipeline_finalrun.md` (253,585 executions); `reports/results/alibaba_gpu_2020/alibaba_gpu_2020_results_tasks1_6.md` |
| Figure | System guide §5.3 (record levels diagram) |

### 2.2.3 Historical Features and Time-Ordered Data

**What the section says:** chronological 70/15/15 split, point-in-time history (only occurrences completed before the current start), next-occurrence targets and target statuses. The adapter never creates these; the target builder does. Difference: Alibaba targets stay within a split, Google targets may cross.

| Kind | Source |
|---|---|
| Writing source | System guide §4.2 (target builder row), §5.5 (targets, split isolation), §10.2 (time order, point-in-time history) |
| Code: shared | `src/features/split_utils.py` — `chronological_split` (L8), used by Google Notebook 04 and Alibaba Task 4 |
| Code: Alibaba | `src/features/target_builder.py` — `iter_resource_history` (L161), `build_targets` (L245); `scripts/build_alibaba_gpu_2020_targets.py`; history statistics in `src/baselines/alibaba_gpu_2020.py` — `compute_history_statistics` (L140) |
| Code: Google | `03_buildProfilesAndMetrics.ipynb` (point-in-time history), `04_splitAndBaselines.ipynb` (split, targets) |
| Code: ML features | `src/features/ml_prep.py` — `validate_features` (L113), `purged_time_series_folds` (L359); `src/features/feature_config.py` |
| Results | Alibaba split 323,329 / 69,286 / 69,285; Google 3,473 / 675 / 731 occurrences |
| Tests | `tests/test_split_utils.py`, `tests/test_target_builder.py`, `tests/test_build_alibaba_gpu_2020_targets.py`, `tests/test_ml_prep.py` |

### 2.2.4 Recommendation Engine

**What the section says:** the seven policies — Request, Mean, P90, P95, P99 (with `min_runs` fallback to Request), ML, and Hybrid `max(ML, baseline)` — and that they are selected on validation only. Architecture level only; model detail goes to Chapters 4 and 5.

| Kind | Source |
|---|---|
| Writing source | System guide §1 (policy table), §8.1, §9 (selection) |
| Code: Google | `04_splitAndBaselines.ipynb` (baselines), `05_evaluateRecommendations.ipynb` (ML: DT, RF, XGBoost), `06_finalPolicyComparison.ipynb` (Hybrid, decision manifest) |
| Code: Alibaba | `src/baselines/alibaba_gpu_2020.py` — `add_baseline_recommendations` (L247), `select_baseline` (L469), `build_locked_recommendations` (L530); `scripts/run_alibaba_gpu_2020_baselines.py` |
| Code: Alibaba ML and Hybrid | `scripts/run_alibaba_gpu_2020_ml.py`, output `data/processed/alibaba_gpu_v2020_ml/`; `scripts/run_alibaba_gpu_2020_final_test.py`, output `data/processed/alibaba_gpu_v2020_final_test/`; features via `src/features/alibaba_gpu_2020_feature_config.py`, `src/features/alibaba_gpu_2020_ml_prep.py`; models in `src/models/alibaba_gpu_2020_{candidates,select,final_test}.py` |
| Code: shared | `src/policies/hybrid.py` — `hybrid_recommendation` (L22) |
| Design docs | `docs/planning/github_issues/task6_baselines_and_min_runs.md`, `docs/planning/github_issues/task7_machine_learning_hybrid_and_final_test.md`; D-19 in `canonical_schema_design_decisions.md` |
| Tests | `tests/test_hybrid.py`, `tests/test_alibaba_gpu_2020_baselines.py`, `tests/test_run_alibaba_gpu_2020_baselines.py` |

### 2.2.5 Shared Metrics and Evaluation Framework

**What the section says:** one set of metric formulas and one evaluator score every policy on both datasets. The capability profile decides what each number means and what may be reported (for example, no any-resource metric for Alibaba). CPU and memory have separate valid-row denominators. The evaluator scores only; it never selects.

| Kind | Source |
|---|---|
| Writing source | System guide §8 |
| Code | `src/evaluation/metrics.py` — `cpu_violation` (L16), `memory_violation` (L42), `any_resource_violation` (L68), `bounded_utilization` (L118), `waste` (L189), `shortfall` (L222); `src/evaluation/evaluator.py` — `RecommendationEvaluator` (L31), `evaluate` (L84), `summarize` (L302), `summary_metadata` (L475), `evaluate_canonical` (L645) |
| Tests | `tests/test_evaluation.py`, `tests/test_evaluator_contract.py` |
| Figure | System guide §8.1 (scoring flow) |

### 2.2.6 Artifact Repository and Presentation Layer

**What the section says:** every stage writes files with checksums and metadata (input hashes, code commit, library versions), built in staging and published only after checks; a decision manifest is locked before the one-time final test; final results go to `reports/results/<dataset>/`. The presentation layer (developer dashboard) is planned, not built.

| Kind | Source |
|---|---|
| Writing source | System guide §3 (layout), §7.2 (last paragraph), §10, §12 |
| Code | `scripts/build_alibaba_gpu_2020_canonical.py` — `verify_output` (L327), `publish` (L397); `scripts/run_alibaba_gpu_2020_baselines.py` — `verify_targets` (L92); Google `06_finalPolicyComparison.ipynb` (manifest, one-time test) |
| Artifacts | `reports/results/google_subset/` (`decision_manifest.json`, `final_test_run_metadata.json`, `n04_metadata.json`, `n05_ml_metadata.json`, `tables/`); `reports/results/alibaba_gpu_2020/` |
| Environment | `requirements-lock.txt` (untracked; needs committing) |
| Figure | System guide §10.1 (lock and final test sequence) |

---

## Check against the code

What I confirmed while building this map, and what to watch for when writing.

| # | Item | Finding | Effect on Chapter 2 |
|---|---|---|---|
| 1 | `GoogleSubsetAdapter` (Task 13) | Not on main yet | Written as complete: both datasets enter through a validated `AdapterResult`. Check the text against the merged code |
| 2 | Alibaba Task 7 (ML, Hybrid, final test) | Merged (PRs #98, #102) and run 30 Oct 2026 | Seven policies on both datasets, one-time final test on both; checked against the merged code |
| 3 | Schema version | `schema.py` is `0.2.0`, but `adapter_framework.md` line 4 still says the Python implementation is `0.1.0` | Use 0.2.0; the framework doc is stale on this line |
| 4 | Metric docs | `docs/evaluation/evaluation_metrics_v0.md` and `evaluation_output_format.md` date from April 2026 and describe the v0 evaluator | Cite `src/evaluation/` and system guide §8, not the v0 docs |
| 5 | Legacy code | `src/eval/evaluator_v0.py` and `src/baselines/baseline1_percentile_margin.py` were unused by the 295B pipeline and have been removed (still in git history at `0b07fed`) | Leave out of the report |
| 6 | Shared code in Google | Notebooks import `chronological_split` (04), `RecommendationEvaluator` (04–06) and `hybrid_recommendation` (06) from `src/` | Supports the claim that both datasets use the same split, evaluator and Hybrid code |
| 7 | Alibaba 2018 | `src/adapters/alibaba.py`, `tests/test_alibaba_adapter.py` and system guide §6.4 still mention it | Leave out; the guide's §1, §3 and §6 mentions should also be removed for consistency |
| 8 | Azure VM adapter | `src/adapters/azure_vm.py` exists (schema 0.1.0, deferred) | Leave out of the architecture, or give it one line as a future portability check (system guide §11) |
