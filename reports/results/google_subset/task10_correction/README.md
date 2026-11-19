# Task 10 (#115): Google Subset Target Correction, Before/After Comparison and Leakage Audit

**Question:** What changes when Google next-occurrence targets are built after split assignment, inside each split, instead of on the full occurrence table?

**Short answer:** 442 targets that came from a later split are now null: 338 in train, 104 in validation and none in test. The common validation population shrinks from 329 to 225 occurrences. The validation-only baseline selection is unchanged (**P99, `min_runs = 1`**), and its any-resource violation rate moves from 21.95% to **18.30%**. That drop does not mean P99 got better: its recommendations are the same as before. Only the scored population changed. The 104 occurrences that left had targets in the test period and a higher violation rate (29.81%, finding F4 in `docs/data/google_subset_pipeline_analysis.md`). The ML model choice and hyperparameters are unchanged (Random Forest for CPU and memory). The locked models are refit on fewer rows, so the test ML predictions change.

**Status:** corrected Notebook 04 and Notebook 05 outputs. No test metric was computed and nothing was scored on test (Notebook 06 was not run). Test target columns were read only to count how many exist and to confirm that the correction did not change them. The earlier Google validation numbers, and the earlier ML and Hybrid final-test numbers, are **superseded** (see section 6).

---

## 1. What changed

| Item | Before (published run, 29 Oct 2026) | After (Task 10) |
|---|---|---|
| Target construction | Once on the complete occurrence table, before splitting | After split assignment, separately inside each split |
| `target_split_isolation` in `metadata.json` | A sentence saying labels may cross splits | `true` |
| Cross-split target | Kept (true next occurrence in a later split) | Null, with `target_null_reason = "next_occurrence_in_other_split"` |
| Final occurrence of a recurrence | Null | Null, with `target_null_reason = "no_next_occurrence"` |
| `target_policy_version` | `next_distinct_full_workload_occurrence_v3` | `next_distinct_full_workload_occurrence_v4_split_isolated` |
| Training targets in later splits (decision D-1) | Kept in the artifact; N05 excluded them from training with its label-period rule | Null in the artifact; the N05 rule is kept as a second guard |

Files changed: `pipelines/google_subset/04_splitAndBaselines.ipynb` (code cells 16, 25, 26, 45, 48, 51; markdown cells 0, 21, 24, 52), `pipelines/google_subset/05_evaluateRecommendations.ipynb` (markdown cells 9, 24, 26 and 27 only; no code change), and `tests/test_google_canonical_contract.py`. No shared module, schema, adapter, evaluator, target builder or Alibaba/Azure file changed.

Unchanged by the correction, and checked:

- Split boundaries and row counts: train ends at 1,812,600,000,000 µs, validation spans 1,813,200,000,000–2,261,100,000,000 µs, and test starts at 2,262,600,000,000 µs. Execution rows are 178,858 / 36,703 / 38,024 and occurrences 3,473 / 675 / 731.
- Every non-target column of the six occurrence and execution artifacts is identical to the earlier run, including every `rec_*` baseline recommendation and every `uses_history_*` flag.
- No target value changed. The correction only nulls targets. Every remaining target equals the earlier target and is the true next occurrence of its recurrence.
- Missing memory stays NaN. Grouping and ordering are unchanged (`shift(-1)` within `recurrence_key`, ordered by `execution_start_time_us`).
- The test split has no cross-split targets, so its targets are unchanged (259 occurrences with both targets).

## 2. Leakage audit: changed-row counts

Source: `leakage_audit.csv`.

| Split | Occurrences | Targets before | Targets after | Nulled (crossed a split) | Nulled target was in validation | Nulled target was in test | Null, no next occurrence |
|---|---|---|---|---|---|---|---|
| Train | 3,473 | 2,010 | 1,672 | **338** | 210 | 128 | 1,463 |
| Validation | 675 | 330 | 226 | **104** | 0 | 104 | 345 |
| Test | 731 | 259 | 259 | **0** | 0 | 0 | 472 |

