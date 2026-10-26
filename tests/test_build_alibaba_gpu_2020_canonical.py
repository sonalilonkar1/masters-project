"""Tests for scripts/build_alibaba_gpu_2020_canonical.py (design §5.7), on the adapter fixture."""

import importlib.util
import json
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from test_alibaba_gpu_2020_adapter import PROVENANCE, _sources_with_rejected_j1, make_sources


def _script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "build_alibaba_gpu_2020_canonical.py"
    spec = importlib.util.spec_from_file_location("build_alibaba_gpu_2020_canonical", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()


def _build(out_dir, tmp_path, **options):
    """Fixture build outside Git (so --allow-dirty) with the count check off unless given."""
    options = {"allow_dirty": True, "expected": None, "repo": tmp_path, **options}
    return script.build(out_dir, sources_loader=lambda: (make_sources(), dict(PROVENANCE)), **options)


@pytest.fixture
def built(tmp_path):
    out_dir = tmp_path / "out"
    assert _build(out_dir, tmp_path) == script.EXIT_OK
    return out_dir


def _leftovers(out_dir):
    return [p.name for p in out_dir.parent.iterdir() if p.name.startswith(f".{out_dir.name}.")]


# --- build --------------------------------------------------------------------

def test_build_writes_the_six_files_and_they_round_trip(built):
    assert sorted(p.name for p in built.iterdir()) == sorted([*script.CHECKED_FILES, "SHA256SUMS"])
    assert _leftovers(built) == []

    metadata = json.loads((built / "metadata.json").read_text())
    for view, name in script.VIEW_FILES.items():
        frame = pd.read_parquet(built / name)
        assert list(frame.columns) == script.PARQUET_COLUMNS[name]
        assert len(frame) == metadata["canonical_row_counts"][view]
    assert len(pd.read_parquet(built / "rejected.parquet")) == metadata["rejection_count"]


def test_metadata_has_the_adapter_metadata_and_a_build_block(built):
    metadata = json.loads((built / "metadata.json").read_text())
    assert metadata["primary_view"] == "role_occurrence"
    assert metadata["provenance"]["source_version"] == PROVENANCE["source_version"]
    assert set(metadata["eligibility_summary"]) == {
        "accepted_roles", "pass_all_but_multi_attempt_worker", "eligible", "eligible_missing_cpu"}
    assert metadata["build"]["code_commit"] is None
    assert set(metadata["build"]) == {
        "code_commit", "code_dirty", "python_version", "pandas_version", "pyarrow_version"}


def test_metadata_reconciles_source_rows_at_each_level(tmp_path):
    # j1 has no submission time, so every level has rejected rows.
    out_dir = tmp_path / "out"
    options = {"allow_dirty": True, "expected": None, "repo": tmp_path}
    assert script.build(out_dir, sources_loader=lambda: (_sources_with_rejected_j1(), dict(PROVENANCE)),
                        **options) == script.EXIT_OK
    metadata = json.loads((out_dir / "metadata.json").read_text())
    levels = metadata["reconciliation"]
    assert {k: (v["source"], v["accepted"], v["rejected"], v["difference"]) for k, v in levels.items()} == {
        "job": (2, 1, 1, 0), "role_occurrence": (2, 1, 1, 0), "instance": (4, 1, 3, 0)}
    roles = pd.read_parquet(out_dir / "role_occurrence.parquet")
    assert levels["job"]["accepted"] == roles["job_name"].nunique()
    assert sum(level["rejected"] for level in levels.values()) == metadata["rejection_count"]

    report = (out_dir / "count_report.md").read_text()
    assert "## Reconciliation (source = accepted + rejected)" in report
    assert "| instance | `pai_instance_table` | 4 | 1 | 3 | 0 |" in report
    assert "Every level reconciles." in report


def test_rejected_counts_are_compared_per_level():
    metadata = script.AlibabaGPU2020Adapter().adapt_sources(
        _sources_with_rejected_j1(), primary_view="role_occurrence", provenance=PROVENANCE).metadata
    counts = script.headline_counts(metadata)
    assert (counts["rejected: job"], counts["rejected: role_occurrence"], counts["rejected: instance"]) == (1, 1, 3)
    assert {"rejected: job", "rejected: role_occurrence", "rejected: instance"} <= set(script.EXPECTED_COUNTS)
    [(_, _, _, difference)] = script.compare_counts(metadata, {"rejected: instance": 2})
    assert difference == 1


def test_unreconciled_build_is_never_published(built, tmp_path, monkeypatch, capsys):
    before = (built / "SHA256SUMS").read_text()
    real = script.reconciliation

    def lose_an_instance(metadata, accepted_jobs):
        levels = real(metadata, accepted_jobs)
        levels["instance"]["difference"] += 1
        return levels

    monkeypatch.setattr(script, "reconciliation", lose_an_instance)
    assert _build(built, tmp_path, force=True) == script.EXIT_MISMATCH
    assert "NOT RECONCILED: not published." in capsys.readouterr().out
    assert (built / "SHA256SUMS").read_text() == before
    assert _leftovers(built) == []

    assert _build(built, tmp_path, force=True, keep_failed_output=True) == script.EXIT_MISMATCH
    [kept] = _leftovers(built)
    assert "**1 level(s) do not reconcile.**" in (built.parent / kept / "count_report.md").read_text()


def test_reconciliation_on_the_full_table_figures():
    metadata = {
        "source_row_counts": {"pai_job_table": 1_055_501, "pai_task_table": 1_261_050,
                              "pai_instance_table": 7_522_002},
        "canonical_row_counts": {"role_occurrence": 1_254_108, "instance": 7_410_783},
        "rejection_counts": {"job": {"missing_submission_time": 3_663},
                             "role_occurrence": {"missing_submission_time": 6_942},
                             "instance": {"missing_submission_time": 111_219}},
    }
    levels = script.reconciliation(metadata, accepted_jobs=1_051_838)
    assert {k: v["difference"] for k, v in levels.items()} == {"job": 0, "role_occurrence": 0, "instance": 0}
    assert levels["job"]["rejected"] == 3_663
    # A lost row shows up as a non-zero difference.
    metadata["canonical_row_counts"]["instance"] -= 1
    assert script.reconciliation(metadata, accepted_jobs=1_051_838)["instance"]["difference"] == 1


def test_checksums_use_the_standard_format(built):
    lines = (built / "SHA256SUMS").read_text().splitlines()
    assert [line.split("  ")[1] for line in lines] == sorted(script.CHECKED_FILES)
    for line in lines:
        digest, name = line.split("  ")
        assert digest == script.sha256(built / name)
    if subprocess.run(["which", "shasum"], capture_output=True).returncode == 0:
        check = subprocess.run(["shasum", "-a", "256", "-c", "SHA256SUMS"], cwd=built, capture_output=True)
        assert check.returncode == 0


def test_build_is_deterministic(built, tmp_path):
    again = tmp_path / "again"
    assert _build(again, tmp_path) == script.EXIT_OK
    assert (again / "SHA256SUMS").read_text() == (built / "SHA256SUMS").read_text()


def test_count_mismatch_is_never_published(built, tmp_path, capsys):
    before = (built / "SHA256SUMS").read_text()
    expected = {"rows: role_occurrence": -1}

    assert _build(built, tmp_path, force=True, expected=expected) == script.EXIT_MISMATCH
    assert "COUNT MISMATCH" in capsys.readouterr().out
    assert (built / "SHA256SUMS").read_text() == before
    assert _leftovers(built) == []

    assert _build(built, tmp_path, force=True, expected=expected, keep_failed_output=True) == script.EXIT_MISMATCH
    [kept] = _leftovers(built)
    report = (built.parent / kept / "count_report.md").read_text()
    assert "1 figure(s) differ" in report


def test_matching_expected_counts_publish(tmp_path):
    out_dir = tmp_path / "out"
    metadata = script.AlibabaGPU2020Adapter().adapt_sources(
        make_sources(), primary_view="role_occurrence", provenance=PROVENANCE).metadata
    expected = script.headline_counts(metadata)
    assert _build(out_dir, tmp_path, expected=expected) == script.EXIT_OK
    assert "All differences are zero." in (out_dir / "count_report.md").read_text()


def test_existing_output_needs_force(built, tmp_path, capsys):
    before = (built / "SHA256SUMS").read_text()
    assert _build(built, tmp_path) == script.EXIT_REFUSED
    assert "--force" in capsys.readouterr().out
    assert (built / "SHA256SUMS").read_text() == before

    (built / "note.txt").write_text("old")
    assert _build(built, tmp_path, force=True) == script.EXIT_OK
    assert not (built / "note.txt").exists()
    assert _leftovers(built) == []


def test_empty_output_folder_is_allowed(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert _build(out_dir, tmp_path) == script.EXIT_OK


def test_dirty_or_non_git_tree_is_refused_without_allow_dirty(tmp_path, capsys):
    out_dir = tmp_path / "out"
    assert _build(out_dir, tmp_path, allow_dirty=False) == script.EXIT_REFUSED
    assert "not a Git checkout" in capsys.readouterr().out
    assert not out_dir.exists()


def test_git_state_reads_commit_and_dirty(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git = lambda *args: subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    git("init", "-q")
    (repo / "a.txt").write_text("1")
    git("add", "a.txt")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "c")

    commit, dirty = script.git_state(repo)
    assert len(commit) == 40 and dirty is False
    (repo / "untracked.txt").write_text("x")
    assert script.git_state(repo)[1] is False
    (repo / "a.txt").write_text("2")
    assert script.git_state(repo)[1] is True


def test_adapter_failure_leaves_existing_output_unchanged(built, tmp_path, capsys):
    before = (built / "SHA256SUMS").read_text()
    broken = make_sources()
    del broken["pai_sensor_table"]
    code = script.build(built, force=True, allow_dirty=True, expected=None, repo=tmp_path,
                        sources_loader=lambda: (broken, dict(PROVENANCE)))
    assert code == script.EXIT_FAILED
    assert "BUILD FAILED" in capsys.readouterr().out
    assert (built / "SHA256SUMS").read_text() == before
    assert _leftovers(built) == []


def test_write_failure_cleans_up(built, tmp_path, monkeypatch):
    before = (built / "SHA256SUMS").read_text()

    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", fail)
    assert _build(built, tmp_path, force=True) == script.EXIT_FAILED
    assert (built / "SHA256SUMS").read_text() == before
    assert _leftovers(built) == []


def test_failed_publish_restores_the_previous_output(built, tmp_path, monkeypatch):
    before = (built / "SHA256SUMS").read_text()
    rename = script.os.rename

    def fail_install(src, dst):
        if ".tmp-" in str(src):
            raise OSError("rename failed")
        rename(src, dst)

    monkeypatch.setattr(script.os, "rename", fail_install)
    assert _build(built, tmp_path, force=True) == script.EXIT_FAILED
    assert (built / "SHA256SUMS").read_text() == before
    assert _leftovers(built) == []


def test_stale_folders_are_reported_not_deleted(tmp_path, capsys):
    out_dir = tmp_path / "out"
    stale = tmp_path / ".out.previous-1"
    stale.mkdir()
    assert _build(out_dir, tmp_path) == script.EXIT_OK
    assert f"stale folder from an earlier run, not deleted: {stale}" in capsys.readouterr().out
    assert stale.is_dir()


def test_each_frame_is_freed_before_the_next_is_written(tmp_path, monkeypatch):
    """No reference to the adapter result or to a written frame survives (hotspot #9)."""
    import weakref

    refs = {}
    run_adapter = script.run_adapter

    def capture(loader):
        result = run_adapter(loader)
        refs["result"] = weakref.ref(result)
        refs.update({name: weakref.ref(result.views[view]) for view, name in script.VIEW_FILES.items()})
        refs["rejected.parquet"] = weakref.ref(result.rejected)
        return result

    alive_at_write = {}
    to_parquet = pd.DataFrame.to_parquet

    def record(self, path, *args, **kwargs):
        alive_at_write[Path(path).name] = sorted(name for name, ref in refs.items() if ref() is not None)
        return to_parquet(self, path, *args, **kwargs)

    monkeypatch.setattr(script, "run_adapter", capture)
    monkeypatch.setattr(pd.DataFrame, "to_parquet", record)
    assert _build(tmp_path / "out", tmp_path) == script.EXIT_OK

    # While a file is written, only that frame and the ones still to come exist.
    assert alive_at_write == {
        "role_occurrence.parquet": ["instance.parquet", "rejected.parquet", "role_occurrence.parquet"],
        "instance.parquet": ["instance.parquet", "rejected.parquet"],
        "rejected.parquet": ["rejected.parquet"],
    }
    assert all(ref() is None for ref in refs.values())


def test_load_sources_verifies_then_loads_the_adapter_columns(monkeypatch):
    calls = []
    monkeypatch.setattr(script.loader, "source_provenance",
                        lambda raw_dir=None: {"source_version": "v", "source_files": {}, "source_checksums": {}})
    monkeypatch.setattr(script.loader, "load_table",
                        lambda table, columns, raw_dir, verify: calls.append((table, columns, verify)) or table)

    sources, provenance = script.load_sources()
    assert set(sources) == set(script.SOURCE_COLUMNS)
    assert provenance["telemetry_window"] == script.TELEMETRY_WINDOW
    for table, columns, verify in calls:
        assert verify is False
        assert "source_row_number" not in columns
        assert set(columns) == set(script.SOURCE_COLUMNS[table]) - {"source_row_number"}


@pytest.fixture
def source_files(tmp_path, monkeypatch):
    """The adapter fixture written as headerless CSV files with a manifest, like the real raw folder."""
    raw_dir = tmp_path / "raw"
    (raw_dir / "archives").mkdir(parents=True)
    tables = {}
    for table, frame in make_sources().items():
        columns = list(script.loader.SCHEMAS[table])
        frame[columns].to_csv(raw_dir / f"{table}.csv", header=False, index=False)
        (raw_dir / f"{table}.header").write_text(",".join(columns) + "\n")
        (raw_dir / "archives" / f"{table}.tar.gz").write_bytes(table.encode())
        entry = lambda name, lines=False: {
            "file": name,
            **{k: v for k, v in script.loader.describe_file(raw_dir / name).items()
               if k in ("sha256", "size_bytes") or (lines and k == "data_lines")},
        }
        tables[table] = {
            "archive": entry(f"archives/{table}.tar.gz"),
            "header": {**entry(f"{table}.header"), "columns": columns},
            "csv": entry(f"{table}.csv", lines=True),
        }
    manifest = {"dataset_id": script.loader.DATASET_ID, "source_version": script.loader.SOURCE_VERSION,
                "tables": tables}
    monkeypatch.setattr(script.loader, "load_manifest", lambda *args, **kwargs: manifest)
    return raw_dir


def test_build_from_real_source_files(source_files, tmp_path):
    """The real verify-and-load path on small CSV files, then a full build and --verify."""
    raw_dir = source_files

    sources, provenance = script.load_sources(raw_dir)
    for table, frame in sources.items():
        # The loader adds source_row_number to every table.
        assert set(frame.columns) == set(script.SOURCE_COLUMNS[table]) | {"source_row_number"}
    assert set(provenance["source_checksums"]) == set(script.SOURCE_COLUMNS)

    out_dir = tmp_path / "out"
    assert script.build(out_dir, raw_dir=raw_dir, allow_dirty=True, expected=None, repo=tmp_path) == script.EXIT_OK
    metadata = json.loads((out_dir / "metadata.json").read_text())
    assert metadata["provenance"]["source_checksums"] == provenance["source_checksums"]
    assert metadata["provenance"]["telemetry_window"] == script.TELEMETRY_WINDOW
    assert script.main(["--verify", str(out_dir)]) == script.EXIT_OK


def test_changed_source_file_fails_before_anything_is_written(source_files, tmp_path, capsys):
    raw_dir = source_files
    with (raw_dir / "pai_sensor_table.csv").open("a") as handle:
        handle.write("extra\n")

    out_dir = tmp_path / "out"
    assert script.build(out_dir, raw_dir=raw_dir, allow_dirty=True, expected=None, repo=tmp_path) == script.EXIT_FAILED
    assert "BUILD FAILED: SourceVerificationError" in capsys.readouterr().out
    assert not out_dir.exists()
    assert _leftovers(out_dir) == []


# --- verify -------------------------------------------------------------------

def test_verify_passes_on_a_clean_copy(built, capsys):
    assert script.main(["--verify", str(built)]) == script.EXIT_OK
    assert "Verified" in capsys.readouterr().out


@pytest.mark.parametrize(
    "damage, message",
    [
        (lambda d: (d / "instance.parquet").unlink(), "instance.parquet is missing"),
        (lambda d: (d / "count_report.md").write_text("changed"), "count_report.md does not match"),
        (lambda d: (d / ".DS_Store").write_text(""), "unexpected entry .DS_Store"),
        (lambda d: (d / "sub").mkdir(), "unexpected entry sub"),
        (lambda d: (d / "SHA256SUMS").unlink(), "SHA256SUMS is missing"),
        (lambda d: (d / "SHA256SUMS").write_text("not a checksum line\n"), "line 1 is not"),
    ],
)
def test_verify_fails(built, damage, message):
    damage(built)
    with pytest.raises(script.VerifyError, match=message):
        script.verify_output(built)


def test_verify_fails_on_a_duplicate_missing_or_empty_manifest(built):
    lines = (built / "SHA256SUMS").read_text().splitlines()
    (built / "SHA256SUMS").write_text("\n".join([lines[0], *lines]) + "\n")
    with pytest.raises(script.VerifyError, match="twice"):
        script.verify_output(built)
    (built / "SHA256SUMS").write_text("\n".join(lines[1:]) + "\n")
    with pytest.raises(script.VerifyError, match="must list exactly"):
        script.verify_output(built)
    # An empty manifest must not skip the checksum check.
    (built / "SHA256SUMS").write_text("")
    with pytest.raises(script.VerifyError, match="must list exactly"):
        script.verify_output(built)


def test_verify_compares_row_counts_with_metadata(built):
    metadata = json.loads((built / "metadata.json").read_text())
    metadata["canonical_row_counts"]["instance"] += 1
    (built / "metadata.json").write_text(json.dumps(metadata))
    lines = [line for line in (built / "SHA256SUMS").read_text().splitlines() if "metadata.json" not in line]
    lines.append(f"{script.sha256(built / 'metadata.json')}  metadata.json")
    (built / "SHA256SUMS").write_text("\n".join(sorted(lines, key=lambda l: l.split('  ')[1])) + "\n")
    with pytest.raises(script.VerifyError, match="instance.parquet has .* rows; metadata.json says"):
        script.verify_output(built)


def test_verify_cli_returns_one_on_failure(built, capsys):
    (built / ".DS_Store").write_text("")
    assert script.main(["--verify", str(built)]) == script.EXIT_MISMATCH
    assert "VERIFY FAILED" in capsys.readouterr().out
