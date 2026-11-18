"""Build the UI bundle from the agreed pipeline outputs (Task 15 Part B).

This module holds the export logic as small functions; the command-line entry
point is ``scripts/export_ui_artifacts.py``.

Source verification: the export reads only inputs whose SHA-256 equals the
value recorded in the reference files committed on ``main``. It never decides
which run is authoritative; ``main`` does. Reference values are read from the
committed files at export time, so a future agreed run needs no code change.
"""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import numpy as np
import pandas as pd
import pyarrow

from src.evaluation.metrics import cpu_violation, memory_violation
from src.policies.hybrid import hybrid_recommendation
from src.service.contract import (
    ALIBABA,
    DATASETS,
    GOOGLE,
    POLICY_IDS,
    POLICY_NAMES,
    RECOMMENDATION_COLUMNS,
    WORKLOAD_COLUMNS,
    validate_frame,
)
from src.service.bundle import verify_bundle, write_checksums
from src.service.contract import BUNDLE_SCHEMA_VERSION
from src.service.risk_levels import DEFAULT_CONFIG_PATH as DEFAULT_RISK_LEVEL_CONFIG
from src.service.risk_levels import load_risk_level_config

ALIBABA_ARTIFACT_MANIFEST = "reports/results/alibaba_gpu_2020/verification/artifact_manifest.json"
ALIBABA_RUN_RECORD = "reports/results/alibaba_gpu_2020/final_test/run_record.json"
ALIBABA_LOCAL_RUN_RECORD = "data/processed/alibaba_gpu_v2020_final_test/run_record.json"
ALIBABA_INPUTS = (
    "data/processed/alibaba_gpu_v2020_final_test/final_test_predictions.parquet",
    ALIBABA_LOCAL_RUN_RECORD,
    "data/processed/alibaba_gpu_v2020_targets/test.parquet",
    "data/processed/alibaba_gpu_v2020_baselines/recommendations_test.parquet",
)

GOOGLE_DECISION_MANIFEST = "reports/results/google_subset/decision_manifest.json"
GOOGLE_INPUTS = (
    "data/processed/google_subset_v1/test_occurrences.parquet",
    "data/processed/google_subset_v1/test_ml_predictions.parquet",
)
# Used only to check recommendations and to copy exceeded flags; not pinned by
# the decision manifest, so its checksum is recorded in metadata.json.
GOOGLE_ROW_LEVEL = "data/processed/google_subset_v1/final_test_row_level.parquet"

# Run-record fields that must equal the committed record, and counters that
# must be exactly the integer 1 (one test-target read, one evaluator call).
RUN_RECORD_IDENTITY_FIELDS = ("run_id", "decision_manifest_sha256")
RUN_RECORD_COUNTERS = ("test_target_read_count", "test_evaluator_call_count")


class SourceVerificationError(RuntimeError):
    """The references are inconsistent, or inputs differ and development mode is off."""


@dataclass(frozen=True)
class ExpectedInput:
    path: str  # relative to the repository root
    sha256: str


@dataclass(frozen=True)
class SourceReference:
    dataset_id: str
    reference_files: tuple[str, ...]
    inputs: tuple[ExpectedInput, ...]
    run_id: str | None
    decision_manifest_sha256: str | None


@dataclass(frozen=True)
class Mismatch:
    path: str
    reason: str  # "missing", "checksum" or "run_record:<field>"
    expected: str | None
    found: str | None

    def describe(self) -> str:
        return f"{self.path}: {self.reason} (expected {self.expected}, found {self.found})"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 24), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict:
    if not path.is_file():
        raise SourceVerificationError(f"reference file missing: {path}")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def alibaba_references(repo: Path) -> SourceReference:
    """Expected Alibaba inputs from the committed artifact manifest and run record."""
    manifest = _load_json(repo / ALIBABA_ARTIFACT_MANIFEST)
    run_record = _load_json(repo / ALIBABA_RUN_RECORD)

    if manifest.get("verified") is not True or manifest.get("status") != "PASS":
        raise SourceVerificationError(f"{ALIBABA_ARTIFACT_MANIFEST} is not a passing verification")
    identity = manifest.get("final_run_identity") or {}
    for field in RUN_RECORD_IDENTITY_FIELDS:
        if identity.get(field) != run_record.get(field):
            raise SourceVerificationError(
                f"committed references disagree on {field}: manifest {identity.get(field)!r}, "
                f"run record {run_record.get(field)!r}"
            )

    recorded = {artifact["path"]: artifact["sha256"] for artifact in manifest.get("artifacts", [])}
    missing = [path for path in ALIBABA_INPUTS if path not in recorded]
    if missing:
        raise SourceVerificationError(f"{ALIBABA_ARTIFACT_MANIFEST} has no checksum for {missing}")

    return SourceReference(
        dataset_id=ALIBABA,
        reference_files=(ALIBABA_ARTIFACT_MANIFEST, ALIBABA_RUN_RECORD),
        inputs=tuple(ExpectedInput(path, recorded[path]) for path in ALIBABA_INPUTS),
        run_id=run_record["run_id"],
        decision_manifest_sha256=run_record["decision_manifest_sha256"],
    )


def google_references(repo: Path) -> SourceReference:
    """Expected Google inputs from the committed decision manifest."""
    manifest = _load_json(repo / GOOGLE_DECISION_MANIFEST)

    if manifest.get("status") != "final":
        raise SourceVerificationError(f"{GOOGLE_DECISION_MANIFEST} status is {manifest.get('status')!r}, not 'final'")
    recorded = manifest.get("input_sha256") or {}
    missing = [path for path in GOOGLE_INPUTS if path not in recorded]
    if missing:
        raise SourceVerificationError(f"{GOOGLE_DECISION_MANIFEST} has no checksum for {missing}")

    return SourceReference(
        dataset_id=GOOGLE,
        reference_files=(GOOGLE_DECISION_MANIFEST,),
        inputs=tuple(ExpectedInput(path, recorded[path]) for path in GOOGLE_INPUTS),
        run_id=None,
        decision_manifest_sha256=file_sha256(repo / GOOGLE_DECISION_MANIFEST),
    )


