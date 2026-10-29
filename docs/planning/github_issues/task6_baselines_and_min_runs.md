# [P1] Task 6: Alibaba GPU 2020 Baselines and `min_runs` Selection

**Labels:** `area-implementation`, `priority-high`

**Owner:** Unassigned

**Priority:** Priority 1 — Required critical-path task for the Alibaba GPU 2020 pipeline

## Objective

Build the Alibaba GPU 2020 baseline pipeline. It computes Request, Mean, P90, P95, and P99 recommendations from point-in-time history, evaluates every policy and `min_runs` candidate on validation using the Task 5 evaluator, and selects one baseline policy and one `min_runs` value using validation only and memory-first ranking.

After the selection is locked, the task produces recommendations for all five baseline policies at the selected `min_runs` for train, validation, and test. It does not read test targets, test statuses, test actual values, or test evaluation outcomes, and it does not score test rows.

Task 7 performs the single final-test evaluation for all five baseline policies, the selected machine-learning model, and the Hybrid policy.

## Dataset Scope

- **In scope:** Alibaba GPU 2020.
- **Google:** No Google pipeline changes.
- **Alibaba 2018:** Not in scope.
- **Azure:** Not in scope.
- **GPU recommendation and evaluation:** Not in scope.

## Alibaba GPU 2020 Resource Semantics

Alibaba GPU 2020 provides different CPU and memory observation semantics:

- CPU observations represent lifetime-average CPU usage.
- Memory observations include true peak memory usage through `max_mem`.
- `peak_cpu` is unavailable and remains null.
- CPU Mean, P90, P95, and P99 are percentiles of historical average CPU usage.
- Memory Mean, P90, P95, and P99 are calculated from historical peak-memory values.
- CPU recommendations must be labeled as average-usage sizing and must never be described as peak-safe CPU provisioning.
- Memory is the primary resource for the Alibaba GPU 2020 experiment.
- Any-resource metrics are suppressed.
- This dataset supports memory peak sizing and CPU average-usage sizing. It does not support CPU peak-safe provisioning.

| Policy | CPU meaning | Memory meaning |
|---|---|---|
| Request | Current canonical CPU request | Current canonical memory request |
| Mean | Historical average CPU usage mean | Historical peak-memory mean |
| P90 | 90th percentile of historical average CPU usage | 90th percentile of historical peak memory |
| P95 | 95th percentile of historical average CPU usage | 95th percentile of historical peak memory |
| P99 | 99th percentile of historical average CPU usage | 99th percentile of historical peak memory |

## What This Task Builds

- Alibaba GPU 2020 point-in-time history statistics:
  - Mean.
  - P90.
  - P95.
  - P99.
- Request, Mean, P90, P95, and P99 recommendations per resource.
- Per-resource Request fallback when history is insufficient.
- A common validation comparison across every policy and `min_runs` candidate.
- Memory-first, validation-only selection of the baseline policy and `min_runs`.
- A locked baseline selection record containing the selected policy and selected `min_runs`.
- Recommendation tables for all five baseline policies at the selected `min_runs` for train, validation, and test.
- Validation sensitivity results for same-second targets, multi-instance roles, and group weighting.
- Point-in-time history statistics for train, validation, and test as inputs for Task 7 machine-learning work.

## What This Task Does Not Build

- Machine-learning models.
- Hybrid policies.
- Final-test scoring.
- Test evaluation.
- Adapter, exclusion, or aggregation logic.
- Splits, history counts, or next-occurrence target construction.
- Evaluator or metric changes.
- Google, Alibaba 2018, or Azure changes.
- GPU-resource recommendation or evaluation.

Task 7 consumes the baseline outputs and performs the only final-test evaluation for all five baseline policies, the selected machine-learning model, and the Hybrid policy.

## Current Project State

- Google baselines currently exist inside `pipelines/google_subset/04_splitAndBaselines.ipynb`.
- Google Notebook 04 currently includes:
  - Request.
  - Mean.
  - P90.
  - P95.
  - P99.
  - Resource-specific history fallback.
  - `MIN_RUNS_CANDIDATES = [1, 3, 5, 10]`.
- Task 4 provides:
  - Train, validation, and test splits.
  - Resource-specific history counts.
  - `actual_cpu` and `actual_memory`.
  - CPU and memory target statuses.
