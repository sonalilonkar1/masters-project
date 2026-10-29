from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple
import numpy as np
import pandas as pd

from .ml_prep import prepare_xy, validate_features
from .alibaba_gpu_2020_feature_config import (
    ALIBABA_GPU_2020_FEATURES,
    ALIBABA_GPU_2020_HISTORY_FEATURES,
    ALIBABA_GPU_2020_LEAKY_COLUMNS,
    HISTORY_JOIN_KEY,
    TARGET_CPU,
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


# ---------------------------------------------------------------------------
# History-statistics join and feature-matrix construction
# ---------------------------------------------------------------------------

def attach_history_statistics(
    rows: pd.DataFrame,
    history_statistics: pd.DataFrame,
) -> pd.DataFrame:
    """Left-join the Task 6 history statistics onto rows by role_key.

    Accepts the statistics either keyed by role_key on the index (the in-memory
    form) or with role_key as a column (the reloaded parquet). A role absent
    from the statistics leaves NaN values, which the missing indicators capture.
    """
    if HISTORY_JOIN_KEY not in rows.columns:
        raise ValueError(f"rows must contain {HISTORY_JOIN_KEY!r}")
    missing = [c for c in ALIBABA_GPU_2020_HISTORY_FEATURES if c not in history_statistics.columns]
    if missing:
        raise ValueError(f"history_statistics missing columns: {missing}")

    stats = history_statistics
    if HISTORY_JOIN_KEY not in stats.columns:
        stats = stats.reset_index()
    stats = stats[[HISTORY_JOIN_KEY, *ALIBABA_GPU_2020_HISTORY_FEATURES]]
    merged = rows.merge(stats, how="left", on=HISTORY_JOIN_KEY, validate="many_to_one")
    if len(merged) != len(rows):
        raise RuntimeError("History-statistics join changed the row count")
    return merged


def _sanitize_feature_name(name: str) -> str:
    """Replace characters XGBoost forbids in feature names ([, ], <, >)."""
    for bad in ("[", "]", "<", ">"):
        name = name.replace(bad, "_")
    return name


@dataclass(frozen=True)
class FeatureMatrices:
    """Aligned train/validation feature matrices and their source rows."""

    X_train: pd.DataFrame
    X_val: pd.DataFrame
    train_rows: pd.DataFrame
    val_rows: pd.DataFrame
    feature_order: list


def build_feature_matrices(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    history_statistics: pd.DataFrame,
) -> FeatureMatrices:
    """Encode train and validation into aligned feature matrices (no test).

    Attaches the Task 6 history statistics, adds missing indicators, runs the
    leakage check with the Alibaba leaky list, one-hot encodes categoricals, and
    reindexes validation to the training schema. The test frame is never touched.
    """
    train_feat = add_history_missing_indicators(attach_history_statistics(train, history_statistics))
    val_feat = add_history_missing_indicators(attach_history_statistics(validation, history_statistics))

    validate_features(train_feat, ALIBABA_GPU_2020_FEATURES, "train", leaky_columns=ALIBABA_GPU_2020_LEAKY_COLUMNS)
    validate_features(val_feat, ALIBABA_GPU_2020_FEATURES, "validation", leaky_columns=ALIBABA_GPU_2020_LEAKY_COLUMNS)

    X_train, _ = prepare_xy(train_feat, ALIBABA_GPU_2020_FEATURES, TARGET_CPU)
    X_val, _ = prepare_xy(val_feat, ALIBABA_GPU_2020_FEATURES, TARGET_CPU)
    X_val = X_val.reindex(columns=X_train.columns, fill_value=0)

    renamed = [_sanitize_feature_name(c) for c in X_train.columns]
    if len(set(renamed)) != len(renamed):
        raise ValueError("Feature-name sanitization produced a collision")
    X_train.columns = renamed
    X_val.columns = renamed

    X_train = X_train.astype("float64")
    X_val = X_val.astype("float64")

    return FeatureMatrices(
        X_train=X_train,
        X_val=X_val,
        train_rows=train_feat,
        val_rows=val_feat,
        feature_order=list(X_train.columns),
    )
