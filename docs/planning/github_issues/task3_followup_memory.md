# [P2] Task 3 Follow-up: Reduce Peak Memory of the Alibaba GPU 2020 Build

**Labels:** `area-implementation`, `priority-medium`

---

## Objective

Lower the peak memory of `scripts/build_alibaba_gpu_2020_canonical.py` so the canonical output can be rebuilt reliably on a 16 GB machine. Today the build peaks at about **27 GB** of process memory: it completes on 16 GB only with heavy swap, and 32 GB is recommended. Teammates normally download the shared output instead (output contract §3.1), so this is not blocking.

Values, columns, dtypes, row order and the validation guarantees must stay the same. A fix is accepted only when a profiled full run shows it lowers the peak.

## Evidence

A stage-by-stage profile of the full build (2026-10-26; macOS process `phys_footprint`, sampled every 0.5 s; results doc §11):

| Stage | Peak footprint |
|---|---|
| Load the six tables | 3.3 GB |
| Framework source copies (`originals`, `copied_sources`) | 5.4 GB |
| `prepare_sources` | 15.0 GB |
| `map_prepared_sources` | 25.4 GB |
| **Framework validation (`adapt_sources`)** | **27.2 GB** |
| Parquet writes | 10.8–16.4 GB |

The cause is whole-frame copies held at the same time; one copy of the 7.4M-row instance view is about 2.8 GB. Python-object strings are not the cause: repeated values share one object, and Arrow-backed strings measured 13% *larger* on load.

## Hotspots

| # | Where | What | Estimated effect |
|---|---|---|---|
| 1 | `base.py` `adapt_sources` | `prepared` (about 6 GB) stays referenced until the method returns, through validation | Release after `map_prepared_sources` |
| 2 | `validation.py` `validate_role_instance_linkage`, called by `adapt_sources` with the full views | `instance_view.copy(deep=True).merge(...)`: a full copy plus a merged copy of the instance view (about 6 GB, temporary) | Pass only the linkage columns, as the adapter's own A7 check already does |
| 3 | `validation.py` `_validate_record_uniqueness` | `groupby("record_level")` materialises the whole view, then `group.loc[eligible]` copies it again | Group only `record_level` and the key columns |
| 4 | `alibaba_gpu_2020.py`, Part A and B steps | Each `.assign()` deep-copies the whole frame (pandas 2.3, copy-on-write off); about 3.7 GB per copy of the instance frame | One copy, then add columns in place |
| 5 | `alibaba_gpu_2020.py` `_view` | `.loc[mask]`, `.assign`, column selection and `reset_index` each copy | Select columns first; reset the index in place |
| 6 | `alibaba_gpu_2020.py` `_assign_validity` | `np.where` text arrays create one new Python string per row (about 1.4 GB retained) | Build from shared string objects |
| 7 | `base.py` `adapt_sources` | `originals` deep-copies every source only for the "inputs unchanged" check (+2.1 GB measured for both copies) | Compare by hash instead (optional) |
| 8 | `validation.py` `validate_adapter_output` | Non-finite check uses a Python `lambda` per value | Vectorise (speed only) |

Already done in Task 3: the build script releases the adapter result and writes and frees one output at a time.

## Out of scope

Arrow-backed strings (measured no saving); partitioning the build (reconsider only if these fixes leave the peak above about 16 GB); chunked Parquet writing (the write phase is not the peak).

## Order and verification

1. #1, then #2 and #3 (framework): one profiled full run after each.
2. #4–#6 (adapter): one profiled run.
3. #7, #8 if still useful.
4. Then: all tests, the full build, the nine B7 checks, `--verify`, and the two-build determinism comparison. Record the new peak in the results doc and the contract.

Framework changes (#1–#3, #7, #8) need review by the framework owners and may go in a separate PR from the adapter changes.

## Dependencies

- Task 3 (#79) merged.
