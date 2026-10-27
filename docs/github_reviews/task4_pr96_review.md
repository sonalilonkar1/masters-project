# Task 4 (#81) Review: PR #96 — Shared Chronological Splits, History and Next-Occurrence Targets

**Branch:** `issue-81-target-builder` (commit `31e5edd`, based on `main` at `c2ae87f`)
**Status:** Review notes only; no fixes applied.
**Tests on branch:** 605 passed, 1 skipped (`tests/test_ml_prep.py` not run locally because `sklearn` isn't installed). Includes the 61 new tests and the Google regression tests `tests/test_split_utils.py` and `tests/test_google_canonical_contract.py`.
**Full-data run:** during this review, `build_targets` was run on the shared Task 3 `role_occurrence.parquet` (built from `c2ae87f`; `--verify` passed), with that build's `metadata.json` as `verified_source_metadata`. About 65 s and 6.3 GB peak memory. Nothing was written to disk.

**Verdict:** the target builder meets every rule in issue #81, and the full-data results match the reference once the final 256-row `multi_attempt_worker` exclusion is taken into account (I1). No logic errors were found. One PR issue (I1) and four issue gaps (G1–G4) must be fixed in PR #96 before merge; one set of wording edits (G5) goes to issue #81.

**Sections:**
1. Fix list
2. PR issues: the PR does not fully do what the issue asks
3. Issue gaps: things issue #81 missed
4. What the PR achieves
5. Detailed checks

---

## 1. Fix list

| # | Kind | Finding | Severity | Fix in | When |
|---|---|---|---|---|---|
| I1 | PR issue | The difference from the reference counts is not explained | Low | `target_builder.py` line 299; PR description | Before merge |
| G1 | Issue gap | No script to build the train, validation and test tables | Medium | New `scripts/build_alibaba_gpu_2020_targets.py`; tests; PR description | Before merge |
| G2 | Issue gap | No checksums for the tables | Medium | The G1 script writes `SHA256SUMS` | Before merge |
| G3 | Issue gap | The history rule cannot be reused by Task 6 | Medium | `target_builder.py`: public function replacing `_history` (lines 117–147); test | Before merge |
| G4 | Issue gap | Output paths in the metadata are absolute | Low | `target_builder.py` lines 326–329; one test | Before merge |
| G5 | Issue wording | #81 names the wrong verification task and its PR boundary leaves out G1–G3 | — | Issue #81 on GitHub | Now, no code change |

Every finding below uses the same layout: **Problem, Evidence, Fix, Where, Tests, Why in this PR, Affects.**

---

## 2. PR issues

Something issue #81 asks for that the PR does not fully do.

### I1. The difference from the reference counts is not explained (Low)

| | |
|---|---|
| **Problem** | **Not a logic or pipeline error:** the counts are correct, and only the explanation is missing. Acceptance criterion 5 of #81: the validation and test rows with an in-split next occurrence must be reconciled with the reference counts (about 42,104 and 44,087, counted before the final 256-row `multi_attempt_worker` exclusion), and "any difference must be explained in the metadata". The PR records the differences in `metadata["reference_comparison"]`, but `reference_notes` only says the exclusion may change counts and that "exact historical attribution is unavailable". The PR description does not mention the reference counts. |
| **Evidence** | The reference counts come from the earlier feasibility analysis (`docs/data/alibaba_gpu_2020_evidence_and_limitations.md`, lines 195–197), run before the final exclusion. The PR's code was rerun with the 256 roles excluded only by `multi_attempt_worker` (they pass every other rule) made eligible again: see the table below. Validation is reproduced exactly. The remaining one-row difference (test −1, validation cross-split +1) is one row at the validation/test boundary: `chronological_split` keeps whole timestamp groups and places the boundary at the group nearest 85% of rows, and the earlier analysis placed it one group differently. This is within the issue's "approximately". |
| **Fix** | Replace the last sentence of `reference_notes` ("Structural successor counts … exact historical attribution is unavailable from the final eligible population alone.") with: "The final counts are lower because 256 roles are excluded by `multi_attempt_worker`. Restoring them reproduces validation exactly (42,104) and test within one row (44,086 against 44,087); that row lies at the validation/test boundary, which the reference analysis placed one timestamp group differently." Keep the note that structural successor counts and available CPU/memory counts are reported separately. Add the table below to the PR description. |
| **Where** | `src/features/target_builder.py` line 299; PR description |
| **Tests** | None needed (text only) |
| **Why in this PR** | It is an explicit acceptance criterion of #81, and the fix is one sentence plus one paragraph |
| **Affects** | Task 8 (verifies the metadata against criterion 5) |

| Split | Reference | PR #96 | Difference | 256 roles restored |
|---|---|---|---|---|
| Validation | 42,104 | 42,069 | −35 | 42,104 |
| Test | 44,087 | 44,053 | −34 | 44,086 |
| Validation, next run in test (cross-split) | 7,742 | 7,736 | −6 | 7,743 |
| Same-second (validation / test) | 245 / 251 | 245 / 251 | 0 / 0 | 245 / 251 |

---

## 3. Issue gaps

Something the work needs that issue #81 missed when it was written. The PR follows the issue, so a gap is **not the author's mistake**. It is still right to correct G1–G4 in PR #96: none of them changes a frozen design decision (split, history and target rules, statuses, isolation), and Tasks 6 and 7 depend on them with no time for a separate PR.

**Why #81 missed them:** it asks to "write the Alibaba GPU 2020 train, validation, and test tables" with metadata and output paths, but its Pull-Request Boundary allows only "the target-builder module [and] target-builder tests". It also predates the Task 6 (#87) and Task 7 (#89) issues, which ask Task 4 for a reusable history rule and checksums.

### G1. No script to build the train, validation and test tables (Medium)

| | |
|---|---|
| **Problem** | `build_targets` and `write_target_tables` exist, but nothing in the repo runs them on the Task 3 data. The tables exist only on the author's machine, in a folder the PR does not name, built **before** the final commit `31e5edd`. The call used (input, whether `verified_source_metadata` was passed, output folder) is not recorded, and `metadata.json` records the Task 3 source commit but not the Task 4 commit. |
| **Evidence** | PR description: "Dataset results are from the verified full-data run before the provenance correction … without regenerating the outputs"; "Stores generated tables and metadata in a separate gitignored directory". |
| **Fix** | New script that every teammate runs locally; no Drive copy (see the comparison below). Usage: `python3 scripts/build_alibaba_gpu_2020_targets.py [--canonical-dir DIR] [--out-dir DIR] [--force] [--allow-dirty]`. Steps are in the table below. After merge, the author runs it from the merge commit, checks the printed counts against §5.2 and posts the `SHA256SUMS` (G2); teammates run the same command. |
| **Where** | New `scripts/build_alibaba_gpu_2020_targets.py`; new script tests; PR description (command, output folder, "run locally after pulling `main`") |
| **Tests** | On a small fixture Task 3 folder: writes the three tables and `metadata.json` with the `build` block and `source_provenance`. Refuses a dirty tree without `--allow-dirty` and an existing output folder without `--force`. A Task 3 folder that fails `--verify` stops the script before anything is written. |
| **Why in this PR** | Task 6 is blocked on the tables (#87: "Read Alibaba GPU 2020 train and validation tables produced by Task 4"), and Task 7 uses them in all four phases (#89). Without a script each consumer writes their own loading code, with their own input, folder and provenance, and the existing tables cannot be shown to match the merged code. |
| **Affects** | Task 6, Task 7 (build and use the tables), Task 8 (checks the Task 3 and Task 4 commits) |

Script steps:

| Step | Does | If it fails |
|---|---|---|
| 1. Pre-checks | Output folder (default `data/processed/alibaba_gpu_v2020_targets/`, gitignored) does not exist, or `--force`; no uncommitted changes to tracked files, or `--allow-dirty` | Stop; nothing read or written |
| 2. Verify input | `scripts/build_alibaba_gpu_2020_canonical.py --verify <canonical-dir>` (default `data/processed/alibaba_gpu_v2020/`) | Stop, non-zero exit; nothing written |
| 3. Read | `role_occurrence.parquet` and `metadata.json` only, never `instance.parquet` or `rejected.parquet` | — |
| 4. Build | `build_targets(roles, ALIBABA_GPU_2020_CAPABILITIES, verified_source_metadata=metadata)` | Stop; nothing written |
| 5. Build block | Add Task 4 `code_commit`, `code_dirty`, Python, pandas and pyarrow versions (same fields as Task 3) | — |
| 6. Write | `write_target_tables`; with `--force`, replace an existing folder only after the new one is complete | Existing output unchanged; no partial folder |
| 7. Checksums | `SHA256SUMS` (G2) | — |
| 8. Summary | Per split: rows, CPU and memory status counts, same-second counts, reference comparison, checksums | — |

Why a local script rather than a Drive copy:

| | Drive copy (as for Task 3) | Local script (recommended) |
|---|---|---|
| Build cost | — | About 1 minute and 6.3 GB, from the Task 3 data everyone already has (Task 3's build needs 29 GB, which is why it is shared) |
| Matches the merged code | Only if re-uploaded after every change | Always |
| Upload and versioning | Needed | None |

### G2. No checksums for the tables (Medium)

| | |
|---|---|
| **Problem** | Nothing records checksums of `train.parquet`, `validation.parquet`, `test.parquet` and `metadata.json`, so no one can confirm two builds are the same. With local builds (G1) this matters more. |
| **Evidence** | Task 6 metadata must record "input artifact paths and checksums" (#87). Task 7 PR 1 trains on train and validation and "must never read the test table"; Phase 4 reads test later, possibly from a build on another machine, and the decision manifest locks everything else by checksum (#89). |
| **Fix** | The G1 script writes `SHA256SUMS` for the four files in the Task 3 format (`<sha256>  <file name>`, sorted), so `shasum -a 256 -c SHA256SUMS` works, and prints the checksums. Parquet bytes match only with the same pandas and pyarrow versions (recorded in the `build` block); if they differ, compare `metadata.json` and the printed counts. |
| **Where** | `scripts/build_alibaba_gpu_2020_targets.py` (step 7) |
| **Tests** | The script test checks `SHA256SUMS` lists the four files and `shasum -c` passes. |
| **Why in this PR** | Task 6 and Task 7 both need the checksums, and they come from the same script as G1. |
| **Affects** | Task 6 (records input checksums), Task 7 (decision manifest; checks the test table), Task 8 |

### G3. The history rule cannot be reused by Task 6 (Medium)

| | |
|---|---|
| **Problem** | The point-in-time history rule is the private `_history`, which returns only counts. Task 6 must compute Mean, P90, P95 and P99 from exactly the same earlier runs, so it would have to write a second copy of the rule. |
| **Evidence** | #87: "Statistic counts must equal the corresponding Task 4 history counts" and "Reuse the Task 4 history-selection function if available"; Risks: reimplementing it "could produce inconsistent counts". #81 itself warns of `<=` versus `<` off-by-one errors. On the full data the history holds about 176 million earlier-run entries per resource (largest recurrence 17,290 runs). |
| **Fix** | Make the sweep public, keeping today's rule and order (same `recurrence_key`, eligible rows, usable resource value, `end_time_us ≤ start_time_us`; order `start_time_us`, `occurrence_id`, `role_key`). Because of the size it must **stream** rather than return a list per row: for example a generator that walks each recurrence once and yields, for each eligible row, its `role_key` and the values of the earlier runs released so far (read-only). `build_targets` takes the history counts from it, so the counts and Task 6's statistics share one implementation. The §5.2 full-data figures must not change. |
| **Where** | `src/features/target_builder.py`, replacing `_history` (lines 117–147) |
| **Tests** | On the fixture of `test_group_isolation_and_history_against_independent_brute_force_oracle`: the yielded values per row equal the brute-force set of earlier runs, and their lengths equal `cpu_history_count` and `memory_history_count`. |
| **Why in this PR** | Task 6 starts next and #87 asks for this function; adding it later means changing Task 4 code during Task 6. |
| **Affects** | Task 6 (history statistics), Task 7 (uses Task 6's statistics as features) |

### G4. Output paths in the metadata are absolute (Low)

| | |
|---|---|
| **Problem** | `write_target_tables` stores full paths in `output_paths`, for example `/Users/<name>/.../train.parquet`. Builds of the same commits on two machines therefore give different `metadata.json` files and different checksums (G2). |
| **Evidence** | Lines 326–329: `str(output_dir / f"{s}.parquet")`. |
| **Fix** | Store file names relative to the output folder: `train.parquet`, `validation.parquet`, `test.parquet`, `metadata.json`. |
| **Where** | `src/features/target_builder.py` lines 326–329 |
| **Tests** | Update `test_writer_round_trip_excluded_rows_paths_and_existing_destination`, which reads the tables through these paths, to join them with the output folder; check the paths are relative. |
| **Why in this PR** | With local builds (G1), identical builds must give identical metadata and checksums. |
| **Affects** | Task 6, Task 7, Task 8 (comparing builds) |

### G5. Wording in issue #81 (edit on GitHub; no code change)

| # | Where in #81 | Current text | Change to | Why |
|---|---|---|---|---|
| G5.1 | Blocks | "**Task 11a:** Verifies the split and target metadata." | "**Task 8:** Verifies the split and target metadata." | The final verification task on GitHub is Task 8 ("Alibaba GPU 2020 Final Verification and Artifact Validation"); same fix as W2 for #77 |
| G5.2 | Handoff | "Split and target metadata → Task 11a." | "Split and target metadata → Task 8." | Same as G5.1 |
| G5.3 | Pull-Request Boundary | "The target-builder module. Target-builder tests." | Add "A public history-selection function, and a build script that writes the tables and `SHA256SUMS` (`scripts/build_alibaba_gpu_2020_targets.py`), with tests." | Matches G1–G3 |

---

## 4. What the PR achieves

**Before the PR:** splits, history and next-occurrence targets existed only inside Google Notebook 04. Task 3 delivers the Alibaba GPU 2020 `role_occurrence` view, but nothing turned it into train, validation and test tables.

**After the PR:** a shared, profile-driven module, `src/features/target_builder.py`, with no change to Google behaviour (`split_utils.py` untouched):
- **Splits:** chronological 70/15/15 through the existing `chronological_split`; whole jobs stay in one split; `val` becomes `validation`; excluded rows get no split.
- **History:** `cpu_history_count` and `memory_history_count`, counting eligible earlier runs of the same recurrence that finished at or before the current submission, CPU and memory separately.
- **Targets:** `actual_cpu` (next run's lifetime-average CPU, `percent_of_vcpu`) and `actual_memory` (next run's peak memory, `gb`), from the immediate next eligible run only; never across splits; never skipping a missing value.
- **Statuses:** the five frozen statuses per resource, with a runtime check that a value exists exactly when the status is `available`.
- **Same-second flag:** `next_occurrence_same_second`; flagged rows kept and counted.
- **Metadata and writer:** split boundaries, per-split row and status counts, same-second counts, reference comparison, verified Task 3 provenance; the writer publishes through a staging folder and leaves no partial output.
- **Tests:** 61 synthetic tests covering every test the issue lists, plus an independent brute-force history check and a leakage test.

---

## 5. Detailed checks

### 5.1 Module against issue #81
| Requirement | Met? | Where / evidence |
|---|---|---|
| Accept only `role_occurrence` rows; clear error otherwise | Yes | `_validate` (80–81) |
| Never read the rejected output | Yes | Only the input frame is read |
| Excluded rows: null split, no history, no target | Yes | Full data: 792,208 excluded rows, none with a split |
| `target_split_isolation`, `evaluation_record_level` from the profile | Yes | 66–67, 244 |
| `chronological_split(time_col="start_time_us", id_col="role_key")`, defaults, unchanged | Yes | 202–203 |
| `val` → `validation`; only `train`, `validation`, `test` in output | Yes | 206, 260 |
| Split boundaries, timestamps and row counts in metadata | Yes | `metadata["split"]` |
| History: same `recurrence_key`, eligible, resource usable, `end_time_us ≤ start_time_us`, earlier or same split | Yes | `_history` (117–147). `partial` with a value counts as usable, as output contract §8.3 states |
| CPU and memory history independent | Yes | Separate masks (211–216) |
| Target order `start_time_us`, `occurrence_id`, `role_key`; immediate successor; no skipping | Yes | 209–210, 238–239 |
| Cross-split status overrides resource status | Yes | 244–246 |
| No imputation; null value unless `available` | Yes | Runtime check 254–255 |
| Same-second flag; rows kept; counts in metadata | Yes | 226–229; `per_split` |
| Metadata: per-split rows, CPU and memory status counts, same-second counts, output paths | Yes | `per_split`; paths added by the writer (see G4 for relative paths) |
| Reference counts reconciled and explained | Partly | See I1 |
| `split_utils.py` and Google behaviour unchanged | Yes | Two new files only; Google tests pass |

### 5.2 Full-data results
Identical to the table in the PR description. The PR's figures came from a run before `31e5edd`; that commit does not change any result.

The split is 70/15/15 of the 461,900 eligible rows (323,329 / 69,286 / 69,285). Not every row has a target: "In-split next occurrence" counts the rows that can be scored, and the rest are the last run of their recurrence or have their next run in a later split. The 42,069 and 44,053 compared with the reference in I1 are these scorable rows, not the split sizes.

| Split | Rows | Occurrences | In-split next occurrence | CPU `available` | Memory `available` | Same-second |
|---|---|---|---|---|---|---|
| train | 323,329 | 319,186 | 220,832 | 220,299 | 220,832 | 2,006 |
| validation | 69,286 | 68,549 | 42,069 | 41,913 | 42,069 | 245 |
| test | 69,285 | 68,677 | 44,053 | 44,045 | 44,053 | 251 |

- Boundaries (`start_time_us`): train up to 5,308,816,000,000; validation 5,308,817,000,000–5,884,553,000,000; test from 5,884,564,000,000.
- `next_occurrence_in_other_split`: 8,842 train, 7,736 validation, 0 test (same for CPU and memory).
- CPU `next_occurrence_ineligible_resource` (next run has no CPU): 533 / 156 / 8. Memory: 0.
- `no_next_occurrence`: 93,655 / 19,481 / 25,232.
- 0 jobs span two splits. 30% of eligible rows have `cpu_history_count = 0`.

### 5.3 Tests against issue #81's test list
| Required test | Covered by |
|---|---|
| Five statuses, CPU and memory independently | `test_all_five_statuses_independently` |
| Deterministic next-occurrence ordering | `test_deterministic_ties_indexes_and_zero_duration_predecessors` |
| No skipping past an invalid resource value | `test_invalid_successor_never_skipped_and_current_value_does_not_gate_target` |
| Prior run ending after the current start excluded from history | `test_history_completion_boundary_nulls_overlap_and_resource_independence` |
| All roles of one job in one split | `test_all_roles_and_timestamp_groups_stay_in_one_split` |
| Split isolation and null cross-split targets | `test_history_crosses_earlier_splits_but_targets_do_not` |
| `validation`, never `val` | `test_split_defaults_metadata_and_input_preservation` |
| Same-second flagging | `test_same_second_uses_buckets_and_keeps_missing_resource_targets`, `test_successor_timestamp_shift_preserves_integer_precision` |
| Missing CPU keeps memory history and targets | `test_all_five_statuses_independently`, `test_history_completion_boundary_nulls_overlap_and_resource_independence` |
| Excluded rows: null split, no history, no target | `test_excluded_rows_have_no_derived_values_and_never_contribute` |
| Non-`role_occurrence` rows rejected | `test_invalid_inputs_fail_clearly`, `test_mixed_excluded_audit_row_is_still_rejected` |
| No history or target from a later split | `test_later_split_measurements_cannot_change_earlier_features_or_targets` |
| `test_split_utils.py`, `test_google_canonical_contract.py` unchanged and passing | Run on the branch |

Also covered: history counts against a brute-force check, partial values, input not mutated, null placeholder columns, too few rows or timestamps, profile-driven behaviour, provenance validation, and the writer (round trip, existing folder refused, no partial output on failure). Tests to add or change are listed under G1–G4.
