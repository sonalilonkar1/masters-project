#!/usr/bin/env python3
"""Task 7 PR1: train/compare Alibaba GPU 2020 ML models, validate Hybrid, lock.

Run locally after Task 4 tables and the Task 6 baselines exist:
    python3 scripts/run_alibaba_gpu_2020_ml.py
    python3 scripts/run_alibaba_gpu_2020_ml.py --force

Reads the Task 4 train+validation tables and the Task 6 handoff (locked
selection, validation recommendations, point-in-time history statistics), after
re-checking both SHA256SUMS. Trains candidate CPU and memory regressors on
train only, selects each resource independently on validation, validates the
fixed Hybrid rule, refits the selected models on train+validation, and writes a
locked decision manifest plus the model artifacts.

PR1 NEVER opens test.parquet. The single final-test evaluation is PR2, run only
after this manifest is locked.

Exit codes: 0 success, 1 invalid input, 2 refused, 3 build/write failure.
"""

from __future__ import annotations

import argparse
import json
import platform
from dataclasses import asdict
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
import numpy as np
import pandas as pd
import sklearn

from scripts import build_alibaba_gpu_2020_canonical as canonical
from scripts import build_alibaba_gpu_2020_targets as targets_build
from scripts import run_alibaba_gpu_2020_baselines as baselines_run
from canonical.schema import ALIBABA_GPU_2020_CAPABILITIES as PROFILE
import baselines.alibaba_gpu_2020 as a6
from features import alibaba_gpu_2020_feature_config as fc
from features.alibaba_gpu_2020_ml_prep import build_feature_matrices
import models.alibaba_gpu_2020_select as sel
import models.alibaba_gpu_2020_candidates as candidates

DEFAULT_TARGETS_DIR = targets_build.DEFAULT_OUT_DIR
DEFAULT_BASELINES_DIR = baselines_run.DEFAULT_OUT_DIR
DEFAULT_OUT_DIR = REPO_ROOT / "data/processed/alibaba_gpu_v2020_ml"

MODEL_FILES = {"cpu": "cpu_model.joblib", "memory": "memory_model.joblib"}
OUTPUT_FILES = (
    "decision_manifest.json",
    "model_selection.json",
    "candidate_models.csv",
    "validation_policy_comparison.csv",
    "validation_ml_hybrid_predictions.parquet",
    "feature_order.json",
    "cpu_model.joblib",
    "memory_model.joblib",
    "metadata.json",
)
# Written inside the output directory by the PR2 final test; its presence means
# this lock has been evaluated on test and must not be replaced.
FINAL_TEST_RUN_LOG = "final_test_runs.jsonl"
EXIT_OK, EXIT_INVALID, EXIT_REFUSED, EXIT_FAILED = 0, 1, 2, 3


class InputError(Exception):
    """Raised when a dependency directory is missing or inconsistent."""


def _verify_manifest(directory: Path, expected_files) -> dict[str, str]:
    """Re-hash the listed files and confirm they match a SHA256SUMS manifest."""
    manifest_path = directory / "SHA256SUMS"
    if not manifest_path.exists():
        raise InputError(f"Missing manifest: {manifest_path}")
    recorded = {}
    for line in manifest_path.read_text().splitlines():
        if line.strip():
            digest, name = line.split("  ", 1)
            recorded[name] = digest
    if set(recorded) != set(expected_files):
        raise InputError(f"{directory} manifest lists {sorted(recorded)}, expected {sorted(expected_files)}")
    for name, digest in recorded.items():
        if canonical.sha256(directory / name) != digest:
            raise InputError(f"Checksum mismatch for {directory / name}")
    return recorded


def _library_versions() -> dict[str, str]:
    versions = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scikit_learn": sklearn.__version__,
        "joblib": joblib.__version__,
    }
    if candidates.HAS_XGBOOST:
        import xgboost
        versions["xgboost"] = xgboost.__version__
    return versions