def verify_sources(reference: SourceReference, repo: Path) -> list[Mismatch]:
    """Hash every expected input; return one mismatch per missing or differing file."""
    mismatches = []
    for expected in reference.inputs:
        path = repo / expected.path
        if not path.is_file():
            mismatches.append(Mismatch(expected.path, "missing", expected.sha256, None))
            continue
        found = file_sha256(path)
        if found != expected.sha256:
            mismatches.append(Mismatch(expected.path, "checksum", expected.sha256, found))
    return mismatches


def check_alibaba_run_record(reference: SourceReference, repo: Path) -> list[Mismatch]:
    """Compare the local run record's identity and counters with the committed run."""
    path = repo / ALIBABA_LOCAL_RUN_RECORD
    if not path.is_file():
        return []  # already reported as missing by verify_sources
    with open(path, encoding="utf-8") as handle:
        local = json.load(handle)

    mismatches = []
    expected_identity = {"run_id": reference.run_id, "decision_manifest_sha256": reference.decision_manifest_sha256}
    for field, expected in expected_identity.items():
        if local.get(field) != expected:
            mismatches.append(Mismatch(ALIBABA_LOCAL_RUN_RECORD, f"run_record:{field}", expected, local.get(field)))
    for field in RUN_RECORD_COUNTERS:
        value = local.get(field)
        # bool is a subclass of int, so True must be rejected explicitly.
        if type(value) is not int or value != 1:
            mismatches.append(Mismatch(ALIBABA_LOCAL_RUN_RECORD, f"run_record:{field}", "1", repr(value)))
    return mismatches


def verify_dataset_sources(dataset_id: str, repo: Path) -> tuple[SourceReference, list[Mismatch]]:
    """References and every mismatch for one dataset."""
    if dataset_id == ALIBABA:
        reference = alibaba_references(repo)
        return reference, verify_sources(reference, repo) + check_alibaba_run_record(reference, repo)
    if dataset_id == GOOGLE:
        reference = google_references(repo)
        return reference, verify_sources(reference, repo)
    raise ValueError(f"unknown dataset: {dataset_id}")


def source_status(mismatches: list[Mismatch], allow_unverified_source: bool) -> str:
    """``verified`` without mismatches, ``development`` when allowed, otherwise refuse."""
    if not mismatches:
        return "verified"
    if allow_unverified_source:
        return "development"
    listed = "\n  ".join(mismatch.describe() for mismatch in mismatches)
    raise SourceVerificationError(
        f"{len(mismatches)} input(s) do not match the references committed on main:\n  {listed}\n"
        "Use --allow-unverified-source only for a local development bundle."
    )


# --- Google export -------------------------------------------------------------

RESOURCES = ("cpu", "memory")

# Google history policies: policy name -> column suffix in test_occurrences.parquet.
GOOGLE_HISTORY_POLICIES = {"Mean": "mean", "P90": "p90", "P95": "p95", "P99": "p99"}
GOOGLE_HYBRID_SAFEGUARD = "p95"
GOOGLE_TARGET_COLUMNS = {
    "cpu": "target_cpu_next_occurrence_peak_ncu",
    "memory": "target_memory_next_occurrence_peak_normalized",
}


class ExportValidationError(RuntimeError):
    """Source tables are inconsistent, or an exported value differs from its source."""


@dataclass(frozen=True)
class DatasetExport:
    recommendations: pd.DataFrame
    # Counts recorded in metadata.json, e.g. rows where Hybrid had no safeguard.
    notes: dict


def _require_unique(df: pd.DataFrame, columns: list[str], table: str) -> None:
    duplicated = int(df.duplicated(columns).sum())
    if duplicated:
        raise ExportValidationError(f"{table}: {duplicated} duplicate rows on {columns}")


def _google_occurrences(occurrences: pd.DataFrame, ml_predictions: pd.DataFrame) -> pd.DataFrame:
    """One row per test occurrence with its ML prediction and the identity of the next run."""
    _require_unique(occurrences, ["occurrence_id"], "test_occurrences")
    _require_unique(ml_predictions, ["occurrence_id"], "test_ml_predictions")
    if set(occurrences["occurrence_id"]) != set(ml_predictions["occurrence_id"]):
        raise ExportValidationError("test_occurrences and test_ml_predictions cover different occurrences")

    frame = occurrences.merge(
        ml_predictions[["occurrence_id", "ml_pred_cpu", "ml_pred_memory"]],
        on="occurrence_id",
        how="inner",
        validate="one_to_one",
    )
    frame = frame.sort_values(["recurrence_key", "execution_start_time_us"], kind="mergesort").reset_index(drop=True)
    next_run = frame.groupby("recurrence_key", sort=False)
    frame["next_occurrence_id"] = next_run["occurrence_id"].shift(-1)
    frame["next_start_time_us"] = next_run["execution_start_time_us"].shift(-1)

    # The stored target must describe exactly the next run of the same workload.
    stored = frame["target_next_occurrence_start_time_us"]
    has_target = stored.notna()
    if not frame["next_occurrence_id"].notna().eq(has_target).all():
        raise ExportValidationError("Google targets do not match the next run of each workload")
    if not (frame.loc[has_target, "next_start_time_us"].astype("int64") == stored[has_target].astype("int64")).all():
        raise ExportValidationError("Google target start times differ from the next run's start time")
    peaks = frame.set_index("occurrence_id")
    for resource, target_column in GOOGLE_TARGET_COLUMNS.items():
        peak_column = "occurrence_peak_cpu_ncu" if resource == "cpu" else "occurrence_peak_memory_normalized"
        next_peak = peaks[peak_column].reindex(frame.loc[has_target, "next_occurrence_id"]).to_numpy()
        target = frame.loc[has_target, target_column].to_numpy()
        if not np.array_equal(next_peak, target, equal_nan=True):
            raise ExportValidationError(f"Google {resource} targets differ from the next run's peak")
    return frame


def _google_target_status(frame: pd.DataFrame, resource: str) -> pd.Series:
    actual = frame[GOOGLE_TARGET_COLUMNS[resource]]
    has_next = frame["target_next_occurrence_start_time_us"].notna()
    status = np.where(actual.notna(), "available", np.where(has_next, "next_occurrence_ineligible_resource", "no_next_occurrence"))
    return pd.Series(status, index=frame.index, dtype="string")


