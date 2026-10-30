# Chapter 7 Source Map: Performance, Results, and Discussion

**Purpose:** for each Chapter 7 section, the result files and the numbers to report. Chapter 7 presents **what the evaluation found** and interprets it. Methods are in Chapters 4–6; refer to them.

**Scope rules**
- Google results are final (one-time test run). Alibaba validation results through Task 6 exist; Alibaba ML, Hybrid and final test are **[Task 7]**: write the structure and the comparison as implemented, leave numbers as *pending*, and add every such sentence to `pending_checks_after_task7.md` when the chapter is written.
- Report test results as the headline and validation results for comparison; never tune or select on test.
- Units: Google CPU in normalized compute units and memory normalized; Alibaba CPU in `percent_of_vcpu` (lifetime average, labelled average-usage sizing) and memory in GB. Do not compare numbers across datasets.
- Small populations: Google 329 validation and 259 test occurrences; one occurrence moves a rate by about 0.3–0.4 points.
- Style: formal prose, few tables, figures only where useful; citations only for the two datasets.

---

## 7.1 Google ClusterData 2019 Results

### 7.1.1 Baseline Recommendation Results

| Kind | Source |
|---|---|
| Validation, all 20 candidates | `reports/results/google_subset/tables/baseline_validation_comparison.csv` |
| Selection | `n04_metadata.json`: P99 at `min_runs = 1` |
| Key validation numbers (`min_runs = 1`, any-resource violation %) | Request 55.52, Mean 42.99, P90 28.66, P95 25.30, P99 21.95 |
| Key test numbers (any-resource / CPU / memory violation %) | Request 54.47 / 50.58 / 34.24; Mean 38.22; P90 22.78; P95 17.37; P99 14.67 / 9.27 / 11.97 (`final_test_policy_comparison.csv`) |
| Waste on test (average, normalized units, CPU / memory) | Request 0.498 / 0.176; P95 7.616 / 1.541; P99 17.483 / 2.994 |
| Points to make | Percentile level trades violations for waste; Request is exceeded on more than half of occurrences, so Google requests are often too low |

### 7.1.2 ML and Hybrid Recommendation Results

| Kind | Source |
|---|---|
| Validation, all policies | `tables/validation_policy_comparison.csv` (Request, Mean, P90, P95, P99, ML, Hybrid, `Hybrid_P99` supplementary) |
| Final test, seven core policies | `tables/final_test_policy_comparison.csv`, 259 occurrences |
| Key test numbers (any-resource / CPU / memory violation %) | ML 32.82 / 30.12 / 18.92; Hybrid 12.36 / 10.81 / 7.72 |
| Waste on test (CPU / memory) | ML 0.424 / 0.130 (lowest of all); Hybrid 7.637 / 1.546 (≈ P95) |
| Points to make | Hybrid has the lowest any-resource and memory violation rates; P99 the lowest CPU violation rate; Hybrid never exceeds its P95 safeguard's violations (17.37 → 12.36) at almost the same waste; ML alone is the most efficient but under-provisions about one occurrence in three |
| Sensitivity | `tables/validation_policy_comparison_target_period_sensitivity.csv`: 225 occurrences whose targets fall in the validation period. P99 any-resource 21.95 → 18.30; Hybrid 17.93 → 17.78; the selected baseline does not change |
| Run record | `decision_manifest.json`, `final_test_run_metadata.json` (commit `e59349e`) |

### 7.1.3 Feature Importance and Explainability

| Kind | Source |
|---|---|
| Current outputs | **None.** No notebook or script in the current pipeline computes feature importance; the old v0 figures (`reports/eval/subset/figures_ml/feature_importance_*.png`) are from the superseded pipeline and are not valid sources |
| Options | (a) Compute impurity or permutation importance from the locked random forests (`n05_locked_models/`) on the training-period rows only, save the table under `reports/results/google_subset/tables/`, and report it; this uses no test data and changes no decision. (b) Drop 7.1.3 and fold a short explainability note into 7.3 |
| Decision | **Needed from the team before writing** |

## 7.2 Cross-Platform Validation Results (Alibaba GPU 2020)

| Kind | Source |
|---|---|
| Baseline validation (Task 6) | `reports/results/alibaba_gpu_2020/alibaba_gpu_2020_results_tasks1_6.md` §5: P99 at `min_runs = 10` selected; memory violation 5.58%, memory waste 8.94 GB; Request 4.74% / 22.26 GB; CPU violation P99 6.62% vs Request 15.52% |
| Sensitivity (Task 6) | Same report §5.5: same-second successors (no change), multi-instance roles (889 rows; P99 beats Request on memory violation, 10.91 vs 13.39), recurrence-weighted |
| **[Task 7]** ML and Hybrid validation | `alibaba_gpu_v2020_ml/validation_policy_comparison.csv`: seven policies on 42,069 rows: *pending* |
| **[Task 7]** Final test | PR2 final-test comparison: *pending* |
| **[Task 7]** Points to make | Whether Hybrid lowers memory violations below P99@10 and at what waste; how ML alone compares; whether the Google pattern (Hybrid best on violations at safeguard-level waste) holds on a second dataset |
| Labels | CPU results are average-usage sizing; no combined CPU-or-memory metric for Alibaba |

## 7.3 Discussion of Findings

| Topic | Source |
|---|---|
| Violation-waste trade-off across percentiles | 7.1.1, 7.2 tables |
| Value of the Hybrid safeguard | Google test: Hybrid vs P95 and P99; **[Task 7]** Alibaba |
| Requests | Google requests often too low (Request violates 54.47%); Alibaba memory requests generous (median request ≈ 7× peak, utilization 0.26) |
| Cold starts and `min_runs` | Chapter 5 §5.2.3 (Google 26 / 28 validation rows from the request; Alibaba 25.7% at `min_runs = 10`) |
| Dataset differences | Table 4.1; different units and semantics, so conclusions are compared qualitatively, not numerically |
| Limitations to flag (details in Ch9) | Google cross-split targets; small Google populations; Alibaba average CPU and selection bias (36.8% eligible) |

---

## Check against the outputs

| # | Item | Finding | Effect on Chapter 7 |
|---|---|---|---|
| 1 | Google numbers | Recomputed from the committed tables (29 Oct) | Use the tables, not the system guide prose |
| 2 | Hybrid ≤ safeguard | Holds on Google test (12.36 ≤ 17.37) | State as an observed property consistent with §4.2.3 |
| 3 | 7.1.3 | No feature-importance output exists | Team decision before writing |
| 4 | 7.2 title | "Cross-Platform Validation Results" means the Alibaba GPU 2020 results | Consider retitling to "Alibaba GPU 2020 Results" in the table of contents |
| 5 | **[Task 7]** | All Alibaba ML, Hybrid and final-test numbers | *pending*; add to the checklist |
| 6 | Figures | None exist for the new results | Create from the committed tables when writing (for example violation vs waste per policy) |
