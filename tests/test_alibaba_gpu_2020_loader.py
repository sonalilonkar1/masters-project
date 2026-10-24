import copy
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.sources import alibaba_gpu_2020 as loader
from src.sources.alibaba_gpu_2020 import (
    SCHEMAS,
    SOURCE_ROW_NUMBER,
    SourceVerificationError,
    describe_file,
    iter_table_chunks,
    load_table,
    source_provenance,
    verify_sources,
    verify_table,
)


# Small headerless fixture tables in source order. The sensor rows include a
# value that the fast float parser would not convert exactly
# (0.23250918136105705) and an empty field; the instance rows include the
# literal text "NA" and "None", which must stay text.
FIXTURE_LINES = {
    "pai_job_table": [
        "j1,i1,u1,Terminated,100.0,200.0",
        "j2,i2,u1,Running,150.0,",
        "j3,i3,u2,Failed,,",
    ],
    "pai_task_table": [
        "j1,worker,1.0,Terminated,100.0,200.0,600.0,29.296875,50.0,MISC",
        "j2,ps,2.0,Running,150.0,,,,,",
    ],
    "pai_instance_table": [
        "j1,worker,n1,w1,i1,Terminated,100.0,200.0,m1",
        "j1,worker,n1,w2,i1,Failed,90.0,95.0,m2",
        "j2,ps,NA,None,i2,Waiting,,,",
        "j3,worker,n3,w3,i3,Terminated,300.0,400.0,m1",
        "j3,worker,n4,w4,i3,Terminated,300.0,410.0,m2",
    ],
    "pai_sensor_table": [
        "j1,worker,w1,i1,m1,/dev/nvidia0,140.1451612903226,16.0625,0.23250918136105705,2.3935546875,1.2446746826171875,2.3994140625,21271328.384615384,16376189.815384615,2922.4461538461537,3419.7846153846153",
        "j1,worker,w2,i1,m2,/dev/nvidia1,,0.0,,0.5,0.0,0.0,1.0,2.0,3.0,4.0",
    ],
    "pai_group_tag_table": [
        "i1,u1,V100M32,g1,nmt",
        "i2,u1,,g1,",
    ],
    "pai_machine_spec": [
        "m1,T4,96,512,2",
        "m2,CPU,64,384,0",
    ],
}


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


