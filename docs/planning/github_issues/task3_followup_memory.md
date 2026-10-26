# [P2] Task 3 Follow-up: Reduce Peak Memory of the Alibaba GPU 2020 Build

**Labels:** `area-implementation`, `priority-medium`

---

## Objective

Lower the peak memory of `scripts/build_alibaba_gpu_2020_canonical.py` so the canonical output can be rebuilt reliably on a 16 GB machine. Today the build peaks at **29.2 GB** of process memory (`/usr/bin/time -l` on three full builds; the 0.5 s profile below catches 27.2 GB because it misses short spikes). It completes on 16 GB only with heavy swap (about +8 GB) in 10–12 minutes, and 32 GB is recommended. Teammates normally download the shared output (output contract §3.1), so this does not block Task 3 or later tasks.

## Acceptance criteria

1. A profiled full build (Appendix A) shows a peak `phys_footprint` **at or below 14 GB**, so a 16 GB machine builds without heavy swap.
2. **Outputs unchanged:** `role_occurrence.parquet`, `instance.parquet` and `rejected.parquet` are **byte-identical** (`SHA256SUMS`) to the build from commit `64d3234` (results doc §11.2) with the same Python, pandas and pyarrow. `metadata.json` differs only in `build.code_commit`.
3. All tests pass; the existing framework tests listed per hotspot still pass unchanged.
4. Every validation still runs and still fails on the same inputs (no check removed or weakened).
5. The new peak and stage table are recorded in `docs/data/alibaba_gpu_2020_adapter_results.md` §11 and the 16/32 GB guidance in the output contract §3.1 is updated.

## Background: where the memory goes

Measured 2026-10-26 on the full tables (16 GB macOS machine; Appendix A):

| Stage | Time | Peak footprint | Peak resident |
|---|---|---|---|
| Load the six tables | 0–53 s | 3.3 GB | 3.8 GB |
| Framework source copies | 68–69 s | 5.4 GB | 5.5 GB |
| `prepare_sources` (Part A) | 69–316 s | 15.0 GB | 7.2 GB |
| `map_prepared_sources` (Part B, views) | 339–465 s | 25.4 GB | 8.2 GB |
| **Framework validation in `adapt_sources`** | 498–648 s | **27.2 GB** | 7.9 GB |
| Metadata | 648–660 s | 16.2 GB | 6.6 GB |
| Parquet writes | 660–734 s | 10.8–16.4 GB | 1.4–6.8 GB |

**Cause: whole-frame copies alive at the same time.** A copy costs about 8 bytes per cell: one copy of the 7.4M × 47 instance view is about **2.8 GB**, of the 7.5M × ~60 working instance frame about **3.7 GB**. Text is not the cause: the CSV parser stores one Python object per repeated value, so a copy duplicates only pointers. **Do not switch to Arrow-backed strings:** on 2M instance rows they used 660 MB against 585 MB (+13%) and add bytes wherever values are copied between frames.

**Two peaks must both come down:** validation (27.2 GB, hotspots 1–3) and Part B view building (25.4 GB, hotspots 4–6). Fixing only one leaves the other above 16 GB.

---

## Hotspots

Estimates (E) come from rows × columns × 8 bytes; measured values (M) from the profile. Re-measure each fix with Appendix A.

### 1. `prepared` frames stay alive through validation (framework)

- **Where:** `src/adapters/base.py`, `adapt_sources`: `prepared = self.prepare_sources(copied_sources)` (line 448) and `views, rejected = self.map_prepared_sources(prepared)` (line 461). `prepared` stays referenced until the method returns (line 568), through all validation (lines 510–545) and metadata (line 560).
- **Cost:** E about 6 GB (M: `prepare_sources` raised the held footprint from 5.4 to 11.4 GB). The views and rejected output already hold every value that is still needed.
- **Change:** `del prepared` right after line 461 (after the type checks on `views`). `copied_sources` (line 446) can be deleted at the same point, because `prepare_sources` has returned.
- **Risk:** none for values. An adapter that returns views sharing memory with `prepared` is unaffected; `del` drops a name, not data in use.
- **Tests:** `tests/test_multiview_adapter_framework.py` (all), including `test_multiview_path_does_not_modify_caller_sources`. New: none needed.
- **Expected effect:** E −6 GB at the validation stage.

### 2. Linkage validation copies and merges the full instance view (framework)

