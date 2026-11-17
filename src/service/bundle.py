"""Read and check the UI bundle (Task 15 Part C).

``SHA256SUMS`` lists every bundle file except itself, in the format written by
``sha256sum``. A bundle is usable only when every listed file exists with its
recorded checksum and no unlisted file is present.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.service.contract import (
    BUNDLE_SCHEMA_VERSION,
    BUNDLE_STATUSES,
    DATASET_IDS,
    RECOMMENDATION_COLUMNS,
    WORKLOAD_COLUMNS,
    BundleContractError,
    validate_frame,
)

CHECKSUM_FILE = "SHA256SUMS"


class BundleIntegrityError(RuntimeError):
    """A bundle file is missing, changed or not listed in SHA256SUMS."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 24), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bundle_files(bundle_dir: Path) -> list[str]:
    """Every file in the bundle except SHA256SUMS, as sorted POSIX paths relative to the bundle."""
    bundle_dir = Path(bundle_dir)
    return sorted(
        path.relative_to(bundle_dir).as_posix()
        for path in bundle_dir.rglob("*")
        if path.is_file() and path.relative_to(bundle_dir).as_posix() != CHECKSUM_FILE
    )


def write_checksums(bundle_dir: Path) -> str:
    """Write SHA256SUMS for every bundle file; return the checksum of SHA256SUMS itself."""
    bundle_dir = Path(bundle_dir)
    lines = "".join(f"{_sha256(bundle_dir / name)}  {name}\n" for name in bundle_files(bundle_dir))
    (bundle_dir / CHECKSUM_FILE).write_text(lines, encoding="utf-8")
    return _sha256(bundle_dir / CHECKSUM_FILE)


def read_checksums(bundle_dir: Path) -> dict[str, str]:
    path = Path(bundle_dir) / CHECKSUM_FILE
    if not path.is_file():
        raise BundleIntegrityError(f"{path} is missing")
    recorded = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        digest, separator, name = line.partition("  ")
        if not separator or len(digest) != 64 or not name or name in recorded:
            raise BundleIntegrityError(f"{path}:{number}: malformed or duplicate line")
        recorded[name] = digest
    return recorded


def verify_bundle(bundle_dir: Path) -> str:
    """Check every file against SHA256SUMS; return the checksum of SHA256SUMS (the bundle checksum)."""
    bundle_dir = Path(bundle_dir)
    recorded = read_checksums(bundle_dir)
    present = set(bundle_files(bundle_dir))

    problems = [f"missing: {name}" for name in sorted(set(recorded) - present)]
    problems += [f"not listed in {CHECKSUM_FILE}: {name}" for name in sorted(present - set(recorded))]
    problems += [
        f"changed: {name}"
        for name in sorted(set(recorded) & present)
        if _sha256(bundle_dir / name) != recorded[name]
    ]
    if problems:
        raise BundleIntegrityError(f"{bundle_dir}: " + "; ".join(problems))
    return _sha256(bundle_dir / CHECKSUM_FILE)


# --- Loading ---------------------------------------------------------------------


@dataclass(frozen=True)
class LoadedDataset:
    info: dict
    policy_metrics: dict
    metadata: dict
    workloads: pd.DataFrame  # indexed by workload_id
    recommendations: pd.DataFrame
    # (workload_id, policy) -> row positions in recommendations, ordered by start time
    positions: dict


@dataclass(frozen=True)
class LoadedBundle:
    path: Path
    checksum: str
    manifest: dict
    risk_levels: dict
    rules: dict
    datasets: dict  # dataset_id -> LoadedDataset

    def rows(self, dataset_id: str, workload_id: str, policy: str) -> pd.DataFrame:
        """All test runs of one workload under one policy, oldest first (empty if unknown)."""
        dataset = self.datasets[dataset_id]
        positions = dataset.positions.get((workload_id, policy))
        if positions is None:
            return dataset.recommendations.iloc[0:0]
        return dataset.recommendations.iloc[positions]


def _read_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _load_dataset(dataset_dir: Path, dataset_id: str) -> LoadedDataset:
    workloads = pd.read_parquet(dataset_dir / "workloads.parquet")
    recommendations = pd.read_parquet(dataset_dir / "recommendations.parquet")
    try:
        validate_frame(workloads, WORKLOAD_COLUMNS, f"{dataset_id} workloads")
        validate_frame(recommendations, RECOMMENDATION_COLUMNS, f"{dataset_id} recommendations")
    except BundleContractError as error:
        raise BundleIntegrityError(str(error)) from error

    info = _read_json(dataset_dir / "dataset.json")
    if info.get("dataset_id") != dataset_id:
        raise BundleIntegrityError(f"{dataset_dir / 'dataset.json'} describes {info.get('dataset_id')!r}")
    grouped = recommendations.groupby(["workload_id", "policy"], sort=False).indices
    positions = {key: np.sort(index) for key, index in grouped.items()}
    return LoadedDataset(
        info=info,
        policy_metrics=_read_json(dataset_dir / "policy_metrics.json"),
        metadata=_read_json(dataset_dir / "metadata.json"),
        workloads=workloads.set_index("workload_id", drop=False).rename_axis(None),
        recommendations=recommendations,
        positions=positions,
    )


def load_bundle(bundle_dir: Path) -> LoadedBundle:
    """Verify checksums and the bundle format, then load every dataset once."""
    bundle_dir = Path(bundle_dir)
    if not bundle_dir.is_dir():
        raise BundleIntegrityError(f"bundle folder not found: {bundle_dir}")
    checksum = verify_bundle(bundle_dir)
    manifest = _read_json(bundle_dir / "manifest.json")
    if manifest.get("bundle_schema_version") != BUNDLE_SCHEMA_VERSION:
        raise BundleIntegrityError(
            f"bundle schema {manifest.get('bundle_schema_version')!r}, this code reads {BUNDLE_SCHEMA_VERSION!r}"
        )
    if manifest.get("bundle_status") not in BUNDLE_STATUSES:
        raise BundleIntegrityError(f"unknown bundle status {manifest.get('bundle_status')!r}")
    if set(manifest.get("datasets", {})) != set(DATASET_IDS):
        raise BundleIntegrityError(f"bundle datasets {sorted(manifest.get('datasets', {}))}, expected {list(DATASET_IDS)}")

    return LoadedBundle(
        path=bundle_dir,
        checksum=checksum,
        manifest=manifest,
        risk_levels=_read_json(bundle_dir / "risk_levels.json"),
        rules=_read_json(bundle_dir / "rules.json"),
        datasets={dataset_id: _load_dataset(bundle_dir / dataset_id, dataset_id) for dataset_id in DATASET_IDS},
    )
