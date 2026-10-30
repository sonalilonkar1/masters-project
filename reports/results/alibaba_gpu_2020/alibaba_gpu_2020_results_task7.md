# Alibaba GPU 2020 — Task 7 Results (ML, Hybrid and Final Test)

**Question:** Which ML models were selected for Alibaba GPU 2020, how do ML and Hybrid compare with the history baselines on validation, and what did the one-time final test show?

**Short answer:** HistGradientBoosting was selected for both CPU and memory. On the final test (44,053 rows), **Hybrid = max(ML, P99 at `min_runs = 10`)** has the lowest violation rate on both resources: 3.77% CPU and 3.15% memory, against 6.45% and 3.44% for its P99 safeguard, at almost the same memory waste (8.71 GB against 8.67 GB). ML alone is the most efficient (1.33 GB memory waste) but under-provisions 44.77% of memory targets. Request matches Hybrid on memory violations (3.16%) but wastes 2.6 times as much memory (22.31 GB) and violates CPU 16.71% of the time.

**Status:** final. PR1 (validation lock) and PR2 (final test) were run once each from a clean checkout of `main` at `fe38ea0`, after PRs #98 and #102 were merged. The test set was read once (`ml/final_test_runs.jsonl` has one entry).

---

## 0. Evidence and provenance

| Item | Source |
|---|---|
| Canonical data | Shared Task 3 build from `c2ae87f`; `--verify` passed (1,254,108 roles, 7,410,783 instances, 121,824 rejected) |
| Targets | `build_alibaba_gpu_2020_targets.py` at `fe38ea0`: `targets/metadata.json`, `targets/SHA256SUMS` |
| Baselines | `run_alibaba_gpu_2020_baselines.py` at `fe38ea0`: P99 at `min_runs = 10`, numbers identical to `alibaba_gpu_2020_results_tasks1_6.md` §5; files in `baselines/` |
| PR1 | `run_alibaba_gpu_2020_ml.py` at `fe38ea0`, clean, 2 min 53 s; locked `2026-10-30T17:33:08Z`; decision manifest SHA-256 `dd6819bf…a34f925`; files in `ml/` |
| Final test | `run_alibaba_gpu_2020_final_test.py` at `fe38ea0`, clean, same commit as the PR1 lock, 7 s; `2026-10-30T17:37:58Z`; files in `final_test/` |
| Software | Python 3.12.9, numpy 2.5.4, pandas 2.3.3, scikit-learn 1.9.1, XGBoost 3.4.1, joblib 1.6.0 (`requirements-lock.txt`) |

Units: memory in GB per instance of a task role; CPU in `percent_of_vcpu`, the lifetime average per run (average-usage sizing, not peak safety). No combined CPU-or-memory metric is reported. Waste and shortfall are averages per scored row. Large files (Parquet tables, model files) stay in `data/processed/` and are identified by the `SHA256SUMS` copies here.

---

## 1. Model selection (validation)

Every candidate is fitted on the training rows with an available target (CPU 220,299; memory 220,832) and scored on validation (CPU 41,913; memory 42,069). Selection order: RMSE, MAE, violation %, average shortfall, model name. The mean `DummyRegressor` is scored but never selected. One fixed setting per model; 25 input features, 43 columns after one-hot encoding. Source: `ml/candidate_models.csv`, `ml/model_selection.json`.

| Resource | Model | RMSE | MAE | R² | Violation % | Avg. shortfall | Clipped | Selected |
|---|---|---|---|---|---|---|---|---|
| CPU | dummy (mean) | 858.95 | 566.23 | −0.049 | 11.97 | 190.73 | 0 | floor |
| CPU | decision tree | 519.17 | 167.49 | 0.617 | 55.59 | 79.09 | 0 | |
| CPU | random forest | 425.97 | 134.67 | 0.742 | 53.98 | 54.39 | 0 | |
| CPU | **HistGradientBoosting** | **412.94** | 135.72 | 0.758 | 41.91 | 49.23 | 151 | ✓ |
| CPU | XGBoost | 415.04 | 134.48 | 0.755 | 45.35 | 49.82 | 1 | |
| Memory | dummy (mean) | 13.28 | 9.23 | −0.030 | 24.79 | 3.49 | 0 | floor |
| Memory | decision tree | 10.34 | 3.62 | 0.376 | 47.75 | 1.42 | 0 | |
| Memory | random forest | 9.16 | 3.21 | 0.510 | 46.38 | 1.24 | 0 | |
| Memory | **HistGradientBoosting** | **8.98** | 3.14 | 0.529 | 47.76 | 1.24 | 376 | ✓ |
| Memory | XGBoost | 9.09 | 3.22 | 0.518 | 50.01 | 1.23 | 353 | |

HistGradientBoosting settings: `max_iter = 100`, `learning_rate = 0.1`, `max_leaf_nodes = 31`, `random_state = 42` (scikit-learn defaults). The dummy has the lowest violation rate of all candidates on both resources, which is why a violation-first order would have selected it (design decision D-19).

## 2. Validation comparison (42,069 rows)

