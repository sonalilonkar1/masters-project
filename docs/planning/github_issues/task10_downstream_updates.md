# Updates After Task 10 (#115): Google Results Downstream

**Status:** Waiting on Task 10. Recorded 2026-11-18.
**Trigger:** Task 10 PR 1 (split-isolated targets, branch `task10-google-split-isolation`, `3c964ba`) merges, and decision D-3 (Notebook 06, the Google final test) is recorded.
**Related:** `task10_google_subset_corrections_and_rerun.md`, Task 12 (#117), Task 15 (#120, PR #131), Task 16.

## Why This Is Needed

Task 10 PR 1 fixes the leakage in training and validation: 338 training and 104 validation targets that crossed into a later split are removed, the models are refit, and validation selection stays P99 with `min_runs = 1` (any-resource violation 21.95% → 18.30%). It does not rerun the Google final test. Until Notebook 06 runs, every Google final-test number in the project still comes from the earlier, contaminated pipeline:

- the Task 12 bundle (`reports/results/cross_dataset_final/`, Google `decision_pending`);
- the Task 15 UI bundle (`reports/results/ui/`), which states the F3/F4 limitation in its Google caveats;
- the report's Google numbers.

PR 1 also regenerates `data/processed/google_subset_v1/`, including the test ML predictions from the refit models. The Task 15 export checks these files against the checksums in the committed Google decision manifest (`reports/results/google_subset/decision_manifest.json`), so after PR 1 merges and the local files are regenerated, a verified UI export is refused until a new decision manifest is committed. The committed UI bundle itself stays valid.

## Path A: D-3 Approved (Notebook 06 Reruns the Google Final Test)

### Task 10 PR 2

- [ ] Notebook 06 scores the locked policies on test once and commits the new `final_test_policy_comparison.csv`, `final_test_run_metadata.json`, `decision_manifest.json` and row-level checksums under `reports/results/google_subset/`.
- [ ] The earlier final-test results stay in the repository, marked superseded, with the before/after comparison.

### Task 12 (Final Cross-Dataset Report)

- [ ] `config/reporting_decisions/google_clusterdata2019.json` (and its `.evidence.json`): change `decision_pending` to the recorded outcome, with the D-3 decision and the Task 10 comparison as evidence.
- [ ] `config/cross_dataset_report_final.json` (Google): point `results`, `metadata`, `run_record` and `decision_manifest` at the new files and update their pinned checksums; reword `reason`.
- [ ] Google limitations: remove the F3/F4 line once the final test is leakage-safe, in both the config and `DATASET_LIMITATIONS` in `src/reporting/artifact_provenance.py` (the validator requires them to match). Keep F7/F8, subset scale and the small validation population.
- [ ] Mark item 6 of Task 12 ("Google results final, or kept with documented limitations") and the Task 10 before/after comparison as done.
- [ ] Regenerate `cross_dataset_final/` into an empty folder in the locked environment, replace the committed bundle, and run `--validate-bundle`.

### Task 15 (UI Bundle and API)

- [ ] Get the regenerated `data/processed/google_subset_v1/` files from Task 10 (Drive, with checksums), matching the new decision manifest.
- [ ] Remove the F3/F4 caveat from `DATASET_CAVEATS[GOOGLE]` in `src/service/export.py`; keep the F7/F8, subset-scale and validation-population caveats.
- [ ] Rebuild the fixture (`python tests/fixtures/make_ui_bundle.py`) and commit the code.
- [ ] Re-export the verified bundle from a clean checkout: `python scripts/export_ui_artifacts.py --force`. Rules, `min_runs` and policy metrics are read from the committed records. The Google Hybrid safeguard is fixed at P95 in `src/service/export.py` (`GOOGLE_HYBRID_SAFEGUARD` and the `"P95"` passed in `build_bundle`); change both only if the new decision manifest changes it. Check that the export reports `verified` with 0 source mismatches, and that every Google `exceeded` flag still passes the actual > recommended and summary checks.
- [ ] Update the bundle checksum in `recommendation_service_design_plan.md`, the Task 15 doc and the Task 16 doc.
- [ ] Full test suite in the locked environment.

### Task 16 (Web UI)

- [ ] Retake the screenshots and report Figures 8.1 and 8.2 from the new bundle.

### Report

- [ ] Update every Google final-test number in the report to the new final test, and describe the correction and the before/after comparison.

## Path B: D-3 Declined (Earlier Final Test Kept)

- [ ] Task 12: record the decision to keep the earlier Google results in `config/reporting_decisions/google_clusterdata2019.json`, with the Task 10 comparison as evidence; keep the F3/F4 limitation; regenerate and validate `cross_dataset_final/`.
- [ ] Task 15: no bundle change. The F3/F4 caveat stays. Keep the earlier `data/processed/google_subset_v1/` files (back them up before regenerating), because a verified export needs the inputs that match the committed decision manifest.
- [ ] Report: state that the Google final-test results predate the correction, and give the corrected validation results from Task 10.

## Either Path

- [ ] D-2: set the Google profile `target_split_isolation` to `true` through its separate issue.
- [ ] `current_status.md`: update the Task 10, Task 12 and Task 15 rows.
