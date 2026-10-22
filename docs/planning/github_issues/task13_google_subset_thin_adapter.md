# [P2] Task 13: Google Subset Thin Adapter (No Pipeline Change)

**Labels:** `area-adapters`, `dataset-google`, `priority-medium`

**Owner:** Unassigned

**Priority:** Priority 2 · Architecture consistency · Not on the Alibaba GPU 2020 critical path. Small, and can start at any time.

---

## Objective

Make the Google subset enter TraceAdvisor through the same shared adapter contract as every other dataset, without changing the Google pipeline.

A thin `GoogleSubsetAdapter` maps the existing corrected Google occurrence artifacts to a validated canonical `occurrence` view through `BaseDatasetAdapter.adapt()`. Google's precomputed next-occurrence targets are attached afterwards by a small helper outside the adapter, as framework §3 requires: *"Google's precomputed targets are referenced from the existing artifacts, not computed by an adapter."*

After this task, Google, Alibaba GPU 2020, Alibaba 2018 and Azure all produce an `AdapterResult` validated against their own capability profile. The project can then claim one common adapter contract with no exceptions.

## What This Task Builds

- `GoogleSubsetAdapter` (`src/adapters/google_subset.py`). Its `to_canonical` maps:
  - identity;
  - time fields;
  - current requests;
  - current peaks.

  It does **not** map `actual_*` targets or `split`.
- A small helper that joins Google's precomputed targets onto the validated view by `occurrence_id`, outside the adapter.
- Tests showing that the adapter output plus the attached targets equals the existing Google canonical contract view.
- A one-sentence design-doc update.

## What This Task Does Not Build

- Any change to the Google notebooks (`pipelines/google_subset/`) or to the Google artifacts.
- Google splits, history or targets through the shared target builder (Task 4).
- Any change to the shared framework (`base.py`, `validation.py`), the canonical schema or the Google capability profile.
- Any Alibaba GPU 2020, Alibaba 2018 or Azure change.

## Current Project State

- **No Google adapter exists.** `docs/design/adapter_framework.md` §1 and §9.1 say *"No production adapter is needed."*
- **The mapping already exists, but only in a test.** `tests/test_google_canonical_contract.py` has `build_google_canonical_contract_view()`. It maps the corrected N04 artifacts:
  - `recurrence_key` → `workload_id`, `recurrence_key`;
  - `occurrence_key` → `occurrence_id`;
  - `execution_start_time_us` → `start_time_us`;
  - `occurrence_end_time_us` → `end_time_us`;
  - requests and peaks in `ncu` / `normalized`;
  - `target_*_next_occurrence_peak_*` → `actual_cpu`, `actual_memory`.

  It then calls `validate_canonical_frame` directly.
- **Why it can't simply become an adapter:** `validate_adapter_output` rejects populated target-builder columns (`split`, `actual_*`, target statuses). See `_reject_target_builder_columns` in `src/adapters/validation.py`. The test calls `validate_canonical_frame` directly and so skips the adapter checks: uniqueness, dataset ID, profile identity and recurrence-key rules.
- **Profile:** `GOOGLE_CAPABILITIES` (`src/canonical/schema.py`) is already at 0.2.0:
  - `supported_record_levels = ("occurrence",)`, `evaluation_record_level = "occurrence"`;
  - `has_cpu_average = false`, `has_cpu_peak = true`;
  - `cpu_unit = ncu`, `memory_unit = normalized`;
  - `target_split_isolation = false`.

  No profile change is needed.
- **Artifacts:** `data/processed/google_subset_v1/{train,val,test}_occurrences.parquet` and `metadata.json`.

## Design

```
Google notebooks (unchanged) → {train,val,test}_occurrences.parquet
        │
        ▼
GoogleSubsetAdapter().adapt(occurrences)
   to_canonical: identity, time, request, peak   (no actual_*, no split)
   → validate_adapter_output (full adapter checks against GOOGLE_CAPABILITIES)
   → AdapterResult (single "occurrence" view + metadata)
        │
        ▼
attach_google_precomputed_targets(view, occurrences)
   join on occurrence_id: actual_cpu, actual_memory (+ units); split taken from the source file
```

- **The adapter is single-view.** It uses the existing `adapt()` path. It doesn't need the Task 1 multi-view features (`adapt_sources`, rejected output, linkage).
- **Targets stay outside the adapter.** This keeps the framework rule unchanged: adapters never emit splits or targets. Google keeps its precomputed reference targets.
- **Input:** the three split files concatenated, without a `split` column, so that `occurrence_id` stays unique across the subset. The split each row came from is recorded by the attach helper, not by the adapter.

## Relationship to Other Tasks

