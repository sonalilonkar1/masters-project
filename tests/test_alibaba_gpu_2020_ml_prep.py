import numpy as np
import pandas as pd
import pytest

from src.features.alibaba_gpu_2020_feature_config import (
    ALIBABA_GPU_2020_FEATURES,
    ALIBABA_GPU_2020_LEAKY_COLUMNS,
)
from src.features.alibaba_gpu_2020_ml_prep import (
    add_history_missing_indicators,
    clip_negative_predictions,
    select_resource_training_rows,
)
from src.features.ml_prep import validate_features


def test_alibaba_leaky_columns_are_not_features():
    assert (
        set(ALIBABA_GPU_2020_FEATURES)
        & set(ALIBABA_GPU_2020_LEAKY_COLUMNS)
        == set()
    )


def test_validate_features_rejects_alibaba_leaky_column():
    df = pd.DataFrame(
        {
            "requested_cpu": [1.0],
            "actual_cpu": [2.0],
        }
    )

    with pytest.raises(ValueError):
        validate_features(
            df,
            ["requested_cpu", "actual_cpu"],
            "train",
            leaky_columns=ALIBABA_GPU_2020_LEAKY_COLUMNS,
        )


def test_missing_history_and_zero_are_distinguishable():
    df = pd.DataFrame(
        {
            "cpu_history_mean": [np.nan, 0.0],
            "cpu_history_p90": [1.0, 1.0],
            "cpu_history_p95": [1.0, 1.0],
            "cpu_history_p99": [1.0, 1.0],
            "memory_history_mean": [1.0, 1.0],
            "memory_history_p90": [1.0, 1.0],
            "memory_history_p95": [1.0, 1.0],
            "memory_history_p99": [1.0, 1.0],
        }
    )

    result = add_history_missing_indicators(df)

    assert result.loc[
        0,
        "cpu_history_mean_missing",
    ] == 1

    assert result.loc[
        1,
        "cpu_history_mean_missing",
    ] == 0


def test_cpu_and_memory_training_rows_are_independent():
    df = pd.DataFrame(
        {
            "cpu_target_status": [
                "missing",
                "available",
            ],
            "memory_target_status": [
                "available",
                "available",
            ],
            "actual_cpu": [
                np.nan,
                50.0,
            ],
            "actual_memory": [
                10.0,
                20.0,
            ],
        }
    )

    cpu = select_resource_training_rows(
        df,
        "cpu",
    )
    memory = select_resource_training_rows(
        df,
        "memory",
    )

    assert len(cpu) == 1
    assert len(memory) == 2


def test_negative_predictions_are_clipped_and_counted():
    predictions = np.array(
        [-2.0, 0.0, 3.0]
    )

    clipped, count = clip_negative_predictions(
        predictions
    )

    assert count == 1
    assert clipped.tolist() == [
        0.0,
        0.0,
        3.0,
    ]