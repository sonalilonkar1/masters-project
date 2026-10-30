# Google Subset Pipeline: Final Run (Notebooks 01–06)

**Question:** What are the final Google subset results, from the data pipeline through the one-time final test?

**Short answer:** On the final test (259 occurrences with both targets), **Hybrid** (`max(ML prediction, P95)`) has the lowest any-resource violation rate of the seven policies, **12.36%**, against 14.67% for P99, 17.38% for P95 and 54.48% for Request. Its memory violation rate (7.72%) is also the lowest. It keeps P95's waste (CPU 7.64 against 7.62; memory 1.55 against 1.54) and has less than half of P99's (17.48 and 2.99). ML alone wastes the least but is exceeded on 32.82% of occurrences. P99 has the lowest CPU violation rate (9.27%, against 10.81% for Hybrid).

**Status:** final. The decisions were frozen in `decision_manifest.json` (status `final`) before any test target was read, and the final test was run once.

---

## 1. Run details

| Item | Value |
|---|---|
| Date | 29 Oct 2026 |
| Code | `main` at `e59349e` (clean tree; recorded in the decision manifest) |
| Environment | Locked environment (`requirements-lock.txt`): Python 3.12.9, pandas 2.3.3, numpy 2.5.4, scikit-learn 1.9.1, xgboost 3.4.1, pyarrow 23.0.1; Jupyter kernel `traceadvisor-lock` |
| Input | `subset/borg_traces_data.csv` (Kaggle sample of Google ClusterData 2019) |
| Working outputs | `data/processed/google_subset_v1/` (not tracked by Git) |
| Copies of the results | this folder: `tables/`, `decision_manifest.json`, `final_test_run_metadata.json`, `n04_metadata.json`, `n05_ml_metadata.json` |

| Notebook | Run |
|---|---|
| `01_dataIngestion` to `04_splitAndBaselines` | Rerun in order; outputs byte-identical to the existing outputs |
| `05_evaluateRecommendations` | Run in the locked environment; reproduces the committed report table 5.1 exactly |
| `06_finalPolicyComparison`, freeze | `FREEZE_STATUS = "final"`; manifest written at 20:03:25 UTC with 13 hashed inputs |
| `06_finalPolicyComparison`, final test | `RUN_FINAL_TEST = True`; run once at 20:03:35 UTC; all freeze checks passed |

The two Notebook 06 parameters were set in memory when the notebook was run; the notebook file was not changed.

## 2. Frozen decisions

From `decision_manifest.json` (SHA-256 `0669ca5c…fa775`):

| Decision | Value | Source |
|---|---|---|
| Split | Chronological 70/15/15, equal start times kept together | Notebook 04 |
| Baseline policy and `min_runs` | **P99, `min_runs = 1`** | Notebook 04, validation only |
| ML models | CPU: **Random Forest** (`max_depth = 10`, `min_samples_leaf = 10`, `max_features = sqrt`, 300 trees); memory: **Random Forest** (`max_depth = 6`, otherwise the same); seed 42 | Notebook 05, lowest validation `log1p` RMSE |
| Hybrid rule | `max(ML prediction, P95)` per resource; ML prediction where P95 is unavailable | Project starting rule (`assumptions.md` P-9), fixed in advance |
| Supplementary | `Hybrid_P99 = max(ML prediction, P99)`, reported on validation only | Not a decision |
| Evaluation population | Occurrences with both next-occurrence CPU and memory targets | Notebook 04 rule |

## 3. Data and splits

| | Train | Validation | Test |
|---|---|---|---|
| Execution rows (253,585 total) | 178,858 (70.5%) | 36,703 (14.5%) | 38,024 (15.0%) |
| Occurrences | 3,473 | 675 | 731 |
| Evaluated (both targets present) | — | 329 | 259 |

## 4. Final test results

259 occurrences. CPU in normalized CPU units (NCU), memory in normalized units. Violation: the recommendation is below the next occurrence's peak. Waste and shortfall are averages per occurrence.

| Policy | CPU viol. % | Mem. viol. % | Any-resource viol. % | CPU util. | Mem. util. | CPU waste | Mem. waste | CPU shortfall | Mem. shortfall |
|---|---|---|---|---|---|---|---|---|---|
| Request | 50.58 | 34.24 | 54.47 | 0.617 | 0.548 | 0.498 | 0.176 | 1.078 | 0.187 |
| Mean | 28.57 | 33.59 | 38.22 | 0.436 | 0.491 | 1.226 | 0.235 | 0.811 | 0.126 |
| P90 | 18.15 | 16.60 | 22.78 | 0.330 | 0.383 | 3.847 | 0.744 | 0.509 | 0.077 |
| P95 | 13.13 | 13.13 | 17.38 | 0.278 | 0.342 | 7.616 | 1.541 | 0.371 | 0.043 |
| P99 | **9.27** | 11.97 | 14.67 | 0.233 | 0.297 | 17.483 | 2.994 | **0.220** | **0.039** |
| ML | 30.12 | 18.92 | 32.82 | 0.431 | 0.312 | **0.424** | **0.130** | 1.065 | 0.165 |
| **Hybrid** | 10.81 | **7.72** | **12.36** | 0.242 | 0.190 | 7.637 | 1.546 | 0.365 | 0.042 |

