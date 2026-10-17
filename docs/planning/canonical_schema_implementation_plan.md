# PR #70 Follow-up: Canonical Schema and Validation Corrections

**Status:** Implementation plan. No code has been changed.
**Design sources (frozen):**
- `docs/design/canonical_workload_schema.md` (specification; § numbers refer to it)
- `docs/design/adapter_framework.md`
- `docs/design/canonical_schema_design_decisions.md`

**Consistent with:**
- `docs/design/pr70_schema_followup_review.md` (the detailed review: exact symbols, test IDs, contradictions and the confirmed choices)
- `docs/planning/data_integration_tasks.md` (Tasks 1–11 and the six-day schedule)

This pull request corrects and extends the canonical foundation introduced by PR #70 so that it matches the frozen schema 0.2.0 design. It is **not** the Alibaba GPU 2020 integration. It only prepares the shared canonical contract and the generic validation that later adapters will use.

---

## 1. Relationship to PR #70

PR #70 (merged into `main` at `a0b3c77`) introduced:
- the initial canonical schema (`SCHEMA_VERSION = "0.1.0"`, record levels, units, resource fields);
- dataset capability profiles for Google, Alibaba 2018 and Azure;
- adapter-output validation (`validate_adapter_output`, record uniqueness, capability gating);
- canonical examples (`examples/canonical_records.jsonl`);
- initial adapter contract tests.

The design was then finalized for Google (reference), Alibaba GPU 2020 (required second integration), Alibaba 2018 (optional) and Azure (deferred). This follow-up corrects and extends the shared components so they express those decisions. It extends 0.1.0 without removing or renaming any existing field, flag, record level, unit or validation rule (§2).

---

## 2. Pull-request scope

Only these files change:
- `src/canonical/schema.py`
- `src/adapters/validation.py`
- `config/dataset_capabilities.json`
- `examples/canonical_records.jsonl`
- schema-related tests (`tests/test_canonical_schema.py`, extended; a new schema test module)
- validation-related tests (a new validation test module)

The follow-up covers only:
- schema version `0.2.0`;
- generic `role_occurrence` support;
- generic `role_key` uniqueness and non-null validation on `role_occurrence` rows;
- generic profile-driven identity validation;
- capability fields and consistency rules;
- resource and GPU field validation;
- generic recurrence and vocabulary validation;
- capability registry updates;
- canonical examples;
- schema and validation tests.

**Profile-driven validation** means validation based on what a dataset profile declares (its capability fields and `supported_record_levels`). It checks identity values that are already present on rows. It never constructs Alibaba GPU 2020-specific identity fields.

**Boundary with later tasks** (`docs/planning/data_integration_tasks.md`):
- **Task 1** provides multiple validated views, the rejected output, provenance metadata and the linkage-validation interface that accepts role and instance views.
- **Task 2** provides verified source loading and a stable `source_row_number`.
- **Task 3** constructs the Alibaba GPU 2020 identities (`role_key`, `instance_slot_key`, `instance_attempt_index`, `instance_id`), copies parent fields onto instance rows, and implements full instance-to-parent linkage through the Task 1 interface.

```text
PR #70 follow-up
→ Task 1 shared multi-view adapter framework
→ Task 2 verified Alibaba GPU 2020 data loading
→ Task 3 Alibaba GPU 2020 adapter and canonical artifacts
→ Task 4 shared targets and evaluation
```

Task 2 has no code dependency on this follow-up or on Task 1 and starts on day 1.

---

## 3. Required corrections to PR #70

