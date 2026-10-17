# PR #70 Follow-up Review: Canonical Schema 0.1.0 → 0.2.0

**Date:** 2026-10-17
**Status:** Review only. No source code, tests, configuration or other documents were changed.
**Authoritative contract (frozen):**
- `docs/design/canonical_workload_schema.md` (the specification; § numbers below refer to it unless another document is named)
- `docs/design/adapter_framework.md` (cited as "framework §")
- `docs/design/canonical_schema_design_decisions.md` (cited as "D-nn")

**Plan reviewed against the contract:** `docs/planning/canonical_schema_implementation_plan.md` (cited as "plan §").

**Code inspected (as merged at `a0b3c77`):**
- `src/canonical/schema.py`
- `src/adapters/base.py`, `src/adapters/validation.py`, `src/adapters/reference.py`
- `src/adapters/alibaba.py`, `src/adapters/azure_vm.py` (only where they touch the schema)
- `config/dataset_capabilities.json`
- `examples/canonical_records.jsonl`
- `tests/test_canonical_schema.py`, `tests/test_adapter_contract.py`, `tests/test_alibaba_adapter.py`, `tests/test_azure_vm_adapter.py`, `tests/test_external_adapter_integration.py`, `tests/test_google_canonical_contract.py`

**Current test baseline (run on 2026-10-17):** 81 passed, 1 failed. The failure is `tests/test_google_canonical_contract.py::test_google_train_target_nulls_are_preserved`, which is a known, separate Google issue. The 53 tests in the five PR #70 schema and adapter modules all pass. The project virtual environment `mastersvenv` has no `pytest`, so the suite was run with the system Python 3.10 interpreter.

The review keeps three kinds of work apart:
- **Required follow-up corrections** (sections 2–7, 9–10): needed to bring the shared canonical code to the frozen 0.2.0 contract.
- **Optional improvements** (section 11.2): useful, but not required by the contract.
- **Later dataset-specific work** (section 11.3): belongs to later issues, not to this follow-up.

### Responsibility boundary

The PR #70 follow-up contains only shared schema, capability, example and generic validation work:
- schema version `0.2.0`;
- `role_occurrence` as a supported record level;
- generic `role_key` uniqueness and non-null validation for `role_occurrence` rows;
- generic profile-driven identity checks;
- generic recurrence-key validation;
- resource fields and units;
- GPU field vocabulary and unit validation;
- average-versus-peak capability fields;
- capability consistency rules;
- record-level and resource-semantics validation;
- validity, exclusion-reason and target-status vocabularies;
- capability registry updates;
- canonical examples;
- schema and validation tests.

**Profile-driven validation** means validation based on what a dataset profile declares (its capability fields, such as `has_cpu_peak`, `recurrence_key_origin` and `instance_event_time_semantics`) and on the record levels it declares (`supported_record_levels`). It checks identity values that are already present on rows. It never constructs Alibaba GPU 2020-specific identity fields.

The PR #70 follow-up does **not** include:
- multiple named validated views, or any change to `AdapterResult`;
- separate role and instance views;
- rejected-output routing;
- adapter provenance and rejection metadata;
- multi-table preparation;
- Alibaba GPU 2020 construction of `role_key`, `instance_id`, `instance_attempt_index` or `source_row_number`;
- parent-field inheritance or instance-to-parent linkage;
- dataset-specific exclusion logic;
- dataset-specific resource aggregation.

| Responsibility | PR #70 follow-up | Later task |
|---|---|---|
| Generic `role_occurrence` record level | Yes | — |
| Generic `role_key` uniqueness and non-null validation | Yes | — |
| Generic profile-driven identity validation | Yes | — |
| Multiple validated views | No | Task 1 |
| Rejected output and provenance metadata | No | Task 1 |
| Linkage-validation interface accepting role and instance views | No | Task 1 |
| Alibaba GPU 2020 identity construction | No | Task 3 |
| Alibaba GPU 2020 instance-to-parent linkage | No | Task 3 |
| Alibaba GPU 2020 linkage tests | No | Task 3 |

- **PR #70 follow-up:** generic schema and profile-driven validation only.
- **Task 1** (`docs/planning/data_integration_tasks.md`): the multi-view adapter framework, rejected output, provenance metadata and the linkage-validation interface.
- **Task 3:** the actual Alibaba GPU 2020 identity construction and full instance-to-parent linkage, checked through the Task 1 interface.

Task numbers refer to `docs/planning/data_integration_tasks.md`.

---

## 1. What PR #70 already implements correctly

These parts match the 0.2.0 contract already. Version 0.2.0 extends 0.1.0 without removing or renaming anything (§2, D-02), so all of them stay.

| Area | Where | Why it is already correct |
|---|---|---|
| Core required columns | `CORE_REQUIRED_COLUMNS`, `schema.py:10` | Same six columns in 0.2.0 |
| Record-level, time-basis and validity vocabularies | `RECORD_LEVELS`, `TIME_BASES`, `VALIDITY_STATUSES`, `schema.py:7–9` | The five 0.1.0 levels and both other vocabularies are kept (§4.1, §9.1). Only `role_occurrence` is missing |
| Non-null `workload_id` | `schema.py:96–97` | §5.1. The Alibaba GPU 2020 fallback keys depend on this rule (§5.3, D-05) |
| Event-or-start time on every row | `schema.py:98–99` | Unchanged in 0.2.0 (plan §3 note; D-22 rejected relaxing it) |
| End time at or after start | `schema.py:100–103` | Unchanged |
| Numeric, non-negative values, and a unit from the allowed list on every populated resource value | `schema.py:104–135` | §6.1–6.2. New GPU fields and units only need to be added to the lists |
| Ten capability flags and their gating | `DatasetCapabilities`, `schema.py:30–45`; gates `schema.py:136–211` | §10.1 keeps and still enforces all ten |
| Nulls never zero-filled | No helper fills values | §1, §9.2; covered by `test_missing_optional_value_not_zero_filled` |
| Python registry and JSON kept identical | `test_capability_json_matches_python_registry` | §2 and D-02 depend on this test |
| Evaluator view | `validate_evaluator_view`, `schema.py:212–231` | §12 says evaluator names and rules are unchanged |
| Duplicate-column check, single `dataset_id`, finite resource values | `validate_adapter_output`, `validation.py:66–91` | Framework §7.1 |
| Uniqueness keys for `occurrence`, `instance`, `execution`, `interval` | `_validate_record_uniqueness`, `validation.py:10–64` | Framework §7.1. The `instance` rule already handles Alibaba GPU 2020, because that adapter emits no `source_seq_no` (§5.4, D-21) |
| Adapter base contract | `BaseDatasetAdapter.adapt`, `base.py:38–54` | Framework §4.1: type check, copy, source-mutation check, validation, `AdapterResult` |
| Version constant used everywhere | Reference, Alibaba 2018 and Azure adapters and the Google contract view all write `SCHEMA_VERSION` | Bumping the constant moves every emitter to 0.2.0 with no adapter edit |
| Alibaba 2018 per-resource validity | `alibaba.py:330–380` | Already uses `cpu_validity_status` and `memory_validity_status` with `valid`, `partial` and `invalid`, which is the standard of §9.1 |

---

## 2. What is missing or inconsistent with the frozen 0.2.0 contract

Each gap is **required** unless it is marked otherwise.

