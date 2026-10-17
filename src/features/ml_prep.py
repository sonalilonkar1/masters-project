# src/features/ml_prep.py
#
# Shared ML matrix construction and validation utilities.
# Extracted from subset-05-ml-prediction.ipynb so that
# Notebooks 5, 6, and any future ML notebooks use the same logic.

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit

# Relative import so the module works both as src.features.ml_prep
# (notebooks) and as features.ml_prep (pytest with pythonpath = src).
from .feature_config import (
    CATEGORICAL_FEATURES,
    FEATURE_COLS,
    LEAKY_COLUMNS,
    OCCURRENCE_FEATURE_COLS,
    OCCURRENCE_LEAKY_COLUMNS,
    OCCURRENCE_LEAKY_PREFIXES,
)


def prepare_xy(
    df: pd.DataFrame,
    feature_cols: List[str],
    target_col: str,
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Build a feature matrix X and target vector y from a DataFrame.

    - Selects the requested feature columns.
    - One-hot encodes categorical features (with a dummy column for NaN).
    - Fills remaining missing values with 0 for numeric features.

    Parameters
    ----------
    df : pd.DataFrame
        Source DataFrame containing feature and target columns.
    feature_cols : list[str]
        Columns to include as model inputs.
    target_col : str
        Column to use as the prediction target.

    Returns
    -------
    X : pd.DataFrame
        Encoded, NaN-filled feature matrix.
    y : pd.Series
        Target values aligned to X.
    """
    X = df[feature_cols].copy()
    y = df[target_col].copy()

    # One-hot encode categorical features
    X = pd.get_dummies(X, dummy_na=True)

    # Fill missing historical values
    X = X.fillna(0)

    return X, y


def build_aligned_matrices(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: List[str],
    target_col: str,
) -> Tuple[
    pd.DataFrame, pd.Series,
    pd.DataFrame, pd.Series,
    pd.DataFrame, pd.Series,
]:
    """
    Build ML-ready feature matrices for train, validation, and test splits.

    Training data defines the feature schema. Validation and test matrices
    are aligned to training columns only — extra columns are dropped and
    missing columns are filled with 0.

    Parameters
    ----------
    train_df, val_df, test_df : pd.DataFrame
        Source DataFrames for each split.
    feature_cols : list[str]
        Columns to include as model inputs.
    target_col : str
        Column to use as the prediction target.

    Returns
    -------
    X_train, y_train, X_val, y_val, X_test, y_test
        Aligned feature matrices and target vectors.
    """
    X_train, y_train = prepare_xy(train_df, feature_cols, target_col)
    X_val, y_val = prepare_xy(val_df, feature_cols, target_col)
    X_test, y_test = prepare_xy(test_df, feature_cols, target_col)

    # Training data defines the ML feature schema.
    # Validation/test are aligned to training only.
    train_cols = X_train.columns

    X_val = X_val.reindex(columns=train_cols, fill_value=0)
    X_test = X_test.reindex(columns=train_cols, fill_value=0)

    return X_train, y_train, X_val, y_val, X_test, y_test


def validate_features(
    df: pd.DataFrame,
    feature_cols: List[str],
    split_name: str,
    leaky_columns: Optional[List[str]] = None,
) -> None:
    """
    Validate that a DataFrame is ready for ML modeling.

    Checks:
    1. All expected feature columns are present.
    2. No leaky columns (current-execution fields) are in the DataFrame.
    3. No merge artifact columns (_x / _y suffixes) exist.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame to validate.
    feature_cols : list[str]
        Expected feature columns.
    split_name : str
        Name of the split (for error messages).
    leaky_columns : list[str], optional
        Columns that must not appear as features.
        Defaults to LEAKY_COLUMNS from feature_config.

    Raises
    ------
    ValueError
        If any validation check fails.
    """
    if leaky_columns is None:
        leaky_columns = LEAKY_COLUMNS

    # Check all expected features exist
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        raise ValueError(
            f"[{split_name}] Missing expected feature columns: {missing}"
        )

    # Check no leaky columns are present in the feature set
    leaky_found = [c for c in leaky_columns if c in feature_cols]
    if leaky_found:
        raise ValueError(
            f"[{split_name}] Leaky columns found in feature_cols: {leaky_found}"
        )

    # Check for merge artifact columns
    merge_artifacts = [
        c for c in df.columns
        if c.endswith("_x") or c.endswith("_y")
    ]
    if merge_artifacts:
        raise ValueError(
            f"[{split_name}] Merge artifact columns found: {merge_artifacts}"
        )

    print(f"[{split_name}] Feature validation passed — "
          f"{len(feature_cols)} features, no leaks, no merge artifacts.")


def get_available_features(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: Optional[List[str]] = None,
) -> List[str]:
    """
    Return the canonical ML feature list only if all expected features
    are present in every split.

    The standardized feature schema must remain identical across train,
    validation, and test. Missing canonical features therefore raise an
    error instead of being silently dropped.
    """
    if feature_cols is None:
        feature_cols = FEATURE_COLS

    missing_by_split = {
        "train": [
            c for c in feature_cols
            if c not in train_df.columns
        ],
        "val": [
            c for c in feature_cols
            if c not in val_df.columns
        ],
        "test": [
            c for c in feature_cols
            if c not in test_df.columns
        ],
    }

    missing_by_split = {
        split: missing
        for split, missing in missing_by_split.items()
        if missing
    }

    if missing_by_split:
        details = "; ".join(
            f"{split}: {missing}"
            for split, missing in missing_by_split.items()
        )

        raise ValueError(
            "Canonical ML feature schema mismatch. "
            f"Missing features -> {details}"
        )

    print(
        f"Using canonical ML feature schema: "
        f"{len(feature_cols)} features"
    )

    return list(feature_cols)

# ===========================================================================
# Google subset occurrence-level helpers (pipelines/google_subset, N05+)
# ===========================================================================
# Unlike prepare_xy above, these helpers never fill missing values: NaN means
# "unknown" (for example, no completed history yet) and is passed to models
# that handle missing values natively.


def audit_occurrence_feature_manifest(
    frames: Dict[str, pd.DataFrame],
    target_cols: List[str],
    feature_cols: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Fail loudly if the feature manifest is incomplete or leaky.

    Checks:
    1. No duplicate features.
    2. No feature is an exact leaky column or starts with a leaky prefix.
    3. Every feature exists in every split.
    4. No feature reproduces a target column.

    Returns a per-split missing-value summary for each feature.
    """
    if feature_cols is None:
        feature_cols = OCCURRENCE_FEATURE_COLS

    if len(feature_cols) != len(set(feature_cols)):
        raise ValueError("Feature manifest contains duplicate columns.")

    leaky = sorted(
        set(feature_cols) & set(OCCURRENCE_LEAKY_COLUMNS)
    ) + [
        column
        for column in feature_cols
        if column.startswith(tuple(OCCURRENCE_LEAKY_PREFIXES))
    ]

    if leaky:
        raise ValueError(
            f"Leaky columns found in the feature manifest: {sorted(set(leaky))}"
        )

    rows = []

    for split_name, df in frames.items():
        missing = [column for column in feature_cols if column not in df.columns]
        if missing:
            raise ValueError(
                f"[{split_name}] Missing feature columns: {missing}"
            )

        for feature in feature_cols:
            values = df[feature]

            for target_col in target_cols:
                if target_col not in df.columns:
                    continue

                both = values.notna() & df[target_col].notna()

                if both.any() and np.allclose(
                    values[both].astype(float),
                    df.loc[both, target_col].astype(float),
                ):
                    raise ValueError(
                        f"[{split_name}] Feature {feature} reproduces {target_col}."
                    )

            rows.append(
                {
                    "split": split_name,
                    "feature": feature,
                    "missing_rows": int(values.isna().sum()),
                    "missing_pct": 100 * float(values.isna().mean()),
                }
            )

    return pd.DataFrame(rows)


def build_occurrence_feature_matrix(
    df: pd.DataFrame,
    feature_cols: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Return the model input matrix in manifest order as float64.

    Missing features raise an error. Missing values stay NaN.
    """
    if feature_cols is None:
        feature_cols = OCCURRENCE_FEATURE_COLS

    missing = [column for column in feature_cols if column not in df.columns]
    if missing:
        raise ValueError(f"Missing feature columns: {missing}")

    return df[list(feature_cols)].astype("float64")


def select_label_period_rows(
    df: pd.DataFrame,
    target_col: str,
    target_time_col: str,
    label_cutoff_time: Optional[int],
    time_col: str = "execution_start_time_us",
    id_col: str = "occurrence_key",
) -> pd.DataFrame:
    """
    Keep rows whose target is present and, when a cutoff is given, whose
    target occurrence starts at or before the cutoff.

    A label whose target occurrence starts after the cutoff describes a
    period the model must not have seen. Rows are returned in deterministic
    chronological order.
    """
    keep = df[target_col].notna()

    if label_cutoff_time is not None:
        keep &= df[target_time_col] <= label_cutoff_time

    return (
        df.loc[keep]
        .sort_values([time_col, id_col], kind="mergesort")
        .reset_index(drop=True)
    )


def purged_time_series_folds(
    df: pd.DataFrame,
    target_time_col: str,
    n_splits: int = 5,
    time_col: str = "execution_start_time_us",
) -> List[Tuple[np.ndarray, np.ndarray]]:
    """
    Expanding-window TimeSeriesSplit folds over complete timestamp groups.

    For each fold:
    - rows sharing a timestamp always land on the same side;
    - training rows start before the validation block;
    - training rows whose target occurrence starts at or after the
      validation block are purged, so no training label comes from the
      period being validated.

    Returns positional (train_index, validation_index) pairs for df.
    """
    times = df[time_col].to_numpy()
    target_times = df[target_time_col].to_numpy(dtype=float)

    if np.isnan(target_times).any():
        raise ValueError(f"{target_time_col} must be present for every row.")

    unique_times = np.unique(times)

    if len(unique_times) <= n_splits:
        raise ValueError(
            "Not enough distinct timestamps for the requested number of folds."
        )

    folds = []

    for train_time_idx, val_time_idx in TimeSeriesSplit(n_splits=n_splits).split(
        unique_times
    ):
        val_start = unique_times[val_time_idx].min()
        val_end = unique_times[val_time_idx].max()

        train_mask = (times < val_start) & (target_times < val_start)
        val_mask = (times >= val_start) & (times <= val_end)

        train_index = np.flatnonzero(train_mask)
        val_index = np.flatnonzero(val_mask)

        if len(train_index) == 0 or len(val_index) == 0:
            raise ValueError("A time-series fold is empty after purging.")

        folds.append((train_index, val_index))

    return folds