| Item | Relationship |
|---|---|
| Task 1 (PR #91) | Uses only the existing single-view `adapt()` and `AdapterResult`. Works before or after Task 1 merges. If Task 1 makes `views` the same on every path, the Google result gets `views = {"canonical": ...}` like the other single-view adapters |
| Task 4 | Not used. Google targets remain the precomputed reference targets |
| Task 10 | Task 10 regenerates the Google artifacts. Re-run this adapter's tests on the corrected artifacts afterwards. If Task 10 renames source columns, update the mapping here |
| Task 12 | Can state that every dataset enters through the shared adapter contract |

## Dependencies

- None. The existing `adapt()`, `GOOGLE_CAPABILITIES` and the Google artifacts are enough.

## Parallel Work

- Can run in parallel with every task. It touches no Alibaba GPU 2020 code.

## Blocks

- None.

## Detailed Implementation Tasks

### 1. Adapter

- [ ] Create `src/adapters/google_subset.py` with `GoogleSubsetAdapter(BaseDatasetAdapter)`:
  - `adapter_name = "google_subset"`;
  - `capabilities = GOOGLE_CAPABILITIES`.
- [ ] Implement `to_canonical` by moving the mapping from `build_google_canonical_contract_view()`, **except** the four `actual_cpu` / `actual_memory` (+ unit) lines.
- [ ] Keep `validity_status = "valid"` and `exclusion_reason` null (framework §9.1).
- [ ] Export the adapter from `src/adapters/__init__.py`.

### 2. Precomputed-target helper

- [ ] Add `attach_google_precomputed_targets(view, occurrences)`:
  - join `target_cpu_next_occurrence_peak_ncu` → `actual_cpu` and `target_memory_next_occurrence_peak_normalized` → `actual_memory` on `occurrence_id`, with units `ncu` / `normalized`;
  - join `split` from the source file.
- [ ] Keep nulls exactly as they are. The last occurrence of a recurrence has no target.
- [ ] Return a new frame; never modify the adapter's view.

### 3. Design doc

- [ ] `docs/design/adapter_framework.md` §1 and §9.1: change "No production adapter is needed" to "A thin `GoogleSubsetAdapter` maps the corrected artifacts. Precomputed targets are attached outside the adapter."
- [ ] While editing `adapter_framework.md`, update the outdated status lines (found in the Task 1 review):
  - `adapter_framework.md` §1–§2: "the Python implementation is still 0.1.0" → implemented in 0.2.0 (PR #86).
  - `adapter_framework.md` §11: change the "Issue 3 / Issue 4" boundaries to Task 1 / Task 3.
  - `canonical_workload_schema.md` §2 and §15 item 1: "code still 0.1.0" → 0.2.0.
- [ ] No contract change.

## Required Tests

New test module `tests/test_google_subset_adapter.py`:

- [ ] `GoogleSubsetAdapter().adapt()` passes `validate_adapter_output` on the concatenated train, validation and test artifacts.
- [ ] Adapter output contains no populated `split`, `actual_*` or target-status columns.
- [ ] Row count and `occurrence_id` match the source, and `occurrence_id` is unique.
- [ ] Adapter output plus `attach_google_precomputed_targets` equals `build_google_canonical_contract_view()` on every shared column, with null counts identical.
- [ ] The source frame is not modified.
- [ ] Skip, rather than fail, when the artifacts aren't present locally (same behavior as the existing contract test).

Regression:

- [ ] `tests/test_google_canonical_contract.py` passes **unchanged**. It stays as the independent reference check.
- [ ] Adapter regression modules pass: `tests/test_adapter_contract.py`, `tests/test_alibaba_adapter.py`, `tests/test_azure_vm_adapter.py`, `tests/test_external_adapter_integration.py`.

## Acceptance Criteria

1. Google occurrences go through `BaseDatasetAdapter.adapt()` and pass the full adapter validation against `GOOGLE_CAPABILITIES`.
2. The adapter emits no splits or targets. Precomputed targets are attached outside it, with nulls preserved.
3. Adapter output plus attached targets equals the existing Google canonical contract view.
4. No change to the Google notebooks, the Google artifacts, the shared framework, the schema or the profile.
5. No new test failures.

## Expected Outputs

- `src/adapters/google_subset.py`.
- `tests/test_google_subset_adapter.py`.
- Updates to `docs/design/adapter_framework.md` (Google adapter sentence and status lines) and the status lines in `docs/design/canonical_workload_schema.md`.
- No new data artifacts.

## Data Leakage Controls

- The adapter reads only current-occurrence fields. Targets are copied from the existing artifacts and not recomputed.
- Google's known cross-split target behavior (`target_split_isolation = false`) is unchanged here. It is corrected separately in Task 10.

## Schema and Adapter Boundaries

- Follows framework §3: the adapter owns mapping; it does not own splits or targets.
- Google-specific logic (episode reconstruction, aligned-window summing) stays in the notebooks and does not move into the adapter or into shared code (framework §8).

## Unresolved Decisions

| ID | Decision | Recommendation |
|---|---|---|
| D-1 | Should the existing contract test later import the adapter instead of its own mapping? | No. Keep the test's own mapping as an independent check of the adapter |
| D-2 | Should Google later run through the shared target builder (Task 4) as a cross-check? | Out of scope. Consider it after Task 4 and Task 10, as an optional validation of the shared builder against the reference pipeline |

## Risks

- **Column renames in Task 10** would break the mapping. This is caught by the equivalence test.
- **The adapter's extra checks may expose an existing artifact issue** that `validate_canonical_frame` alone did not catch (for example a duplicate `occurrence_id` across splits). If so, report it to Task 10; don't work around it in the adapter.

## Pull-Request Boundary

One small PR: the adapter, the target helper, the new test module and the design-doc updates. No notebook, artifact, framework or schema changes.

## Not in This Issue

- Google pipeline corrections (Task 10).
- Google splits, history or targets through the shared target builder.
- Any Alibaba GPU 2020, Alibaba 2018 or Azure work.

## References

- `tests/test_google_canonical_contract.py` (`build_google_canonical_contract_view`)
- `src/adapters/base.py`, `src/adapters/validation.py` (`_reject_target_builder_columns`)
- `src/canonical/schema.py` (`GOOGLE_CAPABILITIES`)
- `docs/design/adapter_framework.md` §1, §3, §8, §9.1
- `docs/design/canonical_workload_schema.md` §3, §10.3
- `docs/planning/github_issues/task10_google_subset_corrections_and_rerun.md`
