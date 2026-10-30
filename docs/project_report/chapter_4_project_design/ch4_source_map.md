# Chapter 4 Source Map: Project Design

**Purpose:** for each Chapter 4 section, the design decisions, code and artifacts to read before writing it. Chapter 4 explains **what was designed and why**. How it was built goes in Chapter 5, how it was tested in Chapter 6, and the numbers in Chapter 7.

**Scope rules**
- Datasets: Google ClusterData 2019 (Kaggle subset) and Alibaba GPU Cluster Trace 2020. Alibaba 2018 is not in the report.
- The old report draft and `REPORT_TRACEABILITY.md` are not sources; nor are `docs/data/google_clusterdata_2019_analysis.md` (full trace) or `docs/data/alibaba_gpu_2020_evidence_and_limitations.md` (dropped).
- Task 13, Alibaba Task 7 and the presentation layer are written as implemented. Statements that depend on Alibaba Task 7 go in `docs/project_report/pending_checks_after_task7.md`; Task 13 and the presentation layer are written as implemented and are not tracked there.
- Every factual claim is checked against code, committed config or real outputs, not only documents.
- Line numbers are from the working tree on `docs/issue-17-final-report` (after `0b07fed`).

**Main design sources**
| Source | Use |
|---|---|
| `docs/design/traceadvisor_system_guide.md` | Writing source for every section |
| `docs/design/canonical_schema_design_decisions.md` | D-01 to D-24: the decisions and their reasons |
| `docs/planning/assumptions.md` | P-1 to P-11: project-level assumptions |
| `docs/design/canonical_workload_schema.md`, `adapter_framework.md`, `alibaba_gpu_2020_adapter_design.md`, `alibaba_gpu_2020_output_contract.md` | Schema, adapter and Alibaba design (verified up to date) |
| `docs/planning/github_issues/task6_baselines_and_min_runs.md`, `task7_machine_learning_hybrid_and_final_test.md`, `task13_google_subset_thin_adapter.md` | Baseline, ML, Hybrid, lock and Google adapter design |
| `docs/data/google_subset_pipeline_analysis.md` | Google pipeline design (Notebooks 00–05) |

---

## 4.1 Data Pipeline Design

**What the section says:** the design of the path from raw trace to evaluation-ready rows, and why. (1) One canonical schema with separate meanings for request, average, peak and actual, explicit units, and nulls never filled. (2) Dataset capability profiles that drive validation, targets and reporting. (3) Adapters own source-specific work; a separate target builder owns splits, history and targets. (4) Record levels: Google's full-workload occurrence and Alibaba's role-occurrence, and why each was chosen. (5) Identity: constructed recurrence for Google, official tag plus role for Alibaba. (6) Time-ordered design: chronological split that keeps equal start times together, point-in-time history, next-run targets, and split-isolated targets for Alibaba. (7) Eligibility kept separate from validity; ineligible rows retained.

| Kind | Source |
|---|---|
| Writing source | System guide §4.2, §5, §6.1, §6.6, §7 |
| Decisions | D-03 (`role_occurrence`), D-04 (Alibaba identity), D-05 (jobs without `group`), D-10 (CPU average-only), D-11 (memory = max over workers), D-12 (units), D-14 (scope and aggregation), D-15 (validity vs eligibility vs capability), D-16 (missing values), D-17 (eligibility rules), D-18 (splits, history, split-isolated targets), D-23 (rejected output) |
| Assumptions | P-2 (never merge datasets), P-3 (own semantics), P-5 (nulls), P-6 (units), P-11 (70/15/15) |
| Design docs | `canonical_workload_schema.md` §3–§11; `adapter_framework.md` §3–§4, §8; `alibaba_gpu_2020_adapter_design.md`; `alibaba_gpu_2020_output_contract.md` |
| Code: schema and profiles | `src/canonical/schema.py` — `DatasetCapabilities` (L127), `GOOGLE_CAPABILITIES` (L266), `ALIBABA_GPU_2020_CAPABILITIES` (L325) |
| Code: adapter boundary | `src/adapters/validation.py` — `_reject_target_builder_columns` (L173), `validate_adapter_output` (L189) |
| Code: Alibaba aggregation | `src/adapters/alibaba_gpu_2020.py` — `_failed_rules` (14 rules), `_assign_exclusion_reasons` (first broken rule wins), `_aggregate_role_resources` (L780) |
| Code: time-ordered data | `src/features/split_utils.py` — `chronological_split` (L8; boundaries only between timestamp groups); `src/features/target_builder.py` — `iter_resource_history` (L161; history uses `end_time_us ≤ start_time_us`), `build_targets` (L245; target statuses, split isolation) |
| Code: Google | `pipelines/google_subset/02_reconstructExecutions.ipynb`, `03_buildProfilesAndMetrics.ipynb`, `04_splitAndBaselines.ipynb`; `src/adapters/google_subset.py` *(Task 13)* |
| Possible figure | Record levels (system guide §5.3), only if Chapter 4 needs one |

