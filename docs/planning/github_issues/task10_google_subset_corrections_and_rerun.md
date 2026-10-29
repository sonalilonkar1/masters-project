# [P3] Task 10: Google Subset Corrections and Rerun

**Labels:** `area-implementation`, `priority-low`

**Owner:** Unassigned

**Priority:** Priority 3 · Google-only · Lower than the complete Alibaba GPU 2020 pipeline (Tasks 1–8) and the optional Alibaba 2018 demonstration (Task 9). Needed for final, leakage-safe Google results.

---

## Objective

Correct the Google subset pipeline's next-occurrence target and split-boundary behavior so that test-period outcomes cannot influence validation, rerun the Google baselines and validation-only selection on corrected artifacts, and compare the results with the earlier Google results.

This task changes Google-specific notebooks and artifacts only. It does not redesign the canonical schema, the adapter framework or any Alibaba or Azure pipeline.

## What This Task Builds

- A corrected `pipelines/google_subset/04_splitAndBaselines.ipynb` that builds targets after split assignment.
- Regenerated Google split, target and baseline artifacts and metadata.
- A before/after comparison and a leakage audit with changed-row counts.
- Tests that protect the corrected behavior.

## What This Task Does Not Build

- Any change to Alibaba GPU 2020, Alibaba 2018, Azure, the adapter framework, the shared target builder or the shared evaluator.
- A change to the shared schema contract, unless a separate approved issue is created.
- Filtering of failed or killed records (F7) or removal of repeated multi-machine rows (F8), unless separately approved.

## Current Project State

Findings from `docs/data/google_subset_pipeline_analysis.md`:

- **F1:** targets are built on the full occurrence table before split assignment (N04 cells 12–13, 16, 22).
- **F2:** `shift(-1)` is grouped by `recurrence_key` and ordered by `execution_start_time_us`; 9 next occurrences start before the current one ends.
- **F3:** 104 of 330 validation targets start in the test period; 338 training targets start after `TRAIN_END_TIME`.
- **F4:** with validation-period targets only, P99 with `min_runs = 1` stays selected; its any-resource violation moves from 21.95% to 18.30%.
- **F5:** N04 markdown cell 0 says targets never cross splits; cell 24 and the metadata say they may.
- **F6 (resolved in part):** `05_evaluateRecommendations.ipynb` was 0 bytes when the analysis was written. Commit `0a3cf8e` added it as the Google ML notebook: feature contract and leakage audit, label-purged tuning, validation model selection, lock and refit on train plus validation, and test predictions without scoring. Its handoff names a Notebook 06 for policy scoring (violations, waste, Hybrid), which is not yet in the repository.
- **F7, F8, F11, F12:** abnormal events included; identical values summed across machines; runtime units inconsistent; next-occurrence size unused. Recorded, not fixed here unless approved.
- Notebook 04 already uses the full-workload occurrence fields (`occurrence_peak_cpu_ncu`, `occurrence_peak_memory_normalized`) and next-occurrence target columns as evaluator actuals (cells 32–33), and keeps missing memory as NaN (cell 10).
- The Google profile records `target_split_isolation = false`.
- The earlier target-null test failure (1,463 vs 1,801) was fixed in commit `89d03e8`. The test is now `test_google_target_nulls_match_global_final_occurrences`, which checks the current behavior: next-occurrence targets are null only for each recurrence's globally final occurrence.

## Relationship to PR #70 and Tasks 1–5

| Item | Relationship |
|---|---|
| PR #70 follow-up | Google profile value `target_split_isolation` would change only through a separate approved issue (Decision D-2) |
| Tasks 1–3 | Not used |
| Task 4 | Not used; Google targets stay in the Google notebook (no shared target-builder change) |
| Task 5 | Its no-profile evaluator path is used unchanged by Notebook 04 |

## Scope

- Dataset: Google Cluster Data 2019 Kaggle subset only.
- Files: Google notebooks, Google artifacts under `data/processed/google_subset_v1/`, Google tests.

## Dependencies

- Team approval of the target-isolation rule (Decision D-1).
- Technically independent of Tasks 1–9, but scheduled after Task 8, so it does not take capacity from the Alibaba GPU 2020 path.
- Task 5 merged (the evaluator Notebook 04 calls).

## Parallel Work

- Can run in parallel with Task 9, Task 11 and Task 12 script development.
- Never blocks an Alibaba GPU 2020 task.

## Blocks

- **Task 12:** Google final results come from this task, or from a documented decision to keep the earlier results.

## Detailed Implementation Tasks

### 1. Target and Split Correction

- [ ] Assign splits first using the existing frozen chronological 70/15/15 boundaries (`chronological_split`, unchanged).
- [ ] Build next-occurrence targets after split assignment. A validation or test target whose next occurrence is in another split becomes unavailable (null), with its reason recorded in metadata.
- [ ] Decide and record how training targets in later splits are handled (Decision D-1).
- [ ] Fix the contradictory markdown (F5) so the notebook text matches the code.

### 2. Leakage-Safe Selection

- [ ] Freeze the common validation population after the correction.
- [ ] Rerun Request, Mean, P90, P95 and P99 for `min_runs` in `[1, 3, 5, 10]` with the existing evaluator.
- [ ] Select the baseline and `min_runs` on validation only, with the existing Notebook 04 sort order.