- Task 5 provides:
  - Profile-aware evaluation.
  - Separate CPU and memory denominators.
  - Average-usage CPU labeling.
  - Memory-primary metadata.
  - No any-resource metric for Alibaba GPU 2020.

## Relationship to PR #70 and Tasks 1–5

| Item | Relationship |
|---|---|
| PR #70 follow-up | Provides the Alibaba GPU 2020 profile, resource units, evaluation mode, CPU semantics, memory-primary metadata, and target-status vocabulary. It is not modified here. |
| Task 1 | Indirect dependency through Task 3. |
| Task 2 | Indirect dependency through Task 3. |
| Task 3 | Provides eligible canonical `role_occurrence` rows, canonical request fields, resource semantics, and `exclusion_reason`. Consumed, not modified. |
| Task 4 | Provides splits, target statuses, history counts, and point-in-time input tables. Consumed, not modified. |
| Task 5 | Provides the shared evaluator and metrics. Consumed, not modified. |

Task 3 provides the canonical role-occurrence `requested_cpu` and `requested_memory` fields with the schema-defined units and aggregation semantics. Task 6 does not reinterpret or reconstruct those fields.

## Scope

- Dataset: Alibaba GPU 2020 only.
- History: point-in-time eligible history.
- Selection: validation only.
- Primary selection resource: memory.
- Test split: recommendations may be generated after locking, but test targets and test outcomes are never read or scored in this task.
- Final test scoring: owned exclusively by Task 7.

## Dependencies

- Task 3 must be merged and provide the canonical `role_occurrence` artifact.
- Task 4 must be merged and provide train, validation, and test tables with target statuses and history counts.
- Task 5 must be merged and provide the profile-aware evaluator.
- Fixture development can begin once the Task 4 and Task 5 interfaces are agreed.

## Parallel Work

- Fixture development can run in parallel with Tasks 3, 4, and 5.
- Task 7 feature preparation can begin using Task 4 tables while Task 6 is being completed.
- Task 8 verification tooling can be prepared in parallel.
- Full-data baseline selection waits for Tasks 3, 4, and 5.

## Blocks

- **Task 7:** requires the locked baseline selection, recommendations, history statistics, and validation comparison.
- **Task 8:** verifies all Task 6 artifacts and metadata.

## Detailed Implementation Tasks

### 1. Input Contract

- [ ] Read the Alibaba GPU 2020 train, validation, and test tables produced by Task 4.
- [ ] Use only eligible rows with null `exclusion_reason` and a non-null `split`.
- [ ] Never read the rejected output or `instance` audit rows.
- [ ] Use canonical role-occurrence request fields.
- [ ] Do not use descriptive job-total fields as evaluation targets.

### 2. Point-in-Time History Statistics

- [ ] For each eligible row, compute Mean, P90, P95, and P99 from eligible prior values in the same `recurrence_key`.
- [ ] A prior occurrence is eligible only when:
  - `exclusion_reason` is null.
  - The relevant resource value is valid.
  - `end_time_us <= current start_time_us`.

- [ ] CPU statistics use prior lifetime-average CPU in `percent_of_vcpu`.
- [ ] Memory statistics use prior peak memory in `gb`.
- [ ] CPU and memory statistics are computed independently.
- [ ] Missing CPU values do not remove rows from memory history.
- [ ] Statistic counts must equal the corresponding Task 4 history counts.
- [ ] Reuse the Task 4 history-selection function if Task 4 exposes one.
- [ ] Otherwise compute statistics in Task 6 using exactly the same point-in-time rule.
- [ ] Do not change Task 4 split, target, or history behavior.

### 3. Baseline Policies

- [ ] **Request:** use the canonical role-occurrence `requested_cpu` and `requested_memory` fields with the schema-defined units and aggregation semantics from schema §§6 and 8.
- [ ] Do not use `requested_total_cpu` or `requested_total_memory`; those are descriptive job-total fields and are not evaluation targets.
- [ ] **Mean:** use historical average CPU usage for CPU and historical peak memory for memory.
- [ ] **P90:** use the 90th percentile of historical average CPU usage for CPU and the 90th percentile of historical peak memory for memory.
- [ ] **P95:** use the 95th percentile of historical average CPU usage for CPU and the 95th percentile of historical peak memory for memory.
- [ ] **P99:** use the 99th percentile of historical average CPU usage for CPU and the 99th percentile of historical peak memory for memory.
- [ ] Apply history statistics independently per resource.
- [ ] Use a history statistic only when the resource history count is at least `min_runs` and the statistic is non-null.
- [ ] Otherwise use the current canonical request for that resource.
- [ ] A missing request remains missing and is never imputed.
- [ ] An unexpected missing request on an otherwise eligible row is reported as an input error.
- [ ] Recommendation unit columns must match the Alibaba GPU 2020 profile:
  - CPU: `percent_of_vcpu`
  - Memory: `gb`