## 4.2 Recommendation Model Design

**Intro:** the seven policies, the principle that every choice is made on validation only, and one shared evaluator for all of them.

| Kind | Source |
|---|---|
| Writing source | System guide §1, §8.1, §9 |
| Assumptions | P-9 (policies compared), P-10 (validation-only selection, lock, one-time test) |
| Decisions | D-19 (evaluation and selection rules) |

### 4.2.1 Historical Percentile Baselines

**What the section says:** Request as the status quo; Mean, P90, P95 and P99 of point-in-time history; the `min_runs` threshold and fallback to Request; candidate grid of four policies × four `min_runs` values; validation-only selection with dataset-specific ranking (Google: any-resource violation first; Alibaba: memory first); why Request is reported but not selectable on Alibaba.

| Kind | Source |
|---|---|
| Writing source | System guide §1, §9 (including "Why Request is not selectable") |
| Code: Google | `04_splitAndBaselines.ipynb` — `MIN_RUNS_CANDIDATES = [1, 3, 5, 10]`; ranking: any-resource violation, worst single-resource violation, CPU + memory violation, CPU waste, memory waste, lower `min_runs` |
| Code: Alibaba | `src/baselines/alibaba_gpu_2020.py` — `MIN_RUNS_CANDIDATES`, `HISTORY_POLICIES`, `SELECTABLE_POLICIES` (Request excluded), `SELECTION_SORT_ORDER` (memory violation, memory waste, CPU violation, CPU waste, `min_runs`, policy), `add_baseline_recommendations` (L247; per-resource fallback), `freeze_common_validation_population` (L374), `select_baseline` (L469) |
| Design docs | Task 6 issue §2–§6; D-19 |
| Results (for checking only) | `reports/results/google_subset/n04_metadata.json`, `tables/baseline_validation_comparison.csv`; `reports/results/alibaba_gpu_2020/alibaba_gpu_2020_results_tasks1_6.md` |

### 4.2.2 Machine Learning Forecasting

**What the section says:** the prediction task (next-run usage per resource), per-dataset and per-resource models, pre-execution features only and the leakage exclusion list, missing-value design, target transform, candidate families, tuning respecting time order, accuracy-based selection on validation, refit on train plus validation for the final model.

| Kind | Source |
|---|---|
| Writing source | System guide §9 (ML candidates, ranking, "Why ML selection is accuracy-first"), §10.2 (pre-execution features) |
| Google features | `data/processed/google_subset_v1/ml_feature_manifest.json` (from `src/features/feature_config.py` — `OCCURRENCE_FEATURE_COLS`, L147): 24 features (occurrence requests, execution count, request variety, prior completed occurrence count, history count/mean/std/P90/P95/P99 for CPU peak, memory peak and runtime); 8 leaky columns and 3 leaky prefixes excluded; NaN kept for models with native missing support, no imputation; `log1p` target; labels used only if the next occurrence starts within the learnable period |
| Google tuning and selection | `05_evaluateRecommendations.ipynb`; `reports/results/google_subset/n05_ml_metadata.json` (`tuning`, `selection_rule`: lowest validation RMSE on `log1p`, tie-break raw MAE); `src/features/ml_prep.py` — `purged_time_series_folds` (L359), `select_label_period_rows` (L331) |
| Alibaba features | Task 7 issue "Features" (requests, Task 4 history counts, Task 6 history statistics, GPU type only if a canonical pre-execution field; explicit never-use list passed to `validate_features`; missing-indicator column per history statistic before zero fill) |
| Alibaba models and selection | Task 7 issue "Candidate Models", "Validation-Only Selection" (fit on train, score on validation, no CV search); refit on train plus validation (Phase 3) |
| Code: leakage check | `src/features/ml_prep.py` — `validate_features` (L113), `prepare_xy` (L27) |
| Decisions | D-19 (uncommitted edit: accuracy-first ML selection) |

### 4.2.3 Hybrid Risk-Aware Layer

**What the section says:** why Hybrid exists (ML predicts accurately but under-provisions on its own; a historical baseline guards against that), the rule `max(ML, baseline)` per resource, no tunable parameters, fallback to ML when the baseline is missing, and the safeguard choice per dataset: Google uses P95, fixed in advance from the project backlog (not tuned), with `max(ML, P99)` reported as a supplement; Alibaba uses the baseline selected in Task 6.