def _google_policy_rows(frame: pd.DataFrame, policy: str) -> tuple[pd.DataFrame, dict]:
    """Recommendation, basis and history count per resource for one policy."""
    columns, missing_safeguard = {}, {}
    for resource in RESOURCES:
        count = frame[f"occ_hist_peak_{resource}_count"].astype("Int64")
        if policy == "Request":
            value = frame[f"rec_{resource}_request"]
            basis = pd.Series("request", index=frame.index)
            count = pd.Series(pd.NA, index=frame.index, dtype="Int64")
        elif policy == "ML":
            value = frame[f"ml_pred_{resource}"]
            basis = pd.Series("model", index=frame.index)
            count = pd.Series(pd.NA, index=frame.index, dtype="Int64")
        else:
            suffix = GOOGLE_HISTORY_POLICIES.get(policy, GOOGLE_HYBRID_SAFEGUARD)
            uses_history = frame[f"uses_history_{resource}_{suffix}"].astype(bool)
            basis = pd.Series(np.where(uses_history, "history", "request_fallback"), index=frame.index)
            value = frame[f"rec_{resource}_{suffix}"]
            if policy == "Hybrid":
                hybrid, guard_missing = hybrid_recommendation(frame[f"ml_pred_{resource}"], value)
                value = pd.Series(hybrid, index=frame.index)
                # Without a safeguard, Hybrid is the ML prediction alone.
                basis = basis.mask(guard_missing, "model")
                missing_safeguard[resource] = int(guard_missing.sum())
        columns[f"recommended_{resource}"] = value.astype("float64")
        columns[f"{resource}_basis"] = basis.astype("string")
        columns[f"{resource}_history_run_count"] = count
    return pd.DataFrame(columns, index=frame.index), missing_safeguard


VIOLATION_RULES = {"cpu": cpu_violation, "memory": memory_violation}


def _attach_exceeded(recommendations: pd.DataFrame, row_level: pd.DataFrame) -> pd.DataFrame:
    """Copy the stored violation flags; check every scored recommendation and flag equals the stored one."""
    _require_unique(row_level, ["occurrence_id", "policy_name"], "final_test_row_level")
    stored = row_level.rename(columns={"policy_name": "policy"})[
        ["occurrence_id", "policy", "recommended_cpu", "recommended_memory", "cpu_violation", "memory_violation"]
    ]
    merged = recommendations.merge(
        stored, on=["occurrence_id", "policy"], how="left", validate="one_to_one", suffixes=("", "_stored"), indicator=True
    )
    if (merged["_merge"] == "both").sum() != len(stored):
        raise ExportValidationError("final_test_row_level has rows that are not test recommendations")
    scored = merged["_merge"] == "both"
    available = (merged["cpu_target_status"] == "available") | (merged["memory_target_status"] == "available")
    if not scored.eq(available).all():
        raise ExportValidationError("scored rows differ from rows with an available target")

    for resource in RESOURCES:
        ours = merged.loc[scored, f"recommended_{resource}"].to_numpy()
        theirs = merged.loc[scored, f"recommended_{resource}_stored"].to_numpy()
        differs = ~((ours == theirs) | (np.isnan(ours) & np.isnan(theirs)))
        if differs.any():
            policies = sorted(merged.loc[scored].loc[differs, "policy"].unique())
            raise ExportValidationError(f"{resource} recommendations differ from the stored final test for {policies}")
        stored_flag = merged.loc[scored, f"{resource}_violation"].to_numpy(dtype=float)
        recomputed = VIOLATION_RULES[resource](
            merged.loc[scored, f"actual_{resource}"].to_numpy(dtype=float), merged.loc[scored, f"recommended_{resource}"].to_numpy(dtype=float)
        )
        differs = ~((stored_flag == recomputed) | (np.isnan(stored_flag) & np.isnan(recomputed)))
        if differs.any():
            policies = sorted(merged.loc[scored].loc[differs, "policy"].unique())
            raise ExportValidationError(f"stored {resource} violation flags differ from actual > recommended for {policies}")
        merged[f"{resource}_exceeded"] = merged[f"{resource}_violation"].map({1.0: True, 0.0: False}).astype("boolean")
    return merged


def _finish(recommendations: pd.DataFrame, dataset_id: str) -> pd.DataFrame:
    """Select and type the bundle columns, validate them, and check one latest run per workload."""
    recommendations = recommendations[[spec.name for spec in RECOMMENDATION_COLUMNS]].astype(
        {spec.name: "string" for spec in RECOMMENDATION_COLUMNS if spec.dtype == "string"}
    )
    validate_frame(recommendations, RECOMMENDATION_COLUMNS, f"{dataset_id} recommendations")

    latest = recommendations[recommendations["is_latest"] & (recommendations["policy"] == POLICY_NAMES[0])]
    if latest["workload_id"].duplicated().any() or latest["workload_id"].nunique() != recommendations["workload_id"].nunique():
        raise ExportValidationError(f"{dataset_id}: expected exactly one latest run per workload")

    # A fixed row order makes the written files, and so their checksums, reproducible.
    policy_rank = recommendations["policy"].map({name: rank for rank, name in enumerate(POLICY_NAMES)})
    order = recommendations.assign(_policy_rank=policy_rank).sort_values(
        ["workload_id", "start_time_us", "occurrence_id", "role_key", "_policy_rank"], kind="mergesort", na_position="first"
    )
    return order.drop(columns="_policy_rank").reset_index(drop=True)


