# src/sources/alibaba_gpu_2020.py
#
# Source loader for the official Alibaba GPU 2020 trace
# (cluster-trace-gpu-v2020).
#
# Responsibilities:
#   - verify the decompressed source files against the committed checksum
#     manifest (config/alibaba_gpu_2020_sources.json);
#   - load the six headerless tables with explicit column names and types;
#   - preserve source-file order;
#   - assign source_row_number, the 1-based data-line number in the verified
#     decompressed source file.
#
# This module does not join tables, build canonical identities, or map
# records to canonical fields. That work belongs to the adapter (Task 3).

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Dict, Iterator, List, Mapping, Optional, Sequence

import pandas as pd


DATASET_ID = "alibaba_gpu_v2020"
SOURCE_VERSION = "cluster-trace-gpu-v2020"
SOURCE_ROW_NUMBER = "source_row_number"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_PATH = REPO_ROOT / "config" / "alibaba_gpu_2020_sources.json"
DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw" / "alibaba_gpu_2020"

TEXT = "string"
FLOAT = "float64"
INT = "int64"

# Column order follows the official .header files. Types were chosen from the
# full verified tables: identifiers and categories are text; times, plans and
# usage are float64 because they contain empty (missing) fields; machine
# capacities have no missing values and are whole numbers.
SCHEMAS: Dict[str, Dict[str, str]] = {
    "pai_job_table": {
        "job_name": TEXT,
        "inst_id": TEXT,
        "user": TEXT,
        "status": TEXT,
        "start_time": FLOAT,
        "end_time": FLOAT,
    },
    "pai_task_table": {
        "job_name": TEXT,
        "task_name": TEXT,
        "inst_num": FLOAT,
        "status": TEXT,
        "start_time": FLOAT,
        "end_time": FLOAT,
        "plan_cpu": FLOAT,
        "plan_mem": FLOAT,
        "plan_gpu": FLOAT,
        "gpu_type": TEXT,
    },
    "pai_instance_table": {
        "job_name": TEXT,
        "task_name": TEXT,
        "inst_name": TEXT,
        "worker_name": TEXT,
        "inst_id": TEXT,
        "status": TEXT,
        "start_time": FLOAT,
        "end_time": FLOAT,
        "machine": TEXT,
    },
    "pai_sensor_table": {
        "job_name": TEXT,
        "task_name": TEXT,
        "worker_name": TEXT,
        "inst_id": TEXT,
        "machine": TEXT,
        "gpu_name": TEXT,
        "cpu_usage": FLOAT,
        "gpu_wrk_util": FLOAT,
        "avg_mem": FLOAT,
        "max_mem": FLOAT,
        "avg_gpu_wrk_mem": FLOAT,
        "max_gpu_wrk_mem": FLOAT,
        "read": FLOAT,
        "write": FLOAT,
        "read_count": FLOAT,
        "write_count": FLOAT,
    },
    "pai_group_tag_table": {
        "inst_id": TEXT,
        "user": TEXT,
        "gpu_type_spec": TEXT,
        "group": TEXT,
        "workload": TEXT,
    },
    "pai_machine_spec": {
        "machine": TEXT,
        "gpu_type": TEXT,
        "cap_cpu": INT,
        "cap_mem": INT,
        "cap_gpu": INT,
    },
}

TABLES: tuple = tuple(SCHEMAS)


class SourceVerificationError(RuntimeError):
    """A source file is missing, modified, incomplete, or has an unexpected header."""


def describe_file(path: Path) -> Dict[str, int | str]:
    """Return the SHA-256, size in bytes, and number of data lines of a file."""
    digest = hashlib.sha256()
    size = 0
    lines = 0
    last_byte = b""

    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1 << 24), b""):
            digest.update(chunk)
            size += len(chunk)
            lines += chunk.count(b"\n")
            last_byte = chunk[-1:]

    # A final line without a trailing newline is still a data line.
    if size and last_byte != b"\n":
        lines += 1

    return {"sha256": digest.hexdigest(), "size_bytes": size, "data_lines": lines}


