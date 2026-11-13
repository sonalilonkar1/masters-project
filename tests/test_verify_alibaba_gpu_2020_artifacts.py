from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd


def _load():
    path = Path(__file__).resolve().parents[1] / "scripts" / "verify_alibaba_gpu_2020_artifacts.py"
    spec = importlib.util.spec_from_file_location("verify_a6", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v = _load()


def _write_sha(directory: Path, names: list[str]) -> None:
    (directory / "SHA256SUMS").write_text(
        "".join(f"{v.sha256(directory / name)}  {name}\n" for name in sorted(names))
    )


def test_verify_sha256sums_detects_corruption(tmp_path):
    d = tmp_path / "stage"
    d.mkdir()
    (d / "a.txt").write_text("original")
    _write_sha(d, ["a.txt"])

    ok, _, _ = v.verify_sha256sums(d, required_files={"a.txt"}, exact_files=True)
    assert ok

    (d / "a.txt").write_text("corrupted")
    ok, detail, _ = v.verify_sha256sums(d, required_files={"a.txt"}, exact_files=True)
    assert not ok
    assert "expected" in detail


def test_verify_sha256sums_rejects_empty_manifest(tmp_path):
    d = tmp_path / "stage"
    d.mkdir()
    (d / "SHA256SUMS").write_text("")
    ok, detail, recorded = v.verify_sha256sums(d, required_files={"required.txt"})
    assert not ok
    assert recorded == {}
    assert "empty SHA256SUMS" in detail


def test_verify_sha256sums_rejects_missing_required_artifact(tmp_path):
    d = tmp_path / "stage"
    d.mkdir()
    (d / "present.txt").write_text("ok")
    _write_sha(d, ["present.txt"])

    ok, detail, _ = v.verify_sha256sums(
        d,
        required_files={"present.txt", "required.txt"},
        exact_files=False,
    )
    assert not ok
    assert "required artifacts absent" in detail


def test_parquet_row_count_uses_metadata_not_pandas_read(tmp_path, monkeypatch):
    path = tmp_path / "test.parquet"
    pd.DataFrame({"secret_target": [1, 2, 3]}).to_parquet(path, index=False)

    def forbidden(*args, **kwargs):
        raise AssertionError("pd.read_parquet must not be used for row counts")

    monkeypatch.setattr(v.pd, "read_parquet", forbidden)
    assert v.artifact_row_count(path) == 3


def test_metadata_contract_requires_dataset_and_schema():
    checks = v._metadata_contract(
        {"dataset_id": v.DATASET_ID, "schema_version": v.SCHEMA_VERSION},
        "x",
    )
    assert all(c.ok for c in checks)

    checks = v._metadata_contract({"dataset_id": v.DATASET_ID}, "x")
    assert any(not c.ok and c.name.endswith("schema_version") for c in checks)


def test_forbidden_eval_columns_allows_label_but_rejects_metrics():
    assert v._forbidden_eval_columns([
        "policy",
        "any_resource_metric_reported",
        "cpu_violation_pct",
    ]) == []

    bad = v._forbidden_eval_columns([
        "any_resource_violation_pct",
        "gpu_violation_pct",
    ])
    assert bad == ["any_resource_violation_pct", "gpu_violation_pct"]


def test_run_history_cross_checks_run_record(tmp_path):
    log = tmp_path / "final_test_runs.jsonl"
    decision_sha = "d" * 64
    run_id = "run-1"
    entry = {
        "decision_manifest_sha256": decision_sha,
        "code_commit": "c" * 40,
        "run_id": run_id,
        "timestamp_utc": "2026-11-10T23:14:33Z",
        "defect_rerun_reason": None,
        "out_dir": str(
            (tmp_path / "final_test").resolve()
        ),
    }
    log.write_text(json.dumps(entry) + "\n")

    checks = v._check_run_history(
        run_record=entry,
        decision={
            "build": {
                "code_commit": "c" * 40,
            },
            "lock_timestamp_utc": "2026-11-10T23:10:00Z",
        },
        decision_sha=decision_sha,
        run_log_path=log,
        final_dir=tmp_path / "final_test",
    )
    assert all(check.ok for check in checks)


def test_run_history_fails_when_run_id_not_in_log(tmp_path):
    log = tmp_path / "final_test_runs.jsonl"
    decision_sha = "d" * 64
    logged = {
        "decision_manifest_sha256": decision_sha,
        "code_commit": "c" * 40,
        "run_id": "different-run",
        "timestamp_utc": "2026-11-10T23:14:33Z",
        "defect_rerun_reason": None,
    }
    log.write_text(json.dumps(logged) + "\n")
    record = dict(logged, run_id="reported-run")

    checks = v._check_run_history(
        run_record=record,
        decision={
            "build": {
                "code_commit": "c" * 40,
            },
            "lock_timestamp_utc": "2026-11-10T23:10:00Z",
        },
        decision_sha=decision_sha,
        run_log_path=log,
        final_dir=tmp_path / "final_test",
    )
    assert any(
        check.name == "task7.run_log_contains_final_run" and not check.ok
        for check in checks
    )


def test_render_report_marks_failures_and_limitations():
    checks = [
        v.Check("good", True, "ok"),
        v.Check("bad", False, "broken"),
    ]
    manifest = {
        "verification_timestamp_utc": "2026-01-01T00:00:00Z",
        "decision_manifest_sha256": "abc",
        "final_run_identity": {"run_id": "r1", "code_commit": "c1"},
        "unverified_items": v.UNVERIFIED_ITEMS,
    }
    report = v.render_report(checks, manifest)
    assert "Result: **FAIL**" in report
    assert "`bad` | FAIL" in report
    assert "Explicit verification limitations" in report
    assert "UNVERIFIED" in report


def test_final_policy_order_is_frozen():
    assert v.FINAL_POLICIES == (
        "Request", "Mean", "P90", "P95", "P99", "ML", "Hybrid"
    )
