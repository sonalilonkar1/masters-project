# Task 1 (#66) Review: PR #91 — Multi-view Adapter Framework

**Branch:** `feature/issue-66-multiview-adapter-framework` (commit `1989fb2`)
**Status:** Review notes only; no fixes applied.
**Tests on branch:** 199 passed (`tests/test_ml_prep.py` skipped locally because `sklearn` isn't installed).

**Sections:**
1–4 review the PR's code, one class or module per section.
5 lists gaps in the Task 1 issue text compared with the frozen design.

---

## 1. `AdapterResult` (`src/adapters/base.py:22–66`)

### About
`AdapterResult` is the object every adapter returns. It carries canonical output and metadata to the downstream stages (target builder, baselines, ML, evaluator).

Alibaba GPU 2020 produces three outputs from one run (framework §4.3–§4.4):
- **`role_occurrence` view:** evaluation rows, used by splits, history, targets and evaluation.
- **`instance` view:** audit rows, one per worker or attempt, each linked to its parent role row.
- **Rejected output:** records with no usable canonical time (`missing_submission_time`). They are kept for audit only and never used downstream.

**Before the PR:** `canonical: pd.DataFrame` and `metadata: Mapping`, which was enough for the single-view adapters (Alibaba 2018, Azure, Reference).

### Changes in PR #91
| Change | Description |
|---|---|
| `views: Mapping[str, pd.DataFrame]` (default `{}`) | Named canonical views |
| `rejected: pd.DataFrame` (default empty) | Rejected output, kept separate from the views |
| `get_view(name)` | Returns a view by name. `"canonical"` is an alias for the primary view; an unknown name raises `KeyError` |

Both new fields have defaults, so existing callers are unaffected (for example, `azure_vm.py:648` builds `AdapterResult` directly).

### Issues

**1.1 `views` holds different things depending on how the result was built (Medium)**
- **What:**
  - Built through `adapt()`: `views = {"canonical": df}`.
  - Built directly (`azure_vm.py:648`): `views = {}`.
  - Built through `adapt_sources()`: `views = {"role_occurrence", "instance"}`, with no `"canonical"` key.
- **Why it matters:** code that iterates `result.views` sees zero, one or two views depending on the adapter. Tasks 3 and 4 read views by name. `get_view("canonical")` hides the problem because it bypasses `views`.
- **Fix:** add a `__post_init__` that sets `views = {primary_view: canonical}` when no views are given, and copies `views` into a new dict.
- **Where:** `AdapterResult`, `base.py:22–66`.
- **Affects:** Task 3, Task 4.

**1.2 `primary_view` isn't stored on the result (Medium)**
- **What:** the primary view is recorded only in `metadata["primary_view"]`, and only by `adapt_sources()`. Nothing checks that `canonical` is the same frame as `views[primary_view]`.
- **Why it matters:** code that receives a result can't tell which view `canonical` is, and the two could silently differ.
- **Fix:**
  - Add a field `primary_view: str | None = None`.
  - In `__post_init__`:
    - default it to `"canonical"` when no views are given;
    - otherwise infer it from the view that is `canonical`, and raise if that's ambiguous;
    - check that `views[primary_view] is canonical`.
  - Set it explicitly in `adapt()` and `adapt_sources()`.
- **Where:** `AdapterResult`; `adapt()` (`base.py:115`); `adapt_sources()` (`base.py:350`).
- **Affects:** Task 3, Task 4.

**1.3 Test coverage is thin (Medium)**
- **What:** the only direct test checks `result.canonical is canonical`. Nothing tests `get_view` (the alias, or `KeyError` for an unknown name), the field defaults, `primary_view`, or the `views` / `rejected` values that `adapt()` returns.
- **Why it matters:** the acceptance criteria require backward compatibility and named views, so these need tests to stay working.
- **Fix:** add tests for:
  - single-view defaults;
  - a named primary view;
  - inferring the primary view;
  - an inconsistent `primary_view` raising;
  - an unknown view raising `KeyError`;
  - the result's `views` not changing when the caller's dict changes;
  - `adapt()` and `adapt_sources()` setting `primary_view`.
- **Where:** `tests/test_multiview_adapter_framework.py`.
- **Affects:** Task 3.

**1.4 `frozen=True` is shallow (Low)**
- **What:** fields can't be reassigned, but the DataFrames and dicts can still be changed in place.
- **Why it matters:** if Task 4 adds a `split` column to `result.canonical`, `views[primary_view]` changes too, because it is the same object.
- **Fix:** add a docstring note that downstream stages must copy a view before changing it. Optionally wrap `views` and `metadata` in `MappingProxyType`.
- **Where:** `AdapterResult` docstring.
- **Affects:** Task 4.

### Summary
| # | Issue | Severity | Affects |
|---|---|---|---|
| 1.1 | `views` holds different things depending on the path | Medium | Task 3, Task 4 |
| 1.2 | `primary_view` not stored or checked | Medium | Task 3, Task 4 |
| 1.3 | Missing tests | Medium | Task 3 |
| 1.4 | Shallow immutability | Low | Task 4 |

---

## 2. `BaseDatasetAdapter` (`src/adapters/base.py:69–578`)

### About
`BaseDatasetAdapter` is the abstract base class for every adapter (framework §4):
- **The subclass provides** the capability profile and the source-to-canonical mapping.
- **The base class provides** input copying, a check that the caller's input wasn't modified, validation and metadata. Adapters can't skip validation, and every result has the same shape.

Task 1 extends it from one source table and one canonical frame to several source tables, several views, a rejected output and provenance metadata.

**Before the PR:** `capabilities` and `to_canonical` were abstract. `build_metadata()` returned name, version, dataset ID, row counts and capabilities. `adapt()` ran: type check → copy → `to_canonical` → input-unchanged check → `validate_adapter_output` → `AdapterResult`.

### Changes in PR #91
| Method | Line | Change |
|---|---|---|
| `capabilities`, `to_canonical` | 75, 81 | Formatting and docstrings only |
| `build_metadata` | 94 | Adds `schema_version` |
| `adapt` | 115 | Same steps; the result also gets `views={"canonical": df}` and an empty `rejected` |
| **`prepare_sources`** (new) | 172 | Multi-table preparation hook. The default returns deep copies; Task 3 overrides it for joins |
| **`map_prepared_sources`** (new) | 190 | Returns `(views, rejected)`. The default handles a single `"source"` table through `to_canonical` and raises `NotImplementedError` otherwise |
| **`build_multiview_metadata`** (new) | 225 | Builds metadata: schema and adapter info, capabilities, `primary_view`, row counts per table and per view, validity counts, total exclusions, total rejections, and the provenance values passed in (source version, files, checksums, telemetry window, join coverage) |
| **`adapt_sources`** (new) | 350 | Multi-view pipeline: check inputs and copy → `prepare_sources` → `map_prepared_sources` → per view, a record-level check and `validate_adapter_output` → `validate_rejected_output` → input-unchanged check → resolve `primary_view` → metadata → result |

Existing adapters are unaffected. Alibaba 2018 `adapt_tables` and Azure `adapt_cpu_readings` are unchanged, and the regression modules pass.

### Issues

**2.1 A record can appear in both a view and the rejected output (Medium)**
- **What:** `adapt_sources` validates the views and the rejected output separately but never checks whether they overlap.
- **Why it matters:** Task 1 acceptance criterion 2 says no rejected record may appear in a validated view, and Task 4 must never use rejected rows (#81).
- **Fix:** raise if a rejected row's `role_key` appears in the `role_occurrence` view, or a rejected row's `instance_id` appears in the `instance` view.
- **Where:** `adapt_sources`, next to `validate_rejected_output` (line 523). Add one test.
- **Affects:** Task 3, Task 4.

**2.2 Provenance is never checked (Medium)**
- **What:** `build_multiview_metadata` copies whatever provenance the adapter passes in, and missing keys silently become `None` or `{}`.
- **Why it matters:** acceptance criterion 4 says metadata is "produced **and checked**". Missing checksums would only surface at Task 8.
- **Fix:** raise if `source_version`, `source_files`, `source_checksums` or `telemetry_window` is missing or empty on the multi-view path.
- **Where:** `build_multiview_metadata` (line 225), or a helper called from `adapt_sources`. Add one test.
- **Affects:** Task 3, Task 8.

**2.3 The input-unchanged check isn't tested on the multi-view path (Low)**
- **What:** `adapt_sources` checks that the caller's source tables weren't modified (framework §4.1, §4.3), but no test covers this.
- **Why it matters:** it's a frozen contract rule, and a refactor could remove it unnoticed.
- **Fix:** add a test where `prepare_sources` or `map_prepared_sources` modifies its input.
- **Where:** `tests/test_multiview_adapter_framework.py`.
- **Affects:** Task 3.

### Summary
| # | Issue | Severity | Affects |
|---|---|---|---|
| 2.1 | Rejected output and views can overlap | Medium | Task 3, Task 4 |
| 2.2 | Provenance not checked | Medium | Task 3, Task 8 |
| 2.3 | Input-unchanged check not tested | Low | Task 3 |

---

## 3. Validation functions (`src/adapters/validation.py`)

### About
`validation.py` holds the shared checks that every adapter's output must pass. It builds on `validate_canonical_frame` (`src/canonical/schema.py`) and adds the adapter-level rules from framework §7.

### Existing code (PR #70; unchanged by PR #91)
| Function | Checks |
|---|---|
| `AdapterValidationError` | (The error type raised by all adapter checks) |
| `_validate_record_uniqueness` | Unique rows per record level: `occurrence_id`, `role_key` (null or missing is an error), `instance_id` (+ `source_seq_no`), `execution_id`, interval keys |
| `_validate_profile_identity` | Profiles with `role_occurrence`: instance rows must have `role_key` and `instance_id` |
| `_validate_recurrence_keys` | Origin `none`: `recurrence_key` is always null. Otherwise it may be null only on rows excluded as `no_recurrence_key` |
| `_reject_target_builder_columns` | No `split`, `actual_*` or target-status values in adapter output |
| `validate_adapter_output` | Runs: duplicate columns → uniqueness → dataset ID → finite values → `validate_canonical_frame` → the 0.2.0 checks |

Through `validate_canonical_frame`, the existing code covers every framework §7.2 rule except one:
- **Covered:** vocabularies, `exclusion_reason` against the profile, `peak_cpu` gating, `supported_record_levels`, units.
- **Not covered:** instance `event_time_us` (G3). No validator reads `instance_event_time_semantics`.

### Changes in PR #91
| Function | Line | Checks |
|---|---|---|
| **`validate_rejected_output`** (new) | 217 | No duplicate columns; every row has a non-null, non-blank `rejection_reason`. An empty frame passes |
| **`_null_equal`** (new) | 288 | Equality where null = null |
| **`validate_role_instance_linkage`** (new) | 304 | Requires the linkage columns, and a non-null, unique `role_key` on the role view. Left-joins instances to roles on `role_key` and compares `workload_id`, `recurrence_key` and `occurrence_id`. Returns `(valid, rejected)`, labeling rejected rows `missing_parent_role` or `parent_identity_mismatch` |

**Correct as written:**
- the join is `many_to_one`, and row order is preserved;
- it compares the four inherited fields (schema §5.5);
- null = null handles jobs without `group`;
- a null `role_key` counts as an orphan;
- inputs are not modified.

### Issues
None. The changes this module needs come from the Task 1 issue gaps (G1, G3, G4, G6 in §5).

---

## 4. Tests (`tests/test_multiview_adapter_framework.py`)

### About
Synthetic framework tests. A test-only `SyntheticMultiViewAdapter` passes `roles`, `instances` and `rejected` tables straight through to views, using the test profile `TEST_CAPABILITIES` (`supported_record_levels = (role_occurrence, instance)`). The fixtures are one role row and one instance row.

These regression modules are unchanged and pass: `test_adapter_contract.py`, `test_alibaba_adapter.py`, `test_azure_vm_adapter.py`, `test_external_adapter_integration.py`, `test_google_canonical_contract.py`.

### Changes in PR #91 (11 tests, against the issue's test list)
| Requirement | Test | Covered? |
|---|---|---|
| Named views, role and instance | `test_multiview_adapter_returns_named_views` | Yes |
| Single-view backward compatibility | `test_adapter_result_preserves_single_view_access` | Weak (1.3) |
| Per-view validation | `test_role_and_instance_views_validate_independently` | Yes |
| Rejected output kept separate | `test_rejected_output_is_separate_from_views` | Partly: rows are returned, but separation from the views isn't checked (2.1) |
| Minimal rejected checks | `test_rejected_output_requires_reason` | Yes |
| Metadata complete | `test_metadata_contains_required_framework_fields` | Partly: provenance values aren't asserted |
| Missing parent | `test_missing_parent_role_is_rejected` | Yes; changes with G1 |
| Mismatched parent fields | `test_mismatched_parent_identity_is_rejected` (×3) | Yes; changes with G1 |
| Null = null linkage | `test_null_parent_identity_values_compare_equal` | Yes, but uses invalid data (4.1) |
| Linkage doesn't modify input | `test_linkage_validation_does_not_modify_identity_fields` | Yes |
| `primary_view` required | `test_multiview_requires_explicit_primary_view` | Yes |

### Tests that change with the fixes
- **G1:** the linkage tests should expect an error. Add a case where an instance has a null `role_key`.
- **G4, G5, 2.2:** the metadata test should assert `rejection_counts` by level and reason, the per-value counts, and that missing provenance fails.
- **G4, G6, 2.1:** the rejected-output tests need the level and required columns, plus an overlap test.
- **1.3, 2.3:** the `AdapterResult` tests and the input-unchanged test.

### Issues

**4.1 The test fixtures don't follow the Alibaba GPU 2020 contract (Medium)**
- **What (each point confirmed by running it):**
  - `test_null_parent_identity_values_compare_equal` sets `recurrence_key = None` on a role row that has no `exclusion_reason = no_recurrence_key`. `validate_adapter_output` rejects that row; the test passes only because it calls the linkage function directly.
  - The instance fixture has no `event_time_us` (schema §7).
  - `TEST_CAPABILITIES` has `instance_event_time_semantics = None` and `allowed_exclusion_reasons = ()`.
- **Why it matters:** G3 can't be tested with these fixtures; the null-key test covers a case that can't occur in real output; and Task 3 will likely copy these fixtures.
- **Fix:**
  - Profile: set `instance_event_time_semantics = "parent_job_submission"`, and include `no_recurrence_key` in `allowed_exclusion_reasons`.
  - Instance fixture: add `event_time_us = 100` (the role's `start_time_us`).
  - Null-key test: set `exclusion_reason = "no_recurrence_key"` on the role row and run the test through `adapt_sources`.
- **Where:** `TEST_CAPABILITIES` (line 21), `make_instance_view` (line 107), `test_null_parent_identity_values_compare_equal`.
- **Affects:** G3 testing, Task 3.

### Summary
| # | Issue | Severity | Affects |
|---|---|---|---|
| 4.1 | Fixtures don't follow the Alibaba GPU 2020 contract | Medium | G3 testing, Task 3 |

---

## 5. Task 1 issue gaps (G1–G6)

These are gaps in the Task 1 issue text compared with the frozen design. They are not mistakes in the PR. They are listed here because Task 3 or Task 4 depends on them, so PR #91 should fix them. The remaining gaps are tracked elsewhere: the Task 3 items are in the "Notes from the Task 1 (PR #91) review" on #79; the issue-text corrections (wrong references in #66, "Task 11a" vs Task 8, and wording in #66 that should match the corrected PR) are edited directly in the GitHub issues; the design-doc status lines are updated in Task 13.

**G1 The linkage check rejects bad rows instead of failing (High)**
- **Issue / PR:** the issue says "orphan and mismatched rows are rejected". The PR adds the rejection reasons `missing_parent_role` and `parent_identity_mismatch`.
- **Design:** the only rejection reason is `missing_submission_time` (schema §9.5), and orphan instance rows must not exist (framework §9.2).
- **Why it matters:** Task 3 requires zero orphan and zero mismatched rows (#79). Rejecting these rows hides adapter bugs and changes the rejected counts that Task 8 checks (3,663 / 6,942 / 111,219).
- **Fix:** raise an error with counts and sample `instance_id`s; add no new rejection reasons.
- **Where:** `validation.py`, `validate_role_instance_linkage` (304–504): change the return value and the reason labels (lines 486–499), the docstring (lines 319–320) and the two linkage tests.
- **Affects:** Task 3, Task 8.

**G2 The linkage check isn't run automatically (Medium)**
- **Design:** framework §7.2 lists parent linkage as a required check.
- **Why it matters:** as written, each adapter has to remember to call it.
- **Fix:** `adapt_sources` runs it on the validated views whenever both views are present.
- **Where:** `base.py:350`, after the per-view loop (~519) and before `validate_rejected_output` (523). Add a test where an orphan instance fails `adapt_sources`.
- **Affects:** Task 3.

**G3 The instance `event_time_us` contract isn't checked (Medium)**
- **Design:** framework §7.2 and schema §7. With `parent_job_submission`, an instance's `event_time_us` must be non-null and equal to the parent role's `start_time_us`.
- **Why it matters:** Task 3 requires this (#79), but no shared check enforces it; PR #70 checks only `role_key` and `instance_id`.
- **Fix:** add the comparison to the linkage check, enabled by the profile.
- **Where:** `validation.py:304`: add `start_time_us` to the parent lookup (~371–389) and a `capabilities` argument. `base.py:350`: pass `self.capabilities`.
- **Affects:** Task 3.

**G4 The rejected output has no levels (Medium)**
- **Design:** metadata reports rejected job, role and instance counts per reason (framework §6, schema §9.5).
- **Why it matters:** Task 3 fills these counts (#79), but the PR has only a single total.
- **Fix:** require a level column on rejected rows, and report `rejection_counts = {level: {reason: count}}`.
- **Where:** `validation.py:217` (level column); `base.py:325` (counts).
- **Affects:** Task 3.

**G5 Metadata breakdowns are missing (Medium)**
- **Design:** framework §6 and planning item 4 require counts per `validity_status`, `cpu_validity_status`, `memory_validity_status` and `exclusion_reason`.
- **Why it matters:** Task 3 fills these counts, and Task 4 checks the eligible population (461,900) and the missing-CPU count. The PR has no per-resource counts, and exclusions are totals.
- **Fix:** per-value counts for each view. Count exclusions only on the evaluation-level view, because a null `exclusion_reason` on an instance row doesn't mean "eligible" (framework §9.4).
- **Where:** `base.py:225–345` (validity loop 258–273, exclusions 279–287); update `test_metadata_contains_required_framework_fields`.
- **Affects:** Task 3, Task 4.

**G6 The rejected output has no hook for required columns (Medium)**
- **Design:** rejected rows keep identity fields "where possible" and source traceability (framework §4.4, schema §9.5), but the design doesn't name the columns.
- **Why it matters:** Task 3 must declare the Alibaba GPU 2020 columns, and without a hook it would have to edit the shared validator.
- **Fix:** `validate_rejected_output` accepts per-level required columns declared by the adapter. Task 3 supplies the values (see the plan doc).
- **Where:** `validation.py:217` (`required_columns` argument); `BaseDatasetAdapter.rejected_required_columns`, passed in at `base.py:523`.
- **Affects:** Task 3.

### Summary
| # | Gap | Severity | Affects |
|---|---|---|---|
| G1 | Linkage rejects bad rows instead of failing | High | Task 3, Task 8 |
| G2 | Linkage not run automatically | Medium | Task 3 |
| G3 | Instance `event_time_us` not checked | Medium | Task 3 |
| G4 | Rejected output has no levels | Medium | Task 3 |
| G5 | Metadata breakdowns missing | Medium | Task 3, Task 4 |
| G6 | No hook for required rejected-row columns | Medium | Task 3 |

