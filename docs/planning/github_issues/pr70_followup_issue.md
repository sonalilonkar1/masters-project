# [P0] PR #70 Follow-up: Canonical Schema 0.2.0 and Generic Validation

**Labels:** `area-implementation`, `priority-high`

---

## Objective

Correct and extend the canonical foundation introduced by PR #70 so that it matches the frozen schema 0.2.0 design. This is shared schema, capability, example and generic validation work only. It is **not** the Alibaba GPU 2020 integration; it prepares the shared contract that later adapters use.

Version 0.2.0 extends 0.1.0 without removing or renaming any existing field, capability flag, record level, unit or validation rule.

## Responsibility Split

- **This issue:** schema version 0.2.0, generic `role_occurrence` support, generic `role_key` validation, profile-driven identity validation, capability fields and consistency rules, resource and GPU field validation, generic recurrence and vocabulary validation, the capability registry, canonical examples, and schema and validation tests.
- **Task 1** provides multiple validated views, the rejected output, provenance metadata and the linkage-validation interface.
- **Task 2** provides verified source loading and a stable `source_row_number`.
- **Task 3** constructs the Alibaba GPU 2020 identities, copies parent fields onto instance rows and runs full instance-to-parent linkage.

**Profile-driven validation** means validation based on what a dataset profile declares: its capability fields and its `supported_record_levels`. It checks identity values already present on rows. It never constructs Alibaba GPU 2020 identity fields.

## Dependencies

- None. The frozen design documents are complete; no further design approval is needed.

## Blocks

- **Task 1** must merge after this issue.
- **Task 3** needs the Alibaba GPU 2020 profile and generic validation.
- **Task 4** and **Task 5** need the target-status vocabulary and capability fields before they merge.

## Files in Scope

Only these files change:

- `src/canonical/schema.py`
- `src/adapters/validation.py`
- `config/dataset_capabilities.json`
- `examples/canonical_records.jsonl`
- schema tests: `tests/test_canonical_schema.py` (tests added only) and a new schema test module
- validation tests: a new validation test module

## Tasks

### Schema Version and Record Levels

- [ ] Set `SCHEMA_VERSION = "0.2.0"` in `src/canonical/schema.py`.
- [ ] Add `role_occurrence` to `RECORD_LEVELS`.

### Generic `role_occurrence` and `role_key` Validation

- [ ] Add a `role_occurrence` uniqueness rule keyed on `role_key` in `_validate_record_uniqueness`.
- [ ] Reject a `role_occurrence` frame with no `role_key` column, any null `role_key`, or duplicate `role_key` values.
- [ ] Allow several role rows of one job (same `occurrence_id`, different `role_key`).

### Profile-Driven Identity Validation

- [ ] For any profile whose `supported_record_levels` includes `role_occurrence`: require a non-null `role_key` on `role_occurrence` and `instance` rows, and a non-null `instance_id` on `instance` rows.
- [ ] Require `event_time_us` on `instance` rows only when the profile declares `instance_event_time_semantics = parent_job_submission`.
- [ ] Leave Alibaba 2018 and Azure unchanged: their profiles declare neither, so their key and timestamp behavior stays as today.
- [ ] Validate keys only; construct nothing.

### Units and Resource Fields

- [ ] Add `percent_of_vcpu` and `percent_of_gpu` to `ALLOWED_RESOURCE_UNITS`.
- [ ] Add `requested_gpu`, `observed_gpu` and `peak_gpu_memory` to `RESOURCE_VALUE_FIELDS`, so unit, non-negative and finite checks apply.
- [ ] Add no GPU capability flag and no GPU gating; GPU evaluation stays out of scope.

### Capability Fields and Consistency Rules

- [ ] Extend `DatasetCapabilities` with the schema §7 and §10.2 fields, all with defaults and placed after `notes`, so the existing positional profile calls keep working:
  - `has_cpu_average`, `has_cpu_peak`, `has_memory_average`, `has_memory_peak`
  - `recurrence_key_origin`
  - `observed_cpu_semantics`, `peak_cpu_semantics`, `observed_memory_semantics`, `peak_memory_semantics`
  - `cpu_target_semantics`, `memory_target_semantics`
  - `time_semantics`, `instance_event_time_semantics`
  - `cpu_unit`, `memory_unit`
  - `telemetry_window`
  - `supported_record_levels`, `evaluation_record_level`, `evaluation_mode`
  - `allowed_exclusion_reasons`
  - `any_resource_metric_valid`, `target_split_isolation`
- [ ] Resolve the `has_*` defaults from `supports_observed_cpu` and `supports_observed_memory` when they are not given (a `None` sentinel resolved in `__post_init__`).
- [ ] Enforce the consistency rules: `supports_observed_cpu` equals `has_cpu_average or has_cpu_peak`, and the same for memory. `supports_cpu` never implies a CPU peak.
- [ ] Validate profile declarations against their vocabularies: record levels, semantics, `recurrence_key_origin`, `evaluation_mode`, and `cpu_unit` / `memory_unit`.
- [ ] Make `to_dict()` return lists for sequence fields so it compares equal to the JSON.