def export_google(
    occurrences: pd.DataFrame, ml_predictions: pd.DataFrame, row_level: pd.DataFrame, summary: pd.DataFrame | None = None
) -> DatasetExport:
    """Google recommendations in the bundle format: one row per test occurrence and policy.

    With ``summary`` (the committed policy comparison), the exceeded flags must also reproduce its rates.
    """
    frame = _google_occurrences(occurrences, ml_predictions)

    base = pd.DataFrame(
        {
            "workload_id": frame["recurrence_key"].astype("string"),
            "occurrence_id": frame["occurrence_id"].astype("string"),
            "role_key": pd.Series(pd.NA, index=frame.index, dtype="string"),
            "start_time_us": frame["execution_start_time_us"].astype("int64"),
            "target_start_time_us": frame["target_next_occurrence_start_time_us"].astype("Int64"),
            "target_occurrence_id": frame["next_occurrence_id"].astype("string"),
            "request_cpu": frame["rec_cpu_request"].astype("float64"),
            "request_memory": frame["rec_memory_request"].astype("float64"),
            "actual_cpu": frame[GOOGLE_TARGET_COLUMNS["cpu"]].astype("float64"),
            "actual_memory": frame[GOOGLE_TARGET_COLUMNS["memory"]].astype("float64"),
            "cpu_target_status": _google_target_status(frame, "cpu"),
            "memory_target_status": _google_target_status(frame, "memory"),
            "is_latest": frame["next_occurrence_id"].isna(),
        }
    )

    parts, hybrid_safeguard_missing = [], {}
    for policy in POLICY_NAMES:
        values, missing = _google_policy_rows(frame, policy)
        hybrid_safeguard_missing.update(missing)
        parts.append(base.assign(policy=pd.Series(policy, index=frame.index, dtype="string")).join(values))
    recommendations = pd.concat(parts, ignore_index=True)

    recommendations = _finish(_attach_exceeded(recommendations, row_level), GOOGLE)
    if summary is not None:
        _check_against_summary(recommendations, summary, GOOGLE)

    notes = {
        "hybrid_safeguard": "P95",
        "hybrid_safeguard_missing": hybrid_safeguard_missing,
        "target_occurrence_id": "next run of the same workload by start time, checked against the stored target start time and peak",
        "exceeded": "stored final-test flags, checked against actual > recommended (src/evaluation/metrics.py) "
        "and final_test_policy_comparison.csv",
    }
    return DatasetExport(recommendations=recommendations, notes=notes)


# --- Alibaba export ------------------------------------------------------------

# Alibaba recommendation columns in final_test_predictions.parquet, per policy.
ALIBABA_PREDICTION_COLUMNS = {
    "Request": "rec_{resource}_request",
    "Mean": "rec_{resource}_mean",
    "P90": "rec_{resource}_p90",
    "P95": "rec_{resource}_p95",
    "P99": "rec_{resource}_p99",
    "ML": "ml_recommended_{resource}",
    "Hybrid": "hybrid_recommended_{resource}",
}
ALIBABA_HISTORY_POLICIES = {"Mean": "mean", "P90": "p90", "P95": "p95", "P99": "p99"}
ALIBABA_HYBRID_SAFEGUARD = "p99"
# Task 4 measures the CPU target as the next run's average and memory as its peak.
ALIBABA_TARGET_SOURCE = {"cpu": "observed_cpu", "memory": "peak_memory"}
# Task 4 total order that defines each run's successor (src/features/target_builder.py).
ALIBABA_RUN_ORDER = ["recurrence_key", "start_time_us", "occurrence_id", "role_key"]


def _same_values(left: pd.Series, right: pd.Series) -> bool:
    """Exact equality with nulls equal to nulls."""
    a = left.astype("float64").to_numpy()
    b = right.astype("float64").to_numpy()
    return bool(np.array_equal(a, b, equal_nan=True))


def _alibaba_runs(predictions: pd.DataFrame, targets: pd.DataFrame, baselines: pd.DataFrame) -> pd.DataFrame:
    """One row per test run: predictions joined one-to-one with Task 4 and Task 6 on role_key."""
    for table, frame in (("final_test_predictions", predictions), ("targets/test", targets), ("recommendations_test", baselines)):
        _require_unique(frame, ["role_key"], table)
    if not (set(predictions["role_key"]) == set(targets["role_key"]) == set(baselines["role_key"])):
        raise ExportValidationError("Alibaba predictions, Task 4 targets and Task 6 recommendations cover different runs")

    target_columns = ["role_key", "occurrence_id", "recurrence_key", "start_time_us", *ALIBABA_TARGET_SOURCE.values()]
    target_columns += [f"{r}_target_status" for r in RESOURCES] + [f"actual_{r}" for r in RESOURCES]
    history_columns = ["role_key", "start_time_us"] + [f"{r}_history_count" for r in RESOURCES]
    for resource in RESOURCES:
        for suffix in ALIBABA_HISTORY_POLICIES.values():
            history_columns += [f"uses_history_{resource}_{suffix}", f"rec_{resource}_{suffix}"]
        history_columns.append(f"rec_{resource}_request")

    runs = predictions.merge(targets[target_columns], on="role_key", how="inner", validate="one_to_one", suffixes=("", "_task4"))
    runs = runs.merge(baselines[history_columns], on="role_key", how="inner", validate="one_to_one", suffixes=("", "_task6"))

    for column in ("occurrence_id", "recurrence_key"):
        if not runs[column].astype("string").eq(runs[f"{column}_task4"].astype("string")).all():
            raise ExportValidationError(f"Alibaba {column} differs between predictions and Task 4 targets")
    if not runs["start_time_us"].astype("int64").eq(runs["start_time_us_task6"].astype("int64")).all():
        raise ExportValidationError("Alibaba start times differ between Task 4 and Task 6")
    for resource in RESOURCES:
        status = f"{resource}_target_status"
        if not runs[status].astype("string").eq(runs[f"{status}_task4"].astype("string")).all():
            raise ExportValidationError(f"Alibaba {status} differs between predictions and Task 4 targets")
        if not _same_values(runs[f"actual_{resource}"], runs[f"actual_{resource}_task4"]):
            raise ExportValidationError(f"Alibaba actual_{resource} differs between predictions and Task 4 targets")
        for suffix in ("request", *ALIBABA_HISTORY_POLICIES.values()):
            column = f"rec_{resource}_{suffix}"
            if not _same_values(runs[column], runs[f"{column}_task6"]):
                raise ExportValidationError(f"Alibaba {column} differs between predictions and Task 6 recommendations")
        hybrid = np.fmax(runs[f"ml_recommended_{resource}"].astype("float64"), runs[f"rec_{resource}_{ALIBABA_HYBRID_SAFEGUARD}"].astype("float64"))
        if not _same_values(runs[f"hybrid_recommended_{resource}"], hybrid):
            raise ExportValidationError(f"Alibaba stored {resource} Hybrid is not max(ML, P99)")
    return runs


