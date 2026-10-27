"""Task 4 command tests using small, verified Task 3 folders only."""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pandas as pd
import pytest

from test_build_alibaba_gpu_2020_canonical import _build as build_canonical_fixture
from test_target_builder import make_roles, PROFILE


def _script():
    path = Path(__file__).resolve().parents[1] / "scripts/build_alibaba_gpu_2020_targets.py"
    spec = importlib.util.spec_from_file_location("build_alibaba_gpu_2020_targets", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()


@pytest.fixture
def canonical_dir(tmp_path):
    folder = tmp_path / "canonical"
    assert build_canonical_fixture(folder, tmp_path) == 0
    # Expand a fixture role into enough submissions for three partitions. Keep
    # the real canonical column order and dtypes for the actual Task 3 verifier.
    original = pd.read_parquet(folder / "role_occurrence.parquet")
    template = original.loc[original["exclusion_reason"].isna()].iloc[:1]
    roles = pd.concat([template] * 20, ignore_index=True)
    for column, values in make_roles().items():
        if column in roles:
            roles[column] = values
    roles.to_parquet(folder / "role_occurrence.parquet", index=False)
    metadata_path = folder / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["canonical_row_counts"]["role_occurrence"] = 20
    metadata["canonical_row_count"] = 20
    metadata["build"]["code_commit"] = "c2ae87f4aa357384a3cc8bdc72f776f1012c3ab7"
    metadata["build"]["code_dirty"] = False
    metadata_path.write_text(json.dumps(metadata))
    (folder / "SHA256SUMS").write_text("".join(
        f"{script.canonical.sha256(folder / name)}  {name}\n"
        for name in sorted(script.canonical.CHECKED_FILES)))
    script.canonical.verify_output(folder)
    return folder


def run_build(canonical_dir, out_dir, monkeypatch, **kwargs):
    monkeypatch.setattr(script.canonical, "git_state", lambda repo: ("a" * 40, False))
    return script.build(canonical_dir, out_dir, **kwargs)


def test_build_files_provenance_checksums_and_only_role_records_read(canonical_dir, tmp_path, monkeypatch, capsys):
    out = tmp_path / "targets"
    before = {p.name: p.read_bytes() for p in canonical_dir.iterdir()}
    real = pd.read_parquet
    reads = []

    def record_read(path, *args, **kwargs):
        reads.append(Path(path).name)
        return real(path, *args, **kwargs)

    monkeypatch.setattr(script.pd, "read_parquet", record_read)
    assert run_build(canonical_dir, out, monkeypatch) == script.EXIT_OK
    assert reads == ["role_occurrence.parquet"]
    assert {p.name: p.read_bytes() for p in canonical_dir.iterdir()} == before
    assert sorted(p.name for p in out.iterdir()) == ["SHA256SUMS", *sorted(script.CHECKED_FILES)]
    metadata = json.loads((out / "metadata.json").read_text())
    assert metadata["build"]["code_commit"] == "a" * 40
    assert metadata["build"]["code_dirty"] is False
    assert set(metadata["build"]) == {
        "code_commit", "code_dirty", "python_version", "pandas_version", "pyarrow_version"}
    assert metadata["source_provenance"]["build"]["code_commit"].startswith("c2ae87f")
    assert metadata["source_artifact"]["checksum_verified"] is True
    assert metadata["source_artifact"]["sha256"] == script.canonical.sha256(canonical_dir / "role_occurrence.parquet")
    for split, expected in (("train", 14), ("validation", 3), ("test", 3)):
        assert len(real(out / metadata["output_paths"][split])) == expected
    manifest = (out / "SHA256SUMS").read_text().splitlines()
    assert [line.split("  ")[1] for line in manifest] == sorted(script.CHECKED_FILES)
    for line in manifest:
        digest, name = line.split("  ")
        assert script.canonical.sha256(out / name) == digest
    if shutil.which("shasum"):
        assert subprocess.run(["shasum", "-a", "256", "-c", "SHA256SUMS"], cwd=out,
                              capture_output=True).returncode == 0
    printed = capsys.readouterr().out
    assert "same_second" in printed and "reference_comparison" in printed and "SHA256SUMS" in printed
    assert not list(tmp_path.glob(".targets.*"))


def test_dirty_tree_refused_before_verification(tmp_path, monkeypatch):
    monkeypatch.setattr(script.canonical, "git_state", lambda repo: ("a" * 40, True))
    monkeypatch.setattr(script.canonical, "verify_output", lambda path: pytest.fail("must not verify"))
    assert script.build(tmp_path / "input", tmp_path / "out") == script.EXIT_REFUSED
    assert not (tmp_path / "out").exists()


def test_allow_dirty_records_local_build(canonical_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(script.canonical, "git_state", lambda repo: ("a" * 40, True))
    assert script.build(canonical_dir, tmp_path / "out", allow_dirty=True) == 0
    assert json.loads((tmp_path / "out/metadata.json").read_text())["build"]["code_dirty"] is True


def test_existing_output_refused_before_verification(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setattr(script.canonical, "verify_output", lambda path: pytest.fail("must not verify"))
    assert script.build(tmp_path / "input", out) == script.EXIT_REFUSED


@pytest.mark.parametrize("relative_output", [".", "child", ".."])
def test_output_cannot_modify_or_enclose_canonical(canonical_dir, monkeypatch, relative_output):
    assert run_build(canonical_dir, canonical_dir / relative_output, monkeypatch, force=True) == script.EXIT_REFUSED


def test_failed_verification_stops_before_loading_or_writing(canonical_dir, tmp_path, monkeypatch):
    (canonical_dir / "count_report.md").write_text("tampered")
    monkeypatch.setattr(script.pd, "read_parquet", lambda *a, **k: pytest.fail("must not load"))
    out = tmp_path / "new-parent/out"
    assert run_build(canonical_dir, out, monkeypatch) == script.EXIT_INVALID
    assert not out.parent.exists()


def test_force_replacement_and_deterministic_builds(canonical_dir, tmp_path, monkeypatch):
    out = tmp_path / "out"
    assert run_build(canonical_dir, out, monkeypatch) == 0
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    assert run_build(canonical_dir, out, monkeypatch, force=True) == 0
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before
    other = tmp_path / "another-path/out"
    assert run_build(canonical_dir, other, monkeypatch) == 0
    assert {p.name: p.read_bytes() for p in other.iterdir()} == before
    assert not list(tmp_path.glob(".out.*"))


@pytest.mark.parametrize("stage", ["build", "write", "checksums", "publish"])
def test_force_failure_keeps_existing_output(canonical_dir, tmp_path, monkeypatch, stage):
    out = tmp_path / "out"
    assert run_build(canonical_dir, out, monkeypatch) == 0
    before = {p.name: p.read_bytes() for p in out.iterdir()}

    def fail(*args, **kwargs):
        raise OSError("simulated failure")

    if stage == "build":
        monkeypatch.setattr(script, "build_targets", fail)
    elif stage == "write":
        monkeypatch.setattr(script, "write_target_tables", fail)
    elif stage == "checksums":
        real = script.canonical.sha256

        def fail_target_hash(path):
            if "tables" in Path(path).parts:
                return fail()
            return real(path)
        monkeypatch.setattr(script.canonical, "sha256", fail_target_hash)
    else:
        real = Path.rename

        def fail_install(self, destination):
            if self.name == "tables":
                return fail()
            return real(self, destination)
        monkeypatch.setattr(Path, "rename", fail_install)
    assert run_build(canonical_dir, out, monkeypatch, force=True) == script.EXIT_FAILED
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before
    assert not list(tmp_path.glob(".out.*"))


def test_cli_help_and_arguments(canonical_dir, tmp_path, monkeypatch):
    path = Path(script.__file__)
    result = subprocess.run([sys.executable, str(path), "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "--canonical-dir" in result.stdout and "--allow-dirty" in result.stdout
    monkeypatch.setattr(script, "build", lambda canonical_dir, out_dir, **kwargs: (
        0 if canonical_dir == Path("input") and out_dir == Path("output")
        and kwargs == {"force": True, "allow_dirty": True} else 99))
    assert script.main(["--canonical-dir", "input", "--out-dir", "output", "--force", "--allow-dirty"]) == 0