### Average Versus Peak Gating

- [ ] Reject a populated `peak_cpu` when `has_cpu_peak` is false, and the same for `observed_cpu`, `observed_memory` and `peak_memory` with their flags.
- [ ] Keep the existing `supports_observed_*` gates.

### Vocabulary Validation

Each check applies only when its column is present.

- [ ] `resource_scope`: `full_workload`, `task_role_per_instance`, `instance`, `job_total`.
- [ ] `request_aggregation_method`: `sum_over_executions`, `none`, `descriptive_job_total`.
- [ ] `observed_aggregation_method`: `aligned_window_sum_then_maximum`, `maximum_over_instances`, `none`.
- [ ] `cpu_validity_status` and `memory_validity_status`: the existing validity vocabulary.
- [ ] `exclusion_reason`: null, or in the profile's `allowed_exclusion_reasons`.
- [ ] `cpu_target_status` and `memory_target_status`: `available`, `no_next_occurrence`, `next_occurrence_in_other_split`, `next_occurrence_ineligible_resource`, `unsupported_resource`.
- [ ] `record_level` must be in the profile's `supported_record_levels` when that field is set.

### Generic Recurrence Validation

- [ ] When `recurrence_key_origin = none`, `recurrence_key` must be null.
- [ ] Otherwise, on `occurrence` and `role_occurrence` rows, `recurrence_key` may be null only where `exclusion_reason = no_recurrence_key`.
- [ ] Do not apply this rule to instance rows; they are checked later through the Task 1 linkage interface.

### Adapter-Output Rule

- [ ] `validate_adapter_output` rejects populated `split`, `actual_cpu`, `actual_memory`, `cpu_target_status` and `memory_target_status`.
- [ ] The Google contract view calls `validate_canonical_frame` directly, so its precomputed targets stay valid.

### Capability Registry

- [ ] Update the Google profile: `has_cpu_average = false`, `has_cpu_peak = true`, `has_memory_average = false`, `has_memory_peak = true`, `recurrence_key_origin = constructed`, and the other schema §10.3 Google values.
- [ ] Update the Alibaba 2018 profile with its schema §10.3 values.
- [ ] Leave the Azure Python profile unedited; it takes the defaults.
- [ ] Add `ALIBABA_GPU_2020_CAPABILITIES` (`alibaba_gpu_v2020`) with the schema §10.3 values: average CPU supported, CPU peak unsupported, memory average and peak supported, `official_with_role`, `percent_of_vcpu` / `gb`, record levels `role_occurrence` and `instance`, the 14 exclusion reasons in order, `any_resource_metric_valid = false`, `target_split_isolation = true`, `instance_event_time_semantics = parent_job_submission`.
- [ ] Add the new profile to `DEFAULT_CAPABILITY_REGISTRY`.
- [ ] Update `config/dataset_capabilities.json` in the same commit: version `0.2.0`, every new field on all four profiles, Azure with its resolved defaults.

### Canonical Examples

- [ ] Bump the three existing rows in `examples/canonical_records.jsonl` to `0.2.0` with no other change.
- [ ] Append four hand-written Alibaba GPU 2020 rows: a grouped role row, a fallback role row (`no_recurrence_key`), a missing-CPU role row, and an instance row whose parent is the grouped role row.
- [ ] Write the identity values by hand; nothing is constructed or linked by code.

### Schema Tests

- [ ] Version `0.2.0` in code, JSON and every example.
- [ ] `role_occurrence` is accepted as a record level.
- [ ] Positional `DatasetCapabilities` construction still works, and the `has_*` flags resolve correctly.
- [ ] Consistency-rule violations are rejected.
- [ ] `to_dict()` without `notes` equals the JSON for all four profiles.
- [ ] Profile values match schema §10.3; Azure holds the resolved defaults.
- [ ] Populated `peak_cpu` is rejected for Alibaba GPU 2020; populated `observed_cpu` is rejected for Google.
- [ ] New units are accepted; unknown units, unitless GPU values and negative GPU values are rejected; null GPU values stay null.
- [ ] Scope, aggregation, per-resource validity, exclusion-reason and target-status vocabularies are enforced; absent columns pass.
- [ ] A `record_level` outside `supported_record_levels` is rejected; invalid profile declarations are rejected.
- [ ] The instance event-time rule applies to Alibaba GPU 2020 only.
- [ ] Every example row validates.

### Validation Tests