### 3. Resource Fields and Missing Values

- [ ] Confirm the evaluator actuals are the next-occurrence target columns, not current-occurrence peaks.
- [ ] Confirm the full-workload occurrence resource fields are used (`occurrence_peak_cpu_ncu`, `occurrence_peak_memory_normalized`, `occurrence_requested_cpu_ncu`, `occurrence_requested_memory_normalized`).
- [ ] Keep missing memory as NaN; never fill it.

### 4. Chronological Split Integrity

- [ ] No occurrence crosses a split boundary.
- [ ] Split boundaries and row counts are unchanged by the correction.

### 5. Artifacts and Metadata

- [ ] Regenerate the Google artifacts in `data/processed/google_subset_v1/` and `metadata.json`, after backing up the earlier versions for the comparison.
- [ ] Record `target_split_isolation` in the Google metadata.
- [ ] Verify the saved artifacts reload with the expected row counts and columns (N04 cell 51 checks).

### 6. Comparison and Leakage Audit

- [ ] Before/after table: selected policy and `min_runs`, validation population size, and CPU, memory and any-resource violation.
- [ ] Changed-row counts: targets nulled per split, rows leaving the validation population.
- [ ] Mark earlier Google numbers as superseded.

### 7. Test Reconciliation

- [ ] Update `test_google_target_nulls_match_global_final_occurrences` to match the corrected targets: after the correction, validation and test targets whose next occurrence lies in another split are also null.
- [ ] Rerun Notebook 05 on the regenerated Notebook 04 artifacts, because its locked models and test predictions are built from them.

### 8. Google Final Evaluation (Decision D-3)

- [ ] If approved, add the Notebook 06 policy-scoring step named in the Notebook 05 handoff, which scores the locked Google policies on test once.

## Required Tests

- [ ] No validation or test target comes from another split.
- [ ] Every target points to a strictly later occurrence in the same `recurrence_key`.
- [ ] Missing memory stays NaN in targets and recommendations.
- [ ] `chronological_split` output for Google is unchanged.
- [ ] The full suite passes with no failures, including the updated `test_google_target_nulls_match_global_final_occurrences`.
- [ ] Regression: all tests unrelated to the corrected behavior pass unchanged.

## Acceptance Criteria

1. No Google validation or test target crosses a split (if isolation is approved).
2. Selection uses validation outcomes only.
3. The before/after comparison and changed-row counts are recorded.
4. Earlier Google numbers are marked superseded.
5. The full suite passes with no failures.
6. No Alibaba, Azure, adapter-framework, target-builder, evaluator or schema code changes.

## Expected Outputs

- Corrected Notebook 04, Notebook 05 rerun on the corrected artifacts, and Notebook 06 if approved.
- Regenerated Google artifacts and metadata.
- Before/after comparison and leakage audit.

## Data Leakage Controls

- Targets built after split assignment and limited to the same split.
- Validation selection uses no test-period outcome.
- Test is scored at most once, only in the approved Notebook 06. Notebook 05 produces test predictions without scoring them.

## Schema and Adapter Boundaries

- No change to `src/canonical/schema.py`, `config/dataset_capabilities.json`, the adapter framework or shared modules in this task.
- A Google profile value change goes through a separate approved issue.

## Unresolved Decisions

| ID | Decision | Recommendation |
|---|---|---|
| D-1 | Target-isolation rule for Google | Adopt split isolation for validation and test targets; for train, null targets in later splits so models trained later never learn from them |
| D-2 | Google profile `target_split_isolation` value | Raise a one-line separate issue to set it to `true` once the correction merges, so the profile matches the artifacts |
| D-3 | Google final evaluation (Notebook 06) | Include it as a second PR, because Task 12 needs leakage-safe Google final-test results |
| D-4 | F7 and F8 | Raise as separate decisions; not part of this task |

## Risks

- Corrected numbers differ from earlier reported Google results.
- The validation population shrinks (329 to about 225 rows), making differences between configurations smaller than noise.
- Regenerating artifacts overwrites the earlier versions; back them up first.

## Pull-Request Boundary

Up to two Google-only PRs: (1) target and split correction with regenerated artifacts and the comparison; (2) Notebook 06 final evaluation, if approved. Never combined with Alibaba or Azure work.

## Handoff

- **Task 12:** corrected Google results and the before/after comparison, or a documented decision to keep the earlier results with their contamination disclosed.

## Not in This Issue

- Alibaba GPU 2020 (Tasks 1–8), Alibaba 2018 (Task 9) or Azure (Task 11).
- Shared schema contract changes without a separate approved issue.
- Adapter framework, shared target builder or shared evaluator changes.
- F7, F8, F11 and F12 fixes unless separately approved.

## References

- `pipelines/google_subset/04_splitAndBaselines.ipynb`, `pipelines/google_subset/05_evaluateRecommendations.ipynb`
- `data/processed/google_subset_v1/` (gitignored)
- `src/features/split_utils.py`, `src/evaluation/evaluator.py`
- `tests/test_google_canonical_contract.py`
- `docs/data/google_subset_pipeline_analysis.md` §4–§5
- `docs/design/canonical_workload_schema.md` §11
- `docs/planning/data_integration_tasks.md` Task 9 (earlier numbering)