- **Rows leaving the validation population:** 104 (329 → 225). These are exactly the 104 validation occurrences whose earlier target came from the test period. No row entered the population.
- **Execution-level artifacts:** the same nulling repeated on every execution row of an affected occurrence: 23,347 train rows and 8,897 validation rows. These files are compatibility artifacts and are not evaluated.
- These counts match findings F3 and F4 in `docs/data/google_subset_pipeline_analysis.md`, and the `cross_split_targets_removed` field in the corrected `metadata.json`.
- **Overlapping occurrences (F2) are kept:** 7 train, 1 validation and 1 test targets start before the current occurrence ends. The target still starts strictly later. This behavior was not changed (out of scope).

## 3. Validation baseline selection

Source: `baseline_validation_before_after.csv` (all 20 configurations) and `selection_before_after.json`. Selection uses validation only, with the unchanged Notebook 04 sort order.

| | Before | After |
|---|---|---|
| Common validation population | 329 | **225** |
| Selected policy and `min_runs` | P99, 1 | **P99, 1** (unchanged) |
| Valid any-resource rows (selected) | 328 | 224 |
| CPU violation % (selected) | 16.77 | **12.95** |
| Memory violation % (selected) | 17.07 | **15.62** |
| Any-resource violation % (selected) | 21.95 | **18.30** |
| Average CPU waste (selected) | 19.04 | 25.04 |
| Average memory waste (selected) | 3.35 | 4.49 |

All policies at `min_runs = 1` (any-resource / CPU / memory violation %):

| Policy | Before | After |
|---|---|---|
| Request | 55.52 / 52.15 / 38.04 | 57.66 / 52.70 / 40.54 |
| Mean | 42.99 / 35.37 / 34.15 | 40.18 / 31.25 / 35.27 |
| P90 | 28.66 / 22.26 / 21.65 | 26.79 / 20.09 / 20.98 |
| P95 | 25.30 / 18.60 / 19.82 | 23.21 / 15.62 / 19.20 |
| **P99** | **21.95 / 16.77 / 17.07** | **18.30 / 12.95 / 15.62** |

- **The before and after rates are not a performance comparison.** Every `rec_*` recommendation is identical before and after (section 1). The rates differ only because 104 occurrences left the scored population.
  - Those 104 are the validation occurrences whose earlier target came from the test period.
  - On them, P99 at `min_runs = 1` had a 29.81% any-resource violation rate (finding F4), against 18.30% on the 225 that remain.
  - In counts: 72 violations out of 328 valid rows before, and 41 out of 224 after. The 31 violations that left were among the 104 removed rows.
- The top three configurations are unchanged: P99 at `min_runs` 1, 3 and 5. Six of the 20 configurations change rank. For example, P95 at `min_runs = 3` (22.97%) now ranks just above P95 at `min_runs = 1` (23.21%).
- The corrected `min_runs = 1` rows equal, to 1e-12, the earlier "targets within the validation period" sensitivity table (`../tables/validation_policy_comparison_target_period_sensitivity.csv`). That sensitivity table was the same population scored without the correction.
- With 225 occurrences, one occurrence moves a rate by about 0.45 percentage points. The gap between P99 at `min_runs` 1 and 3 is 0.17 points, which is smaller than one occurrence.

## 4. ML (Notebook 05)

Source: `ml_validation_before_after.csv` and `selection_before_after.json`.