### 4. Validation Population

- [ ] Freeze one common validation population before scoring.
- [ ] Include eligible validation rows with `memory_target_status = available` or `cpu_target_status = available`.
- [ ] Score every policy and `min_runs` candidate on the same population.
- [ ] Rows with an unavailable CPU target retain null CPU actual values and are excluded only from CPU denominators.
- [ ] Rows with an unavailable memory target retain null memory actual values and are excluded only from memory denominators.
- [ ] Preserve separate CPU and memory valid-row denominators.

### 5. Validation Evaluation

- [ ] Score every policy and `min_runs` candidate using the Task 5 evaluator with the Alibaba GPU 2020 profile.
- [ ] Supply the canonical evaluator columns:
  - `dataset_id`
  - `workload_id`
  - `policy_name`
  - `actual_cpu`
  - `actual_memory`
  - `recommended_cpu`
  - `recommended_memory`

- [ ] Supply the corresponding:
  - `actual_cpu_unit`
  - `recommended_cpu_unit`
  - `actual_memory_unit`
  - `recommended_memory_unit`

- [ ] Use Task 5’s violation, utilization, denominator, missing-value, and suppression behavior.
- [ ] Do not reimplement evaluator metrics in Task 6.
- [ ] Report CPU and memory metrics with separate denominators.
- [ ] Do not report any-resource metrics.
- [ ] Do not report GPU metrics.
- [ ] Carry the average-usage CPU label and memory-primary metadata into the validation outputs.

### 6. Validation-Only, Memory-First Selection

- [ ] Rank policy and `min_runs` candidates using validation results only.
- [ ] Rank memory first.
- [ ] Use the agreed deterministic sort order:
  1. `memory_violation_pct`
  2. `average_memory_waste`
  3. `cpu_violation_pct`
  4. `average_cpu_waste`
  5. `min_runs`
  6. Policy name

- [ ] Select exactly one baseline policy and one `min_runs` value.
- [ ] Record validation metrics for every candidate.
- [ ] Write the locked selection record before producing any test recommendation.
- [ ] Include the selected policy, selected `min_runs`, sort order, validation population, timestamp, and code commit.
- [ ] Sensitivity analyses must not change the selected policy or `min_runs`.

### 7. Locked Recommendations for All Splits

- [ ] After the selection record is written, produce recommendations for all five baseline policies:
  - Request
  - Mean
  - P90
  - P95
  - P99

- [ ] Produce those recommendations at the selected `min_runs` for:
  - Train
  - Validation
  - Test

- [ ] Mark the selected baseline policy in the recommendation tables.
- [ ] The selected baseline is the baseline input to Task 7’s Hybrid policy.
- [ ] Test recommendations use only point-in-time history and the current canonical role-occurrence request.
- [ ] Do not load test target columns:
  - `actual_cpu`
  - `actual_memory`
  - `cpu_target_status`
  - `memory_target_status`

- [ ] Do not call the evaluator on test rows.
- [ ] Task 7 performs the single final-test evaluation of all five baseline policies, the selected machine-learning model, and the Hybrid policy.

### 8. Sensitivity Results

- [ ] Report validation results with and without the Task 4 same-second target flag.
- [ ] Report the eligible multi-instance role-occurrence subgroup separately.
- [ ] Report occurrence-weighted results.
- [ ] Report group-weighted results using equal weighting per `recurrence_key`.
- [ ] Keep all sensitivity results separate from the primary selection.
- [ ] Do not use sensitivity results to change the selected policy or `min_runs`.

### 9. Artifacts and Metadata

