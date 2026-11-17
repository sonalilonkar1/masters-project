"""Build the UI bundle from the agreed pipeline outputs (Task 15 Part B).

This module holds the export logic as small functions; the command-line entry
point is ``scripts/export_ui_artifacts.py``.

Source verification: the export reads only inputs whose SHA-256 equals the
value recorded in the reference files committed on ``main``. It never decides
which run is authoritative; ``main`` does. Reference values are read from the
committed files at export time, so a future agreed run needs no code change.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.policies.hybrid import hybrid_recommendation
from src.service.contract import (
    ALIBABA,
    GOOGLE,
    POLICY_NAMES,
    RECOMMENDATION_COLUMNS,
    validate_frame,
)

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


def _attach_exceeded(recommendations: pd.DataFrame, row_level: pd.DataFrame) -> pd.DataFrame:
    """Copy the stored violation flags; check every scored recommendation equals the stored one."""
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
        merged[f"{resource}_exceeded"] = merged[f"{resource}_violation"].map({1.0: True, 0.0: False}).astype("boolean")
    return merged


def export_google(occurrences: pd.DataFrame, ml_predictions: pd.DataFrame, row_level: pd.DataFrame) -> DatasetExport:
    """Google recommendations in the bundle format: one row per test occurrence and policy."""
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

    recommendations = _attach_exceeded(recommendations, row_level)
    recommendations = recommendations[[spec.name for spec in RECOMMENDATION_COLUMNS]].astype(
        {spec.name: "string" for spec in RECOMMENDATION_COLUMNS if spec.dtype == "string"}
    )
    validate_frame(recommendations, RECOMMENDATION_COLUMNS, f"{GOOGLE} recommendations")

    latest = recommendations[recommendations["is_latest"] & (recommendations["policy"] == "Request")]
    if latest["workload_id"].nunique() != frame["recurrence_key"].nunique() or latest["workload_id"].duplicated().any():
        raise ExportValidationError("Google: expected exactly one latest run per workload")

    notes = {
        "hybrid_safeguard": "P95",
        "hybrid_safeguard_missing": hybrid_safeguard_missing,
        "target_occurrence_id": "next run of the same workload by start time, checked against the stored target start time and peak",
    }
    return DatasetExport(recommendations=recommendations, notes=notes)
