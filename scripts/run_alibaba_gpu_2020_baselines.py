#!/usr/bin/env python3
"""Task 6: build Alibaba GPU 2020 baselines, select on validation, lock, recommend.

Run locally after Task 4 tables exist and verify:
    python3 scripts/run_alibaba_gpu_2020_baselines.py
    python3 scripts/run_alibaba_gpu_2020_baselines.py --force

Reads the Task 4 tables in data/processed/alibaba_gpu_v2020_targets (after
re-checking their SHA256SUMS). Writes to data/processed/alibaba_gpu_v2020_baselines:
validation comparison, the locked baseline selection record, sensitivity tables,
point-in-time history statistics (Task 7 handoff), locked recommendations for
train/validation/test, metadata, and SHA256SUMS.

Leakage discipline: validation selection uses train+validation only; the locked
selection record is written before test.parquet is opened; test is read with
column selection (never its targets or statuses) and is never scored. Task 7
performs the only final-test evaluation.

Exit codes: 0 success, 1 invalid input, 2 refused, 3 build/write failure.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
from dataclasses import asdict
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT, REPO_ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pandas as pd
import pyarrow.parquet as pq

from scripts import build_alibaba_gpu_2020_canonical as canonical
from scripts import build_alibaba_gpu_2020_targets as targets_build
from canonical.schema import ALIBABA_GPU_2020_CAPABILITIES as PROFILE
import baselines.alibaba_gpu_2020 as a6

DEFAULT_TARGETS_DIR = targets_build.DEFAULT_OUT_DIR
DEFAULT_OUT_DIR = REPO_ROOT / "data/processed/alibaba_gpu_v2020_baselines"

# Task 4 target/status columns that Task 6 must never load for the test split.
TEST_FORBIDDEN_COLUMNS = (
    "actual_cpu", "actual_memory", "actual_cpu_unit", "actual_memory_unit",
    "cpu_target_status", "memory_target_status",
)

# History-input columns iter_resource_history needs (none are targets).
HISTORY_INPUT_COLUMNS = (
    "dataset_id", "record_level", "role_key", "occurrence_id", "recurrence_key",
    "start_time_us", "end_time_us", "exclusion_reason",
    "observed_cpu", "peak_memory", "cpu_validity_status", "memory_validity_status",
)

# Explicit allow-list for the test read (review I1). Only identity, times,
# requests (+units), point-in-time history inputs, and history counts are
# loaded. Nothing target-side or future-derived (e.g. next_occurrence_same_second,
# observed_gpu, source_*_status) is read, and a missing column fails the build.
TEST_ALLOWED_COLUMNS = (
    "dataset_id", "workload_id", "record_level", "role_key", "occurrence_id",
    "recurrence_key", "split", "start_time_us", "end_time_us",
    "requested_cpu", "requested_memory", "requested_cpu_unit", "requested_memory_unit",
    "observed_cpu", "peak_memory", "cpu_validity_status", "memory_validity_status",
    "exclusion_reason", "cpu_history_count", "memory_history_count",
)

OUTPUT_FILES = (
    "baseline_selection.json",
    "validation_comparison.csv",
    "sensitivity_validation.csv",
    "history_statistics.parquet",
    "recommendations_train.parquet",
    "recommendations_validation.parquet",
    "recommendations_test.parquet",
    "metadata.json",
)
EXIT_OK, EXIT_INVALID, EXIT_REFUSED, EXIT_FAILED = 0, 1, 2, 3


class InputError(Exception):
    """Raised when the Task 4 target directory is missing or inconsistent."""


def verify_targets(targets_dir: Path) -> dict[str, str]:
    """Re-hash the Task 4 CHECKED_FILES and confirm they match SHA256SUMS."""
    manifest_path = targets_dir / "SHA256SUMS"
    if not manifest_path.exists():
        raise InputError(f"Missing Task 4 manifest: {manifest_path}")
    recorded = {}
    for line in manifest_path.read_text().splitlines():
        if not line.strip():
            continue
        digest, name = line.split("  ", 1)
        recorded[name] = digest
    expected = set(targets_build.CHECKED_FILES)
    if set(recorded) != expected:
        raise InputError(f"Task 4 manifest lists {sorted(recorded)}, expected {sorted(expected)}")
    for name, digest in recorded.items():
        actual = canonical.sha256(targets_dir / name)
        if actual != digest:
            raise InputError(f"Task 4 checksum mismatch for {name}")
    return recorded


def _read_split(targets_dir: Path, split: str, columns: list[str] | None = None) -> pd.DataFrame:
    return pd.read_parquet(targets_dir / f"{split}.parquet", columns=columns)


def _test_allowed_columns(targets_dir: Path) -> list[str]:
    """Return the explicit test allow-list, requiring every column to exist."""
    schema_names = set(pq.ParquetFile(targets_dir / "test.parquet").schema.names)
    missing = [c for c in TEST_ALLOWED_COLUMNS if c not in schema_names]
    if missing:
        raise InputError(f"test.parquet is missing required columns: {missing}")
    return list(TEST_ALLOWED_COLUMNS)


def _relpath(path: Path) -> str:
    """Repo-relative path when possible, for portable metadata."""
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _counts(selection: a6.BaselineSelection, sensitivity: pd.DataFrame) -> dict[str, int]:
    def total(label: str) -> int:
        rows = sensitivity.loc[sensitivity["sensitivity"] == label, "row_count"]
        return int(rows.iloc[0]) if len(rows) else 0
    return {
        "validation_population": selection.validation_population_size,
        "same_second_rows": total("same_second_only"),
        "multi_instance_rows": total("multi_instance"),
    }


def _source_commits(targets_dir: Path) -> dict[str, object]:
    """Pull the Task 3 source commit and Task 4 code commit from Task 4 metadata."""
    metadata = json.loads((targets_dir / "metadata.json").read_text())
    build = metadata.get("build", {})
    provenance = metadata.get("source_provenance", {}).get("build", {})
    return {
        "task4_code_commit": build.get("code_commit"),
        "task4_code_dirty": build.get("code_dirty"),
        "task3_source_commit": provenance.get("code_commit"),
    }


def run(targets_dir: Path = DEFAULT_TARGETS_DIR,
        out_dir: Path = DEFAULT_OUT_DIR, *, force: bool = False,
        allow_dirty: bool = False, repo: Path = REPO_ROOT) -> int:
    """Verify inputs, select on validation, lock, recommend, and publish."""
    targets_dir = Path(targets_dir).resolve()
    requested_out = Path(out_dir)
    out_dir = requested_out.resolve()
    if requested_out.is_symlink() or targets_dir == out_dir or out_dir in targets_dir.parents:
        print("REFUSED: output must be a separate directory, disjoint from the Task 4 input")
        return EXIT_REFUSED
    if out_dir.exists() and (not out_dir.is_dir() or not force):
        print(f"REFUSED: {out_dir} exists; choose another directory or use --force")
        return EXIT_REFUSED
    commit, dirty = canonical.git_state(repo)
    if (commit is None or dirty) and not allow_dirty:
        print("REFUSED: code must be in a clean Git checkout; use --allow-dirty for local review")
        return EXIT_REFUSED

    started = time.monotonic()
    try:
        manifest = verify_targets(targets_dir)
    except (InputError, OSError) as error:
        print(f"VERIFY FAILED: {error}")
        return EXIT_INVALID

    staging = None
    try:
        # ---- Phase A: validation selection (train + validation only) --------
        train = _read_split(targets_dir, "train")
        validation = _read_split(targets_dir, "validation")

        trainval = pd.concat([train, validation], ignore_index=True)
        stats_trainval = a6.compute_history_statistics(trainval, PROFILE)

        common = a6.freeze_common_validation_population(validation)
        comparison = a6.build_validation_comparison(common, stats_trainval, PROFILE)
        selection = a6.select_baseline(comparison, validation_population_size=len(common))
        sensitivity = a6.build_sensitivity_tables(common, stats_trainval, PROFILE, selection)

        out_dir.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.tmp-", dir=out_dir.parent))
        staged = staging / "baselines"
        staged.mkdir()

        source_commits = _source_commits(targets_dir)
        source_artifacts = {
            "task4_input_dir": _relpath(targets_dir),
            "task4_files": sorted(targets_build.CHECKED_FILES),
            "task4_manifest": manifest,
            **source_commits,
        }
        # Profile-semantics labels for the selected candidate, taken from the
        # evaluator's own output (review I2), not hard-coded text.
        selected_row = comparison[
            (comparison["policy"] == selection.selected_policy)
            & (comparison["min_runs"] == selection.selected_min_runs)
        ].iloc[0]
        selected_labels = {
            "cpu_result_semantics": selected_row["cpu_result_semantics"],
            "primary_resource": selected_row["primary_resource"],
            "any_resource_metric_reported": bool(selected_row["any_resource_metric_reported"]),
            "cpu_usage_label": selected_row["cpu_usage_label"],
        }

        selection_record = {
            "selected_policy": selection.selected_policy,
            "selected_min_runs": selection.selected_min_runs,
            "selection_candidate_policies": list(a6.SELECTABLE_POLICIES),
            "sort_order": list(selection.sort_order),
            "validation_population_size": selection.validation_population_size,
            "validation_metrics": selection.validation_metrics,
            **selected_labels,
            "min_runs_candidates": list(a6.MIN_RUNS_CANDIDATES),
            "dataset_id": PROFILE.dataset_id,
            "build": canonical.build_info(commit, dirty),
            "source_artifacts": source_artifacts,
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        # Lock: the selection record is written BEFORE test.parquet is opened.
        (staged / "baseline_selection.json").write_text(
            json.dumps(selection_record, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        comparison.to_csv(staged / "validation_comparison.csv", index=False)
        sensitivity.to_csv(staged / "sensitivity_validation.csv", index=False)

        # ---- Phase B: locked recommendations (test read only after lock) ----
        test_columns = _test_allowed_columns(targets_dir)
        test = _read_split(targets_dir, "test", columns=test_columns)
        unexpected = [c for c in test.columns if c not in TEST_ALLOWED_COLUMNS]
        if unexpected:
            raise RuntimeError(f"Test read loaded columns outside the allow-list: {unexpected}")
        leaked = [c for c in (*TEST_FORBIDDEN_COLUMNS, "next_occurrence_same_second")
                  if c in test.columns]
        if leaked:
            raise RuntimeError(f"Test read must exclude target/future columns, found: {leaked}")

        all_rows = pd.concat([trainval[list(HISTORY_INPUT_COLUMNS)], test[list(HISTORY_INPUT_COLUMNS)]],
                             ignore_index=True)
        stats_all = a6.compute_history_statistics(all_rows, PROFILE)
        # Train/validation statistics must be identical whether or not test is
        # present, because test never precedes a train/validation row.
        shared = stats_trainval.index
        pd.testing.assert_frame_equal(
            stats_all.loc[shared].sort_index(), stats_trainval.sort_index(), check_dtype=False
        )

        recommendations = {
            "train": a6.build_locked_recommendations(train, stats_trainval, selection, PROFILE),
            "validation": a6.build_locked_recommendations(validation, stats_trainval, selection, PROFILE),
            "test": a6.build_locked_recommendations(test, stats_all, selection, PROFILE),
        }
        for split, frame in recommendations.items():
            frame.to_parquet(staged / f"recommendations_{split}.parquet", index=False)
        stats_all.reset_index().to_parquet(staged / "history_statistics.parquet", index=False)

        metadata = {
            "dataset_id": PROFILE.dataset_id,
            "task": "task6_alibaba_gpu_2020_baselines",
            "profile": asdict(PROFILE),
            "units": {"cpu": a6.RESOURCE_UNIT["cpu"], "memory": a6.RESOURCE_UNIT["memory"]},
            "resource_scope": a6.RESOURCE_SCOPE,
            # Semantics taken from the evaluator's output for the selected
            # candidate, not fixed text (review I2).
            "cpu_result_semantics": selected_labels["cpu_result_semantics"],
            "primary_resource": selected_labels["primary_resource"],
            "any_resource_metric_reported": selected_labels["any_resource_metric_reported"],
            "cpu_usage_label": selected_labels["cpu_usage_label"],
            "percentile_method": a6.PERCENTILE_METHOD,
            "min_runs_candidates": list(a6.MIN_RUNS_CANDIDATES),
            "selection_sort_order": list(a6.SELECTION_SORT_ORDER),
            "selected_policy": selection.selected_policy,
            "selected_min_runs": selection.selected_min_runs,
            "counts": _counts(selection, sensitivity),
            "split_row_counts": {
                "train": int(len(train)), "validation": int(len(validation)), "test": int(len(test)),
            },
            "build": canonical.build_info(commit, dirty),
            "source_artifacts": source_artifacts,
            "output_files": list(OUTPUT_FILES),
        }
        (staged / "metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

        checksums = {name: canonical.sha256(staged / name) for name in sorted(OUTPUT_FILES)}
        (staged / "SHA256SUMS").write_text(
            "".join(f"{digest}  {name}\n" for name, digest in checksums.items()), encoding="utf-8")
        targets_build._publish(staged, out_dir)
    except InputError as error:
        print(f"VERIFY FAILED: {error}")
        return EXIT_INVALID
    except Exception as error:
        print(f"BUILD FAILED: {type(error).__name__}: {error}")
        return EXIT_FAILED
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging)

    print(f"Built {out_dir} in {time.monotonic() - started:.1f} s")
    print(f"Selected baseline: {selection.selected_policy} at min_runs={selection.selected_min_runs}")
    print(f"Validation population: {selection.validation_population_size}")
    print("SHA256SUMS:")
    print("".join(f"{digest}  {name}\n" for name, digest in checksums.items()), end="")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--targets-dir", type=Path, default=DEFAULT_TARGETS_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--force", action="store_true", help="replace a complete baseline build after staging")
    parser.add_argument("--allow-dirty", action="store_true", help="allow an uncommitted local review build")
    args = parser.parse_args(argv)
    return run(args.targets_dir, args.out_dir, force=args.force, allow_dirty=args.allow_dirty)


if __name__ == "__main__":
    sys.exit(main())