def _relpath(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def run(targets_dir: Path = DEFAULT_TARGETS_DIR,
        baselines_dir: Path = DEFAULT_BASELINES_DIR,
        out_dir: Path = DEFAULT_OUT_DIR, *, force: bool = False,
        allow_dirty: bool = False, repo: Path = REPO_ROOT) -> int:
    """Verify inputs, train+select+validate, refit, and lock the manifest."""
    targets_dir = Path(targets_dir).resolve()
    baselines_dir = Path(baselines_dir).resolve()
    requested_out = Path(out_dir)
    out_dir = requested_out.resolve()
    for source in (targets_dir, baselines_dir):
        if out_dir == source or out_dir in source.parents:
            print("REFUSED: output must be a separate directory, disjoint from inputs")
            return EXIT_REFUSED
    if requested_out.is_symlink():
        print("REFUSED: output path must not be a symlink")
        return EXIT_REFUSED
    if out_dir.exists() and (not out_dir.is_dir() or not force):
        print(f"REFUSED: {out_dir} exists; choose another directory or use --force")
        return EXIT_REFUSED
    if (out_dir / FINAL_TEST_RUN_LOG).exists():
        print(f"REFUSED: {out_dir} has been evaluated on test ({FINAL_TEST_RUN_LOG}); it cannot be replaced")
        return EXIT_REFUSED
    commit, dirty = canonical.git_state(repo)
    if (commit is None or dirty) and not allow_dirty:
        print("REFUSED: code must be in a clean Git checkout; use --allow-dirty for local review")
        return EXIT_REFUSED
    if not candidates.HAS_XGBOOST and not allow_dirty:
        print("REFUSED: xgboost is not importable; install requirements-lock.txt "
              "(a locked run must compare the full candidate set)")
        return EXIT_REFUSED

    started = time.monotonic()
    try:
        targets_manifest = _verify_manifest(targets_dir, targets_build.CHECKED_FILES)
        baselines_manifest = _verify_manifest(baselines_dir, baselines_run.OUTPUT_FILES)
    except (InputError, OSError) as error:
        print(f"VERIFY FAILED: {error}")
        return EXIT_INVALID

    staging = None
    try:
        # ---- Load inputs (TRAIN + VALIDATION only; test is never opened) ----
        train = pd.read_parquet(targets_dir / "train.parquet")
        validation = pd.read_parquet(targets_dir / "validation.parquet")
        history_statistics = pd.read_parquet(baselines_dir / "history_statistics.parquet")
        baselines_validation = pd.read_parquet(baselines_dir / "recommendations_validation.parquet")
        task6_selection = json.loads((baselines_dir / "baseline_selection.json").read_text())
        task4_metadata = json.loads((targets_dir / "metadata.json").read_text())
    
        # ---- Features, candidate comparison, selection -----------------------
        matrices = build_feature_matrices(train, validation, history_statistics)
        candidate_table, selections, fitted_by_resource = sel.compare_and_select(matrices, PROFILE)

        common = a6.freeze_common_validation_population(validation)
        validation_hybrid = sel.evaluate_validation_policies(
            matrices, baselines_validation, selections, fitted_by_resource, PROFILE,
            common_population=common,
        )

        # ---- Refit selected models on train+validation -----------------------
        refit_models = sel.refit_on_train_plus_validation(matrices, selections)

        out_dir.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.tmp-", dir=out_dir.parent))
        staged = staging / "ml"
        staged.mkdir()

        # ---- Persist model artifacts + supporting tables ---------------------
        model_checksums = {}
        for resource, model in refit_models.items():
            path = staged / MODEL_FILES[resource]
            joblib.dump(model, path)
            model_checksums[resource] = canonical.sha256(path)

        candidate_table.to_csv(staged / "candidate_models.csv", index=False)
        validation_hybrid.comparison.to_csv(staged / "validation_policy_comparison.csv", index=False)
        (staged / "feature_order.json").write_text(
            json.dumps({"feature_order": matrices.feature_order}, indent=2) + "\n", encoding="utf-8")

        validation_predictions = matrices.val_rows[
            [
                "role_key",
                "occurrence_id",
                "recurrence_key",
                fc.CPU_TARGET_STATUS,
                fc.TARGET_CPU,
                fc.MEMORY_TARGET_STATUS,
                fc.TARGET_MEMORY,
            ]
        ].copy()

        validation_predictions["ml_recommended_cpu"] = (
            validation_hybrid.ml_predictions["cpu"]
        )
        validation_predictions["ml_recommended_memory"] = (
            validation_hybrid.ml_predictions["memory"]
        )

        validation_predictions["hybrid_recommended_cpu"] = (
            validation_hybrid.hybrid_recommendations["cpu"]
        )
        validation_predictions["hybrid_recommended_memory"] = (
            validation_hybrid.hybrid_recommendations["memory"]
        )

        for resource in sel.RESOURCES:
            validation_predictions[f"hybrid_{resource}_safeguard_missing"] = (
                np.asarray(validation_hybrid.safeguard_missing[resource], dtype=bool)
            )

        # Rows of the frozen validation population where Hybrid fell back to ML.
        in_population = matrices.val_rows["role_key"].isin(set(common["role_key"])).to_numpy()
        safeguard_missing_validation = {
            resource: int(np.count_nonzero(
                np.asarray(validation_hybrid.safeguard_missing[resource], dtype=bool) & in_population))
            for resource in sel.RESOURCES
        }

        validation_predictions["recommended_cpu_unit"] = (
            fc.RESOURCE_UNIT["cpu"]
        )
        validation_predictions["recommended_memory_unit"] = (
            fc.RESOURCE_UNIT["memory"]
        )
        validation_predictions["recommended_resource_scope"] = (
            fc.RESOURCE_SCOPE
        )

        validation_predictions.to_parquet(
            staged / "validation_ml_hybrid_predictions.parquet",
            index=False,
        )
        
        selection_payload = {
            resource: {
                "selected_model": s.selected_model,
                "hyperparameters": s.hyperparameters,
                "validation_metrics": s.validation_metrics,
                "n_clipped_validation": s.n_clipped_validation,
                "selection_order": list(s.selection_order),
            }
            for resource, s in selections.items()
        }
        (staged / "model_selection.json").write_text(
            json.dumps(selection_payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

        # ---- Decision manifest (locked; written before any test read) --------
        manifest = {
            "task": "task7_alibaba_gpu_2020_ml_hybrid",
            "phase": "pr1_validation_lock",
            "dataset_id": PROFILE.dataset_id,
            "profile": asdict(PROFILE),
            "task6_selection": {
                "selected_policy": task6_selection.get("selected_policy"),
                "selected_min_runs": task6_selection.get("selected_min_runs"),
                "baseline_selection_sha256": canonical.sha256(baselines_dir / "baseline_selection.json"),
                "baselines_manifest": baselines_manifest,
            },
            "task4_inputs": {
                "targets_dir": _relpath(targets_dir),
                "targets_manifest": targets_manifest,
                "task3_source_commit": (task4_metadata["source_provenance"]["build"]["code_commit"]),
                "task4_code_commit": (task4_metadata["build"]["code_commit"]),
            },
            "selected_models": {r: selections[r].selected_model for r in sel.RESOURCES},
            "model_hyperparameters": {r: selections[r].hyperparameters for r in sel.RESOURCES},
            "model_artifacts": {r: {"file": MODEL_FILES[r], "sha256": model_checksums[r]} for r in sel.RESOURCES},
            "feature_list": list(fc.ALIBABA_GPU_2020_FEATURES),
            "missing_indicator_columns": list(fc.ALIBABA_GPU_2020_HISTORY_MISSING_INDICATORS),
            "feature_order": matrices.feature_order,
            "hybrid_rule": sel.HYBRID_RULE,
            "hybrid_safeguard": "task6_selected_baseline",
            "negative_prediction_rule": sel.NEGATIVE_PREDICTION_RULE,
            "model_selection_order": list(sel.MODEL_SELECTION_ORDER),
            "candidate_models": sorted(candidates.build_candidate_models()),
            "skipped_candidates": {} if candidates.HAS_XGBOOST else {"xgboost": "not importable"},
            "non_selectable_models": sorted(sel.NON_SELECTABLE_MODELS),
            "random_seed": candidates.RANDOM_SEED,
            "library_versions": _library_versions(),
            "units": fc.RESOURCE_UNIT,
            "resource_scope": fc.RESOURCE_SCOPE,
            "cpu_result_semantics": "average_usage",
            "primary_resource": "memory",
            "any_resource_metric_reported": False,
            "validation_population_size": int(len(common)),
            "build": canonical.build_info(commit, dirty),
            "lock_timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        (staged / "decision_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

        metadata = {
            "task": "task7_alibaba_gpu_2020_ml_hybrid",
            "phase": "pr1_validation_lock",
            "reads_test": False,
            "hybrid_safeguard_missing_validation": safeguard_missing_validation,
            "selected_models": manifest["selected_models"],
            "validation_population_size": int(len(common)),
            "split_row_counts": {"train": int(len(train)), "validation": int(len(validation))},
            "output_files": list(OUTPUT_FILES),
            "build": canonical.build_info(commit, dirty),
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
    print(f"Selected CPU model: {selections['cpu'].selected_model}")
    print(f"Selected memory model: {selections['memory'].selected_model}")
    print("SHA256SUMS:")
    print("".join(f"{digest}  {name}\n" for name, digest in checksums.items()), end="")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--targets-dir", type=Path, default=DEFAULT_TARGETS_DIR)
    parser.add_argument("--baselines-dir", type=Path, default=DEFAULT_BASELINES_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--force", action="store_true", help="replace a complete build after staging")
    parser.add_argument("--allow-dirty", action="store_true", help="allow an uncommitted local review build")
    args = parser.parse_args(argv)
    return run(args.targets_dir, args.baselines_dir, args.out_dir, force=args.force, allow_dirty=args.allow_dirty)


if __name__ == "__main__":
    sys.exit(main())
