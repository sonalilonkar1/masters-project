import numpy as np
import pandas as pd
import pytest

from features.feature_config import OCCURRENCE_FEATURE_COLS
from features.ml_prep import (
    audit_occurrence_feature_manifest,
    build_occurrence_feature_matrix,
    purged_time_series_folds,
    select_label_period_rows,
)


TARGET_CPU = "target_cpu_next_occurrence_peak_ncu"
TARGET_MEMORY = "target_memory_next_occurrence_peak_normalized"
TARGET_TIME = "target_next_occurrence_start_time_us"


def make_occurrences(n_rows: int = 12) -> pd.DataFrame:
    rng = np.random.default_rng(0)

    df = pd.DataFrame(
        {
            column: rng.random(n_rows)
            for column in OCCURRENCE_FEATURE_COLS
        }
    )
    df["occurrence_key"] = [f"o{i}" for i in range(n_rows)]
    df["execution_start_time_us"] = np.arange(n_rows) * 10
    df[TARGET_TIME] = df["execution_start_time_us"] + 15
    df[TARGET_CPU] = rng.random(n_rows) + 5
    df[TARGET_MEMORY] = rng.random(n_rows) + 5

    return df


def test_audit_passes_for_clean_manifest():
    df = make_occurrences()

    audit = audit_occurrence_feature_manifest(
        {"train": df},
        target_cols=[TARGET_CPU, TARGET_MEMORY],
    )

    assert len(audit) == len(OCCURRENCE_FEATURE_COLS)
    assert (audit["missing_rows"] == 0).all()


@pytest.mark.parametrize(
    "leaky_feature",
    [
        "occurrence_peak_cpu_ncu",
        TARGET_CPU,
        "rec_cpu_p95",
        "uses_history_cpu_p95",
    ],
)
def test_audit_rejects_leaky_features(leaky_feature):
    df = make_occurrences()
    df[leaky_feature] = 1.0

    with pytest.raises(ValueError, match="Leaky"):
        audit_occurrence_feature_manifest(
            {"train": df},
            target_cols=[TARGET_CPU],
            feature_cols=OCCURRENCE_FEATURE_COLS + [leaky_feature],
        )


def test_audit_rejects_feature_that_copies_target():
    df = make_occurrences()
    df["occurrence_execution_count"] = df[TARGET_CPU]

    with pytest.raises(ValueError, match="reproduces"):
        audit_occurrence_feature_manifest(
            {"train": df},
            target_cols=[TARGET_CPU],
        )


def test_audit_rejects_missing_feature():
    df = make_occurrences().drop(columns=["occ_hist_peak_cpu_p95"])

    with pytest.raises(ValueError, match="Missing feature columns"):
        audit_occurrence_feature_manifest(
            {"validation": df},
            target_cols=[TARGET_CPU],
        )


def test_feature_matrix_preserves_missing_values_and_order():
    df = make_occurrences()
    df.loc[0, "occ_hist_peak_cpu_mean"] = np.nan

    matrix = build_occurrence_feature_matrix(df)

    assert list(matrix.columns) == OCCURRENCE_FEATURE_COLS
    assert (matrix.dtypes == "float64").all()
    assert np.isnan(matrix.loc[0, "occ_hist_peak_cpu_mean"])


def test_feature_matrix_rejects_missing_feature():
    df = make_occurrences().drop(columns=["occurrence_requested_cpu_ncu"])

    with pytest.raises(ValueError, match="Missing feature columns"):
        build_occurrence_feature_matrix(df)


def test_label_period_rows_respect_cutoff_and_missing_targets():
    df = make_occurrences()
    df.loc[1, TARGET_CPU] = np.nan

    rows = select_label_period_rows(
        df,
        target_col=TARGET_CPU,
        target_time_col=TARGET_TIME,
        label_cutoff_time=65,
    )

    assert rows[TARGET_CPU].notna().all()
    assert (rows[TARGET_TIME] <= 65).all()
    assert "o1" not in set(rows["occurrence_key"])
    assert rows["execution_start_time_us"].is_monotonic_increasing


def test_label_period_rows_without_cutoff_keep_all_targets():
    df = make_occurrences()

    rows = select_label_period_rows(
        df,
        target_col=TARGET_CPU,
        target_time_col=TARGET_TIME,
        label_cutoff_time=None,
    )

    assert len(rows) == len(df)


def test_purged_folds_are_chronological_and_label_safe():
    df = make_occurrences(30)

    folds = purged_time_series_folds(df, TARGET_TIME, n_splits=4)

    assert len(folds) == 4

    for train_index, val_index in folds:
        val_start = df["execution_start_time_us"].iloc[val_index].min()

        assert (df["execution_start_time_us"].iloc[train_index] < val_start).all()
        assert (df[TARGET_TIME].iloc[train_index] < val_start).all()
        assert set(train_index).isdisjoint(set(val_index))


def test_purged_folds_keep_shared_timestamps_together():
    df = make_occurrences(30)
    df["execution_start_time_us"] = np.repeat(np.arange(10) * 10, 3)
    df[TARGET_TIME] = df["execution_start_time_us"] + 15

    for train_index, val_index in purged_time_series_folds(
        df,
        TARGET_TIME,
        n_splits=3,
    ):
        train_times = set(df["execution_start_time_us"].iloc[train_index])
        val_times = set(df["execution_start_time_us"].iloc[val_index])

        assert train_times.isdisjoint(val_times)


def test_purged_folds_reject_missing_target_times():
    df = make_occurrences(30)
    df.loc[3, TARGET_TIME] = np.nan

    with pytest.raises(ValueError, match="must be present"):
        purged_time_series_folds(df, TARGET_TIME, n_splits=3)
