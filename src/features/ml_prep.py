# src/features/ml_prep.py
#
# Shared ML matrix construction and validation utilities.
# Extracted from subset-05-ml-prediction.ipynb so that
# Notebooks 5, 6, and any future ML notebooks use the same logic.

from __future__ import annotations

from typing import List, Optional, Tuple

import pandas as pd

from src.features.feature_config import (
    CATEGORICAL_FEATURES,
    FEATURE_COLS,
    LEAKY_COLUMNS,
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
    Filter the canonical feature list to only features present in all splits.

    Parameters
    ----------
    train_df, val_df, test_df : pd.DataFrame
        Source DataFrames for each split.
    feature_cols : list[str], optional
        Feature list to filter. Defaults to FEATURE_COLS.

    Returns
    -------
    list[str]
        Features available in all three splits.
    """
    if feature_cols is None:
        feature_cols = FEATURE_COLS

    available = [
        c for c in feature_cols
        if c in train_df.columns
        and c in val_df.columns
        and c in test_df.columns
    ]

    dropped = set(feature_cols) - set(available)
    if dropped:
        print(f"Warning: {len(dropped)} features not available in all splits: {sorted(dropped)}")

    print(f"Using {len(available)} / {len(feature_cols)} features")
    return available
