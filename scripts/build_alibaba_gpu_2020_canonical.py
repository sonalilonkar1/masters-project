#!/usr/bin/env python3
"""Build or verify the Alibaba GPU 2020 canonical output (Task 3, design §5.7).

Usage:
    python3 scripts/build_alibaba_gpu_2020_canonical.py                  # build
    python3 scripts/build_alibaba_gpu_2020_canonical.py --force          # replace an existing build
    python3 scripts/build_alibaba_gpu_2020_canonical.py --verify DIR     # check a downloaded copy

A build verifies the six source tables, runs the adapter and writes six files
(three Parquet files, metadata.json, count_report.md, SHA256SUMS) to a
temporary folder. The folder replaces the output only after every check
passes, so the output is never partial or mixed. The script only calls the
loader, the adapter and the framework; it changes none of them.

Exit codes: 0 success; 1 count mismatch or failed --verify; 2 refused to
start; 3 build failed.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Callable, Mapping, Optional

import pandas as pd
import pyarrow
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.adapters import AlibabaGPU2020Adapter
from src.adapters.alibaba_gpu_2020 import (
    INSTANCE_VIEW_COLUMNS,
    ROLE_VIEW_COLUMNS,
    SOURCE_COLUMNS,
)
from src.sources import alibaba_gpu_2020 as loader


DEFAULT_OUT_DIR = REPO_ROOT / "data" / "processed" / "alibaba_gpu_v2020"

PRIMARY_VIEW = "role_occurrence"
VIEW_FILES = {"role_occurrence": "role_occurrence.parquet", "instance": "instance.parquet"}
REJECTED_FILE = "rejected.parquet"
METADATA_FILE = "metadata.json"
COUNT_REPORT_FILE = "count_report.md"
CHECKSUM_FILE = "SHA256SUMS"
CHECKED_FILES = (*VIEW_FILES.values(), REJECTED_FILE, METADATA_FILE, COUNT_REPORT_FILE)
PARQUET_COLUMNS = {
    VIEW_FILES["role_occurrence"]: list(ROLE_VIEW_COLUMNS),
    VIEW_FILES["instance"]: list(INSTANCE_VIEW_COLUMNS),
}

# The sensor table has no timestamps, so the window comes from the source
# data checks (docs/data/alibaba_gpu_2020_source_data_checks.md).
TELEMETRY_WINDOW = {"description": "About day 19 to day 68.9", "start_day": 19, "end_day": 68.9}

# Verified full-table figures. This is a copy of results doc §1, §5 and §9
# (docs/data/alibaba_gpu_2020_adapter_results.md): a code change that moves a
# count must update both in the same commit.
EXPECTED_COUNTS = {
    "rows: role_occurrence": 1_254_108,
    "rows: instance": 7_410_783,
    "rows: rejected": 121_824,
    "rejected: job": 3_663,
    "rejected: role_occurrence": 6_942,
    "rejected: instance": 111_219,
    "exclusion: no_recurrence_key": 1_788,
    "exclusion: job_failed": 282_027,
    "exclusion: job_incomplete": 87_980,
    "exclusion: task_not_terminated": 0,
    "exclusion: missing_or_invalid_request": 2,
    "exclusion: instance_failed": 33_022,
    "exclusion: instance_interrupted": 31,
    "exclusion: instance_incomplete": 0,
    "exclusion: missing_worker_name": 0,
    "exclusion: multi_attempt_worker": 2_048,
    "exclusion: missing_sensor": 287_780,
    "exclusion: partial_sensor_coverage": 97_018,
    "exclusion: invalid_memory_exceeds_capacity": 512,
    "exclusion: invalid_resource": 0,
    "exclusion: <null>": 461_900,
    "eligibility: accepted_roles": 1_254_108,
    "eligibility: pass_all_but_multi_attempt_worker": 462_156,
    "eligibility: eligible": 461_900,
    "eligibility: eligible_missing_cpu": 1_224,
}

# Rejection level -> source table it reconciles against. Accepted jobs are the
# distinct job_name values in the role view; roles and instances are view rows.
RECONCILIATION_SOURCES = {
    "job": "pai_job_table",
    "role_occurrence": "pai_task_table",
    "instance": "pai_instance_table",
}

EXIT_OK, EXIT_MISMATCH, EXIT_REFUSED, EXIT_FAILED = 0, 1, 2, 3
CHECKSUM_LINE = re.compile(r"^([0-9a-f]{64})  ([^/\\\s]+)$")


class VerifyError(Exception):
    """An output folder does not match its manifest or metadata."""


# --- sources and adapter ------------------------------------------------------

def load_sources(raw_dir: Optional[Path] = None) -> tuple[dict, dict]:
    """Verify the six tables, then load only the columns the adapter reads."""
    provenance = loader.source_provenance(raw_dir=raw_dir)
    provenance["telemetry_window"] = dict(TELEMETRY_WINDOW)
    # The loader always adds source_row_number, so it is not requested.
    sources = {
        table: loader.load_table(
            table,
            columns=[c for c in SOURCE_COLUMNS[table] if c != loader.SOURCE_ROW_NUMBER],
            raw_dir=raw_dir,
            verify=False,
        )
        for table in SOURCE_COLUMNS
    }
    return sources, provenance


def run_adapter(sources_loader: Callable[[], tuple[dict, dict]]):
    # The sources go out of scope when this returns, so only the result stays in memory.
    sources, provenance = sources_loader()
    return AlibabaGPU2020Adapter().adapt_sources(
        sources, primary_view=PRIMARY_VIEW, provenance=provenance
    )


# --- build information ----------------------------------------------------------

def git_state(repo: Path) -> tuple[Optional[str], Optional[bool]]:
    """(commit, dirty); (None, None) outside a Git checkout. Untracked files are ignored."""
    def git(*args):
        return subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
        ).stdout.strip()

    try:
        commit = git("rev-parse", "HEAD")
        dirty = bool(git("status", "--porcelain", "--untracked-files=no"))
    except (OSError, subprocess.CalledProcessError):
        return None, None
    return commit, dirty


def build_info(commit: Optional[str], dirty: Optional[bool]) -> dict:
    return {
        "code_commit": commit,
        "code_dirty": dirty,
        "python_version": platform.python_version(),
        "pandas_version": pd.__version__,
        "pyarrow_version": pyarrow.__version__,
    }


# --- expected counts and count report ----------------------------------------------

def headline_counts(metadata: Mapping) -> dict:
    """The metadata values that EXPECTED_COUNTS describes, under the same labels."""
    counts = {f"rows: {view}": n for view, n in metadata.get("canonical_row_counts", {}).items()}
    counts["rows: rejected"] = metadata.get("rejection_count")
    counts.update({f"rejected: {level}": sum(reasons.values())
                   for level, reasons in metadata.get("rejection_counts", {}).items()})
    counts.update({f"exclusion: {k}": n for k, n in metadata.get("exclusion_reason_counts", {}).items()})
    counts.update({f"eligibility: {k}": n for k, n in metadata.get("eligibility_summary", {}).items()})
    return counts


def compare_counts(metadata: Mapping, expected: Mapping[str, int]) -> list[tuple]:
    """(label, expected, actual, difference) for every expected figure; difference None if missing."""
    actual = headline_counts(metadata)
    rows = []
    for label, value in expected.items():
        got = actual.get(label)
        rows.append((label, value, got, None if got is None else got - value))
    return rows


def reconciliation(metadata: Mapping, accepted_jobs: int) -> dict:
    """source = accepted + rejected at each level (issue #79); difference is source - accepted - rejected."""
    accepted = {"job": accepted_jobs, **metadata["canonical_row_counts"]}
    levels = {}
    for level, table in RECONCILIATION_SOURCES.items():
        source = metadata["source_row_counts"][table]
        rejected = sum(metadata.get("rejection_counts", {}).get(level, {}).values())
        levels[level] = {"source_table": table, "source": source, "accepted": accepted[level],
                         "rejected": rejected, "difference": source - accepted[level] - rejected}
    return levels


def unreconciled(metadata: Mapping) -> list[str]:
    """Levels whose difference is not zero."""
    return [level for level, v in metadata.get("reconciliation", {}).items() if v["difference"] != 0]


def _table(header: list[str], rows: list[list]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    return lines + [""]


def _cell(value) -> str:
    if value is None:
        return "—"
    return f"{value:,}" if isinstance(value, int) and not isinstance(value, bool) else str(value)


def count_report(metadata: Mapping, comparison: Optional[list[tuple]]) -> str:
    """Markdown summary of metadata.json. No timestamps, so the file is deterministic."""
    lines = ["# Alibaba GPU 2020 canonical build: count report", ""]
    build = metadata.get("build", {})
    lines += [f"Code commit: `{build.get('code_commit')}` (dirty: {build.get('code_dirty')})", ""]

    lines += ["## Rows", ""]
    rows = [[view, n] for view, n in metadata["canonical_row_counts"].items()]
    rows.append(["rejected", metadata["rejection_count"]])
    lines += _table(["Output", "Rows"], rows)
    rejected = [
        [level, reason, n]
        for level, reasons in metadata.get("rejection_counts", {}).items()
        for reason, n in reasons.items()
    ]
    lines += _table(["Rejected level", "Reason", "Rows"], rejected)

    lines += ["## Reconciliation (source = accepted + rejected)", ""]
    lines += _table(["Level", "Source table", "Source", "Accepted", "Rejected", "Difference"],
                    [[level, f"`{v['source_table']}`", v["source"], v["accepted"], v["rejected"],
                      v["difference"]] for level, v in metadata["reconciliation"].items()])
    bad = unreconciled(metadata)
    lines += ["Every level reconciles." if not bad else f"**{len(bad)} level(s) do not reconcile.**", ""]

    lines += ["## Exclusion reasons (role_occurrence, rule order)", ""]
    lines += _table(["`exclusion_reason`", "Roles"],
                    [[f"`{k}`", n] for k, n in metadata["exclusion_reason_counts"].items()])

    lines += ["## Eligibility summary", ""]
    lines += _table(["Field", "Roles"], [[k, n] for k, n in metadata["eligibility_summary"].items()])

    lines += ["## Validity", ""]
    for key, title in (("validity_counts", "Row"), ("cpu_validity_counts", "CPU"),
                       ("memory_validity_counts", "Memory")):
        rows = [[view, status, n] for view, counts in metadata[key].items() for status, n in counts.items()]
        lines += [f"{title} validity:", ""] + _table(["View", "Status", "Rows"], rows)

    lines += ["## Join coverage", ""]
    coverage = metadata.get("join_coverage_counts", {})
    fields = sorted({field for counts in coverage.values() for field in counts})
    lines += _table(["Join", *fields], [[join, *(counts.get(f) for f in fields)] for join, counts in coverage.items()])

    lines += ["## Expected versus actual", ""]
    if comparison is None:
        lines += ["Not compared.", ""]
    else:
        lines += _table(["Figure", "Expected", "Actual", "Difference"], [list(row) for row in comparison])
        bad = sum(1 for row in comparison if row[3] != 0)
        lines += ["All differences are zero." if not bad else f"**{bad} figure(s) differ.**", ""]
    return "\n".join(lines)


# --- writing and verifying ----------------------------------------------------

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def take_frames(result) -> dict:
    """The three output frames by file name. The caller must drop ``result``
    afterwards: it also holds every view (``views`` and ``canonical``)."""
    frames = {VIEW_FILES[view]: result.views[view] for view in VIEW_FILES}
    frames[REJECTED_FILE] = result.rejected
    return frames


def write_outputs(frames: dict, folder: Path, metadata: Mapping, comparison: Optional[list[tuple]]) -> None:
    """Write the six files. ``frames`` must hold the only references to the
    output frames: each is removed from it after writing, so it is freed
    before the next one is written."""
    for name in (*VIEW_FILES.values(), REJECTED_FILE):
        frame = frames.pop(name)
        frame.to_parquet(folder / name, engine="pyarrow", index=False)
        del frame
        gc.collect()
    (folder / METADATA_FILE).write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n")
    (folder / COUNT_REPORT_FILE).write_text(count_report(metadata, comparison))
    lines = [f"{sha256(folder / name)}  {name}\n" for name in sorted(CHECKED_FILES)]
    (folder / CHECKSUM_FILE).write_text("".join(lines))


def _read_manifest(folder: Path, problems: list[str]) -> dict:
    path = folder / CHECKSUM_FILE
    if not path.is_file():
        problems.append(f"{CHECKSUM_FILE} is missing")
        return {}
    manifest = {}
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        match = CHECKSUM_LINE.match(line)
        if not match:
            problems.append(f"{CHECKSUM_FILE} line {number} is not '<sha256>  <file name>'")
        elif match.group(2) in manifest:
            problems.append(f"{CHECKSUM_FILE} lists {match.group(2)} twice")
        else:
            manifest[match.group(2)] = match.group(1)
    return manifest


def verify_output(folder: Path) -> dict:
    """Check a folder against design §5.7. Returns the Parquet row counts; raises VerifyError."""
    folder = Path(folder)
    if not folder.is_dir():
        raise VerifyError(f"{folder} is not a folder")
    problems: list[str] = []
    manifest = _read_manifest(folder, problems)

    # Checked whenever the manifest exists, so an empty one cannot skip the hashes.
    if (folder / CHECKSUM_FILE).is_file() and set(manifest) != set(CHECKED_FILES):
        missing = sorted(set(CHECKED_FILES) - set(manifest))
        extra = sorted(set(manifest) - set(CHECKED_FILES))
        problems.append(f"{CHECKSUM_FILE} must list exactly {sorted(CHECKED_FILES)}"
                        f" (missing {missing}, unexpected {extra})")
    for name in sorted(CHECKED_FILES):
        path = folder / name
        if not path.is_file():
            problems.append(f"{name} is missing")
        elif name in manifest and sha256(path) != manifest[name]:
            problems.append(f"{name} does not match its SHA-256 in {CHECKSUM_FILE}")
    allowed = {*CHECKED_FILES, CHECKSUM_FILE}
    for entry in sorted(folder.iterdir()):
        if entry.name not in allowed or not entry.is_file():
            problems.append(f"unexpected entry {entry.name} (download into an empty folder)")

    rows = {}
    expected_rows = {}
    try:
        metadata = json.loads((folder / METADATA_FILE).read_text())
        expected_rows = {VIEW_FILES[v]: metadata["canonical_row_counts"][v] for v in VIEW_FILES}
        expected_rows[REJECTED_FILE] = metadata["rejection_count"]
    except FileNotFoundError:
        pass  # already reported as missing
    except (ValueError, KeyError, TypeError) as error:
        problems.append(f"{METADATA_FILE} is not valid or lacks row counts ({error!r})")

    for name in (*VIEW_FILES.values(), REJECTED_FILE):
        path = folder / name
        if not path.is_file():
            continue
        try:
            parquet = pq.ParquetFile(path)
        except Exception as error:
            problems.append(f"{name} is not a readable Parquet file ({error})")
            continue
        rows[name] = parquet.metadata.num_rows
        if name in expected_rows and rows[name] != expected_rows[name]:
            problems.append(f"{name} has {rows[name]:,} rows; {METADATA_FILE} says {expected_rows[name]:,}")
        if name in PARQUET_COLUMNS and parquet.schema_arrow.names != PARQUET_COLUMNS[name]:
            problems.append(f"{name} columns differ from the output contract")

    if problems:
        raise VerifyError("\n".join(problems))
    return rows


# --- publishing ---------------------------------------------------------------

def _sibling(out_dir: Path, kind: str) -> Path:
    return out_dir.with_name(f".{out_dir.name}.{kind}-{os.getpid()}")


def stale_folders(out_dir: Path) -> list[Path]:
    if not out_dir.parent.is_dir():
        return []
    return sorted(out_dir.parent.glob(f".{out_dir.name}.tmp-*")) + sorted(
        out_dir.parent.glob(f".{out_dir.name}.previous-*")
    )


def publish(folder: Path, out_dir: Path) -> None:
    """Install folder as out_dir with two renames; the previous output is kept until then."""
    previous = None
    if out_dir.exists():
        previous = _sibling(out_dir, "previous")
        os.rename(out_dir, previous)
    try:
        os.rename(folder, out_dir)
    except BaseException:
        if previous is not None:
            os.rename(previous, out_dir)
        raise
    if previous is not None:
        try:
            shutil.rmtree(previous)
        except OSError as error:
            # The new output is installed; only the old copy is left behind.
            print(f"WARNING: could not delete the previous output {previous}: {error}")


# --- build --------------------------------------------------------------------

def build(
    out_dir: Path = DEFAULT_OUT_DIR,
    *,
    force: bool = False,
    allow_dirty: bool = False,
    keep_failed_output: bool = False,
    raw_dir: Optional[Path] = None,
    sources_loader: Optional[Callable[[], tuple[dict, dict]]] = None,
    expected: Optional[Mapping[str, int]] = EXPECTED_COUNTS,
    repo: Path = REPO_ROOT,
) -> int:
    """Build the output folder; returns the exit code. expected=None skips the count check (fixtures)."""
    out_dir = Path(out_dir)
    started = time.monotonic()

    # 1. Pre-checks: nothing is loaded or written if one fails.
    for stale in stale_folders(out_dir):
        print(f"WARNING: stale folder from an earlier run, not deleted: {stale}")
    if out_dir.exists() and (not out_dir.is_dir() or any(out_dir.iterdir())) and not force:
        print(f"REFUSED: {out_dir} exists and is not empty; use --force to replace it.")
        return EXIT_REFUSED
    commit, dirty = git_state(repo)
    if (commit is None or dirty) and not allow_dirty:
        reason = "is not a Git checkout" if commit is None else "has uncommitted changes to tracked files"
        print(f"REFUSED: the code tree {reason}; commit first, or use --allow-dirty for a local build.")
        return EXIT_REFUSED

    folder = None
    published = False
    try:
        # 2–3. Sources and adapter.
        result = run_adapter(sources_loader or (lambda: load_sources(raw_dir)))
        metadata = {**result.metadata, "build": build_info(commit, dirty)}
        comparison = None if expected is None else compare_counts(metadata, expected)
        # Keep only the three frames, so each can be freed once it is written.
        frames = take_frames(result)
        del result
        gc.collect()
        accepted_jobs = int(frames[VIEW_FILES["role_occurrence"]]["job_name"].nunique())
        metadata["reconciliation"] = reconciliation(metadata, accepted_jobs)

        # 4–5. Write to a temporary folder, then check it.
        out_dir.parent.mkdir(parents=True, exist_ok=True)
        folder = _sibling(out_dir, "tmp")
        folder.mkdir()
        write_outputs(frames, folder, metadata, comparison)
        rows = verify_output(folder)

        mismatches = [row for row in comparison or [] if row[3] != 0]
        if mismatches:
            print("COUNT MISMATCH: not published.")
            for label, want, got, _ in mismatches:
                print(f"  {label}: expected {_cell(want)}, actual {_cell(got)}")
        # Checked even with expected=None: it needs no reference figures.
        not_reconciled = unreconciled(metadata)
        if not_reconciled:
            print("NOT RECONCILED: not published.")
            for level in not_reconciled:
                v = metadata["reconciliation"][level]
                print(f"  {level}: {v['source_table']} {_cell(v['source'])} != accepted "
                      f"{_cell(v['accepted'])} + rejected {_cell(v['rejected'])}")
        if mismatches or not_reconciled:
            return EXIT_MISMATCH

        # 6. Publish.
        publish(folder, out_dir)
        published = True
    except Exception as error:
        traceback.print_exc()
        print(f"BUILD FAILED: {type(error).__name__}: {error}")
        return EXIT_FAILED
    finally:
        if folder is not None and not published and folder.exists():
            if keep_failed_output:
                print(f"Failed output kept for inspection (not published): {folder}")
            else:
                shutil.rmtree(folder)

    print(f"Built {out_dir}")
    for name, n in rows.items():
        print(f"  {name}: {n:,} rows")
    print(f"  code commit {commit} (dirty: {dirty}); {time.monotonic() - started:.0f} s")
    return EXIT_OK


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="output folder")
    parser.add_argument("--raw-dir", type=Path, default=None, help="source folder (default: the loader's)")
    parser.add_argument("--force", action="store_true", help="replace an existing output folder")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="build from a tree with uncommitted changes or outside Git (local use only)")
    parser.add_argument("--keep-failed-output", action="store_true",
                        help="keep the temporary folder of a failed build for inspection")
    parser.add_argument("--verify", type=Path, metavar="DIR", help="verify a downloaded output folder and exit")
    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        return EXIT_OK if error.code == 0 else EXIT_REFUSED

    if args.verify is not None:
        try:
            rows = verify_output(args.verify)
        except VerifyError as error:
            print(f"VERIFY FAILED: {args.verify}\n{error}")
            return EXIT_MISMATCH
        print(f"Verified {args.verify}: " + ", ".join(f"{name} {n:,} rows" for name, n in rows.items()))
        return EXIT_OK

    return build(
        args.out_dir,
        force=args.force,
        allow_dirty=args.allow_dirty,
        keep_failed_output=args.keep_failed_output,
        raw_dir=args.raw_dir,
    )


if __name__ == "__main__":
    sys.exit(main())
