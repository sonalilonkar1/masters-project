# Alibaba GPU 2020 Adapter Results (Task 3, #79)

**Measured:** Part A on 2026-10-24, Part B (B1–B6) on 2026-10-25, on the full source tables.
**Design:** `docs/design/alibaba_gpu_2020_adapter_design.md` · **Contract:** `docs/design/alibaba_gpu_2020_output_contract.md`
**Data:** `data/raw/alibaba_gpu_2020/` (gitignored), loaded with the Task 2 loader after checksum verification.
**Method:** each step was run on the full tables and every figure compared with an independently computed expectation (for example, role maxima recomputed by sorting instead of the adapter's group-by). The run scripts are read-only and not committed.
**For the report:** cite this document for **pipeline validation**. Cite `docs/data/alibaba_gpu_2020_source_data_checks.md` for **data validation**.

**Result: every reconciliation holds and every expected figure is reproduced exactly. The full `adapt_sources` pipeline passes on the full tables.**

---

## Part A: preparation

### 1. Prepared frames

| Frame | Rows | Columns | Memory (deep) | Accepted | Rejected |
|---|---|---|---|---|---|
| `jobs` | 1,055,501 | 12 | 0.23 GB | 1,051,838 | 3,663 |
| `roles` | 1,261,050 | 31 | 0.82 GB | 1,254,108 | 6,942 |
| `instances` | 7,522,002 | 41 | 9.34 GB | 7,410,783 | 111,219 |
| `rejected` | 121,824 | 64 | 0.18 GB | — | 3,663 job + 6,942 role + 111,219 instance |

One row per source row, in source order; no join drops, adds or duplicates a row. The only rejection reason is `missing_submission_time`; all 3,663 rejected jobs are `Waiting`.

### 2. Reconciliation

| Level | Reconciliation |
|---|---|
| Task | 1,261,050 = 1,254,108 accepted + 6,942 rejected |
| Instance | 7,522,002 = 7,410,783 accepted + 111,219 rejected |
| Job | 1,055,501 = 1,051,838 accepted + 3,663 rejected |

0 accepted keys appear in the rejected output; 0 accepted roles or instances lack a canonical time.

The build script checks these three equations on every build (`reconciliation` in `metadata.json` and `count_report.md`) and does not publish if one fails; the rejected rows per level are also in `EXPECTED_COUNTS` (PR #95 review).

### 3. Join coverage

`driving_unmatched` includes the null-key rows. These values are written to `metadata.json` (B6).

| Join | Driving matched | Driving unmatched | Of which null key | Lookup used | Lookup unused |
|---|---|---|---|---|---|
| `job_group_tag` | 1,053,971 | 1,530 | 0 | 1,053,971 | 1,061 |
| `task_job` | 1,261,050 | 0 | 0 | 1,055,501 | 0 |
| `instance_task` | 7,522,002 | 0 | 0 | 1,260,920 | 130 |
| `instance_sensor` | 3,027,318 | 4,494,684 | 331,057 | 3,019,349 | 13,883 |
| `instance_machine_spec` | 7,190,945 | 331,057 | 331,057 | 1,897 | 0 |

- 1,530 jobs without a group tag use fallback identity (1,460 accepted). 130 tasks have no instance rows.
- 3,027,318 instance matches use 3,019,349 sensor rows: every attempt of a retried worker carries that worker's single sensor row (7,969 extra matches). Rule 10 excludes these roles.
- The only machine-spec misses are the 331,057 instances with no machine, the same rows that have no `worker_name`.

### 4. Identity, time and linkage

| Check | Result |
|---|---|
| `role_key` / `instance_id` unique | Yes, on all 1,261,050 roles and 7,522,002 instances |
| Fallback roles (null `recurrence_key`) | 1,888 (1,788 accepted, 100 rejected) |
| Slots / retried slots / rows in retried slots | 6,846,883 / 231,632 / 906,751; largest attempt index 338 |
| Inherited identity (A4) | 0 differences; 12,810 instances inherit a null `recurrence_key` |
| Null times (all rows) | Roles: `start_time_us` 6,942, `end_time_us` 324,028, `launch_time_us` 3,714. Instances: `event_time_us` 111,219, `start_time_us` 1,773,468, `end_time_us` 2,267,582 |
| Accepted instances without their own start | 1,673,976 |
| Linkage, accepted (1,254,108 roles / 7,410,783 instances) | 0 orphans, 0 identity mismatches, 0 event-time mismatches |
| Linkage, rejected (6,942 roles / 111,219 instances) | 0 orphans, 0 identity mismatches, 0 non-null times |

Rerunning `prepare_sources` on the merged Task 2 loader output gave identical row counts, rejection flags, join coverage, and identity and time columns.

---

## Part B: eligibility, resources and outputs

### 5. B1 Exclusion rules

Over the 1,254,108 accepted roles, each counted once under its first failed rule.

| Order | `exclusion_reason` | Roles |
|---|---|---|
| 1 | `no_recurrence_key` | 1,788 |
| 2 | `job_failed` | 282,027 |
| 3 | `job_incomplete` | 87,980 |
| 4 | `task_not_terminated` | 0 |
| 5 | `missing_or_invalid_request` | 2 |
| 6 | `instance_failed` | 33,022 |
| 7 | `instance_interrupted` | 31 |
| 8 | `instance_incomplete` | 0 |
| 9 | `missing_worker_name` | 0 |
| 10 | `multi_attempt_worker` | 2,048 |
| 11 | `missing_sensor` | 287,780 |
| 12 | `partial_sensor_coverage` | 97,018 |
| 13 | `invalid_memory_exceeds_capacity` | 512 |
| 14 | `invalid_resource` | 0 |
| — | **Eligible** | **461,900** (1,224 with missing CPU) |

462,156 roles fail none of rules 1–9 and 11–14; rule 10 alone removes 256. No rejected role received a reason; no accepted row has a null status.

### 6. B3 Resource mappings

Every canonical value equals its source column, nulls included; every unit is the expected constant; no value is negative; `peak_cpu` is null everywhere.

| Field | Null |
|---|---|
| `requested_cpu`, `requested_memory` (roles) | 18,454 each (only 2 have rule 5 as their first reason) |
| `requested_gpu` (roles) | 223,965 |
| `observed_cpu` (instances) | 4,500,495 (4,494,684 without a sensor row + 5,811 null `cpu_usage`) |
| `observed_memory` (instances) | 4,495,890 (+ 1,206 null `avg_mem`) |
| `peak_memory`, `observed_gpu`, `peak_gpu_memory` (instances) | 4,494,684 each |

### 7. B4 Role aggregation

| Check | Result |
|---|---|
| Role value = maximum over sensor-covered instances (five fields, recomputed independently) | Every role |
| Eligible roles with null `observed_cpu` / `observed_memory` / `peak_memory` | 1,224 / 336 / 0 |
| Accepted roles with any usage value | 850,020 = 461,900 eligible + 387,608 excluded by rules 1–12 + 512 by rule 13 |
| Rejected roles with any usage value | 13 |
| Scope columns | Only the per-frame constants |

The first estimate (849,508) left out the rule-13 roles, which always have full sensor coverage.

### 8. B2 Validity

| Rows (row status) | `valid` | `partial` | `invalid` |
|---|---|---|---|
| Eligible roles | 461,564 | 336 | 0 |
| Accepted roles | 677,334 | 574,793 | 1,981 |
| Accepted instances | 3,020,973 | 4,384,687 | 5,123 |

- Eligible: memory `invalid` 0; CPU `partial` 1,224 (row still `valid`, since CPU is not populated); memory `partial` 336.
- 1,981 roles are memory-invalid, of which 512 have rule 13 as their first reason; the other 1,469 fail an earlier rule first.
- CPU above host capacity: 0. Null statuses: 0.
- Row status counts equal memory status counts: for this dataset CPU never changes a row's status.

### 9. B5 Views and B6 metadata

| Check | Result |
|---|---|
| `role_occurrence` / `instance` / rejected rows | 1,254,108 / 7,410,783 / 121,824 |
| View columns | Equal the contract lists (46 role, 47 instance) |
| Rejected dtypes | No `object` columns (31 `string`, 19 `float64`, 8 `Int64`, 6 `boolean`) |
| `adapt_sources` (validation, linkage, rejected checks, overlap) | Passes |
| `exclusion_reason_counts` | §5 in rule order with zeros; `<null>` 461,900 |
| `eligibility_summary` | 1,254,108 accepted / 462,156 / 461,900 eligible / 1,224 missing CPU |
| `join_coverage_counts` | Identical to §3 |

### 10. Run cost

Loading the six tables takes 43 s. A full `adapt_sources` run with metadata took 551 s. Its peak *resident* memory was 9.3 GB on the 16 GB (17.2 billion byte) test machine, but resident memory leaves out what macOS compressed or swapped: the full process footprint is about 29 GB (§11).

---

## 11. Build script and artifacts (B7)

### 11.1 Memory profile

A read-only profile of the full build (2026-10-26) sampled the Python process's macOS `phys_footprint` (all memory it uses, including what macOS compressed or swapped) and resident size every 0.5 s, labelled by stage. Publishing was disabled; the canonical output was not touched.

| Stage | Time | Peak footprint | Peak resident |
|---|---|---|---|
| Load the six tables | 0–53 s | 3.3 GB | 3.8 GB |
| Framework source copies | 68–69 s | 5.4 GB | 5.5 GB |
| `prepare_sources` | 69–316 s | 15.0 GB | 7.2 GB |
| `map_prepared_sources` | 339–465 s | 25.4 GB | 8.2 GB |
| **Framework validation** (`adapt_sources`) | 498–648 s | **27.2 GB** | 7.9 GB |
| Metadata | 648–660 s | 16.2 GB | 6.6 GB |
| Write `role_occurrence` / `instance` / `rejected` | 660–734 s | 10.8 / 16.4 / 11.0 GB | 6.8 / 5.5 / 1.4 GB |
| After the build returns | 752 s | 0.4 GB | 1.1 GB |

- The machine already had 8.5 GB of swap in use; the build added up to about 7.3 GB (15.8 GB at the peak).
- The peak comes from whole-frame copies alive at once: the prepared frames, the views, and the framework's validation copies (one copy of the instance view is about 2.8 GB). Text stored as Python objects is not the cause: the CSV parser shares one object per repeated value. On 2M instance rows, Arrow-backed strings used 660 MB against 585 MB for Python strings.
- §10's 9.3 GB was resident memory only.
- The remaining hotspots are in `base.py`, `validation.py` and the adapter; they are listed in `docs/planning/github_issues/task3_followup_memory.md`. B7 itself drops the adapter result before writing and frees each frame after writing it.

In the profile, the stage peaks were sampled every 0.5 s; `/usr/bin/time -l` records the exact peak, which is higher because short spikes fall between samples (§11.2).

### 11.2 Final build

Built 2026-10-26 from the clean committed tree with `--force`, replacing the earlier `--allow-dirty` validation build only after every check passed. A second build from the same commit into a separate folder checked determinism.

**Build block:** `code_commit` `9d08d0dce2f38fb9c0dfd82f1e9dc2ba95aec8e9`, `code_dirty: false`, Python 3.10.0, pandas 2.3.3, pyarrow 23.0.1.

| Measure (`/usr/bin/time -l`) | Build 1 (published) | Build 2 (determinism) |
|---|---|---|
| Run time | 624 s | 634 s |
| Peak memory footprint | 29.2 GB | 29.2 GB |
| Peak resident memory | 9.1 GB | 9.2 GB |
| Machine swap: at start → peak | 6.1 → 14.1 GB | 9.0 → 14.2 GB |

The test machine has 16 GB RAM. Releasing the adapter result before writing (B7) does not change the peak, which is in framework validation (§11.1).

| File | Bytes | SHA-256 |
|---|---|---|
| `role_occurrence.parquet` | 289,775,773 | `e1823b92b2851675d567a9b4f55cdce47036b74082e7eb8247c1b77d1c33b107` |
| `instance.parquet` | 2,687,477,627 | `c209d4aebfbaabb2222ccdb0b0c6aaa83edb2de32dfffcc50567abe404b18b63` |
| `rejected.parquet` | 33,112,990 | `f1891c5bd544e3e3a184c642d0c2f054ee29039e7242b0a7efe21bb00ff94ef4` |
| `metadata.json` | 6,328 | `959c477ea1d9bcb6e51b6373b2344fc341ec7a6d48e2821aaa0a3ed286838363` |
| `count_report.md` | 3,685 | `da918da30cf4a7206c8f9540613c3803bf70fc86d2d78472a78e8709e22b8baf` |

| # | Check | Result |
|---|---|---|
| 1 | Row counts | 1,254,108 / 7,410,783 / 121,824 |
| 2 | Expected vs actual (22 headline figures) | All differences zero |
| 3 | Column lists | 46 role and 47 instance columns, equal to contract §4–5 |
| 4 | `metadata.json` | All 18 expected keys; 6 source checksums; telemetry window mapping; build block as above |
| 5 | Rejected dtypes | 31 `string`, 19 `float64`, 8 `Int64`, 6 `boolean`, no `object`; 3,663 job / 6,942 role / 111,219 instance rows |
| 6 | `shasum -a 256 -c SHA256SUMS` | 5 / 5 OK |
| 7 | `--verify` | Exit 0 |
| 8 | Run time | 624 s |
| 9 | Memory | Footprint 29.2 GB, resident 9.1 GB, swap +8.0 GB |
| — | Determinism | Build 2's `SHA256SUMS` identical to build 1's, all five files |
| — | Tampered copy | One changed byte and an added `.DS_Store`: `--verify` fails (exit 1) and names both |
| — | Publish | Previous output replaced only after all checks passed; no `.tmp-*` or `.previous-*` folders left |

These checksums belong to this pre-merge validation build. The shared copy is rebuilt from the merge commit, so its `metadata.json`, `count_report.md` and `SHA256SUMS` differ (they record the commit) even when the Parquet files are byte-identical; check a download against its own `SHA256SUMS`.

The three Parquet files are also byte-identical to the earlier `--allow-dirty` build (commit `11de456` plus uncommitted B7 code); only `metadata.json` and `count_report.md` differ, because they record the commit.

`EXPECTED_COUNTS` in `scripts/build_alibaba_gpu_2020_canonical.py` is a copy of §1, §5 and §9: a change that moves a count must update both.