def load_manifest(path: Optional[Path] = None) -> dict:
    """Load the committed source manifest."""
    with open(Path(path or DEFAULT_MANIFEST_PATH), "r", encoding="utf-8") as file:
        manifest = json.load(file)

    if manifest.get("dataset_id") != DATASET_ID:
        raise SourceVerificationError(
            f"Manifest dataset_id is {manifest.get('dataset_id')!r}; expected {DATASET_ID!r}."
        )
    return manifest


def _table_entry(manifest: Mapping, table: str) -> Mapping:
    if table not in SCHEMAS:
        raise KeyError(f"Unknown Alibaba GPU 2020 table: {table!r}. Known tables: {list(SCHEMAS)}")
    try:
        return manifest["tables"][table]
    except KeyError as exc:
        raise SourceVerificationError(f"Manifest has no entry for {table!r}.") from exc


def _check(path: Path, expected: Mapping, label: str, check_lines: bool) -> Dict[str, int | str]:
    if not path.exists():
        raise SourceVerificationError(f"{label} not found: {path}")

    actual = describe_file(path)

    if actual["size_bytes"] != expected["size_bytes"]:
        raise SourceVerificationError(
            f"{label} size mismatch for {path.name}: expected {expected['size_bytes']} bytes, "
            f"found {actual['size_bytes']} (incomplete or modified file)."
        )
    if actual["sha256"] != expected["sha256"]:
        raise SourceVerificationError(
            f"{label} checksum mismatch for {path.name}: expected {expected['sha256']}, "
            f"found {actual['sha256']} (modified or corrupted file)."
        )
    if check_lines and actual["data_lines"] != expected["data_lines"]:
        raise SourceVerificationError(
            f"{label} line-count mismatch for {path.name}: expected {expected['data_lines']}, "
            f"found {actual['data_lines']}."
        )
    return actual


def verify_table(
    table: str,
    raw_dir: Optional[Path] = None,
    manifest: Optional[Mapping] = None,
    check_archive: bool = False,
) -> Dict[str, object]:
    """
    Verify one table's decompressed CSV and header file against the manifest.

    Raises SourceVerificationError on any missing, modified, or incomplete
    file, or when the header does not match the loader schema.
    """
    manifest = manifest if manifest is not None else load_manifest()
    raw_dir = Path(raw_dir or DEFAULT_RAW_DIR)
    entry = _table_entry(manifest, table)

    csv_path = raw_dir / entry["csv"]["file"]
    header_path = raw_dir / entry["header"]["file"]

    csv_actual = _check(csv_path, entry["csv"], "Source CSV", check_lines=True)
    _check(header_path, entry["header"], "Header file", check_lines=False)

    header_columns = header_path.read_text(encoding="utf-8").strip().split(",")
    if header_columns != list(SCHEMAS[table]):
        raise SourceVerificationError(
            f"Header columns for {table} do not match the loader schema: "
            f"{header_columns} != {list(SCHEMAS[table])}"
        )

    if check_archive:
        _check(raw_dir / entry["archive"]["file"], entry["archive"], "Archive", check_lines=False)

    return {
        "table": table,
        "csv_path": str(csv_path),
        "sha256": csv_actual["sha256"],
        "size_bytes": csv_actual["size_bytes"],
        "data_lines": csv_actual["data_lines"],
        "columns": header_columns,
    }


def verify_sources(
    raw_dir: Optional[Path] = None,
    tables: Optional[Sequence[str]] = None,
    manifest: Optional[Mapping] = None,
    check_archives: bool = False,
) -> List[Dict[str, object]]:
    """Verify every requested table (default: all six). Raises on the first failure."""
    manifest = manifest if manifest is not None else load_manifest()
    return [
        verify_table(table, raw_dir=raw_dir, manifest=manifest, check_archive=check_archives)
        for table in (tables or TABLES)
    ]