| ID | Gap | Current code | Contract |
|---|---|---|---|
| G-01 | Schema version | `SCHEMA_VERSION = "0.1.0"` (`schema.py:6`); JSON `"schema_version": "0.1.0"`; all three example rows at `0.1.0` | `0.2.0` in code, JSON and examples, in one change (§2) |
| G-02 | Record level `role_occurrence` | Missing from `RECORD_LEVELS` | §4.1, D-03 |
| G-03 | `role_occurrence` uniqueness on `role_key` | No rule: levels without a rule are skipped (`validation.py:38–39`), and a missing key column is skipped silently (`validation.py:41–42`) | Unique and non-null `role_key` (§4.1; framework §7.2) |
| G-04 | Units `percent_of_vcpu`, `percent_of_gpu` | Missing from `ALLOWED_RESOURCE_UNITS` | §6.2, D-12 |
| G-05 | GPU resource fields | `requested_gpu`, `observed_gpu`, `peak_gpu_memory` missing from `RESOURCE_VALUE_FIELDS`, so they would escape unit and non-negativity checks | §6.1, §6.4, D-09, D-20. There is no GPU capability flag and no GPU gating |
| G-06 | Average and peak separation | `supports_observed_cpu` / `supports_observed_memory` gate average and peak together (`schema.py:185–197`) | Add `has_cpu_average`, `has_cpu_peak`, `has_memory_average`, `has_memory_peak`; reject `peak_cpu` when `has_cpu_peak = false`, with the average and memory equivalents (§9.2, §10.2, D-10; framework §7.2) |
| G-07 | New capability fields | `DatasetCapabilities` has only the ten flags and `notes` | All §10.2 and §7 fields, each with a default, so existing profiles and positional calls keep working (§10.2, D-02) |
| G-08 | Consistency rules between old flags and new fields | None | `supports_observed_cpu` agrees with `has_cpu_average or has_cpu_peak`, and the same for memory (§10.2) |
| G-09 | Alibaba GPU 2020 profile | Not in the registry or JSON | `alibaba_gpu_v2020` with the §10.3 values |
| G-10 | Google profile values for the new fields | n/a | `has_cpu_average = false`, `has_memory_average = false`, peaks true, `constructed`, and the other §10.3 Google values |
| G-11 | Scope and aggregation vocabularies | None | `resource_scope`, `request_aggregation_method`, `observed_aggregation_method` (§8, D-14) |
| G-12 | Per-resource validity vocabulary | Not checked; only the Alibaba 2018 adapter's own logic produces it | `cpu_validity_status`, `memory_validity_status` checked against `VALIDITY_STATUSES` (§9.1; framework §7.2) |
| G-13 | Exclusion-reason vocabulary | Not checked | `exclusion_reason` is null or in the profile's `allowed_exclusion_reasons` (§9.3, §10.2; framework §7.2) |
| G-14 | Target-status vocabulary | Not checked | `cpu_target_status`, `memory_target_status` checked against the five §11 values |
| G-15 | Record level allowed by the profile | Not checked | `record_level` is in the profile's `supported_record_levels` (framework §7.2) |
| G-16 | Recurrence never invented | Only `supports_recurrence = false` gates `recurrence_key` | `recurrence_key` null exactly when `recurrence_key_origin = none`, or on rows excluded as `no_recurrence_key` (framework §7.2). See contradiction C-03 for instance rows |
| G-17 | Adapters must not emit targets | `supports_targets = true` allows `actual_*` in adapter output | `validate_adapter_output` rejects populated `split`, `actual_*` and target-status values. The Google artifacts are the exception (framework §3, §7.2) |
| G-18 | Instance-row time rule | Not present | `event_time_us` required on `instance` rows **only when** the profile declares `instance_event_time_semantics = parent_job_submission` (§7; plan §3) |
| G-19 | Profile-driven identity validation | `instance_id` and `role_key` may be null; null keys are not checked (`validation.py:44`) | For any profile whose `supported_record_levels` includes `role_occurrence`, a non-null `role_key` on `role_occurrence` and `instance` rows and a non-null `instance_id` on `instance` rows. `workload_id` stays non-null on every row. Keys are validated, not constructed (§5.4; framework §7.2; plan §3). See C-04 |
| G-20 | Instance-to-parent linkage | No check | **Not part of the PR #70 follow-up.** The linkage-validation interface, which accepts the role and instance views, is Task 1. The Alibaba GPU 2020 parent-field inheritance, full linkage and linkage tests are Task 3 (§5.5, D-08; framework §7.2). See the responsibility boundary above |
| G-21 | `to_dict()` output type | `asdict()` would keep tuples, which never equal JSON lists | `to_dict()` returns lists, so the registry test can compare it with the JSON (plan §3) |
| G-22 | Alibaba GPU 2020 examples | None | Role, fallback-key, missing-CPU and instance examples (§2; plan §3) |
| G-23 | Tests for every item above | 0.1.0 tests only | Schema and validation tests (§2; plan §2, §7) |
| G-24 | Record-level and resource-semantics validation of profiles | Profiles carry no record-level or semantics declarations | Each profile's `supported_record_levels` and `evaluation_record_level` use `RECORD_LEVELS`; the per-field semantics, `time_semantics` and `instance_event_time_semantics` use the §7 vocabulary; `recurrence_key_origin` and `evaluation_mode` use the §10.2 vocabularies; `cpu_unit` and `memory_unit` are null or in `ALLOWED_RESOURCE_UNITS` (§7, §10.2) |

---

## 3. Files that require changes

| File | Required change | Reason | Tests required | Dependency |
|---|---|---|---|---|
| `src/canonical/schema.py` | Bump the version; add `role_occurrence`, the two units, three GPU fields, vocabulary constants, the new `DatasetCapabilities` fields with defaults, consistency checks, profile vocabulary checks and list output; update the Google and Alibaba 2018 profiles; add `ALIBABA_GPU_2020_CAPABILITIES` and register it; add the new checks to `validate_canonical_frame` after the existing checks | G-01, G-02, G-04–G-15, G-18, G-21, G-24 | Schema test module (section 7.1); existing `tests/test_canonical_schema.py` unchanged and passing | None. Must land together with the JSON file, because of the registry test |
| `src/adapters/validation.py` | `role_occurrence` uniqueness and non-null `role_key`; the profile-driven identity checks; the recurrence-key rule on evaluation rows; reject adapter-emitted `split`, `actual_*` and target statuses. No linkage helper (Task 1) | G-03, G-16, G-17, G-19 | Validation test module (section 7.2); `tests/test_adapter_contract.py` unchanged and passing | `schema.py` (record level, profile fields, vocabularies) |
| `config/dataset_capabilities.json` | Version `0.2.0`; every new field on all three existing entries; add the `alibaba_gpu_v2020` entry | G-01, G-07, G-09, G-21 | `test_capability_json_matches_python_registry`, unchanged | `schema.py` profile values, in the same commit |
| `examples/canonical_records.jsonl` | Bump rows 1–3 to `0.2.0` with no other change; append the four Alibaba GPU 2020 example rows | G-01, G-22 | Existing `test_examples_validate[0–2]`; new example tests | `schema.py` and `validation.py` |
| `tests/test_canonical_schema.py` | Add tests only; do not edit any existing test function | G-23 | n/a | All of the above |
| New schema test module (plan §2 leaves the name open, for example `tests/test_canonical_schema_v020.py`) | Tests in section 7.1 | G-23 | n/a | `schema.py`, JSON, examples |
| New validation test module (name left open, for example `tests/test_adapter_validation_v020.py`) | Tests in section 7.2 | G-23 | n/a | `validation.py`, examples |

