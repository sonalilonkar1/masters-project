from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd


def _load():
    import sys

    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "verify_alibaba_gpu_2020_artifacts.py"
    )
    spec = importlib.util.spec_from_file_location(
        "verify_a6",
        path,
    )
    module = importlib.util.module_from_spec(spec)

    # Required for dataclasses/type resolution during dynamic import.
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

    ok, _, _ = v.verify_sha256sums(d)
    assert ok

    (d / "a.txt").write_text("corrupted")
    ok, detail, _ = v.verify_sha256sums(d)
    assert not ok
    assert "expected" in detail


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


def test_render_report_marks_failures():
    checks = [
        v.Check("good", True, "ok"),
        v.Check("bad", False, "broken"),
    ]
    manifest = {"verification_timestamp_utc": "2026-01-01T00:00:00Z"}
    report = v.render_report(checks, manifest)
    assert "Result: **FAIL**" in report
    assert "`bad` | FAIL" in report


def test_final_policy_order_is_frozen():
    assert v.FINAL_POLICIES == (
        "Request", "Mean", "P90", "P95", "P99", "ML", "Hybrid"
    )
