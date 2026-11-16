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
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT, REPO_ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.build_alibaba_gpu_2020_targets import EXIT_INVALID

DATASET_ID = "alibaba_gpu_v2020"
SCHEMA_VERSION = "0.2.0"
FINAL_POLICIES = ("Request", "Mean", "P90", "P95", "P99", "ML", "Hybrid")

COMPARISON_COLUMNS = (
    "policy",
    "row_count",
    "valid_cpu_violation_count",
    "valid_memory_violation_count",
    "valid_cpu_utilization_count",
    "valid_memory_utilization_count",
    "cpu_violation_pct",
    "memory_violation_pct",
    "average_cpu_utilization",
    "average_memory_utilization",
    "average_cpu_waste",
    "average_memory_waste",
    "average_cpu_shortfall",
    "average_memory_shortfall",
    "cpu_result_semantics",
    "primary_resource",
    "any_resource_metric_reported",
)
SENSITIVITY_SCENARIOS = (
    "occurrence_weighted",
    "same_second_excluded",
    "same_second_only",
    "multi_instance",
    "group_weighted",
)
SENSITIVITY_COLUMNS = COMPARISON_COLUMNS + ("sensitivity", "n_groups")
PUBLISHED_CANONICAL_REQUIRED_FILES = {"count_report.md", "metadata.json"}
AUDITED_EXECUTION_REFERENCE_COMMIT = "ea6aa08458aace364cd33529ce77de894bcd76ad"
AUDITED_EXECUTION_PATHS = (
    "scripts/run_alibaba_gpu_2020_final_test.py",
    "src/models/alibaba_gpu_2020_final_test.py",
    "src/evaluation/evaluator.py",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")

TASK3_REQUIRED_FILES = {
    "role_occurrence.parquet",
    "instance.parquet",
    "rejected.parquet",
    "metadata.json",
    "count_report.md",
}
TASK4_REQUIRED_FILES = {
    "train.parquet", "validation.parquet", "test.parquet", "metadata.json"
}
TASK6_REQUIRED_FILES = {
    "baseline_selection.json",
    "validation_comparison.csv",
    "sensitivity_validation.csv",
    "history_statistics.parquet",
    "recommendations_train.parquet",
    "recommendations_validation.parquet",
    "recommendations_test.parquet",
    "metadata.json",
}
TASK7_PR1_REQUIRED_FILES = {
    "decision_manifest.json",
    "model_selection.json",
    "candidate_models.csv",
    "validation_policy_comparison.csv",
    "validation_ml_hybrid_predictions.parquet",
    "feature_order.json",
    "cpu_model.joblib",
    "memory_model.joblib",
    "metadata.json",
}
TASK7_FINAL_REQUIRED_FILES = {
    "final_test_policy_comparison.csv",
    "final_test_sensitivity.csv",
    "final_test_predictions.parquet",
    "run_record.json",
    "metadata.json",
}

PUBLISHED_ML_REQUIRED_FILES = {
    "SHA256SUMS",
    "candidate_models.csv",
    "decision_manifest.json",
    "feature_order.json",
    "final_test_runs.jsonl",
    "metadata.json",
    "model_selection.json",
    "validation_policy_comparison.csv",
}
PUBLISHED_FINAL_REQUIRED_FILES = {
    "SHA256SUMS",
    "final_test_policy_comparison.csv",
    "final_test_sensitivity.csv",
    "metadata.json",
    "run_record.json",
}
REPORT_ROOT = REPO_ROOT / "reports/results/alibaba_gpu_2020"

UNVERIFIED_ITEMS = [
    {
        "item": "Task 4 split isolation / history timing / target-value consistency on test rows",
        "reason": (
            "Task 8 deliberately does not reopen test target values. Test-side value-level "
            "checks are therefore inherited from the frozen Task 4 artifact checksums and metadata, "
            "not independently recomputed here."
        ),
    },
    {
        "item": "Task 7 model-prediction reproduction on the real test feature rows",
        "reason": (
            "The verifier checks the locked model checksums, feature-order lock, saved prediction "
            "artifact checksum and run provenance, but does not rerun model inference in Task 8."
        ),
    },
]

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

    def __post_init__(self) -> None:
        if not isinstance(self.ok, (bool, np.bool_)):
            raise TypeError("Check.ok must be a boolean")
        self.ok = bool(self.ok)


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


def verify_sha256sums(
    directory: Path,
    *,
    required_files: set[str] | None = None,
    exact_files: bool = False,
) -> tuple[bool, str, dict[str, str]]:
    try:
        recorded = parse_sha256sums(directory)
    except Exception as exc:
        return False, str(exc), {}

    if not recorded:
        return False, f"empty SHA256SUMS: {directory / 'SHA256SUMS'}", {}

    failures: list[str] = []
    recorded_names = set(recorded)
    if required_files:
        missing_from_manifest = sorted(required_files - recorded_names)
        if missing_from_manifest:
            failures.append(
                f"required artifacts absent from SHA256SUMS: {missing_from_manifest}"
            )
        if exact_files:
            unexpected = sorted(recorded_names - required_files)
            if unexpected:
                failures.append(
                    f"unexpected artifacts in SHA256SUMS: {unexpected}"
                )

    for name, digest in recorded.items():
        path = directory / name
        if not path.exists():
            failures.append(f"missing {name}")
            continue
        if not path.is_file():
            failures.append(f"not a regular file: {name}")
            continue
        actual = sha256(path)
        if actual != digest:
            failures.append(f"{name}: expected {digest}, got {actual}")

    if failures:
        return False, "; ".join(failures), recorded
    return True, f"{len(recorded)} checksums match", recorded

def _parse_utc_timestamp(value: str | None) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing or invalid UTC timestamp: {value!r}")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid UTC timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"UTC timestamp lacks timezone: {value!r}")
    return parsed.astimezone(timezone.utc)


def _timestamp_order_check(
    name: str,
    earlier: str | None,
    later: str | None,
) -> Check:
    try:
        earlier_dt = _parse_utc_timestamp(earlier)
        later_dt = _parse_utc_timestamp(later)
        ok = earlier_dt <= later_dt
        detail = f"earlier={earlier!r}, later={later!r}"
    except (TypeError, ValueError) as exc:
        ok = False
        detail = f"invalid timestamps: earlier={earlier!r}, later={later!r}; {exc}"
    return Check(name, ok, detail)

def artifact_row_count(path: Path) -> int | None:
    """Return row count without reading Parquet row data.

    This is especially important for Task 4 test.parquet: Task 8 must not reopen
    test target values merely to count rows.
    """
    try:
        if path.suffix == ".parquet":
            return int(pq.ParquetFile(path).metadata.num_rows)
        if path.suffix == ".csv":
            with path.open("rb") as handle:
                # Header is not a data row; blank trailing lines are ignored.
                return max(sum(1 for line in handle if line.strip()) - 1, 0)
    except Exception:
        return None
    return None


def _load_run_log(path: Path, decision_sha: str) -> list[dict[str, Any]]:
    if not path.exists():
        raise VerificationError(f"missing final-test run log: {path}")
    matches: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise VerificationError(
                f"invalid JSON in {path} line {lineno}: {exc}"
            ) from exc
        if entry.get("decision_manifest_sha256") == decision_sha:
            matches.append(entry)
    return matches

def _check_run_history(
    *,
    run_record: dict[str, Any],
    decision: dict[str, Any],
    decision_sha: str,
    run_log_path: Path,
    final_dir: Path,
) -> list[Check]:
    checks: list[Check] = []

    try:
        matches = _load_run_log(
            run_log_path,
            decision_sha,
        )
    except VerificationError as exc:
        return [
            Check(
                "task7.run_log",
                False,
                str(exc),
            )
        ]

    run_id = run_record.get("run_id")

    matching_ids = [
        entry
        for entry in matches
        if entry.get("run_id") == run_id
    ]

    checks.append(
        Check(
            "task7.run_log_contains_final_run",
            len(matching_ids) == 1,
            (
                f"matching entries for "
                f"run_id={run_id!r}: "
                f"{len(matching_ids)}"
            ),
        )
    )

    if len(matching_ids) == 1:
        logged = matching_ids[0]

        # Only compare fields that are expected to exist in both
        # the pre-test log and the post-test run record.
        fields_to_match = (
            "run_id",
            "decision_manifest_sha256",
            "code_commit",
            "defect_rerun_reason",
        )

        mismatches = {
            key: (
                logged.get(key),
                run_record.get(key),
            )
            for key in fields_to_match
            if logged.get(key)
            != run_record.get(key)
        }

        checks.append(
            Check(
                "task7.run_log_matches_run_record",
                not mismatches,
                f"mismatches={mismatches}",
            )
        )

        # Validate the logged output directory independently.
        logged_out_dir = logged.get("out_dir")

        try:
            expected_out_dir = str(
                final_dir.resolve().relative_to(
                    REPO_ROOT.resolve()
                )
            )
        except ValueError:
            expected_out_dir = str(
                final_dir.resolve()
            )

        checks.append(
            Check(
                "task7.run_log_output_directory",
                logged_out_dir
                == expected_out_dir,
                (
                    f"logged_out_dir="
                    f"{logged_out_dir!r}, "
                    f"expected_out_dir="
                    f"{expected_out_dir!r}"
                ),
            )
        )

        # The run log is written before the test is opened,
        # while run_record.json is written after evaluation.
        # Therefore timestamps should be ordered, not equal.
        log_timestamp = logged.get(
            "timestamp_utc"
        )
        record_timestamp = run_record.get(
            "timestamp_utc"
        )

        try:
            log_time = _parse_utc_timestamp(
                log_timestamp
            )
            record_time = _parse_utc_timestamp(
                record_timestamp
            )

            timestamp_ok = (
                log_time <= record_time
            )

            timestamp_detail = (
                f"run_log={log_timestamp!r}, "
                f"run_record={record_timestamp!r}"
            )

        except (TypeError, ValueError):
            timestamp_ok = False

            timestamp_detail = (
                "invalid timestamps: "
                f"run_log={log_timestamp!r}, "
                f"run_record="
                f"{record_timestamp!r}"
            )

        checks.append(
            Check(
                "task7.run_log_precedes_run_record",
                timestamp_ok,
                timestamp_detail,
            )
        )

        # Verify complete chronology independently so malformed log/record
        # timestamps become a failed check rather than an internal exception.
        lock_timestamp = decision.get("lock_timestamp_utc")
        try:
            lock_time = _parse_utc_timestamp(lock_timestamp)
            chronology_log_time = _parse_utc_timestamp(log_timestamp)
            chronology_record_time = _parse_utc_timestamp(record_timestamp)
            chronology_ok = lock_time <= chronology_log_time <= chronology_record_time
            chronology_detail = (
                f"lock={lock_timestamp!r}, run_log={log_timestamp!r}, "
                f"run_record={record_timestamp!r}"
            )
        except (TypeError, ValueError) as exc:
            chronology_ok = False
            chronology_detail = (
                "invalid chronology timestamps: "
                f"lock={lock_timestamp!r}, run_log={log_timestamp!r}, "
                f"run_record={record_timestamp!r}; {exc}"
            )

        checks.append(Check(
            "task7.final_run_chronology",
            chronology_ok,
            chronology_detail,
        ))

    ids = [
        entry.get("run_id")
        for entry in matches
    ]

    unique_ids = (
        len(ids) == len(set(ids))
        and all(
            isinstance(value, str)
            and bool(value)
            for value in ids
        )
    )

    documented = all(
        index == 0
        or bool(
            entry.get(
                "defect_rerun_reason"
            )
        )
        for index, entry
        in enumerate(matches)
    )

    checks.append(
        Check(
            "task7.run_history_documented",
            bool(matches)
            and unique_ids
            and documented,
            (
                f"matching_runs="
                f"{len(matches)}, "
                f"unique_run_ids="
                f"{unique_ids}, "
                f"documented_reruns="
                f"{documented}"
            ),
        )
    )

    decision_commit = (
        decision.get("build") or {}
    ).get("code_commit")

    checks.append(
        Check(
            "task7.final_run_code_commit_matches_lock",
            bool(decision_commit)
            and run_record.get(
                "code_commit"
            ) == decision_commit,
            (
                f"decision_commit="
                f"{decision_commit!r}, "
                f"run_commit="
                f"{run_record.get('code_commit')!r}"
            ),
        )
    )

    return checks


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



def _safe_artifact_path(directory: Path, name: str) -> tuple[Path | None, str | None]:
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        return None, f"unsafe artifact path {name!r}"
    candidate = (directory / name).resolve()
    root = directory.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None, f"artifact path escapes stage directory: {name!r}"
    return candidate, None


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value))