**Files that must not change in this follow-up:**
- `src/adapters/base.py`, `src/adapters/reference.py`, `src/adapters/alibaba.py`, `src/adapters/azure_vm.py`
- `tests/test_adapter_contract.py`, `tests/test_alibaba_adapter.py`, `tests/test_azure_vm_adapter.py`, `tests/test_external_adapter_integration.py`, `tests/test_google_canonical_contract.py`
- notebooks, `scripts/`, data artifacts and the evaluator

`AdapterResult`, multi-view support, rejected output and provenance metadata are in `base.py` and belong to Task 1. No Alibaba GPU 2020 adapter module is created in this follow-up.

The `adapter_version = "0.1.0"` strings in `base.py`, `reference.py` and the two adapters are adapter versions, not the schema version. They stay unchanged.

---

## 4. Exact symbols that require changes

### 4.1 `src/canonical/schema.py`

| Symbol | Line | Change |
|---|---|---|
| `SCHEMA_VERSION` | 6 | `"0.1.0"` → `"0.2.0"` |
| `RECORD_LEVELS` | 7 | Add `"role_occurrence"` |
| `VALIDITY_STATUSES` | 9 | Unchanged; also used for `cpu_validity_status` and `memory_validity_status` |
| `RESOURCE_VALUE_FIELDS` | 11–15 | Append `requested_gpu`, `observed_gpu`, `peak_gpu_memory`. `RESOURCE_UNIT_FIELDS` (line 16) then derives their unit columns automatically |
| `ALLOWED_RESOURCE_UNITS` | 18–28 | Add `percent_of_vcpu`, `percent_of_gpu` |
| New vocabulary constants (names are suggestions; values come from the specification) | after line 28 | Resource scope (§8): `full_workload`, `task_role_per_instance`, `instance`, `job_total`. Request aggregation (§8): `sum_over_executions`, `none`, `descriptive_job_total`. Observed aggregation (§8): `aligned_window_sum_then_maximum`, `maximum_over_instances`, `none`. Target status (§11): `available`, `no_next_occurrence`, `next_occurrence_in_other_split`, `next_occurrence_ineligible_resource`, `unsupported_resource`. Recurrence-key origin (§10.2): `constructed`, `official`, `official_with_role`, `none`. Evaluation mode (§10.2): `full_next_occurrence`, `next_occurrence_memory_peak_cpu_average`, `instance_request_versus_observed`. Resource semantics (§7): `window_peak`, `lifetime_peak`, `lifetime_average`, `instance_peak`, `instance_average`. Target semantics (§7): `next_occurrence_peak`, `next_occurrence_lifetime_average`, `next_occurrence_lifetime_peak`. Time semantics (§7): `first_execution_start`, `job_submission`, `instance_start`. Instance event-time semantics (§7): `parent_job_submission`. Alibaba GPU 2020 exclusion reasons, in rule order (§9.3) |
| `DatasetCapabilities` | 30–45 | Add the fields below, all with defaults and **after** `notes`, so the positional calls at lines 47–61 still work. Add `__post_init__` for the has-flag defaults and the consistency rules. `to_dict()` returns lists for sequence fields |
| `GOOGLE_CAPABILITIES` | 47–51 | Keep the positional arguments; add the §10.3 Google values as keyword arguments |
| `ALIBABA_CAPABILITIES` | 52–56 | Keep the positional arguments; add the §10.3 Alibaba 2018 values as keyword arguments |
| `AZURE_VM_CAPABILITIES` | 57–61 | **No edit.** It gets its new values from the defaults (§3, §10.2; plan §4) |
| `ALIBABA_GPU_2020_CAPABILITIES` (name from plan §3) | new | `dataset_id = "alibaba_gpu_v2020"` with the §10.3 values |
| `DEFAULT_CAPABILITY_REGISTRY` | 62–64 | Add the new profile |
| `validate_canonical_frame` | 80–211 | Append the new checks **after** the existing ones (plan §3 note) |
| `validate_evaluator_view` | 212–231 | No change (§12) |

**New `DatasetCapabilities` fields.** These come from §10.2 and §7 only; no other fields are added.

| Field | Type | Default | Source |
|---|---|---|---|
| `has_cpu_average`, `has_cpu_peak` | bool | Resolve from `supports_observed_cpu` when not given | §10.2; plan §3 |
| `has_memory_average`, `has_memory_peak` | bool | Resolve from `supports_observed_memory` when not given | §10.2; plan §3 |
| `recurrence_key_origin` | str | `"none"` (confirmed, section 8.2) | §10.2 |
| `observed_cpu_semantics`, `peak_cpu_semantics`, `observed_memory_semantics`, `peak_memory_semantics` | str or null | null | §7 |
| `cpu_target_semantics`, `memory_target_semantics` | str or null | null | §7 |
| `time_semantics` | str or null | null | §7, §10.2 |
| `instance_event_time_semantics` | str or null | null | §7, §10.2 |
| `cpu_unit`, `memory_unit` | str or null | null | §10.2 |
| `telemetry_window` | str or null | null | §10.2; plan §3 says string |
| `supported_record_levels` | tuple of str, or null | null, meaning no restriction | §10.2; plan §3 |
| `evaluation_record_level` | str or null | null | §10.2 |
| `evaluation_mode` | str or null | null | §10.2 |
| `allowed_exclusion_reasons` | tuple of str | `()`, meaning every `exclusion_reason` must be null | §10.2; plan §3 |
| `any_resource_metric_valid` | bool | `true` (keeps 0.1.0 evaluator behavior; confirmed) | §10.2, §12 |
| `target_split_isolation` | bool | `false` (keeps 0.1.0 behavior; confirmed) | §10.2, §11 |

Implementation notes for the dataclass:
- The class is `frozen=True`. Resolving the has-flag defaults therefore needs a `None` sentinel and `object.__setattr__` inside `__post_init__`.
- Sequence fields use tuples, because a frozen dataclass needs immutable defaults. `to_dict()` converts them to lists.
- `CanonicalSchemaError` is defined after the dataclass (line 66). Move it above the dataclass, or raise `ValueError`, so `__post_init__` can raise it.

### 4.2 `src/adapters/validation.py`

| Symbol | Line | Change |
|---|---|---|
| `_validate_record_uniqueness` | 10–64 | Add a `role_occurrence` branch keyed on `["role_key"]`. For `role_occurrence` rows, a missing `role_key` column or a null `role_key` is an error, not a skip (lines 41–44 currently skip both) |
| `validate_adapter_output` | 66–96 | After the existing checks: run the profile-driven identity checks (G-19), the recurrence-key rule on evaluation rows (G-16) and the adapter-must-not-emit-targets rule (G-17). Then call `validate_canonical_frame` as now |
| `resource_prefixes` finite check | 83–91 | No required change; see optional improvement O-01 |

No cross-view linkage helper is added here. `validate_adapter_output` keeps validating one frame at a time. The linkage-validation interface that accepts both the role and instance views is Task 1, and the Alibaba GPU 2020 linkage is Task 3.

### 4.3 `config/dataset_capabilities.json`