def _read_options(table: str, columns: Optional[Sequence[str]]) -> dict:
    schema = SCHEMAS[table]
    selected = list(schema) if columns is None else list(columns)

    unknown = [column for column in selected if column not in schema]
    if unknown:
        raise KeyError(f"Unknown columns for {table}: {unknown}")
    if not selected:
        raise ValueError(f"At least one column must be selected for {table}.")
    if len(set(selected)) != len(selected):
        raise ValueError(f"Duplicate columns requested for {table}: {selected}")

    return {
        "header": None,
        "names": list(schema),
        "usecols": selected,
        "dtype": {column: schema[column] for column in selected},
        # Only empty fields are missing; text such as "NA" or "None" is kept.
        "keep_default_na": False,
        "na_values": [""],
        # Blank lines are kept as rows so row positions stay equal to line numbers.
        "skip_blank_lines": False,
        # The official files contain no quotes; disabling quoting means a
        # field can never span lines, so each row is exactly one line.
        "quoting": csv.QUOTE_NONE,
        "on_bad_lines": "error",
        "engine": "c",
        # Exact decimal-to-float conversion; the default fast parser can be off
        # in the last binary digit (observed on cpu_usage and avg_mem).
        "float_precision": "round_trip",
    }, selected


def _finalize(frame: pd.DataFrame, selected: List[str], first_row_number: int) -> pd.DataFrame:
    frame = frame[selected].reset_index(drop=True)
    frame.insert(
        len(selected),
        SOURCE_ROW_NUMBER,
        pd.RangeIndex(first_row_number, first_row_number + len(frame)).to_numpy(dtype="int64"),
    )
    return frame


def _source_path(table: str, raw_dir: Optional[Path], manifest: Mapping) -> Path:
    entry = _table_entry(manifest, table)
    return Path(raw_dir or DEFAULT_RAW_DIR) / entry["csv"]["file"]


def load_table(
    table: str,
    columns: Optional[Sequence[str]] = None,
    raw_dir: Optional[Path] = None,
    manifest: Optional[Mapping] = None,
    verify: bool = True,
) -> pd.DataFrame:
    """
    Load one table in source-file order.

    Returns the selected columns plus source_row_number, the 1-based
    data-line number in the decompressed source file. With verify=True
    (default) the file is checked against the manifest before reading and
    the row count is checked afterwards; verify=False skips both checks.
    """
    manifest = manifest if manifest is not None else load_manifest()
    path = _source_path(table, raw_dir, manifest)

    if verify:
        verify_table(table, raw_dir=raw_dir, manifest=manifest)

    options, selected = _read_options(table, columns)
    frame = _finalize(pd.read_csv(path, **options), selected, first_row_number=1)

    expected_rows = manifest["tables"][table]["csv"]["data_lines"]
    if verify and len(frame) != expected_rows:
        raise SourceVerificationError(
            f"{table}: loaded {len(frame)} rows, expected {expected_rows}."
        )
    return frame


def iter_table_chunks(
    table: str,
    columns: Optional[Sequence[str]] = None,
    chunksize: int = 1_000_000,
    raw_dir: Optional[Path] = None,
    manifest: Optional[Mapping] = None,
    verify: bool = True,
) -> Iterator[pd.DataFrame]:
    """
    Yield one table in source-file order as chunks.

    source_row_number continues across chunks, so concatenating every chunk
    equals load_table() for the same columns.
    """
    if chunksize < 1:
        raise ValueError("chunksize must be at least 1.")

    manifest = manifest if manifest is not None else load_manifest()
    path = _source_path(table, raw_dir, manifest)

    if verify:
        verify_table(table, raw_dir=raw_dir, manifest=manifest)

    options, selected = _read_options(table, columns)
    next_row_number = 1

    with pd.read_csv(path, chunksize=chunksize, **options) as reader:
        for chunk in reader:
            yield _finalize(chunk, selected, first_row_number=next_row_number)
            next_row_number += len(chunk)

    expected_rows = manifest["tables"][table]["csv"]["data_lines"]
    if verify and next_row_number - 1 != expected_rows:
        raise SourceVerificationError(
            f"{table}: read {next_row_number - 1} rows in chunks, expected {expected_rows}."
        )
