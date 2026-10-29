# [P2] Task 9: Alibaba 2018 Adapter Demonstration

**Labels:** `dataset-alibaba`, `priority-low`

**Owner:** Unassigned

**Priority:** Priority 2 · Optional · Only if time permits after the complete Alibaba GPU 2020 pipeline (Tasks 1–8). Not on the critical path.

---

## Objective

Show that the canonical adapter contract accepts a second, structurally different Alibaba source by running the existing `Alibaba2018Adapter` through the Task 1 framework on the Alibaba 2018 sample, producing validated instance-level canonical output and metadata.

**This is an adapter-integration demonstration, not a second full next-occurrence TraceAdvisor experiment.** Alibaba 2018 has no recurrence identity, so no recurrence key, history, next-occurrence target or recommendation result is produced.

## What This Task Builds

- The existing adapter run through the Task 1 framework, with unchanged behavior.
- Validated instance-level canonical output and adapter metadata for the sample.
- Optionally, a request-versus-observed comparison for the current instance, only where units allow it (see task 4 below).
- A one-outcome scope statement for Task 12.

## What This Task Does Not Build

- A recurrence key, history features, next-occurrence targets, splits, baselines, ML or Hybrid.
- Any change to the Alibaba GPU 2020 pipeline.
- Azure or Google work.

## Current Project State

- `src/adapters/alibaba.py` (`Alibaba2018Adapter`, `adapter_version = "0.1.0"`):
  - joins `batch_task` plan rows onto `batch_instance` rows and adds `task_metadata_matched`; duplicate `(job_name, task_name)` plan rows are rejected;
  - emits `instance` rows with `workload_id = job_name`, `execution_id = job_name|task_name`, `instance_id = instance_name`;
  - no recurrence key;
  - source-specific units: `alibaba_plan_cpu_100_per_core` for CPU request, `alibaba_cpu_usage_source_unit` for CPU usage, and `alibaba_memory_source_normalized` for memory;
  - per-resource validity status (`partial`, `invalid` when average exceeds maximum).
- Registered profile: `supports_recurrence = false`, `supports_targets = false`, `supports_ml = false`. After the PR #70 follow-up: `supported_record_levels = instance`, `evaluation_mode = instance_request_versus_observed`, `cpu_unit = null`, `memory_unit = alibaba_memory_source_normalized`, `recurrence_key_origin = none`.
- Tests: `tests/test_alibaba_adapter.py`. Sample builder: `scripts/build_external_canonical_samples.py` (`--alibaba-task`, `--alibaba-instance`).
- **Known gaps (adapter framework §9.3):** validity ignores the source `status`; CPU request and CPU usage use different unit strings; the full `batch_instance` needs chunked loading.
- **Feasibility evidence:** shared task-name or DAG signatures appear in 89.2% of sampled jobs, which is template evidence, not identity; `plan_mem` and `mem_max` normalization is unconfirmed (medians 0.30 vs 0.05).

## Relationship to PR #70 and Tasks 1–5

| Item | Relationship |
|---|---|
| PR #70 follow-up | Provides the 0.2.0 schema and the Alibaba 2018 profile values. Not modified |
| Task 1 | The framework this adapter is run through. Consumed |
| Tasks 2–4 | Not used (Alibaba GPU 2020 only) |
| Task 5 | Used only if the optional request-versus-observed comparison is pursued |

## Scope

- Dataset: Alibaba Cluster Trace 2018 sample only. Never mixed with Alibaba GPU 2020.
- Record level: `instance` only.

## Dependencies

- **Tasks 1–8 complete:** Alibaba 2018 is attempted only after the complete, verified Alibaba GPU 2020 result.
- The existing Alibaba 2018 sample data.

## Parallel Work

- Can run in parallel with Task 10 and Task 11 and with Task 12 script development.
- Never runs alongside Tasks 1–8 and never blocks them.

## Blocks

- None. Task 12 includes its outcome statement if available.

## Detailed Implementation Tasks

### 1. Framework Integration