| Key | Change |
|---|---|
| `schema_version` | `"0.2.0"` |
| `datasets[google_clusterdata2019]` | Add every new field with the §10.3 Google values |
| `datasets[alibaba_clustertrace2018]` | Add every new field with the §10.3 Alibaba 2018 values |
| `datasets[azure_public_vm_v2]` | Add every new field with the **resolved default** values only. The ten existing flags stay unchanged |
| `datasets[alibaba_gpu_v2020]` | New entry with every field |

`notes` stays out of the JSON, as `test_capability_json_matches_python_registry` already expects.

### 4.4 `examples/canonical_records.jsonl`

| Row | Change |
|---|---|
| 1 Google occurrence | `schema_version` → `0.2.0`; nothing else |
| 2 Alibaba 2018 instance | `schema_version` → `0.2.0`; nothing else |
| 3 Azure interval | `schema_version` → `0.2.0`; nothing else |
| 4 (new) Alibaba GPU 2020 grouped role | The role row described in section 5.4 |
| 5 (new) Alibaba GPU 2020 fallback role | The role row of a job without `group` |
| 6 (new) Alibaba GPU 2020 missing-CPU role | Memory-eligible, with CPU missing |
| 7 (new) Alibaba GPU 2020 instance | Audit row whose parent is row 4 |

New rows go **after** row 3, so the existing index-based `test_examples_validate[0–2]` stays valid without an edit.

---

## 5. Required changes by file

### 5.1 `src/canonical/schema.py`

1. **Version and vocabularies.** Make the G-01, G-02, G-04, G-05 and G-11–G-14 changes in section 4.1.
2. **Capability fields.** Add the section 4.1 fields with their defaults, after `notes`.
3. **`__post_init__`.**
   - Resolve `has_cpu_average` and `has_cpu_peak` from `supports_observed_cpu` when they are not given, and `has_memory_*` from `supports_observed_memory`.
   - Enforce the §10.2 consistency rules:
     - `supports_observed_cpu == (has_cpu_average or has_cpu_peak)`;
     - `supports_observed_memory == (has_memory_average or has_memory_peak)`.
   - Never infer `has_cpu_peak` from `supports_cpu` (§10.2, third consistency rule).
   - Check the profile's declared values (G-24): `supported_record_levels` and `evaluation_record_level` against `RECORD_LEVELS`; the per-field semantics, `time_semantics` and `instance_event_time_semantics` against the §7 vocabulary; `recurrence_key_origin` and `evaluation_mode` against §10.2; `cpu_unit` and `memory_unit` null or in `ALLOWED_RESOURCE_UNITS`.
4. **`to_dict()`.** Return plain lists for `supported_record_levels` and `allowed_exclusion_reasons`.
5. **Profiles** (values from §10.3 and §7):

   | Field | Google | Alibaba 2018 | Alibaba GPU 2020 |
   |---|---|---|---|
   | Ten existing flags | Unchanged | Unchanged | `true` except `supports_allocated_cpu` and `supports_allocated_memory`, which are `false` |
   | `has_cpu_average` / `has_cpu_peak` | `false` / `true` | `true` / `true` | `true` / `false` |
   | `has_memory_average` / `has_memory_peak` | `false` / `true` | `true` / `true` | `true` / `true` |
   | `recurrence_key_origin` | `constructed` | `none` | `official_with_role` |
   | `observed_cpu_semantics` / `peak_cpu_semantics` | null / `window_peak` | `instance_average` / `instance_peak` | `lifetime_average` / null |
   | `observed_memory_semantics` / `peak_memory_semantics` | null / `window_peak` | `instance_average` / `instance_peak` | `lifetime_average` / `lifetime_peak` |
   | `cpu_target_semantics` / `memory_target_semantics` | `next_occurrence_peak` / `next_occurrence_peak` | null / null | `next_occurrence_lifetime_average` / `next_occurrence_lifetime_peak` |
   | `time_semantics` | `first_execution_start` | `instance_start` | `job_submission` |
   | `instance_event_time_semantics` | null | null | `parent_job_submission` |
   | `cpu_unit` / `memory_unit` | `ncu` / `normalized` | CPU null / `alibaba_memory_source_normalized` (confirmed, section 8.2) | `percent_of_vcpu` / `gb` |
   | `supported_record_levels` | `occurrence` | `instance` | `role_occurrence`, `instance` |
   | `evaluation_record_level` | `occurrence` | `instance` | `role_occurrence` |
   | `evaluation_mode` | `full_next_occurrence` | `instance_request_versus_observed` | `next_occurrence_memory_peak_cpu_average` |
   | `allowed_exclusion_reasons` | empty | empty | The 14 reasons of §9.3, in rule order |
   | `any_resource_metric_valid` | `true` | Default ("not applicable") | `false` |
   | `target_split_isolation` | `false` | Default ("not applicable") | `true` |
   | `telemetry_window` | Full 31-day subset | Full trace | About day 19 to day 68.9 |

   The Azure Python profile is not edited. Under the defaults it resolves to: `has_cpu_average` and `has_cpu_peak` true; `has_memory_average` and `has_memory_peak` false; origin `none`; no record-level restriction; empty exclusion list; `any_resource_metric_valid` true; `target_split_isolation` false; every other new field null.

6. **New checks in `validate_canonical_frame`**, appended after the existing checks so that existing error messages still come first:
   - `has_cpu_average = false` rejects populated `observed_cpu`; `has_cpu_peak = false` rejects populated `peak_cpu`; the same for memory. The existing `supports_observed_*` gates stay.
   - When `supported_record_levels` is not null, every `record_level` must be in it.
   - When present, `cpu_validity_status` and `memory_validity_status` must be in `VALIDITY_STATUSES`.
   - When present, `resource_scope`, `request_aggregation_method` and `observed_aggregation_method` must be in their vocabularies.
   - When present, non-null `exclusion_reason` values must be in `allowed_exclusion_reasons`.
   - When present, `cpu_target_status` and `memory_target_status` must be in the target-status vocabulary.
   - When the profile declares `instance_event_time_semantics = parent_job_submission`, every `instance` row needs a non-null `event_time_us`.
   - Every vocabulary check applies only when its column is present (plan §3), so 0.1.0-shaped frames still validate.
   - GPU fields get unit and non-negativity checks through `RESOURCE_VALUE_FIELDS`, but no capability gate (§6.4; plan §3).

### 5.2 `src/adapters/validation.py`

1. **`role_occurrence` uniqueness.** Key on `role_key`; reject a missing column, null values and duplicates.
2. **Profile-driven identity checks**, applied to any profile that declares `role_occurrence` in `supported_record_levels` (today only Alibaba GPU 2020); see section 8.2 for how this is gated:
   - non-null `role_key` on `instance` rows as well as role rows;
   - non-null `instance_id` on `instance` rows.

   The `workload_id` rule already applies to every row. These checks read the identity values already on the rows. They don't build `role_key`, `instance_id`, `instance_attempt_index` or `source_row_number`, and they don't compare an instance row with its parent; that construction and linkage are Task 3.
3. **Recurrence-key rule** (framework §7.2):
   - When `recurrence_key_origin = none`, `recurrence_key` must be null. This is already true for Alibaba 2018 and Azure through `supports_recurrence = false`.
   - Otherwise, on evaluation rows (`occurrence` and `role_occurrence`), `recurrence_key` may be null only where `exclusion_reason = no_recurrence_key`.
   - Instance rows are not checked by this rule; see C-03.