- **Where:** `src/adapters/base.py` line 521 calls `validate_role_instance_linkage(normalized_views["role_occurrence"], normalized_views["instance"], ...)` with the **full** views. In `src/adapters/validation.py`, `validate_role_instance_linkage` (line 402) does `instance_view.copy(deep=True).merge(parent_lookup, ...)` (lines 515–518): a full copy of the instance view and a merged copy with the parent columns added.
- **Cost:** E about 2.8 GB (copy) + about 3 GB (merge result), temporary, at the 27.2 GB peak.
- **Change:** in `base.py` line 521, pass only the columns the check reads:
  - role view: `role_key`, `workload_id`, `recurrence_key`, `occurrence_id`, plus `start_time_us` when `instance_event_time_semantics == "parent_job_submission"`;
  - instance view: the same four, plus `event_time_us` (same condition) and `instance_id` (used by `_sample_instance_ids`, line 383).

  The Alibaba adapter already does exactly this for its own A7 check (`LINKAGE_ROLE_COLUMNS`, `LINKAGE_INSTANCE_COLUMNS`, `alibaba_gpu_2020.py` lines 107–110), so the column lists can be moved into `validation.py` and shared. Optionally also drop the `copy(deep=True)` at line 515: `merge` already returns a new frame.
- **Risk:** low. The check's required-column test (validation.py lines 423–450) must still run on the full views first, so a view missing a column still fails with the same message.
- **Tests:** `test_missing_parent_role_fails_linkage` (line 620), `test_linkage_validation_does_not_modify_identity_fields` (line 790), and the Alibaba linkage tests in `tests/test_alibaba_gpu_2020_adapter.py`. New: a test that a view missing `event_time_us` still fails under `parent_job_submission`.
- **Expected effect:** E −5 to −6 GB at the validation stage.

### 3. Uniqueness validation copies the whole view twice (framework)

- **Where:** `src/adapters/validation.py`, `_validate_record_uniqueness` (line 21), called by `validate_adapter_output` (line 189) for every view. `df.groupby("record_level")` (line 25) yields each group as a full sub-frame; with one record level per view that is a full copy. `group.loc[eligible]` (line 69) copies it again.
- **Cost:** E up to 2 × 2.8 GB, temporary.
- **Change:** before grouping, reduce to the columns the check uses: `df[["record_level", *candidate_keys]]`, where the candidate keys are the union of the key columns present (`occurrence_id`, `instance_id`, `event_time_us`, `source_seq_no`, `execution_id`, `start_time_us`, `role_key`). Then compute `duplicated` on the key columns with a boolean mask instead of `group.loc[eligible]`.
- **Risk:** low; the same keys are checked. The error example (lines 76–80) still has the key columns.
- **Tests:** the uniqueness tests in `tests/test_adapter_contract.py` and `tests/test_multiview_adapter_framework.py`.
- **Expected effect:** E −3 to −5 GB at the validation stage.

### 4. Every `.assign()` copies the whole frame (adapter)

- **Where:** `src/adapters/alibaba_gpu_2020.py`. With pandas 2.3 and copy-on-write off (`pd.get_option("mode.copy_on_write")` is `False`), each `DataFrame.assign` deep-copies the frame before adding columns. On the instance frame: lines 331 (A3), 395 (A4), 454 (A5), 522 (A6), 742 and 760 (B3), 833 (B4 scope), 951 (B2). While each runs, the old frame, the new frame and the original in `prepared["instances"]` are alive together.
- **Cost:** E about 3.7 GB per copy of the instance frame; M: Part B rose from 11.4 to a 25.4 GB peak.
- **Change, preferred:** turn on copy-on-write for the build only, `pd.set_option("mode.copy_on_write", True)` in the build script before the adapter runs (pandas 3 makes it the default). `assign` then shares unchanged columns instead of copying them. Run the full test suite with the option on first; fix any `SettingWithCopy`-style code it exposes.
- **Change, fallback (adapter only):** in each step, make one shallow frame (`frame = frame.copy(deep=False)`) and add columns with `frame[name] = values`, instead of `frame.assign(...)`.
- **Risk:** medium for the option (it changes copy semantics process-wide; the adapter already never mutates inputs in place, which is what the tests check). Low for the fallback.
- **Tests:** all of `tests/test_alibaba_gpu_2020_adapter.py` (the "inputs unchanged" tests in particular) and `test_multiview_path_does_not_modify_caller_sources`.
- **Expected effect:** E −7 to −10 GB at the Part B stage; also lowers `prepare_sources`.

### 5. View assembly makes three or four copies (adapter)