| Kind | Source |
|---|---|
| Writing source | System guide §8.1, §8.4 (safeguard and missing-safeguard rows), §9 |
| Code | `src/policies/hybrid.py` — `hybrid_recommendation` (L22): `np.fmax`, returns a `safeguard_missing` flag |
| Google | `reports/results/google_subset/decision_manifest.json` → `hybrid_rule`, `hybrid_fallback`, `hybrid_rule_rationale` ("fixed in advance, not tuned on validation"), `supplementary_policies.Hybrid_P99`; `06_finalPolicyComparison.ipynb` |
| Alibaba | Task 7 issue Phase 2 (one fixed rule, no variants; validation predictions from train-only models) |
| Assumptions | P-9 (Hybrid starts from `max(ML, P95)`) |

## 4.3 Replay and Evaluation Framework Design

**What the section says:** offline replay in time order; one evaluator and one set of metric formulas for every policy; per-resource validity and separate denominators; missing never counted as a success; the profile decides labels and what may be reported; a common evaluation population frozen before scoring so all policies are compared on the same rows; the evaluator scores but never selects; lock-then-test with a one-time final test.

| Kind | Source |
|---|---|
| Writing source | System guide §8, §10 |
| Code: metrics | `src/evaluation/metrics.py` — `cpu_violation` (L16), `memory_violation` (L42), `any_resource_violation` (L68), `bounded_utilization` (L118; capped, NaN when recommendation ≈ 0), `waste` (L189), `shortfall` (L222) |
| Code: evaluator | `src/evaluation/evaluator.py` — `RecommendationEvaluator` (L31; `reports_any_resource`), `evaluate` (L84), `summarize` (L302), `summary_metadata` (L475), `evaluate_canonical` (L645) |
| Common population | Google: both targets available (`decision_manifest.json` → `evaluation_population`; Notebook 04 metadata `common_validation_population`). Alibaba: at least one target available, per-resource denominators (`freeze_common_validation_population`, L374) |
| Sensitivity | Alibaba `build_sensitivity_tables` (L656; same-second, multi-instance, group-weighted); Google target-period sensitivity (`tables/validation_policy_comparison_target_period_sensitivity.csv`) |
| Lock and final test | Google `decision_manifest.json`, `final_test_run_metadata.json`; Task 7 issue Phases 3–4 |
| Decisions and assumptions | D-19; P-4, P-5, P-8, P-10 |
| Possible figure | Lock and one-time final test (system guide §10.1) |

## 4.4 Artifact and Presentation Layer Design

**What the section says:** file-based stages with verified inputs and staged, checked publishing; per-stage metadata and checksums for provenance; the decision manifest as the boundary between selection and test; and the presentation layer design (a read-only REST API over the published results, with a web frontend on top), kept general.

| Kind | Source |
|---|---|
| Writing source | System guide §2.1, §7.2 (last paragraph), §10.2, §12 |
| Code | `scripts/build_alibaba_gpu_2020_canonical.py` — `verify_output` (L327), `publish` (L397); `scripts/run_alibaba_gpu_2020_baselines.py` — `verify_targets` (L92) |
| Artifacts | `reports/results/google_subset/` (manifest, run metadata, tables); `data/processed/alibaba_gpu_v2020/metadata.json`, `SHA256SUMS` |
| Presentation | No code or stack yet; keep general, written as implemented |

---

## Check against the code

| # | Item | Finding | Effect on Chapter 4 |
|---|---|---|---|
| 1 | Google ML features | Notebook 05 uses the 24 `OCCURRENCE_FEATURE_COLS` recorded in `ml_feature_manifest.json`. The older `FEATURE_COLS` list in the same file (295A profile features such as confidence tiers) is not used by the final pipeline | Describe the 24 occurrence features; ignore `FEATURE_COLS` |
| 2 | Missing-value design differs | Google keeps NaN for models with native missing support (no imputation); Alibaba adds a missing-indicator per history statistic, then zero-fills | State both in 4.2.2 with the reason (zero and missing must stay distinguishable) |
| 3 | Hybrid safeguard differs | Google's safeguard is P95, fixed in advance from the backlog, although Notebook 04 selected P99 as the best baseline; `max(ML, P99)` is reported as a supplement. Alibaba uses its selected baseline (P99 at `min_runs = 10`) | Explain both choices in 4.2.3 so the difference does not look inconsistent |
| 4 | Common population differs | Google requires both targets; Alibaba requires at least one, with per-resource denominators | State in 4.3 |
| 5 | ML ranking order (D1) | System guide §9 and the D-19 edit: accuracy first. Task 7 issue D-2: violation first | Write accuracy first, as in the system guide; listed in `pending_checks_after_task7.md` D1 |
| 6 | Section title 4.2.3 | "Hybrid Risk-Aware Layer": there is no risk level or safety-buffer setting; the risk control is the baseline floor | Keep the title but define "risk-aware" as the baseline floor, or retitle to "Hybrid Safeguard Layer" |
| 7 | Google split boundary | Google targets may cross splits (104 of 330 validation targets in the test period); Alibaba targets are split-isolated | Explain as a design difference and known limitation in 4.1, consistent with Chapter 2 |