4. **Adapter output carries no target-builder columns.**
   - Reject populated `split`, `actual_cpu`, `actual_memory`, `cpu_target_status` or `memory_target_status`.
   - Do this in `validate_adapter_output` only. The Google contract view calls `validate_canonical_frame` directly, which is how the "Google artifacts excepted" clause is met without a Google-specific branch.
5. Keep the existing order: duplicate columns, uniqueness, `dataset_id`, finiteness, then `validate_canonical_frame`. Put the new checks after uniqueness, and keep the existing error messages unchanged.

### 5.3 `config/dataset_capabilities.json`

- Regenerate the file from `DEFAULT_CAPABILITY_REGISTRY` (`to_dict()` without `notes`), or edit it by hand to the same content.
- It must contain four entries, and each entry must contain every field that `to_dict()` emits.
- Use JSON `null` for null fields and arrays for sequence fields.

### 5.4 `examples/canonical_records.jsonl`

- Rows 1–3: change only `schema_version`.
- New Alibaba GPU 2020 rows. Values are illustrative but must follow §5.3–§9.3 exactly:
  - **Row 4, grouped role:**
    - identity:
      - `record_level = role_occurrence`;
      - `workload_id = <group>`;
      - `recurrence_key = <group>||<task_name>`;
      - `occurrence_id = <group>||<job_name>`;
      - `role_key = <group>||<job_name>||<task_name>`;
      - `execution_id` and `instance_id` null;
    - time: `start_time_us` (submission) and `end_time_us` (completion);
    - resources:
      - `requested_cpu` in `percent_of_vcpu`;
      - `requested_memory` in `gb`;
      - `requested_gpu` in `percent_of_gpu`;
      - `observed_cpu` in `percent_of_vcpu`;
      - `peak_cpu` null;
      - `observed_memory` and `peak_memory` in `gb`;
      - optionally `observed_gpu` and `peak_gpu_memory`;
    - scope:
      - `resource_scope = task_role_per_instance`;
      - `request_aggregation_method = none`;
      - `observed_aggregation_method = maximum_over_instances`;
    - validity and eligibility:
      - `cpu_validity_status`, `memory_validity_status` and `validity_status` all `valid`;
      - `exclusion_reason` null;
    - no `actual_*`, `split` or target status.
  - **Row 5, fallback role** (job without `group`):
    - `workload_id = <job_name>`;
    - `occurrence_id = <job_name>`;
    - `role_key = <job_name>||<task_name>`;
    - `recurrence_key` null;
    - `exclusion_reason = no_recurrence_key`.
  - **Row 6, missing-CPU role:**
    - `observed_cpu` and its unit null;
    - `cpu_validity_status = partial`, `memory_validity_status = valid`, `validity_status = partial`;
    - `exclusion_reason` null.
  - **Row 7, instance audit row** (values written by hand; nothing is constructed or linked by code in this follow-up):
    - `record_level = instance`;
    - parent fields equal to row 4;
    - `execution_id = <job_name>||<task_name>`;
    - `instance_id = <job_name>||<task_name>||<inst_name>||1`;
    - `instance_slot_key`, `instance_attempt_index = 1`, `worker_id`, `source_row_number`, and the raw `source_inst_name`, `source_worker_name`, `source_status` and `source_machine`;
    - time: `event_time_us` = parent submission; `start_time_us` and `end_time_us` either the instance's own times or null;
    - `resource_scope = instance`, both aggregation methods `none`;
    - no `source_seq_no`.
- Every example is adapter-level output, so none of them carries `actual_*`. This matches row 1, which has no Google target either.

### 5.5 Schema and validation tests

- Existing test functions stay unedited.
- New tests go in the existing module or in the two new modules. They are listed in section 7.

---

## 6. Required backward-compatibility behavior

### 6.1 Google (`google_clusterdata2019`)

- **Unchanged:**
  - notebooks, pipeline, artifacts and target logic;
  - `tests/test_google_canonical_contract.py`;
  - the ten flags;
  - the known failure of `test_google_train_target_nulls_are_preserved`, which is not fixed here (plan §4).
- **Contract view still validates.**
  - The view populates `peak_*`, `requested_*` and `actual_*`, but not `observed_*`. Under `has_cpu_average = false` and `has_memory_average = false` there is therefore nothing to reject.
  - Its rows are `occurrence`, which is in `supported_record_levels`.
  - It has no `exclusion_reason`, scope or target-status columns, so those checks don't apply.
- **Not affected by the adapter-target rule.** The view passes through `validate_canonical_frame`, not `validate_adapter_output`, so its precomputed `actual_*` values stay allowed (framework §3).
- **Separate policies stay separate.** `target_split_isolation = false` records the current behavior. Nothing here enforces or changes the F1/F3/F5 issues; those are separate Google work.

### 6.2 Alibaba 2018 (`alibaba_clustertrace2018`)

- **Adapter code and tests unchanged:**
  - identity: `workload_id = job_name`, `execution_id = job_name|task_name`, `instance_id = instance_name`;
  - the `source_seq_no` instance key;
  - source-specific units;
  - `cpu_validity_status` and `memory_validity_status`;
  - no `recurrence_key` column;
  - existing timestamp behavior.
- **New fields leave its output valid:**
  - `has_*` all true, so it still accepts `observed_*` and `peak_*`;
  - `supported_record_levels = instance` matches the only level it emits;
  - its validity values are already in the vocabulary;
  - `instance_event_time_semantics` is null, so the instance event-time rule doesn't apply.
- **The `instance_id` rule must not tighten.** Non-null `instance_id` must not be required for Alibaba 2018 (C-04): today a null `instance_name` gives a row whose key is not checked.

### 6.3 Azure (`azure_public_vm_v2`)

- **Unchanged:** adapter code, its Python profile, the ten flags and both views. `adapt_vm_table` keeps validating directly (framework §4.3, §9.4).
- **JSON only.** The JSON entry receives the new fields at their default values, for registry consistency (plan §4).
- **Under the defaults its output still validates:**
  - `has_cpu_average` and `has_cpu_peak` resolve to true, so `observed_cpu` and the populated `peak_cpu` (`max_cpu`) stay accepted;
  - `has_memory_*` resolve to false, which repeats the existing "observed memory unsupported" rejection;
  - `supported_record_levels` is null, so both its `instance` and `interval` rows are allowed;
  - the origin is `none`, which matches its null `recurrence_key`;
  - the instance event-time rule doesn't apply.
- **Existing error messages are kept.** `test_azure_observed_memory_rejected` matches `"observed memory unsupported"`. The existing `supports_observed_memory` gate fires first because the new checks are appended later.

### 6.4 Reference adapter (`ReferenceOccurrenceAdapter`)

- **No code change.** It writes `SCHEMA_VERSION`, so it emits `0.2.0` automatically.
- **Its rows still validate against the Google profile:**
  - `occurrence` rows;
  - non-null `recurrence_key`, as `constructed` requires;
  - `requested_cpu` and `peak_cpu` only, which `has_cpu_peak = true` allows;
  - no `actual_*`, so it passes the adapter-target rule.
- **All ten tests in `tests/test_adapter_contract.py` must pass unedited.** That includes `test_reference_adapter_returns_valid_result`, `test_adapter_does_not_mutate_source`, `test_nonfinite_resource_rejected` and `test_duplicate_interval_records_rejected`.

---

## 7. Required test cases before merge

### 7.1 Schema tests

