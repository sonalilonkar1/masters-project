#!/usr/bin/env python3
"""Task 7 PR2: one-shot Alibaba GPU 2020 final-test evaluation.

Consumes the LOCKED PR1 artifacts. Never trains, selects, tunes, or rewrites
the PR1 decision manifest. Verifies all relevant checksums before opening the
Task 4 test table, loads the locked refit models, evaluates exactly
Request/Mean/P90/P95/P99/ML/Hybrid, writes required sensitivities, and records
a run fingerprint.

Do not run this against the real Alibaba test table until PR1 has been reviewed
and frozen by the team.

The locked PR1 manifest must have been built from a clean checkout at the
current code commit. Every run is appended to RUN_LOG_NAME inside the PR1
directory before the test table is opened; a second run for the same decision
manifest is refused, whatever --out-dir is given. A documented defect rerun
requires --defect-rerun-reason, is logged, and preserves any previous output
directory before writing a new result. The log is a local file: it stops the
script from re-evaluating a lock, not manual deletion of files.

Exit codes: 0 success, 1 invalid input, 2 refused, 3 build/write failure.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT, REPO_ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import joblib
import pandas as pd

from scripts import build_alibaba_gpu_2020_canonical as canonical
from scripts import build_alibaba_gpu_2020_targets as targets_build
from scripts import run_alibaba_gpu_2020_baselines as baselines_run
from scripts import run_alibaba_gpu_2020_ml as ml_run
from canonical.schema import ALIBABA_GPU_2020_CAPABILITIES as PROFILE
from models.alibaba_gpu_2020_final_test import (
    FINAL_POLICIES,
    evaluate_final_test,
    validate_locked_manifest,
)

DEFAULT_TARGETS_DIR = targets_build.DEFAULT_OUT_DIR
DEFAULT_BASELINES_DIR = baselines_run.DEFAULT_OUT_DIR
DEFAULT_ML_DIR = ml_run.DEFAULT_OUT_DIR
DEFAULT_OUT_DIR = REPO_ROOT / "data/processed/alibaba_gpu_v2020_final_test"

OUTPUT_FILES = (
    "final_test_policy_comparison.csv",
    "final_test_sensitivity.csv",
    "final_test_predictions.parquet",
    "run_record.json",
    "metadata.json",
)

RUN_LOG_NAME = ml_run.FINAL_TEST_RUN_LOG

EXIT_OK, EXIT_INVALID, EXIT_REFUSED, EXIT_FAILED = 0, 1, 2, 3


class InputError(Exception):
    """Raised when a locked dependency is missing or inconsistent."""


def _verify_manifest(directory: Path, expected_files) -> dict[str, str]:
    manifest_path = directory / "SHA256SUMS"
    if not manifest_path.exists():
        raise InputError(f"Missing manifest: {manifest_path}")

    recorded = {}
    for line in manifest_path.read_text().splitlines():
        if line.strip():
            digest, name = line.split("  ", 1)
            recorded[name] = digest

    if set(recorded) != set(expected_files):
        raise InputError(
            f"{directory} manifest lists {sorted(recorded)}, "
            f"expected {sorted(expected_files)}"
        )
    for name, digest in recorded.items():
        if canonical.sha256(directory / name) != digest:
            raise InputError(f"Checksum mismatch for {directory / name}")
    return recorded


def _relpath(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _verify_pr1_lock(
    targets_dir: Path,
    baselines_dir: Path,
    ml_dir: Path,
) -> tuple[dict, dict[str, str], dict[str, str], str]:
    """Verify PR1/Task6/Task4 before any test data is opened."""
    pr1_manifest = _verify_manifest(ml_dir, ml_run.OUTPUT_FILES)
    baselines_manifest = _verify_manifest(
        baselines_dir,
        baselines_run.OUTPUT_FILES,
    )

    decision_path = ml_dir / "decision_manifest.json"
    decision_sha = canonical.sha256(decision_path)
    manifest = _load_json(decision_path)
    validate_locked_manifest(manifest)

    if pr1_manifest["decision_manifest.json"] != decision_sha:
        raise InputError(
            "PR1 decision manifest checksum disagrees with PR1 SHA256SUMS"
        )

    recorded_task4 = manifest["task4_inputs"]["targets_manifest"]
    if set(recorded_task4) != set(targets_build.CHECKED_FILES):
        raise InputError(
            "PR1 manifest does not contain the complete Task 4 checksum set"
        )

    # Re-hash the physical test file BEFORE pd.read_parquet is ever called.
    expected_test_sha = recorded_task4["test.parquet"]
    actual_test_sha = canonical.sha256(targets_dir / "test.parquet")
    if actual_test_sha != expected_test_sha:
        raise InputError(
            "Task 4 test.parquet checksum differs from the locked PR1 manifest"
        )

    task4_manifest = _verify_manifest(
        targets_dir,
        targets_build.CHECKED_FILES,
    )
    if task4_manifest != recorded_task4:
        raise InputError(
            "Current Task 4 SHA256SUMS differs from the locked PR1 manifest"
        )

    task6_lock_sha = canonical.sha256(
        baselines_dir / "baseline_selection.json"
    )
    if task6_lock_sha != manifest["task6_selection"]["baseline_selection_sha256"]:
        raise InputError(
            "Task 6 baseline selection differs from the locked PR1 manifest"
        )
    if baselines_manifest != manifest["task6_selection"]["baselines_manifest"]:
        raise InputError(
            "Task 6 handoff manifest differs from the locked PR1 manifest"
        )

    for resource in ("cpu", "memory"):
        artifact = manifest["model_artifacts"][resource]
        model_path = ml_dir / artifact["file"]
        if canonical.sha256(model_path) != artifact["sha256"]:
            raise InputError(
                f"Locked {resource} model checksum mismatch"
            )

    feature_payload = _load_json(ml_dir / "feature_order.json")
    if feature_payload.get("feature_order") != manifest["feature_order"]:
        raise InputError(
            "feature_order.json disagrees with the locked PR1 manifest"
        )

    return manifest, pr1_manifest, baselines_manifest, decision_sha


def _check_pr1_build(
    manifest: dict,
    commit: str | None,
    allow_dirty: bool,
) -> None:
    """Refuse a PR1 lock built dirty or at a different commit than this run."""
    build = manifest.get("build") or {}
    if allow_dirty:
        return
    if build.get("code_dirty") is not False:
        raise InputError(
            "PR1 decision manifest was not built from a clean checkout"
        )
    if build.get("code_commit") != commit:
        raise InputError(
            f"PR1 decision manifest was built at {build.get('code_commit')}, "
            f"current code is {commit}; run PR1 and PR2 at the same commit"
        )


def _logged_runs(run_log: Path, decision_sha: str) -> list[dict]:
    """Prior final-test runs recorded for this decision manifest."""
    if not run_log.exists():
        return []
    runs = []
    for line in run_log.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            if entry.get("decision_manifest_sha256") == decision_sha:
                runs.append(entry)
    return runs


def _append_run_log(run_log: Path, entry: dict) -> None:
    with run_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _run_fingerprint(
    decision_manifest_sha256: str,
    code_commit: str | None,
) -> str:
    return f"{decision_manifest_sha256}:{code_commit}"


def _existing_fingerprint(out_dir: Path) -> str | None:
    record_path = out_dir / "run_record.json"
    if not record_path.exists():
        return None
    try:
        return _load_json(record_path).get("run_fingerprint")
    except (OSError, json.JSONDecodeError):
        return None


def run(
    targets_dir: Path = DEFAULT_TARGETS_DIR,
    baselines_dir: Path = DEFAULT_BASELINES_DIR,
    ml_dir: Path = DEFAULT_ML_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
    *,
    allow_dirty: bool = False,
    defect_rerun_reason: str | None = None,
    repo: Path = REPO_ROOT,
) -> int:
    targets_dir = Path(targets_dir).resolve()
    baselines_dir = Path(baselines_dir).resolve()
    ml_dir = Path(ml_dir).resolve()
    requested_out = Path(out_dir)
    out_dir = requested_out.resolve()

    if requested_out.is_symlink():
        print("REFUSED: output path must not be a symlink")
        return EXIT_REFUSED
    for source in (targets_dir, baselines_dir, ml_dir):
        if out_dir == source or out_dir in source.parents:
            print("REFUSED: output must be separate from all locked inputs")
            return EXIT_REFUSED

    commit, dirty = canonical.git_state(repo)
    if (commit is None or dirty) and not allow_dirty:
        print(
            "REFUSED: code must be in a clean Git checkout; "
            "use --allow-dirty only for synthetic/local review"
        )
        return EXIT_REFUSED

    started = time.monotonic()
    try:
        manifest, pr1_checksums, baseline_checksums, decision_sha = (
            _verify_pr1_lock(targets_dir, baselines_dir, ml_dir)
        )
        _check_pr1_build(manifest, commit, allow_dirty)
        run_log = ml_dir / RUN_LOG_NAME
        prior_runs = _logged_runs(run_log, decision_sha)
    except (
        InputError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print(f"VERIFY FAILED: {error}")
        return EXIT_INVALID

    fingerprint = _run_fingerprint(decision_sha, commit)
    preserved_dir = None

    if prior_runs and not defect_rerun_reason:
        print(
            "REFUSED: this locked manifest has already been evaluated "
            f"({len(prior_runs)} run(s) in {_relpath(run_log)}); "
            "a documented defect rerun is required"
        )
        return EXIT_REFUSED

    if out_dir.exists():
        existing = _existing_fingerprint(out_dir)
        if not defect_rerun_reason:
            if existing == fingerprint:
                print(
                    "REFUSED: this locked manifest + code commit "
                    "has already been evaluated"
                )
            else:
                print(
                    "REFUSED: final-test output already exists; "
                    "a documented defect rerun is required"
                )
            return EXIT_REFUSED

        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        preserved_dir = out_dir.with_name(
            f"{out_dir.name}.preserved-{stamp}"
        )
        if preserved_dir.exists():
            print(
                f"REFUSED: preservation path already exists: {preserved_dir}"
            )
            return EXIT_REFUSED
        shutil.move(str(out_dir), str(preserved_dir))
    elif defect_rerun_reason and not prior_runs:
        print(
            "REFUSED: --defect-rerun-reason is only valid when "
            "a prior final-test run exists"
        )
        return EXIT_REFUSED

    staging = None
    try:
        # All integrity/duplicate checks above happen before test is opened.
        # Log the run first, so a run that fails after reading test still counts.
        _append_run_log(run_log, {
            "decision_manifest_sha256": decision_sha,
            "code_commit": commit,
            "code_dirty": dirty,
            "out_dir": _relpath(out_dir),
            "defect_rerun_reason": defect_rerun_reason,
            "prior_runs": len(prior_runs),
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        test = pd.read_parquet(targets_dir / "test.parquet")
        history_statistics = pd.read_parquet(
            baselines_dir / "history_statistics.parquet"
        )
        recommendations_test = pd.read_parquet(
            baselines_dir / "recommendations_test.parquet"
        )

        models = {}
        for resource in ("cpu", "memory"):
            models[resource] = joblib.load(
                ml_dir / manifest["model_artifacts"][resource]["file"]
            )

        result = evaluate_final_test(
            test,
            history_statistics,
            recommendations_test,
            models,
            manifest,
            PROFILE,
        )

        if list(result.comparison["policy"]) != list(FINAL_POLICIES):
            raise RuntimeError(
                "Final comparison does not contain exactly "
                "the seven locked policies"
            )
        if result.comparison["policy"].duplicated().any():
            raise RuntimeError(
                "Final comparison contains duplicate policies"
            )
        any_resource = result.comparison.get(
            "any_resource_metric_reported",
            pd.Series(dtype=bool),
        )
        if any_resource.fillna(False).any():
            raise RuntimeError(
                "Any-resource metrics must remain suppressed"
            )

        out_dir.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{out_dir.name}.tmp-",
                dir=out_dir.parent,
            )
        )
        staged = staging / "final_test"
        staged.mkdir()

        result.comparison.to_csv(
            staged / "final_test_policy_comparison.csv",
            index=False,
        )
        result.sensitivity.to_csv(
            staged / "final_test_sensitivity.csv",
            index=False,
        )
        result.predictions.to_parquet(
            staged / "final_test_predictions.parquet",
            index=False,
        )

        run_record = {
            "task": "task7_alibaba_gpu_2020_ml_hybrid",
            "phase": "pr2_final_test",
            "run_fingerprint": fingerprint,
            "decision_manifest_sha256": decision_sha,
            "code_commit": commit,
            "code_dirty": dirty,
            "defect_rerun_reason": defect_rerun_reason,
            "run_log": _relpath(run_log),
            "prior_runs": len(prior_runs),
            "pr1_build": manifest.get("build"),
            "preserved_previous_output": (
                _relpath(preserved_dir)
                if preserved_dir else None
            ),
            "final_policies": list(FINAL_POLICIES),
            "selected_models": manifest["selected_models"],
            "selected_baseline_policy": (
                manifest["task6_selection"]["selected_policy"]
            ),
            "selected_min_runs": (
                manifest["task6_selection"]["selected_min_runs"]
            ),
            "final_population_size": result.final_population_size,
            "n_clipped_test": result.n_clipped,
            "hybrid_safeguard_missing": result.safeguard_missing,
            "task4_test_sha256": (
                manifest["task4_inputs"]["targets_manifest"]["test.parquet"]
            ),
            "pr1_checksums": pr1_checksums,
            "task6_checksums": baseline_checksums,
            "timestamp_utc": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ",
                time.gmtime(),
            ),
        }
        (staged / "run_record.json").write_text(
            json.dumps(
                run_record,
                indent=2,
                sort_keys=True,
                default=str,
            ) + "\n",
            encoding="utf-8",
        )

        metadata = {
            "task": "task7_alibaba_gpu_2020_ml_hybrid",
            "phase": "pr2_final_test",
            "reads_test": True,
            "trains_models": False,
            "changes_selection": False,
            "changes_manifest": False,
            "final_policies": list(FINAL_POLICIES),
            "cpu_result_semantics": manifest["cpu_result_semantics"],
            "primary_resource": manifest["primary_resource"],
            "any_resource_metric_reported": False,
            "final_population_size": result.final_population_size,
            "output_files": list(OUTPUT_FILES),
            "build": canonical.build_info(commit, dirty),
        }
        (staged / "metadata.json").write_text(
            json.dumps(
                metadata,
                indent=2,
                sort_keys=True,
                default=str,
            ) + "\n",
            encoding="utf-8",
        )

        checksums = {
            name: canonical.sha256(staged / name)
            for name in sorted(OUTPUT_FILES)
        }
        (staged / "SHA256SUMS").write_text(
            "".join(
                f"{digest}  {name}\n"
                for name, digest in checksums.items()
            ),
            encoding="utf-8",
        )
        targets_build._publish(staged, out_dir)

    except Exception as error:
        if (
            preserved_dir is not None
            and preserved_dir.exists()
            and not out_dir.exists()
        ):
            shutil.move(str(preserved_dir), str(out_dir))
        print(
            f"BUILD FAILED: {type(error).__name__}: {error}"
        )
        return EXIT_FAILED
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging)

    print(
        f"Built {out_dir} in "
        f"{time.monotonic() - started:.1f} s"
    )
    print(
        f"Final-test population: {result.final_population_size}"
    )
    print("Policies: " + ", ".join(FINAL_POLICIES))
    print("SHA256SUMS:")
    print(
        "".join(
            f"{digest}  {name}\n"
            for name, digest in checksums.items()
        ),
        end="",
    )
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--targets-dir",
        type=Path,
        default=DEFAULT_TARGETS_DIR,
    )
    parser.add_argument(
        "--baselines-dir",
        type=Path,
        default=DEFAULT_BASELINES_DIR,
    )
    parser.add_argument(
        "--ml-dir",
        type=Path,
        default=DEFAULT_ML_DIR,
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="allow an uncommitted synthetic/local review build",
    )
    parser.add_argument(
        "--defect-rerun-reason",
        type=str,
        default=None,
        help=(
            "documented reason for preserving and replacing "
            "an existing final-test run"
        ),
    )
    args = parser.parse_args(argv)
    return run(
        args.targets_dir,
        args.baselines_dir,
        args.ml_dir,
        args.out_dir,
        allow_dirty=args.allow_dirty,
        defect_rerun_reason=args.defect_rerun_reason,
    )


if __name__ == "__main__":
    sys.exit(main())
