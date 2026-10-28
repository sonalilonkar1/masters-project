# [P1] Task 8: Alibaba GPU 2020 Final Verification and Artifact Validation

**Labels:** `area-implementation`, `priority-high`

**Owner:** Unassigned

**Priority:** Priority 1 · Required · End of the Alibaba GPU 2020 critical path

---

## Objective

Verify the complete Alibaba GPU 2020 pipeline after the Task 7 final test. Every artifact, its metadata and the final result are re-validated, traced to the locked decision manifest, and reproduced from documented inputs.

This is a verification and reporting task only. It introduces no new model, baseline, adapter, target, evaluator or schema behavior, and it does not fix earlier tasks. A failed verification is reported and returned to the owning task.

## What This Task Builds

- An artifact manifest with paths, checksums, row counts, code commit, source checksums and generating commands for every required Alibaba GPU 2020 artifact.
- A verification script that re-validates artifacts and metadata and checks the final result's traceability.
- A verification report with counts and exclusions.
- A fresh-environment reproduction of the required path.
- README and runbook steps for the Alibaba GPU 2020 path.

## What This Task Does Not Build

- Any new model, baseline, adapter, target, evaluator or schema behavior.
- Fixes to earlier tasks. A verification failure is reported and returned to the owning task.
- The cross-dataset report (Task 12).

## Current Project State

- `scripts/verify_data_setup.py` is a Google smoke test that loads `data/raw/clusterdata2019_kaggle_subset.csv` and prints its shape; it does not verify Alibaba GPU 2020 artifacts.
- No artifact manifest or checksum tooling exists.
- The full test suite passes with no failures. The earlier Google target-null failure was fixed in commit `89d03e8` (the test is now `test_google_target_nulls_match_global_final_occurrences`).
- Processed data under `data/processed/` is gitignored, so verification runs locally and its report is committed.
- `requirements.txt` does not list every test tool (for example `pytest`), so a fresh environment needs the repository's test dependencies in addition to `requirements.txt`.

## Test-Data Access Being Verified

Task 8 verifies four distinct stages of test-data access:

| Stage | Owner | What is allowed |
|---|---|---|
| Baseline recommendation generation | Task 6 | Reads test feature and request columns only. Does not read test targets, target statuses, actual resource values or test evaluation results, and never calls the evaluator on test rows |
| First read of test targets | Task 7 Phase 4 | Reads test target and target-status columns for the first time, after the decision manifest is locked |
| Final-test scoring | Task 7 Phase 4 | Calls the evaluator on test rows exactly once for all seven policies (Request, Mean, P90, P95, P99, the selected machine-learning model, and Hybrid) |
| Verification | Task 8 | Reads the final-test outputs and metadata; never reruns or retunes the final test |

## Artifact Classes Being Verified

| Class | How it is verified |
|---|---|
| Raw source files | Source checksums, file identity, row counts, source version and Task 2 loader metadata. Raw files are not expected to contain canonical schema fields |
| Canonical `role_occurrence` artifacts | Re-validation against the Alibaba GPU 2020 profile, canonical metadata, counts |
| Canonical `instance` artifacts | Re-validation, canonical metadata, parent linkage |
| Rejected output | Rejection reasons and counts, canonical metadata |
| Split and target tables (Task 4) | Split boundaries, history counts, target statuses, isolation, canonical metadata |
| Baseline recommendation tables (Task 6) | Selection record, recommendation counts, canonical metadata |
| Machine-learning and Hybrid prediction tables (Task 7) | Manifest traceability, model reload, canonical metadata |
| Evaluation outputs (Tasks 6 and 7) | Denominators, labels, suppression of any-resource and GPU evaluation metrics |
| Metadata and manifests | Checksums, ordering of lock and run timestamps, profile values |

## Relationship to PR #70 and Tasks 1–7

| Item | Relationship |
|---|---|
| PR #70 follow-up | Its profile and validation functions are used to re-validate artifacts. Not modified |
| Task 1 | Its per-view validation and rejected-output checks are rerun |
| Task 2 | Its source checksums, loader metadata and `source_row_number` are verified |
| Task 3 | Canonical views, rejected output and count report are verified |
| Task 4 | Splits, history counts, targets and statuses are verified |
| Task 5 | Evaluator outputs are checked for denominators, labels and suppression |
| Task 6 | Selection record, baseline recommendations, history statistics and validation tables are verified |
| Task 7 | Decision manifest, model artifacts, predictions, final-test outputs and run record are verified |

## Scope

- Dataset: Alibaba GPU 2020.
- Google, Alibaba 2018 and Azure tests are run as regressions only.

## Dependencies

- **Task 7** complete, including Phase 4 final-test execution.
- Transitively Tasks 2 → 3 → 4 → 6 → 7.

## Parallel Work

- Manifest and verification tooling can be developed early against fixtures and intermediate artifacts, alongside Tasks 4, 6 and 7.
- Final verification starts only after the Task 7 final test completes and does not run in parallel with it.

## Blocks

