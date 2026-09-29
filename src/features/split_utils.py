from __future__ import annotations

from typing import cast

import pandas as pd


def chronological_split(
    df: pd.DataFrame,
    time_col: str = "execution_start_time_us",
    id_col: str = "execution_id",
    train_fraction: float = 0.70,
    val_fraction: float = 0.15,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, object],
]:
    """
    Split execution-level data chronologically into train,
    validation, and test partitions.

    The split is deterministic and does not shuffle data.

    Default split:
        earliest 70% -> train
        next 15%     -> validation
        latest 15%   -> test
    """

    # ---------------------------------------------------------
    # Validate split fractions
    # ---------------------------------------------------------
    if not 0 < train_fraction < 1:
        raise ValueError(
            "train_fraction must be between 0 and 1."
        )

    if not 0 < val_fraction < 1:
        raise ValueError(
            "val_fraction must be between 0 and 1."
        )

    if train_fraction + val_fraction >= 1:
        raise ValueError(
            "train_fraction + val_fraction must be less than 1."
        )

    # ---------------------------------------------------------
    # Validate required columns
    # ---------------------------------------------------------
    required_columns = [
        time_col,
        id_col,
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required split columns: {missing_columns}"
        )

    # ---------------------------------------------------------
    # Validate IDs and timestamps
    # ---------------------------------------------------------
    if df[time_col].isna().any():
        raise ValueError(
            f"{time_col} contains missing values."
        )

    if df[id_col].isna().any():
        raise ValueError(
            f"{id_col} contains missing values."
        )

    if df[id_col].duplicated().any():
        duplicate_count = int(
            df[id_col].duplicated().sum()
        )

        raise ValueError(
            f"{id_col} contains "
            f"{duplicate_count} duplicate values."
        )

    # ---------------------------------------------------------
    # Sort chronologically
    # ---------------------------------------------------------
    ordered = cast(
        pd.DataFrame,
        df.sort_values(
            by=[time_col, id_col],
            kind="mergesort",
        )
        .reset_index(drop=True)
        .copy(),
    )

    total_rows = len(ordered)

    if total_rows < 3:
        raise ValueError(
            "At least 3 rows are required "
            "for train/validation/test splitting."
        )

    # ---------------------------------------------------------
    # Calculate split boundaries
    # ---------------------------------------------------------
    train_end = int(
        total_rows * train_fraction
    )

    val_end = int(
        total_rows
        * (train_fraction + val_fraction)
    )

    # ---------------------------------------------------------
    # Create splits
    # ---------------------------------------------------------
    train_df = cast(
        pd.DataFrame,
        ordered.iloc[0:train_end, :].copy(),
    )

    val_df = cast(
        pd.DataFrame,
        ordered.iloc[train_end:val_end, :].copy(),
    )

    test_df = cast(
        pd.DataFrame,
        ordered.iloc[val_end:, :].copy(),
    )

    train_df["_split"] = "train"
    val_df["_split"] = "val"
    test_df["_split"] = "test"

    # ---------------------------------------------------------
    # Integrity checks
    # ---------------------------------------------------------
    if (
        len(train_df)
        + len(val_df)
        + len(test_df)
        != total_rows
    ):
        raise AssertionError(
            "Split row counts do not equal "
            "the original row count."
        )

    train_ids = set(train_df[id_col])
    val_ids = set(val_df[id_col])
    test_ids = set(test_df[id_col])

    if train_ids & val_ids:
        raise AssertionError(
            "Execution IDs overlap between "
            "train and validation."
        )

    if train_ids & test_ids:
        raise AssertionError(
            "Execution IDs overlap between "
            "train and test."
        )

    if val_ids & test_ids:
        raise AssertionError(
            "Execution IDs overlap between "
            "validation and test."
        )

    if not train_df.empty and not val_df.empty:
        if (
            train_df[time_col].max()
            > val_df[time_col].min()
        ):
            raise AssertionError(
                "Train and validation splits "
                "are not chronological."
            )

    if not val_df.empty and not test_df.empty:
        if (
            val_df[time_col].max()
            > test_df[time_col].min()
        ):
            raise AssertionError(
                "Validation and test splits "
                "are not chronological."
            )

    # ---------------------------------------------------------
    # Record metadata
    # ---------------------------------------------------------
    metadata = {
        "split_type": "chronological",
        "time_col": time_col,
        "id_col": id_col,
        "train_fraction": train_fraction,
        "val_fraction": val_fraction,
        "test_fraction": (
            1.0
            - train_fraction
            - val_fraction
        ),
        "total_rows": total_rows,
        "train_rows": len(train_df),
        "val_rows": len(val_df),
        "test_rows": len(test_df),
        "train_start": (
            train_df[time_col].min()
            if not train_df.empty
            else None
        ),
        "train_end": (
            train_df[time_col].max()
            if not train_df.empty
            else None
        ),
        "val_start": (
            val_df[time_col].min()
            if not val_df.empty
            else None
        ),
        "val_end": (
            val_df[time_col].max()
            if not val_df.empty
            else None
        ),
        "test_start": (
            test_df[time_col].min()
            if not test_df.empty
            else None
        ),
        "test_end": (
            test_df[time_col].max()
            if not test_df.empty
            else None
        ),
    }

    return (
        train_df,
        val_df,
        test_df,
        metadata
    )