- [ ] Duplicate, missing and null `role_key` on `role_occurrence` rows are rejected; different roles of one job pass.
- [ ] Null `role_key` or `instance_id` on instance rows is rejected for a profile that declares `role_occurrence`.
- [ ] Duplicate `instance_id` without `source_seq_no` is rejected.
- [ ] Recurrence rule: fallback rows with `no_recurrence_key` pass; grouped rows with a null key fail; Alibaba 2018 and Azure keep the existing `recurrence unsupported` message.
- [ ] Adapter-emitted `split`, `actual_*` and target statuses are rejected; the Google contract view still validates.
- [ ] Existing PR #70 error messages are unchanged.

## Confirmed Choices

These were left open by the design documents and are confirmed (evidence in `docs/planning/github_issues/pr70_schema_followup_review.md` §8.2):

- `telemetry_window` is a string.
- Alibaba 2018 `cpu_unit` is null, because its CPU request and usage units differ; its `memory_unit` is `alibaba_memory_source_normalized`.
- A null `supported_record_levels` means no restriction.
- An empty `allowed_exclusion_reasons` means every `exclusion_reason` must be null.
- Defaults: `recurrence_key_origin = none`, `any_resource_metric_valid = true`, `target_split_isolation = false`.
- Non-null `role_key` and `instance_id` on instance rows are enforced only for profiles that declare `role_occurrence`.

## Acceptance Criteria

- [ ] The schema version is `0.2.0` in code, JSON and examples.
- [ ] `role_occurrence` and `role_key` are supported; duplicate, missing or null `role_key` on role rows is rejected.
- [ ] The new units and GPU fields validate; missing GPU values stay null.
- [ ] Capability defaults preserve the existing Google, Alibaba 2018 and Azure profiles; positional profile calls still work; the consistency rules are enforced.
- [ ] The Alibaba GPU 2020 profile exists, and a populated `peak_cpu` is rejected for it.
- [ ] The profile-driven identity and instance event-time checks apply only to profiles that declare them; Alibaba 2018 and Azure behavior is unchanged.
- [ ] The Python registry and the JSON configuration match exactly.
- [ ] All examples pass validation.
- [ ] All existing PR #70 tests pass without edits.
- [ ] No new test failure; the only permitted failure is the existing `test_google_train_target_nulls_are_preserved`.
- [ ] No adapter, `base.py`, notebook, script or downstream pipeline code is changed.

## Expected Output

- Updated `src/canonical/schema.py`
- Updated `src/adapters/validation.py`
- Updated `config/dataset_capabilities.json`
- Updated `examples/canonical_records.jsonl`
- New schema and validation tests

## Not in This Issue

- Multiple validated views, `AdapterResult` changes, rejected output, provenance metadata, multi-table preparation and the linkage-validation interface (Task 1).
- Source loading and `source_row_number` construction (Task 2).
- The Alibaba GPU 2020 adapter, identity construction, parent inheritance, linkage, exclusion processing and resource aggregation (Task 3).
- Splits, history, targets, the evaluator, baselines, machine learning and Hybrid (Tasks 4 to 7).
- Alibaba 2018 or Azure adapter changes, Google notebook or pipeline changes, and GPU-resource recommendation or evaluation.

## Implementation Order

1. `schema.py`: version, record level, units, GPU fields and vocabulary constants.
2. `schema.py`: `DatasetCapabilities` fields, defaults, consistency rules, profile vocabulary checks and `to_dict()`.
3. Profiles and registry: Google, Alibaba 2018, new Alibaba GPU 2020; Azure unedited.
4. `config/dataset_capabilities.json`, in the same commit as steps 1 to 3.
5. New checks in `validate_canonical_frame`, after the existing checks.
6. `validation.py`: `role_occurrence` uniqueness, profile-driven identity checks, recurrence rule and adapter-output rule.
7. Canonical examples.
8. Schema and validation tests.
9. Focused tests, then the PR #70 regression modules, then the full suite.

## Risks

- New checks must run after the existing checks, so existing error messages that tests match still appear first.
- The Python registry and the JSON must change together, or `test_capability_json_matches_python_registry` fails.
- Any saved 0.1.0 canonical sample fails exact version validation and must be regenerated (handled in Task 1).

## Pull-Request Boundary

- One PR, limited to the files in scope.

## Handoff

- **Task 1** builds the multi-view framework on the 0.2.0 validation.
- **Task 3** uses the Alibaba GPU 2020 profile and the generic validation.
- **Tasks 4 and 5** use the target-status vocabulary and capability fields.

## References

- `docs/design/canonical_schema_implementation_plan.md`: the PR #70 follow-up plan
- `docs/planning/github_issues/pr70_schema_followup_review.md`: exact symbols, test IDs, contradictions and confirmed choices
- `docs/design/canonical_workload_schema.md`: §2, §4.1, §5, §6, §7, §8, §9, §10 and §11
- `docs/design/adapter_framework.md`: §7.1 and §7.2
- `docs/planning/data_integration_tasks.md`: responsibility boundary with Tasks 1 to 3

## Owner

@meghanakoti