- **Where:** `src/adapters/alibaba_gpu_2020.py`, `_view` (line 1000): `frame.loc[mask]` (line 1004, copy) → `.assign(...)` (line 1006, copy) → `accepted[list(columns)]` (copy) → `.reset_index(drop=True)` (copy) (line 1014).
- **Cost:** E 2–3 × 2.8–3.7 GB on the instance view, temporary.
- **Change:** select the needed source columns and rows in one step, `frame.loc[mask, needed_columns]`, where `needed_columns` is the view's columns minus the ones `_view` adds; then add the 3–4 new columns with `frame[name] = ...`; then `frame.index = pd.RangeIndex(len(frame))` instead of `reset_index`; finally reorder with `frame = frame[list(columns)]` only if the order differs.
- **Risk:** low; column order and values are checked by the view-column tests.
- **Tests:** the B5 tests in `tests/test_alibaba_gpu_2020_adapter.py` (`ROLE_VIEW_COLUMNS`, `INSTANCE_VIEW_COLUMNS`) plus acceptance criterion 2.
- **Expected effect:** E −3 to −6 GB at the Part B peak.

### 6. Validity text creates one new string per row (adapter)

- **Where:** `src/adapters/alibaba_gpu_2020.py`, `_status` (line 845) and `_row_status` (line 850) return numpy text arrays from `np.where`; `_assign_validity` (line 951) turns each into `pd.array(value, dtype="string")`, creating a new Python string per row for 3 columns on 8.8M rows.
- **Cost:** E about 1.4 GB retained.
- **Change:** build the statuses as an object array that reuses three string constants, for example `np.array(["valid", "partial", "invalid"], dtype=object)[codes]` with integer codes, then `pd.array(..., dtype="string")`.
- **Risk:** none; same values and dtype.
- **Tests:** the B2 validity tests in `tests/test_alibaba_gpu_2020_adapter.py`.
- **Expected effect:** E −1.4 GB from Part B onward.

### 7. A full deep copy of every source only to prove inputs are unchanged (framework, optional)

- **Where:** `src/adapters/base.py` line 445, `originals[name] = frame.copy(deep=True)`, used only by `pd.testing.assert_frame_equal(sources[name], original, ...)` at line 538.
- **Cost:** M +2.1 GB for both source copies (lines 445–446); this one is about half.
- **Change:** store `pd.util.hash_pandas_object(frame, index=True).to_numpy()` plus `frame.dtypes` and `frame.columns` instead of the copy, and compare those at line 538.
- **Risk:** medium: the hash comparison must be as strict as `assert_frame_equal(check_dtype=True)`. Comparing dtypes and columns explicitly covers that; a hash collision is practically impossible but should be stated. Needs agreement from the framework owners.
- **Tests:** `test_multiview_path_does_not_modify_caller_sources` (line 821) must still fail when an adapter mutates its input; add a test that changes one value and one dtype.
- **Expected effect:** E −1 GB for the whole run.

### 8. Python-level non-finite check (framework, speed only)

- **Where:** `src/adapters/validation.py`, `validate_adapter_output`, `values.map(lambda x: ...)` (line 246), once per resource column (about 12 columns × 7.4M values on the instance view).
- **Change:** `np.isfinite(values.to_numpy(dtype=float, na_value=np.nan))` with nulls treated as finite, as now.
- **Risk:** none. **Effect:** shorter validation stage (part of its 150 s), no memory change.

---

## Plan and order

| Step | Hotspots | Files | Check after the step |
|---|---|---|---|
| 1 | #1 | `base.py` | Appendix A: validation stage drops by about 6 GB |
| 2 | #2, #3 | `validation.py`, `base.py` | Validation stage below the Part B stage |
| 3 | #4 (copy-on-write option, or fallback), #5, #6 | build script or adapter | Part B stage at or below 14 GB |
| 4 | #7, #8 if still useful | `base.py`, `validation.py` | — |
| 5 | — | docs | Acceptance criteria 1–5; full build, nine B7 checks, `--verify`, two-build determinism |

- Steps 1, 2 and 4 change the shared framework: review by the framework owners, a separate PR from the adapter changes.
- Do one step per profiled run, so each effect is measured on its own.
- If steps 1–3 leave the peak above about 16 GB, reconsider processing the instance table in partitions; it is a redesign and out of scope here.

## Out of scope

Arrow-backed strings (measured no saving); chunked Parquet writing (the write phase, at most 16.4 GB, is not the peak); partitioning (see above).

