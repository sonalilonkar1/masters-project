from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd

from .alibaba_gpu_2020_feature_config import (
    ALIBABA_GPU_2020_HISTORY_FEATURES,
)


def add_history_missing_indicators(
    df: pd.DataFrame,
) -> pd.DataFrame:
    result = df.copy()

    for column in ALIBABA_GPU_2020_HISTORY_FEATURES:
        if column not in result.columns:
            raise ValueError(
                f"Missing Task 6 history feature: {column}"
            )

        result[f"{column}_missing"] = (
            result[column].isna().astype("int8")
        )

    return result


def select_resource_training_rows(
    df: pd.DataFrame,
    resource: str,
) -> pd.DataFrame:
    if resource == "cpu":
        status_col = "cpu_target_status"
        target_col = "actual_cpu"
    elif resource == "memory":
        status_col = "memory_target_status"
        target_col = "actual_memory"
    else:
        raise ValueError(
            "resource must be 'cpu' or 'memory'"
        )

    required = [status_col, target_col]
    missing = [
        column
        for column in required
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )

    mask = df[status_col].eq("available")

    return df.loc[mask].copy()


def clip_negative_predictions(
    predictions: np.ndarray,
) -> Tuple[np.ndarray, int]:
    predictions = np.asarray(
        predictions,
        dtype=float,
    )

    negative_count = int(
        np.count_nonzero(predictions < 0)
    )

    clipped = np.clip(
        predictions,
        0,
        None,
    )

    return clipped, negative_count