def _alibaba_successors(runs: pd.DataFrame) -> pd.DataFrame:
    """Next run of each workload in the Task 4 order, checked against the stored targets."""
    runs = runs.sort_values(ALIBABA_RUN_ORDER, kind="mergesort").reset_index(drop=True)
    following = runs.assign(start_time_us=runs["start_time_us"].astype("Int64")).groupby("recurrence_key", sort=False)
    runs["next_occurrence_id"] = following["occurrence_id"].shift(-1)
    runs["next_start_time_us"] = following["start_time_us"].shift(-1)
    has_next = runs["next_occurrence_id"].notna()

    for resource, source in ALIBABA_TARGET_SOURCE.items():
        status = runs[f"{resource}_target_status"].astype("string")
        if not status.eq("no_next_occurrence").eq(~has_next).all():
            raise ExportValidationError(f"Alibaba {resource}: 'no_next_occurrence' does not match the Task 4 run order")
        available = status.eq("available")
        next_value = following[source].shift(-1)
        if not _same_values(runs.loc[available, f"actual_{resource}"], next_value[available]):
            raise ExportValidationError(f"Alibaba {resource} targets differ from the next run in the Task 4 order")
    return runs


def _alibaba_policy_rows(runs: pd.DataFrame, policy: str) -> tuple[pd.DataFrame, dict]:
    columns, missing_safeguard = {}, {}
    for resource in RESOURCES:
        value = runs[ALIBABA_PREDICTION_COLUMNS[policy].format(resource=resource)].astype("float64")
        count = runs[f"{resource}_history_count"].astype("Int64")
        if policy == "Request":
            basis = pd.Series("request", index=runs.index)
            count = pd.Series(pd.NA, index=runs.index, dtype="Int64")
        elif policy == "ML":
            basis = pd.Series("model", index=runs.index)
            count = pd.Series(pd.NA, index=runs.index, dtype="Int64")
        else:
            suffix = ALIBABA_HISTORY_POLICIES.get(policy, ALIBABA_HYBRID_SAFEGUARD)
            uses_history = runs[f"uses_history_{resource}_{suffix}"].astype(bool)
            basis = pd.Series(np.where(uses_history, "history", "request_fallback"), index=runs.index)
            if policy == "Hybrid":
                guard_missing = runs[f"rec_{resource}_{suffix}"].isna()
                basis = basis.mask(guard_missing, "model")
                missing_safeguard[resource] = int(guard_missing.sum())
        exceeded = VIOLATION_RULES[resource](runs[f"actual_{resource}"].astype("float64"), value)
        columns[f"recommended_{resource}"] = value
        columns[f"{resource}_basis"] = basis.astype("string")
        columns[f"{resource}_history_run_count"] = count
        columns[f"{resource}_exceeded"] = pd.Series(exceeded, index=runs.index).map({1.0: True, 0.0: False}).astype("boolean")
    return pd.DataFrame(columns, index=runs.index), missing_safeguard


def _check_against_summary(recommendations: pd.DataFrame, summary: pd.DataFrame, dataset_id: str) -> None:
    """Violation rates and valid counts from the exceeded flags must equal the run's summary CSV."""
    summary = summary.set_index("policy")
    for policy, rows in recommendations.groupby("policy", sort=False):
        for resource in RESOURCES:
            flags = rows[f"{resource}_exceeded"]
            valid = int(flags.notna().sum())
            rate = float(flags.dropna().astype(float).mean() * 100) if valid else float("nan")
            expected_valid = int(summary.loc[policy, f"valid_{resource}_violation_count"])
            expected_rate = float(summary.loc[policy, f"{resource}_violation_pct"])
            if valid != expected_valid or not np.isclose(rate, expected_rate, rtol=1e-12, atol=0):
                raise ExportValidationError(
                    f"{dataset_id} {policy} {resource}: exceeded flags give {rate} over {valid} rows, "
                    f"summary has {expected_rate} over {expected_valid}"
                )


def export_alibaba(
    predictions: pd.DataFrame, targets: pd.DataFrame, baselines: pd.DataFrame, summary: pd.DataFrame
) -> DatasetExport:
    """Alibaba recommendations in the bundle format: one row per test run (role_key) and policy."""
    runs = _alibaba_successors(_alibaba_runs(predictions, targets, baselines))
    has_next = runs["next_occurrence_id"].notna()

    base = pd.DataFrame(
        {
            "workload_id": runs["recurrence_key"].astype("string"),
            "occurrence_id": runs["occurrence_id"].astype("string"),
            "role_key": runs["role_key"].astype("string"),
            "start_time_us": runs["start_time_us"].astype("int64"),
            "target_start_time_us": runs["next_start_time_us"].astype("Int64"),
            "target_occurrence_id": runs["next_occurrence_id"].astype("string"),
            "request_cpu": runs["rec_cpu_request"].astype("float64"),
            "request_memory": runs["rec_memory_request"].astype("float64"),
            "actual_cpu": runs["actual_cpu"].astype("float64"),
            "actual_memory": runs["actual_memory"].astype("float64"),
            "cpu_target_status": runs["cpu_target_status"].astype("string"),
            "memory_target_status": runs["memory_target_status"].astype("string"),
            "is_latest": ~has_next,
        }
    )

    parts, hybrid_safeguard_missing = [], {}
    for policy in POLICY_NAMES:
        values, missing = _alibaba_policy_rows(runs, policy)
        hybrid_safeguard_missing.update(missing)
        parts.append(base.assign(policy=pd.Series(policy, index=runs.index, dtype="string")).join(values))
    recommendations = _finish(pd.concat(parts, ignore_index=True), ALIBABA)
    _check_against_summary(recommendations, summary, ALIBABA)

    notes = {
        "hybrid_safeguard": "P99",
        "hybrid_safeguard_missing": hybrid_safeguard_missing,
        "target_occurrence_id": "next run of the same workload in the Task 4 order "
        "(recurrence_key, start_time_us, occurrence_id, role_key), checked against the stored targets",
        "exceeded": "actual > recommended (src/evaluation/metrics.py), checked against final_test_policy_comparison.csv",
    }
    return DatasetExport(recommendations=recommendations, notes=notes)


# --- Bundle contents -------------------------------------------------------------

GOOGLE_SUMMARY_CSV = "reports/results/google_subset/tables/final_test_policy_comparison.csv"
ALIBABA_SUMMARY_CSV = "reports/results/alibaba_gpu_2020/final_test/final_test_policy_comparison.csv"
ALIBABA_ML_DECISION_MANIFEST = "reports/results/alibaba_gpu_2020/ml/decision_manifest.json"
FALLBACK_POLICIES = ("Mean", "P90", "P95", "P99", "Hybrid")

