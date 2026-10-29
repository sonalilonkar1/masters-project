#!/usr/bin/env python3
"""Build reproducible Task 4 tables from the existing, verified Task 3 output.

Run locally after pulling main (no raw-data rebuild or shared target download):
    python3 scripts/build_alibaba_gpu_2020_targets.py
    python3 scripts/build_alibaba_gpu_2020_targets.py --force

Outputs: train.parquet, validation.parquet, test.parquet, metadata.json,
SHA256SUMS in data/processed/alibaba_gpu_v2020_targets/. Byte-identical Parquet
requires matching pandas/pyarrow versions; otherwise compare metadata/counts.
Exit codes: 0 success, 1 invalid canonical input, 2 refused, 3 build/write failure.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT, REPO_ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pandas as pd

from scripts import build_alibaba_gpu_2020_canonical as canonical
from canonical.schema import ALIBABA_GPU_2020_CAPABILITIES
from features.target_builder import build_targets, write_target_tables


DEFAULT_CANONICAL_DIR = canonical.DEFAULT_OUT_DIR
DEFAULT_OUT_DIR = REPO_ROOT / "data/processed/alibaba_gpu_v2020_targets"
CHECKED_FILES = ("metadata.json", "test.parquet", "train.parquet", "validation.parquet")
EXIT_OK, EXIT_INVALID, EXIT_REFUSED, EXIT_FAILED = 0, 1, 2, 3


def _publish(staged: Path, out_dir: Path) -> None:
    """Keep previous output until the complete replacement can be installed."""
    previous = None
    if out_dir.exists():
        previous = out_dir.with_name(f".{out_dir.name}.previous-{uuid4().hex}")
        out_dir.rename(previous)
    try:
        staged.rename(out_dir)
    except BaseException:
        if previous is not None:
            previous.rename(out_dir)
        raise
    if previous is not None:
        try:
            shutil.rmtree(previous)
        except OSError as error:
            print(f"WARNING: new output installed; previous copy retained at {previous}: {error}")


def build(canonical_dir: Path = DEFAULT_CANONICAL_DIR,
          out_dir: Path = DEFAULT_OUT_DIR, *, force: bool = False,
          allow_dirty: bool = False, repo: Path = REPO_ROOT) -> int:
    """Verify inputs, build once, and publish a complete checksummed folder.

    --allow-dirty is for local review only. Like Task 3, Git status checks tracked
    files; untracked files are ignored. No time or absolute path enters metadata.
    """
    canonical_dir = Path(canonical_dir).resolve()
    requested_out = Path(out_dir)
    out_dir = requested_out.resolve()
    # A mistaken --force must never replace, add to, or enclose canonical data.
    if (requested_out.is_symlink() or canonical_dir == out_dir
            or canonical_dir in out_dir.parents or out_dir in canonical_dir.parents):
        print("REFUSED: output must be a separate directory, disjoint from canonical input")
        return EXIT_REFUSED
    if out_dir.exists() and (not out_dir.is_dir() or not force):
        print(f"REFUSED: {out_dir} exists; choose another directory or use --force")
        return EXIT_REFUSED
    commit, dirty = canonical.git_state(repo)
    if (commit is None or dirty) and not allow_dirty:
        print("REFUSED: code must be in a clean Git checkout; use --allow-dirty for local review")
        return EXIT_REFUSED

    started = time.monotonic()
    # This is the same verifier used by the Task 3 script's --verify command.
    # It hashes all artifacts and inspects Parquet footers; it does not load
    # instance/rejected records into the target-building pipeline.
    try:
        canonical.verify_output(canonical_dir)
    except (canonical.VerifyError, OSError) as error:
        print(f"VERIFY FAILED: {error}")
        return EXIT_INVALID

    staging = None
    try:
        source_metadata = json.loads((canonical_dir / "metadata.json").read_text())
        roles = pd.read_parquet(canonical_dir / "role_occurrence.parquet")
        result = build_targets(roles, ALIBABA_GPU_2020_CAPABILITIES,
                               verified_source_metadata=source_metadata)
        result.metadata["build"] = canonical.build_info(commit, dirty)
        # Keep the verified artifact identities portable and traceable to Task 3.
        result.metadata["source_artifact"] = {
            "path": "role_occurrence.parquet",
            "sha256": canonical.sha256(canonical_dir / "role_occurrence.parquet"),
            "metadata_sha256": canonical.sha256(canonical_dir / "metadata.json"),
            "manifest_sha256": canonical.sha256(canonical_dir / "SHA256SUMS"),
            "checksum_verified": True,
        }
        out_dir.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.tmp-", dir=out_dir.parent))
        staged_output = staging / "tables"
        metadata = write_target_tables(result, staged_output)
        checksums = {name: canonical.sha256(staged_output / name) for name in sorted(CHECKED_FILES)}
        (staged_output / "SHA256SUMS").write_text(
            "".join(f"{digest}  {name}\n" for name, digest in checksums.items()), encoding="utf-8")
        _publish(staged_output, out_dir)
    except Exception as error:
        print(f"BUILD FAILED: {type(error).__name__}: {error}")
        return EXIT_FAILED
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging)

    print(f"Built {out_dir} in {time.monotonic() - started:.1f} s")
    print(json.dumps({"build": metadata["build"], "per_split": metadata["per_split"],
                     "reference_comparison": metadata["reference_comparison"]}, indent=2, sort_keys=True))
    print(metadata["reference_notes"])
    print("SHA256SUMS:")
    print("".join(f"{digest}  {name}\n" for name, digest in checksums.items()), end="")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--canonical-dir", type=Path, default=DEFAULT_CANONICAL_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--force", action="store_true", help="replace a complete target build after staging succeeds")
    parser.add_argument("--allow-dirty", action="store_true", help="allow an uncommitted local review build")
    args = parser.parse_args(argv)
    return build(args.canonical_dir, args.out_dir, force=args.force, allow_dirty=args.allow_dirty)


if __name__ == "__main__":
    sys.exit(main())