def _checksum_binding_check(
    label: str,
    directory: Path,
    expected: Any,
    *,
    required_names: set[str] | None = None,
    recorded: dict[str, str] | None = None,
    exact_names: bool = False,
) -> Check:
    if not isinstance(expected, dict) or not expected:
        return Check(label, False, f"missing checksum binding: {expected!r}")

    failures: list[str] = []
    expected_names = set(expected)
    if required_names:
        missing = sorted(required_names - expected_names)
        if missing:
            failures.append(f"missing expected checksum entries={missing}")
        if exact_names:
            unexpected = sorted(expected_names - required_names)
            if unexpected:
                failures.append(f"unexpected checksum entries={unexpected}")

    for name, digest in sorted(expected.items(), key=lambda item: str(item[0])):
        if not isinstance(name, str) or not _valid_sha256(digest):
            failures.append(f"invalid checksum entry {name!r}={digest!r}")
            continue
        path, path_error = _safe_artifact_path(directory, name)
        if path_error:
            failures.append(path_error)
            continue
        if recorded is not None and recorded.get(name) != digest:
            failures.append(
                f"{name}: frozen decision={digest}, stage manifest={recorded.get(name)!r}"
            )
        if path is None or not path.is_file():
            failures.append(f"missing {name}")
            continue
        actual = sha256(path)
        if actual != digest:
            failures.append(f"{name}: expected {digest}, got {actual}")

    return Check(
        label,
        not failures,
        "; ".join(failures) if failures else f"{len(expected)} bound checksums match",
    )


def _mapping_field(parent: Any, key: str, label: str) -> tuple[dict[str, Any], Check]:
    value = parent.get(key) if isinstance(parent, dict) else None
    ok = isinstance(value, dict)
    return (value if ok else {}), Check(label, ok, f"{key}={value!r}")


def _list_field(parent: Any, key: str, label: str) -> tuple[list[Any], Check]:
    value = parent.get(key) if isinstance(parent, dict) else None
    ok = isinstance(value, list)
    return (value if ok else []), Check(label, ok, f"{key}={value!r}")


def _overlap_consistency_check(
    label: str,
    left: dict[str, Any],
    right: dict[str, Any],
    fields: tuple[str, ...],
) -> Check:
    mismatches: dict[str, tuple[Any, Any]] = {}
    missing: list[str] = []
    for field in fields:
        if field not in left or field not in right:
            missing.append(field)
        elif left.get(field) != right.get(field):
            mismatches[field] = (left.get(field), right.get(field))
    return Check(
        label,
        not missing and not mismatches,
        f"missing={missing}, mismatches={mismatches}",
    )


def _exactly_one(value: Any) -> bool:
    return type(value) is int and value == 1


def _counter_checks(run_record: dict[str, Any], final_metadata: dict[str, Any]) -> list[Check]:
    checks: list[Check] = []
    for source_name, source in (("run_record", run_record), ("final_metadata", final_metadata)):
        for field in ("test_evaluator_call_count", "test_target_read_count"):
            value = source.get(field)
            checks.append(Check(
                f"task7.{source_name}.{field}",
                _exactly_one(value),
                f"expected exact integer 1, found {value!r} ({type(value).__name__})",
            ))
    checks.append(Check(
        "task7.operation_counters_cross_record",
        all(run_record.get(field) == final_metadata.get(field) for field in (
            "test_evaluator_call_count", "test_target_read_count"
        )),
        "run-record and final-metadata counters must agree",
    ))
    return checks


