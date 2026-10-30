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
        lambda *args: ({}, {}, {}, decision_sha),
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
            {},
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
