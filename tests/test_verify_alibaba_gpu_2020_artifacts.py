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

def test_sensitivity_numeric_contract_allows_structural_nulls():
    rows = []

    sensitivities = (
        "occurrence_weighted",
        "same_second_excluded",
        "same_second_only",
        "multi_instance",
        "group_weighted",
    )

    for sensitivity_name in sensitivities:
        for policy in v.FINAL_POLICIES:
            group_weighted = sensitivity_name == "group_weighted"

            rows.append({
                "sensitivity": sensitivity_name,
                "policy": policy,
                "row_count": 100,
                "valid_cpu_violation_count": (
                    None if group_weighted else 99
                ),
                "valid_memory_violation_count": (
                    None if group_weighted else 100
                ),
                "valid_cpu_utilization_count": (
                    None if group_weighted else 99
                ),
                "valid_memory_utilization_count": (
                    None if group_weighted else 100
                ),
                "cpu_violation_pct": 1.0,
                "memory_violation_pct": 2.0,
                "average_cpu_utilization": 0.5,
                "average_memory_utilization": 0.6,
                "average_cpu_waste": 10.0,
                "average_memory_waste": 2.0,
                "average_cpu_shortfall": 1.0,
                "average_memory_shortfall": 0.2,
                "cpu_result_semantics": "average_usage",
                "primary_resource": "memory",
                "any_resource_metric_reported": False,
                "n_groups": 25 if group_weighted else None,
            })

    frame = pd.DataFrame(rows)

    checks = v._validate_sensitivity(frame)

    finite_check = next(
        check
        for check in checks
        if check.name == "task7_pr2.sensitivity.numeric_finite"
    )

    assert finite_check.ok, finite_check.detail

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

def test_run_captures_reproduction_metadata_before_writing_outputs(
    tmp_path, monkeypatch
):
    out_dir = tmp_path / "verification"
    observed = {}

    def fake_reproduction_metadata(repo):
        observed["files_exist_when_called"] = list(out_dir.glob("*"))
        return {
            "dataset_id": v.DATASET_ID,
            "schema_version": v.SCHEMA_VERSION,
            "python_version": "test",
            "pandas_version": "test",
            "code_commit": "abc",
            "code_dirty": False,
            "verification_command": "test",
            "full_test_command": "test",
            "generated_utc": "2026-11-15T00:00:00Z",
        }

    monkeypatch.setattr(
        v,
        "reproduction_metadata",
        fake_reproduction_metadata,
    )

    monkeypatch.setattr(
        v,
        "verify_pipeline",
        lambda *args: (
            [],
            {
                "verified": True,
                "verification_timestamp_utc": "2026-11-15T00:00:00Z",
                "dataset_id": v.DATASET_ID,
                "schema_version": v.SCHEMA_VERSION,
                "decision_manifest_sha256": "d" * 64,
                "final_run_identity": {
                    "run_id": "test-run-id",
                    "code_commit": "abc",
                    "decision_manifest_sha256": "d" * 64,
                    "timestamp_utc": "2026-11-15T00:00:00Z",
                },
                "unverified_items": [],
            },
        ),
    )

    args = v.argparse.Namespace(
        canonical_dir=tmp_path / "canonical",
        targets_dir=tmp_path / "targets",
        baselines_dir=tmp_path / "baselines",
        ml_dir=tmp_path / "ml",
        final_dir=tmp_path / "final",
        out_dir=out_dir,
        force=True,
    )

    assert v.run(args) == v.EXIT_OK
    assert observed["files_exist_when_called"] == []

def test_final_policy_order_is_frozen():
    assert v.FINAL_POLICIES == (
        "Request", "Mean", "P90", "P95", "P99", "ML", "Hybrid"
    )


def test_checksum_binding_rejects_rechecksummed_inconsistent_artifact(tmp_path):
    d = tmp_path / "stage"
    d.mkdir()
    artifact = d / "feature_order.json"
    artifact.write_text('{"features":["a"]}\n')
    locked = {"feature_order.json": v.sha256(artifact)}

    artifact.write_text('{"features":["b"]}\n')
    _write_sha(d, ["feature_order.json"])

    check = v._checksum_binding_check("x", d, locked)
    assert not check.ok
    assert "expected" in check.detail


def test_policy_comparison_rejects_invalid_numeric_data():
    frame = pd.DataFrame({
        "policy": list(v.FINAL_POLICIES),
        "valid_cpu_violation_count": [10] * 7,
        "valid_memory_violation_count": [10] * 7,
        "cpu_result_semantics": ["average_usage"] * 7,
        "primary_resource": ["memory"] * 7,
        "cpu_violation_pct": [0, 1, 2, 3, 4, 5, 101],
    })
    checks = v._validate_policy_comparison(frame)
    assert any(c.name == "task7_pr2.comparison.numeric_bounds" and not c.ok for c in checks)


