"""Task 6 runner tests: end-to-end on a fabricated Task 4 directory.

Covers the leakage controls that live in the runner rather than the module:
test is read with column selection (never its targets/statuses), the locked
selection record is written before test is opened, and test is never scored.
"""

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from canonical.schema import ALIBABA_GPU_2020_CAPABILITIES as PROFILE
from features.target_builder import build_targets, write_target_tables

from test_target_builder import make_roles


def _runner():
    path = Path(__file__).resolve().parents[1] / "scripts/run_alibaba_gpu_2020_baselines.py"
    spec = importlib.util.spec_from_file_location("run_alibaba_gpu_2020_baselines", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _runner()


@pytest.fixture
def targets_dir(tmp_path):
    """A small, valid Task 4 directory with a SHA256SUMS manifest."""
    source = make_roles(80)
    source["workload_id"] = "wl-" + source["recurrence_key"].astype(str)
    source["inst_num"] = 2
    result = build_targets(source, PROFILE)
    out = tmp_path / "targets"
    write_target_tables(result, out)
    # Add the metadata provenance the runner reads for commit tracking.
    metadata = json.loads((out / "metadata.json").read_text())
    metadata["build"] = {"code_commit": "a" * 40, "code_dirty": False}
    metadata["source_provenance"] = {"build": {"code_commit": "c2ae87f" + "0" * 33}}
    (out / "metadata.json").write_text(json.dumps(metadata))
    manifest = "".join(
        f"{runner.canonical.sha256(out / name)}  {name}\n"
        for name in sorted(runner.targets_build.CHECKED_FILES)
    )
    (out / "SHA256SUMS").write_text(manifest)
    return out


def run_ok(targets_dir, out_dir, monkeypatch):
    monkeypatch.setattr(runner.canonical, "git_state", lambda repo: ("b" * 40, False))
    return runner.run(targets_dir, out_dir)


def test_end_to_end_produces_all_artifacts(targets_dir, tmp_path, monkeypatch):
    out = tmp_path / "baselines"
    assert run_ok(targets_dir, out, monkeypatch) == runner.EXIT_OK
    produced = sorted(p.name for p in out.iterdir())
    assert produced == sorted(("SHA256SUMS", *runner.OUTPUT_FILES))

    selection = json.loads((out / "baseline_selection.json").read_text())
    assert selection["selected_policy"] in ("Request", "Mean", "P90", "P95", "P99")
    assert selection["selected_min_runs"] in (1, 3, 5, 10)
    assert selection["sort_order"][0] == "memory_violation_pct"
    assert selection["source_artifacts"]["task3_source_commit"].startswith("c2ae87f")
    assert selection["source_artifacts"]["task4_code_commit"] == "a" * 40

    metadata = json.loads((out / "metadata.json").read_text())
    assert metadata["primary_resource"] == "memory"
    assert metadata["cpu_result_semantics"] == "average_usage"
    assert metadata["any_resource_metric_reported"] is False
    assert metadata["selected_policy"] == selection["selected_policy"]

    # Manifest verifies.
    for line in (out / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        assert runner.canonical.sha256(out / name) == digest


def test_test_recommendations_carry_no_targets_or_metrics(targets_dir, tmp_path, monkeypatch):
    out = tmp_path / "baselines"
    assert run_ok(targets_dir, out, monkeypatch) == runner.EXIT_OK
    test_recs = pd.read_parquet(out / "recommendations_test.parquet")
    for forbidden in (*runner.TEST_FORBIDDEN_COLUMNS, "cpu_violation", "memory_violation", "policy_name"):
        assert forbidden not in test_recs.columns
    # The locked recommendation columns are present.
    assert "rec_memory_selected" in test_recs.columns
    assert (test_recs["selected_baseline_policy"] == test_recs["selected_baseline_policy"].iloc[0]).all()


def test_test_split_is_read_with_column_selection_after_lock(targets_dir, tmp_path, monkeypatch):
    out = tmp_path / "baselines"
    reads: list[tuple[str, tuple[str, ...] | None]] = []
    real = runner.pd.read_parquet

    def record(path, *args, columns=None, **kwargs):
        reads.append((Path(path).name, tuple(columns) if columns is not None else None))
        return real(path, *args, columns=columns, **kwargs)

    monkeypatch.setattr(runner.pd, "read_parquet", record)
    assert run_ok(targets_dir, out, monkeypatch) == runner.EXIT_OK

    test_reads = [cols for name, cols in reads if name == "test.parquet"]
    assert test_reads, "test.parquet was never read"
    for cols in test_reads:
        assert cols is not None, "test.parquet must be read with explicit column selection"
        for forbidden in runner.TEST_FORBIDDEN_COLUMNS:
            assert forbidden not in cols

    # train/validation are read before test (selection happens before test).
    order = [name for name, _ in reads if name in ("train.parquet", "validation.parquet", "test.parquet")]
    assert order.index("train.parquet") < order.index("test.parquet")
    assert order.index("validation.parquet") < order.index("test.parquet")


def test_rerun_with_force_reproduces_selection(targets_dir, tmp_path, monkeypatch):
    out = tmp_path / "baselines"
    assert run_ok(targets_dir, out, monkeypatch) == runner.EXIT_OK
    first = json.loads((out / "baseline_selection.json").read_text())
    comparison_first = pd.read_csv(out / "validation_comparison.csv")

    monkeypatch.setattr(runner.canonical, "git_state", lambda repo: ("b" * 40, False))
    assert runner.run(targets_dir, out, force=True) == runner.EXIT_OK
    second = json.loads((out / "baseline_selection.json").read_text())
    comparison_second = pd.read_csv(out / "validation_comparison.csv")

    assert first["selected_policy"] == second["selected_policy"]
    assert first["selected_min_runs"] == second["selected_min_runs"]
    pd.testing.assert_frame_equal(comparison_first, comparison_second)


def test_missing_manifest_is_invalid_input(tmp_path, monkeypatch):
    empty = tmp_path / "targets"
    empty.mkdir()
    monkeypatch.setattr(runner.canonical, "git_state", lambda repo: ("b" * 40, False))
    assert runner.run(empty, tmp_path / "out") == runner.EXIT_INVALID


def test_tampered_target_checksum_is_invalid_input(targets_dir, tmp_path, monkeypatch):
    # Corrupt validation.parquet after the manifest was written.
    df = pd.read_parquet(targets_dir / "validation.parquet")
    df.to_parquet(targets_dir / "validation.parquet", index=False)
    (targets_dir / "SHA256SUMS").write_text(
        (targets_dir / "SHA256SUMS").read_text().replace(
            runner.canonical.sha256(targets_dir / "validation.parquet"), "0" * 64
        )
    )
    monkeypatch.setattr(runner.canonical, "git_state", lambda repo: ("b" * 40, False))
    assert runner.run(targets_dir, tmp_path / "out") == runner.EXIT_INVALID