| | Before | After |
|---|---|---|
| Selected models | Random Forest (CPU), Random Forest (memory) | Same |
| Locked hyperparameters | CPU `max_depth = 10`, memory `max_depth = 6`; `max_features = sqrt`, `min_samples_leaf = 10`, 300 trees, seed 42 | Same |
| Training rows (train-period labels) | CPU 1,672, memory 1,649 | Same |
| Training rows, "all available" sensitivity | CPU 2,010, memory 1,983 | CPU 1,672, memory 1,649 (equal to the primary rows) |
| Tuning, cross-validation and feature manifest | — | Byte-identical to before |
| Validation `log1p` RMSE, CPU RF (225 vs 329 rows) | 0.850 | 0.850 |
| Validation `log1p` RMSE, memory RF | 0.387 | 0.404 |
| Locked refit rows (train + validation, labels ≤ validation end) | CPU 2,108, memory 2,082 | CPU 1,898, memory 1,874 |
| Test ML predictions (731 rows) | — | Every row changes; median absolute change 0.025 (CPU) and 0.006 (memory) |
| P95 inputs to Hybrid on test | — | Unchanged (0 rows differ) |

- Training rows and tuning do not change because Notebook 05 already excluded training labels from later periods. The correction makes the artifact itself enforce that rule.
- The refit rows drop by 210 (CPU) and 208 (memory). Before the correction, the refit kept 210 training occurrences whose next occurrence lay in the validation period (the "Nulled target was in validation" count in section 2). Under split isolation those training targets are null, so the locked models are trained on fewer rows.
- On the 225 occurrences common to both runs, the validation ML predictions are identical, because the models trained on training rows are unchanged.

## 5. Checksums and reproduction

`SHA256SUMS` lists the corrected artifacts in `data/processed/google_subset_v1/`, which is not tracked by Git. Copies of the small corrected files are in this folder: `n04_metadata.json`, `n05_ml_metadata.json`, `baseline_validation_comparison.csv` and `ml_validation_model_comparison.csv`.

Environment: `requirements-lock.txt` installed into `~/venvs/traceadvisor-lock` (Python 3.12.15, pandas 2.3.3, numpy 2.5.4, scikit-learn 1.9.1, xgboost 3.4.1, pyarrow 23.0.1), kernel `traceadvisor-lock`.

Steps:

1. Before the correction, the unchanged Notebooks 04 and 05 were rerun in this environment. Notebook 04 reproduced the published inputs byte for byte (`val_occurrences.parquet` `44470ffb…`, `test_occurrences.parquet` `1a3c7a07…`, `metadata.json` `71961278…`). Notebook 05 reproduced the published locked models and predictions byte for byte. Two differences remained: `ml_metadata.json` records a different Python patch version (3.12.9 vs 3.12.15), and the memory XGBoost `log1p` metrics in `ml_validation_model_comparison.csv` differ by at most 5.7e-12. Neither difference affects any decision or prediction. That run was kept locally as `data/processed/google_subset_v1_before_task10/`.
2. The corrected Notebook 04 and Notebook 05 were then run in order. Notebook 05 was run twice and produced byte-identical outputs both times.
3. This folder was generated with:

```bash
~/venvs/traceadvisor-lock/bin/jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=traceadvisor-lock pipelines/google_subset/04_splitAndBaselines.ipynb
~/venvs/traceadvisor-lock/bin/jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=traceadvisor-lock pipelines/google_subset/05_evaluateRecommendations.ipynb
~/venvs/traceadvisor-lock/bin/python reports/results/google_subset/task10_correction/make_task10_comparison.py
```

The kernel name must be given. The notebooks' saved kernelspecs (`python3`, `masters-project`) point to other environments.

The comparison script reads the published "before" files in `reports/results/google_subset/` and the corrected files in `data/processed/google_subset_v1/`. It computes no test metric. It reads test target columns only to count how many exist.

After the corrected run, the earlier local Notebook 06 outputs (18 Oct, built on the 329-row population) were moved out of `data/processed/google_subset_v1/` into `data/processed/google_subset_v1_stale_n06_2026-10-18/`, so they cannot be mistaken for corrected results. Notebook 06 regenerates them in the second PR.

## 6. Superseded numbers