def test_sensitivity_requires_exact_five_by_seven_contract():
    rows = []

    for scenario in range(5):
        for policy in v.FINAL_POLICIES:
            rows.append({
                "scenario": f"s{scenario}",
                "policy": policy,
            })

    frame = pd.DataFrame(rows)

    checks = v._validate_sensitivity(frame)

    row_count_check = next(
        check
        for check in checks
        if check.name == "task7_pr2.sensitivity_row_count"
    )

    policy_coverage_check = next(
        check
        for check in checks
        if check.name == "task7_pr2.sensitivity_policy_coverage"
    )

    exact_groups_check = next(
        check
        for check in checks
        if check.name == "task7_pr2.sensitivity_exact_groups"
    )

    assert row_count_check.ok, row_count_check.detail
    assert policy_coverage_check.ok, policy_coverage_check.detail
    assert exact_groups_check.ok, exact_groups_check.detail


def test_prediction_inspection_reads_only_non_target_metadata_columns(tmp_path, monkeypatch):
    path = tmp_path / "predictions.parquet"
    pd.DataFrame({
        "role_key": ["r"],
        "recurrence_key": ["x"],
        "recommended_cpu_unit": ["percent_of_vcpu"],
        "recommended_memory_unit": ["gb"],
        "recommended_resource_scope": ["task_role_per_instance"],
        "secret_target": [999.0],
    }).to_parquet(path, index=False)

    real_read = pd.read_parquet
    observed = {}

    def guarded_read(path_arg, *args, **kwargs):
        observed["columns"] = kwargs.get("columns")
        return real_read(path_arg, *args, **kwargs)

    monkeypatch.setattr(v.pd, "read_parquet", guarded_read)
    checks = v._prediction_schema_checks(path)
    assert all(c.ok for c in checks)
    assert observed["columns"] == [
        "recommended_cpu_unit",
        "recommended_memory_unit",
        "recommended_resource_scope",
    ]
    assert "secret_target" not in observed["columns"]


def test_malformed_timestamps_become_failed_checks_not_exceptions(tmp_path):
    log = tmp_path / "final_test_runs.jsonl"
    decision_sha = "d" * 64
    run_id = "run-1"
    entry = {
        "decision_manifest_sha256": decision_sha,
        "code_commit": "c" * 40,
        "run_id": run_id,
        "timestamp_utc": "not-a-time",
        "defect_rerun_reason": None,
        "out_dir": str((tmp_path / "final_test").resolve()),
    }
    log.write_text(json.dumps(entry) + "\n")

    checks = v._check_run_history(
        run_record=entry,
        decision={
            "build": {"code_commit": "c" * 40},
            "lock_timestamp_utc": "2026-11-10T23:10:00Z",
        },
        decision_sha=decision_sha,
        run_log_path=log,
        final_dir=tmp_path / "final_test",
    )
    assert any(c.name == "task7.run_log_precedes_run_record" and not c.ok for c in checks)
    assert any(c.name == "task7.final_run_chronology" and not c.ok for c in checks)


def test_final_metadata_overlap_detects_inconsistency():
    check = v._overlap_consistency_check(
        "x",
        {"run_id": "a", "selected_min_runs": 10},
        {"run_id": "b", "selected_min_runs": 10},
        ("run_id", "selected_min_runs"),
    )
    assert not check.ok
    assert "run_id" in check.detail


def test_published_evidence_is_required_and_must_match(tmp_path, monkeypatch):
    ml_dir = tmp_path / "ml"
    final_dir = tmp_path / "final"
    report_root = tmp_path / "reports"
    report_ml = report_root / "ml"
    report_final = report_root / "final_test"
    for d in (ml_dir, final_dir, report_ml, report_final):
        d.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(v, "DEFAULT_ML_DIR", ml_dir)
    monkeypatch.setattr(v, "DEFAULT_FINAL_DIR", final_dir)
    monkeypatch.setattr(v, "REPORT_ROOT", report_root)
    monkeypatch.setattr(v, "PUBLISHED_ML_REQUIRED_FILES", {"decision_manifest.json"})
    monkeypatch.setattr(v, "PUBLISHED_FINAL_REQUIRED_FILES", {"run_record.json"})

    (ml_dir / "decision_manifest.json").write_text('{"x":1}\n')
    (final_dir / "run_record.json").write_text('{"x":1}\n')
    (report_ml / "decision_manifest.json").write_text('{"x":1}\n')
    (report_final / "run_record.json").write_text('{"x":2}\n')

    checks = v._published_evidence_checks(ml_dir, final_dir)
    assert checks[0].ok
    assert not checks[1].ok


def test_standalone_script_import_bootstraps_repo_before_scripts_import():
    source = (Path(__file__).resolve().parents[1] / "scripts" / "verify_alibaba_gpu_2020_artifacts.py").read_text()
    bootstrap = source.index('REPO_ROOT = Path(__file__).resolve().parents[1]')
    scripts_import = source.index('from scripts.build_alibaba_gpu_2020_targets import EXIT_INVALID')
    assert bootstrap < scripts_import
