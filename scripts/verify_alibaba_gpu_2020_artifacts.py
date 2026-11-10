#!/usr/bin/env python3
"""Task 8: verify the frozen Alibaba GPU 2020 pipeline and publish verification evidence.

Verification-only. This script never trains, selects, tunes, evaluates test rows,
or rewrites Task 3/4/6/7 artifacts. A failure is reported and must be returned
to the owning task.

Default inputs:
  data/processed/alibaba_gpu_v2020
  data/processed/alibaba_gpu_v2020_targets
  data/processed/alibaba_gpu_v2020_baselines
  data/processed/alibaba_gpu_v2020_ml
  data/processed/alibaba_gpu_v2020_final_test

Default outputs:
  reports/results/alibaba_gpu_2020/verification/artifact_manifest.json
  reports/results/alibaba_gpu_2020/verification/verification_report.md
  reports/results/alibaba_gpu_2020/verification/reproduction_metadata.json

Exit codes: 0 verified, 1 verification failed, 2 refused, 3 write failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT, REPO_ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

DATASET_ID = "alibaba_gpu_v2020"
SCHEMA_VERSION = "0.2.0"
FINAL_POLICIES = ("Request", "Mean", "P90", "P95", "P99", "ML", "Hybrid")

DEFAULT_CANONICAL_DIR = REPO_ROOT / "data/processed/alibaba_gpu_v2020"
DEFAULT_TARGETS_DIR = REPO_ROOT / "data/processed/alibaba_gpu_v2020_targets"
DEFAULT_BASELINES_DIR = REPO_ROOT / "data/processed/alibaba_gpu_v2020_baselines"
DEFAULT_ML_DIR = REPO_ROOT / "data/processed/alibaba_gpu_v2020_ml"
DEFAULT_FINAL_DIR = REPO_ROOT / "data/processed/alibaba_gpu_v2020_final_test"
DEFAULT_OUT_DIR = REPO_ROOT / "reports/results/alibaba_gpu_2020/verification"

EXIT_OK, EXIT_FAILED, EXIT_REFUSED, EXIT_WRITE_FAILED = 0, 1, 2, 3


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


class VerificationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_sha256sums(directory: Path) -> dict[str, str]:
    path = directory / "SHA256SUMS"
    if not path.exists():
        raise VerificationError(f"missing SHA256SUMS: {path}")
    recorded: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split("  ", 1)
        recorded[name] = digest
    return recorded


def verify_sha256sums(directory: Path) -> tuple[bool, str, dict[str, str]]:
    try:
        recorded = parse_sha256sums(directory)
    except Exception as exc:
        return False, str(exc), {}
    failures: list[str] = []
    for name, digest in recorded.items():
        path = directory / name
        if not path.exists():
            failures.append(f"missing {name}")
            continue
        actual = sha256(path)
        if actual != digest:
            failures.append(f"{name}: expected {digest}, got {actual}")
    if failures:
        return False, "; ".join(failures), recorded
    return True, f"{len(recorded)} checksums match", recorded


def artifact_row_count(path: Path) -> int | None:
    try:
        if path.suffix == ".parquet":
            return int(len(pd.read_parquet(path)))
        if path.suffix == ".csv":
            return int(len(pd.read_csv(path)))
    except Exception:
        return None
    return None


def git_state(repo: Path) -> tuple[str | None, bool]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=repo, text=True
            ).strip()
        )
        return commit, dirty
    except Exception:
        return None, True


def _first_present(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _metadata_contract(metadata: dict[str, Any], label: str) -> list[Check]:
    dataset = _first_present(metadata, "dataset_id")
    schema = _first_present(metadata, "schema_version")
    return [
        Check(
            f"{label}.dataset_id",
            dataset == DATASET_ID,
            f"expected {DATASET_ID!r}, found {dataset!r}",
        ),
        Check(
            f"{label}.schema_version",
            schema == SCHEMA_VERSION,
            f"expected {SCHEMA_VERSION!r}, found {schema!r}",
        ),
    ]


def _forbidden_eval_columns(columns: list[str]) -> list[str]:
    bad: list[str] = []
    for col in columns:
        low = col.lower()
        if "gpu" in low:
            bad.append(col)
        if "any_resource" in low and col != "any_resource_metric_reported":
            bad.append(col)
    return sorted(set(bad))


def _artifact_entries(stage: str, directory: Path, recorded: dict[str, str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for name, digest in sorted(recorded.items()):
        path = directory / name
        entry: dict[str, Any] = {
            "stage": stage,
            "path": str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path),
            "sha256": digest,
            "row_count": artifact_row_count(path),
        }
        entries.append(entry)
    return entries


def verify_pipeline(
    canonical_dir: Path,
    targets_dir: Path,
    baselines_dir: Path,
    ml_dir: Path,
    final_dir: Path,
) -> tuple[list[Check], dict[str, Any]]:
    checks: list[Check] = []
    manifest: dict[str, Any] = {
        "dataset_id": DATASET_ID,
        "schema_version": SCHEMA_VERSION,
        "artifacts": [],
    }

    stage_dirs = {
        "task3_canonical": canonical_dir,
        "task4_targets": targets_dir,
        "task6_baselines": baselines_dir,
        "task7_pr1_ml": ml_dir,
        "task7_pr2_final_test": final_dir,
    }
    stage_manifests: dict[str, dict[str, str]] = {}
    for stage, directory in stage_dirs.items():
        ok, detail, recorded = verify_sha256sums(directory)
        checks.append(Check(f"{stage}.sha256", ok, detail))
        stage_manifests[stage] = recorded
        if recorded:
            manifest["artifacts"].extend(_artifact_entries(stage, directory, recorded))

    # Metadata contract: derived artifacts must identify dataset and schema.
    for label, path in (
        ("task3", canonical_dir / "metadata.json"),
        ("task4", targets_dir / "metadata.json"),
        ("task6", baselines_dir / "metadata.json"),
        ("task7_pr1", ml_dir / "metadata.json"),
        ("task7_pr2", final_dir / "metadata.json"),
    ):
        if not path.exists():
            checks.append(Check(f"{label}.metadata_exists", False, f"missing {path}"))
            continue
        metadata = load_json(path)
        checks.extend(_metadata_contract(metadata, label))

    # Task 6 lock.
    baseline_selection_path = baselines_dir / "baseline_selection.json"
    if baseline_selection_path.exists():
        baseline = load_json(baseline_selection_path)
        policy = baseline.get("selected_policy")
        min_runs = baseline.get("selected_min_runs")
        checks.append(Check(
            "task6.selected_policy",
            policy in ("Mean", "P90", "P95", "P99"),
            f"selected_policy={policy!r}",
        ))
        checks.append(Check(
            "task6.selected_min_runs",
            min_runs in (1, 3, 5, 10),
            f"selected_min_runs={min_runs!r}",
        ))

    # PR1 locked manifest.
    decision_path = ml_dir / "decision_manifest.json"
    decision: dict[str, Any] = {}
    decision_sha = None
    if decision_path.exists():
        decision = load_json(decision_path)
        decision_sha = sha256(decision_path)
        checks.append(Check(
            "task7_pr1.phase",
            decision.get("phase") == "pr1_validation_lock",
            f"phase={decision.get('phase')!r}",
        ))
        checks.append(Check(
            "task7_pr1.cpu_semantics",
            decision.get("cpu_result_semantics") == "average_usage",
            f"cpu_result_semantics={decision.get('cpu_result_semantics')!r}",
        ))
        checks.append(Check(
            "task7_pr1.primary_resource",
            decision.get("primary_resource") == "memory",
            f"primary_resource={decision.get('primary_resource')!r}",
        ))
        checks.append(Check(
            "task7_pr1.no_any_resource",
            decision.get("any_resource_metric_reported") is False,
            f"any_resource_metric_reported={decision.get('any_resource_metric_reported')!r}",
        ))
        models = decision.get("selected_models", {})
        checks.append(Check(
            "task7_pr1.models_locked",
            set(models) == {"cpu", "memory"},
            f"selected_models={models!r}",
        ))

    # Final-test table.
    comparison_path = final_dir / "final_test_policy_comparison.csv"
    if comparison_path.exists():
        comparison = pd.read_csv(comparison_path)
        policies = tuple(comparison["policy"].tolist()) if "policy" in comparison else ()
        checks.append(Check(
            "task7_pr2.seven_policies",
            policies == FINAL_POLICIES,
            f"policies={policies}",
        ))
        required_denominators = {"valid_cpu_violation_count", "valid_memory_violation_count"}
        checks.append(Check(
            "task7_pr2.separate_denominators",
            required_denominators.issubset(comparison.columns),
            f"required={sorted(required_denominators)}, columns={list(comparison.columns)}",
        ))
        if "cpu_result_semantics" in comparison:
            cpu_ok = set(comparison["cpu_result_semantics"].dropna()) == {"average_usage"}
        else:
            cpu_ok = False
        checks.append(Check(
            "task7_pr2.cpu_semantics",
            cpu_ok,
            "all rows must carry cpu_result_semantics=average_usage",
        ))
        if "primary_resource" in comparison:
            memory_ok = set(comparison["primary_resource"].dropna()) == {"memory"}
        else:
            memory_ok = False
        checks.append(Check(
            "task7_pr2.memory_primary",
            memory_ok,
            "all rows must carry primary_resource=memory",
        ))
        forbidden = _forbidden_eval_columns(list(comparison.columns))
        checks.append(Check(
            "task7_pr2.no_gpu_or_any_resource_metrics",
            not forbidden,
            f"forbidden columns={forbidden}",
        ))

    # PR1 lock must predate PR2 final run.
    run_record_path = final_dir / "run_record.json"
    run_record: dict[str, Any] = {}
    if run_record_path.exists():
        run_record = load_json(run_record_path)
        lock_ts = decision.get("lock_timestamp_utc")
        run_ts = run_record.get("timestamp_utc")
        checks.append(Check(
            "task7.lock_before_final_test",
            bool(lock_ts and run_ts and lock_ts < run_ts),
            f"lock={lock_ts!r}, final_run={run_ts!r}",
        ))
        checks.append(Check(
            "task7.final_run_traces_manifest",
            bool(decision_sha and run_record.get("decision_manifest_sha256") == decision_sha),
            f"expected manifest sha={decision_sha!r}, run_record={run_record.get('decision_manifest_sha256')!r}",
        ))

        # Task 8 needs explicit evidence. Do not infer "exactly once" from absence.
        evaluator_calls = run_record.get("test_evaluator_call_count")
        target_reads = run_record.get("test_target_read_count")
        checks.append(Check(
            "task7.test_evaluator_call_count",
            evaluator_calls == 1,
            f"expected explicit test_evaluator_call_count=1, found {evaluator_calls!r}",
        ))
        checks.append(Check(
            "task7.test_target_read_count",
            target_reads == 1,
            f"expected explicit test_target_read_count=1, found {target_reads!r}",
        ))
        run_id = run_record.get("run_id")
        checks.append(Check(
            "task7.final_run_id",
            isinstance(run_id, str) and bool(run_id.strip()),
            f"expected non-empty run_id, found {run_id!r}",
        ))

    # Prediction artifact traceability and expected units/scope.
    pred_path = final_dir / "final_test_predictions.parquet"
    if pred_path.exists():
        pred = pd.read_parquet(pred_path)
        required = {
            "role_key",
            "recurrence_key",
            "recommended_cpu_unit",
            "recommended_memory_unit",
            "recommended_resource_scope",
        }
        checks.append(Check(
            "task7.prediction_columns",
            required.issubset(pred.columns),
            f"missing={sorted(required - set(pred.columns))}",
        ))
        if required.issubset(pred.columns):
            checks.append(Check(
                "task7.prediction_units_scope",
                set(pred["recommended_cpu_unit"].dropna()) == {"percent_of_vcpu"}
                and set(pred["recommended_memory_unit"].dropna()) == {"gb"}
                and set(pred["recommended_resource_scope"].dropna()) == {"task_role_per_instance"},
                "expected CPU=percent_of_vcpu, memory=gb, scope=task_role_per_instance",
            ))

    manifest["verification_timestamp_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    manifest["decision_manifest_sha256"] = decision_sha
    manifest["checks"] = [asdict(c) for c in checks]
    manifest["verified"] = all(c.ok for c in checks)
    return checks, manifest


def render_report(checks: list[Check], manifest: dict[str, Any]) -> str:
    passed = sum(c.ok for c in checks)
    failed = len(checks) - passed
    lines = [
        "# Alibaba GPU 2020 Verification Report",
        "",
        f"- Dataset: `{DATASET_ID}`",
        f"- Schema: `{SCHEMA_VERSION}`",
        f"- Result: **{'PASS' if failed == 0 else 'FAIL'}**",
        f"- Checks: {passed} passed, {failed} failed",
        f"- Generated: `{manifest['verification_timestamp_utc']}`",
        "",
        "## Verification checks",
        "",
        "| Check | Result | Detail |",
        "|---|---|---|",
    ]
    for check in checks:
        detail = check.detail.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{check.name}` | {'PASS' if check.ok else 'FAIL'} | {detail} |")

    lines += [
        "",
        "## Interpretation",
        "",
        "This report is verification-only. A failed check must be returned to the task that owns the artifact; Task 8 does not repair earlier pipeline behavior.",
        "",
        "The verifier does not rerun or retune the final test.",
        "",
    ]
    return "\n".join(lines)


def reproduction_metadata(repo: Path) -> dict[str, Any]:
    commit, dirty = git_state(repo)
    return {
        "dataset_id": DATASET_ID,
        "schema_version": SCHEMA_VERSION,
        "python_version": platform.python_version(),
        "pandas_version": pd.__version__,
        "code_commit": commit,
        "code_dirty": dirty,
        "verification_command": "python scripts/verify_alibaba_gpu_2020_artifacts.py",
        "full_test_command": "python -m pytest -q",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir).resolve()
    if out_dir.exists() and any(out_dir.iterdir()) and not args.force:
        print(f"REFUSED: {out_dir} exists and is non-empty; use --force")
        return EXIT_REFUSED

    try:
        checks, manifest = verify_pipeline(
            Path(args.canonical_dir).resolve(),
            Path(args.targets_dir).resolve(),
            Path(args.baselines_dir).resolve(),
            Path(args.ml_dir).resolve(),
            Path(args.final_dir).resolve(),
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "artifact_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        (out_dir / "verification_report.md").write_text(
            render_report(checks, manifest) + "\n",
            encoding="utf-8",
        )
        (out_dir / "reproduction_metadata.json").write_text(
            json.dumps(reproduction_metadata(REPO_ROOT), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"VERIFY FAILED: {type(exc).__name__}: {exc}")
        return EXIT_FAILED

    failed = [c for c in checks if not c.ok]
    print(f"Verification checks: {len(checks) - len(failed)} passed, {len(failed)} failed")
    for check in failed:
        print(f"FAIL: {check.name}: {check.detail}")
    print(f"Wrote {out_dir}")
    return EXIT_OK if not failed else EXIT_FAILED


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-dir", type=Path, default=DEFAULT_CANONICAL_DIR)
    parser.add_argument("--targets-dir", type=Path, default=DEFAULT_TARGETS_DIR)
    parser.add_argument("--baselines-dir", type=Path, default=DEFAULT_BASELINES_DIR)
    parser.add_argument("--ml-dir", type=Path, default=DEFAULT_ML_DIR)
    parser.add_argument("--final-dir", type=Path, default=DEFAULT_FINAL_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