- [ ] Write one validation comparison row per policy and `min_runs` candidate.
- [ ] Write the locked baseline selection record.
- [ ] Write baseline recommendation tables for all five policies at the selected `min_runs` for train, validation, and test.
- [ ] Mark the selected baseline policy.
- [ ] Write validation sensitivity tables.
- [ ] Preserve point-in-time history statistics for Task 7 feature preparation.
- [ ] Record:
  - Input artifact paths and checksums.
  - Dataset profile.
  - CPU and memory units.
  - CPU average-usage semantics.
  - Memory-primary evaluation mode.
  - Validation population size.
  - `min_runs` candidate grid.
  - Selection sort order.
  - Selected policy.
  - Selected `min_runs`.
  - Code commit.
  - Same-second and subgroup counts.

- [ ] Confirm the output data location and the pipeline or script location before implementation.

## Required Tests

- [ ] History statistics use only eligible prior occurrences completed at or before the current start.
- [ ] History statistic counts equal the Task 4 history counts.
- [ ] Below `min_runs`, the recommendation falls back to the current canonical request for that resource.
- [ ] A null statistic triggers Request fallback.
- [ ] Missing CPU never removes memory history or memory recommendations.
- [ ] Request recommendations equal the canonical `requested_cpu` and `requested_memory` values.
- [ ] Descriptive job-total request fields are never read.
- [ ] CPU statistics are calculated from historical average CPU usage.
- [ ] Memory statistics are calculated from historical peak memory.
- [ ] `peak_cpu` is never populated.
- [ ] CPU results carry the average-usage label.
- [ ] Memory is reported as the primary resource.
- [ ] Every policy and `min_runs` candidate is scored on the same validation population.
- [ ] The evaluator output contains no any-resource metric and no GPU metric.
- [ ] Selection reads validation results only.
- [ ] Task 6 never loads test target columns or test statuses.
- [ ] Task 6 never calls the evaluator on test rows.
- [ ] Test recommendations for all five baseline policies are produced only after the selection record is written.
- [ ] Test recommendations use the selected `min_runs`.
- [ ] The selected policy is marked in the recommendation tables.
- [ ] A rerun reproduces the validation comparison table and selection.
- [ ] Same-second, multi-instance, and group-weighted sensitivity outputs are reproducible.
- [ ] Existing Google tests pass unchanged.

## Acceptance Criteria

1. All five baseline policies and every `min_runs` candidate are evaluated on the same validation population using Task 5’s evaluator.
2. Selection uses validation outcomes only and ranks memory first.
3. Exactly one baseline policy and one `min_runs` value are recorded in a locked selection record.
4. The locked selection record is written before any test recommendation is produced.
5. Recommendations exist for all five baseline policies at the selected `min_runs` for train, validation, and test, with the selected policy marked.
6. Task 6 reads no test targets, test statuses, or test outcomes and performs no test scoring.
7. Task 7 performs the only final-test evaluation for all five baseline policies, the selected machine-learning model, and the Hybrid policy.
8. No any-resource or GPU metric appears in Alibaba GPU 2020 baseline outputs.
9. CPU metrics are labeled as average-usage results and are never presented as CPU peak-safe provisioning.
10. Memory is reported as the primary resource.
11. CPU and memory denominators are reported separately.
12. Same-second, multi-instance, and group-weighted sensitivity results are reported without changing the selection.
13. Point-in-time history statistics are available for Task 7 machine-learning feature preparation.
14. A rerun reproduces the validation comparison table and selected configuration.

## Expected Outputs

- Alibaba GPU 2020 baseline module or pipeline.
- Validation comparison table.
- Locked baseline selection record.
- Baseline recommendation tables for all five policies at the selected `min_runs` for train, validation, and test.
- Point-in-time history-statistics tables for Task 7.
- Same-second, multi-instance, and group-weighted sensitivity tables.
- Metadata containing selection, units, semantics, counts, paths, checksums, and code commit information.

## Data Leakage Controls

- History uses only prior eligible occurrences completed at or before the current occurrence start.
- Task 4 provides split-isolated targets.
- Validation outcomes are the only outcomes used for policy and `min_runs` selection.
- The selection record is written before test recommendations are created.
- Test targets and test statuses are never loaded in Task 6.
- The evaluator is never called on test rows in Task 6.
- Test recommendations use only historical information and the current canonical request.
- Task 7 performs the only final-test scoring.

## Schema and Adapter Boundaries

