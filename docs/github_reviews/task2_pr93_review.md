# Task 2 (#77) Review: PR #93 — Alibaba GPU 2020 Source Setup and Loader

**Branch:** `feature/task2-alibaba-gpu-2020-loader` (commit `1cbaa9a`)
**Status:** Review notes only; no fixes applied. See the fix list below.
**Tests on branch:** 310 passed, 1 skipped (`tests/test_ml_prep.py` skipped locally because `sklearn` isn't installed). The skipped test is the opt-in full-data test; the raw tables are not downloaded locally, so the loads on the real files are not re-run here. The 18 manifest checksums were checked against the official README (§3).

**Sections:**
1–5 review the PR's files, one file per section.
6 lists gaps in the Task 2 issue text compared with the frozen design.

## Fix list for PR #93

Every finding in one place, grouped by where it comes from. Details are in the section named in the last column.

**A. PR issues** (the code does not do what the issue asks, or does it badly)
| # | Finding | Severity | Affects | Details |
|---|---|---|---|---|
| 1.1 | Every load re-hashes the whole file | Low | Task 3 | §1 |
| 5.1 | Full-data test skips the instance and sensor tables | Low | Task 3, Task 8 | §5 |

**B. Task 2 issue gaps** (the design requires it, the issue left it out, so the PR follows the issue; still fixed in this PR)
| # | Finding | Severity | Affects | Details |
|---|---|---|---|---|
| G1 | Loader doesn't hand provenance to the adapter | Medium | Task 3, Task 8 | §6.1 |

**C. Issue wording fixes** (edit #77 on GitHub; no PR change)
| # | Finding | Details |
|---|---|---|
| W1 | Row-count check points to the wrong document | §6.2 |
| W2 | "Task 11a" should be Task 8 | §6.2 |

---

## 1. Source loader (`src/sources/alibaba_gpu_2020.py`)

### About
Loads the six raw Alibaba GPU 2020 tables (`pai_job_table`, `pai_task_table`, `pai_instance_table`, `pai_sensor_table`, `pai_group_tag_table`, `pai_machine_spec`). It verifies each file against the committed manifest, reads it with explicit column names and types, and adds `source_row_number`. It does no joins, identity construction or canonical mapping (Task 3).

### What it adds
| Part | Description |
|---|---|
| `SCHEMAS` (44–108) | Column names and types per table, in `.header` order. IDs, names, status and categories are `string`; times, plans and usage are `float64` (they have empty fields); `cap_cpu`, `cap_mem`, `cap_gpu` are `int64` |
| `verify_table` / `verify_sources` (183–236) | Check the CSV (existence, size, SHA-256, line count) and the header file (size, SHA-256), check the header columns match `SCHEMAS`, and optionally check the archive. Any failure raises `SourceVerificationError` |
| `_read_options` (239–269) | `QUOTE_NONE` (one row is one line), blank lines kept, only empty fields are missing, `float_precision="round_trip"` |
| `load_table` / `iter_table_chunks` (287–354) | Verify, read in file order, assign `source_row_number` = 1…N (continuing across chunks), then check the loaded row count |

### Required behaviour check
Rules from the frozen design (`adapter_framework.md` §9.2, `canonical_workload_schema.md` §7, D-21) and from the Task 2 GitHub issue (#77), and whether the loader follows them:

| Rule | Source | Met? |
|---|---|---|
| `source_row_number` is the data-line number in the checksum-verified, decompressed file | Design, Task 2 issue | Yes: assigned while reading, never after filtering, sorting or joining |
| The loader keeps source-file order | Design, Task 2 issue | Yes |
| `source_row_number` is the same across full, column-selected, repeated and chunked loads | Task 2 issue | Yes |
| Explicit column names and types for every table | Task 2 issue | Yes (`SCHEMAS`) |
| No joins, canonical identities or mapping | Task 2 issue, PR boundary | Yes |

The design requires `source_row_number` only for the instance table; the loader adds it to all six tables, which is harmless.

### Issues

**1.1 Every load re-hashes the whole file (Low)**
- **What:** with `verify=True` (the default), every `load_table` / `iter_table_chunks` call runs `verify_table`, which reads and hashes the full CSV before reading it again to parse.
- **Why it matters:** Task 3 loads the large instance and sensor tables more than once (different column selections, chunked passes). Each call re-hashes gigabytes for no new information. The only way around it is `verify=False`, which also turns off the post-read row-count check.
- **Fix:** remember files already verified in this process, keyed by `(resolved path, size, mtime_ns)`, and skip the hash when the key matches. The row-count check after reading still runs.
- **Where:** `verify_table` (183–222), used by `load_table` (305–306) and `iter_table_chunks` (339–340). Add one test: two loads hash the file once, and a modified file is hashed again. Update the setup doc line "Every call verifies the file against the manifest first" (`docs/data/alibaba_gpu_2020_source_setup.md` §4).
- **Affects:** Task 3.

### Summary
| # | Issue | Severity | Affects |
|---|---|---|---|
| 1.1 | Every load re-hashes the whole file | Low | Task 3 |

---

## 2. Verification script (`scripts/verify_data_setup.py`)

### About
The repository's data-setup check. Before the PR it only smoke-loaded the Google Kaggle subset. The PR adds an Alibaba GPU 2020 mode that runs the loader's verification over all six tables.

### Changes in PR #93
| Change | Description |
|---|---|
| `--dataset` (`google_kaggle_subset` default, `alibaba_gpu_2020`) | Selects the mode; the default Google smoke test is unchanged (moved into `verify_google_kaggle_subset`) |
| `verify_alibaba_gpu_2020` (40–76) | Runs `verify_table` per table, prints `OK` / `FAIL` with row count and short SHA-256, continues past failures, returns exit code 1 if any table failed |
| `--check-archives` | Also verifies the downloaded `.tar.gz` archives |
| `--load` | Also loads each table (`verify=False`, since it was just verified) and compares the loaded row count with the verified line count |
| `--raw-dir` | Overrides the default `data/raw/alibaba_gpu_2020/` |
| `sys.exit(main())` | The exit code now reflects the result |

### Required behaviour check
Checks that the Task 2 GitHub issue (#77) requires the script to run:

| Required check | How the script does it | Met? |
|---|---|---|
| File exists | `verify_table` raises when the CSV, header or archive is missing | Yes |
| Checksum matches | SHA-256 of each CSV and header file (and each archive with `--check-archives`) against the manifest | Yes |
| Decompression status | The decompressed CSV's own size, SHA-256 and line count | Yes |
| Expected table sizes | Line count against the manifest; with `--load`, the loaded row count as well | Yes |
| Failures are clear | Prints `FAIL <table>: <reason>` and exits with code 1 | Yes |

### Issues
None.

---

## 3. Checksum manifest (`config/alibaba_gpu_2020_sources.json`)

### About
The committed record of what the six verified source tables must look like. The loader and the verification script read it; Task 8 reuses it for final reproducibility checks.

### Contents
| Part | Per table | Source of the values |
|---|---|---|
| `archive` | File (`archives/<table>.tar.gz`), download URL, SHA-256, size | SHA-256 from the official README; size measured |
| `header` | File, URL, SHA-256, size, column list | SHA-256 from the official README; size and columns from the official `.header` file |
| `csv` | File, SHA-256, size, `data_lines` | SHA-256 from the official README; size and line count measured |
| Top level | `dataset_id = alibaba_gpu_v2020`, `source_version`, README link, checksum algorithm, `source_row_number` definition | — |

### Required behaviour check
Checked during this review against the official `cluster-trace-gpu-v2020` README and `.header` files:

| Check | Result |
|---|---|
| All 18 SHA-256 values (archive, header, CSV × 6 tables) match the official README | Yes, 18/18 |
| Header SHA-256, size and column list match the downloaded official `.header` files | Yes, all six |
| `data_lines` match the row counts in `docs/data/alibaba_dataset_selection_feasibility.md` (job and task also in `alibaba_gpu_2020_evidence_and_limitations.md`) | Yes: 1,055,501 / 1,261,050 / 7,522,002 / 3,033,232 / 1,055,032 / 1,897 |
| Covers all six required tables (Task 2 issue) | Yes; `pai_machine_metric` is correctly left out |

CSV sizes and line counts can only be confirmed against the downloaded data, which isn't available locally, but the CSV SHA-256 values are the official ones, so a file that passes the checksum also has the recorded size and line count.

### Issues
None.

---

## 4. Setup documentation (`docs/data/alibaba_gpu_2020_source_setup.md`)

### About
The instructions a teammate follows on a fresh clone to download, verify and load the six tables.

### Contents
| Section | Covers |
|---|---|
| 1. Tables | The six tables with row counts, CSV and archive sizes; `pai_machine_metric` left out; the CSVs have no header line |
| 2. Download and decompression | `curl` loop for archives and `.header` files, `tar -xzf`, expected layout under `data/raw/alibaba_gpu_2020/` (gitignored) |
| 3. Verification | `verify_data_setup.py --dataset alibaba_gpu_2020 --check-archives --load` and what it checks |
| 4. Loading | `load_table` / `iter_table_chunks` examples, `source_row_number` definition, missing values, quoting, exact float parsing, column types, empty-field counts per column |
| 5. Disk and memory | About 4.65 GB on disk; peak memory per table (instance 3.5–3.8 GiB, sensor about 2.2 GiB) |
| 6. Optional cache | Parquet under `data/processed/`, not committed, must keep the loader's `source_row_number` |
| 7. Tests | Fixture tests and the opt-in full-data test |

### Required behaviour check
Documentation items required by the Task 2 GitHub issue (#77):

| Required item | Where in the doc | Met? |
|---|---|---|
| Raw-data location, kept outside Git | §2 | Yes |
| Download instructions | §2 (URLs and file names match the official README) | Yes |
| Decompression instructions | §2 (extracts into the folder the manifest expects) | Yes |
| Source-table schemas | §4 Column types | Yes |
| Disk requirements | §5 | Yes |
| Memory requirements | §5 | Yes |
| Optional local cache, not committed | §6 | Yes |

### Issues
None. If issue 1.1 is fixed, the §4 line "Every call verifies the file against the manifest first" changes with it (listed under 1.1).

---

## 5. Tests (`tests/test_alibaba_gpu_2020_loader.py`)

### About
37 tests run on small headerless fixture tables written to a temp folder, with a manifest built from those fixtures. One extra test runs on the real tables only when they are downloaded and `TRACEADVISOR_FULL_DATA_TESTS=1` is set.

### Required behaviour check
Tests required by the Task 2 GitHub issue (#77):

| Required test | Test(s) | Met? |
|---|---|---|
| Column names and types | `test_full_load_columns_types_order_and_row_numbers` (all six tables) | Yes |
| Source order | same test (values checked line by line) | Yes |
| Repeated loads | `test_repeated_loads_are_identical` | Yes |
| Full-table and column-selected loads | `test_column_selection_keeps_row_numbers` | Yes |
| Chunked loads | `test_chunked_load_equals_full_load` (chunk sizes 1, 2, 3, 5, 100), `test_chunked_column_selection_equals_full_load` | Yes |
| Stable `source_row_number` | all of the above compare `source_row_number` | Yes |
| Checksum failure with a clear error | `test_modified_file_fails_checksum`, `test_truncated_file_fails`, `test_missing_file_fails`, archive and header mismatch tests | Yes |

Also covered: text `NA` / `None` kept as text, exact float parsing, quotes never joining lines, manifest errors, the post-read row-count check, and the verify script (pass, fail, `--load` guard, exit code, unchanged Google mode).

### Tests that change with the fixes
- 1.1: add a test that two loads hash an unchanged file once and a modified file again.
- G1: add a test for the provenance helper, including a failing (missing) file.
- 5.1: extend `test_real_tables_verify_and_load`.

### Issues

**5.1 The full-data test skips the instance and sensor tables (Low)**
- **What:** `test_real_tables_verify_and_load` verifies all six files, but only loads the job, task, group tag and machine spec tables. The PR description says full, column-selected, chunked and repeated loads were compared on the real instance and sensor tables, but that check is not in the committed test.
- **Why it matters:** `pai_instance_table` is the table whose `source_row_number` the frozen instance identity depends on (D-21), and it is the one most likely to be loaded in chunks. Task 8 reruns this test for reproducibility, so the check the author ran by hand should be repeatable.
- **Fix:** in the full-data test, load `pai_instance_table` and `pai_sensor_table` with a small column selection (for example `job_name` only, to keep memory low), check `source_row_number` = 1…N, and check that `iter_table_chunks` with the same columns gives an identical frame.
- **Where:** `test_real_tables_verify_and_load` (lines 301–311).
- **Affects:** Task 3, Task 8.

### Summary
| # | Issue | Severity | Affects |
|---|---|---|---|
| 5.1 | Full-data test skips the instance and sensor tables | Low | Task 3, Task 8 |

---

## 6. Task 2 issue gaps

A gap is something the frozen design requires that the Task 2 GitHub issue (#77) left out. The PR follows the issue, so a gap is not the PR author's mistake. Gaps are still fixed in PR #93, because Task 3 needs them and there is no time for a separate PR.

There are two kinds of finding here:
- **6.1 Gaps that need a PR change:** G1.
- **6.2 Wording fixes that only need an edit to issue #77:** W1, W2. No PR change.

### 6.1 Gaps that need a PR change

**G1 The loader doesn't hand provenance to the adapter (Medium)**

| | |
|---|---|
| **What the design says** | "Loaders record source file paths and checksums for provenance" (`adapter_framework.md` §5). Adapter metadata must include `source_version` and source file paths and checksums (§6). |
| **What the Task 2 issue says** | Nothing. It asks for a checksum manifest and verification, but not for the loader to return provenance to the adapter. |
| **What the PR does** | Follows the issue. The values exist (the manifest, and `verify_table` returns `csv_path` and `sha256` per table), but no function returns them in the form the adapter needs. |
| **Why it matters** | Since PR #91, `adapt_sources(provenance=...)` fails unless `source_version`, `source_files`, `source_checksums` and `telemetry_window` are given, and the last three must be mappings. Without a helper, Task 3 has to build them by hand, and the checksums in the metadata might not come from the verification that actually passed. Task 8 compares them against the manifest. |
| **Fix** | Add `source_provenance(tables=None, raw_dir=None, manifest=None)`. It runs `verify_sources` on the requested tables (default: all six) and returns `{"source_version": ..., "source_files": {table: csv path}, "source_checksums": {table: sha256}}`. `telemetry_window` is computed from the data, so Task 3 adds it. |
| **Where to apply** | `src/sources/alibaba_gpu_2020.py`: new function after `verify_sources` (lines 225–236). `docs/data/alibaba_gpu_2020_source_setup.md` §4: one line describing it. `tests/test_alibaba_gpu_2020_loader.py`: one test that checks the returned paths and checksums against the fixture manifest, and one that a missing file fails. |
| **Affects** | Task 3 (passes it to `adapt_sources`), Task 8 (checks it against the manifest). |

### 6.2 Wording fixes in issue #77 (no PR change)

The design and the PR are both correct for these; only the issue text is wrong.

| # | Where in #77 | Current text | Change to | Why |
|---|---|---|---|---|
| W1 | Implementation Tasks | "Verify local row counts against `docs/data/alibaba_gpu_2020_evidence_and_limitations.md`." | "Verify local row counts against `docs/data/alibaba_dataset_selection_feasibility.md` (job and task counts also in `alibaba_gpu_2020_evidence_and_limitations.md`)." Also add the feasibility document to References. | The evidence document only has the job and task counts (1,055,501 and 1,261,050). All six counts are in the feasibility document. |
| W2 | Blocks; Parallel Work; Handoff | "Task 11a: Alibaba GPU 2020 Artifact, Metadata and Test Verification"; "Task 11a reuses the checksum manifest…" (twice) | "Task 8" in all three places | The final verification task is Task 8 in the GitHub issues. Same rename as in #79 and #81. |

### Summary
| # | Finding | Kind | Severity | Fixed in | Affects |
|---|---|---|---|---|---|
| G1 | Loader doesn't hand provenance to the adapter | Gap | Medium | PR #93 | Task 3, Task 8 |
| W1 | Row-count check points to the wrong document | Wording | — | Issue #77 | — |
| W2 | "Task 11a" should be Task 8 | Wording | — | Issue #77 | — |
