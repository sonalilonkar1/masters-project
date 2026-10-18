# TraceAdvisor Remaining Development Plan

**Status:** Project-level planning document. Each task is written as an issue that can be created on GitHub later. No code has been changed.
**Date:** 2026-10-16 (work allocation revised 2026-10-17)
**Deadline:** exactly six working days, fixed. Section 5.4 defines what must be complete by the end of day 6.
**Frozen sources (not changed or reinterpreted by this plan):**
- `docs/design/canonical_workload_schema.md` ("schema §")
- `docs/design/adapter_framework.md` ("framework §")
- `docs/design/canonical_schema_design_decisions.md` ("D-nn")
- `docs/design/canonical_schema_implementation_plan.md` (the PR #70 follow-up)

**Supporting evidence:**
- `docs/data/alibaba_gpu_2020_evidence_and_limitations.md` (verified Alibaba GPU 2020 counts and reporting limitations)
- `docs/data/google_subset_pipeline_analysis.md` ("Google analysis F-nn")
- `docs/data/alibaba_dataset_selection_feasibility.md`
- `docs/data/dataset_inspection_and_integration_design.md`

---

## 1. Purpose and relationship to PR #70

**What PR #70 introduced** (merged into `main` at `a0b3c77`):
- the initial canonical schema (`src/canonical/schema.py`, version 0.1.0);
- capability profiles for Google, Alibaba 2018 and Azure (`config/dataset_capabilities.json`);
- adapter-output validation (`src/adapters/validation.py`);
- the adapter base classes and a reference adapter (`src/adapters/base.py`, `src/adapters/reference.py`);
- the Alibaba 2018 and Azure adapters at 0.1.0 (`src/adapters/alibaba.py`, `src/adapters/azure_vm.py`);
- canonical examples and contract tests.

**What the PR #70 follow-up covers** (`docs/design/canonical_schema_implementation_plan.md`): bringing the schema, validation, capability registry, examples and their tests to the frozen 0.2.0 design. It is a **prerequisite** for every task here and is **not repeated** in this document. The PR #70 cleanup is owned by the author of this plan; it is the only work with a fixed owner.

**What this document covers:** all remaining development work after that follow-up. That work builds the actual TraceAdvisor integration and evaluation pipeline, not only the adapter contract:
- the shared adapter framework implementation;
- the Alibaba GPU 2020 integration, from raw data to canonical artifacts;
- shared target construction (splits, history, next-occurrence targets);
- dataset-aware evaluation, baselines, ML and Hybrid;
- final reporting and reproducibility.

**Work areas, kept separate**

| Work area | Where it is planned |
|---|---|
| PR #70 schema and validation correction | `canonical_schema_implementation_plan.md` (prerequisite) |
| Shared adapter framework | Task 1 |
| Alibaba GPU 2020 integration and evaluation | Tasks 2–7 (Priority 1) |
| Alibaba 2018 optional work | Task 8 (Priority 2) |
| Google correction | Task 9 (Priority 3, Google-only) |
| Azure future work | Task 10 (Priority 4, lowest) |
| Alibaba GPU 2020 artifact, metadata and test verification | Task 11a (Priority 1, required) |
| Final cross-dataset reporting and project completion | Task 11b |

---

## 2. Current project state

Verified on branch `docs/canonical-schema-v0.2.0`, which has no code commits beyond `main`.

| Area | What exists | What is missing |
|---|---|---|
| Adapter framework | `src/adapters/base.py` (`AdapterResult`, `BaseDatasetAdapter`), `src/adapters/reference.py` (`ReferenceOccurrenceAdapter`), `src/adapters/validation.py` (0.1.0 checks) | Multiple validated views per result, rejected output, multi-table preparation hooks, dataset-level provenance and rejected counts (framework §4.2–§4.4, §6) |
| Alibaba GPU 2020 data | Verified evidence in the supporting documents. A local copy of the raw tables exists only outside the repository, from earlier analysis | Repository data location, checksum manifest, setup instructions, a loader with stable source row numbers |
| Alibaba GPU 2020 adapter | Nothing | The adapter, its tests and canonical artifacts |
| Alibaba 2018 adapter | `src/adapters/alibaba.py` at 0.1.0: instance rows, no recurrence key; sample build in `scripts/build_external_canonical_samples.py`; `tests/test_alibaba_adapter.py` | 0.2.0 gaps listed in framework §9.3 (status-based validity, unit unification, chunked loading) |
| Azure adapter | `src/adapters/azure_vm.py` at 0.1.0; `tests/test_azure_vm_adapter.py`; local data under `data/raw/azure/` (contents to confirm) | Everything beyond 0.1.0; V1/V2 identity unresolved (framework §9.4) |
| Chronological splits | `src/features/split_utils.py::chronological_split`, used by Google Notebook 04; labels the middle split `"val"`; `tests/test_split_utils.py` | Shared split on the profile ordering time, grouped by job, on eligible role rows only |
| History | Built inside Google Notebook 04, with Google column names | Shared history from eligible prior occurrences completed before the current start |
| Next-occurrence targets | Built inside Google Notebook 04, before split assignment (Google analysis F1) | Shared targets within `recurrence_key`, split-isolated for Alibaba GPU 2020, with per-resource target statuses |
| Baselines | `src/baselines/baseline1_percentile_margin.py` (requires `recurring_job_id`, `peak_cpu`, `peak_mem`); Request, Mean, P90, P95 and P99 inside Notebook 04 | Baselines on canonical target columns |
| ML and Hybrid | `src/features/ml_prep.py`, `src/features/feature_config.py` (Google features); older Google ML and recommender notebooks in `notebooks/subset/` with v0 results in `reports/eval/subset/tables/` | Alibaba GPU 2020 features, models, Hybrid and a locked final test |
| Evaluator and metrics | `src/evaluation/evaluator.py` (`RecommendationEvaluator`), `src/evaluation/metrics.py`; any-resource violation is always computed; `tests/test_evaluation.py` | Any-resource suppression, unit and scope checks, unsupported-resource handling, CPU average-usage labeling (schema §12) |
| Google pipeline | `pipelines/google_subset/` Notebooks 00–04 with outputs in `data/processed/google_subset_v1/` (occurrences, features, `baseline_validation_comparison.csv`, `metadata.json`). Notebook 05 is 0 bytes (F6) | Leakage-safe targets (F1–F5), a final Google evaluation on corrected artifacts |
| Tests | 8 modules under `tests/`. Baseline run: 81 pass, 1 fails (`test_google_train_target_nulls_are_preserved`, 1,463 vs 1,801) | Framework, GPU 2020 loader and adapter, target-builder, evaluator-contract and integration tests |
| Reproducibility | `scripts/verify_data_setup.py`, `scripts/report_summary.py`, `docs/data/subsetSetup.md` (Google), `requirements.txt` | GPU 2020 setup and verification, artifact manifest with checksums, fresh-environment run |

---

## 3. Project priority order

### Priority 1: Alibaba GPU 2020 (required; critical path)
The required second full integration and the primary development path.
- **Required within the six-day deadline:** the shared adapter framework (Task 1), data setup and source loading (Task 2), the adapter and canonical artifacts (Task 3), shared splits, history and targets (Task 4), the dataset-aware evaluator (Task 5), baselines and validation evaluation (Task 6), ML, Hybrid, the locked decision manifest and the final test (Task 7), and verification of the completed final result (Task 11a).
- **The completed Alibaba GPU 2020 result includes ML, Hybrid and the final-test evaluation.** Baseline validation alone (Task 6) is only an intermediate result.

### Priority 2: Alibaba Cluster Trace 2018 (optional, if time permits)
Task 8. An adapter-only demonstration using the existing adapter, attempted only after the required Alibaba GPU 2020 path is complete. It has no official recurrence identifier, so no next-occurrence result is claimed and no recurrence is invented.

### Priority 3: Google subset corrections (separate lower-priority Google-only issue)
Task 9. Fixes targets built before split assignment, validation targets in the test period, and leakage-safe validation selection; reruns Google baselines and the final Google evaluation; updates Google artifacts and metadata. Never combined with Alibaba work, and never scheduled ahead of the required Alibaba GPU 2020 path.

### Priority 4: Azure VM (future; lowest priority)
Task 10. Kept in the plan as an explicit future implementation task. No Azure implementation within the deadline and no Azure code changes in the current sequence. Azure is deferred by priority, not excluded.

Task 11b (final cross-dataset report and project completion) closes the project after the issues above.

**No lower-priority issue blocks a higher-priority one.** Tasks 8, 9 and 10 never block the Alibaba GPU 2020 deliverable.

---

## 4. Recommended development tasks

Each task below is written as a GitHub issue. Issues are **not assigned to fixed people**. Any of the four team members picks up the highest-priority issue whose prerequisites are met. Larger issues (Tasks 3 and 4) may be shared by two members working on separate parts of the same issue.

| # | Issue | Priority | Status | Prerequisites | Critical path | Within the deadline |
|---|---|---|---|---|---|---|
| 1 | Shared Adapter Framework and Rejected-Output Support | 1 | Required | PR #70 cleanup | Yes | Required |
| 2 | Alibaba GPU 2020 Data Setup and Reproducible Source Loading | 1 | Required | Raw data access | Yes | Required |
| 3 | Alibaba GPU 2020 Adapter and Canonical Artifact Generation | 1 | Required | PR #70 cleanup; 1, 2 | Yes | Required |
| 4 | Shared Chronological Splits, History and Next-Occurrence Targets | 1 | Required | PR #70 cleanup; full run: 3 | Yes | Required |
| 5 | Dataset-Aware Evaluator and Metric Contract | 1 | Required | PR #70 cleanup | Yes (must finish before 6) | Required |
| 6 | Alibaba GPU 2020 Baselines and Validation Evaluation | 1 | Required | 4, 5 | Yes | Required |
| 7 | Alibaba GPU 2020 Machine-Learning, Hybrid and Final-Test Evaluation (7a validation, 7b manifest and final test) | 1 | Required | 7a: 4, 6; 7b: 6, 7a | Yes | Required |
| 11a | Alibaba GPU 2020 Artifact, Metadata and Test Verification | 1 | Required | 2, 3, 4, 6, 7a, 7b | Yes (end of path) | Required |
| 8 | Alibaba 2018 Optional Adapter Demonstration or Full Integration Decision | 2 | Optional | Tasks 1–7 and 11a complete | No | If time remains |
| 9 | Google Subset Leakage-Safe Target and Split Correction | 3 | Separate, lower priority | Team approval; required path complete | No | If time remains |
| 10 | Azure VM Future Integration | 4 | Future | Priority 1 complete | No | Not in scope |
| 11b | Final Cross-Dataset Report and Project Completion | — | Final | 7; 9 or a documented Google decision; 8 and 10 decisions | No | After the required path |

Task numbers are unchanged from the earlier version of this plan; Task 7 is split into 7a and 7b, and Task 11 into 11a and 11b.

---

### Task 1. Shared Adapter Framework and Rejected-Output Support

**Priority and status:** Priority 1 · Required · Critical path.

**What this task builds:** The shared adapter machinery in `src/adapters/`:
- `AdapterResult` extended to carry several named, separately validated canonical views, including a `role_occurrence` (role) view and an `instance` view;
- a separate rejected output;
- per-view validation routing;
- multi-table preparation hooks;
- adapter provenance and rejection metadata;
- a linkage-validation interface that accepts both a role view and an instance view.

**Purpose:** The Alibaba GPU 2020 adapter must return a `role_occurrence` view, an `instance` view and a rejected output with provenance (framework §4.2–§4.4, §6), and its instance rows must be checked against their parent role rows (framework §7.2). The current `AdapterResult` holds one frame and has no rejected output, and the PR #70 follow-up validates one frame at a time.

**Task 1 provides the framework that Task 3 needs. It does not implement Alibaba GPU 2020-specific joins, identity construction, resource aggregation or parent linkage**; those are Task 3.

**Dataset scope:** Shared code. Exercised with `ReferenceOccurrenceAdapter` and synthetic role and instance fixtures. Alibaba 2018 and Azure must keep working unchanged.

**Prerequisites:**
- PR #70 cleanup merged before this issue merges (0.2.0 validation and capability fields). Development can start on day 1 on top of the cleanup branch.
- No earlier task, raw data or generated artifacts.
- Design: framework §3, §4, §6, §7 and §8 (frozen).

**Can run in parallel:** Yes, with Tasks 2, 4 (fixture work) and 5.

**Work to complete:**
1. **Result structure:** `AdapterResult` extended to multiple named validated views (for example a role view and an instance view), a separate rejected output, and metadata. Existing single-view attributes remain available.
2. **Multi-table preparation:** a preparation step that receives several source tables before mapping.
3. **Rejected output:** records carry `rejection_reason`, receive only the minimal checks (schema §9.5), and are kept out of every validated view and all downstream processing.
4. **Provenance and rejection metadata:** `schema_version`, capabilities, adapter name and version, source and canonical row counts, `source_version`, source file paths and checksums, `telemetry_window`, counts per validity status, per CPU and memory validity status and per exclusion reason, rejected counts per `rejection_reason`, and join-coverage counts (framework §6); source-row traceability through `source_` columns. Task 1 defines and checks these fields; Task 3 fills in the Alibaba GPU 2020 values.
5. **Per-view validation:** each view goes through the shared `validate_adapter_output` with the dataset profile; adapters never apply splits, history, targets or evaluation (framework §8).
6. **Linkage-validation interface:** a shared check that accepts a role view and an instance view and confirms, on validated views only, that every instance row's `role_key` exists in the role view and that its `workload_id`, `recurrence_key` and `occurrence_id` equal the parent role row's values, with nulls compared as equal (framework §7.2; schema §5.5). Rejected records never take part. The interface only checks; it does not build or copy any field.
7. **Backward compatibility:** existing adapters, `scripts/build_external_canonical_samples.py` and their callers keep working; the 0.2.0 sample outputs of that script are regenerated.
8. **No dataset-specific logic:** no Alibaba GPU 2020 joins, identity construction, attempt indexing, resource aggregation, exclusion rules or parent linkage.

**Design and decisions required:**
- Applied as frozen: rejected-output semantics, provenance fields, ownership boundaries.
- To decide at implementation: the Python shape of the result (for example a mapping of view name to frame), how the rejected output is typed, how metadata is serialized next to artifacts, and the name and signature of the linkage-validation interface.

**Files or modules likely involved:** `src/adapters/base.py`, `src/adapters/reference.py`, `src/adapters/__init__.py`; new `tests/test_adapter_framework.py` (name to confirm during implementation).

**Tests and verification:**
- Synthetic framework tests with a role view and an instance view: multi-view results, rejected-output separation, minimal rejected checks, metadata completeness, per-view validation errors.
- Linkage-interface tests on synthetic views: matching parent fields pass (including a null `recurrence_key` on both sides); a missing parent `role_key` and a mismatched `workload_id`, `recurrence_key` or `occurrence_id` are rejected.
- Regression: `tests/test_adapter_contract.py`, `tests/test_alibaba_adapter.py`, `tests/test_azure_vm_adapter.py`, `tests/test_external_adapter_integration.py` pass without edits.

**Expected outputs or artifacts:** Framework code and tests only.

**Acceptance criteria:**
1. Existing Alibaba 2018, Azure and reference adapters work without edits.
2. A result can carry several validated views, including a role view and an instance view, and a rejected output; no rejected record appears in a validated view.
3. Every view is validated separately against the dataset profile.
4. Provenance and rejection metadata is produced and checked.
5. The linkage-validation interface accepts a role view and an instance view and rejects orphan and mismatched instance rows.
6. No Alibaba GPU 2020-specific identity construction, joins, aggregation or linkage is present.
7. The full suite's only failure is the existing Google target-null test.

**Risks and limitations:** Backward compatibility of `AdapterResult` for existing callers and `scripts/build_external_canonical_samples.py`.

**Pull-request boundary:** One PR. No dataset-specific joins or resource aggregation.

**Handoff:** Task 3 builds on the multi-view result, rejected output, metadata fields and linkage-validation interface. Task 8 reuses the framework for the Alibaba 2018 demonstration. Agree the result and linkage interfaces early (day 1) so Task 3 fixture work can start before this issue merges.

---

### Task 2. Alibaba GPU 2020 Data Setup and Reproducible Source Loading

**Priority and status:** Priority 1 · Required · Critical path.

**What this task builds:** A reproducible raw-data setup for the six Alibaba GPU 2020 tables, a checksum manifest, a data-verification step, and a source loader that reads the tables with explicit schemas, preserves source-file order and assigns a stable `source_row_number`.

**Not in this task:** canonical role or instance identity construction (`role_key`, `instance_slot_key`, `instance_attempt_index`, `instance_id`), joins across tables, and any canonical mapping. Those are Task 3.

**Purpose:** The frozen instance identity depends on `source_row_number`, the data-line number in the checksum-verified decompressed file, so the loader must preserve file order (framework §9.2, D-21). Results must be reproducible from documented inputs.

**Dataset scope:** Alibaba GPU 2020 (`cluster-trace-gpu-v2020`) only.

**Prerequisites:**
- Raw data: access to the six tables.
- No earlier task. The loader does not depend on the schema changes, so this issue **can start immediately**, before the PR #70 cleanup merges. It uses the literal identifier `alibaba_gpu_v2020` and imports nothing from the 0.2.0 schema.

**Can run in parallel:** Yes, with Tasks 1, 4 (fixture work) and 5.

**Work to complete:**
1. **Setup:** a documented raw-data location (for example `data/raw/alibaba_gpu_v2020/`, to confirm during implementation), not committed to git; download and decompression instructions.
2. **Verification:** a checksum manifest for `pai_job_table`, `pai_task_table`, `pai_instance_table`, `pai_sensor_table`, `pai_group_tag_table`, `pai_machine_spec`; an extension of `scripts/verify_data_setup.py`.
3. **Source-table loading:** explicit column names and types (explicit schemas for the headerless official tables), column selection, chunked or columnar reading for the large tables.
4. **Source order and row numbers:** source-file order preserved; `source_row_number` assigned as the data-line number in the checksum-verified, decompressed file, stable across repeated and chunked loads.
5. **Reproducible loader tests:** see Tests and verification.
6. **Resource requirements:** document disk and memory needs.

**Design and decisions required:**
- Applied as frozen: `source_row_number` definition and file-order preservation.
- To decide: raw-data location, whether a local Parquet cache is built after verification, chunk sizes and column types.

**Files or modules likely involved:** a new loader module, for example `src/adapters/alibaba_gpu_2020_source.py` (to confirm during implementation); `scripts/verify_data_setup.py`; a setup section in `docs/data/subsetSetup.md` or a new setup document (to confirm); `.gitignore` if needed.

**Tests and verification:**
- Reproducible loader fixture tests: column naming and types, checksum failure, preserved source-file order, identical `source_row_number` under repeated, chunked and full loads.
- Local data check: table row counts match the verified counts in the evidence document.

**Expected outputs or artifacts:** Checksum manifest; setup instructions; optional verified local cache (not committed).

**Acceptance criteria:**
1. A fresh clone plus the documented download yields verified tables.
2. The loader reproduces the verified row counts.
3. `source_row_number` is stable across repeated and chunked loads.

**Risks and limitations:** Download size and local storage; memory for the instance and sensor tables; the official source location could change.

**Pull-request boundary:** One PR. No canonical identity construction, no role aggregation and no target generation.

**Handoff:** Task 3 receives the verified source tables with `source_row_number` and the checksum manifest. Task 11a reuses the checksum manifest and verification step.

---

### Task 3. Alibaba GPU 2020 Adapter and Canonical Artifact Generation

**Priority and status:** Priority 1 · Required · Critical path.

**What this task builds:** The production Alibaba GPU 2020 adapter and a build script that produce three canonical artifacts: the validated `role_occurrence` evaluation view, the validated `instance` audit view, and the rejected output, with adapter metadata.

**Purpose:** This is the core of the second full integration: turning the six source tables into canonical evaluation rows exactly as the frozen design specifies (framework §9.2, schema §5–§9).

**Dataset scope:** Alibaba GPU 2020 only.

**Prerequisites:**
- PR #70 cleanup merged (0.2.0 fields, profile, generic validation).
- Tasks 1 and 2 merged. Fixture-based adapter tests can begin once the Task 1 result and linkage interfaces are agreed.
- Raw data verified by Task 2.
- Design: all frozen; nothing to reopen.

Dependency order:

```text
PR #70 follow-up
→ Task 1 shared multi-view adapter framework
→ Task 2 verified Alibaba GPU 2020 data loading
→ Task 3 Alibaba GPU 2020 adapter and canonical artifacts
→ Task 4 shared targets and evaluation
```

Task 3 needs the first three. Task 2 has no code dependency on the PR #70 follow-up or Task 1, so it still starts on day 1 (section 5).

**Can run in parallel:** Yes, with Tasks 4 and 6 (fixture work) and 5. Two members can share this issue, for example one on joins, identity and timestamps, the other on exclusion rules and resources.

**Work to complete:**
1. **Source-table joins:** job ← group; job ← task ← instance ← sensor ← machine specification; sensor rows join on `job_name`, `task_name` and `worker_name`, through the Task 1 multi-table preparation step.
2. **Role identity:** `workload_id = group`, `recurrence_key = group||task_name`, `occurrence_id = group||job_name`, `role_key = group||job_name||task_name`; jobs without `group` use the fallback keys (`workload_id = job_name`, `occurrence_id = job_name`, `role_key = job_name||task_name`) with `recurrence_key` null and `exclusion_reason = no_recurrence_key`.
3. **Instance identity:** deterministic `instance_slot_key` (`job_name||task_name||inst_name`); 1-based `instance_attempt_index` within the slot, ordered by instance start time (null last) and then `source_row_number`; `instance_id = job_name||task_name||inst_name||instance_attempt_index`; nullable `worker_id`; `source_row_number` taken unchanged from the Task 2 loader (never recomputed); raw `source_` columns; no `source_seq_no`.
4. **Parent-field inheritance:** instance rows copy `workload_id`, `recurrence_key`, `occurrence_id` and `role_key` from their parent role row, including the fallback values.
5. **Full instance-to-parent linkage:** the Task 1 linkage-validation interface runs on the full role and instance views; zero orphan and zero mismatched instance rows.
6. **Timestamps** (source seconds × 10⁶, `time_basis = trace_relative`):
   - role `start_time_us` = the job submission time;
   - role `end_time_us` = the job completion time, or null if unavailable;
   - instance `event_time_us` = the parent job submission time, always;
   - instance `start_time_us` and `end_time_us` = the instance's own source timestamps, or null if unavailable;
   - the first task launch time is kept only as the lifecycle extension `launch_time_us`; it is never used as any `start_time_us` or `end_time_us`;
   - no task-launch time, sensor time or other timestamp is substituted or inferred for a missing required timestamp; nothing is carried forward or fabricated.
7. **Rejected-record routing through Task 1:** jobs without a submission time rejected whole as `missing_submission_time`, with all their role and instance rows, into the Task 1 rejected output.
8. **Exclusions:** the 14 ordered rules of schema §9.3, evaluated on role rows in this order; the first failed rule sets the single primary `exclusion_reason`, and a null `exclusion_reason` means eligible:
   1. `no_recurrence_key`: the job has no `group`;
   2. `job_failed`: job status is `Failed`;
   3. `job_incomplete`: the job is not `Terminated`, or has no completion time;
   4. `task_not_terminated`: task status is not `Terminated`;
   5. `missing_or_invalid_request`: `plan_cpu` or `plan_mem` is missing or not greater than 0;
   6. `instance_failed`: any instance of the role is `Failed`;
   7. `instance_interrupted`: any instance of the role is `Interrupted`;
   8. `instance_incomplete`: any instance of the role is otherwise not `Terminated` (for example `Running`, `Waiting`, `Ready`);
   9. `missing_worker_name`: any instance of the role has no `worker_name`;
   10. `multi_attempt_worker`: any worker of the role has more than one attempt;
   11. `missing_sensor`: no worker of the role has a sensor row;
   12. `partial_sensor_coverage`: some, but not all, workers of the role have a sensor row;
   13. `invalid_memory_exceeds_capacity`: any worker's `max_mem` exceeds the host's `cap_mem`;
   14. `invalid_resource`: any worker's `max_mem` is below its `avg_mem`, or a memory value is negative.

   Eligible and ineligible role rows both stay in the validated `role_occurrence` view for audit; excluded rows are never used for history or targets. A sensor row with missing CPU still counts as sensor coverage (rules 11–12). Instance rows get no independent exclusion reason: eligibility is decided on the parent role row, and a null `exclusion_reason` on an instance row does not mean eligible. Google has no exclusion rules and Alibaba 2018 rules are not defined in this version.
   - **Per-resource validity:** `cpu_validity_status`, `memory_validity_status` and row `validity_status`; missing CPU gives `cpu_validity_status = partial` and does not affect memory eligibility.
9. **Resource aggregation:** requests in `percent_of_vcpu`, `gb` and `percent_of_gpu`; role values as the maximum over eligible instances; `observed_cpu` as a lifetime average, null if any eligible worker's CPU is missing; `peak_cpu` always null; `peak_memory` from `max_mem` as the maximum over eligible workers; worker peaks never summed; GPU fields retained, not evaluated.
10. **View validation:** the `role_occurrence` view and the `instance` view each validated against the Alibaba GPU 2020 profile through Task 1 per-view validation.
11. **Artifacts:** a build script that writes the canonical `role_occurrence`, `instance` and rejected-output artifacts, and the Task 1 metadata fields filled in for Alibaba GPU 2020 (checksums, counts per exclusion and rejection reason).

**The adapter must not own:** chronological splits, history, next-occurrence targets, baselines, ML predictions, Hybrid policies or evaluator metrics.

**Design and decisions required:**
- Applied as frozen: everything listed in Work to complete.
- To decide: artifact file format and paths, and the layout of the count report.

**Files or modules likely involved:** new `src/adapters/alibaba_gpu_2020.py`; `src/adapters/__init__.py`; a new build script under `scripts/` (name to confirm); new `tests/test_alibaba_gpu_2020_adapter.py` (to confirm); outputs under `data/processed/alibaba_gpu_v2020/` (to confirm).

**Tests and verification:**
- Alibaba GPU 2020 identity and linkage tests on fixtures: each identity rule, the fallback keys, `instance_slot_key`, attempt ordering (null start times, ties broken by `source_row_number`), `instance_id` uniqueness across retries, parent-field inheritance, and the linkage check rejecting orphan and mismatched instance rows.
- Fixture tests for the timestamp contract, rejected routing, each exclusion rule and the rule order, CPU nullness, and `peak_cpu` rejection.
- Full-data population checks against the verified evidence (`docs/data/alibaba_gpu_2020_evidence_and_limitations.md`):
  - 462,156 role-occurrences pass every exclusion rule before the final `multi_attempt_worker` rule;
  - the final `multi_attempt_worker` rule removes 256 of them, leaving 461,900 eligible role-occurrences;
  - 1,224 eligible role-occurrences have missing CPU;
  - the rejected output holds 3,663 jobs, 6,942 role rows and 111,219 instance rows (`missing_submission_time`).
- Every view validated against the Alibaba GPU 2020 profile.

**Expected outputs or artifacts:** canonical `role_occurrence`, `instance` and rejected-output artifacts; adapter metadata; a count report explaining any difference from the evidence.

**Acceptance criteria:**
1. Both validated views pass validation; `role_key` and `instance_id` are unique and non-null.
2. No validated row lacks a usable canonical time; the Task 1 linkage check reports zero orphan and zero mismatched instance rows.
3. Counts match the verified evidence (462,156 before `multi_attempt_worker`; 256 removed by it; 461,900 eligible; 1,224 eligible with missing CPU; rejected 3,663 jobs, 6,942 role rows, 111,219 instance rows), or each difference is explained in the count report.
4. `peak_cpu` is null everywhere; GPU fields are present but unused.
5. Existing adapters and their tests are unchanged.

**Risks and limitations:** Selection bias from eligibility rules; low sensor coverage on multi-instance roles; the final `multi_attempt_worker` rule removes 256 role-occurrences (462,156 → 461,900); memory pressure on the instance–sensor join.

**Pull-request boundary:** One PR for the adapter and tests. Full-data artifacts in the same PR or a short follow-up PR. No split or target columns.

**Handoff:** The `role_occurrence` artifact and its metadata unblock the Task 4 full-data run. The `instance` view, the rejected output and the count report go to Task 11a for verification.

---

### Task 4. Shared Chronological Splits, History and Next-Occurrence Targets

**Priority and status:** Priority 1 · Required · Critical path.

**What this task builds:** A shared target-builder module that takes eligible `role_occurrence` rows and adds `split`, history features, `actual_cpu`, `actual_memory`, `cpu_target_status` and `memory_target_status`, producing the Alibaba GPU 2020 train, validation and test tables.

**Purpose:** Splits, history and targets are shared downstream logic, not adapter logic (framework §8, schema §11). Today they exist only inside Google Notebook 04.

**Dataset scope:** Alibaba GPU 2020. Google targets stay referenced from existing artifacts and are unchanged here; any Google change belongs to Task 9.

**Prerequisites:**
- PR #70 cleanup merged before this issue merges (target-status vocabulary). The module and its synthetic-fixture tests can be developed from day 1 on the cleanup branch.
- **Full execution waits for the Task 3 canonical artifacts.**
- Design: schema §11 (frozen).

**Can run in parallel:** Yes, with Tasks 1, 2, 3 and 5 while working on fixtures. Its full-data run cannot start until Task 3 delivers artifacts.

**Work to complete:**
1. **Splits:** chronological 70/15/15 by job submission, so all role rows of a job share a split; only eligible `role_occurrence` rows receive a split; instance audit rows and rejected records are never processed.
2. **History:** eligible prior occurrences in the same `recurrence_key` only (null `exclusion_reason`, relevant resource valid, `end_time_us` ≤ current `start_time_us`).
3. **Targets:** the next eligible occurrence within the same `recurrence_key`; split-isolated; CPU targets are lifetime averages, memory targets are peaks.
4. **Target statuses:** `available`, `no_next_occurrence`, `next_occurrence_in_other_split`, `next_occurrence_ineligible_resource`, `unsupported_resource`, assigned per resource.
5. **Flags and optional features:** a flag for same-second targets (expected 245 validation and 251 test); an optional count of earlier completed failed jobs in the same group, used only when completion is known and at or before the current start, never for resource history or targets.

**Design and decisions required:**
- Applied as frozen: split rule, history rule, target rule, statuses, isolation.
- To decide: the module interface; how the schema label `validation` coexists with the existing Google `"val"` label without changing Google behavior; whether the optional failed-job feature is built in this task or in Task 7.

**Files or modules likely involved:** new `src/features/target_builder.py` (to confirm); `src/features/split_utils.py` (extended, Google behavior unchanged); new `tests/test_target_builder.py` (to confirm); `tests/test_split_utils.py`.

**Tests and verification:**
- Fixture tests for each status, the completion-before-start rule, same-job grouping, split isolation and the same-second flag.
- Leakage test: no history or target value comes from a later split.
- Full-data check against the expected split-isolated populations (42,104 validation and 44,087 test before the final `multi_attempt_worker` exclusion).
- Regression: `tests/test_split_utils.py`, `tests/test_google_canonical_contract.py` unchanged; Google artifacts byte-identical.

**Expected outputs or artifacts:** Alibaba GPU 2020 train, validation and test tables; split and target metadata (boundaries, status counts per resource).

**Acceptance criteria:**
1. Every eligible role row has one split; no job spans two splits.
2. CPU and memory statuses are independent; missing CPU never removes a memory target.
3. No Alibaba GPU 2020 target crosses a split.
4. Google outputs are unchanged.

**Risks and limitations:** Many recurrences have short histories; same-second targets are flagged, not removed; off-by-one errors in time comparisons are a leakage risk.

**Pull-request boundary:** One PR. No evaluator or baseline code.

**Handoff:** The train, validation and test tables go to Task 6 (and later Task 7). Split and target metadata go to Task 11a.

---

### Task 5. Dataset-Aware Evaluator and Metric Contract

**Priority and status:** Priority 1 · Required · Critical path.

**What this task builds:** An extension of the shared evaluator and metrics that applies the dataset capability contract (schema §12) when scoring recommendations.

**Purpose:** Alibaba GPU 2020 must report no any-resource metric, keep CPU and memory denominators separate, and label CPU as average-usage. The current evaluator always computes any-resource violation.

**Dataset scope:** Shared; used by Alibaba GPU 2020 and Google.

**Prerequisites:**
- PR #70 cleanup merged before this issue merges (capability fields such as `any_resource_metric_valid`). Development and synthetic-fixture tests can start on day 1 on the cleanup branch.
- No earlier task, and no Alibaba GPU 2020 artifacts.

**Can run in parallel:** Yes, with Tasks 1–4. It must be merged before Task 6's full validation run.

**Work to complete:**
1. **Suppression:** any-resource metrics are not reported when `any_resource_metric_valid` is false.
2. **Denominators:** separate valid-row counts for CPU and memory; missing values stay unknown and never count as non-violations.
3. **Contract checks:** actual and recommended units and scope must match; unsupported resources are excluded from that resource's metrics.
4. **Labeling:** Alibaba GPU 2020 CPU results carry an average-usage label.
5. **Output contract:** results use the canonical evaluator names (`dataset_id`, `workload_id`, `policy_name`, `actual_*`, `recommended_*`).

Baseline and `min_runs` selection are not part of this task (Task 6).

**Design and decisions required:**
- Applied as frozen: schema §12 rules.
- To decide: how the dataset profile is passed to the evaluator, and how the CPU label appears in summary output.

**Files or modules likely involved:** `src/evaluation/evaluator.py`, `src/evaluation/metrics.py`, `tests/test_evaluation.py`; a new evaluator-contract test module (to confirm).

**Tests and verification:** Tests for suppression, unit and scope mismatch errors, separate denominators, unsupported resources and labeling. Regression: Google validation outputs (`baseline_validation_comparison.csv`) reproduce exactly.

**Expected outputs or artifacts:** Evaluator code and tests.

**Acceptance criteria:**
1. Google metrics are unchanged within floating-point tolerance.
2. An Alibaba GPU 2020 evaluation reports no any-resource metric.
3. Unit or scope mismatches fail with a clear error.
4. CPU average-usage results are labeled.

**Risks and limitations:** Existing notebooks may expect `any_resource_violation_pct` to always exist; it stays for profiles where it is valid.

**Pull-request boundary:** One PR.

**Handoff:** Tasks 6 and 7 score recommendations with it. Task 9 reuses it for the Google rerun, and Task 11b for final tables.

---

### Task 6. Alibaba GPU 2020 Baselines and Validation Evaluation

**Priority and status:** Priority 1 · Required · Critical path. **Produces the first end-to-end Alibaba GPU 2020 validation result, which is an intermediate result.** The completed result also needs Task 7 (ML, Hybrid and the final test).

**What this task builds:** An Alibaba GPU 2020 evaluation pipeline that computes Request, Mean, P90, P95 and P99 recommendations from train history, scores them on validation with the dataset-aware evaluator, and selects a baseline and `min_runs`.

**Purpose:** It is the first end-to-end result from raw data to evaluated recommendations, and the reference against which ML and Hybrid are judged.

**Dataset scope:** Alibaba GPU 2020.

**Prerequisites:** Task 5 merged; Task 4 merged with its train and validation tables. Baseline generalization and fixture tests can start once Task 5's interface is agreed; **the full validation run waits for the Task 4 tables, which in turn need the Task 3 artifacts.**

**Can run in parallel:** Fixture work runs alongside Tasks 3 and 4. Once the full run is under way, Task 11a verification tooling and Task 7 feature work can proceed in parallel.

**Work to complete:**
1. **Baselines on canonical columns:** generalize `baseline1_percentile_margin.py` to `recurrence_key`, `actual_cpu` and `actual_memory`, keeping Google behavior; Request fallback when history is below `min_runs`.
2. **Validation evaluation:** memory as the primary resource; CPU reported separately as average-usage sizing; no any-resource metric; no GPU metric.
3. **Selection:** memory-first choice of the baseline and `min_runs`, using train and validation only; test is never read.
4. **Sensitivity:** same-second targets reported separately; group-weighted sensitivity (schema §14).
5. **Artifacts:** validation tables and metadata.

**Design and decisions required:**
- Applied as frozen: memory-first ranking, CPU labeling, no any-resource metric.
- To decide: the `min_runs` grid, the tie-break rule after memory, and the group-weighting method.

**Files or modules likely involved:** `src/baselines/baseline1_percentile_margin.py`; a new Alibaba GPU 2020 pipeline, for example `pipelines/alibaba_gpu_2020/` or a script under `scripts/` (to confirm); new tests.

**Tests and verification:** Baselines use train history only; Google baseline outputs unchanged; a rerun reproduces the validation table.

**Expected outputs or artifacts:** Alibaba GPU 2020 validation summary (memory first, CPU labeled), selected baseline and `min_runs`, sensitivity tables, metadata.

**Acceptance criteria:**
1. All baselines are scored on the same targets with the shared evaluator.
2. Selection uses train and validation only.
3. No any-resource or GPU metric appears; CPU is labeled average-usage throughout.

**Risks and limitations:** Average CPU sizing is not peak-safe; results describe per-instance role behavior, not full workloads. These are validation results, so they are preliminary until Task 7 freezes decisions.

**Pull-request boundary:** One PR, including the validation artifacts' metadata.

**Handoff:** The selected baseline, `min_runs` and validation tables go to Task 7a and the decision manifest (Task 7b). The validation artifacts and metadata go to Task 11a, which verifies them with the final result after Task 7b.

---

### Task 7. Alibaba GPU 2020 Machine-Learning, Hybrid and Final-Test Evaluation

**Priority and status:** Priority 1 · Required within the six-day deadline · Critical path. **Produces the completed Alibaba GPU 2020 result.** The issue has two parts: **7a** (ML and Hybrid on validation) and **7b** (locked decision manifest and final test).

**What this task builds:** Alibaba GPU 2020 feature preparation, dataset-specific ML models, validation-based model selection, Hybrid recommendations, a locked decision manifest, and the one untouched final-test evaluation of all policies.

**Purpose:** Completes the 295B policy comparison (Request, Mean, P90, P95, P99, ML-only and Hybrid) for the second dataset under final-test discipline. The completed Alibaba GPU 2020 result must include ML, Hybrid and the final test; baseline validation alone (Task 6) is an intermediate result.

**Dataset scope:** Alibaba GPU 2020.

**Prerequisites:**
- **7a:** the Task 4 train and validation tables (day 4); the Task 6 baseline selection for the comparison and for Hybrid. Feature work starts on the Task 4 tables while Task 6 finishes.
- **7b:** Task 6 and Task 7a complete. The manifest is locked on day 5, before the test split is read; the final test runs on day 6.

**Can run in parallel:** 7a runs alongside Task 6; Task 11a verification tooling can be prepared alongside 7a and 7b. Task 11a's final verification starts only after the 7b final test completes. Tasks 8 and 9 never take capacity from Task 7.

**Work to complete:**
1. **Feature preparation (7a):** pre-execution fields and Task 4 history features only; GPU type may be a feature, but no GPU target.
2. **Dataset-specific ML models (7a):** regression models trained on train; the fitted Google model is not reused.
3. **Validation-based model selection (7a):** models and hyperparameters selected on validation only; test is never read.
4. **Hybrid recommendation construction (7a):** start from the existing Google rule (`max(ML prediction, P95)`), applied per resource, memory primary; validated on validation.
5. **Locked decision manifest (7b):** baseline, `min_runs`, features, models, hyperparameters, Hybrid rules and fallbacks, locked before the test is read.
6. **Final-test evaluation (7b):** one evaluation of all policies from the locked manifest, run exactly once; **no post-test tuning**.
7. **Reporting rules (7a and 7b):** memory-first reporting; CPU labeled as average-usage sizing, not peak-safe sizing; no GPU metric and no any-resource metric, because both are unsupported for Alibaba GPU 2020.

**Design and decisions required:**
- To decide: model families, the feature list, the Hybrid variants (the 295B Conservative, Balanced and Efficient objectives), and the documented procedure for rerunning after a real bug.

**Files or modules likely involved:** `src/features/ml_prep.py`; a separate Alibaba GPU 2020 feature configuration beside `src/features/feature_config.py` (Google configuration unchanged; to confirm); the Task 6 pipeline; new tests.

**Tests and verification:** Leakage test on the feature matrix; a test that only the final step reads the test split; a check that final outputs come from the frozen manifest.

**Expected outputs or artifacts:** The decision manifest; model configuration or artifacts; final-test tables for all policies; final-test metadata.

**Acceptance criteria:**
1. ML and Hybrid are evaluated on validation, and the selection uses train and validation only.
2. All decisions are recorded in the locked manifest before the test runs.
3. The final test runs exactly once and is the only source of final Alibaba GPU 2020 numbers; no tuning follows it.
4. Memory is reported first; CPU is labeled average-usage sizing, not peak-safe sizing; no GPU or any-resource metric.
5. 7a and 7b are complete by the end of day 6.

**Risks and limitations:** Short histories limit ML gains; any rerun after a real bug must be documented openly. The day-5 manifest lock is the tightest point in the schedule (section 5.3).

**Pull-request boundary:** Two PRs: (a) 7a features, models and Hybrid on validation; (b) 7b the decision manifest and final test. The final test never runs before the manifest is locked; the schedule locks it on day 5 so the test runs on day 6.

**Handoff:** The locked manifest and final-test tables go to Task 11a for final verification, then to Task 11b.

---

### Task 8. Alibaba 2018 Optional Adapter Demonstration or Full Integration Decision

**Priority and status:** Priority 2 · Optional · Not on the critical path.

**What this task builds:** An adapter-only demonstration: the existing `Alibaba2018Adapter` run through the Task 1 framework on the Alibaba 2018 sample, producing validated instance-level canonical output and metadata, plus a documented scope decision.

**Purpose:** Shows that the canonical interface accepts a second Alibaba source format, without claiming a recommendation result the dataset cannot support.

**Dataset scope:** Alibaba Cluster Trace 2018 only. Never mixed with Alibaba GPU 2020.

**Prerequisites:** Tasks 1–7 and Task 11a complete; Alibaba 2018 is attempted only after the complete Alibaba GPU 2020 result. Existing Alibaba 2018 sample data.

**Can run in parallel:** Yes, with Task 9 and Task 11b. It never runs alongside Task 7 and never blocks an Alibaba GPU 2020 issue.

**Work to complete:**
1. Run the existing adapter through the new framework and confirm unchanged behavior.
2. Produce validated instance-level canonical output and metadata.
3. Record the decision on fuller integration (see the recommendation below).
4. Only if time permits after Priority 1: the framework §9.3 0.2.0 gaps (status-based validity, unit unification for CPU request and usage, chunked loading of the full `batch_instance`).

**Design and decisions required:** Scope: adapter-only demonstration versus fuller integration. The feasibility findings show only shared task-name or DAG signatures in sampled jobs, which is template evidence, not identity, so no recurrence key exists and none may be invented.

**Recommendation:** **Adapter-only demonstration.** Do not attempt a full next-occurrence pipeline. If even the demonstration does not fit, defer it and report it as retained at 0.1.0.

**Files or modules likely involved:** `src/adapters/alibaba.py`, `tests/test_alibaba_adapter.py`, `scripts/build_external_canonical_samples.py`.

**Tests and verification:** Existing Alibaba 2018 tests pass; validated output passes 0.2.0 validation with no recurrence fields populated.

**Expected outputs or artifacts:** Validated instance-level sample and metadata; a short scope statement for the final report.

**Acceptance criteria:** The report states exactly one outcome: demonstrated (adapter-only), partially integrated (with the gaps listed), or deferred. No next-occurrence or recommendation claim is made.

**Risks and limitations:** Source-specific units and status-blind validity at 0.1.0; full-table loading needs chunking.

**Pull-request boundary:** One PR, only if pursued.

**Handoff:** The scope statement (demonstrated, partial or deferred) goes to Task 11b.

---

### Task 9. Google Subset Leakage-Safe Target and Split Correction

**Priority and status:** Priority 3 · Separate, lower-priority Google-only issue · Not on the critical path and not part of the required end-of-period boundary; needed for final, leakage-safe Google results.

**What this task builds:** A corrected Google Notebook 04 that assigns splits before building targets (if isolation is adopted), regenerated Google split, target and baseline artifacts and metadata, a valid final-evaluation step in place of the empty Notebook 05, and a rerun Google final evaluation.

**Purpose:** Google targets are built before split assignment (F1); 104 of 330 validation targets fall in the test period (F3); the notebook contradicts itself on isolation (F5). Final Google numbers must be leakage-safe.

**Dataset scope:** Google Cluster Data 2019 Kaggle subset only.

**Prerequisites:**
- Team approval of the target-isolation rule.
- PR #70 cleanup only if the Google profile value `target_split_isolation` changes.
- Technically independent of Tasks 1–8, but scheduled only after the required Alibaba GPU 2020 path is complete (never on day 1), so it does not take capacity from it.

**Can run in parallel:** Yes, with Tasks 7 and 8. It never blocks an Alibaba GPU 2020 issue.

**Work to complete:**
1. **Decision:** approve whether Google targets become split-isolated (recommended).
2. **Correction:** build targets after split assignment; validation and test targets that would cross a split become unavailable.
3. **Leakage-safe selection:** rerun Request, Mean, P90, P95 and P99 and the validation selection; record the before/after comparison (the analysis expects P99 with `min_runs = 1` to remain selected, with the any-resource rate moving from 21.95% to 18.30%).
4. **Artifacts:** regenerate `data/processed/google_subset_v1/` outputs and `metadata.json`.
5. **Final evaluation:** replace the 0-byte Notebook 05 with a valid final-evaluation notebook, and rerun the Google ML, Hybrid and final test on the corrected artifacts through the existing Google track.
6. **Test reconciliation:** explain and fix the `test_google_train_target_nulls_are_preserved` discrepancy (1,463 vs 1,801).
7. **Preservation:** no other Google behavior changes. Filtering failed or killed records (F7) and removing repeated multi-machine rows (F8) are separate decisions, not part of this task unless approved separately.

**Design and decisions required:** The Google target-isolation rule, and whether F7 and F8 are raised as separate decisions.

**Files or modules likely involved:** `pipelines/google_subset/04_splitAndBaselines.ipynb`, `pipelines/google_subset/05_evaluateRecommendations.ipynb`, `data/processed/google_subset_v1/`, `tests/test_google_canonical_contract.py`, and the Google entry in `config/dataset_capabilities.json` (only `target_split_isolation`, if adopted).

**Tests and verification:** A test that no validation or test target comes from another split; all Google tests pass, including the target-null test; separate review from any Alibaba PR.

**Expected outputs or artifacts:** Regenerated Google artifacts and metadata, a before/after selection table, corrected Google final-test results.

**Acceptance criteria:**
1. No Google target crosses a split (if adopted).
2. The full suite passes with no failures.
3. Earlier Google numbers are marked superseded.
4. No Alibaba or shared target-builder code changes.

**Risks and limitations:** Corrected numbers differ from earlier reported Google results; validation populations shrink.

**Pull-request boundary:** Two Google-only PRs: (a) target and split correction with regenerated validation artifacts; (b) final Google evaluation. Never combined with Alibaba work.

**Handoff:** Corrected Google results, or a documented decision not to apply the correction, go to Task 11b.

---

### Task 10. Azure VM Future Integration

**Priority and status:** Priority 4 (lowest) · Deferred · Not on the critical path.

**What this task builds (in the future):** A determination of whether Azure can support a valid TraceAdvisor experiment, then, only if it can, an upgraded Azure adapter and evaluation. In the current sequence it builds nothing; the existing adapter and tests stay unchanged and keep passing.

**Purpose:** Keeps Azure as an available future path. It is deferred by priority, not excluded.

**Dataset scope:** Azure public VM.

**Prerequisites:** Completion of Priority 1; a resolved V1/V2 dataset identity. Not scheduled within the deadline, and no Azure implementation is part of the six-day scope.

**Can run in parallel:** Not applicable now; no work is scheduled.

**Work to complete (future):**
1. Resolve the V1/V2 identity of the available data (the sample matches V1, 2017).
2. Assess recurrence: whether any identity supports next-occurrence targets.
3. Assess resource semantics: CPU readings, memory (observed memory is not populated today), capacity buckets.
4. Decide whether a valid experiment exists; if so, plan adapter and evaluation work as new tasks.

**Not done now:** no Azure adapter code changes, no Azure integration, no Azure next-occurrence evaluation.

**Design and decisions required:** V1/V2 identity and resource semantics, before any code.

**Files or modules likely involved:** `src/adapters/azure_vm.py`, `tests/test_azure_vm_adapter.py`, `data/raw/azure/` (contents to confirm).

**Tests and verification:** Now: existing Azure tests pass in every regression run. Future: to be defined.

**Expected outputs or artifacts:** Now: a future-work statement in the final report. Future: a feasibility decision.

**Acceptance criteria:** The final report records Azure as future work with its priority and the open questions.

**Risks and limitations:** Azure may not support next-occurrence evaluation at all.

**Pull-request boundary:** None now. Future work gets its own tasks.

**Handoff:** A future-work statement (priority and open questions) goes to Task 11b.

---

### Task 11. Final Cross-Dataset Reporting, Reproducibility and Project Completion

This task has two issues. **11a** is required within the deadline and ends the Alibaba GPU 2020 critical path. **11b** is the final report and closes the project.

#### Task 11a. Alibaba GPU 2020 Artifact, Metadata and Test Verification

**Priority and status:** Priority 1 · Required within the deadline · End of the critical path.

**What this task builds:** An artifact manifest with checksums for the Alibaba GPU 2020 canonical, split and target, validation-evaluation, decision-manifest and final-test artifacts; a verification step that re-validates the artifacts, their metadata and the final result; a full automated regression and test-suite run; a fresh-environment reproduction of the required path; README and runbook instructions for that path. ("Test verification" here means the automated test suite and data checks; the locked final-test evaluation itself is Task 7b.)

**Purpose:** Proves the completed Alibaba GPU 2020 result, including ML, Hybrid and the final test, is correct and reproducible from documented inputs by the end of day 6.

**Dataset scope:** Alibaba GPU 2020. Existing Google, Alibaba 2018 and Azure tests are run as regressions only.

**Prerequisites:**

```text
Task 2
→ Task 3
→ Task 4
→ Task 6
→ Task 7a
→ Task 7b
→ Task 11a
```

Manifest and verification tooling can be prepared early against fixtures and intermediate artifacts. **Final artifact, metadata, checksum and result verification starts only after Task 7b completes the locked final test.**

**Can run in parallel:** Tooling preparation runs alongside Tasks 4, 6 and 7. The final verification does not run in parallel with the final test; it follows it.

**Work to complete:**
1. **Artifact manifest:** paths, checksums, code commit, source checksums (from Task 2) and the generating command for every required artifact, including the locked decision manifest and the final-test tables.
2. **Artifact and metadata checks:** every canonical view re-validated against the Alibaba GPU 2020 profile; metadata counts (per exclusion reason, rejection reason, split and target status) match the artifacts; the count report differences are explained; the final-test tables trace to the locked decision manifest, and the manifest predates the final-test run.
3. **Test suite:** the full `pytest` suite passes. The only allowed failure is the existing `test_google_train_target_nulls_are_preserved`, documented as owned by Task 9.
4. **Reproduction:** a fresh environment from `requirements.txt` plus the documented data setup reproduces the required artifacts within stated tolerance.
5. **Documentation:** README and runbook steps for the required Alibaba GPU 2020 path.

**Design and decisions required:** Reproduction tolerance; manifest format.

**Files or modules likely involved:** `scripts/verify_data_setup.py`, a manifest or verification script under `scripts/` (to confirm), `README.md`, `requirements.txt`.

**Tests and verification:** Manifest checksums recomputed and matched; validation of every artifact; full test suite; clean-environment run.

**Expected outputs or artifacts:** The artifact manifest, a verification report, the runbook.

**Acceptance criteria:**
1. Final verification ran after the Task 7b final test completed.
2. All manifest checksums match the regenerated artifacts, including the decision manifest and final-test tables.
3. Every artifact passes validation, and its metadata counts match.
4. The final-test result comes from the locked manifest, and the test split was read once.
5. The full regression and test suite passes except the one documented Google failure.
6. The fresh-environment reproduction succeeds.

**Risks and limitations:** Full Alibaba GPU 2020 runs need substantial memory and disk; reproduction time may be long. Final verification falls on day 6 after the final test, so the tooling must be ready beforehand.

**Pull-request boundary:** One PR.

**Handoff:** The verified manifest and the verified final Alibaba GPU 2020 result go to Task 11b.

#### Task 11b. Final Cross-Dataset Report and Project Completion

**Priority and status:** Final · Required for project completion · After the required path; not part of the end-of-period boundary.

**What this task builds:** A reporting script that regenerates every final table and figure from frozen artifacts; per-dataset final results; a contract-comparison table; the final reproducibility manifest extended to all final artifacts; final README and runbook.

**Purpose:** Turns the frozen results into report-ready, reproducible outputs, and closes the project.

**Dataset scope:** Google and Alibaba GPU 2020 results; Alibaba 2018 and Azure as scope statements.

**Prerequisites:** Task 11a; Task 7 (final Alibaba GPU 2020 test); Task 9 (corrected Google results) or an explicit documented decision to keep the earlier Google results; Tasks 8 and 10 decisions. The reporting script can be built earlier on validation artifacts.

**Can run in parallel:** Script development runs alongside Tasks 7–9; the final tables wait for them.

**Work to complete:**
1. **Results:** separate per-dataset tables and figures from each dataset's frozen final test:
   - Google: full-workload occurrence CPU and memory peaks, all policies, any-resource metrics where valid;
   - Alibaba GPU 2020: role-level memory (primary, `gb`) and CPU (lifetime average, `percent_of_vcpu`, labeled "average-usage sizing, not peak safety"); no any-resource or GPU metric.
2. **Contract-comparison table:** modeling unit, scope, aggregation, units, target isolation and evaluated resources per dataset; no score ranking.
3. **Limitations:** selection bias from eligibility rules, low sensor coverage on multi-instance roles, the roughly 50-day telemetry window, same-second targets, CPU average semantics, Google subset scale, Alibaba 2018 and Azure scope (evidence document §5).
4. **Reproducibility:** the Task 11a manifest extended to final artifacts; `scripts/verify_data_setup.py` covering both datasets; fresh-environment run from `requirements.txt`.
5. **Documentation:** README and runbook updates; the completion checklist (section 8).

**Design and decisions required:** Final table layout.

**Files or modules likely involved:** `scripts/report_summary.py` (extended), `reports/eval/` (new dataset subfolders, to confirm), `README.md`, `requirements.txt`, `scripts/verify_data_setup.py`.

**Tests and verification:** Every reported number traces to a frozen artifact; the reporting script regenerates all tables; the full `pytest` suite passes; a clean-environment run reproduces the artifacts within tolerance.

**Expected outputs or artifacts:** Final per-dataset tables and figures, the contract-comparison table, the limitations section, the release manifest, the runbook.

**Acceptance criteria:**
1. No combined or cross-dataset accuracy ranking, and no numeric CPU comparison between datasets.
2. Every Alibaba GPU 2020 CPU figure carries the average-usage label.
3. Reproduction succeeds and the manifest is published.

**Risks and limitations:** Readers may still compare numbers across datasets, so labeling must be explicit.

**Pull-request boundary:** Two PRs: (a) reporting script and generated tables; (b) final reproducibility manifest and documentation.

**Handoff:** Final report chapters, the presentation and the release.

---

## 5. Dependency and parallel-work plan

### 5.1 Dependency table

Issues are picked up by whichever team member is available, in priority order, once their prerequisites are met.

| Issue | Prerequisites | When it can start | Needs PR #70 cleanup merged | Needs GPU 2020 canonical artifacts | Critical path |
|---|---|---|---|---|---|
| PR #70 cleanup | — | Immediately (plan author) | — | No | Yes |
| 2 Data setup and loading | Raw data access | **Immediately** | No | No | Yes |
| 1 Adapter framework | PR #70 cleanup | **Immediately**, on the cleanup branch | To merge | No | Yes |
| 4 Targets (fixtures) | PR #70 cleanup | **Immediately**, on the cleanup branch | To merge | No | Yes |
| 5 Evaluator | PR #70 cleanup | **Immediately**, on the cleanup branch | To merge | No | Yes (before 6) |
| 3 GPU 2020 adapter | PR #70 cleanup, 1, 2 | After 1 and 2 merge (fixtures once the Task 1 result and linkage interfaces are agreed) | Yes | Produces them | Yes |
| 4 Targets (full run) | 3 | After Task 3 artifacts exist | Yes | **Yes** | Yes |
| 6 Baselines and validation | 4, 5 | Fixtures after 5's interface; full run after 4 | Yes | **Yes** | Yes |
| 7a ML and Hybrid validation | 4 tables; 6 for selection | Day 4, once Task 4 tables exist | Yes | **Yes** | Yes |
| 7b Locked manifest and final test | 6, 7a | Manifest day 5; final test day 6 | Yes | **Yes** | Yes |
| 11a Verification | 2 → 3 → 4 → 6 → 7a → 7b | Tooling early; final verification on day 6, after the 7b final test completes | Yes | **Yes** | Yes (end) |
| 8 Alibaba 2018 demonstration | Tasks 1–7 and 11a complete | After the complete Alibaba GPU 2020 result (after 11a), if time remains | Yes | No | No |
| 9 Google correction | Team approval; required path complete | After 11a, if time remains; never day 1 | Only if the profile value changes | No | No |
| 10 Azure | Priority 1 complete | Not scheduled (future) | — | — | No |
| 11b Final report | 11a, 7; 9 or a documented decision; 8 and 10 decisions | After 7 | Yes | **Yes** | No |

**Summary**
- **Can start immediately:** the PR #70 cleanup and Task 2. Tasks 1, 4 (fixtures) and 5 can start immediately on top of the cleanup branch.
- **Require the PR #70 cleanup merged** before they merge: Tasks 1, 3, 4, 5, 6, 7, 8, 11a and 11b.
- **Require completed Alibaba GPU 2020 canonical artifacts:** Task 4's full run, Tasks 6, 11a, 7 and 11b.
- **On the critical path:** PR #70 cleanup, Tasks 1, 2, 3, 4, 5 (before 6), 6, 7a, 7b and 11a.

### 5.2 Critical path

**Main path (all required by the end of day 6):**

PR #70 cleanup
→ shared adapter framework (Task 1) and data loading (Task 2)
→ Alibaba GPU 2020 adapter and canonical artifacts (Task 3)
→ shared targets (Task 4) and evaluator (Task 5)
→ baseline validation (Task 6)
→ machine-learning and Hybrid validation (Task 7a)
→ locked decision manifest (Task 7b)
→ final-test evaluation (Task 7b)
→ final verification and reporting (Task 11a, after the 7b final test completes, plus the Alibaba GPU 2020 result tables and limitations)

**Integration dependency order:**

```text
PR #70 follow-up
→ Task 1 shared multi-view adapter framework
→ Task 2 verified Alibaba GPU 2020 data loading
→ Task 3 Alibaba GPU 2020 adapter and canonical artifacts
→ Task 4 shared targets and evaluation
```

Task 3 needs the PR #70 follow-up, Task 1 and Task 2. Task 2 has no code dependency on the other two and starts on day 1.

**Verification dependency order:**

```text
Task 2
→ Task 3
→ Task 4
→ Task 6
→ Task 7a
→ Task 7b
→ Task 11a
```

Task 11a tooling is prepared early; its final verification of the completed result runs only after Task 7b.

**Responsibility boundary for the adapter work:**
- **PR #70 follow-up:** generic schema, capability, example and profile-driven validation only (`docs/planning/github_issues/pr70_schema_followup_review.md`).
- **Task 1:** the multi-view adapter framework, rejected output, provenance metadata and the linkage-validation interface.
- **Task 2:** verified source tables, explicit schemas, preserved file order and stable `source_row_number`.
- **Task 3:** Alibaba GPU 2020 joins, identity construction, parent-field inheritance, full instance-to-parent linkage, exclusions, aggregation and the canonical artifacts.

**Early work with synthetic fixtures.** The target-builder (Task 4) and evaluator (Task 5) code and tests, the Task 6 baseline generalization and the Task 11a verification tooling can be developed from day 1 with synthetic canonical data. **Their full execution waits for the Alibaba GPU 2020 artifacts** from Task 3.

**After the required result:** Task 8 (Alibaba 2018 adapter-only demonstration), then Task 9 (Google correction), then Task 10 (Azure future work). Task 11b (cross-dataset report) follows.

### 5.3 Six-day schedule

The project has exactly six working days. The schedule is issue-based: four team members pick up the highest-priority unblocked issue as they become free. No issue belongs to a fixed person except the PR #70 cleanup, which is owned by the plan author.

| Day | Issues worked on | Issues that can run in parallel | Expected outputs | Blocking dependencies |
|---|---|---|---|---|
| 1 | PR #70 cleanup and review; Task 2 (data setup and source loader); Task 1 (shared adapter framework); Tasks 4 and 5 (fixture tests on synthetic canonical data) | Tasks 1, 2, 4 (fixtures) and 5 (fixtures) alongside the cleanup review | PR #70 cleanup under review; agreed adapter result and linkage-validation interfaces; list of all blocking decisions; loader skeleton; framework skeleton | Tasks 1, 4 and 5 cannot merge before the cleanup merges. Task 3 cannot start until the result and linkage interfaces are agreed. **Risk:** any unresolved blocking decision found today must be settled on day 1 |
| 2 | Task 1 (complete and test); Task 2 (checksum verification, source loading); Task 3 (fixtures, joins, identity, timestamps); Tasks 4, 5 and 6 (target builder, evaluator, baseline generalization on fixtures) | Tasks 1, 2, 3 (fixtures), 4, 5 and 6 (fixtures) | PR #70 cleanup ready for merge; Task 1 tested; Task 2 verified tables with stable `source_row_number` | Task 3 integration needs Tasks 1 and 2 merged. **Risk:** raw data download or checksum failure blocks Task 3 |
| 3 | Task 3 (framework integration; exclusion rules, resource aggregation, rejected output, metadata; first canonical artifacts); Task 4 (split, history and target logic on fixtures); Tasks 5 and 6 (evaluator and baseline contract tests) | Tasks 3, 4, 5 and 6; Task 11a verification tooling | First canonical Alibaba GPU 2020 artifacts; Task 4 fixture logic complete; Tasks 5 and 6 contract tests passing (Task 5 merged) | Full runs of Tasks 4 and 6 wait for Task 3 artifacts. **Risk:** memory pressure on the instance–sensor join |
| 4 | Task 3 (full-data artifact generation, population checks); Task 4 (full-data splits, history, next-occurrence targets); Task 6 (evaluator and baselines connected to full artifacts); Task 7a (validation-based ML and Hybrid implementation) | Tasks 3 (checks), 4, 6 and 7a; Task 11a tooling | Task 3 merged with full canonical artifacts and count report; Task 4 train, validation and test tables; baselines running on full data | Task 6 full run waits for the Task 4 tables; Task 7a training waits for the same tables. **Risk:** adapter, target and evaluator integration failures must be resolved the same day |
| 5 | Task 6 (complete baseline validation, memory-first selection); Task 7a (ML model selection on validation; Hybrid construction and validation); Task 7b (create and review the locked decision manifest; final-test preparation and leakage checks) | Tasks 6, 7a and 7b preparation; Task 11a tooling | Task 6 merged (baseline validation result); Task 7a validation results for ML and Hybrid; **decision manifest reviewed and locked** | The manifest must be locked before the test split is read. **Risk:** the manifest depends on Task 6 and Task 7a finishing the same day; any slip moves directly into day 6 |
| 6 | Task 7b (locked final test, run exactly once); then Task 11a final verification of the completed result (artifact, metadata, checksum, result and reproducibility verification; required regression and integration tests); Alibaba GPU 2020 final result tables and limitations | Before the final test: Task 11a tooling checks on the existing artifacts. After the final test: Task 11a final verification, then the result tables | **Final Alibaba GPU 2020 test result**; verified manifest and metadata; test suite passing (except the documented Google failure); final Alibaba GPU 2020 tables and limitations | The final test needs the locked manifest from day 5. **Task 11a final verification starts only after the 7b final test completes.** Task 8 starts only after all required work is complete. **Google correction and Azure implementation are not scheduled before the required final result** |

**Assumptions:**
- the raw Alibaba GPU 2020 data is available on day 1;
- four team members work in parallel;
- the PR #70 cleanup is ready for merge by day 2;
- no new design decisions are required after day 1;
- enough compute, memory and storage are available for full-data runs;
- tests and data checks pass without major blockers.

**Highest-risk dependencies:**
1. Day 2–3: raw data and full-table loading; everything after Task 2 depends on it.
2. Day 3–4: full-data adapter and target runs (memory and run time).
3. Day 5: baseline selection, ML and Hybrid validation, and the locked manifest all finish on the same day.
4. Day 6: the final test runs once, after the manifest is locked; it cannot be rerun to recover time. Task 11a final verification must then finish the same day, so its tooling must be ready before day 6.

### 5.4 Completion boundary at the end of day 6

The six working days are the fixed project deadline. The following are **all required by the end of day 6**:
1. PR #70 cleanup ready or merged.
2. Shared adapter framework complete (Task 1).
3. Alibaba GPU 2020 data loading verified (Task 2).
4. Alibaba GPU 2020 canonical artifacts generated and validated (Task 3).
5. Shared splits, history and next-occurrence targets working (Task 4).
6. Dataset-aware evaluator working (Task 5).
7. Alibaba GPU 2020 baseline validation completed (Task 6).
8. Alibaba GPU 2020 machine-learning evaluation completed (Task 7a).
9. Alibaba GPU 2020 Hybrid evaluation completed (Task 7a).
10. Decision manifest locked before test evaluation (Task 7b).
11. Alibaba GPU 2020 final test run exactly once (Task 7b).
12. Final artifact, metadata, checksum, regression and test verification completed, after the final test (Task 11a).

The completed Alibaba GPU 2020 result includes ML, Hybrid and the final test. A validation-only result does not meet this boundary.

**Lower-priority work after the required Alibaba GPU 2020 result:**
1. Alibaba 2018 adapter-only demonstration (Task 8).
2. Google subset correction (Task 9).
3. Azure future work (Task 10), with no implementation now.

**Preliminary versus final results:**
- Preliminary (intermediate): all validation results (Task 6, Task 7a) and any Google result produced before Task 9. Baseline validation alone is an intermediate result.
- Final: the Task 7b final test for Alibaba GPU 2020, and the Google final test on corrected artifacts once Task 9 is done, each from a frozen decision manifest.

---


## 6. Dataset boundaries

**Priority order**
1. **Alibaba GPU 2020:** required primary integration.
2. **Alibaba 2018:** optional adapter-only demonstration.
3. **Google subset correction:** separate lower-priority work.
4. **Azure VM:** lowest-priority future work.

**Boundaries**
- Google Cluster Data 2019 is the reference pipeline.
- Alibaba GPU 2020 is the required second full integration.
- Alibaba 2018 is optional, if time permits.
- Azure is a future, lower-priority task, not excluded.
- Google and Alibaba GPU 2020 results are not one combined accuracy ranking.
- Alibaba GPU 2020 CPU is lifetime-average sizing, not peak-safe sizing.
- Alibaba GPU 2020 memory is primary.
- GPU fields are retained, but GPU-resource recommendation and GPU-resource evaluation are out of scope. CPU and memory ML, Hybrid, and final-test evaluation remain required in Task 7.
- No recurrence is invented for Alibaba 2018.
- The Google correction remains separate from Alibaba work.
- Azure code remains unchanged during the current implementation sequence.

---

## 7. Explicit exclusions

This plan does not include:
- PR #70 schema and validation correction work (planned separately);
- changes to the frozen schema or adapter framework design;
- Google changes inside Alibaba tasks;
- Azure adapter code changes in the current implementation;
- GPU-resource recommendation and GPU-resource evaluation. CPU and memory ML, Hybrid, and final-test evaluation remain required in Task 7;
- invented Alibaba 2018 recurrence;
- reuse of the fitted Google model on Alibaba data;
- hundreds of micro-tasks.

---

## 8. Final project completion checklist

**Alibaba GPU 2020 (Priority 1; every item is required by the end of day 6)**
- [ ] PR #70 schema follow-up ready or merged.
- [ ] Adapter framework complete (Task 1).
- [ ] Alibaba GPU 2020 data verified with checksums (Task 2).
- [ ] Alibaba GPU 2020 canonical artifacts generated and validated (Task 3).
- [ ] Shared splits, history and targets validated, with leakage tests passing (Task 4).
- [ ] Dataset-aware evaluator merged with Google outputs unchanged (Task 5).
- [ ] Alibaba GPU 2020 baselines evaluated on validation (Task 6).
- [ ] Alibaba GPU 2020 ML evaluation completed (Task 7a).
- [ ] Alibaba GPU 2020 Hybrid evaluation completed (Task 7a).
- [ ] Decision manifest locked before test evaluation (Task 7b).
- [ ] Alibaba GPU 2020 final test run exactly once from the locked manifest (Task 7b).
- [ ] Final artifact, metadata, checksum, regression and test verification completed after the final test: manifest, checksums, fresh-environment run, test suite passing except the documented Google failure (Task 11a).

**Lower-priority work**
- [ ] Alibaba 2018 decision documented: demonstrated, partial or deferred (Task 8).
- [ ] Google correction handled separately (Task 9) or explicitly documented as not applied.
- [ ] Azure future work and its priority documented (Task 10).

**Project completion**
- [ ] Final cross-dataset report completed, with separate per-dataset results and no combined ranking (Task 11b).
- [ ] Final reproducibility manifest covering all final artifacts (Task 11b).
- [ ] Final project limitations documented (Task 11b).
