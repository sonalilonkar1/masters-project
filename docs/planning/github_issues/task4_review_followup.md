# Task 4 review follow-up: PR and issue text

Prepared locally for review. No GitHub issue or PR description has been edited.
The reconciliation below is the reviewer's measurement from PR #96, not a new
eligibility rule. The production build always honors the canonical exclusions.

## Reproducible local build and Task 6 handoff

After pulling the merged code, run locally against the shared, verified Task 3
data built from c2ae87f:

```bash
python3 scripts/build_alibaba_gpu_2020_targets.py
```

The defaults are `data/processed/alibaba_gpu_v2020/` as canonical input and the
separate gitignored `data/processed/alibaba_gpu_v2020_targets/` as target output.
The script verifies the six-file input with the Task 3 verifier, loads only role
records and source metadata, and writes three Parquet tables, `metadata.json`,
and `SHA256SUMS`. It never rebuilds or changes canonical data. Metadata records
both the verified Task 3 source commit and the Task 4 generating commit, tracked
dirty state, and Python/pandas/pyarrow versions. Output paths are filenames
relative to the containing output folder.

Use `--canonical-dir DIR` and `--out-dir DIR` for other locations. `--force`
replaces an existing target folder only after all replacement files and hashes
are complete. `--allow-dirty` permits local review builds and records their dirty
state; these are not clean merged-code handoff artifacts. After merge, run the
default command from the clean merge commit and share the printed checksum
manifest. No shared Drive copy of Task 4 tables is necessary.

```bash
cd data/processed/alibaba_gpu_v2020_targets
shasum -a 256 -c SHA256SUMS
```

Parquet bytes require the same pandas/pyarrow versions to match. With different
versions compare metadata and counts as well as the recorded generating commits;
different checksums alone do not establish different numerical results.

Local review validation used:

```bash
python scripts/build_alibaba_gpu_2020_targets.py --out-dir data/processed/alibaba_gpu_v2020_targets_review --allow-dirty
```

This completed in about 67 seconds. The generating build is explicitly marked
dirty because the follow-up has not been committed. Every row, column, dtype,
and value in its three tables matches the previous full-data outputs (323,329
train, 69,286 validation, 69,285 test). The output manifest verifies, and the
canonical manifest still verifies. The relevant new, build-script, split,
Google, canonical schema, and adapter regression suites passed: **270 tests**.
The existing target directory was retained; clean merge-commit generation is
still required after review and merge.

Task 6 can reuse the public selector on canonical roles or the concatenated Task
4 train and validation tables. Supply both partitions to preserve completed
training history at validation submission times; no test table is needed:

```python
from canonical.schema import ALIBABA_GPU_2020_CAPABILITIES
from features.target_builder import iter_resource_history

for history in iter_resource_history(roles, ALIBABA_GPU_2020_CAPABILITIES):
    role_key = history.role_key
    cpu_count = len(history.cpu_values)
    memory_count = len(history.memory_values)
    # Compute resource statistics here, then retain only the resulting scalars.
```

Each history is a read-only, fixed-length view of completed usable predecessor
values, including eligible predecessors from earlier splits. Querying its length
and iterating do not copy its buffer. Snapshots remain stable after the iterator
advances. Consumers should process each snapshot immediately; repeatedly
materializing histories would recreate the memory cost the API avoids. CPU and
memory values can have different lengths; missing CPU never removes memory.

## PR #96 description additions (draft)

Add the build command, output location, checksum/version guidance, and public
history API described above. Expand the changed-file list to include
`scripts/build_alibaba_gpu_2020_targets.py` and its tests. Retain the statement
that Google behavior and canonical Task 3 data are unchanged.

Add this reference reconciliation table:

| Population | Reference | Final Task 4 | Difference | 256 roles restored in review |
|---|---:|---:|---:|---:|
| Validation, in-split next occurrence | 42,104 | 42,069 | -35 | 42,104 |
| Test, in-split next occurrence | 44,087 | 44,053 | -34 | 44,086 |
| Validation, next occurrence in test | 7,742 | 7,736 | -6 | 7,743 |
| Same-second validation / test | 245 / 251 | 245 / 251 | 0 / 0 | 245 / 251 |

The final counts are lower because 256 roles passing all other eligibility rules
are excluded by `multi_attempt_worker`. In the reviewer's reconciliation,
restoring those roles reproduces validation exactly and test within one row.
The remaining row lies at the validation/test boundary, which the reference
analysis placed one timestamp group differently. Structural successor counts
and available CPU/memory counts are reported separately. No exclusions are
changed in the implementation.

## Exact proposed edits to GitHub Issue #81 (G5; not applied)

In **Blocks**, replace:

> **Task 11a:** Verifies the split and target metadata.

with:

> **Task 8:** Verifies the split and target metadata.

In **Handoff**, replace:

> Split and target metadata → Task 11a.

with:

> Split and target metadata → Task 8.

In **Pull-Request Boundary**, after the existing target-builder module and
target-builder tests entries, add:

> - A public history-selection function, and a build script that writes the tables and `SHA256SUMS` (`scripts/build_alibaba_gpu_2020_targets.py`), with tests.

For consistency, add `scripts/build_alibaba_gpu_2020_targets.py` and
`tests/test_build_alibaba_gpu_2020_targets.py` to **Files in Scope**. Keep the
existing restrictions on changes to `split_utils.py`, Google notebooks,
adapters, evaluators, and downstream pipeline code.