Valid denominators are 259 for every policy and resource, except Request (257 for violations; 254 for CPU utilization), Mean, P90, P95 and P99 (258 for CPU utilization). Source: `tables/final_test_policy_comparison.csv`.

**Findings:**
- **Hybrid is the safest policy overall:** the lowest any-resource (12.36%) and memory (7.72%) violation rates. It is safer than P95, the baseline it uses, on CPU (10.81% against 13.13%), memory (7.72% against 13.13%) and any resource (12.36% against 17.38%), at almost the same waste (CPU 7.64 against 7.62; memory 1.55 against 1.54).
- **Hybrid against P99**, the validation-selected baseline: fewer violations on memory (7.72% against 11.97%) and any resource (12.36% against 14.67%), and less than half the waste (CPU 7.64 against 17.48; memory 1.55 against 2.99). P99 has fewer CPU violations (9.27% against 10.81%).
- **ML alone** is the most efficient (lowest CPU and memory waste) but under-provisions on a third of occurrences (32.82%), as expected of a point prediction. The ML prediction raises the P95 floor in Hybrid where the history understates the next run.
- **Request**, the current practice, violates on more than half of the occurrences (54.47%).

## 5. Validation results (for comparison)

329 occurrences. Source: `tables/validation_policy_comparison.csv`. The five baseline rows reproduce Notebook 04 exactly.

| Policy | CPU viol. % | Mem. viol. % | Any-resource viol. % | CPU waste | Mem. waste |
|---|---|---|---|---|---|
| Request | 52.15 | 38.04 | 55.52 | 0.957 | 0.449 |
| Mean | 35.37 | 34.15 | 42.99 | 1.740 | 0.363 |
| P90 | 22.26 | 21.65 | 28.66 | 4.856 | 0.980 |
| P95 | 18.60 | 19.82 | 25.30 | 8.449 | 1.865 |
| P99 | 16.77 | 17.07 | 21.95 | 19.041 | 3.346 |
| ML | 30.40 | 25.23 | 34.95 | 0.462 | 0.155 |
| Hybrid | 13.37 | 14.59 | 17.93 | 8.470 | 1.867 |
| Hybrid_P99 (supplementary) | 11.85 | 12.77 | 15.50 | 19.026 | 3.343 |

The any-resource violation ordering is the same on validation and test (Hybrid, P99, P95, P90, ML, Mean, Request). Every policy's any-resource violation rate is lower on test than on validation.

### 5.1 Target-period sensitivity (validation)

Google targets are built before the split, so 104 of the 329 validation occurrences have a next occurrence in the test period. Rescored on the 225 occurrences whose targets stay in the validation period (`tables/validation_policy_comparison_target_period_sensitivity.csv`):

| Policy | Any-resource viol. %, all 329 | Any-resource viol. %, 225 in-period |
|---|---|---|
| P95 | 25.30 | 23.21 |
| P99 | 21.95 | 18.30 |
| ML | 34.95 | 36.89 |
| Hybrid | 17.93 | 17.78 |
| Hybrid_P99 | 15.50 | 14.22 |

The selected baseline and the policy ordering do not change. This is a documented limitation and was not corrected (Task 10 not done).

## 6. Model selection (Notebook 05, validation)

Per resource, the lowest validation RMSE on the `log1p` scale among the tuned candidates (Decision Tree, Random Forest, XGBoost); a median reference and untuned starting models are reported for comparison (`tables/ml_validation_model_comparison.csv`).

| Resource | Selected | Train rows | Validation rows | log1p RMSE | Raw R² |
|---|---|---|---|---|---|
| CPU | Random Forest (tuned) | 1,672 | 329 | 0.850 | −0.005 |
| Memory | Random Forest (tuned) | 1,649 | 329 | 0.387 | 0.107 |

Point accuracy is modest (raw R² near zero for CPU), which is why ML is combined with a historical floor in Hybrid.

## 7. Limitations

- **Targets cross split boundaries** (§5.1): validation numbers are somewhat optimistic; the final test uses test-period occurrences only as current rows.
- **Small evaluation populations:** 329 validation and 259 test occurrences; one occurrence changes a rate by about 0.3–0.4 percentage points.
- **Kaggle sample:** results are for the 31-day sample, not the full ClusterData 2019 trace.
- **Normalized units:** CPU and memory are in Google's normalized units, so waste is not in cores or GB.

## 8. How to reproduce

1. Create the locked environment from `requirements-lock.txt` (instructions at the top of the file).
2. Run `pipelines/google_subset/01` to `05` in order with the `traceadvisor-lock` kernel.
3. Notebook 06 can freeze and run the final test only once: a final manifest or final-test result already exists in `data/processed/google_subset_v1/`, and the notebook refuses to overwrite either. To reproduce elsewhere, freeze from a clean checkout of `e59349e` (`FREEZE_STATUS = "final"`), then run with `RUN_FINAL_TEST = True` at the same commit.