def _git_commit_exists(repo: Path, recorded_sha: Any) -> tuple[bool, str]:
    if not isinstance(recorded_sha, str) or not COMMIT_RE.fullmatch(recorded_sha):
        return False, f"invalid full commit id: {recorded_sha!r}"
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"{recorded_sha}^{{commit}}"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0, (result.stdout.strip() or result.stderr.strip())


def _git_file_bytes(repo: Path, commit: str, path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def _execution_commit_checks(
    repo: Path,
    decision: dict[str, Any],
    run_record: dict[str, Any],
    final_metadata: dict[str, Any],
    logged: dict[str, Any] | None,
) -> list[Check]:
    checks: list[Check] = []
    recorded = run_record.get("code_commit")
    exists, detail = _git_commit_exists(repo, recorded)
    checks.append(Check("task7.execution_commit_exists", exists, detail))

    metadata_commit = (final_metadata.get("build") or {}).get("code_commit")
    logged_commit = logged.get("code_commit") if isinstance(logged, dict) else None
    lock_commit = (decision.get("build") or {}).get("code_commit")
    identities = {
        "run_record": recorded,
        "run_log": logged_commit,
        "final_metadata.build": metadata_commit,
        "decision.build": lock_commit,
    }
    identity_ok = all(isinstance(v, str) and v == recorded for v in identities.values())
    checks.append(Check(
        "task7.execution_commit_identity",
        identity_ok,
        f"identities={identities}",
    ))

    reference_exists, reference_detail = _git_commit_exists(repo, AUDITED_EXECUTION_REFERENCE_COMMIT)
    if not exists or not reference_exists:
        checks.append(Check(
            "task7.execution_instrumentation_audited",
            False,
            f"execution_exists={exists}; audited_reference_exists={reference_exists}; {reference_detail}",
        ))
        return checks

    mismatches: list[str] = []
    for path in AUDITED_EXECUTION_PATHS:
        actual = _git_file_bytes(repo, recorded, path)
        audited = _git_file_bytes(repo, AUDITED_EXECUTION_REFERENCE_COMMIT, path)
        if actual is None or audited is None:
            mismatches.append(f"missing source at {path}")
        elif hashlib.sha256(actual).hexdigest() != hashlib.sha256(audited).hexdigest():
            mismatches.append(f"{path} differs from audited instrumentation")
    checks.append(Check(
        "task7.execution_instrumentation_audited",
        not mismatches,
        "; ".join(mismatches) if mismatches else (
            f"recorded commit matches audited source contract from {AUDITED_EXECUTION_REFERENCE_COMMIT}"
        ),
    ))
    return checks


def _parse_boolean_series(series: pd.Series) -> tuple[pd.Series, list[str]]:
    parsed: list[bool | None] = []
    failures: list[str] = []
    for index, value in series.items():
        if isinstance(value, (bool, np.bool_)):
            parsed.append(bool(value))
        elif isinstance(value, str) and value.strip().lower() in {"true", "false"}:
            parsed.append(value.strip().lower() == "true")
        elif pd.isna(value):
            parsed.append(None)
        else:
            failures.append(f"row {index}: invalid boolean {value!r}")
            parsed.append(None)
    return pd.Series(parsed, index=series.index, dtype="object"), failures


def _parse_numeric_series(series: pd.Series) -> tuple[pd.Series, list[str]]:
    values: list[float] = []
    failures: list[str] = []
    for index, value in series.items():
        if isinstance(value, (bool, np.bool_)):
            failures.append(f"row {index}: boolean is not numeric")
            values.append(np.nan)
            continue
        if pd.isna(value) or (isinstance(value, str) and not value.strip()):
            values.append(np.nan)
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            failures.append(f"row {index}: nonnumeric token {value!r}")
            values.append(np.nan)
            continue
        if not np.isfinite(number):
            failures.append(f"row {index}: non-finite value {value!r}")
        values.append(number)
    return pd.Series(values, index=series.index, dtype="float64"), failures


def _schema_check(frame: pd.DataFrame, expected: tuple[str, ...], label: str) -> Check:
    actual = tuple(frame.columns)
    missing = [name for name in expected if name not in frame.columns]
    extra = [name for name in frame.columns if name not in expected]
    return Check(label, not missing and not extra, f"missing={missing}, unexpected={extra}, columns={actual}")


def _validate_semantics(frame: pd.DataFrame, label: str, *, allow_empty_rows: bool = False) -> list[Check]:
    checks: list[Check] = []
    if not {"cpu_result_semantics", "primary_resource", "any_resource_metric_reported", "row_count"}.issubset(frame.columns):
        return [Check(f"{label}.semantics", False, "missing semantic columns")]
    bools, bool_failures = _parse_boolean_series(frame["any_resource_metric_reported"])
    bad: list[str] = list(bool_failures)
    for index, row in frame.iterrows():
        row_count, row_fail = _parse_numeric_series(pd.Series([row["row_count"]], index=[index]))
        if row_fail or pd.isna(row_count.iloc[0]):
            bad.append(f"row {index}: invalid row_count")
            continue
        empty = row_count.iloc[0] == 0
        cpu = row["cpu_result_semantics"]
        primary = row["primary_resource"]
        any_resource = bools.loc[index]
        if allow_empty_rows and empty:
            if not (pd.isna(cpu) and pd.isna(primary) and any_resource is None):
                bad.append(f"row {index}: empty subset must have null semantics")
        else:
            if cpu != "average_usage" or primary != "memory" or any_resource is not False:
                bad.append(
                    f"row {index}: semantics cpu={cpu!r}, primary={primary!r}, any_resource={any_resource!r}"
                )
    checks.append(Check(f"{label}.semantics", not bad, "; ".join(bad) if bad else "semantics valid"))
    return checks


def _validate_occurrence_numeric_rows(frame: pd.DataFrame, label: str, final_population: int | None = None) -> list[Check]:
    checks: list[Check] = []
    count_columns = (
        "row_count", "valid_cpu_violation_count", "valid_memory_violation_count",
        "valid_cpu_utilization_count", "valid_memory_utilization_count",
    )
    metric_columns = (
        "cpu_violation_pct", "memory_violation_pct", "average_cpu_utilization",
        "average_memory_utilization", "average_cpu_waste", "average_memory_waste",
        "average_cpu_shortfall", "average_memory_shortfall",
    )
    parsed: dict[str, pd.Series] = {}
    parse_failures: list[str] = []
    for column in count_columns + metric_columns:
        if column not in frame:
            parse_failures.append(f"missing {column}")
            continue
        parsed[column], failures = _parse_numeric_series(frame[column])
        parse_failures.extend(f"{column}: {failure}" for failure in failures)
    checks.append(Check(f"{label}.numeric_parse", not parse_failures, "; ".join(parse_failures) if parse_failures else "numeric columns parse"))
    if parse_failures:
        return checks

    relationship_failures: list[str] = []
    metric_failures: list[str] = []
    for index in frame.index:
        row_count = parsed["row_count"].loc[index]
        if pd.isna(row_count) or row_count < 0 or not float(row_count).is_integer():
            relationship_failures.append(f"row {index}: invalid row_count={row_count}")
            continue
        if final_population is not None and int(row_count) != int(final_population):
            relationship_failures.append(f"row {index}: row_count={row_count} != final_population={final_population}")
        for resource in ("cpu", "memory"):
            vio = parsed[f"valid_{resource}_violation_count"].loc[index]
            util = parsed[f"valid_{resource}_utilization_count"].loc[index]
            for name, value in (("violation", vio), ("utilization", util)):
                if pd.isna(value) or value < 0 or value > row_count or not float(value).is_integer():
                    relationship_failures.append(f"row {index}: invalid {resource} {name} denominator={value}")
            if not pd.isna(vio) and not pd.isna(util) and util > vio:
                relationship_failures.append(f"row {index}: {resource} utilization denominator exceeds violation denominator")

            violation = parsed[f"{resource}_violation_pct"].loc[index]
            utilization = parsed[f"average_{resource}_utilization"].loc[index]
            waste = parsed[f"average_{resource}_waste"].loc[index]
            shortfall = parsed[f"average_{resource}_shortfall"].loc[index]
            if vio == 0:
                if not (pd.isna(violation) and pd.isna(waste) and pd.isna(shortfall)):
                    metric_failures.append(f"row {index}: {resource} violation/waste/shortfall must be null when denominator=0")
            else:
                if pd.isna(violation) or not 0 <= violation <= 100:
                    metric_failures.append(f"row {index}: invalid {resource}_violation_pct={violation}")
                for name, value in (("waste", waste), ("shortfall", shortfall)):
                    if pd.isna(value) or value < 0:
                        metric_failures.append(f"row {index}: invalid {resource} {name}={value}")
            if util == 0:
                if not pd.isna(utilization):
                    metric_failures.append(f"row {index}: {resource} utilization must be null when denominator=0")
            elif pd.isna(utilization) or not 0 <= utilization <= 1:
                metric_failures.append(f"row {index}: invalid {resource} utilization={utilization}")
    checks.append(Check(f"{label}.denominator_relationships", not relationship_failures, "; ".join(relationship_failures) if relationship_failures else "count relationships valid"))
    checks.append(Check(f"{label}.metric_contract", not metric_failures, "; ".join(metric_failures) if metric_failures else "metric ranges/nullability valid"))
    return checks


def _validate_policy_comparison(frame: pd.DataFrame, final_population: int | None = None) -> list[Check]:
    checks = [_schema_check(frame, COMPARISON_COLUMNS, "task7_pr2.comparison.schema")]
    policies = tuple(frame["policy"].tolist()) if "policy" in frame else ()
    checks.append(Check("task7_pr2.seven_policies", policies == FINAL_POLICIES, f"policies={policies}"))
    checks.extend(_validate_semantics(frame, "task7_pr2.comparison"))
    checks.extend(_validate_occurrence_numeric_rows(frame, "task7_pr2.comparison", final_population))
    return checks


def _null_aware_equal(left: Any, right: Any, tolerance: float = 1e-12) -> bool:
    if pd.isna(left) and pd.isna(right):
        return True
    try:
        return bool(np.isclose(float(left), float(right), rtol=1e-9, atol=tolerance, equal_nan=True))
    except (TypeError, ValueError):
        return left == right


def _validate_sensitivity(frame: pd.DataFrame, comparison: pd.DataFrame | None = None) -> list[Check]:
    checks: list[Check] = [_schema_check(frame, SENSITIVITY_COLUMNS, "task7_pr2.sensitivity.schema")]
    if not {"sensitivity", "policy"}.issubset(frame.columns):
        checks.append(Check("task7_pr2.sensitivity.cartesian_product", False, "missing sensitivity/policy columns"))
        return checks

    expected_pairs = {(scenario, policy) for scenario in SENSITIVITY_SCENARIOS for policy in FINAL_POLICIES}
    actual_pairs = list(zip(frame["sensitivity"].tolist(), frame["policy"].tolist()))
    pair_set = set(actual_pairs)
    checks.append(Check(
        "task7_pr2.sensitivity.cartesian_product",
        len(frame) == 35 and len(pair_set) == 35 and pair_set == expected_pairs,
        f"rows={len(frame)}, unique_pairs={len(pair_set)}, missing={sorted(expected_pairs-pair_set)}, unexpected={sorted(pair_set-expected_pairs)}",
    ))

    checks.extend(_validate_semantics(frame, "task7_pr2.sensitivity", allow_empty_rows=True))
    numeric_failures: list[str] = []
    for index, row in frame.iterrows():
        row_count_series, row_fail = _parse_numeric_series(pd.Series([row.get("row_count")], index=[index]))
        if row_fail or pd.isna(row_count_series.iloc[0]) or row_count_series.iloc[0] < 0 or not float(row_count_series.iloc[0]).is_integer():
            numeric_failures.append(f"row {index}: invalid row_count={row.get('row_count')!r}")
            continue
        row_count = int(row_count_series.iloc[0])
        scenario = row["sensitivity"]
        count_cols = [
            "valid_cpu_violation_count", "valid_memory_violation_count",
            "valid_cpu_utilization_count", "valid_memory_utilization_count",
        ]
        metric_cols = [
            "cpu_violation_pct", "memory_violation_pct", "average_cpu_utilization",
            "average_memory_utilization", "average_cpu_waste", "average_memory_waste",
            "average_cpu_shortfall", "average_memory_shortfall",
        ]
        if row_count == 0:
            nullable = count_cols + metric_cols + ["n_groups", "cpu_result_semantics", "primary_resource", "any_resource_metric_reported"]
            if any(not pd.isna(row.get(column)) for column in nullable):
                numeric_failures.append(f"row {index}: empty sensitivity row contains nonnull scientific/semantic values")
            continue
        if scenario == "group_weighted":
            if any(not pd.isna(row.get(column)) for column in count_cols):
                numeric_failures.append(f"row {index}: group_weighted count columns must be null")
            n_groups, failures = _parse_numeric_series(pd.Series([row.get("n_groups")], index=[index]))
            value = n_groups.iloc[0]
            if failures or pd.isna(value) or value <= 0 or value > row_count or not float(value).is_integer():
                numeric_failures.append(f"row {index}: invalid n_groups={row.get('n_groups')!r}")
            for column in metric_cols:
                parsed, failures = _parse_numeric_series(pd.Series([row.get(column)], index=[index]))
                value = parsed.iloc[0]
                if failures or pd.isna(value):
                    numeric_failures.append(f"row {index}: invalid {column}={row.get(column)!r}")
                elif ("violation_pct" in column and not 0 <= value <= 100) or ("utilization" in column and not 0 <= value <= 1) or (("waste" in column or "shortfall" in column) and value < 0):
                    numeric_failures.append(f"row {index}: out-of-range {column}={value}")
        else:
            if not pd.isna(row.get("n_groups")):
                numeric_failures.append(f"row {index}: n_groups must be null outside group_weighted")
            one = pd.DataFrame([row[list(COMPARISON_COLUMNS)]])
            for check in _validate_occurrence_numeric_rows(one, "row"):
                if not check.ok:
                    numeric_failures.append(f"row {index}: {check.detail}")
    checks.append(Check(
        "task7_pr2.sensitivity.numeric_contract",
        not numeric_failures,
        "; ".join(numeric_failures) if numeric_failures else "producer-compatible sensitivity numeric/null contract valid",
    ))

    cross_failures: list[str] = []
    denominator_partition_failures: list[str] = []
    population_consistency_failures: list[str] = []

    # The producer applies each sensitivity population mask before evaluating any
    # policy, so membership cannot vary by policy. Require a single row_count per
    # scenario. Group-weighted aggregation uses the same recurrence population for
    # every policy, so n_groups must likewise be policy-independent.
    for scenario in SENSITIVITY_SCENARIOS:
        scenario_rows = frame[frame["sensitivity"] == scenario]
        parsed_counts, count_failures = _parse_numeric_series(scenario_rows["row_count"])
        if count_failures or parsed_counts.isna().any():
            population_consistency_failures.append(
                f"{scenario}: row_count cannot be compared across policies"
            )
        else:
            unique_counts = sorted({int(value) for value in parsed_counts.tolist()})
            if len(unique_counts) != 1:
                population_consistency_failures.append(
                    f"{scenario}: row_count differs across policies: {unique_counts}"
                )

    group_rows = frame[frame["sensitivity"] == "group_weighted"]
    nonempty_group_rows = group_rows[group_rows["row_count"].fillna(0) != 0]
    if not nonempty_group_rows.empty:
        parsed_groups, group_failures = _parse_numeric_series(nonempty_group_rows["n_groups"])
        if group_failures or parsed_groups.isna().any():
            population_consistency_failures.append(
                "group_weighted: n_groups cannot be compared across policies"
            )
        else:
            unique_groups = sorted({int(value) for value in parsed_groups.tolist()})
            if len(unique_groups) != 1:
                population_consistency_failures.append(
                    f"group_weighted: n_groups differs across policies: {unique_groups}"
                )

    if comparison is not None and set(COMPARISON_COLUMNS).issubset(comparison.columns):
        comp_by_policy = comparison.set_index("policy")
        occ = frame[frame["sensitivity"] == "occurrence_weighted"].set_index("policy")
        for policy in FINAL_POLICIES:
            if policy not in comp_by_policy.index or policy not in occ.index:
                cross_failures.append(f"missing comparison/occurrence row for {policy}")
                continue
            for column in COMPARISON_COLUMNS:
                if column == "policy":
                    continue
                if not _null_aware_equal(comp_by_policy.loc[policy, column], occ.loc[policy, column]):
                    cross_failures.append(f"{policy}: occurrence_weighted {column} differs from comparison")

        partition_columns = (
            "valid_cpu_violation_count",
            "valid_memory_violation_count",
            "valid_cpu_utilization_count",
            "valid_memory_utilization_count",
        )
        for policy in FINAL_POLICIES:
            rows = frame[frame["policy"] == policy].set_index("sensitivity")
            if set(SENSITIVITY_SCENARIOS).issubset(rows.index):
                occurrence = rows.loc["occurrence_weighted", "row_count"]
                excluded = rows.loc["same_second_excluded", "row_count"]
                only = rows.loc["same_second_only", "row_count"]
                multi = rows.loc["multi_instance", "row_count"]
                group = rows.loc["group_weighted", "row_count"]
                if excluded + only != occurrence:
                    cross_failures.append(f"{policy}: same-second row counts do not partition occurrence rows")
                if multi > occurrence:
                    cross_failures.append(f"{policy}: multi_instance exceeds occurrence rows")
                if group != occurrence:
                    cross_failures.append(f"{policy}: group_weighted row_count differs from occurrence")

                # same_second_excluded and same_second_only are complementary
                # subsets of occurrence_weighted. Their valid-count denominators
                # must therefore partition the corresponding occurrence count.
                # Producer-compatible empty subsets store null scientific cells;
                # those null count cells contribute zero to the partition.
                for column in partition_columns:
                    occurrence_value = rows.loc["occurrence_weighted", column]
                    excluded_value = rows.loc["same_second_excluded", column]
                    only_value = rows.loc["same_second_only", column]

                    def _partition_value(value: Any) -> float | None:
                        if pd.isna(value):
                            return 0.0
                        parsed, failures = _parse_numeric_series(pd.Series([value]))
                        if failures or pd.isna(parsed.iloc[0]):
                            return None
                        return float(parsed.iloc[0])

                    occurrence_number = _partition_value(occurrence_value)
                    excluded_number = _partition_value(excluded_value)
                    only_number = _partition_value(only_value)
                    if None in (occurrence_number, excluded_number, only_number):
                        denominator_partition_failures.append(
                            f"{policy}: {column} partition contains an unparsable value"
                        )
                    elif excluded_number + only_number != occurrence_number:
                        denominator_partition_failures.append(
                            f"{policy}: {column} does not partition occurrence "
                            f"({excluded_number:g} + {only_number:g} != {occurrence_number:g})"
                        )

    checks.append(Check(
        "task7_pr2.sensitivity.denominator_partition",
        not denominator_partition_failures,
        "; ".join(denominator_partition_failures)
        if denominator_partition_failures
        else "same-second valid-count denominators partition occurrence counts",
    ))
    checks.append(Check(
        "task7_pr2.sensitivity.population_consistency",
        not population_consistency_failures,
        "; ".join(population_consistency_failures)
        if population_consistency_failures
        else "scenario populations and group counts are policy-independent",
    ))
    checks.append(Check(
        "task7_pr2.sensitivity.cross_table_relationships",
        not cross_failures,
        "; ".join(cross_failures) if cross_failures else ("cross-table relationships valid" if comparison is not None else "comparison not supplied; no cross-table comparison performed"),
    ))
    return checks


def _prediction_schema_checks(path: Path) -> list[Check]:
    required = {
        "role_key", "recurrence_key", "recommended_cpu_unit",
        "recommended_memory_unit", "recommended_resource_scope",
    }
    try:
        columns = set(pq.ParquetFile(path).schema_arrow.names)
    except Exception as exc:
        return [Check("task7.prediction_columns", False, f"cannot inspect parquet schema: {exc}")]
    missing = sorted(required - columns)
    checks = [Check("task7.prediction_columns", not missing, f"missing={missing}")]
    if missing:
        return checks
    inspect_columns = ["recommended_cpu_unit", "recommended_memory_unit", "recommended_resource_scope"]
    try:
        pred_meta = pd.read_parquet(path, columns=inspect_columns)
        units_ok = (
            set(pred_meta["recommended_cpu_unit"].dropna()) == {"percent_of_vcpu"}
            and set(pred_meta["recommended_memory_unit"].dropna()) == {"gb"}
            and set(pred_meta["recommended_resource_scope"].dropna()) == {"task_role_per_instance"}
        )
    except Exception as exc:
        checks.append(Check("task7.prediction_units_scope", False, f"metadata-column read failed: {exc}"))
    else:
        checks.append(Check("task7.prediction_units_scope", units_ok, "expected CPU=percent_of_vcpu, memory=gb, scope=task_role_per_instance"))
    return checks


def _published_evidence_checks(
    canonical_dir: Path,
    ml_dir: Path,
    final_dir: Path,
    report_root: Path | None = None,
) -> list[Check]:
    root = (report_root or REPORT_ROOT).resolve()
    checks: list[Check] = []
    for label, source_dir, report_dir, required in (
        ("task3.published_evidence", canonical_dir, root / "canonical", PUBLISHED_CANONICAL_REQUIRED_FILES),
        ("task7_pr1.published_evidence", ml_dir, root / "ml", PUBLISHED_ML_REQUIRED_FILES),
        ("task7_pr2.published_evidence", final_dir, root / "final_test", PUBLISHED_FINAL_REQUIRED_FILES),
    ):
        failures: list[str] = []
        for name in sorted(required):
            report_path = report_dir / name
            source_path = source_dir / name
            if not report_path.is_file():
                failures.append(f"missing published {name}")
                continue
            if not source_path.is_file():
                failures.append(f"missing authoritative {name}")
                continue
            if sha256(report_path) != sha256(source_path):
                failures.append(f"published {name} differs from authoritative artifact")
        checks.append(Check(label, not failures, "; ".join(failures) if failures else f"{len(required)} published files match"))
    return checks


def _model_artifact_bindings(
    decision: dict[str, Any],
    ml_dir: Path,
    ml_manifest: dict[str, str],
    run_record: dict[str, Any],
) -> list[Check]:
    checks: list[Check] = []
    artifacts, field_check = _mapping_field(decision, "model_artifacts", "task7_pr1.model_artifacts_present")
    checks.append(field_check)
    selected, selected_check = _mapping_field(decision, "selected_models", "task7_pr1.selected_models_present")
    checks.append(selected_check)
    run_checksums = run_record.get("pr1_checksums") if isinstance(run_record.get("pr1_checksums"), dict) else {}
    for resource, expected_filename in (("cpu", "cpu_model.joblib"), ("memory", "memory_model.joblib")):
        info = artifacts.get(resource)
        ok_info = isinstance(info, dict)
        checks.append(Check(f"task7_pr1.{resource}_model_artifact_present", ok_info, f"artifact={info!r}"))
        if not ok_info:
            continue
        filename = info.get("file")
        digest = info.get("sha256")
        failures: list[str] = []
        if filename != expected_filename:
            failures.append(f"filename={filename!r}, expected={expected_filename!r}")
        if not _valid_sha256(digest):
            failures.append(f"invalid sha256={digest!r}")
        if ml_manifest.get(expected_filename) != digest:
            failures.append(f"PR1 SHA256SUMS={ml_manifest.get(expected_filename)!r}")
        if run_checksums.get(expected_filename) != digest:
            failures.append(f"run_record.pr1_checksums={run_checksums.get(expected_filename)!r}")
        path = ml_dir / expected_filename
        if path.is_file() and _valid_sha256(digest) and sha256(path) != digest:
            failures.append("physical model hash differs")
        checks.append(Check(f"task7_pr1.{resource}_model_hash_binding", not failures, "; ".join(failures) if failures else "decision/stage/run/physical model hash binding valid"))
        selected_value = selected.get(resource)
        checks.append(Check(
            f"task7_pr1.{resource}_selected_model",
            isinstance(selected_value, str) and bool(selected_value),
            f"selected_model={selected_value!r}",
        ))
    return checks


def _decision_provenance_checks(
    decision: dict[str, Any],
    targets_dir: Path,
    baselines_dir: Path,
    ml_dir: Path,
    stage_manifests: dict[str, dict[str, str]],
    run_record: dict[str, Any],
    baseline_selection: dict[str, Any],
    model_selection: dict[str, Any],
) -> list[Check]:
    checks: list[Check] = []
    task4, c = _mapping_field(decision, "task4_inputs", "task7_pr1.task4_inputs_present"); checks.append(c)
    task4_hashes, c = _mapping_field(task4, "targets_manifest", "task7_pr1.task4_targets_manifest_present"); checks.append(c)
    checks.append(_checksum_binding_check(
        "task7_pr1.task4_checksum_binding", targets_dir, task4_hashes,
        required_names=TASK4_REQUIRED_FILES,
        recorded=stage_manifests.get("task4_targets", {}), exact_names=True,
    ))
    checks.append(Check(
        "task7.task4_test_checksum_binding",
        _valid_sha256(task4_hashes.get("test.parquet")) and run_record.get("task4_test_sha256") == task4_hashes.get("test.parquet"),
        f"decision={task4_hashes.get('test.parquet')!r}, run_record={run_record.get('task4_test_sha256')!r}",
    ))

    task6, c = _mapping_field(decision, "task6_selection", "task7_pr1.task6_selection_present"); checks.append(c)
    task6_hashes, c = _mapping_field(task6, "baselines_manifest", "task7_pr1.task6_baselines_manifest_present"); checks.append(c)
    checks.append(_checksum_binding_check(
        "task7_pr1.task6_checksum_binding", baselines_dir, task6_hashes,
        required_names=TASK6_REQUIRED_FILES,
        recorded=stage_manifests.get("task6_baselines", {}), exact_names=True,
    ))
    run_task6 = run_record.get("task6_checksums") if isinstance(run_record.get("task6_checksums"), dict) else {}
    checks.append(Check(
        "task7.task6_run_record_binding",
        task6_hashes == run_task6,
        f"decision={task6_hashes!r}, run_record={run_task6!r}",
    ))
    baseline_sha = task6.get("baseline_selection_sha256")
    checks.append(Check(
        "task7_pr1.baseline_selection_hash_binding",
        _valid_sha256(baseline_sha)
        and task6_hashes.get("baseline_selection.json") == baseline_sha
        and (baselines_dir / "baseline_selection.json").is_file()
        and sha256(baselines_dir / "baseline_selection.json") == baseline_sha,
        f"decision={baseline_sha!r}, manifest={task6_hashes.get('baseline_selection.json')!r}",
    ))
    decision_policy = task6.get("selected_policy")
    decision_min_runs = task6.get("selected_min_runs")
    checks.append(Check(
        "task7_pr1.baseline_selection_semantics",
        baseline_selection.get("selected_policy") == decision_policy == run_record.get("selected_baseline_policy")
        and baseline_selection.get("selected_min_runs") == decision_min_runs == run_record.get("selected_min_runs"),
        f"physical=({baseline_selection.get('selected_policy')!r},{baseline_selection.get('selected_min_runs')!r}), decision=({decision_policy!r},{decision_min_runs!r}), run=({run_record.get('selected_baseline_policy')!r},{run_record.get('selected_min_runs')!r})",
    ))

    checks.extend(_model_artifact_bindings(decision, ml_dir, stage_manifests.get("task7_pr1_ml", {}), run_record))
    selected = decision.get("selected_models") if isinstance(decision.get("selected_models"), dict) else {}
    for resource in ("cpu", "memory"):
        resource_selection = model_selection.get(resource) if isinstance(model_selection.get(resource), dict) else None
        selected_model = resource_selection.get("selected_model") if resource_selection else None
        checks.append(Check(
            f"task7_pr1.model_selection_{resource}_matches_lock",
            isinstance(resource_selection, dict)
            and selected_model == selected.get(resource)
            and run_record.get("selected_models", {}).get(resource) == selected.get(resource),
            f"decision={selected.get(resource)!r}, model_selection={selected_model!r}, run={run_record.get('selected_models', {}).get(resource)!r}",
        ))

    feature_order, c = _list_field(decision, "feature_order", "task7_pr1.feature_order_present"); checks.append(c)
    feature_path = ml_dir / "feature_order.json"
    feature_payload = load_json(feature_path) if feature_path.is_file() else None
    actual_order = feature_payload.get("feature_order") if isinstance(feature_payload, dict) else feature_payload
    if actual_order is None and isinstance(feature_payload, dict):
        actual_order = feature_payload.get("features")
    checks.append(Check(
        "task7_pr1.feature_order_matches_lock",
        bool(feature_order) and actual_order == feature_order,
        f"decision={feature_order!r}, artifact={actual_order!r}",
    ))
    feature_digest = sha256(feature_path) if feature_path.is_file() else None
    checks.append(Check(
        "task7_pr1.feature_order_hash_binding",
        feature_digest is not None
        and stage_manifests.get("task7_pr1_ml", {}).get("feature_order.json") == feature_digest
        and run_record.get("pr1_checksums", {}).get("feature_order.json") == feature_digest,
        f"physical={feature_digest!r}, stage={stage_manifests.get('task7_pr1_ml', {}).get('feature_order.json')!r}, run={run_record.get('pr1_checksums', {}).get('feature_order.json')!r}",
    ))
    return checks


def _matching_log_entry(run_log_path: Path, decision_sha: str | None, run_id: Any) -> dict[str, Any] | None:
    if not decision_sha:
        return None
    try:
        matches = _load_run_log(run_log_path, decision_sha)
    except VerificationError:
        return None
    selected = [entry for entry in matches if entry.get("run_id") == run_id]
    return selected[0] if len(selected) == 1 else None


def verify_pipeline(
    canonical_dir: Path,
    targets_dir: Path,
    baselines_dir: Path,
    ml_dir: Path,
    final_dir: Path,
    *,
    report_root: Path | None = None,
) -> tuple[list[Check], dict[str, Any]]:
    checks: list[Check] = []
    manifest: dict[str, Any] = {"dataset_id": DATASET_ID, "schema_version": SCHEMA_VERSION, "artifacts": []}
    stage_specs = {
        "task3_canonical": (canonical_dir, TASK3_REQUIRED_FILES, False),
        "task4_targets": (targets_dir, TASK4_REQUIRED_FILES, True),
        "task6_baselines": (baselines_dir, TASK6_REQUIRED_FILES, True),
        "task7_pr1_ml": (ml_dir, TASK7_PR1_REQUIRED_FILES, True),
        "task7_pr2_final_test": (final_dir, TASK7_FINAL_REQUIRED_FILES, True),
    }
    stage_manifests: dict[str, dict[str, str]] = {}
    for stage, (directory, required, exact) in stage_specs.items():
        ok, detail, recorded = verify_sha256sums(directory, required_files=required, exact_files=exact)
        checks.append(Check(f"{stage}.sha256", ok, detail))
        stage_manifests[stage] = recorded
        if recorded:
            manifest["artifacts"].extend(_artifact_entries(stage, directory, recorded))

    checks.extend(_published_evidence_checks(canonical_dir, ml_dir, final_dir, report_root))

    loaded_metadata: dict[str, dict[str, Any]] = {}
    for label, path in (
        ("task3", canonical_dir / "metadata.json"), ("task4", targets_dir / "metadata.json"),
        ("task6", baselines_dir / "metadata.json"), ("task7_pr1", ml_dir / "metadata.json"),
        ("task7_pr2", final_dir / "metadata.json"),
    ):
        if not path.exists():
            checks.append(Check(f"{label}.metadata_exists", False, f"missing {path}"))
            continue
        try:
            metadata = load_json(path)
        except Exception as exc:
            checks.append(Check(f"{label}.metadata_parse", False, f"{type(exc).__name__}: {exc}"))
            continue
        loaded_metadata[label] = metadata
        checks.extend(_metadata_contract(metadata, label))

    baseline_selection_path = baselines_dir / "baseline_selection.json"
    try:
        baseline_selection = load_json(baseline_selection_path) if baseline_selection_path.exists() else {}
    except Exception as exc:
        baseline_selection = {}
        checks.append(Check("task6.baseline_selection_parse", False, f"{type(exc).__name__}: {exc}"))

    decision_path = ml_dir / "decision_manifest.json"
    try:
        decision = load_json(decision_path) if decision_path.exists() else {}
    except Exception as exc:
        decision = {}
        checks.append(Check("task7_pr1.decision_manifest_parse", False, f"{type(exc).__name__}: {exc}"))
    decision_sha = sha256(decision_path) if decision_path.is_file() else None
    checks.extend([
        Check("task7_pr1.phase", decision.get("phase") == "pr1_validation_lock", f"phase={decision.get('phase')!r}"),
        Check("task7_pr1.cpu_semantics", decision.get("cpu_result_semantics") == "average_usage", f"cpu_result_semantics={decision.get('cpu_result_semantics')!r}"),
        Check("task7_pr1.primary_resource", decision.get("primary_resource") == "memory", f"primary_resource={decision.get('primary_resource')!r}"),
        Check("task7_pr1.no_any_resource", decision.get("any_resource_metric_reported") is False, f"any_resource_metric_reported={decision.get('any_resource_metric_reported')!r}"),
    ])

    run_record_path = final_dir / "run_record.json"
    try:
        run_record = load_json(run_record_path) if run_record_path.exists() else {}
    except Exception as exc:
        run_record = {}
        checks.append(Check("task7.run_record_parse", False, f"{type(exc).__name__}: {exc}"))
    final_metadata = loaded_metadata.get("task7_pr2", {})
    try:
        model_selection = load_json(ml_dir / "model_selection.json") if (ml_dir / "model_selection.json").is_file() else {}
    except Exception as exc:
        model_selection = {}
        checks.append(Check("task7_pr1.model_selection_parse", False, f"{type(exc).__name__}: {exc}"))

    checks.extend(_decision_provenance_checks(
        decision, targets_dir, baselines_dir, ml_dir, stage_manifests,
        run_record, baseline_selection, model_selection,
    ))
    run_pr1 = run_record.get("pr1_checksums") if isinstance(run_record.get("pr1_checksums"), dict) else {}
    checks.append(Check(
        "task7.pr1_run_record_binding",
        run_pr1 == stage_manifests.get("task7_pr1_ml", {}),
        f"stage={stage_manifests.get('task7_pr1_ml', {})!r}, run_record={run_pr1!r}",
    ))

    final_population = run_record.get("final_population_size")
    if not (type(final_population) is int and final_population >= 0):
        checks.append(Check("task7.final_population_size", False, f"invalid final_population_size={final_population!r}"))
        final_population_for_checks = None
    else:
        checks.append(Check("task7.final_population_size", True, f"final_population_size={final_population}"))
        final_population_for_checks = final_population

    comparison: pd.DataFrame | None = None
    comparison_path = final_dir / "final_test_policy_comparison.csv"
    if comparison_path.exists():
        try:
            comparison = pd.read_csv(comparison_path)
            checks.extend(_validate_policy_comparison(comparison, final_population_for_checks))
        except Exception as exc:
            checks.append(Check("task7_pr2.comparison_parse", False, f"{type(exc).__name__}: {exc}"))
    else:
        checks.append(Check("task7_pr2.comparison_exists", False, f"missing {comparison_path}"))

    sensitivity_path = final_dir / "final_test_sensitivity.csv"
    if sensitivity_path.exists():
        try:
            sensitivity = pd.read_csv(sensitivity_path)
            checks.extend(_validate_sensitivity(sensitivity, comparison))
        except Exception as exc:
            checks.append(Check("task7_pr2.sensitivity_parse", False, f"{type(exc).__name__}: {exc}"))
    else:
        checks.append(Check("task7_pr2.sensitivity_exists", False, f"missing {sensitivity_path}"))

    checks.append(_timestamp_order_check("task7.lock_before_final_test", decision.get("lock_timestamp_utc"), run_record.get("timestamp_utc")))
    checks.append(Check(
        "task7.final_run_traces_manifest",
        bool(decision_sha and run_record.get("decision_manifest_sha256") == decision_sha and final_metadata.get("decision_manifest_sha256") == decision_sha),
        f"computed={decision_sha!r}, run={run_record.get('decision_manifest_sha256')!r}, metadata={final_metadata.get('decision_manifest_sha256')!r}",
    ))
    checks.extend(_counter_checks(run_record, final_metadata))
    run_id = run_record.get("run_id")
    checks.append(Check("task7.final_run_id", isinstance(run_id, str) and bool(run_id.strip()), f"run_id={run_id!r}"))

    run_log_value = run_record.get("run_log")
    run_log_path = (
        REPO_ROOT / run_log_value if isinstance(run_log_value, str) and not Path(run_log_value).is_absolute()
        else Path(run_log_value) if isinstance(run_log_value, str)
        else ml_dir / "final_test_runs.jsonl"
    )
    logged = _matching_log_entry(run_log_path, decision_sha, run_id)
    checks.append(Check(
        "task7.decision_identity_binding",
        bool(
            decision_sha
            and stage_manifests.get("task7_pr1_ml", {}).get("decision_manifest.json") == decision_sha
            and run_pr1.get("decision_manifest.json") == decision_sha
            and run_record.get("decision_manifest_sha256") == decision_sha
            and final_metadata.get("decision_manifest_sha256") == decision_sha
            and isinstance(logged, dict)
            and logged.get("decision_manifest_sha256") == decision_sha
        ),
        (
            f"computed={decision_sha!r}, stage={stage_manifests.get('task7_pr1_ml', {}).get('decision_manifest.json')!r}, "
            f"run_pr1={run_pr1.get('decision_manifest.json')!r}, run={run_record.get('decision_manifest_sha256')!r}, "
            f"metadata={final_metadata.get('decision_manifest_sha256')!r}, log={(logged or {}).get('decision_manifest_sha256')!r}"
        ),
    ))
    checks.extend(_execution_commit_checks(REPO_ROOT, decision, run_record, final_metadata, logged))
    if decision_sha:
        checks.extend(_check_run_history(
            run_record=run_record, decision=decision, decision_sha=decision_sha,
            run_log_path=run_log_path, final_dir=final_dir,
        ))

    # Compare only fields the final-test producer actually records in both
    # post-execution records. Selection provenance is validated separately via
    # decision -> Task 6/model-selection -> run-record bindings; final metadata
    # intentionally does not duplicate those selections.
    required_final_fields = (
        "dataset_id", "schema_version", "phase", "run_id", "decision_manifest_sha256",
        "final_population_size", "test_evaluator_call_count", "test_target_read_count",
    )
    metadata_failures: list[str] = []
    for field in required_final_fields:
        if field not in final_metadata or field not in run_record:
            metadata_failures.append(f"missing {field}")
        elif final_metadata.get(field) != run_record.get(field):
            metadata_failures.append(f"{field}: metadata={final_metadata.get(field)!r}, run={run_record.get(field)!r}")
    checks.append(Check("task7.final_metadata_matches_run_record", not metadata_failures, "; ".join(metadata_failures) if metadata_failures else "required final metadata fields match"))

    pred_path = final_dir / "final_test_predictions.parquet"
    if pred_path.exists():
        checks.extend(_prediction_schema_checks(pred_path))
    else:
        checks.append(Check("task7.predictions_exists", False, f"missing {pred_path}"))

    manifest["verification_timestamp_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    manifest["decision_manifest_sha256"] = decision_sha
    manifest["final_run_identity"] = {
        "run_id": run_record.get("run_id") if run_record else None,
        "timestamp_utc": run_record.get("timestamp_utc") if run_record else None,
        "code_commit": run_record.get("code_commit") if run_record else None,
        "decision_manifest_sha256": run_record.get("decision_manifest_sha256") if run_record else None,
    }
    manifest["unverified_items"] = UNVERIFIED_ITEMS
    manifest["checks"] = [asdict(c) for c in checks]
    manifest["verified"] = all(c.ok for c in checks)
    manifest["status"] = "PASS" if manifest["verified"] else "FAIL"
    return checks, manifest


def render_report(checks: list[Check], manifest: dict[str, Any]) -> str:
    passed = sum(1 for c in checks if c.ok)
    failed = len(checks) - passed
    status = manifest.get("status") or ("PASS" if failed == 0 else "FAIL")
    lines = [
        "# Alibaba GPU 2020 Verification Report", "",
        f"- Dataset: `{DATASET_ID}`", f"- Schema: `{SCHEMA_VERSION}`",
        f"- Result: **{status}**", f"- Checks: {passed} passed, {failed} failed",
        f"- Generated: `{manifest.get('verification_timestamp_utc')}`",
        f"- Generation ID: `{manifest.get('generation_id')}`",
        f"- Decision manifest SHA-256: `{manifest.get('decision_manifest_sha256')}`",
        f"- Final run ID: `{(manifest.get('final_run_identity') or {}).get('run_id')}`",
        f"- Final run code commit: `{(manifest.get('final_run_identity') or {}).get('code_commit')}`",
        "", "## Verification checks", "", "| Check | Result | Detail |", "|---|---|---|",
    ]
    for check in checks:
        detail = check.detail.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{check.name}` | {'PASS' if check.ok else 'FAIL'} | {detail} |")
    if manifest.get("error"):
        lines += ["", "## Verification error", "", f"`{manifest['error']}`"]
    lines += ["", "## Explicit verification limitations", ""]
    for item in manifest.get("unverified_items", []):
        lines.append(f"- **UNVERIFIED:** {item['item']} — {item['reason']}")
    lines += [
        "", "## Interpretation", "",
        "This report is verification-only. A failed check must be returned to the task that owns the artifact; Task 8 does not repair earlier pipeline behavior.",
        "", "The verifier does not rerun or retune the final test.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def reproduction_metadata(repo: Path) -> dict[str, Any]:
    commit, dirty = git_state(repo)
    return {
        "dataset_id": DATASET_ID, "schema_version": SCHEMA_VERSION,
        "python_version": platform.python_version(), "pandas_version": pd.__version__,
        "code_commit": commit, "code_dirty": dirty,
        "verification_command": "python scripts/verify_alibaba_gpu_2020_artifacts.py",
        "full_test_command": "python -m pytest -q",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def _json_payload(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"


def _paths_overlap(left: Path, right: Path) -> bool:
    left = left.resolve(); right = right.resolve()
    return left == right or left in right.parents or right in left.parents


def _output_path_check(out_dir: Path, inputs: tuple[Path, ...]) -> Check:
    overlaps = [str(path) for path in inputs if _paths_overlap(out_dir, path)]
    published_frozen = (
        REPORT_ROOT / "canonical", REPORT_ROOT / "ml", REPORT_ROOT / "final_test",
    )
    overlaps.extend(str(path) for path in published_frozen if _paths_overlap(out_dir, path))
    return Check("verification.output_directory_isolated", not overlaps, f"overlaps={overlaps}")


def _attempt_manifest(generation_id: str, status: str, *, error: str | None = None) -> dict[str, Any]:
    return {
        "dataset_id": DATASET_ID,
        "schema_version": SCHEMA_VERSION,
        "generation_id": generation_id,
        "status": status,
        "verified": False,
        "verification_timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "decision_manifest_sha256": None,
        "final_run_identity": {},
        "unverified_items": UNVERIFIED_ITEMS,
        "checks": [],
        "error": error,
        "artifacts": [],
    }


def run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir).resolve()
    input_dirs = tuple(Path(value).resolve() for value in (
        args.canonical_dir, args.targets_dir, args.baselines_dir, args.ml_dir, args.final_dir,
    ))
    path_check = _output_path_check(out_dir, input_dirs)
    if not path_check.ok:
        print(f"REFUSED: unsafe output directory: {path_check.detail}")
        return EXIT_REFUSED
    if out_dir.exists() and any(out_dir.iterdir()) and not args.force:
        print(f"REFUSED: {out_dir} exists and is non-empty; use --force")
        return EXIT_REFUSED

    repro_metadata = reproduction_metadata(REPO_ROOT)
    generation_id = uuid.uuid4().hex
    running = _attempt_manifest(generation_id, "RUNNING")
    running["checks"] = [asdict(path_check)]
    try:
        _atomic_write(out_dir / "artifact_manifest.json", _json_payload(running))
        _atomic_write(
            out_dir / "verification_report.md",
            f"# Alibaba GPU 2020 Verification Report\n\n- Result: **RUNNING**\n- Generation ID: `{generation_id}`\n",
        )
    except Exception as exc:
        print(f"VERIFY WRITE FAILED: {type(exc).__name__}: {exc}")
        return EXIT_WRITE_FAILED

    try:
        checks, manifest = verify_pipeline(*input_dirs, report_root=REPORT_ROOT)
        checks.insert(0, path_check)
        manifest["checks"] = [asdict(c) for c in checks]
        manifest["verified"] = all(c.ok for c in checks)
        manifest["status"] = "PASS" if manifest["verified"] else "FAIL"
        manifest["generation_id"] = generation_id
        manifest["error"] = None
    except Exception as exc:
        failure = Check("verification.exception", False, f"{type(exc).__name__}: {exc}")
        checks = [path_check, failure]
        manifest = _attempt_manifest(generation_id, "FAIL", error=failure.detail)
        manifest["checks"] = [asdict(c) for c in checks]

    try:
        report_payload = render_report(checks, manifest)
        reproduction = dict(repro_metadata)
        reproduction["generation_id"] = generation_id
        reproduction["verification_status"] = manifest["status"]
        reproduction_payload = _json_payload(reproduction)
        manifest["companion_files"] = {
            "verification_report.md": hashlib.sha256(report_payload.encode("utf-8")).hexdigest(),
            "reproduction_metadata.json": hashlib.sha256(reproduction_payload.encode("utf-8")).hexdigest(),
        }
        _atomic_write(out_dir / "verification_report.md", report_payload)
        _atomic_write(out_dir / "reproduction_metadata.json", reproduction_payload)
        _atomic_write(out_dir / "artifact_manifest.json", _json_payload(manifest))
    except Exception as exc:
        failure_manifest = _attempt_manifest(generation_id, "INCOMPLETE", error=f"publication failure: {type(exc).__name__}: {exc}")
        try:
            _atomic_write(out_dir / "artifact_manifest.json", _json_payload(failure_manifest))
        except Exception:
            pass
        print(f"VERIFY WRITE FAILED: {type(exc).__name__}: {exc}")
        return EXIT_WRITE_FAILED

    passed = sum(1 for check in checks if check.ok)
    failed = len(checks) - passed
    print(f"Verification checks: {passed} passed, {failed} failed")
    print(f"Wrote {out_dir}")
    return EXIT_OK if manifest["verified"] else EXIT_INVALID


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
