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
    Create deterministic chronological train/validation/test splits.

    Split boundaries are chosen only between complete timestamp groups.
    All rows sharing the same timestamp are therefore assigned to the
    same partition.

    Fractions are approximate because preserving timestamp groups takes
    priority over exact row counts.
    """

    # ---------------------------------------------------------
    # Validate fractions
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
            "Missing required split columns: "
            f"{missing_columns}"
        )

    if df[time_col].isna().any():
        raise ValueError(
            f"{time_col} contains missing values."
        )

    if df[id_col].isna().any():
        raise ValueError(
            f"{id_col} contains missing values."
        )

    if df[id_col].duplicated().any():
        raise ValueError(
            f"{id_col} contains duplicate values."
        )

    if len(df) < 3:
        raise ValueError(
            "At least 3 rows are required."
        )

    # ---------------------------------------------------------
    # Deterministic chronological ordering
    # ---------------------------------------------------------
    ordered = cast(
        pd.DataFrame,
        df.sort_values(
            by=[
                time_col,
                id_col,
            ],
            kind="mergesort",
        )
        .reset_index(drop=True)
        .copy(),
    )

    total_rows = len(ordered)

    # ---------------------------------------------------------
    # Build complete timestamp groups
    # ---------------------------------------------------------
    timestamp_groups = (
        ordered.groupby(
            time_col,
            sort=False,
        )
        .size()
        .rename("row_count")
        .reset_index()
    )

    if len(timestamp_groups) < 3:
        raise ValueError(
            "At least 3 distinct timestamps are required "
            "to create train, validation, and test splits "
            "without dividing timestamp groups."
        )

    timestamp_groups["cumulative_rows"] = (
        timestamp_groups["row_count"].cumsum()
    )

    # Desired row positions.
    target_train_end = (
        total_rows * train_fraction
    )

    target_val_end = (
        total_rows
        * (train_fraction + val_fraction)
    )

    # ---------------------------------------------------------
    # Choose train boundary
    #
    # Leave at least one whole timestamp group for validation
    # and one for test.
    # ---------------------------------------------------------
    train_candidates = timestamp_groups.iloc[:-2].copy()

    train_group_index = (
        (
            train_candidates["cumulative_rows"]
            - target_train_end
        )
        .abs()
        .idxmin()
    )

    train_end = int(
        timestamp_groups.loc[
            train_group_index,
            "cumulative_rows",
        ]
    )

    # ---------------------------------------------------------
    # Choose validation boundary
    #
    # It must occur after train and before the final timestamp
    # group so test remains non-empty.
    # ---------------------------------------------------------
    val_candidates = timestamp_groups.loc[
        (
            timestamp_groups.index
            > train_group_index
        )
        & (
            timestamp_groups.index
            < timestamp_groups.index[-1]
        )
    ].copy()

    if val_candidates.empty:
        raise ValueError(
            "Unable to create a non-empty validation "
            "and test split without dividing timestamps."
        )

    val_group_index = (
        (
            val_candidates["cumulative_rows"]
            - target_val_end
        )
        .abs()
        .idxmin()
    )

    val_end = int(
        timestamp_groups.loc[
            val_group_index,
            "cumulative_rows",
        ]
    )

    # ---------------------------------------------------------
    # Create splits
    # ---------------------------------------------------------
    train_df = cast(
        pd.DataFrame,
        ordered.iloc[
            0:train_end,
            :,
        ].copy(),
    )

    val_df = cast(
        pd.DataFrame,
        ordered.iloc[
            train_end:val_end,
            :,
        ].copy(),
    )

    test_df = cast(
        pd.DataFrame,
        ordered.iloc[
            val_end:,
            :,
        ].copy(),
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
        raise RuntimeError(
            "Split row counts do not sum to the input row count."
        )

    train_ids = set(train_df[id_col])
    val_ids = set(val_df[id_col])
    test_ids = set(test_df[id_col])

    if not train_ids.isdisjoint(val_ids):
        raise RuntimeError(
            "Train and validation IDs overlap."
        )

    if not train_ids.isdisjoint(test_ids):
        raise RuntimeError(
            "Train and test IDs overlap."
        )

    if not val_ids.isdisjoint(test_ids):
        raise RuntimeError(
            "Validation and test IDs overlap."
        )

    # Strict inequality is intentional.
    # Equal timestamps across partitions are not allowed.
    if not (
        train_df[time_col].max()
        < val_df[time_col].min()
    ):
        raise RuntimeError(
            "Train and validation timestamps overlap."
        )

    if not (
        val_df[time_col].max()
        < test_df[time_col].min()
    ):
        raise RuntimeError(
            "Validation and test timestamps overlap."
        )

    # ---------------------------------------------------------
    # Metadata
    # ---------------------------------------------------------
    metadata: dict[str, object] = {
        "split_type": (
            "chronological_timestamp_group_preserving"
        ),
        "time_col": time_col,
        "id_col": id_col,
        "requested_train_fraction": train_fraction,
        "requested_val_fraction": val_fraction,
        "requested_test_fraction": (
            1
            - train_fraction
            - val_fraction
        ),
        "total_rows": total_rows,
        "train_rows": len(train_df),
        "val_rows": len(val_df),
        "test_rows": len(test_df),
        "actual_train_fraction": (
            len(train_df) / total_rows
        ),
        "actual_val_fraction": (
            len(val_df) / total_rows
        ),
        "actual_test_fraction": (
            len(test_df) / total_rows
        ),
        "train_start": train_df[time_col].min(),
        "train_end": train_df[time_col].max(),
        "val_start": val_df[time_col].min(),
        "val_end": val_df[time_col].max(),
        "test_start": test_df[time_col].min(),
        "test_end": test_df[time_col].max(),
        "unique_timestamps": len(timestamp_groups),
    }

    return (
        train_df,
        val_df,
        test_df,
        metadata,
    )