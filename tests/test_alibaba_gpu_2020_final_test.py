# tests/test_alibaba_gpu_2020_final_test.py

from __future__ import annotations

import pandas as pd
import pytest

from canonical.schema import ALIBABA_GPU_2020_CAPABILITIES as PROFILE
from models import alibaba_gpu_2020_final_test as ft
from models import alibaba_gpu_2020_select as sel


def _locked_manifest(feature_order):
    return {
        "task": "task7_alibaba_gpu_2020_ml_hybrid",
        "phase": "pr1_validation_lock",
        "task6_selection": {
            "selected_policy": "P99",
            "selected_min_runs": 10,
        },
        "task4_inputs": {
            "targets_manifest": {
                "test.parquet": "x",
            }
        },
        "selected_models": {
            "cpu": "fake",
            "memory": "fake",
        },
        "model_artifacts": {
            "cpu": {
                "file": "cpu_model.joblib",
                "sha256": "x",
            },
            "memory": {
                "file": "memory_model.joblib",
                "sha256": "y",
            },
        },
        "feature_order": list(feature_order),
        "hybrid_rule": sel.HYBRID_RULE,
        "negative_prediction_rule": sel.NEGATIVE_PREDICTION_RULE,
        "cpu_result_semantics": "average_usage",
        "primary_resource": "memory",
        "any_resource_metric_reported": False,
    }


def test_validate_locked_manifest_rejects_changed_hybrid_rule():
    manifest = _locked_manifest(["requested_cpu"])
    manifest["hybrid_rule"] = "something_else"

    with pytest.raises(ValueError, match="Hybrid"):
        ft.validate_locked_manifest(manifest)


def test_prepare_locked_test_features_uses_locked_order(
    monkeypatch,
):
    rows = pd.DataFrame({
        "role_key": ["r1", "r2"],
        "actual_cpu": [1.0, 2.0],
    })
    history = pd.DataFrame({
        "role_key": ["r1", "r2"],
    })

    prepared = pd.DataFrame({
        "role_key": ["r1", "r2"],
        "actual_cpu": [1.0, 2.0],
    })
    encoded = pd.DataFrame({
        "requested_cpu": [4.0, 8.0],
        "unexpected_new_dummy": [1.0, 1.0],
    })

    monkeypatch.setattr(
        ft,
        "attach_history_statistics",
        lambda r, h: prepared.copy(),
    )
    monkeypatch.setattr(
        ft,
        "add_history_missing_indicators",
        lambda r: r.copy(),
    )
    monkeypatch.setattr(
        ft,
        "validate_features",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        ft,
        "prepare_xy",
        lambda *args, **kwargs: (
            encoded.copy(),
            pd.Series([1.0, 2.0]),
        ),
    )

    X, returned_rows = ft.prepare_locked_test_features(
        rows,
        history,
        ["missing_locked_dummy", "requested_cpu"],
    )

    assert list(X.columns) == [
        "missing_locked_dummy",
        "requested_cpu",
    ]
    assert X["missing_locked_dummy"].tolist() == [0.0, 0.0]
    assert X["requested_cpu"].tolist() == [4.0, 8.0]
    assert len(returned_rows) == 2


def test_final_policies_are_exactly_seven():
    assert ft.FINAL_POLICIES == (
        "Request",
        "Mean",
        "P90",
        "P95",
        "P99",
        "ML",
        "Hybrid",
    )


def test_build_final_sensitivity_reports_all_required_cuts(
    monkeypatch,
):
    rows = pd.DataFrame({
        "next_occurrence_same_second": [
            False,
            True,
            False,
        ],
        "inst_num": [1, 2, 3],
    })

    monkeypatch.setattr(
        ft,
        "_score_policy",
        lambda subset, policy, evaluator,
        group_weighted=False: {
            "policy": policy,
            "row_count": len(subset),
            "cpu_result_semantics": "average_usage",
            "primary_resource": "memory",
            "any_resource_metric_reported": False,
        },
    )

    sensitivity = ft.build_final_sensitivity(
        rows,
        PROFILE,
    )

    assert set(sensitivity["sensitivity"]) == {
        "occurrence_weighted",
        "same_second_excluded",
        "same_second_only",
        "multi_instance",
        "group_weighted",
    }
    assert len(sensitivity) == 5 * 7
    assert set(sensitivity["policy"]) == set(
        ft.FINAL_POLICIES
    )