DATASET_CAVEATS = {
    GOOGLE: [
        "CPU and memory are normalized by the trace publisher: values can be compared between policies "
        "but cannot be converted to cores or gigabytes.",
        "User and job names are hashed in the trace, so workload names are identifiers, not readable names.",
        # The Task 12 limitations for Google (reports/results/cross_dataset_final/limitations.md).
        "Some training and validation targets came from runs in a later split, so validation and the model and "
        "policy selection made on it were contaminated (findings F3 and F4); these are not leakage-safe final results.",
        "Abnormal or incomplete records and aggregation across machines remain limitations (findings F7 and F8).",
        "The data is a subset of the trace, which limits how far the results generalize to the full ClusterData2019 trace.",
        "The validation population is small, which limits confidence in the choice of model and policy.",
    ],
    ALIBABA: [
        "CPU is the average usage of a run, not its peak: a run can stay within a CPU recommendation on "
        "average and still exceed it during short bursts.",
        "Memory is the peak of a run and is the primary resource.",
        "Only completed runs with full measurements are included.",
    ],
}
COMMON_CAVEAT = (
    "Results replay the historical test period once: each recommendation is compared with what the next "
    "run of the same workload actually used. They are not measurements from a live cluster."
)


def workload_display_name(dataset_id: str, workload_id: str) -> str:
    """Google keys are hashed identifiers shown as they are; Alibaba keys read as group / task."""
    return workload_id.replace("||", " / ") if dataset_id == ALIBABA else workload_id


def build_workloads(recommendations: pd.DataFrame, dataset_id: str, default_policy: str) -> pd.DataFrame:
    """One row per workload, summarised from the recommendations of the default risk level's policy."""
    rows = recommendations[recommendations["policy"] == default_policy]
    scored = rows["cpu_target_status"].eq("available") | rows["memory_target_status"].eq("available")
    latest = rows[rows["is_latest"]].set_index("workload_id")
    grouped = rows.assign(scored=scored).groupby("workload_id", sort=True)

    workloads = pd.DataFrame(
        {
            "test_run_count": grouped.size().astype("int64"),
            "scored_run_count": grouped["scored"].sum().astype("int64"),
            "first_start_time_us": grouped["start_time_us"].min().astype("int64"),
            "last_start_time_us": grouped["start_time_us"].max().astype("int64"),
        }
    )
    workloads["latest_occurrence_id"] = latest["occurrence_id"].reindex(workloads.index).astype("string")
    workloads["latest_uses_history"] = (
        latest["cpu_basis"].eq("history") | latest["memory_basis"].eq("history")
    ).reindex(workloads.index).astype(bool)
    workloads["has_scored_history"] = workloads["scored_run_count"] > 0
    workloads = workloads.reset_index()
    workloads["workload_id"] = workloads["workload_id"].astype("string")
    workloads.insert(1, "display_name", workloads["workload_id"].map(lambda key: workload_display_name(dataset_id, key)).astype("string"))
    if not (latest["start_time_us"].reindex(workloads["workload_id"]).to_numpy() == workloads["last_start_time_us"].to_numpy()).all():
        raise ExportValidationError(f"{dataset_id}: a latest run does not have the workload's last start time")

    workloads = workloads[[spec.name for spec in WORKLOAD_COLUMNS]]
    validate_frame(workloads, WORKLOAD_COLUMNS, f"{dataset_id} workloads")
    return workloads


def bundle_fallback_counts(recommendations: pd.DataFrame) -> dict:
    """Latest runs whose recommendation keeps the request, per policy and resource."""
    latest = recommendations[recommendations["is_latest"]]
    counts = {}
    for policy in FALLBACK_POLICIES:
        rows = latest[latest["policy"] == policy]
        counts[policy] = {resource: int(rows[f"{resource}_basis"].eq("request_fallback").sum()) for resource in RESOURCES}
    return counts


def google_source_fallback_counts(occurrences: pd.DataFrame) -> dict:
    """The same counts taken directly from the Google uses_history flags of runs without a next run."""
    latest = occurrences[occurrences["target_next_occurrence_start_time_us"].isna()]
    return {
        policy: {resource: int((~latest[f"uses_history_{resource}_{suffix}"].astype(bool)).sum()) for resource in RESOURCES}
        for policy, suffix in GOOGLE_HISTORY_POLICIES.items()
    }


def alibaba_source_fallback_counts(targets: pd.DataFrame, baselines: pd.DataFrame) -> dict:
    """The same counts taken directly from the Task 6 flags of runs without a next run in Task 4."""
    latest_keys = targets.loc[targets["memory_target_status"].eq("no_next_occurrence"), "role_key"]
    latest = baselines[baselines["role_key"].isin(latest_keys)]
    return {
        policy: {resource: int((~latest[f"uses_history_{resource}_{suffix}"].astype(bool)).sum()) for resource in RESOURCES}
        for policy, suffix in ALIBABA_HISTORY_POLICIES.items()
    }


def check_fallback_counts(bundle_counts: dict, source_counts: dict, hybrid_safeguard: str, hybrid_missing: dict) -> None:
    """History policies must match the source flags; Hybrid must match its safeguard less rows without one."""
    for policy, expected in source_counts.items():
        if bundle_counts[policy] != expected:
            raise ExportValidationError(f"latest-run fallback for {policy}: bundle {bundle_counts[policy]}, source {expected}")
    for resource in RESOURCES:
        expected = source_counts[hybrid_safeguard][resource] - hybrid_missing.get(resource, 0)
        if bundle_counts["Hybrid"][resource] != expected:
            raise ExportValidationError(f"latest-run Hybrid {resource} fallback {bundle_counts['Hybrid'][resource]}, expected {expected}")


def _csv_value(text: str):
    """A summary-CSV cell as JSON: empty -> null, True/False -> bool, numbers exactly as parsed."""
    if text == "":
        return None
    if text in ("True", "False"):
        return text == "True"
    for parse in (int, float):
        try:
            return parse(text)
        except ValueError:
            pass
    return text


