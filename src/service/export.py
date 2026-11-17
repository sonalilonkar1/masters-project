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

from src.service.contract import ALIBABA, GOOGLE

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
