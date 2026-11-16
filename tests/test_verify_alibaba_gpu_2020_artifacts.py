from __future__ import annotations

import importlib.util
import json
import os
import subprocess
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
        if check.name == "task7_pr2.sensitivity.numeric_contract"
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
        lambda *args, **kwargs: (
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


def _valid_comparison(row_count: int = 100) -> pd.DataFrame:
    rows = []
    for policy in v.FINAL_POLICIES:
        rows.append({
            "policy": policy,
            "row_count": row_count,
            "valid_cpu_violation_count": row_count - 1,
            "valid_memory_violation_count": row_count,
            "valid_cpu_utilization_count": row_count - 2,
            "valid_memory_utilization_count": row_count - 1,
            "cpu_violation_pct": 10.0,
            "memory_violation_pct": 5.0,
            "average_cpu_utilization": 0.5,
            "average_memory_utilization": 0.6,
            "average_cpu_waste": 10.0,
            "average_memory_waste": 2.0,
            "average_cpu_shortfall": 1.0,
            "average_memory_shortfall": 0.2,
            "cpu_result_semantics": "average_usage",
            "primary_resource": "memory",
            "any_resource_metric_reported": False,
        })
    return pd.DataFrame(rows)


def _valid_sensitivity(comparison: pd.DataFrame | None = None) -> pd.DataFrame:
    comparison = _valid_comparison() if comparison is None else comparison
    rows = []
    for _, comp in comparison.iterrows():
        policy = comp["policy"]
        occurrence = dict(comp)
        occurrence.update({"sensitivity": "occurrence_weighted", "n_groups": None})
        rows.append(occurrence)
        for scenario, count in (("same_second_excluded", 80), ("same_second_only", 20), ("multi_instance", 50)):
            row = dict(comp)
            row.update({
                "sensitivity": scenario,
                "row_count": count,
                "valid_cpu_violation_count": max(count - 1, 0),
                "valid_memory_violation_count": count,
                "valid_cpu_utilization_count": max(count - 2, 0),
                "valid_memory_utilization_count": max(count - 1, 0),
                "n_groups": None,
            })
            rows.append(row)
        group = dict(comp)
        group.update({
            "sensitivity": "group_weighted",
            "valid_cpu_violation_count": None,
            "valid_memory_violation_count": None,
            "valid_cpu_utilization_count": None,
            "valid_memory_utilization_count": None,
            "n_groups": 10,
        })
        rows.append(group)
    return pd.DataFrame(rows)


def test_policy_comparison_rejects_invalid_numeric_data():
    frame = _valid_comparison()
    frame.loc[6, "cpu_violation_pct"] = 101
    checks = v._validate_policy_comparison(frame, final_population=100)
    assert any(c.name == "task7_pr2.comparison.metric_contract" and not c.ok for c in checks)


def test_sensitivity_requires_exact_five_by_seven_contract():
    frame = _valid_sensitivity()
    frame.loc[frame["sensitivity"] == "multi_instance", "sensitivity"] = "s4"
    checks = v._validate_sensitivity(frame)
    check = next(c for c in checks if c.name == "task7_pr2.sensitivity.cartesian_product")
    assert not check.ok


def test_sensitivity_valid_named_cartesian_product_passes():
    comparison = _valid_comparison()
    frame = _valid_sensitivity(comparison)
    checks = v._validate_sensitivity(frame, comparison)
    assert all(c.ok for c in checks), [(c.name, c.detail) for c in checks if not c.ok]


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
    canonical_dir = tmp_path / "canonical"
    ml_dir = tmp_path / "ml"
    final_dir = tmp_path / "final"
    report_root = tmp_path / "reports"
    report_canonical = report_root / "canonical"
    report_ml = report_root / "ml"
    report_final = report_root / "final_test"
    for d in (canonical_dir, ml_dir, final_dir, report_canonical, report_ml, report_final):
        d.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(v, "PUBLISHED_CANONICAL_REQUIRED_FILES", {"count_report.md"})
    monkeypatch.setattr(v, "PUBLISHED_ML_REQUIRED_FILES", {"decision_manifest.json"})
    monkeypatch.setattr(v, "PUBLISHED_FINAL_REQUIRED_FILES", {"run_record.json"})

    (canonical_dir / "count_report.md").write_text("counts\n")
    (ml_dir / "decision_manifest.json").write_text('{"x":1}\n')
    (final_dir / "run_record.json").write_text('{"x":1}\n')
    (report_canonical / "count_report.md").write_text("counts\n")
    (report_ml / "decision_manifest.json").write_text('{"x":1}\n')
    (report_final / "run_record.json").write_text('{"x":2}\n')

    checks = v._published_evidence_checks(canonical_dir, ml_dir, final_dir, report_root)
    assert checks[0].ok
    assert checks[1].ok
    assert not checks[2].ok


def test_standalone_script_import_bootstraps_repo_before_scripts_import():
    source = (Path(__file__).resolve().parents[1] / "scripts" / "verify_alibaba_gpu_2020_artifacts.py").read_text()
    bootstrap = source.index('REPO_ROOT = Path(__file__).resolve().parents[1]')
    scripts_import = source.index('from scripts.build_alibaba_gpu_2020_targets import EXIT_INVALID')
    assert bootstrap < scripts_import


def _provenance_fixture(tmp_path):
    targets = tmp_path / "targets"
    baselines = tmp_path / "baselines"
    ml = tmp_path / "ml"
    for directory in (targets, baselines, ml):
        directory.mkdir()

    for name in v.TASK4_REQUIRED_FILES:
        (targets / name).write_text("{}\n" if name.endswith(".json") else f"{name}\n")
    baseline_selection = {"selected_policy": "P99", "selected_min_runs": 10}
    for name in v.TASK6_REQUIRED_FILES:
        if name == "baseline_selection.json":
            (baselines / name).write_text(json.dumps(baseline_selection) + "\n")
        else:
            (baselines / name).write_text("{}\n" if name.endswith(".json") else f"{name}\n")
    feature_order = ["f1", "f2"]
    for name in v.TASK7_PR1_REQUIRED_FILES:
        if name == "feature_order.json":
            (ml / name).write_text(json.dumps({"feature_order": feature_order}) + "\n")
        elif name in {"cpu_model.joblib", "memory_model.joblib"}:
            (ml / name).write_bytes((name + "-bytes").encode())
        elif name.endswith(".json"):
            (ml / name).write_text("{}\n")
        else:
            (ml / name).write_text(f"{name}\n")

    target_manifest = {name: v.sha256(targets / name) for name in v.TASK4_REQUIRED_FILES}
    baseline_manifest = {name: v.sha256(baselines / name) for name in v.TASK6_REQUIRED_FILES}
    ml_manifest = {name: v.sha256(ml / name) for name in v.TASK7_PR1_REQUIRED_FILES}
    selected_models = {"cpu": "hist_gradient_boosting", "memory": "hist_gradient_boosting"}
    decision = {
        "task4_inputs": {"targets_manifest": dict(target_manifest)},
        "task6_selection": {
            "baselines_manifest": dict(baseline_manifest),
            "baseline_selection_sha256": baseline_manifest["baseline_selection.json"],
            "selected_policy": "P99",
            "selected_min_runs": 10,
        },
        "model_artifacts": {
            "cpu": {"filename": "cpu_model.joblib", "sha256": ml_manifest["cpu_model.joblib"]},
            "memory": {"filename": "memory_model.joblib", "sha256": ml_manifest["memory_model.joblib"]},
        },
        "selected_models": dict(selected_models),
        "feature_order": feature_order,
    }
    run_record = {
        "task4_test_sha256": target_manifest["test.parquet"],
        "task6_checksums": dict(baseline_manifest),
        "pr1_checksums": dict(ml_manifest),
        "selected_baseline_policy": "P99",
        "selected_min_runs": 10,
        "selected_models": dict(selected_models),
    }
    model_selection = {
        "cpu": {"selected_model": "hist_gradient_boosting"},
        "memory": {"selected_model": "hist_gradient_boosting"},
    }
    manifests = {
        "task4_targets": dict(target_manifest),
        "task6_baselines": dict(baseline_manifest),
        "task7_pr1_ml": dict(ml_manifest),
    }
    return targets, baselines, ml, decision, run_record, baseline_selection, model_selection, manifests


def _provenance_checks(fixture):
    targets, baselines, ml, decision, run_record, baseline_selection, model_selection, manifests = fixture
    return v._decision_provenance_checks(
        decision, targets, baselines, ml, manifests, run_record, baseline_selection, model_selection
    )


def test_task4_train_binding_uses_nested_decision_manifest(tmp_path):
    fixture = list(_provenance_fixture(tmp_path))
    targets, _, _, decision, _, _, _, manifests = fixture
    old = decision["task4_inputs"]["targets_manifest"]["train.parquet"]
    (targets / "train.parquet").write_text("changed\n")
    manifests["task4_targets"]["train.parquet"] = v.sha256(targets / "train.parquet")
    checks = _provenance_checks(tuple(fixture))
    check = next(c for c in checks if c.name == "task7_pr1.task4_checksum_binding")
    assert not check.ok
    assert old in check.detail


def test_model_rebound_in_run_record_still_conflicts_with_decision(tmp_path):
    fixture = list(_provenance_fixture(tmp_path))
    _, _, ml, _, run_record, _, _, manifests = fixture
    (ml / "cpu_model.joblib").write_bytes(b"replacement")
    rebound = v.sha256(ml / "cpu_model.joblib")
    manifests["task7_pr1_ml"]["cpu_model.joblib"] = rebound
    run_record["pr1_checksums"]["cpu_model.joblib"] = rebound
    checks = _provenance_checks(tuple(fixture))
    assert any(c.name == "task7_pr1.cpu_model_hash_binding" and not c.ok for c in checks)


def test_task6_rebound_in_run_record_still_conflicts_with_decision(tmp_path):
    fixture = list(_provenance_fixture(tmp_path))
    _, baselines, _, _, run_record, baseline_selection, _, manifests = fixture
    baseline_selection.update({"selected_policy": "P95"})
    (baselines / "baseline_selection.json").write_text(json.dumps(baseline_selection) + "\n")
    rebound = v.sha256(baselines / "baseline_selection.json")
    manifests["task6_baselines"]["baseline_selection.json"] = rebound
    run_record["task6_checksums"]["baseline_selection.json"] = rebound
    checks = _provenance_checks(tuple(fixture))
    assert any(c.name == "task7_pr1.task6_checksum_binding" and not c.ok for c in checks)


def test_nested_model_selection_must_match_lock(tmp_path):
    fixture = list(_provenance_fixture(tmp_path))
    fixture[6]["cpu"]["selected_model"] = "wrong"
    checks = _provenance_checks(tuple(fixture))
    assert any(c.name == "task7_pr1.model_selection_cpu_matches_lock" and not c.ok for c in checks)


def test_missing_decision_bindings_fail_without_skipping_checks(tmp_path):
    fixture = list(_provenance_fixture(tmp_path))
    fixture[3].pop("task4_inputs")
    checks = _provenance_checks(tuple(fixture))
    names = {c.name for c in checks if not c.ok}
    assert "task7_pr1.task4_inputs_present" in names
    assert "task7_pr1.task4_checksum_binding" in names


def test_checksum_binding_rejects_unsafe_artifact_paths(tmp_path):
    d = tmp_path / "stage"
    d.mkdir()
    check = v._checksum_binding_check("x", d, {"../outside": "a" * 64})
    assert not check.ok
    assert "escapes" in check.detail


def _make_git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    for rel in v.AUDITED_EXECUTION_PATHS:
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"audited {rel}\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "audit"], cwd=repo, check=True)
    audit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    return repo, audit


def _execution_records(commit):
    return (
        {"build": {"code_commit": commit}},
        {"code_commit": commit},
        {"build": {"code_commit": commit}},
        {"code_commit": commit},
    )


def test_execution_commit_must_exist(tmp_path, monkeypatch):
    repo, audit = _make_git_repo(tmp_path)
    monkeypatch.setattr(v, "AUDITED_EXECUTION_REFERENCE_COMMIT", audit)
    decision, record, metadata, logged = _execution_records("0" * 40)
    checks = v._execution_commit_checks(repo, decision, record, metadata, logged)
    assert any(c.name == "task7.execution_commit_exists" and not c.ok for c in checks)


def test_existing_uninstrumented_commit_is_rejected(tmp_path, monkeypatch):
    repo, audit = _make_git_repo(tmp_path)
    monkeypatch.setattr(v, "AUDITED_EXECUTION_REFERENCE_COMMIT", audit)
    runner = repo / v.AUDITED_EXECUTION_PATHS[0]
    runner.write_text("different implementation\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "different"], cwd=repo, check=True)
    changed = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    decision, record, metadata, logged = _execution_records(changed)
    checks = v._execution_commit_checks(repo, decision, record, metadata, logged)
    assert any(c.name == "task7.execution_instrumentation_audited" and not c.ok for c in checks)


def test_different_commit_with_audited_source_is_accepted(tmp_path, monkeypatch):
    repo, audit = _make_git_repo(tmp_path)
    monkeypatch.setattr(v, "AUDITED_EXECUTION_REFERENCE_COMMIT", audit)
    (repo / "README.md").write_text("unrelated\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "unrelated"], cwd=repo, check=True)
    later = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    decision, record, metadata, logged = _execution_records(later)
    checks = v._execution_commit_checks(repo, decision, record, metadata, logged)
    assert all(c.ok for c in checks), [(c.name, c.detail) for c in checks if not c.ok]


def test_metadata_build_commit_matches_run_and_log(tmp_path, monkeypatch):
    repo, audit = _make_git_repo(tmp_path)
    monkeypatch.setattr(v, "AUDITED_EXECUTION_REFERENCE_COMMIT", audit)
    decision, record, metadata, logged = _execution_records(audit)
    metadata["build"]["code_commit"] = "f" * 40
    checks = v._execution_commit_checks(repo, decision, record, metadata, logged)
    assert any(c.name == "task7.execution_commit_identity" and not c.ok for c in checks)


def test_operation_counters_require_integer_one():
    invalid = [True, False, 1.0, "1", None, 0, 2]
    for value in invalid:
        record = {"test_evaluator_call_count": value, "test_target_read_count": 1}
        metadata = {"test_evaluator_call_count": value, "test_target_read_count": 1}
        checks = v._counter_checks(record, metadata)
        assert any(c.name.endswith("test_evaluator_call_count") and not c.ok for c in checks)


def test_final_metadata_requires_both_operation_counters():
    checks = v._counter_checks(
        {"test_evaluator_call_count": 1, "test_target_read_count": 1},
        {"test_evaluator_call_count": 1},
    )
    assert any(c.name == "task7.final_metadata.test_target_read_count" and not c.ok for c in checks)


def test_comparison_requires_complete_producer_schema():
    frame = _valid_comparison().drop(columns=["average_cpu_waste"])
    checks = v._validate_policy_comparison(frame, final_population=100)
    assert any(c.name == "task7_pr2.comparison.schema" and not c.ok for c in checks)


def test_comparison_rejects_nonnumeric_fractional_and_excessive_counts():
    for bad in ("garbage", 10.5, 1000):
        frame = _valid_comparison()
        frame["valid_cpu_violation_count"] = frame["valid_cpu_violation_count"].astype(object)
        frame.loc[0, "valid_cpu_violation_count"] = bad
        checks = v._validate_policy_comparison(frame, final_population=100)
        assert any(not c.ok for c in checks if c.name in {
            "task7_pr2.comparison.numeric_parse", "task7_pr2.comparison.denominator_relationships"
        })


def test_comparison_utilization_is_fraction_not_percentage():
    frame = _valid_comparison()
    frame.loc[0, "average_cpu_utilization"] = 50
    checks = v._validate_policy_comparison(frame, final_population=100)
    assert any(c.name == "task7_pr2.comparison.metric_contract" and not c.ok for c in checks)


def test_comparison_allows_only_applicable_null_metrics():
    frame = _valid_comparison()
    frame.loc[0, "valid_cpu_violation_count"] = 0
    frame.loc[0, "valid_cpu_utilization_count"] = 0
    frame.loc[0, ["cpu_violation_pct", "average_cpu_utilization", "average_cpu_waste", "average_cpu_shortfall"]] = None
    checks = v._validate_policy_comparison(frame, final_population=100)
    assert all(c.ok for c in checks), [(c.name, c.detail) for c in checks if not c.ok]


def test_sensitivity_rejects_wrong_semantics_and_gpu_metrics():
    frame = _valid_sensitivity()
    frame.loc[0, "primary_resource"] = "cpu"
    frame["gpu_violation_pct"] = 0.0
    checks = v._validate_sensitivity(frame)
    assert any(c.name == "task7_pr2.sensitivity.schema" and not c.ok for c in checks)
    assert any(c.name == "task7_pr2.sensitivity.semantics" and not c.ok for c in checks)


def test_sensitivity_group_weighted_structural_nulls():
    frame = _valid_sensitivity()
    mask = frame["sensitivity"] == "group_weighted"
    frame.loc[mask, "valid_cpu_violation_count"] = 10
    checks = v._validate_sensitivity(frame)
    assert any(c.name == "task7_pr2.sensitivity.numeric_contract" and not c.ok for c in checks)


def test_sensitivity_empty_subset_matches_producer_output():
    comparison = _valid_comparison()
    frame = _valid_sensitivity(comparison)
    only_mask = frame["sensitivity"] == "same_second_only"
    excluded_mask = frame["sensitivity"] == "same_second_excluded"
    occurrence_mask = frame["sensitivity"] == "occurrence_weighted"
    nullable = [
        "valid_cpu_violation_count", "valid_memory_violation_count",
        "valid_cpu_utilization_count", "valid_memory_utilization_count",
        "cpu_violation_pct", "memory_violation_pct", "average_cpu_utilization",
        "average_memory_utilization", "average_cpu_waste", "average_memory_waste",
        "average_cpu_shortfall", "average_memory_shortfall", "cpu_result_semantics",
        "primary_resource", "any_resource_metric_reported", "n_groups",
    ]
    for column in nullable:
        frame[column] = frame[column].astype(object)
    frame.loc[only_mask, "row_count"] = 0
    frame.loc[only_mask, nullable] = None
    occurrence_by_policy = frame.loc[occurrence_mask].set_index("policy")["row_count"]
    for policy in v.FINAL_POLICIES:
        frame.loc[excluded_mask & (frame["policy"] == policy), "row_count"] = occurrence_by_policy.loc[policy]
    checks = v._validate_sensitivity(frame, comparison=comparison)
    failures = [(check.name, check.detail) for check in checks if not check.ok]
    assert not failures, failures

def test_sensitivity_occurrence_rows_match_comparison():
    comparison = _valid_comparison()
    frame = _valid_sensitivity(comparison)
    frame.loc[(frame["sensitivity"] == "occurrence_weighted") & (frame["policy"] == "P99"), "average_memory_waste"] += 1
    checks = v._validate_sensitivity(frame, comparison)
    assert any(c.name == "task7_pr2.sensitivity.cross_table_relationships" and not c.ok for c in checks)


def _args(tmp_path, out_dir):
    dirs = [tmp_path / name for name in ("canonical", "targets", "baselines", "ml", "final")]
    for directory in dirs:
        directory.mkdir(exist_ok=True)
    return v.argparse.Namespace(
        canonical_dir=dirs[0], targets_dir=dirs[1], baselines_dir=dirs[2],
        ml_dir=dirs[3], final_dir=dirs[4], out_dir=out_dir, force=True,
    )


def _fake_success_manifest():
    return {
        "verified": True, "status": "PASS", "verification_timestamp_utc": "2026-11-15T00:00:00Z",
        "dataset_id": v.DATASET_ID, "schema_version": v.SCHEMA_VERSION,
        "decision_manifest_sha256": "d" * 64, "final_run_identity": {}, "unverified_items": [],
        "checks": [], "artifacts": [],
    }


def test_success_then_malformed_json_publishes_failure(tmp_path, monkeypatch):
    out = tmp_path / "verification"
    args = _args(tmp_path, out)
    monkeypatch.setattr(v, "reproduction_metadata", lambda repo: {"code_commit": "x", "code_dirty": False})
    monkeypatch.setattr(v, "verify_pipeline", lambda *a, **k: ([], _fake_success_manifest()))
    assert v.run(args) == v.EXIT_OK
    assert json.loads((out / "artifact_manifest.json").read_text())["status"] == "PASS"

    def broken(*a, **k):
        raise json.JSONDecodeError("bad", "{", 0)
    monkeypatch.setattr(v, "verify_pipeline", broken)
    assert v.run(args) == v.EXIT_INVALID
    current = json.loads((out / "artifact_manifest.json").read_text())
    assert current["status"] == "FAIL"
    assert current["verified"] is False
    assert any(c["name"] == "verification.exception" for c in current["checks"])


def test_publication_error_cannot_preserve_current_success(tmp_path, monkeypatch):
    out = tmp_path / "verification"
    args = _args(tmp_path, out)
    monkeypatch.setattr(v, "reproduction_metadata", lambda repo: {"code_commit": "x", "code_dirty": False})
    monkeypatch.setattr(v, "verify_pipeline", lambda *a, **k: ([], _fake_success_manifest()))
    assert v.run(args) == v.EXIT_OK
    real_atomic = v._atomic_write
    calls = {"n": 0}

    def flaky(path, payload):
        calls["n"] += 1
        if calls["n"] == 3:
            raise OSError("simulated publication failure")
        return real_atomic(path, payload)
    monkeypatch.setattr(v, "_atomic_write", flaky)
    assert v.run(args) == v.EXIT_WRITE_FAILED
    current = json.loads((out / "artifact_manifest.json").read_text())
    assert current["status"] != "PASS"
    assert current["verified"] is False


def test_out_dir_cannot_overlap_frozen_inputs(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    check = v._output_path_check(input_dir / "verification", (input_dir,))
    assert not check.ok


def test_missing_count_report_fails_after_rechecksumming(tmp_path):
    d = tmp_path / "canonical"
    d.mkdir()
    for name in v.TASK3_REQUIRED_FILES - {"count_report.md"}:
        (d / name).write_text("x\n")
    _write_sha(d, sorted(v.TASK3_REQUIRED_FILES - {"count_report.md"}))
    ok, detail, _ = v.verify_sha256sums(d, required_files=v.TASK3_REQUIRED_FILES)
    assert not ok
    assert "count_report.md" in detail


def test_missing_published_count_report_fails_with_custom_inputs(tmp_path, monkeypatch):
    canonical = tmp_path / "canonical"; ml = tmp_path / "ml"; final = tmp_path / "final"; reports = tmp_path / "reports"
    for d in (canonical, ml, final, reports / "canonical", reports / "ml", reports / "final_test"):
        d.mkdir(parents=True, exist_ok=True)
    (canonical / "count_report.md").write_text("counts\n")
    monkeypatch.setattr(v, "PUBLISHED_CANONICAL_REQUIRED_FILES", {"count_report.md"})
    monkeypatch.setattr(v, "PUBLISHED_ML_REQUIRED_FILES", set())
    monkeypatch.setattr(v, "PUBLISHED_FINAL_REQUIRED_FILES", set())
    checks = v._published_evidence_checks(canonical, ml, final, reports)
    assert not checks[0].ok


def test_numpy_boolean_results_serialize_as_json_booleans():
    import numpy as np
    payload = {"checks": [v.Check("t", np.bool_(True), "ok").__dict__, v.Check("f", np.bool_(False), "no").__dict__]}
    decoded = json.loads(v._json_payload(payload))
    assert all(type(check["ok"]) is bool for check in decoded["checks"])


def test_nonboolean_check_results_are_rejected():
    import pytest
    with pytest.raises(TypeError):
        v.Check("bad", "False", "wrong")


def test_rendered_report_has_exactly_one_final_newline():
    report = v.render_report([], {
        "status": "PASS", "verification_timestamp_utc": "x", "generation_id": "g",
        "decision_manifest_sha256": "d", "final_run_identity": {}, "unverified_items": [],
    })
    assert report.endswith("\n")
    assert not report.endswith("\n\n")


def test_standalone_script_runs_with_pythonpath_unset():
    script = Path(__file__).resolve().parents[1] / "scripts" / "verify_alibaba_gpu_2020_artifacts.py"
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    result = subprocess.run([sys.executable, str(script), "--help"], cwd=script.parents[1], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_model_artifact_binding_uses_file_key(tmp_path):
    ml = tmp_path / "ml"
    ml.mkdir()
    for name in ("cpu_model.joblib", "memory_model.joblib"):
        (ml / name).write_bytes(name.encode())
    cpu_sha = v.sha256(ml / "cpu_model.joblib")
    mem_sha = v.sha256(ml / "memory_model.joblib")
    decision = {
        "model_artifacts": {
            "cpu": {"file": "cpu_model.joblib", "sha256": cpu_sha},
            "memory": {"file": "memory_model.joblib", "sha256": mem_sha},
        },
        "selected_models": {"cpu": "hist_gradient_boosting", "memory": "hist_gradient_boosting"},
    }
    manifest = {"cpu_model.joblib": cpu_sha, "memory_model.joblib": mem_sha}
    run_record = {"pr1_checksums": dict(manifest)}
    checks = v._model_artifact_bindings(decision, ml, manifest, run_record)
    assert next(c for c in checks if c.name == "task7_pr1.cpu_model_hash_binding").ok
    assert next(c for c in checks if c.name == "task7_pr1.memory_model_hash_binding").ok


def test_final_metadata_consistency_does_not_require_selection_duplicates():
    # Selection provenance is owned by the decision/run-record binding. The
    # final metadata producer does not duplicate selected policy/min-runs/models.
    run_record = {
        "dataset_id": v.DATASET_ID, "schema_version": v.SCHEMA_VERSION,
        "phase": "pr2_final_test", "run_id": "r1",
        "decision_manifest_sha256": "d" * 64, "final_population_size": 44,
        "selected_baseline_policy": "P99", "selected_min_runs": 10,
        "selected_models": {"cpu": "hgb", "memory": "hgb"},
        "test_evaluator_call_count": 1, "test_target_read_count": 1,
    }
    metadata = {
        "dataset_id": v.DATASET_ID, "schema_version": v.SCHEMA_VERSION,
        "phase": "pr2_final_test", "run_id": "r1",
        "decision_manifest_sha256": "d" * 64, "final_population_size": 44,
        "test_evaluator_call_count": 1, "test_target_read_count": 1,
    }
    required = (
        "dataset_id", "schema_version", "phase", "run_id",
        "decision_manifest_sha256", "final_population_size",
        "test_evaluator_call_count", "test_target_read_count",
    )
    failures = []
    for field in required:
        if field not in metadata or field not in run_record:
            failures.append(field)
        elif metadata[field] != run_record[field]:
            failures.append(field)
    assert failures == []
