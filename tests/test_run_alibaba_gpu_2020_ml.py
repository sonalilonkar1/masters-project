"""Task 7 PR1 runner tests: end-to-end on a fabricated Task 4 + Task 6 setup.

Confirms the runner-level leakage control (PR1 never opens test.parquet), a
complete locked decision manifest, and reloadable model artifacts.
"""

import importlib.util
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from canonical.schema import ALIBABA_GPU_2020_CAPABILITIES as PROFILE
from features.target_builder import build_targets, write_target_tables

from test_target_builder import make_roles


def _load(path_name, module_name):
    path = Path(__file__).resolve().parents[1] / "scripts" / path_name
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


baselines_runner = _load("run_alibaba_gpu_2020_baselines.py", "run_alibaba_gpu_2020_baselines")
ml_runner = _load("run_alibaba_gpu_2020_ml.py", "run_alibaba_gpu_2020_ml")


def _task4_dir(tmp_path):
    n = 90
    src = make_roles(n)
    src["workload_id"] = "wl-" + src["recurrence_key"].astype(str)
    src["requested_gpu"] = 1.0
    src["inst_num"] = np.where(np.arange(n) % 2 == 0, 1.0, 2.0)
    src["gpu_type"] = np.where(np.arange(n) % 2 == 0, "T4", "P100")
    src["gpu_type_spec"] = pd.Series([None if i % 3 else "specA" for i in range(n)], dtype="string")
    src["workload"] = pd.Series([None if i % 4 else "wlX" for i in range(n)], dtype="string")
    src["requested_cpu_unit"] = "percent_of_vcpu"
    src["requested_memory_unit"] = "gb"
    result = build_targets(src, PROFILE)
    out = tmp_path / "targets"
    write_target_tables(result, out)
    meta = json.loads((out / "metadata.json").read_text())
    meta["build"] = {"code_commit": "a" * 40, "code_dirty": False}
    meta["source_provenance"] = {"build": {"code_commit": "c2ae87f" + "0" * 33}}
    (out / "metadata.json").write_text(json.dumps(meta))
    (out / "SHA256SUMS").write_text("".join(
        f"{baselines_runner.canonical.sha256(out / name)}  {name}\n"
        for name in sorted(baselines_runner.targets_build.CHECKED_FILES)))
    return out


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    monkeypatch.setattr(baselines_runner.canonical, "git_state", lambda repo: ("b" * 40, False))
    targets = _task4_dir(tmp_path)
    baselines = tmp_path / "baselines"
    assert baselines_runner.run(targets, baselines) == baselines_runner.EXIT_OK
    return targets, baselines


def test_pr1_end_to_end_locks_manifest_and_never_reads_test(prepared, tmp_path, monkeypatch):
    targets, baselines = prepared
    out = tmp_path / "ml"

    reads: list[str] = []
    real = ml_runner.pd.read_parquet

    def record(path, *args, **kwargs):
        reads.append(Path(path).name)
        return real(path, *args, **kwargs)

    monkeypatch.setattr(ml_runner.pd, "read_parquet", record)
    monkeypatch.setattr(ml_runner.canonical, "git_state", lambda repo: ("b" * 40, False))
    assert ml_runner.run(targets, baselines, out) == ml_runner.EXIT_OK

    assert "test.parquet" not in reads
    assert "train.parquet" in reads and "validation.parquet" in reads

    produced = sorted(p.name for p in out.iterdir())
    assert produced == sorted(("SHA256SUMS", *ml_runner.OUTPUT_FILES))

    manifest = json.loads((out / "decision_manifest.json").read_text())
    for key in ("task6_selection", "task4_inputs", "selected_models", "model_hyperparameters",
                "model_artifacts", "feature_list", "missing_indicator_columns", "feature_order",
                "hybrid_rule", "negative_prediction_rule", "random_seed", "library_versions",
                "lock_timestamp_utc", "build"):
        assert key in manifest, f"manifest missing {key}"
    assert manifest["hybrid_rule"] == "max(ml_prediction, selected_task6_baseline)"
    assert manifest["primary_resource"] == "memory"
    assert manifest["cpu_result_semantics"] == "average_usage"
    assert manifest["any_resource_metric_reported"] is False
    assert set(manifest["selected_models"]) == {"cpu", "memory"}
    assert "dummy_mean" not in manifest["selected_models"].values()
    # Task 6 selects a history policy (never Request); exact policy depends on data.
    assert manifest["task6_selection"]["selected_policy"] in ("Mean", "P90", "P95", "P99")
    assert manifest["task4_inputs"]["task3_source_commit"].startswith("c2ae87f")

    for resource in ("cpu", "memory"):
        model = joblib.load(out / ml_runner.MODEL_FILES[resource])
        assert hasattr(model, "predict")
        assert ml_runner.canonical.sha256(out / ml_runner.MODEL_FILES[resource]) == \
            manifest["model_artifacts"][resource]["sha256"]


def test_pr1_validation_comparison_has_seven_policies(prepared, tmp_path, monkeypatch):
    targets, baselines = prepared
    out = tmp_path / "ml"
    monkeypatch.setattr(ml_runner.canonical, "git_state", lambda repo: ("b" * 40, False))
    assert ml_runner.run(targets, baselines, out) == ml_runner.EXIT_OK
    comparison = pd.read_csv(out / "validation_policy_comparison.csv")
    assert list(comparison["policy"]) == ["Request", "Mean", "P90", "P95", "P99", "ML", "Hybrid"]
    # No any-resource *metric* (the any_resource_metric_reported=False label is fine).
    assert "any_resource_violation" not in comparison.columns
    assert "any_resource_violation_pct" not in comparison.columns
    assert (comparison["cpu_result_semantics"] == "average_usage").all()


def test_pr1_refuses_tampered_task6_checksum(prepared, tmp_path, monkeypatch):
    targets, baselines = prepared
    df = pd.read_parquet(baselines / "recommendations_validation.parquet")
    df.to_parquet(baselines / "recommendations_validation.parquet", index=False)
    good = ml_runner.canonical.sha256(baselines / "recommendations_validation.parquet")
    (baselines / "SHA256SUMS").write_text(
        (baselines / "SHA256SUMS").read_text().replace(good, "0" * 64))
    monkeypatch.setattr(ml_runner.canonical, "git_state", lambda repo: ("b" * 40, False))
    assert ml_runner.run(targets, baselines, tmp_path / "ml") == ml_runner.EXIT_INVALID