- **Task 12:** final reporting uses only verified Alibaba GPU 2020 results.
- **Task 9:** may start after the verified Alibaba GPU 2020 result if the project schedule permits.

## Detailed Implementation Tasks

### 1. Artifact Manifest

- [ ] List every required artifact with path, checksum, row count, code commit and generating command.
- [ ] Include Task 2 source checksums.
- [ ] Manifest format to confirm (Decision D-1).

### 2. Raw Source Files (Task 2)

- [ ] Verify each raw source file by checksum, file identity, row count and source version.
- [ ] Verify the Task 2 loader metadata and that `source_row_number` is preserved unchanged in canonical output.
- [ ] Do not require canonical schema fields in raw source files.

### 3. Canonical Artifacts (Task 3)

- [ ] Re-validate the `role_occurrence` and `instance` views against the Alibaba GPU 2020 profile.
- [ ] Verify the rejected output (jobs, role rows and instance rows) and its rejection reasons.
- [ ] Verify the adapter metadata and count report:
  - counts per exclusion reason in rule order;
  - the eligible population (reference: 462,156 before `multi_attempt_worker`, 256 removed, 461,900 eligible);
  - missing-CPU eligible rows (reference: 1,224);
  - rejected counts (reference: 3,663 jobs, 6,942 role rows, 111,219 instance rows).
- [ ] Explain any difference from the reference counts in the report.
- [ ] Verify instance-to-parent linkage and the timestamp contract.
- [ ] GPU source fields defined by the schema may be present in canonical artifacts and metadata for provenance and future use; their presence is not a failure.

### 4. Splits, History and Targets (Task 4)

- [ ] Split boundaries and row counts match the Task 4 metadata.
- [ ] No job spans two splits; excluded rows have a null `split`.
- [ ] History counts recomputed independently match the stored counts.
- [ ] Target statuses use only the frozen vocabulary; `available` rows have non-null targets and all others null.
- [ ] Split isolation: no target comes from another split.
- [ ] Leakage check: no history value comes from a later occurrence or later split.
- [ ] Same-second flag counts are reported (reference: 245 validation, 251 test).

### 5. Baselines (Task 6)

- [ ] Baseline history-statistic counts match the Task 4 history counts.
- [ ] The locked selection record predates the baseline test recommendations.
- [ ] The selected policy and `min_runs` match the validation comparison under the documented sort order, among the selection candidates (Mean, P90, P95, P99; Request excluded).
- [ ] Recommendation tables exist for all five baseline policies at the selected `min_runs` for train, validation and test, with the selected policy marked.
- [ ] Task 6 metadata confirms it read test feature and request columns only, and that no evaluator call was made on test rows.

### 6. Models, Hybrid and Final Test (Task 7)

- [ ] The candidate-experiment table covers every candidate configuration per resource, including `DummyRegressor`, and the selected models match the documented validation selection order.
- [ ] Hybrid validation predictions come from models fitted on train only.
- [ ] Locked model artifacts reload and reproduce their saved predictions, using the saved training column order.
- [ ] The negative-prediction rule and its counts are recorded.
- [ ] The decision manifest's checksum matches, and its lock timestamp predates the final-test run.
- [ ] Final-test predictions and tables trace to the manifest (models, Hybrid rule, selected baseline, `min_runs`).
- [ ] Test target and evaluation columns were read once during Task 7 Phase 4, after the decision manifest was locked. Task 6 may read test feature and request columns but does not read test targets or score test rows.
- [ ] The final-test run record shows one evaluator call on test rows for all seven policies (Request, Mean, P90, P95, P99, the selected machine-learning model, and Hybrid), and lists any documented rerun with its own run ID and retained original outputs.

### 7. Evaluation Contract

- [ ] Every evaluation table has separate CPU and memory denominators.
- [ ] Every CPU result carries the average-usage label.
- [ ] Memory is reported as the primary resource.
- [ ] No any-resource metric or GPU evaluation metric appears in the baseline, machine-learning, Hybrid, or final-test evaluation outputs. Canonical artifacts may retain GPU source fields for provenance and future use.

### 8. Schema and Capability Metadata

- [ ] Every canonical and derived artifact, including its metadata, records `schema_version = 0.2.0` and `dataset_id = alibaba_gpu_v2020`. Raw source files are verified through their source checksums and loader metadata.
- [ ] Profile values in metadata match the registry.

### 9. Test Suite and Reproduction

- [ ] Run the full `pytest` suite. No failures are allowed.
- [ ] Reproduce the required artifacts in a fresh environment using the dependencies in `requirements.txt`, the test dependencies required by the repository, and the documented Alibaba GPU 2020 data setup, within the tolerance set in Decision D-2.
- [ ] If Task 7 includes XGBoost: install the recorded XGBoost version, confirm that the model artifact reloads successfully, confirm that predictions are reproducible, and record the XGBoost version in the reproduction metadata.
- [ ] Recompute manifest checksums and compare.

### 10. Report and Documentation