## Dependencies

- Task 3 (#79) merged.

---

## Appendix A: memory profiler

macOS only (`proc_pid_rusage` from `libSystem`). Read-only: it runs the real build in its own process, samples its own `phys_footprint` and resident size every 0.5 s, labels each sample by stage, and never publishes (the script's `publish` is replaced by a no-op). Run from the repository root:

```bash
python3 -u profile_b7_memory.py /tmp/b7_profile_out > profile.log 2>&1
rm -rf /tmp/.b7_profile_out.tmp-*        # the unpublished build folder (about 3 GB)
```

```python
"""Stage-by-stage memory profile of the Alibaba GPU 2020 build (macOS)."""
import ctypes, gc, importlib.util, os, sys, threading, time
from pathlib import Path
import pandas as pd
import psutil

REPO = Path.cwd()
sys.path.insert(0, str(REPO))
OUT, PID, GB = Path(sys.argv[1]), os.getpid(), 2**30
libc = ctypes.CDLL("/usr/lib/libSystem.dylib")
BUF = (ctypes.c_uint64 * 40)()

def footprint_and_rss():
    # RUSAGE_INFO_V2: 16-byte uuid, then uint64s; resident_size = 6, phys_footprint = 7.
    libc.proc_pid_rusage(PID, 2, ctypes.byref(BUF))
    fields = list(BUF)[2:]
    return fields[7], fields[6]

T0, stage, peaks, lock, done = time.monotonic(), ["start"], {}, threading.Lock(), threading.Event()

def record():
    fp, rss = footprint_and_rss()
    swap, t = psutil.swap_memory().used, time.monotonic() - T0
    with lock:
        p = peaks.setdefault(stage[0], [0, 0, 0, t, t])
        p[0], p[1], p[2], p[4] = max(p[0], fp), max(p[1], rss), max(p[2], swap), t

def sample():
    while not done.is_set():
        record(); time.sleep(0.5)

def mark(name):
    record()
    with lock:
        stage[0] = name
    print(f"t={time.monotonic() - T0:6.0f}s -> {name}", flush=True)

spec = importlib.util.spec_from_file_location("b7", REPO / "scripts" / "build_alibaba_gpu_2020_canonical.py")
b7 = importlib.util.module_from_spec(spec); spec.loader.exec_module(b7)
from src.adapters.alibaba_gpu_2020 import AlibabaGPU2020Adapter as A

def wrap(owner, attr, before, after):
    original = getattr(owner, attr)
    def wrapper(*args, **kwargs):
        mark(before)
        try:
            return original(*args, **kwargs)
        finally:
            mark(after)
    setattr(owner, attr, wrapper)

load = b7.load_sources
def load_sources(raw_dir=None):
    mark("1 load sources")
    out = load(raw_dir)
    mark("4a framework source copies")  # adapt_sources copies the sources next
    return out
b7.load_sources = load_sources
wrap(A, "prepare_sources", "2 prepare_sources", "2 after prepare_sources")
wrap(A, "map_prepared_sources", "3 map_prepared_sources", "4b framework validation")
wrap(A, "build_multiview_metadata", "4c metadata", "4c after metadata")
to_parquet = pd.DataFrame.to_parquet
def write(self, path, *args, **kwargs):
    mark(f"write {Path(path).name}")
    return to_parquet(self, path, *args, **kwargs)
pd.DataFrame.to_parquet = write
b7.publish = lambda folder, out_dir: print(f"not published: {folder}")

threading.Thread(target=sample, daemon=True).start()
code = b7.build(OUT, allow_dirty=True, force=True)
mark("8 after build"); gc.collect(); time.sleep(3); record(); done.set()
print(f"\nexit {code}\n{'stage':34s} {'footprint':>10s} {'resident':>9s} {'swap':>7s}")
for name, (fp, rss, swap, t1, t2) in peaks.items():
    print(f"{name:34s} {fp/GB:8.1f} GB {rss/GB:6.1f} GB {swap/GB:5.1f} GB   {t1:4.0f}-{t2:4.0f} s")
```

Notes: `phys_footprint` is what `/usr/bin/time -l` reports as "peak memory footprint" and includes compressed and swapped memory; resident size alone understates the build (it showed 9.3 GB while the footprint was about 27 GB). Swap is machine-wide, so record the value before the run and report the increase. Use footprint, not pandas `memory_usage(deep=True)`, which counts a shared string once per cell and overstates Python-stored text.