- Read canonical columns only.
- Do not add or modify canonical schema fields.
- Do not modify the dataset capability profile.
- Do not reconstruct identity fields.
- Do not modify adapter, exclusion, or aggregation logic.
- Use Task 5’s evaluator without reimplementing metric logic.
- Preserve Alibaba GPU 2020 resource semantics:
  - CPU is lifetime-average usage.
  - Memory is peak usage.
  - CPU peak is unavailable.
  - Memory is the primary resource.
  - Any-resource metrics are suppressed.

## Unresolved Decisions

| ID | Decision | Recommendation |
|---|---|---|
| D-1 | Where final-test scoring occurs | Task 6 locks the baseline policy and `min_runs`, produces recommendations for all five baseline policies at the selected `min_runs`, and does not score test rows. Task 7 performs the one final-test evaluation for Request, Mean, P90, P95, P99, the selected machine-learning model, and the Hybrid policy. |
| D-2 | Sort order after memory | `memory_violation_pct` → `average_memory_waste` → `cpu_violation_pct` → `average_cpu_waste` → `min_runs` → policy name. |
| D-3 | Common validation population | Eligible validation rows with at least one available target: memory or CPU. |
| D-4 | Group-weighting method | Weight each `recurrence_key` equally by taking the mean of per-group metrics. Report as sensitivity only. |
| D-5 | `min_runs` grid | `[1, 3, 5, 10]`, matching the existing Google Notebook 04 candidate grid unless later changed by an approved design decision. |
| D-6 | Module location | Create new Alibaba GPU 2020 baseline code under the appropriate pipeline or shared module location (to confirm). |

## Risks

- CPU recommendations are based on average usage and are not peak-safe.
- P90, P95, and P99 CPU values may still underestimate short-lived CPU spikes because CPU peak observations are unavailable.
- Memory is the stronger resource for peak-sizing conclusions.
- Many recurrence groups have short histories, so Request fallback may dominate at larger `min_runs` values.
- Violation-first ranking may select conservative policies; waste must be reported alongside violation rates.
- Reimplementing Task 4 history selection could produce inconsistent counts; the count consistency check prevents this.
- Accidentally loading test targets before Task 7 would create evaluation leakage.

## Pull-Request Boundary

One pull request containing:

- Alibaba GPU 2020 history-statistics implementation.
- Request, Mean, P90, P95, and P99 baseline policies.
- Validation comparison and selection logic.
- Locked recommendation generation.
- Sensitivity analyses.
- Metadata and artifacts.
- Tests.

Do not include:

- Machine-learning implementation.
- Hybrid implementation.
- Final-test scoring.
- Evaluator changes.
- Target-builder changes.
- Adapter changes.
- Google changes.
- Alibaba 2018 changes.
- Azure changes.

## Handoff

### Task 7

Provide:

- Locked baseline selection record.
- Selected baseline policy.
- Selected `min_runs`.
- All five baseline recommendation tables at the selected `min_runs` for train, validation, and test.
- Selected baseline marked for Hybrid construction.
- Point-in-time history statistics for train, validation, and test.
- Validation comparison table.
- CPU average-usage and memory-primary metadata.

Task 7 uses these artifacts to train and select machine-learning models, construct the Hybrid policy, and perform the single final-test evaluation for all five baseline policies, ML, and Hybrid.

### Task 8

Provide:

- All Task 6 artifacts.
- Metadata.
- Selection record.
- Validation comparison.
- Sensitivity tables.
- Recommendation tables.
- History-statistics tables.
- Reproducibility information.

## Not in This Issue

- Machine-learning models, which belong to Task 7.
- Hybrid policy construction, which belongs to Task 7.
- Final-test scoring, which belongs to Task 7.
- Adapter work, which belongs to Task 3.
- Split or target construction, which belongs to Task 4.
- Evaluator changes, which belong to Task 5.
- Google changes, which belong to Task 10.
- Alibaba 2018, which belongs to Task 9.
- Azure, which belongs to Task 11.
- GPU-resource recommendation or evaluation.

## References

- `pipelines/google_subset/04_splitAndBaselines.ipynb`
- `src/evaluation/evaluator.py`
- `src/evaluation/metrics.py`
- `docs/planning/task5_evaluator_issue.md`
- `docs/design/canonical_workload_schema.md` §§6, 8, 11, and 12
- `docs/design/adapter_framework.md` §9.2
- `docs/data/alibaba_gpu_2020_evidence_and_limitations.md`
- `docs/planning/data_integration_tasks.md`