- [ ] Run `Alibaba2018Adapter` through the Task 1 framework.
- [ ] Confirm unchanged output: same rows, columns and values as the current adapter on the sample.

### 2. Validated Canonical Output

- [ ] Produce validated `instance` rows and adapter metadata at schema 0.2.0.
- [ ] Confirm no recurrence field (`recurrence_key`, history or target columns) is populated.
- [ ] Record the known gaps in the metadata.

### 3. Capability Checks

- [ ] Confirm the profile values listed above are applied and that validation rejects any `occurrence` or `role_occurrence` row.

### 4. Optional Request-Versus-Observed Comparison

- [ ] Only for the current instance, never as a next-occurrence result.
- [ ] CPU: possible only if CPU request and usage units are unified (both documented as 100 = 1 core); unification is a 0.2.0 gap and needs approval (Decision D-1).
- [ ] Memory: not compared until the `plan_mem` and `mem_max` normalization is confirmed (Decision D-2).
- [ ] If neither condition is met, skip the comparison and state why.

### 5. Scope Statement

- [ ] Record exactly one outcome: demonstrated (adapter-only), partially integrated (with gaps listed), or deferred.

## Required Tests

- [ ] Existing `tests/test_alibaba_adapter.py` passes unchanged.
- [ ] Framework-run output equals the direct adapter output on the sample.
- [ ] 0.2.0 validation passes with no recurrence or target fields populated.
- [ ] If the comparison is pursued: unit mismatches are rejected by the Task 5 evaluator.

## Acceptance Criteria

1. The scope statement records exactly one outcome.
2. Validated instance-level output and metadata exist, or the deferral is documented.
3. No next-occurrence, recurrence or recommendation claim is made.
4. No Alibaba GPU 2020, Google or Azure code or artifact changes.

## Expected Outputs

- Validated instance-level sample and metadata.
- Optional request-versus-observed summary, labeled as current-instance only.
- Scope statement for Task 12.

## What Can and Cannot Be Compared with Google

- **Can be compared:** capability flags, record levels, field coverage and adapter-contract behavior.
- **Cannot be compared:** any accuracy, violation or utilization number. Alibaba 2018 has no next-occurrence targets, different units and instance scope.

## Data Leakage Controls

- No split, history or target is created, so no future information can enter.

## Schema and Adapter Boundaries

- Uses the existing adapter and the Task 1 framework; no schema or profile change.
- Unit unification or status-based validity are changes to this adapter only, and only if approved.

## Unresolved Decisions

| ID | Decision | Recommendation |
|---|---|---|
| D-1 | Unify CPU request and usage units | Defer; report CPU request-versus-observed as not evaluated unless time remains after the demonstration |
| D-2 | Memory normalization | Do not compare memory; record the unconfirmed normalization as a limitation |
| D-3 | Outcome if time runs out | Report "deferred; retained at adapter 0.1.0" |

## Risks

- Source-specific units and status-blind validity at 0.1.0.
- Full-table loading needs chunking; the demonstration uses the sample only.

## Pull-Request Boundary

One PR, only if pursued: framework integration, validation output, tests and the scope statement. No Alibaba GPU 2020, Google or Azure code.

## Handoff

- **Task 12:** the scope statement and, if produced, the validated sample metadata.

## Not in This Issue

- Recurrence keys, history, next-occurrence targets, baselines, ML or Hybrid.
- Full `batch_instance` processing.
- Alibaba GPU 2020 changes (Tasks 1–8).
- Google (Task 10) or Azure (Task 11) work.

## References

- `src/adapters/alibaba.py`, `tests/test_alibaba_adapter.py`, `scripts/build_external_canonical_samples.py`
- `docs/design/adapter_framework.md` §9.3
- `docs/data/alibaba_dataset_selection_feasibility.md` §6
- `docs/data/old_dataset_semantics_alibaba2018_azure.md`
- `docs/design/canonical_workload_schema.md` §10
- `docs/planning/data_integration_tasks.md` Task 8 (earlier numbering)