| # | Test | Expected |
|---|---|---|
| S-01 | Version in code, JSON and every example | All `0.2.0` |
| S-02 | `role_occurrence` is accepted as a record level | Pass |
| S-03 | Positional `DatasetCapabilities(id, ten flags, notes)` still constructs | Pass, with the has-flags resolved from `supports_observed_*` |
| S-04 | Consistency rule: `supports_observed_cpu = true` with `has_cpu_average = has_cpu_peak = false` | Rejected; the same for memory and for the reverse case |
| S-05 | `to_dict()` returns lists, and `to_dict()` minus `notes` equals the JSON for all four profiles | Pass. The existing registry test also passes |
| S-06 | The Google, Alibaba 2018 and Alibaba GPU 2020 profiles hold the §10.3 values; the Azure profile holds the resolved defaults and its ten flags are unchanged | Pass |
| S-07 | Alibaba GPU 2020 row with populated `peak_cpu` | Rejected (`has_cpu_peak = false`) |
| S-08 | Alibaba GPU 2020 row with `observed_cpu` populated and `peak_cpu` null | Pass |
| S-09 | Google row with populated `observed_cpu` | Rejected (`has_cpu_average = false`) |
| S-10 | `percent_of_vcpu` and `percent_of_gpu` values | Pass; an unknown unit is still rejected |
| S-11 | GPU field without a unit, or with a negative value | Rejected |
| S-12 | GPU fields null | Pass; values stay null, not zero |
| S-13 | Invalid `resource_scope`, `request_aggregation_method` or `observed_aggregation_method` | Rejected; valid values pass; an absent column passes |
| S-14 | Invalid `cpu_validity_status` or `memory_validity_status` | Rejected |
| S-15 | `exclusion_reason` outside the profile's list, for example any non-null value under Google or Azure | Rejected; each of the 14 Alibaba GPU 2020 reasons passes |
| S-16 | Invalid `cpu_target_status` or `memory_target_status` | Rejected; the five valid values pass |
| S-17 | `record_level` outside `supported_record_levels`, for example an `occurrence` row under the Alibaba GPU 2020 profile | Rejected; Azure `instance` and `interval` rows pass, because its levels are unrestricted |
| S-18 | Alibaba GPU 2020 `instance` row without `event_time_us` but with `start_time_us` | Rejected |
| S-19 | Alibaba GPU 2020 `instance` row with `event_time_us` and null `start_time_us` | Pass |
| S-20 | Alibaba 2018 and Azure `instance` rows without `event_time_us` | Pass, as before |
| S-21 | Every Alibaba GPU 2020 example row (4–7) validates against its profile | Pass |
| S-22 | Missing-CPU example: CPU null, `cpu_validity_status = partial`, memory populated | Pass; CPU null and not zero |
| S-23 | Profile with an unknown record level in `supported_record_levels` or `evaluation_record_level`, an unknown semantics value, `recurrence_key_origin` or `evaluation_mode`, or a `cpu_unit` outside the allowed units | Rejected at construction; all four registry profiles construct |

### 7.2 Validation tests

| # | Test | Expected |
|---|---|---|
| V-01 | Two `role_occurrence` rows with the same `role_key` | `AdapterValidationError`, duplicate `role_occurrence` |
| V-02 | `role_occurrence` row with null `role_key`, and a frame with no `role_key` column | Rejected |
| V-03 | Two role rows of one job (same `occurrence_id`, different `role_key`) | Pass |
| V-04 | Alibaba GPU 2020 instance row with null `role_key` or null `instance_id` | Rejected |
| V-05 | Two Alibaba GPU 2020 instance rows with the same `instance_id` and no `source_seq_no` | Rejected; different attempt indices pass |
| V-06 | Fallback role row: null `recurrence_key` with `exclusion_reason = no_recurrence_key` | Pass |
| V-07 | Grouped role row: null `recurrence_key` with null `exclusion_reason` | Rejected |
| V-08 | Alibaba 2018 or Azure row with populated `recurrence_key` | Rejected with the existing message (`recurrence unsupported`) |
| V-09 | Adapter output with populated `split`, `actual_cpu`, `actual_memory`, `cpu_target_status` or `memory_target_status` under the Alibaba GPU 2020 profile | Rejected by `validate_adapter_output` |
| V-10 | The same `actual_*` values passed to `validate_canonical_frame` with the Google profile | Pass (Google exception) |
| V-13 | Existing Alibaba 2018 duplicate retry (`test_alibaba_duplicate_instance_retry_record_rejected`) | Still rejected with the same message |
| V-14 | New checks run after the existing ones | Existing `match=` strings in the PR #70 tests are unchanged |

IDs V-11 and V-12 are retired. They tested the instance-to-parent linkage helper, which is no longer in this follow-up. Linkage-interface tests on synthetic role and instance views belong to Task 1, and Alibaba GPU 2020 linkage tests belong to Task 3.

### 7.3 Test gate

The gate is strict:
- **All existing PR #70 tests pass, unedited:** `tests/test_canonical_schema.py`, `tests/test_adapter_contract.py`, `tests/test_alibaba_adapter.py`, `tests/test_azure_vm_adapter.py`, `tests/test_external_adapter_integration.py`, and the rest of `tests/test_google_canonical_contract.py`.
- **All new schema and validation tests pass** (sections 7.1 and 7.2).
- **No new test failure is allowed.**
- **The only permitted pre-existing failure** is the documented Google target-null test, `test_google_train_target_nulls_are_preserved` (1,463 vs 1,801). This matches the baseline of 81 passed and 1 failed, plus the new tests passing.
- **Not required in PR #70:** any Alibaba GPU 2020 adapter implementation, multi-view support or parent-linkage implementation. No test may depend on them.

Order: the focused modules first, then the PR #70 regression modules, then the full suite.

---

## 8. Contradictions and open items

### 8.1 Contradictions between the documents and the code

