import pandas as pd
import pytest

from features.split_utils import chronological_split


def make_demo_df(n_rows: int = 100) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "execution_id": [
                f"e{i}" for i in range(n_rows)
            ],
            "execution_start_time_us": list(
                range(n_rows)
            ),
        }
    )


def test_chronological_split_sizes():
    df = make_demo_df(100)

    train_df, val_df, test_df, metadata = (
        chronological_split(df)
    )

    assert len(train_df) == 70
    assert len(val_df) == 15
    assert len(test_df) == 15

    assert metadata["total_rows"] == 100
    assert metadata["train_rows"] == 70
    assert metadata["val_rows"] == 15
    assert metadata["test_rows"] == 15


def test_chronological_order_is_preserved():
    df = make_demo_df(100)

    # Reverse input deliberately.
    df = df.iloc[::-1].reset_index(drop=True)

    train_df, val_df, test_df, _ = (
        chronological_split(df)
    )

    assert (
        train_df["execution_start_time_us"].max()
        <= val_df["execution_start_time_us"].min()
    )

    assert (
        val_df["execution_start_time_us"].max()
        <= test_df["execution_start_time_us"].min()
    )


def test_execution_ids_do_not_overlap():
    df = make_demo_df(100)

    train_df, val_df, test_df, _ = (
        chronological_split(df)
    )

    train_ids = set(train_df["execution_id"])
    val_ids = set(val_df["execution_id"])
    test_ids = set(test_df["execution_id"])

    assert train_ids.isdisjoint(val_ids)
    assert train_ids.isdisjoint(test_ids)
    assert val_ids.isdisjoint(test_ids)


def test_duplicate_execution_ids_are_rejected():
    df = pd.DataFrame(
        {
            "execution_id": [
                "e1",
                "e1",
                "e2",
            ],
            "execution_start_time_us": [
                1,
                2,
                3,
            ],
        }
    )

    with pytest.raises(
        ValueError,
        match="duplicate",
    ):
        chronological_split(df)


def test_missing_timestamp_is_rejected():
    df = pd.DataFrame(
        {
            "execution_id": [
                "e1",
                "e2",
                "e3",
            ],
            "execution_start_time_us": [
                1,
                None,
                3,
            ],
        }
    )

    with pytest.raises(
        ValueError,
        match="missing",
    ):
        chronological_split(df)


def test_required_columns_are_checked():
    df = pd.DataFrame(
        {
            "execution_id": [
                "e1",
                "e2",
                "e3",
            ],
        }
    )

    with pytest.raises(
        ValueError,
        match="Missing required split columns",
    ):
        chronological_split(df)
        
def test_shared_timestamps_are_not_split():
    df = pd.DataFrame(
        {
            "execution_id": [
                f"e{i}"
                for i in range(20)
            ],
            "execution_start_time_us": (
                [100] * 6
                + [200] * 6
                + [300] * 4
                + [400] * 4
            ),
        }
    )

    train_df, val_df, test_df, _ = (
        chronological_split(
            df,
            train_fraction=0.50,
            val_fraction=0.25,
        )
    )

    train_times = set(
        train_df["execution_start_time_us"]
    )

    val_times = set(
        val_df["execution_start_time_us"]
    )

    test_times = set(
        test_df["execution_start_time_us"]
    )

    assert train_times.isdisjoint(
        val_times
    )

    assert train_times.isdisjoint(
        test_times
    )

    assert val_times.isdisjoint(
        test_times
    )

    assert (
        train_df[
            "execution_start_time_us"
        ].max()
        <
        val_df[
            "execution_start_time_us"
        ].min()
    )

    assert (
        val_df[
            "execution_start_time_us"
        ].max()
        <
        test_df[
            "execution_start_time_us"
        ].min()
    )