@pytest.fixture()
def fixture_sources(tmp_path):
    """Write fixture CSV and header files and a manifest describing them."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    tables = {}

    for table, lines in FIXTURE_LINES.items():
        _write(raw_dir / f"{table}.csv", "\n".join(lines) + "\n")
        _write(raw_dir / f"{table}.header", ",".join(SCHEMAS[table]) + "\n")
        archive = raw_dir / "archives" / f"{table}.tar.gz"
        archive.parent.mkdir(exist_ok=True)
        archive.write_bytes(b"archive-placeholder-" + table.encode())

        tables[table] = {
            "archive": {"file": f"archives/{table}.tar.gz", **_entry(archive, lines=False)},
            "header": {"file": f"{table}.header", "columns": list(SCHEMAS[table]), **_entry(raw_dir / f"{table}.header", lines=False)},
            "csv": {"file": f"{table}.csv", **_entry(raw_dir / f"{table}.csv", lines=True)},
        }

    manifest = {"dataset_id": loader.DATASET_ID, "source_version": loader.SOURCE_VERSION, "tables": tables}
    return raw_dir, manifest


def _entry(path: Path, lines: bool) -> dict:
    described = describe_file(path)
    entry = {"sha256": described["sha256"], "size_bytes": described["size_bytes"]}
    if lines:
        entry["data_lines"] = described["data_lines"]
    return entry


def test_schemas_cover_the_six_official_tables():
    assert loader.TABLES == (
        "pai_job_table",
        "pai_task_table",
        "pai_instance_table",
        "pai_sensor_table",
        "pai_group_tag_table",
        "pai_machine_spec",
    )


@pytest.mark.parametrize("table", list(FIXTURE_LINES))
def test_full_load_columns_types_order_and_row_numbers(fixture_sources, table):
    raw_dir, manifest = fixture_sources

    frame = load_table(table, raw_dir=raw_dir, manifest=manifest)

    assert list(frame.columns) == list(SCHEMAS[table]) + [SOURCE_ROW_NUMBER]
    for column, dtype in SCHEMAS[table].items():
        assert str(frame[column].dtype) == dtype, column
    assert frame[SOURCE_ROW_NUMBER].dtype == np.int64
    np.testing.assert_array_equal(frame[SOURCE_ROW_NUMBER], np.arange(1, len(FIXTURE_LINES[table]) + 1))

    # Values match the source lines in file order; empty fields are missing.
    for line_number, line in enumerate(FIXTURE_LINES[table], start=1):
        row = frame.loc[frame[SOURCE_ROW_NUMBER] == line_number].iloc[0]
        for column, raw in zip(SCHEMAS[table], line.split(",")):
            value = row[column]
            if raw == "":
                assert pd.isna(value), (line_number, column)
            elif SCHEMAS[table][column] == "string":
                assert value == raw, (line_number, column)
            else:
                assert float(value) == float(raw), (line_number, column)


def test_text_like_missing_markers_are_kept_as_text(fixture_sources):
    raw_dir, manifest = fixture_sources

    frame = load_table("pai_instance_table", raw_dir=raw_dir, manifest=manifest)
    row = frame.loc[frame[SOURCE_ROW_NUMBER] == 3].iloc[0]

    assert row["inst_name"] == "NA"
    assert row["worker_name"] == "None"
    assert pd.isna(row["machine"])


def test_floats_are_parsed_exactly(fixture_sources):
    raw_dir, manifest = fixture_sources

    frame = load_table("pai_sensor_table", raw_dir=raw_dir, manifest=manifest)

    assert frame.loc[0, "avg_mem"] == float("0.23250918136105705")


def test_column_selection_keeps_row_numbers(fixture_sources):
    raw_dir, manifest = fixture_sources
    full = load_table("pai_instance_table", raw_dir=raw_dir, manifest=manifest)

    selected = load_table(
        "pai_instance_table",
        columns=["start_time", "inst_name"],
        raw_dir=raw_dir,
        manifest=manifest,
    )

    assert list(selected.columns) == ["start_time", "inst_name", SOURCE_ROW_NUMBER]
    pd.testing.assert_frame_equal(selected, full[["start_time", "inst_name", SOURCE_ROW_NUMBER]])


@pytest.mark.parametrize("chunksize", [1, 2, 3, 5, 100])
def test_chunked_load_equals_full_load(fixture_sources, chunksize):
    raw_dir, manifest = fixture_sources
    full = load_table("pai_instance_table", raw_dir=raw_dir, manifest=manifest)

    chunks = list(iter_table_chunks("pai_instance_table", chunksize=chunksize, raw_dir=raw_dir, manifest=manifest))

    assert all(len(chunk) <= chunksize for chunk in chunks)
    pd.testing.assert_frame_equal(pd.concat(chunks, ignore_index=True), full)


def test_chunked_column_selection_equals_full_load(fixture_sources):
    raw_dir, manifest = fixture_sources
    columns = ["job_name", "end_time"]
    full = load_table("pai_instance_table", columns=columns, raw_dir=raw_dir, manifest=manifest)

    chunked = pd.concat(
        iter_table_chunks("pai_instance_table", columns=columns, chunksize=2, raw_dir=raw_dir, manifest=manifest),
        ignore_index=True,
    )

    pd.testing.assert_frame_equal(chunked, full)


def test_repeated_loads_are_identical(fixture_sources):
    raw_dir, manifest = fixture_sources

    first = load_table("pai_sensor_table", raw_dir=raw_dir, manifest=manifest)
    second = load_table("pai_sensor_table", raw_dir=raw_dir, manifest=manifest)

    pd.testing.assert_frame_equal(first, second)


def test_verify_sources_reports_every_table(fixture_sources):
    raw_dir, manifest = fixture_sources

    report = verify_sources(raw_dir=raw_dir, manifest=manifest, check_archives=True)

    assert [entry["table"] for entry in report] == list(loader.TABLES)
    assert [entry["data_lines"] for entry in report] == [len(FIXTURE_LINES[t]) for t in loader.TABLES]


def test_modified_file_fails_checksum(fixture_sources):
    raw_dir, manifest = fixture_sources
    path = raw_dir / "pai_job_table.csv"
    path.write_text(path.read_text().replace("Running", "Runnong"))

    with pytest.raises(SourceVerificationError, match="checksum mismatch"):
        load_table("pai_job_table", raw_dir=raw_dir, manifest=manifest)


def test_truncated_file_fails(fixture_sources):
    raw_dir, manifest = fixture_sources
    path = raw_dir / "pai_job_table.csv"
    path.write_text("\n".join(FIXTURE_LINES["pai_job_table"][:2]) + "\n")

    with pytest.raises(SourceVerificationError, match="size mismatch"):
        verify_table("pai_job_table", raw_dir=raw_dir, manifest=manifest)


def test_missing_file_fails(fixture_sources):
    raw_dir, manifest = fixture_sources
    (raw_dir / "pai_task_table.csv").unlink()

    with pytest.raises(SourceVerificationError, match="not found"):
        verify_table("pai_task_table", raw_dir=raw_dir, manifest=manifest)


def test_changed_archive_fails_only_when_archives_are_checked(fixture_sources):
    raw_dir, manifest = fixture_sources
    (raw_dir / "archives" / "pai_job_table.tar.gz").write_bytes(b"different")

    verify_table("pai_job_table", raw_dir=raw_dir, manifest=manifest)
    with pytest.raises(SourceVerificationError, match="Archive"):
        verify_table("pai_job_table", raw_dir=raw_dir, manifest=manifest, check_archive=True)


def test_header_that_differs_from_schema_fails(fixture_sources):
    raw_dir, manifest = fixture_sources
    manifest = copy.deepcopy(manifest)
    header = raw_dir / "pai_machine_spec.header"
    header.write_text("machine,gpu_type,cap_mem,cap_cpu,cap_gpu\n")
    manifest["tables"]["pai_machine_spec"]["header"].update(_entry(header, lines=False))

    with pytest.raises(SourceVerificationError, match="do not match the loader schema"):
        verify_table("pai_machine_spec", raw_dir=raw_dir, manifest=manifest)


def test_unknown_table_and_columns_are_rejected(fixture_sources):
    raw_dir, manifest = fixture_sources

    with pytest.raises(KeyError, match="Unknown Alibaba GPU 2020 table"):
        load_table("pai_machine_metric", raw_dir=raw_dir, manifest=manifest)
    with pytest.raises(KeyError, match="Unknown columns"):
        load_table("pai_job_table", columns=["job_name", "group"], raw_dir=raw_dir, manifest=manifest)
    with pytest.raises(ValueError, match="At least one column"):
        load_table("pai_job_table", columns=[], raw_dir=raw_dir, manifest=manifest)
    with pytest.raises(ValueError, match="Duplicate columns"):
        load_table("pai_job_table", columns=["job_name", "job_name"], raw_dir=raw_dir, manifest=manifest)


def test_invalid_chunksize_is_rejected(fixture_sources):
    raw_dir, manifest = fixture_sources

    with pytest.raises(ValueError, match="chunksize"):
        next(iter_table_chunks("pai_job_table", chunksize=0, raw_dir=raw_dir, manifest=manifest))


def test_source_provenance_matches_manifest(fixture_sources):
    raw_dir, manifest = fixture_sources

    provenance = source_provenance(raw_dir=raw_dir, manifest=manifest)

    assert set(provenance) == {"source_version", "source_files", "source_checksums"}
    assert provenance["source_version"] == loader.SOURCE_VERSION
    assert list(provenance["source_files"]) == list(loader.TABLES)
    for table in loader.TABLES:
        assert provenance["source_files"][table] == manifest["tables"][table]["csv"]["file"]
        assert provenance["source_checksums"][table] == manifest["tables"][table]["csv"]["sha256"]
        assert provenance["source_checksums"][table] == describe_file(raw_dir / f"{table}.csv")["sha256"]

    subset = source_provenance(tables=["pai_instance_table"], raw_dir=raw_dir, manifest=manifest)
    assert list(subset["source_files"]) == ["pai_instance_table"]
    assert list(subset["source_checksums"]) == ["pai_instance_table"]


def test_source_provenance_is_accepted_by_the_adapter_framework(fixture_sources):
    from src.adapters.base import BaseDatasetAdapter

    raw_dir, manifest = fixture_sources
    provenance = source_provenance(raw_dir=raw_dir, manifest=manifest)
    provenance["telemetry_window"] = {"start": 90.0, "end": 410.0}

    assert BaseDatasetAdapter._validate_provenance(provenance) == provenance


@pytest.mark.parametrize("change", ["missing", "modified"])
def test_source_provenance_fails_on_missing_or_modified_file(fixture_sources, change):
    raw_dir, manifest = fixture_sources
    path = raw_dir / "pai_sensor_table.csv"
    if change == "missing":
        path.unlink()
    else:
        path.write_text(path.read_text().replace("16.0625", "16.0626"))

    with pytest.raises(SourceVerificationError, match="not found" if change == "missing" else "checksum mismatch"):
        source_provenance(raw_dir=raw_dir, manifest=manifest)


def _count_csv_hashes(monkeypatch, csv_path):
    calls = []
    original = loader.describe_file

    def counting(path):
        if Path(path) == csv_path:
            calls.append(path)
        return original(path)

    monkeypatch.setattr(loader, "describe_file", counting)
    return calls


def test_loads_hash_an_unchanged_file_once(fixture_sources, monkeypatch):
    raw_dir, manifest = fixture_sources
    calls = _count_csv_hashes(monkeypatch, raw_dir / "pai_instance_table.csv")

    full = load_table("pai_instance_table", raw_dir=raw_dir, manifest=manifest)
    selected = load_table("pai_instance_table", columns=["job_name"], raw_dir=raw_dir, manifest=manifest)
    chunked = pd.concat(
        iter_table_chunks("pai_instance_table", chunksize=2, raw_dir=raw_dir, manifest=manifest),
        ignore_index=True,
    )

    assert len(calls) == 1
    pd.testing.assert_frame_equal(chunked, full)
    pd.testing.assert_frame_equal(selected, full[["job_name", SOURCE_ROW_NUMBER]])

    # Explicit verification always hashes the file.
    verify_table("pai_instance_table", raw_dir=raw_dir, manifest=manifest)
    source_provenance(tables=["pai_instance_table"], raw_dir=raw_dir, manifest=manifest)
    assert len(calls) == 3


def test_loads_hash_a_modified_file_again(fixture_sources, monkeypatch):
    raw_dir, manifest = fixture_sources
    path = raw_dir / "pai_instance_table.csv"
    calls = _count_csv_hashes(monkeypatch, path)
    load_table("pai_instance_table", raw_dir=raw_dir, manifest=manifest)
    original_text = path.read_text()
    original_mtime = path.stat().st_mtime_ns

    # Same size, different content, new modification time: hashed again and rejected.
    path.write_text(original_text.replace("w1", "w9", 1))
    os.utime(path, ns=(original_mtime + 1_000_000_000, original_mtime + 1_000_000_000))
    with pytest.raises(SourceVerificationError, match="checksum mismatch"):
        load_table("pai_instance_table", raw_dir=raw_dir, manifest=manifest)
    with pytest.raises(SourceVerificationError, match="checksum mismatch"):
        next(iter_table_chunks("pai_instance_table", raw_dir=raw_dir, manifest=manifest))
    assert len(calls) == 3

    # Restored content with yet another modification time: hashed again and accepted.
    path.write_text(original_text)
    os.utime(path, ns=(original_mtime + 2_000_000_000, original_mtime + 2_000_000_000))
    load_table("pai_instance_table", raw_dir=raw_dir, manifest=manifest)
    assert len(calls) == 4


def test_loads_verify_again_against_a_different_manifest_entry(fixture_sources):
    raw_dir, manifest = fixture_sources
    load_table("pai_job_table", raw_dir=raw_dir, manifest=manifest)

    other = copy.deepcopy(manifest)
    other["tables"]["pai_job_table"]["csv"]["sha256"] = "0" * 64
    with pytest.raises(SourceVerificationError, match="checksum mismatch"):
        load_table("pai_job_table", raw_dir=raw_dir, manifest=other)


def test_loads_verify_a_deleted_file_again(fixture_sources):
    raw_dir, manifest = fixture_sources
    load_table("pai_job_table", raw_dir=raw_dir, manifest=manifest)
    (raw_dir / "pai_job_table.csv").unlink()

    with pytest.raises(SourceVerificationError, match="not found"):
        load_table("pai_job_table", raw_dir=raw_dir, manifest=manifest)


def test_committed_manifest_matches_schemas_and_documented_counts():
    manifest = loader.load_manifest()

    assert manifest["source_version"] == "cluster-trace-gpu-v2020"
    assert list(manifest["tables"]) == list(loader.TABLES)
    for table, entry in manifest["tables"].items():
        assert entry["header"]["columns"] == list(SCHEMAS[table])
        for part in ("archive", "header", "csv"):
            assert len(entry[part]["sha256"]) == 64

    # Row counts documented in docs/data/alibaba_dataset_selection_feasibility.md;
    # job and task counts also appear in alibaba_gpu_2020_evidence_and_limitations.md.
    documented = {
        "pai_job_table": 1_055_501,
        "pai_task_table": 1_261_050,
        "pai_instance_table": 7_522_002,
        "pai_sensor_table": 3_033_232,
        "pai_group_tag_table": 1_055_032,
        "pai_machine_spec": 1_897,
    }
    for table, rows in documented.items():
        assert manifest["tables"][table]["csv"]["data_lines"] == rows


@pytest.mark.skipif(
    os.environ.get("TRACEADVISOR_FULL_DATA_TESTS") != "1"
    or not (loader.DEFAULT_RAW_DIR / "pai_job_table.csv").exists(),
    reason="Set TRACEADVISOR_FULL_DATA_TESTS=1 with the official tables downloaded to run.",
)
def test_real_tables_verify_and_load():
    report = verify_sources()
    manifest = loader.load_manifest()

    for entry in report:
        assert entry["data_lines"] == manifest["tables"][entry["table"]]["csv"]["data_lines"]

    for table in ("pai_job_table", "pai_task_table", "pai_group_tag_table", "pai_machine_spec"):
        frame = load_table(table, verify=False)
        assert len(frame) == manifest["tables"][table]["csv"]["data_lines"]
        np.testing.assert_array_equal(frame[SOURCE_ROW_NUMBER], np.arange(1, len(frame) + 1))

    # The large tables are loaded with one column to keep memory low; the
    # chunked load must equal the full load, including source_row_number.
    for table in ("pai_instance_table", "pai_sensor_table"):
        frame = load_table(table, columns=["job_name"])
        assert len(frame) == manifest["tables"][table]["csv"]["data_lines"]
        np.testing.assert_array_equal(frame[SOURCE_ROW_NUMBER], np.arange(1, len(frame) + 1))
        chunked = pd.concat(iter_table_chunks(table, columns=["job_name"], chunksize=1_000_000), ignore_index=True)
        pd.testing.assert_frame_equal(chunked, frame)

    provenance = source_provenance()
    assert provenance["source_version"] == manifest["source_version"]
    for table in loader.TABLES:
        assert provenance["source_files"][table] == manifest["tables"][table]["csv"]["file"]
        assert provenance["source_checksums"][table] == manifest["tables"][table]["csv"]["sha256"]



def test_quotes_are_text_and_never_merge_lines(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    lines = ['j1,"i1', 'x",u1,Terminated,1.0,2.0', "j2,i2,u2,Terminated,3.0,4.0"]
    _write(raw_dir / "pai_job_table.csv", "\n".join(lines) + "\n")
    manifest = {
        "dataset_id": loader.DATASET_ID,
        "tables": {"pai_job_table": {"csv": {"file": "pai_job_table.csv", "data_lines": 3}}},
    }

    frame = load_table("pai_job_table", raw_dir=raw_dir, manifest=manifest, verify=False)

    # One row per line: the quote is kept as text instead of joining lines 1 and 2.
    np.testing.assert_array_equal(frame[SOURCE_ROW_NUMBER], [1, 2, 3])
    assert frame.loc[0, "inst_id"] == '"i1'
    assert frame.loc[2, "job_name"] == "j2"


def test_manifest_for_another_dataset_is_rejected(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text('{"dataset_id": "google_clusterdata2019", "tables": {}}')

    with pytest.raises(SourceVerificationError, match="dataset_id"):
        loader.load_manifest(path)


def test_manifest_without_table_entry_is_rejected(fixture_sources):
    raw_dir, manifest = fixture_sources
    manifest = copy.deepcopy(manifest)
    del manifest["tables"]["pai_task_table"]

    with pytest.raises(SourceVerificationError, match="no entry"):
        verify_table("pai_task_table", raw_dir=raw_dir, manifest=manifest)


def test_manifest_line_count_must_match(fixture_sources):
    raw_dir, manifest = fixture_sources
    manifest = copy.deepcopy(manifest)
    manifest["tables"]["pai_job_table"]["csv"]["data_lines"] += 1

    with pytest.raises(SourceVerificationError, match="line-count mismatch"):
        verify_table("pai_job_table", raw_dir=raw_dir, manifest=manifest)


@pytest.mark.parametrize("chunked", [False, True])
def test_loaded_row_count_is_checked_after_reading(fixture_sources, monkeypatch, chunked):
    raw_dir, manifest = fixture_sources
    manifest = copy.deepcopy(manifest)
    manifest["tables"]["pai_job_table"]["csv"]["data_lines"] = 99
    monkeypatch.setattr(loader, "verify_table", lambda *args, **kwargs: None)

    with pytest.raises(SourceVerificationError, match="expected 99"):
        if chunked:
            list(iter_table_chunks("pai_job_table", chunksize=2, raw_dir=raw_dir, manifest=manifest))
        else:
            load_table("pai_job_table", raw_dir=raw_dir, manifest=manifest)


# --- scripts/verify_data_setup.py -------------------------------------------------

def _verify_script():
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "scripts" / "verify_data_setup.py"
    spec = importlib.util.spec_from_file_location("verify_data_setup", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verify_script_passes_on_verified_sources(fixture_sources, monkeypatch, capsys):
    raw_dir, manifest = fixture_sources
    monkeypatch.setattr(loader, "load_manifest", lambda *args, **kwargs: manifest)
    monkeypatch.setattr("sys.argv", ["verify_data_setup.py", "--dataset", "alibaba_gpu_2020", "--raw-dir", str(raw_dir), "--check-archives", "--load"])

    assert _verify_script().main() == 0

    output = capsys.readouterr().out
    for table in loader.TABLES:
        assert f"OK    {table}: {len(FIXTURE_LINES[table])} rows" in output
        assert f"(loaded {len(FIXTURE_LINES[table])} rows)" in output
    assert "All Alibaba GPU 2020 source tables verified." in output


def test_verify_script_fails_on_modified_source(fixture_sources, monkeypatch, capsys):
    raw_dir, manifest = fixture_sources
    path = raw_dir / "pai_sensor_table.csv"
    path.write_text(path.read_text().replace("nvidia1", "nvidia2"))
    monkeypatch.setattr(loader, "load_manifest", lambda *args, **kwargs: manifest)
    monkeypatch.setattr("sys.argv", ["verify_data_setup.py", "--dataset", "alibaba_gpu_2020", "--raw-dir", str(raw_dir)])

    assert _verify_script().main() == 1

    output = capsys.readouterr().out
    assert "FAIL  pai_sensor_table" in output and "checksum mismatch" in output
    assert "OK    pai_job_table" in output
    assert "1 table(s) failed verification." in output


def test_verify_script_default_google_mode_is_unchanged(tmp_path, monkeypatch, capsys):
    script = _verify_script()
    csv_path = tmp_path / "subset.csv"
    csv_path.write_text("a,b\n1,2\n")
    monkeypatch.setattr(script, "FILE_PATH", str(csv_path))
    monkeypatch.setattr("sys.argv", ["verify_data_setup.py"])

    assert script.main() == 0
    output = capsys.readouterr().out
    assert "File loaded successfully!" in output and "(1, 2)" in output

    monkeypatch.setattr(script, "FILE_PATH", str(tmp_path / "missing.csv"))
    assert script.main() == 0
    assert "File not found at" in capsys.readouterr().out


def test_verify_script_load_count_guard(fixture_sources, monkeypatch, capsys):
    raw_dir, manifest = fixture_sources
    monkeypatch.setattr(loader, "load_manifest", lambda *args, **kwargs: manifest)
    monkeypatch.setattr(loader, "load_table", lambda *args, **kwargs: pd.DataFrame({"x": []}))
    monkeypatch.setattr("sys.argv", ["verify_data_setup.py", "--dataset", "alibaba_gpu_2020", "--raw-dir", str(raw_dir), "--load"])

    assert _verify_script().main() == 1
    assert "loaded 0 rows, expected" in capsys.readouterr().out


def test_verify_script_command_line_exit_code(tmp_path):
    import subprocess
    import sys

    script = Path(__file__).resolve().parents[1] / "scripts" / "verify_data_setup.py"
    result = subprocess.run(
        [sys.executable, str(script), "--dataset", "alibaba_gpu_2020", "--raw-dir", str(tmp_path / "empty")],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "6 table(s) failed verification." in result.stdout
