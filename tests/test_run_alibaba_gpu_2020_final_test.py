# tests/test_run_alibaba_gpu_2020_final_test.py

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load(path_name, module_name):
    path = Path(__file__).resolve().parents[1] / "scripts" / path_name
    spec = importlib.util.spec_from_file_location(
        module_name,
        path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load(
    "run_alibaba_gpu_2020_final_test.py",
    "run_alibaba_gpu_2020_final_test",
)


def _manifest(commit, dirty=False):
    return {"build": {"code_commit": commit, "code_dirty": dirty}}


def _dirs(tmp_path):
    dirs = [tmp_path / name for name in ("targets", "baselines", "ml")]
    for directory in dirs:
        directory.mkdir()
    return (*dirs, tmp_path / "final")


def _patch(monkeypatch, commit, manifest, decision_sha="d" * 64):
    monkeypatch.setattr(runner.canonical, "git_state", lambda repo: (commit, False))
    monkeypatch.setattr(
        runner, "_verify_pr1_lock", lambda *args: (manifest, {}, {}, decision_sha)
    )
    reads = []

    def fake_read(path, *args, **kwargs):
        reads.append(Path(path).name)
        raise AssertionError("Final test should not be opened")

    monkeypatch.setattr(runner.pd, "read_parquet", fake_read)
    return reads


def _log_entries(ml):
    log = ml / runner.RUN_LOG_NAME
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def test_dirty_pr1_build_is_refused_before_test_read(tmp_path, monkeypatch):
    targets, baselines, ml, out = _dirs(tmp_path)
    reads = _patch(monkeypatch, "c" * 40, _manifest("c" * 40, dirty=True))
    assert runner.run(targets, baselines, ml, out) == runner.EXIT_INVALID
    assert reads == [] and _log_entries(ml) == []


def test_pr1_built_at_other_commit_is_refused_before_test_read(tmp_path, monkeypatch):
    targets, baselines, ml, out = _dirs(tmp_path)
    reads = _patch(monkeypatch, "c" * 40, _manifest("e" * 40))
    assert runner.run(targets, baselines, ml, out) == runner.EXIT_INVALID
    assert reads == [] and _log_entries(ml) == []


def test_run_is_logged_before_test_is_opened(tmp_path, monkeypatch):
    targets, baselines, ml, out = _dirs(tmp_path)
    reads = _patch(monkeypatch, "c" * 40, _manifest("c" * 40))
    # fake_read fails the run after the log entry is written.
    assert runner.run(targets, baselines, ml, out) == runner.EXIT_FAILED
    assert reads == ["test.parquet"]
    entries = _log_entries(ml)
    assert len(entries) == 1
    assert entries[0]["decision_manifest_sha256"] == "d" * 64
    assert entries[0]["defect_rerun_reason"] is None


def test_second_run_to_new_out_dir_is_refused_before_test_read(tmp_path, monkeypatch):
    targets, baselines, ml, out = _dirs(tmp_path)
    _patch(monkeypatch, "c" * 40, _manifest("c" * 40))
    runner.run(targets, baselines, ml, out)
    reads = _patch(monkeypatch, "c" * 40, _manifest("c" * 40))
    assert runner.run(targets, baselines, ml, tmp_path / "other_final") == runner.EXIT_REFUSED
    assert reads == [] and len(_log_entries(ml)) == 1


def test_other_manifest_is_not_blocked_by_log(tmp_path, monkeypatch):
    targets, baselines, ml, out = _dirs(tmp_path)
    _patch(monkeypatch, "c" * 40, _manifest("c" * 40), decision_sha="d" * 64)
    runner.run(targets, baselines, ml, out)
    reads = _patch(monkeypatch, "c" * 40, _manifest("c" * 40), decision_sha="f" * 64)
    assert runner.run(targets, baselines, ml, tmp_path / "other_final") == runner.EXIT_FAILED
    assert reads == ["test.parquet"]


def test_defect_rerun_after_logged_run_is_allowed_and_logged(tmp_path, monkeypatch):
    targets, baselines, ml, out = _dirs(tmp_path)
    _patch(monkeypatch, "c" * 40, _manifest("c" * 40))
    runner.run(targets, baselines, ml, out)
    reads = _patch(monkeypatch, "c" * 40, _manifest("c" * 40))
    result = runner.run(
        targets, baselines, ml, tmp_path / "rerun",
        defect_rerun_reason="documented implementation bug",
    )
    assert result == runner.EXIT_FAILED  # proceeds to the test read
    assert reads == ["test.parquet"]
    entries = _log_entries(ml)
    assert len(entries) == 2
    assert entries[1]["defect_rerun_reason"] == "documented implementation bug"
    assert entries[1]["prior_runs"] == 1


def test_duplicate_fingerprint_is_refused_before_test_read(
    tmp_path,
    monkeypatch,
):
    targets = tmp_path / "targets"
    baselines = tmp_path / "baselines"
    ml = tmp_path / "ml"
    out = tmp_path / "final"

    for directory in (
        targets,
        baselines,
        ml,
        out,
    ):
        directory.mkdir()

    decision_sha = "d" * 64
    commit = "c" * 40
    fingerprint = f"{decision_sha}:{commit}"

    (out / "run_record.json").write_text(
        json.dumps({
            "run_fingerprint": fingerprint,
        })
    )

    monkeypatch.setattr(
        runner.canonical,
        "git_state",
        lambda repo: (commit, False),
    )
    monkeypatch.setattr(
        runner,
        "_verify_pr1_lock",
        lambda *args: (_manifest(commit), {}, {}, decision_sha),
    )

    reads = []

    def fake_read(path, *args, **kwargs):
        reads.append(Path(path).name)
        raise AssertionError(
            "Final test should not be opened"
        )

    monkeypatch.setattr(
        runner.pd,
        "read_parquet",
        fake_read,
    )

    assert (
        runner.run(
            targets,
            baselines,
            ml,
            out,
        )
        == runner.EXIT_REFUSED
    )
    assert reads == []


def test_real_test_is_not_read_when_pr1_verification_fails(
    tmp_path,
    monkeypatch,
):
    targets = tmp_path / "targets"
    baselines = tmp_path / "baselines"
    ml = tmp_path / "ml"
    out = tmp_path / "final"

    for directory in (
        targets,
        baselines,
        ml,
    ):
        directory.mkdir()

    monkeypatch.setattr(
        runner.canonical,
        "git_state",
        lambda repo: ("c" * 40, False),
    )

    def fail_lock(*args):
        raise runner.InputError("bad lock")

    monkeypatch.setattr(
        runner,
        "_verify_pr1_lock",
        fail_lock,
    )

    reads = []

    def fake_read(path, *args, **kwargs):
        reads.append(Path(path).name)
        raise AssertionError(
            "Final test should not be opened"
        )

    monkeypatch.setattr(
        runner.pd,
        "read_parquet",
        fake_read,
    )

    assert (
        runner.run(
            targets,
            baselines,
            ml,
            out,
        )
        == runner.EXIT_INVALID
    )
    assert reads == []


def test_defect_rerun_reason_requires_existing_output(
    tmp_path,
    monkeypatch,
):
    targets = tmp_path / "targets"
    baselines = tmp_path / "baselines"
    ml = tmp_path / "ml"
    out = tmp_path / "final"

    for directory in (
        targets,
        baselines,
        ml,
    ):
        directory.mkdir()

    monkeypatch.setattr(
        runner.canonical,
        "git_state",
        lambda repo: ("c" * 40, False),
    )
    monkeypatch.setattr(
        runner,
        "_verify_pr1_lock",
        lambda *args: (
            _manifest("c" * 40),
            {},
            {},
            "d" * 64,
        ),
    )

    assert (
        runner.run(
            targets,
            baselines,
            ml,
            out,
            defect_rerun_reason=(
                "documented implementation bug"
            ),
        )
        == runner.EXIT_REFUSED
    )


def test_pr1_then_pr2_end_to_end_runs_once(tmp_path, monkeypatch):
    import test_run_alibaba_gpu_2020_ml as pr1

    commit = "b" * 40
    monkeypatch.setattr(pr1.baselines_runner.canonical, "git_state", lambda repo: (commit, False))
    targets = pr1._task4_dir(tmp_path)
    baselines, ml = tmp_path / "baselines", tmp_path / "ml"
    assert pr1.baselines_runner.run(targets, baselines) == pr1.baselines_runner.EXIT_OK
    monkeypatch.setattr(pr1.ml_runner.canonical, "git_state", lambda repo: (commit, False))
    assert pr1.ml_runner.run(targets, baselines, ml) == pr1.ml_runner.EXIT_OK

    monkeypatch.setattr(runner.canonical, "git_state", lambda repo: (commit, False))
    out = tmp_path / "final"
    assert runner.run(targets, baselines, ml, out) == runner.EXIT_OK
    record = json.loads((out / "run_record.json").read_text())
    assert record["pr1_build"]["code_commit"] == commit
    assert record["prior_runs"] == 0
    assert len(_log_entries(ml)) == 1

    # A second run to a new folder, or a re-lock of the tested PR1 folder, is refused.
    assert runner.run(targets, baselines, ml, tmp_path / "again") == runner.EXIT_REFUSED
    assert not (tmp_path / "again").exists()
    assert pr1.ml_runner.run(targets, baselines, ml, force=True) == pr1.ml_runner.EXIT_REFUSED

    # A PR2 run at a later commit than the PR1 lock is refused before reading test.
    monkeypatch.setattr(runner.canonical, "git_state", lambda repo: ("e" * 40, False))
    assert runner.run(targets, baselines, ml, tmp_path / "later") == runner.EXIT_INVALID