| ID | Contradiction | Sources | Resolution within the frozen contract |
|---|---|---|---|
| C-01 | Where the vocabulary checks live. The §2 table assigns the per-resource validity, exclusion and target-status vocabularies to `schema.py`, but assigns "vocabulary checks for scope, aggregation, exclusion reasons and target statuses" to `validation.py`. Framework §7.2 lists every check under `validate_adapter_output` | §2 table; framework §2, §7.2 | Define the constants in `schema.py` and run the checks inside `validate_canonical_frame`. `validate_adapter_output` always calls it, so both readings are satisfied and no check runs twice |
| C-02 | The plan's scope omits four checks that framework §7.2 lists as required for 0.2.0: (a) adapter output carries no `split`, `actual_*` or target statuses; (b) the recurrence-key rule; (c) `record_level` within `supported_record_levels` (the plan only defines how null is represented); (d) non-null `role_key` on Alibaba GPU 2020 **instance** rows | Plan §3, §7; framework §7.2 | The frozen framework is authoritative, so all four are included as required (G-15, G-16, G-17, G-19). Framework §7.2's rejected-output check is the exception: the plan explicitly excludes it, and it needs `AdapterResult` changes in `base.py`, so it is later work (section 11.3). **Resolved in the plan (2026-10-17):** plan §3 now includes all four checks |
| C-03 | Framework §7.2 allows a null `recurrence_key` only when the origin is `none` or the row is excluded as `no_recurrence_key`. But instance rows of jobs without `group` inherit a null `recurrence_key` (§5.5) and carry no exclusion reason (§9.4, D-08). Applied literally to every row, the rule would reject valid instance audit rows | Framework §7.2; §5.5, §9.4 | In PR #70, apply the per-row rule to evaluation rows (`occurrence`, `role_occurrence`) only. Instance-row `recurrence_key` is checked later through the Task 1 linkage-validation interface, which requires it to equal the parent role row's value; that is null exactly when the parent is `no_recurrence_key`. Task 3 runs that check on the Alibaba GPU 2020 views |
| C-04 | The plan says "`instance_id` is required for validated instance rows according to the existing record-level uniqueness rules". The existing rules don't require non-null keys: null-key rows are skipped (`validation.py:44`; framework §7.1, "rows with a null key are not checked"). A global non-null rule would change Alibaba 2018 behavior when `instance_name` is null | Plan §3, §7 item 6; framework §7.1; `validation.py:44` | **Resolved (2026-10-17).** Non-null `instance_id` is enforced only for profiles that declare `role_occurrence` in `supported_record_levels` (today only Alibaba GPU 2020). Alibaba 2018 and Azure keep their existing behavior: null-key instance rows are still skipped by the uniqueness check, and no new non-null rule applies to them. Plan §3 and §7 item 6 state the same rule |
| C-05 | §10.3 gives the Alibaba 2018 `cpu_unit` as "Alibaba 2018 source units", but Alibaba 2018 uses two different CPU unit strings (§6.2). The plan resolves this as `null` | §6.2, §10.3; plan §3 | Use `null`, as the plan proposes, because one value can't describe both. **Confirmed (2026-10-17)**, section 8.2 |
| C-06 | §10.3 marks `any_resource_metric_valid` and `target_split_isolation` as "not applicable" for Alibaba 2018 and "Default" for Azure, but both are boolean fields, and the documents never state the defaults | §10.2, §10.3 | Use the defaults `true` and `false`, which match 0.1.0 behavior. Alibaba 2018 and Azure have `supports_targets = false`, so neither value has any effect. **Confirmed (2026-10-17)**, section 8.2 |
| C-07 | The documents never state the default for `recurrence_key_origin` | §10.2, §10.3 | Use `none`. It is the only vocabulary value consistent with Azure's null `recurrence_key` and with the G-16 rule. **Confirmed (2026-10-17)**, section 8.2 |
| C-08 | Framework §6 requires `schema_version` and provenance in `AdapterResult.metadata`. `BaseDatasetAdapter.build_metadata` (`base.py:28–36`) has neither, and the plan excludes `base.py` | Framework §2, §6; plan §5 | Not part of this follow-up: it is assigned to Task 1 (section 11.3). Note that adapter metadata keeps lacking `schema_version` until then |
| C-11 | The implementation plan's "Instance identity and time" row asks this follow-up to "add a helper that checks instance rows against their parent role row" and to define `instance_slot_key`, `instance_attempt_index`, `worker_id` and `source_row_number`. Cross-view linkage needs separate role and instance views, which only Task 1 provides, and building those fields is Task 3 | Plan §3; framework §4.3, §7.2 | The linkage helper is not in this follow-up: the interface is Task 1 and the Alibaba GPU 2020 linkage is Task 3. This follow-up only names those fields in the hand-written examples and doesn't construct them. **Resolved in the plan (2026-10-17):** the helper and the field construction are removed from plan §3, listed as non-goals in plan §5, and assigned to Tasks 1–3 in plan §2 |
| C-09 | Plan acceptance item 9 says the existing tests pass "without edits", while §2 says the tests are "updated together" with the code | Plan §7; §2 | No existing test function is edited. New tests are added, and the examples and JSON are updated so that the existing tests keep passing |
| C-10 | The plan says the has-flag defaults "resolve from `supports_observed_*`", but a frozen dataclass default can't refer to another field | Plan §3; `schema.py:30` | Use a `None` sentinel resolved in `__post_init__` (section 4.1). This is implementation detail, not a contract change |

### 8.2 Confirmed choices

All choices that the documents left open were confirmed on 2026-10-17. Each one was checked against the frozen design and the current code:

| # | Choice | Why it holds |
|---|---|---|
| 1 | `telemetry_window` is a string | The §10.3 values are descriptions ("Full 31-day subset", "About day 19 to day 68.9", "Full trace"). A numeric range would have to invent bounds for Google and Alibaba 2018 |
| 2 | Alibaba 2018 `cpu_unit` is `null`; `memory_unit` is `alibaba_memory_source_normalized` (C-05) | The adapter writes `alibaba_plan_cpu_100_per_core` on `requested_cpu` but `alibaba_cpu_usage_source_unit` on `observed_cpu` and `peak_cpu` (`alibaba.py:233–268`), so no single CPU unit is true. All its memory fields use `alibaba_memory_source_normalized`. Alibaba 2018 has no targets, so nothing compares a CPU request with an actual (§6.2) |
| 3 | `supported_record_levels = null` means no restriction | The Azure Python profile is not edited and its adapter emits both `instance` and `interval` rows (`azure_vm.py:270, 452`). Any other default would reject them. Profiles that declare levels (Google `occurrence`, Alibaba 2018 `instance`, Alibaba GPU 2020 `role_occurrence` and `instance`) are restricted to them |
| 4 | An empty `allowed_exclusion_reasons` means every `exclusion_reason` must be null | Google has no exclusion rules (§9.3), Alibaba 2018 rules are not defined in this version, and no existing adapter or the Google contract view emits `exclusion_reason` |
| 5 | `recurrence_key_origin` defaults to `none` (C-07) | `none` is in the §10.2 vocabulary. Azure has `supports_recurrence = false` and never emits a `recurrence_key`; any other default would make the G-16 rule demand one. Google (`constructed`), Alibaba 2018 (`none`) and Alibaba GPU 2020 (`official_with_role`) set the value explicitly |
| 6 | `any_resource_metric_valid` defaults to `true`, `target_split_isolation` to `false` (C-06) | Both match current behavior: the evaluator always computes any-resource violation (`evaluator.py:97`) and the Google targets cross splits. Alibaba 2018 and Azure have `supports_targets = false`, so the values have no effect for them. Google and Alibaba GPU 2020 set both explicitly |
| 7 | The non-null `role_key` check on instance rows is gated by `role_occurrence` in `supported_record_levels` | It uses an existing §10.2 field, so no new flag is needed, and it is the same gate as the `instance_id` rule |
| 8 | Non-null `instance_id` is enforced only for profiles that declare `role_occurrence` (C-04) | Keeps Alibaba 2018 and Azure behavior unchanged |

Nothing remains to confirm before coding.

The name and signature of the linkage-validation interface are decided in Task 1, not here.

---

## 9. Recommended implementation order and dependencies

| Step | Work | Depends on | Notes |
|---|---|---|---|
| 1 | `schema.py`: version, record level, units, GPU fields, vocabulary constants | — | |
| 2 | `schema.py`: `DatasetCapabilities` fields, `__post_init__` (defaults, consistency rules, profile vocabulary checks), `to_dict()` | 1 | Move `CanonicalSchemaError` above the dataclass, or raise `ValueError` |
| 3 | `schema.py`: Google and Alibaba 2018 keyword values; new Alibaba GPU 2020 profile; registry | 2 | Azure is not edited |
| 4 | `config/dataset_capabilities.json` | 3 | **Same commit as steps 1–3**, or the registry test fails |
| 5 | `schema.py`: new checks in `validate_canonical_frame` | 1–3 | Append after the existing checks |
| 6 | `validation.py`: `role_occurrence` uniqueness, profile-driven identity checks, recurrence rule on evaluation rows, target-column rule | 1–3 | No linkage helper (Task 1) |
| 7 | `examples/canonical_records.jsonl` | 5, 6 | Rows 1–3 only change version; rows 4–7 are appended |
| 8 | New schema and validation tests | 4–7 | Section 7 |
| 9 | Focused tests, then the PR #70 regression modules, then the full suite | 8 | Section 7.3 |

