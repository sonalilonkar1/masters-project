#!/usr/bin/env python3
"""Export the recommendation UI bundle (Task 15).

Reads the agreed Google and Alibaba final-test outputs, checks them against
the checksums committed on main, and writes a checksummed bundle for the
read-only API:

    python3 scripts/export_ui_artifacts.py                              # verified bundle -> reports/results/ui/
    python3 scripts/export_ui_artifacts.py --allow-unverified-source    # development bundle -> data/processed/ui_dev/

A development bundle may use inputs that differ from main (for example older
local copies). It lists every mismatch, may not be written inside reports/,
and must never be used for screenshots or report figures.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT, REPO_ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.build_alibaba_gpu_2020_canonical import git_state  # noqa: E402
from src.service.export import (  # noqa: E402
    INPUT_FOLDERS,
    ExportValidationError,
    SourceVerificationError,
    build_bundle,
    write_bundle,
)

EXIT_OK, EXIT_INVALID, EXIT_REFUSED, EXIT_FAILED = 0, 1, 2, 3
DEFAULT_OUT_DIR = Path("reports/results/ui")
DEFAULT_DEV_OUT_DIR = Path("data/processed/ui_dev")


def _inside(path: Path, folder: Path) -> bool:
    return path == folder or folder in path.parents


def run_export(
    out_dir: Path | None = None,
    *,
    allow_dirty: bool = False,
    force: bool = False,
    allow_unverified_source: bool = False,
    repo: Path = REPO_ROOT,
    builder=build_bundle,
    git=git_state,
) -> int:
    repo = Path(repo).resolve()
    default = DEFAULT_DEV_OUT_DIR if allow_unverified_source else DEFAULT_OUT_DIR
    requested_out = Path(out_dir) if out_dir is not None else repo / default
    out = requested_out.resolve()

    if requested_out.is_symlink():
        print("REFUSED: output path must not be a symlink")
        return EXIT_REFUSED
    if any(_inside(out, (repo / folder).resolve()) for folder in INPUT_FOLDERS):
        print("REFUSED: output must be separate from all inputs")
        return EXIT_REFUSED
    if allow_unverified_source and _inside(out, (repo / "reports").resolve()):
        print("REFUSED: a development bundle may not be written inside reports/; use data/processed/ui_dev/")
        return EXIT_REFUSED
    if out.exists() and not force:
        print(f"REFUSED: {out} already exists; use --force to replace it")
        return EXIT_REFUSED

    commit, dirty = git(repo)
    if (commit is None or dirty) and not allow_dirty:
        print("REFUSED: code must be in a clean Git checkout; use --allow-dirty only for local review")
        return EXIT_REFUSED

    started = time.monotonic()
    export_info = {
        "code_commit": commit,
        "code_dirty": dirty,
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        contents = builder(repo, allow_unverified_source, export_info)
    except SourceVerificationError as error:
        print(f"REFUSED: {error}")
        return EXIT_REFUSED
    except ExportValidationError as error:
        print(f"EXPORT FAILED: {error}")
        return EXIT_FAILED

    try:
        checksum = write_bundle(contents, out, force=force)
    except Exception as error:
        print(f"EXPORT FAILED: {type(error).__name__}: {error}")
        return EXIT_FAILED

    print(f"Wrote {out} in {time.monotonic() - started:.1f} s")
    print(f"Bundle status: {contents.manifest['bundle_status']}")
    for dataset_id, bundle in contents.datasets.items():
        metadata = bundle.metadata
        print(
            f"  {dataset_id}: {metadata['bundle_status']}, {metadata['row_counts']['workloads']} workloads, "
            f"{metadata['row_counts']['recommendations']} recommendations, "
            f"{len(metadata['source_mismatches'])} source mismatches"
        )
    print(f"Bundle checksum (SHA256SUMS): {checksum}")
    if contents.manifest["bundle_status"] == "development":
        print("WARNING: development bundle; do not commit it or use it for screenshots or report figures")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", type=Path, default=None, help=f"default {DEFAULT_OUT_DIR} ({DEFAULT_DEV_OUT_DIR} in development)")
    parser.add_argument("--allow-dirty", action="store_true", help="allow uncommitted code (local review only)")
    parser.add_argument("--force", action="store_true", help="replace an existing output folder")
    parser.add_argument(
        "--allow-unverified-source",
        action="store_true",
        help="development only: allow inputs that differ from the checksums on main",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as stop:  # argparse exits with 2, which would read as "refused"
        return EXIT_OK if stop.code == 0 else EXIT_INVALID
    return run_export(
        args.out_dir,
        allow_dirty=args.allow_dirty,
        force=args.force,
        allow_unverified_source=args.allow_unverified_source,
    )


if __name__ == "__main__":
    sys.exit(main())