| Earlier Google number (in `../googlepipeline_finalrun.md`, `../google_subset_results_and_analysis.md` and `../tables/`) | Status |
|---|---|
| Validation baseline comparison on 329 occurrences (`../tables/baseline_validation_comparison.csv`) | **Superseded** by `baseline_validation_comparison.csv` here (225 occurrences) |
| ML validation comparison on 329 occurrences (`../tables/ml_validation_model_comparison.csv`) | **Superseded** by `ml_validation_model_comparison.csv` here |
| Validation policy comparison including ML and Hybrid (`../tables/validation_policy_comparison.csv`) and its sensitivity table | **Superseded**; regenerated by Notebook 06 (decision D-3, second PR) |
| Final-test ML and Hybrid rows (`../tables/final_test_policy_comparison.csv`) | **Superseded**: the locked models changed. A corrected final test needs the approved Notebook 06 rerun, reported as a new run |
| Final-test Request, Mean, P90, P95 and P99 rows | Their inputs are unchanged: identical test targets, identical baseline recommendations and the same selected `min_runs`. They are not rescored here |
| ML training, tuning and cross-validation tables (`../tables/ml_tuning_results.csv`, `../tables/ml_cv_summary.csv`) | Unchanged (byte-identical) |

The earlier files are kept unchanged as the record of the 29 Oct run. The cross-dataset report (Task 12) cites them with their checksums.

## 7. Not done in this change

- Notebook 06 (validation Hybrid comparison, new decision freeze and a second one-time final test) is decision D-3, the second PR. It was not run on the real artifacts, and nothing was scored on test.
  - Its run in a throwaway copy of the repository is described in section 8.
  - Its markdown cells 0, 14 and 20 and its manifest `status_reason` still say targets are built before splitting. The second PR must update them.
- The Google capability profile (`target_split_isolation = False` in `src/canonical/schema.py` and `config/dataset_capabilities.json`) is decision D-2, a separate one-line issue.
- Findings F7 (abnormal records) and F8 (repeated multi-machine rows) are decision D-4 and were not changed. F2, F11 and F12 were not changed either.
- The project report chapters and the planning documents still quote the earlier Google numbers.

## 8. Additional checks

- **Independent rebuild of the targets.** The split-isolated targets were rebuilt from the Notebook 03 occurrence table (`job_profiles_google_subset_history_v1.parquet`) with separate code: assign splits by the recorded boundaries, then `shift(-1)` within `recurrence_key`, keeping only next occurrences in the same split. All 4,879 occurrences match the saved target time, CPU and memory values and `target_null_reason` exactly.
- **Notebook 06 compatibility.** Notebook 06 was run unchanged in its default mode (`RUN_FINAL_TEST = False`, `FREEZE_STATUS = "preliminary"`), on a throwaway copy of the repository and the corrected artifacts.
  - It loaded the corrected files and found 225 validation occurrences.
  - It reproduced the Notebook 04 baseline metrics exactly.
  - It wrote no final-test file.
  - The repository's own `data/processed/` was not written.
- **The leakage audit checks every row (PR #132 review).** `make_task10_comparison.py` derives each row's expected null reason from the true next occurrence and never trusts the stored `target_null_reason`. It also checks that:
  - a target exists exactly when the next occurrence is in the same split;
  - every kept target time, CPU and memory value equals the true next occurrence;
  - the removals to validation plus those to test add up to the total removed.

  Any disagreement stops the script. `tests/test_google_task10_split_isolation.py` checks that it rejects swapped reasons, a restored cross-split target, a dropped same-split target, a changed target value and an unknown reason.
- **Tests without local data.** `tests/test_google_task10_split_isolation.py` runs the Notebook 04 target-construction cells on a small made-up table. The table covers all three splits, missing CPU and memory targets, and both null reasons, and the test checks that non-target columns are unchanged.
- **Older local artifacts.** On local Google files made before Task 10, the split-isolation tests in `tests/test_google_canonical_contract.py` skip with the reason ("local Google artifacts predate Task 10; rerun Notebooks 04 and 05") instead of failing.