Steps 1–4 are one atomic change. Steps 5 and 6 can proceed in parallel once step 3 exists. The choices in section 8.2 are confirmed; they set the defaults that steps 2–4 write into code and JSON.

**After this follow-up:**

```text
PR #70 follow-up
→ Task 1 shared multi-view adapter framework
→ Task 2 verified Alibaba GPU 2020 data loading
→ Task 3 Alibaba GPU 2020 adapter and canonical artifacts
→ Task 4 shared targets and evaluation
```

Task 2 has no code dependency on this follow-up or on Task 1, so it can start on day 1 (see `docs/planning/data_integration_tasks.md` §5). Task 3 needs all three.

---

## 10. Definition of done for the PR #70 follow-up

The follow-up is done when every item holds:

1. `SCHEMA_VERSION`, the JSON `schema_version` and all example rows are `0.2.0`.
2. `role_occurrence` is a record level; `role_key` is unique and non-null on its rows.
3. `percent_of_vcpu` and `percent_of_gpu` are allowed units. `requested_gpu`, `observed_gpu` and `peak_gpu_memory` are resource fields with unit, non-negativity and finiteness checks, and no capability gate.
4. `DatasetCapabilities` has every §10.2 and §7 field with a default. Existing positional calls still work, and the §10.2 consistency rules are enforced.
5. `peak_cpu` is rejected when `has_cpu_peak = false`, and the average and memory equivalents work the same way. The ten 0.1.0 gates still apply.
6. The scope, aggregation, per-resource validity, exclusion-reason, target-status and supported-record-level checks are in place, each applied only when its column (or profile value) is present. Profile record-level and resource-semantics declarations are validated (G-24).
7. The `event_time_us` and identity checks are driven only by profile and record-level declarations, and nothing in this follow-up constructs identity fields. Alibaba 2018 and Azure timestamp and key behavior is unchanged.
8. `validate_adapter_output` rejects adapter-emitted `split`, `actual_*` and target statuses; the Google contract view still validates.
9. The recurrence-key rule applies to `occurrence` and `role_occurrence` rows, as resolved in C-03. No instance-to-parent linkage helper is required.
10. `ALIBABA_GPU_2020_CAPABILITIES` (`alibaba_gpu_v2020`) is in the Python registry and the JSON, and the two match exactly for all four profiles.
11. The examples contain the three updated rows and the four Alibaba GPU 2020 rows, and all of them validate.
12. Every test in section 7 exists and passes.
13. The section 7.3 test gate holds: existing PR #70 tests pass unedited, no new failure appears, and the full suite's only failure is `test_google_train_target_nulls_are_preserved`.
14. No file outside section 3 has changed: no adapter, `base.py`, notebook, script, artifact or evaluator change.
15. The confirmed choices in section 8.2 are recorded in the pull-request description.

The follow-up does **not** require any Alibaba GPU 2020 adapter behavior, multi-view `AdapterResult`, rejected output, provenance metadata or instance-to-parent linkage. Those are Tasks 1 and 3.

---

## 11. Classification of work

### 11.1 Required PR #70 follow-up corrections

G-01 to G-19 and G-21 to G-24 (section 2), implemented as described in sections 4–5, tested as in section 7, with C-01 to C-04, C-10 and C-11 resolved as in section 8.1. G-20 (instance-to-parent linkage) is not a PR #70 correction; it is classified under Tasks 1 and 3 in section 11.3.

### 11.2 Optional improvements (not required by the contract)

| ID | Improvement | Reason |
|---|---|---|
| O-01 | Run the finiteness check in `validate_adapter_output` (`validation.py:83–91`) over `RESOURCE_VALUE_FIELDS` instead of column-name prefixes | The prefix match also catches the new non-numeric `observed_aggregation_method` column. Its strings coerce to NaN and pass harmlessly today, but the check is fragile |
| O-02 | Check the `split` column against `train`, `validation` and `test` when present | §11 defines the vocabulary. Neither framework §7.2 nor the plan lists the check, and adapters must not emit `split` anyway |
| O-04 | Reject a non-null `exclusion_reason` on `instance` rows for profiles that declare `role_occurrence` | §9.4 says instance rows have no independent reason. No document lists this as a validation check |
| O-06 | Move the CPU and memory gate column lists (`schema.py:136–211`) into named constants | Readability |

### 11.3 Later dataset-specific implementation work (not part of this follow-up)

| Item | Owner or task | Source |
|---|---|---|
| Multiple named validated views in `AdapterResult`, including separate role and instance views; per-view validation | Task 1 | Framework §4.3 |
| Rejected output in `AdapterResult`, with its minimal checks | Task 1 | Framework §4.4, §7.2; plan §5 |
| Adapter provenance and rejection metadata: `schema_version`, provenance, validity-count, exclusion-count and rejection-count metadata in `build_metadata` | Task 1 | Framework §6 (C-08) |
| Multi-table preparation as part of the base contract | Task 1 | Framework §4.2 |
| Linkage-validation interface that accepts role and instance views | Task 1 | Framework §7.2; §5.5 |
| Regenerating saved 0.1.0 canonical samples. None exist under `data/processed`; samples from `scripts/build_external_canonical_samples.py` must be rebuilt after the bump, because version validation is exact | Task 1 | `schema.py:86–87` |
| Columnar loading with explicit schemas; source checksums; stable `source_row_number` in source-file order | Task 2 | Framework §5, §9.2; D-21 |
| Alibaba GPU 2020 adapter logic: source-table joins, timestamp contract, rejected-record routing through Task 1 | Task 3 | §7, §9.5; framework §9.2 |
| Alibaba GPU 2020 identity construction: `workload_id`, `recurrence_key`, `occurrence_id`, `role_key`, `instance_slot_key`, `instance_attempt_index`, `instance_id`, and `source_row_number` carried from Task 2 | Task 3 | §5.3–§5.4; D-04, D-05, D-21 |
| Alibaba GPU 2020 parent-field inheritance, full instance-to-parent linkage and linkage tests | Task 3 | §5.5, §9.4; D-08 |
| Alibaba GPU 2020 exclusion processing (the 14 ordered rules) | Task 3 | §9.3; D-17 |
| Alibaba GPU 2020 resource aggregation | Task 3 | §6.3, §8; D-10, D-11 |
| Shared target builder: splits, history, `actual_*`, target statuses, split isolation | Task 4 | §11 |
| Evaluator suppression of any-resource metrics and the average-usage CPU label | Task 5 | §12 |
| Alibaba 2018 upgrade to 0.2.0: unit unification, status-based validity, chunked loading | Task 8 (optional) | §6.2, §14; framework §9.3 |
| Google target-null discrepancy and the F1/F3/F5 target corrections | Task 9 | Plan §4; Google Subset Pipeline Analysis |
| Azure V1/V2 identity and retiring the `adapt_vm_table` bypass | Task 10 (deferred) | §3; framework §4.3, §9.4 |
| GPU aggregation and target semantics; GPU evaluation | Future scope | §6.4, D-20 |