| Area | Correction | Spec |
|---|---|---|
| Version | `SCHEMA_VERSION = "0.2.0"` | §2 |
| Record levels | Add `role_occurrence` | §4.1 |
| Identity | Add `role_key`; `role_occurrence` rows are unique on it, and a missing or null `role_key` is rejected | §4.1, §5 |
| Profile-driven identity | For any profile whose `supported_record_levels` includes `role_occurrence`: non-null `role_key` on `role_occurrence` and `instance` rows, and non-null `instance_id` on `instance` rows. Keys are validated, not constructed | §5.4; framework §7.2 |
| Instance time | `event_time_us` is required on instance rows **only when** the dataset profile declares `instance_event_time_semantics = parent_job_submission`. Alibaba GPU 2020 uses this rule; Alibaba 2018 and Azure keep their existing timestamp and validation behavior | §7 |
| Units | Add `percent_of_vcpu` and `percent_of_gpu` | §6.2 |
| GPU fields | Add `requested_gpu`, `observed_gpu`, `peak_gpu_memory` to the resource fields, so unit, non-negative and finite checks apply. No GPU capability flag; no GPU evaluation | §6.1, §6.4 |
| Scope and aggregation | Add `resource_scope`, `request_aggregation_method` and `observed_aggregation_method` with their vocabularies | §8 |
| Vocabularies | Per-resource validity (`cpu_validity_status`, `memory_validity_status`), exclusion reasons (against the profile's `allowed_exclusion_reasons`), target statuses; each checked only when its column is present | §9, §11 |
| Record level and semantics | `record_level` must be in the profile's `supported_record_levels`; profile record-level, semantics, recurrence-origin, evaluation-mode and unit declarations use their vocabularies | §7, §10.2; framework §7.2 |
| Recurrence | `recurrence_key` must be null when `recurrence_key_origin = none`; otherwise, on `occurrence` and `role_occurrence` rows, it may be null only where `exclusion_reason = no_recurrence_key`. Instance rows are checked later through the Task 1 linkage interface | Framework §7.2 |
| Adapter output | `validate_adapter_output` rejects populated `split`, `actual_*` and target-status values; the Google contract view, which uses `validate_canonical_frame` directly, is unaffected | Framework §3, §7.2 |
| Capabilities | Extend `DatasetCapabilities` with the §7 and §10.2 fields, all with defaults placed after `notes`, so existing profiles keep working | §10.2 |
| Average vs peak | Add `has_cpu_average`, `has_cpu_peak`, `has_memory_average`, `has_memory_peak`. Defaults resolve from `supports_observed_*`, so Azure and Alibaba 2018 keep accepting their current peak values. Enforce the §10.2 consistency rules | §10.2 |
| `peak_cpu` gating | `peak_cpu` is rejected when `has_cpu_peak` is false (and the average and memory equivalents). The existing `supports_observed_*` gates stay | §9.2, §10 |
| New profile | Add `ALIBABA_GPU_2020_CAPABILITIES` (`alibaba_gpu_v2020`) to the registry | §10.3 |
| Registries | Update the Python registry and `config/dataset_capabilities.json` together; `to_dict()` outputs lists so it compares equal to the JSON | §2 |
| Examples | Bump existing examples to 0.2.0; add hand-written Alibaba GPU 2020 role, fallback-key, missing-CPU and instance examples. Their identity values are written by hand; nothing is constructed or linked by code | §15 |
| Tests | Add schema and validation tests (section 8) | §15 |

**Implementation notes**
- New checks run **after** the existing checks, so existing error messages that tests match still appear first.
- The rule that every validated row needs `event_time_us` or `start_time_us` is unchanged.
- `validate_adapter_output` keeps validating one frame at a time. No cross-view or instance-to-parent check is added.
- Choices the documents left open, confirmed on 2026-10-17 (review §8.2 gives the evidence):
  - `telemetry_window` is a string;
  - Alibaba 2018 `cpu_unit` is `null`, because its CPU request and usage units differ; its `memory_unit` is `alibaba_memory_source_normalized`;
  - `supported_record_levels = null` means no restriction;
  - an empty `allowed_exclusion_reasons` means every `exclusion_reason` must be null;
  - defaults: `recurrence_key_origin = none`, `any_resource_metric_valid = true`, `target_split_isolation = false`;
  - the non-null `role_key` and `instance_id` rules on instance rows apply only to profiles that declare `role_occurrence`, so Alibaba 2018 and Azure behavior is unchanged.

---

## 4. Dataset compatibility requirements

- **Google:** the pipeline, notebooks and existing Google contract behavior stay unchanged. Its capability values stay the same; average flags are set to false because its artifacts have no occurrence-level averages.
- **Alibaba 2018:** adapter behavior stays unchanged, including its units, validity, `source_seq_no` instance key, and existing timestamp validation. Its profile doesn't declare `instance_event_time_semantics` or `role_occurrence`, so the instance event-time rule and the profile-driven identity checks don't apply.
- **Azure:** adapter code stays unchanged. Its JSON entry receives only the schema version and the default metadata required for registry consistency. Its Python profile isn't edited. Its profile doesn't declare `instance_event_time_semantics` or `role_occurrence`, so its existing timestamp validation is unchanged.
- **Reference adapter:** no code change; it emits `0.2.0` through `SCHEMA_VERSION`, and its tests pass unedited.
- **Alibaba GPU 2020:** only its capability profile and examples are added. The adapter isn't included. Its profile declares `instance_event_time_semantics = parent_job_submission` and `role_occurrence`, so its instance rows require `event_time_us`, `role_key` and `instance_id`.
- **Google target-null discrepancy:** `test_google_train_target_nulls_are_preserved` already fails on the local artifacts (1,463 vs 1,801). It is a separate issue and is not fixed here.

---

## 5. Explicit non-goals

This pull request does not include:
- `src/adapters/base.py`;
- multiple named validated views or any `AdapterResult` change (Task 1);
- separate role and instance views (Task 1);
- rejected-output support or routing (Tasks 1 and 3);
- adapter provenance and rejection metadata (Task 1);
- multi-table preparation (Task 1);
- the linkage-validation interface (Task 1);
- data loading and joins (Tasks 2 and 3);
- `source_row_number` construction (Task 2);
- the Alibaba GPU 2020 adapter (Task 3);
- Alibaba GPU 2020 identity construction: `role_key`, `instance_slot_key`, `instance_attempt_index`, `instance_id` (Task 3);
- Alibaba GPU 2020 parent-field inheritance and instance-to-parent linkage (Task 3);
- dataset-specific exclusion processing or resource aggregation (Task 3);
- Alibaba 2018 adapter changes;
- Azure adapter changes;
- splits;
- history;
- next-occurrence targets;
- the target builder;
- evaluator or metrics changes;
- baselines, machine learning and Hybrid logic;
- Google notebook or pipeline changes;
- GPU-resource recommendation or GPU-resource evaluation;
- generated Alibaba GPU artifacts.

---

## 6. Implementation order

1. Update `schema.py`: version, record level, units, GPU fields and vocabulary constants.
2. Update `schema.py`: `DatasetCapabilities` fields, defaults, consistency rules, profile vocabulary checks and `to_dict()`.
3. Update the Python capability profiles and registry (Google, Alibaba 2018, new Alibaba GPU 2020; Azure unedited).
4. Update `config/dataset_capabilities.json` in the same commit as steps 1–3, so the registry test keeps passing.
5. Add the new checks to `validate_canonical_frame`, after the existing ones.
6. Update `validation.py`: `role_occurrence` uniqueness, the profile-driven identity checks, the recurrence rule on `occurrence` and `role_occurrence` rows, and the adapter-target rule. No linkage helper.
7. Update canonical examples.
8. Add the schema and validation tests.
9. Run focused tests and PR #70 regression tests:
   - focused: the schema and validation test modules;
   - regression: `tests/test_adapter_contract.py`, `tests/test_alibaba_adapter.py`, `tests/test_azure_vm_adapter.py`, `tests/test_external_adapter_integration.py`, `tests/test_google_canonical_contract.py`;
   - then the full `pytest` suite.

Steps 5 and 6 can run in parallel once step 3 exists.

---

## 7. Acceptance criteria

1. The schema version is `0.2.0` in code, JSON and examples.
2. `role_occurrence` and `role_key` are supported; duplicate, missing or null `role_key` on role rows is rejected.
3. The new units and GPU fields validate; missing GPU values stay null.
4. Capability defaults preserve the existing Google, Alibaba 2018 and Azure profiles; existing positional profile calls still work; the consistency rules are enforced.
5. The Alibaba GPU 2020 profile exists, with average CPU supported, CPU peak unsupported and memory peak supported, and a populated `peak_cpu` is rejected.
6. The profile-driven identity checks require a non-null `role_key` and `instance_id` on instance rows only for profiles that declare `role_occurrence`. `event_time_us` is required on instance rows only when the profile declares `instance_event_time_semantics = parent_job_submission` (Alibaba GPU 2020). Alibaba 2018 and Azure instance rows keep their existing timestamp, key and validation behavior.
7. The Python and JSON registries match exactly.
8. All examples pass validation.
9. Existing Google, Alibaba 2018, Azure and reference-adapter tests pass without edits. The suite's only failure is the existing Google target-null test.
10. No adapter, `base.py` or downstream pipeline code is changed. No linkage helper, identity construction or multi-view support is added.

---

## 8. Required tests

The full test list with IDs is in `docs/design/pr70_schema_followup_review.md` §7. In summary:

**Schema tests**
- version 0.2.0 in code, JSON and examples;
- `role_occurrence` accepted;
- positional profile construction, has-flag defaults and consistency rules;
- `to_dict()` equals the JSON for all four profiles;
- profile values for Google, Alibaba 2018, Alibaba GPU 2020 and the Azure defaults;
- `peak_cpu` rejected for Alibaba GPU 2020; `observed_cpu` rejected for Google;
- new units accepted; unknown units, unitless or negative GPU values rejected; null GPU values stay null;
- scope, aggregation, per-resource validity, exclusion-reason and target-status vocabularies;
- `record_level` outside `supported_record_levels` rejected; invalid profile declarations rejected;
- the instance event-time rule for Alibaba GPU 2020, and no change for Alibaba 2018 and Azure;
- every example row validates.

**Validation tests**
- duplicate, missing and null `role_key` on `role_occurrence` rows rejected; different roles of one job pass;
- null `role_key` or `instance_id` on instance rows rejected for a profile that declares `role_occurrence`;
- duplicate `instance_id` without `source_seq_no` rejected;
- the recurrence rule: fallback rows with `no_recurrence_key` pass; grouped rows with a null key fail; Alibaba 2018 and Azure keep the existing message;
- adapter-emitted `split`, `actual_*` and target statuses rejected; the Google contract view still validates;
- existing PR #70 error messages unchanged.

No test in this follow-up covers instance-to-parent linkage. Linkage-interface tests on synthetic views belong to Task 1, and Alibaba GPU 2020 identity and linkage tests belong to Task 3.

**Test gate**
- All existing PR #70 tests pass, unedited.
- All new schema and validation tests pass.
- No new test failure is allowed; the only permitted pre-existing failure is `test_google_train_target_nulls_are_preserved`.
- No Alibaba GPU 2020 adapter, multi-view or parent-linkage implementation is required.

---

## 9. Definition of done

The follow-up is done when:
1. Every correction in section 3 is implemented, within the files in section 2.
2. The acceptance criteria in section 7 hold.
3. The tests in section 8 exist and pass, and the test gate holds.
4. The confirmed choices listed in section 3 are recorded in the pull-request description.
5. Nothing in section 5 is implemented.

It does **not** require the instance-to-parent linkage helper, Alibaba GPU 2020 identity construction, or any Alibaba GPU 2020 adapter behavior.

---

## 10. Later work

The remaining work is planned as issues in `docs/planning/data_integration_tasks.md`:
- Task 1: the shared multi-view adapter framework, rejected output, provenance metadata and the linkage-validation interface;
- Task 2: Alibaba GPU 2020 data setup and reproducible source loading;
- Task 3: the Alibaba GPU 2020 adapter, identity construction, full instance-to-parent linkage and canonical artifacts;
- Tasks 4–7: shared splits, history and targets, the evaluator, baselines, ML, Hybrid and the final test;
- Task 11a: verification of the completed Alibaba GPU 2020 result;
- Tasks 8–10: optional Alibaba 2018, the Google correction and deferred Azure work.

Detailed adapter steps, raw-data counts, exclusion rules and individual adapter test cases belong in those tasks, not in this plan.