Models trained on train only. Hybrid's safeguard is the selected Task 6 baseline (P99 at `min_runs = 10`), which always has a value because it falls back to the request when history is short: Hybrid fell back to ML on 0 rows. Source: `ml/validation_policy_comparison.csv`, `ml/metadata.json`.

| Policy | CPU viol. % | Memory viol. % | CPU waste | Memory waste (GB) | CPU util. | Memory util. |
|---|---|---|---|---|---|---|
| Request | 15.52 | 4.74 | 430.06 | 22.26 | 0.37 | 0.26 |
| Mean | 40.84 | 39.90 | 142.56 | 6.85 | 0.78 | 0.74 |
| P90 | 12.25 | 12.40 | 235.44 | 7.80 | 0.70 | 0.68 |
| P95 | 9.00 | 8.46 | 263.08 | 8.26 | 0.68 | 0.66 |
| P99 | 6.62 | 5.58 | 294.96 | 8.94 | 0.64 | 0.63 |
| ML | 41.91 | 47.76 | 86.50 | 1.90 | 0.82 | 0.85 |
| Hybrid | 4.60 | 5.15 | 305.62 | 9.14 | 0.63 | 0.62 |

The validation split also selected the ML models, so the ML and Hybrid validation rows are optimistic; the final test below is the unbiased result.

## 3. Final test (44,053 rows, run once)

Locked models refitted on train + validation; no training, selection or manifest change. CPU valid rows 44,045, memory 44,053. Negative predictions clipped: CPU 44, memory 18. Hybrid fell back to ML on 0 rows. Source: `final_test/final_test_policy_comparison.csv`, `final_test/run_record.json`.

| Policy | CPU viol. % | Memory viol. % | CPU waste | Memory waste (GB) | CPU util. | Memory util. | CPU shortfall | Memory shortfall (GB) |
|---|---|---|---|---|---|---|---|---|
| Request | 16.71 | 3.16 | 419.97 | 22.31 | 0.38 | 0.25 | 191.46 | 0.66 |
| Mean | 41.83 | 37.02 | 138.75 | 6.45 | 0.79 | 0.75 | 81.05 | 0.61 |
| P90 | 12.41 | 9.89 | 237.57 | 7.44 | 0.70 | 0.68 | 48.06 | 0.30 |
| P95 | 9.10 | 6.04 | 266.95 | 7.89 | 0.68 | 0.66 | 45.27 | 0.26 |
| P99 | 6.45 | 3.44 | 306.44 | 8.67 | 0.65 | 0.62 | 43.53 | 0.23 |
| ML | 47.37 | 44.77 | 72.01 | 1.33 | 0.86 | 0.84 | 78.38 | 1.05 |
| **Hybrid** | **3.77** | **3.15** | 326.82 | 8.71 | 0.63 | 0.62 | **20.54** | **0.20** |

Observations:
- Hybrid has the lowest violation rate and the lowest average shortfall on both resources. It never exceeds its safeguard's violations (CPU 3.77 ≤ 6.45; memory 3.15 ≤ 3.44), as the max rule implies.
- Hybrid's memory waste is 0.04 GB above P99's; its CPU waste is 6.7% above P99's.
- ML alone is the most efficient policy but under-provisions roughly every second run.
- Request ties Hybrid on memory violations (3.16 against 3.15) at 2.6 times the memory waste, and has more than four times Hybrid's CPU violation rate.
- Memory violation rates are lower on test than on validation for every history policy (P99 5.58 → 3.44), so the split periods differ; the ranking of policies is unchanged.

## 4. Final-test sensitivity

Source: `final_test/final_test_sensitivity.csv`.

| Cut | Rows | P99 CPU / memory viol. % | Hybrid CPU / memory viol. % | Request CPU / memory viol. % |
|---|---|---|---|---|
| All rows (occurrence-weighted) | 44,053 | 6.45 / 3.44 | 3.77 / 3.15 | 16.71 / 3.16 |
| Same-second successors excluded | 43,802 | 6.48 / 3.46 | 3.78 / 3.16 | 16.81 / 3.17 |
| Same-second successors only | 251 | 1.20 / 1.20 | 1.20 / 1.20 | 0.00 / 1.99 |
| Multi-instance roles (`inst_num > 1`) | 595 | 12.10 / 8.07 | 5.55 / 5.71 | 14.79 / 13.45 |
| Group-weighted (each recurrence equal) | 44,053 | 11.38 / 4.17 | 4.08 / 3.71 | 21.22 / 4.11 |

Hybrid has the lowest or equal-lowest violation rates in every cut except same-second CPU, where Request has none on 251 rows. On multi-instance roles Hybrid's gain over P99 is largest.

## 5. Limitations

- CPU is the lifetime average per run, so CPU results describe average-usage sizing, not peak safety.
- One fixed setting per model and no hyperparameter search; validation results for ML and Hybrid are optimistic because the same split selected the models.
- Only eligible roles are evaluated (36.8% of roles; `alibaba_gpu_2020_results_tasks1_6.md` §2), and most evaluated roles are single-instance.
- GPU fields are used as features only; GPU sizing is not evaluated.