def build_policy_metrics(repo: Path, summary_csv: str, dataset_id: str) -> dict:
    """The committed summary CSV copied field by field; nothing is recomputed."""
    with open(Path(repo) / summary_csv, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    policies = [row["policy"] for row in rows]
    if policies != list(POLICY_NAMES):
        raise ExportValidationError(f"{summary_csv}: policies {policies}, expected {list(POLICY_NAMES)}")
    metrics = [{key: _csv_value(value) for key, value in row.items()} for row in rows]
    for row, copied in zip(rows, metrics):
        for key, value in row.items():
            back = "" if copied[key] is None else str(copied[key])
            if back != value and not (isinstance(copied[key], float) and float(value) == copied[key]):
                raise ExportValidationError(f"{summary_csv}: {row['policy']}.{key} did not copy exactly")
    for row in metrics:
        row["policy_id"] = POLICY_IDS[row["policy"]]
    return {"dataset_id": dataset_id, "source": summary_csv, "policies": metrics}


def build_rules(repo: Path) -> dict:
    """Locked rules per dataset, copied from the committed decision records."""
    google = _load_json(repo / GOOGLE_DECISION_MANIFEST)["decisions"]
    if "P95" not in google["hybrid_rule"] or GOOGLE_HYBRID_SAFEGUARD != "p95":
        raise ExportValidationError(f"Google Hybrid rule {google['hybrid_rule']!r} does not use P95")
    run_record = _load_json(repo / ALIBABA_RUN_RECORD)
    alibaba_ml = _load_json(repo / ALIBABA_ML_DECISION_MANIFEST)
    if run_record["selected_baseline_policy"].lower() != ALIBABA_HYBRID_SAFEGUARD:
        raise ExportValidationError(f"Alibaba selected baseline {run_record['selected_baseline_policy']} is not the Hybrid safeguard")

    return {
        GOOGLE: {
            "min_runs": google["baseline_min_runs"],
            "selected_baseline_policy": google["selected_baseline_policy"],
            "hybrid_safeguard_policy": "P95",
            "hybrid_rule": google["hybrid_rule"],
            "hybrid_fallback": google["hybrid_fallback"],
            "ml_models": google["ml_selected_models"],
            "source": GOOGLE_DECISION_MANIFEST,
        },
        ALIBABA: {
            "min_runs": run_record["selected_min_runs"],
            "selected_baseline_policy": run_record["selected_baseline_policy"],
            "hybrid_safeguard_policy": run_record["selected_baseline_policy"],
            "hybrid_rule": alibaba_ml["hybrid_rule"],
            "hybrid_fallback": "ML prediction where the safeguard is unavailable",
            "ml_models": run_record["selected_models"],
            "source": f"{ALIBABA_RUN_RECORD}, {ALIBABA_ML_DECISION_MANIFEST}",
        },
    }


def build_dataset_info(dataset_id: str, recommendations: pd.DataFrame, workloads: pd.DataFrame) -> dict:
    spec = DATASETS[dataset_id]
    runs = recommendations[recommendations["policy"] == POLICY_NAMES[0]]
    return {
        "dataset_id": dataset_id,
        "display_name": spec.display_name,
        "resources": {
            resource: {"unit": r.unit, "semantics": r.semantics, "description": r.description}
            for resource, r in (("cpu", spec.cpu), ("memory", spec.memory))
        },
        "primary_resource": spec.primary_resource,
        "evaluation_scope": "One-time final test: each test run's recommendation is compared with the next run of the same workload.",
        "population": {
            "test_runs": int(len(runs)),
            "workloads": int(len(workloads)),
            "scored_runs_cpu": int(runs["cpu_target_status"].eq("available").sum()),
            "scored_runs_memory": int(runs["memory_target_status"].eq("available").sum()),
            "workloads_with_history_latest": int(workloads["latest_uses_history"].sum()),
        },
        "caveats": [*DATASET_CAVEATS[dataset_id], COMMON_CAVEAT],
    }


def build_risk_levels(config_path: Path = DEFAULT_RISK_LEVEL_CONFIG) -> dict:
    """The validated risk-level configuration with policy IDs added."""
    config = load_risk_level_config(config_path)
    return {
        "default_risk_level": config.default_risk_level,
        "risk_levels": [
            {"risk_level": level.risk_level, "label": level.label, "description": level.description}
            for level in config.risk_levels
        ],
        "datasets": {
            dataset_id: {level: {"policy": policy, "policy_id": POLICY_IDS[policy]} for level, policy in mapping.items()}
            for dataset_id, mapping in config.datasets.items()
        },
    }


def build_metadata(
    reference: SourceReference,
    mismatches: list[Mismatch],
    status: str,
    input_checksums: dict,
    check_files: dict,
    export: DatasetExport,
    workloads: pd.DataFrame,
    fallback_counts: dict,
) -> dict:
    """Per-dataset provenance; the export commit and timestamp are added by the command-line script."""
    return {
        "dataset_id": reference.dataset_id,
        "bundle_status": status,
        "source_mismatches": [vars(mismatch) for mismatch in mismatches],
        "reference_files": list(reference.reference_files),
        "source_run_id": reference.run_id,
        "decision_manifest_sha256": reference.decision_manifest_sha256,
        "inputs": input_checksums,
        "check_files": check_files,
        "row_counts": {
            "recommendations": int(len(export.recommendations)),
            "workloads": int(len(workloads)),
            "test_runs": int(len(export.recommendations) // len(POLICY_NAMES)),
        },
        "latest_run_fallback_counts": fallback_counts,
        "notes": export.notes,
    }


# --- Building and writing the bundle ---------------------------------------------

GOOGLE_DATA = "data/processed/google_subset_v1"
ALIBABA_FINAL_TEST_SUMMARY = "data/processed/alibaba_gpu_v2020_final_test/final_test_policy_comparison.csv"
# zstd keeps the full bundle near 13 MB (22 MB with the default snappy), under the 20 MB commit limit.
PARQUET_COMPRESSION = "zstd"
# Folders the bundle must never be written into.
INPUT_FOLDERS = (
    GOOGLE_DATA,
    "data/processed/alibaba_gpu_v2020_final_test",
    "data/processed/alibaba_gpu_v2020_targets",
    "data/processed/alibaba_gpu_v2020_baselines",
    "reports/results/google_subset",
    "reports/results/alibaba_gpu_2020",
)


@dataclass
class DatasetBundle:
    dataset_info: dict
    policy_metrics: dict
    workloads: pd.DataFrame
    recommendations: pd.DataFrame
    metadata: dict


@dataclass
class BundleContents:
    manifest: dict
    risk_levels: dict
    rules: dict
    datasets: dict[str, DatasetBundle]


def _input_checksums(reference: SourceReference, mismatches: list[Mismatch]) -> dict:
    found = {m.path: m.found for m in mismatches if m.reason in ("missing", "checksum")}
    return {item.path: {"expected_sha256": item.sha256, "sha256": found.get(item.path, item.sha256)} for item in reference.inputs}


def _assemble(
    reference, mismatches, status, export, repo, summary_csv, check_files, source_counts, safeguard, default_policy
) -> DatasetBundle:
    dataset_id = reference.dataset_id
    workloads = build_workloads(export.recommendations, dataset_id, default_policy)
    fallback_counts = bundle_fallback_counts(export.recommendations)
    check_fallback_counts(fallback_counts, source_counts, safeguard, export.notes["hybrid_safeguard_missing"])
    metadata = build_metadata(
        reference, mismatches, status, _input_checksums(reference, mismatches), check_files, export, workloads, fallback_counts
    )
    return DatasetBundle(
        dataset_info=build_dataset_info(dataset_id, export.recommendations, workloads),
        policy_metrics=build_policy_metrics(repo, summary_csv, dataset_id),
        workloads=workloads,
        recommendations=export.recommendations,
        metadata=metadata,
    )


def build_bundle(repo: Path, allow_unverified_source: bool, export_info: dict) -> BundleContents:
    """Verify sources, export both datasets and build every bundle file in memory."""
    repo = Path(repo)
    risk_levels = build_risk_levels()
    rules = build_rules(repo)
    datasets = {}

    reference, mismatches = verify_dataset_sources(GOOGLE, repo)
    status = source_status(mismatches, allow_unverified_source)
    occurrences = pd.read_parquet(repo / GOOGLE_INPUTS[0])
    google = export_google(
        occurrences, pd.read_parquet(repo / GOOGLE_INPUTS[1]), pd.read_parquet(repo / GOOGLE_ROW_LEVEL),
        pd.read_csv(repo / GOOGLE_SUMMARY_CSV),
    )
    datasets[GOOGLE] = _assemble(
        reference, mismatches, status, google, repo, GOOGLE_SUMMARY_CSV,
        {GOOGLE_ROW_LEVEL: file_sha256(repo / GOOGLE_ROW_LEVEL)},
        google_source_fallback_counts(occurrences), "P95", _default_policy(risk_levels, GOOGLE),
    )

    reference, mismatches = verify_dataset_sources(ALIBABA, repo)
    status = source_status(mismatches, allow_unverified_source)
    targets = pd.read_parquet(repo / ALIBABA_INPUTS[2])
    baselines = pd.read_parquet(repo / ALIBABA_INPUTS[3])
    alibaba = export_alibaba(
        pd.read_parquet(repo / ALIBABA_INPUTS[0]), targets, baselines, pd.read_csv(repo / ALIBABA_FINAL_TEST_SUMMARY)
    )
    datasets[ALIBABA] = _assemble(
        reference, mismatches, status, alibaba, repo, ALIBABA_SUMMARY_CSV,
        {ALIBABA_FINAL_TEST_SUMMARY: file_sha256(repo / ALIBABA_FINAL_TEST_SUMMARY)},
        alibaba_source_fallback_counts(targets, baselines), "P99", _default_policy(risk_levels, ALIBABA),
    )

    return BundleContents(
        manifest=build_manifest(datasets, export_info), risk_levels=risk_levels, rules=rules, datasets=datasets
    )


def _default_policy(risk_levels: dict, dataset_id: str) -> str:
    return risk_levels["datasets"][dataset_id][risk_levels["default_risk_level"]]["policy"]


def build_manifest(datasets: dict[str, DatasetBundle], export_info: dict) -> dict:
    statuses = {dataset_id: bundle.metadata["bundle_status"] for dataset_id, bundle in datasets.items()}
    return {
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
        "bundle_status": "verified" if all(s == "verified" for s in statuses.values()) else "development",
        "datasets": {
            dataset_id: {"bundle_status": status, "source_run_id": datasets[dataset_id].metadata["source_run_id"]}
            for dataset_id, status in statuses.items()
        },
        "export": {
            **export_info,
            "python_version": platform.python_version(),
            "pandas_version": pd.__version__,
            "pyarrow_version": pyarrow.__version__,
        },
    }


def _bundle_files(contents: BundleContents) -> dict[str, object]:
    """Relative path -> dict (written as JSON) or DataFrame (written as Parquet)."""
    files = {"manifest.json": contents.manifest, "risk_levels.json": contents.risk_levels, "rules.json": contents.rules}
    for dataset_id, bundle in contents.datasets.items():
        files[f"{dataset_id}/dataset.json"] = bundle.dataset_info
        files[f"{dataset_id}/policy_metrics.json"] = bundle.policy_metrics
        files[f"{dataset_id}/workloads.parquet"] = bundle.workloads
        files[f"{dataset_id}/recommendations.parquet"] = bundle.recommendations
        files[f"{dataset_id}/metadata.json"] = bundle.metadata
    return files


def _write_and_check(path: Path, content) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, pd.DataFrame):
        content.to_parquet(path, index=False, compression=PARQUET_COMPRESSION)
        pd.testing.assert_frame_equal(pd.read_parquet(path), content, check_exact=True)
    else:
        path.write_text(json.dumps(content, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        if json.loads(path.read_text(encoding="utf-8")) != content:
            raise ExportValidationError(f"{path.name} did not read back as written")


def write_bundle(contents: BundleContents, out_dir: Path, force: bool = False) -> str:
    """Write through a staging folder next to out_dir, check it, then move it into place.

    Returns the bundle checksum. On any failure nothing is left behind and an
    existing bundle is kept.
    """
    out_dir = Path(out_dir)
    if out_dir.exists() and not force:
        raise FileExistsError(f"{out_dir} already exists")
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = out_dir.parent / f".{out_dir.name}.staging-{uuid4().hex}"
    previous = out_dir.parent / f".{out_dir.name}.previous-{uuid4().hex}"
    try:
        staging.mkdir()
        for relative, content in _bundle_files(contents).items():
            _write_and_check(staging / relative, content)
        write_checksums(staging)
        checksum = verify_bundle(staging)

        if out_dir.exists():
            out_dir.rename(previous)
        try:
            staging.rename(out_dir)
        except OSError:
            if previous.exists():
                previous.rename(out_dir)
            raise
        if previous.exists():
            shutil.rmtree(previous)
        return checksum
    finally:
        if staging.exists():
            shutil.rmtree(staging)
