"""Task 7 PR1: feature-matrix, selection, and Hybrid tests (built on Sonali's
foundation + the merged Task 6 handoff). Synthetic fixtures only."""

import numpy as np
import pandas as pd
import pytest

from canonical.schema import ALIBABA_GPU_2020_CAPABILITIES as PROFILE
from features.target_builder import build_targets
from features import alibaba_gpu_2020_feature_config as fc
from features.alibaba_gpu_2020_ml_prep import build_feature_matrices
import baselines.alibaba_gpu_2020 as a6
import models.alibaba_gpu_2020_select as sel

from test_target_builder import make_roles


def _task4(n=90):
    src = make_roles(n)
    src["workload_id"] = "wl-" + src["recurrence_key"].astype(str)
    src["requested_gpu"] = 1.0
    src["inst_num"] = np.where(np.arange(n) % 2 == 0, 1.0, 2.0)
    src["gpu_type"] = np.where(np.arange(n) % 2 == 0, "T4", "P100")
    src["gpu_type_spec"] = pd.Series([None if i % 3 else "specA" for i in range(n)], dtype="string")
    src["workload"] = pd.Series([None if i % 4 else "wlX" for i in range(n)], dtype="string")
    src["requested_cpu_unit"] = "percent_of_vcpu"
    src["requested_memory_unit"] = "gb"
    return build_targets(src, PROFILE).rows


@pytest.fixture
def handoff():
    rows = _task4(90)
    train = rows[rows["split"] == "train"].reset_index(drop=True)
    val = rows[rows["split"] == "validation"].reset_index(drop=True)
    trainval = pd.concat([train, val], ignore_index=True)
    stats = a6.compute_history_statistics(trainval, PROFILE)
    selection = a6.BaselineSelection("P99", 10, a6.SELECTION_SORT_ORDER, {}, len(val))
    baselines_val = a6.build_locked_recommendations(val, stats, selection, PROFILE)
    return train, val, stats, baselines_val


def test_build_feature_matrices_aligned_float_no_leak(handoff):
    train, val, stats, _ = handoff
    m = build_feature_matrices(train, val, stats)
    assert list(m.X_train.columns) == list(m.X_val.columns) == m.feature_order
    assert (m.X_train.dtypes == "float64").all()
    for col in m.feature_order:
        assert not col.startswith(("actual_", "observed_", "peak_", "cpu_target", "memory_target"))
        assert col not in {"role_key", "occurrence_id", "recurrence_key", "workload_id", "split"}
    assert any(c.startswith("gpu_type") for c in m.feature_order)
    # The Task 6 history stats and their missing indicators are present.
    assert "hist_memory_p99" in m.feature_order
    assert "hist_memory_p99_missing" in m.feature_order


def test_feature_names_bind_to_task6_history_columns(stats_cols=fc.ALIBABA_GPU_2020_HISTORY_FEATURES):
    # The config history names must equal the Task 6 history_statistics columns.
    rows = _task4(30)
    stats = a6.compute_history_statistics(rows, PROFILE)
    for column in stats_cols:
        assert column in stats.columns


def test_compare_and_select_independent_and_dummy_not_selected(handoff):
    train, val, stats, _ = handoff
    m = build_feature_matrices(train, val, stats)
    table, selections, fitted = sel.compare_and_select(m, PROFILE)
    expected = set(sel.build_candidate_models().keys())
    for resource in ("cpu", "memory"):
        assert set(table[table.resource == resource]["model"]) == expected
        chosen = table[(table.resource == resource) & table.selected]
        assert len(chosen) == 1
        assert selections[resource].selected_model != "dummy_mean"  # floor, not selectable
    assert selections["cpu"].resource == "cpu" and selections["memory"].resource == "memory"
    assert selections["cpu"].selection_order[0] == "rmse"


def test_seven_policies_and_hybrid_reduces_violation(handoff):
    train, val, stats, baselines_val = handoff
    m = build_feature_matrices(train, val, stats)
    _, selections, fitted = sel.compare_and_select(m, PROFILE)
    result = sel.evaluate_validation_policies(m, baselines_val, selections, fitted, PROFILE)
    assert list(result.comparison["policy"]) == ["Request", "Mean", "P90", "P95", "P99", "ML", "Hybrid"]
    for resource in ("cpu", "memory"):
        assert np.all(result.hybrid_recommendations[resource] >= result.ml_predictions[resource] - 1e-9)
    # Profile labels carried into the comparison.
    assert (result.comparison["cpu_result_semantics"] == "average_usage").all()
    assert (result.comparison["primary_resource"] == "memory").all()


def test_refit_differs_from_train_only(handoff):
    train, val, stats, _ = handoff
    m = build_feature_matrices(train, val, stats)
    _, selections, fitted = sel.compare_and_select(m, PROFILE)
    refit = sel.refit_on_train_plus_validation(m, selections)
    for resource in ("cpu", "memory"):
        name = selections[resource].selected_model
        if name == "dummy_mean":
            continue
        train_only = np.maximum(fitted[resource][name].predict(m.X_val), 0)
        refit_pred = np.maximum(refit[resource].predict(m.X_val), 0)
        assert not np.allclose(train_only, refit_pred)