- [ ] Verification report: counts per stage, exclusions per reason, rejections per reason, split and status counts, final-test population and denominators, the test-data access stages, and every explained difference from reference counts.
- [ ] README and runbook steps for the Alibaba GPU 2020 path.

## Required Tests

- [ ] The verification script fails on a deliberately corrupted fixture artifact (checksum, count, label and suppression checks).
- [ ] The verification script passes on a consistent fixture set.
- [ ] The verification script fails when an evaluation output contains an any-resource or GPU evaluation metric.
- [ ] The verification script does not fail when a canonical artifact contains schema-defined GPU source fields.
- [ ] The verification script fails when a canonical or derived artifact lacks `schema_version` or `dataset_id`, and does not require these fields in raw source files.
- [ ] The verification script fails when the manifest lock timestamp is later than the final-test run, or when the run record shows more than one evaluator call on test rows without a documented rerun.
- [ ] The full test suite result is recorded in the report.

## Acceptance Criteria

1. Final verification ran after Task 7 final-test execution completed.
2. All manifest checksums match the regenerated artifacts, and raw source files match their source checksums and loader metadata.
3. Every canonical and derived artifact passes validation, and its metadata counts match or differences are explained.
4. The final-test result traces to the locked manifest. Test target and evaluation columns were read once during Task 7 Phase 4, after the decision manifest was locked. Task 6 may read test feature and request columns but does not read test targets or score test rows.
5. Separate denominators, CPU average-usage labeling and memory-primary reporting are confirmed in every evaluation table. No any-resource metric or GPU evaluation metric appears in the baseline, machine-learning, Hybrid, or final-test evaluation outputs. Canonical artifacts may retain GPU source fields for provenance and future use.
6. Every canonical and derived artifact, including its metadata, records `schema_version = 0.2.0` and `dataset_id = alibaba_gpu_v2020`.
7. The full suite passes with no failures.
8. The fresh-environment reproduction, using `requirements.txt`, the repository's test dependencies and the documented data setup, succeeds within tolerance, including the XGBoost checks if XGBoost was used.

## Expected Outputs

- Artifact manifest covering raw source files, canonical and derived artifacts, metadata and manifests.
- Verification script (location to confirm, under `scripts/`).
- Verification report, including confirmation that evaluation outputs contain no any-resource or GPU evaluation metric.
- Reproduction metadata (environment, library versions, and the XGBoost version if used).
- README and runbook updates for the Alibaba GPU 2020 path.

## Data Leakage Controls

- Independently rechecks split isolation, history timing and the order of the manifest lock and the final-test run.
- Confirms that Task 6 read test feature and request columns only, and that test target and evaluation columns were read once during Task 7 Phase 4, after the decision manifest was locked.
- Reads final-test outputs only; never reruns or retunes the final test.

## Schema and Adapter Boundaries

- Uses existing validation functions; changes no schema, profile, adapter, evaluator or pipeline code.
- Accepts schema-defined GPU source fields in canonical artifacts.

## Unresolved Decisions

| ID | Decision | Recommendation |
|---|---|---|
| D-1 | Manifest format | One JSON file listing artifacts with SHA-256 checksums, row counts, commit and command |
| D-2 | Reproduction tolerance | Exact match for counts and identifiers; floating-point tolerance `1e-9` relative for metrics; model predictions within the tolerance of the library versions recorded in the manifest |

## Risks

- Full Alibaba GPU 2020 runs need substantial memory and disk; reproduction may be slow.
- Verification falls after the final test, so tooling must be ready beforehand.
- A verification failure sends work back to an earlier task late in the schedule.
- If XGBoost is used, a fresh environment may need extra setup to install the recorded version.

## Pull-Request Boundary

One PR: manifest, verification script, its tests, the verification report and documentation. No pipeline behavior changes.

## Handoff

- **Task 12:** the verified manifest and the verified final Alibaba GPU 2020 result, including the verified test-data access record (Task 6 feature and request reads; Task 7 Phase 4 target reads and single evaluator call).
- **Task 9:** may start after the verified Alibaba GPU 2020 result if the project schedule permits.

## Not in This Issue

- New model, baseline, adapter, target, evaluator or schema behavior.
- Fixes to earlier tasks (returned to their owners).
- The cross-dataset report (Task 12).
- Alibaba 2018 (Task 9), Google (Task 10) or Azure (Task 11) work.

## References

- `scripts/verify_data_setup.py`, `requirements.txt`, `pytest.ini`, `README.md`
- `docs/planning/github_issues/task6_baselines_and_min_runs.md`
- `docs/planning/github_issues/task7_machine_learning_hybrid_and_final_test.md`
- `docs/planning/github_issues/pr70_followup_issue.md`
- `docs/design/canonical_workload_schema.md` §9, §11, §12
- `docs/data/alibaba_gpu_2020_evidence_and_limitations.md` §5
- `docs/planning/data_integration_tasks.md` Task 11, verification part (earlier numbering)
- Note: the Task 5 evaluator issue file is not currently in `docs/planning/`; reference it from wherever it now lives.
