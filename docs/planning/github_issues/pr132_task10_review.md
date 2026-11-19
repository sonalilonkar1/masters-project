# Review of PR #132: Task 10 PR 1, Split-Isolated Google Targets

**PR:** #132 (`task10-google-split-isolation`, commit `3c964ba`), author shivani-jariwala
**Issue:** #115 (Task 10, `task10_google_subset_corrections_and_rerun.md`)
**Reviewed:** 2026-11-18, in the locked environment (`requirements-lock.txt`, Python 3.12) with the earlier Google processed data available locally

## How It Was Checked

- Merged the PR with the current `main` (`e636b10`, which includes #129 and #131). The merge is clean, and `--validate-bundle` on `reports/results/cross_dataset_final/` still passes. The PR changes no file that Task 12 pins.
- Read the corrected target construction in Notebook 04 (cells 16, 25 and 26). Targets are built inside each split and checked against a next-occurrence reference built over the full table. Each null target has a recorded reason, and the notebook raises an error on any inconsistency.
- Reran the corrected Notebooks 04 and 05 on a copy of the earlier artifacts with the commands in `task10_correction/README.md`. 15 of the 17 files in `task10_correction/SHA256SUMS` match byte for byte, including both locked models and `test_ml_predictions.parquet`. The other two are the differences the README describes: `ml_metadata.json` records a different Python patch version, and the XGBoost memory row of `ml_validation_model_comparison.csv` differs by about 5e-12.
- Reran `make_task10_comparison.py`. The committed tables are reproduced, apart from the same 5e-12 difference.
- Ran the tests on the merged tree with the regenerated artifacts: the 14 tests in `tests/test_google_canonical_contract.py` pass, and the full suite gives 1151 passed, 1 skipped.
- Checked the scope. No `src/`, `config/`, schema, evaluator, target-builder, adapter or Alibaba/Azure file changes, and nothing is scored on test.

The tests confirm the reported numbers on the regenerated data:

- Cross-split targets removed: 338 train, 104 validation, 0 test.
- Common validation population: 329 → 225 occurrences.
- Selection is unchanged at P99 with `min_runs = 1`, and the any-resource violation rate falls from 21.95% to 18.30%.

The issues below are what remains.

## Required Changes

### 1. The new tests fail, instead of skipping, on artifacts from before Task 10

The new tests in `tests/test_google_canonical_contract.py` skip only when an artifact file is missing (`load_google_occurrence_split`, `_load_google_metadata`). Every local copy of `data/processed/google_subset_v1/` made before this PR still holds the earlier artifacts. On those, 8 tests fail:

```text
FAILED test_google_target_nulls_match_global_final_occurrences
FAILED test_google_metadata_records_target_split_isolation
FAILED test_google_targets_never_come_from_another_split[train|validation|test]
FAILED test_google_targets_point_to_a_later_occurrence_of_the_same_recurrence
FAILED test_google_missing_memory_stays_nan[train|validation]
8 failed, 6 passed
```

The failures are bare assertion errors and two `KeyError`s on `target_null_reason`. None of them says the artifacts are out of date. Regenerating the artifacts is not a full fix:

- The Task 15 export checks the Google inputs against the committed `reports/results/google_subset/decision_manifest.json`.
- After regeneration, a verified UI export is refused until decision D-3 commits a new manifest, as described in `task10_downstream_updates.md`.
- So after merge, a developer either has 8 failing tests or cannot produce a verified UI bundle.

**Fix:** in the test helpers, skip with a clear reason when the local `metadata.json` does not record `target_policy_version = "next_distinct_full_workload_occurrence_v4_split_isolated"`. For example: "local Google artifacts predate Task 10; rerun Notebooks 04 and 05". Also state in the PR description that running Notebooks 04 and 05 is required to run these tests.

### 2. Decision D-1 is applied but not recorded as approved

The PR nulls training targets whose next occurrence is in a later split "per decision D-1". On `main`:

- `current_status.md` lists D-1 (target isolation) as **Remaining**.
- The Task 10 issue lists D-1 as unresolved, and "Decide and record how training targets in later splits are handled (Decision D-1)" is unchecked.
- The issue's Dependencies section requires team approval of the target-isolation rule.

The PR follows the issue's recommended option, but it changes the training and refit data, and the locked models are refit on 210 fewer rows.

**Fix:** record the team's D-1 approval and its date before merge. Put it in the Task 10 issue doc's Unresolved Decisions table and in `current_status.md`, and reference it from the PR.

## Recommended Changes

### 3. The Task 10 issue doc is not updated

All the checklist items in `task10_google_subset_corrections_and_rerun.md` are still `[ ]`. This includes the work this PR completes: target and split correction, leakage-safe selection, resource-field checks, split integrity, artifacts and metadata, the comparison and leakage audit, and test reconciliation.

**Fix:** tick the completed items, and keep sections 6 ("Mark earlier Google numbers as superseded", done in part) and 8 (Notebook 06, decision D-3) open.
