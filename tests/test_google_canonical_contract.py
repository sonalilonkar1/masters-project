import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.canonical.schema import (
    GOOGLE_CAPABILITIES,
    SCHEMA_VERSION,
    validate_canonical_frame,
)


REPO_ROOT = Path(__file__).resolve().parents[1]

GOOGLE_DATA_DIR = (
    REPO_ROOT
    / "data"
    / "processed"
    / "google_subset_v1"
)

SPLIT_PATHS = {
    "train": GOOGLE_DATA_DIR / "train_occurrences.parquet",
    "validation": GOOGLE_DATA_DIR / "val_occurrences.parquet",
    "test": GOOGLE_DATA_DIR / "test_occurrences.parquet",
}

METADATA_PATH = GOOGLE_DATA_DIR / "metadata.json"

OCCURRENCE_FILES = {
    "train": "train_occurrences.parquet",
    "validation": "val_occurrences.parquet",
    "test": "test_occurrences.parquet",
}


def load_google_occurrence_split(split_name):
    path = (
        GOOGLE_DATA_DIR
        / OCCURRENCE_FILES[split_name]
    )

    if not path.exists():
        pytest.skip(
            f"Corrected N04 artifact not available: {path}"
        )

    return pd.read_parquet(path)

def build_google_canonical_contract_view(
    source: pd.DataFrame,
) -> pd.DataFrame:
    """
    Represent corrected Google N04 occurrence artifacts using the
    TraceAdvisor canonical schema.

    IMPORTANT:
    This function does NOT reconstruct occurrences, history, targets,
    splits, recommendations, or resource peaks.

    It only maps already-corrected N04 fields into canonical semantic names.
    """

    canonical = pd.DataFrame(index=source.index)

    # ------------------------------------------------------------------
    # Canonical identity
    # ------------------------------------------------------------------

    canonical["schema_version"] = SCHEMA_VERSION
    canonical["dataset_id"] = GOOGLE_CAPABILITIES.dataset_id
    canonical["record_level"] = "occurrence"

    # recurrence_key identifies the logical recurring workload.
    canonical["workload_id"] = source["recurrence_key"]

    # occurrence_key is the authoritative occurrence identifier.
    canonical["occurrence_id"] = source["occurrence_key"]
    canonical["recurrence_key"] = source["recurrence_key"]

    # ------------------------------------------------------------------
    # Canonical time fields
    # ------------------------------------------------------------------

    # Google trace timestamps are relative to the trace, not Unix epoch.
    canonical["time_basis"] = "trace_relative"

    canonical["start_time_us"] = source[
        "execution_start_time_us"
    ]

    canonical["end_time_us"] = source[
        "occurrence_end_time_us"
    ]

    canonical["duration_sec"] = (
        source["occurrence_runtime_us"].astype("Float64")
        / 1_000_000.0
    )

    # ------------------------------------------------------------------
    # Current occurrence request
    # ------------------------------------------------------------------

    canonical["requested_cpu"] = source[
        "occurrence_requested_cpu_ncu"
    ]
    canonical["requested_cpu_unit"] = "ncu"

    canonical["requested_memory"] = source[
        "occurrence_requested_memory_normalized"
    ]
    canonical["requested_memory_unit"] = "normalized"

    # ------------------------------------------------------------------
    # Current occurrence observed full-workload peak
    # ------------------------------------------------------------------

    canonical["peak_cpu"] = source[
        "occurrence_peak_cpu_ncu"
    ]
    canonical["peak_cpu_unit"] = "ncu"

    canonical["peak_memory"] = source[
        "occurrence_peak_memory_normalized"
    ]
    canonical["peak_memory_unit"] = "normalized"

    # ------------------------------------------------------------------
    # Evaluator actual / next-occurrence target
    # ------------------------------------------------------------------

    canonical["actual_cpu"] = source[
        "target_cpu_next_occurrence_peak_ncu"
    ]
    canonical["actual_cpu_unit"] = "ncu"

    canonical["actual_memory"] = source[
        "target_memory_next_occurrence_peak_normalized"
    ]
    canonical["actual_memory_unit"] = "normalized"

    # A row remains valid even if a next-occurrence target is unavailable.
    # The final occurrence of a recurrence intentionally has no target.
    canonical["validity_status"] = "valid"

    return canonical


@pytest.mark.parametrize(
    "split_name",
    ["train", "validation", "test"],
)
def test_real_google_occurrence_artifact_fits_canonical_schema(
    split_name,
):
    source_path = SPLIT_PATHS[split_name]

    assert source_path.exists(), (
        f"Missing Google N04 artifact: {source_path}"
    )

    source = pd.read_parquet(source_path)

    canonical = build_google_canonical_contract_view(source)

    # --------------------------------------------------------------
    # Basic row-preservation checks
    # --------------------------------------------------------------

    assert len(canonical) == len(source)

    assert canonical["occurrence_id"].is_unique

    pd.testing.assert_series_equal(
        canonical["occurrence_id"],
        source["occurrence_key"],
        check_names=False,
    )

    pd.testing.assert_series_equal(
        canonical["recurrence_key"],
        source["recurrence_key"],
        check_names=False,
    )

    # --------------------------------------------------------------
    # Timestamp preservation
    # --------------------------------------------------------------

    pd.testing.assert_series_equal(
        canonical["start_time_us"],
        source["execution_start_time_us"],
        check_names=False,
    )

    pd.testing.assert_series_equal(
        canonical["end_time_us"],
        source["occurrence_end_time_us"],
        check_names=False,
    )

    # --------------------------------------------------------------
    # Current full-workload resource preservation
    # --------------------------------------------------------------

    pd.testing.assert_series_equal(
        canonical["peak_cpu"],
        source["occurrence_peak_cpu_ncu"],
        check_names=False,
    )

    pd.testing.assert_series_equal(
        canonical["peak_memory"],
        source["occurrence_peak_memory_normalized"],
        check_names=False,
    )

    # --------------------------------------------------------------
    # Request preservation
    # --------------------------------------------------------------

    pd.testing.assert_series_equal(
        canonical["requested_cpu"],
        source["occurrence_requested_cpu_ncu"],
        check_names=False,
    )

    pd.testing.assert_series_equal(
        canonical["requested_memory"],
        source["occurrence_requested_memory_normalized"],
        check_names=False,
    )

    # --------------------------------------------------------------
    # Next-occurrence target preservation
    # --------------------------------------------------------------

    pd.testing.assert_series_equal(
        canonical["actual_cpu"],
        source["target_cpu_next_occurrence_peak_ncu"],
        check_names=False,
    )

    pd.testing.assert_series_equal(
        canonical["actual_memory"],
        source[
            "target_memory_next_occurrence_peak_normalized"
        ],
        check_names=False,
    )

    # Nulls must remain exactly unchanged.
    assert (
        canonical["actual_cpu"].isna().sum()
        == source[
            "target_cpu_next_occurrence_peak_ncu"
        ].isna().sum()
    )

    assert (
        canonical["actual_memory"].isna().sum()
        == source[
            "target_memory_next_occurrence_peak_normalized"
        ].isna().sum()
    )

    # --------------------------------------------------------------
    # Canonical validation
    # --------------------------------------------------------------

    validate_canonical_frame(
        canonical,
        GOOGLE_CAPABILITIES,
    )


def test_google_metadata_matches_canonical_contract():
    assert METADATA_PATH.exists()

    with METADATA_PATH.open("r", encoding="utf-8") as handle:
        metadata = json.load(handle)

    assert (
        metadata["canonical_modeling_unit"]
        == "recurrence_occurrence"
    )

    assert (
        metadata["occurrence_key_field"]
        == "occurrence_key"
    )

    assert (
        metadata["recurrence_key_field"]
        == "recurrence_key"
    )

    assert (
        metadata["timestamp_field"]
        == "execution_start_time_us"
    )

    assert (
        metadata["target_cpu_field"]
        == "target_cpu_next_occurrence_peak_ncu"
    )

    assert (
        metadata["target_memory_field"]
        == "target_memory_next_occurrence_peak_normalized"
    )

    assert (
        metadata["evaluation_actual_cpu_field"]
        == "target_cpu_next_occurrence_peak_ncu"
    )

    assert (
        metadata["evaluation_actual_memory_field"]
        == "target_memory_next_occurrence_peak_normalized"
    )

def test_google_target_nulls_match_global_final_occurrences():
    """Null targets are the globally final occurrences plus cross-split ones.

    The name is kept from before Task 10 (#115), which asks for this test to
    be updated. It now checks that null CPU targets are exactly the last
    occurrence of each recurrence within each split.
    """
    train = pd.read_parquet(
        SPLIT_PATHS["train"]
    )
    validation = pd.read_parquet(
        SPLIT_PATHS["validation"]
    )
    test = pd.read_parquet(
        SPLIT_PATHS["test"]
    )

    combined = pd.concat(
        [
            train.assign(_split="train"),
            validation.assign(_split="validation"),
            test.assign(_split="test"),
        ],
        ignore_index=True,
    )

    combined = combined.sort_values(
        [
            "recurrence_key",
            "execution_start_time_us",
            "occurrence_key",
        ]
    )

    final_occurrences = (
        combined
        .groupby(
            "recurrence_key",
            sort=False,
        )
        .tail(1)
    )

    # Exactly one globally final occurrence per recurrence.
    assert (
        len(final_occurrences)
        == combined["recurrence_key"].nunique()
    )

    # The last occurrence of each recurrence inside its own split.
    split_final_occurrences = (
        combined
        .groupby(
            ["_split", "recurrence_key"],
            sort=False,
        )
        .tail(1)
    )

    cpu_target = (
        "target_cpu_next_occurrence_peak_ncu"
    )

    cpu_null_keys = set(
        combined.loc[
            combined[cpu_target].isna(),
            "occurrence_key",
        ]
    )

    final_keys = set(
        final_occurrences[
            "occurrence_key"
        ]
    )

    split_final_keys = set(
        split_final_occurrences[
            "occurrence_key"
        ]
    )

    # Since Task 10, N04 builds next-occurrence targets after split
    # assignment, inside each split. CPU targets are null for the globally
    # final occurrence of each recurrence and, in every split, also for the
    # occurrence whose next occurrence lies in another split. Together these
    # are exactly the last occurrence of each recurrence within each split.
    assert final_keys <= cpu_null_keys
    assert cpu_null_keys == split_final_keys

    cross_split_keys = split_final_keys - final_keys
    reason = combined.set_index("occurrence_key")["target_null_reason"]

    assert (
        reason.loc[sorted(final_keys)] == "no_next_occurrence"
    ).all()
    assert (
        reason.loc[sorted(cross_split_keys)]
        == "next_occurrence_in_other_split"
    ).all()
    assert reason.loc[
        sorted(set(combined["occurrence_key"]) - cpu_null_keys)
    ].isna().all()

    # The test split is last, so no test target can be removed for crossing.
    assert not (
        combined.loc[
            combined["_split"] == "test",
            "target_null_reason",
        ]
        == "next_occurrence_in_other_split"
    ).any()


# ----------------------------------------------------------------------
# Task 10: split-isolated Google targets
# ----------------------------------------------------------------------

TARGET_TIME_COL = "target_next_occurrence_start_time_us"
TARGET_CPU_COL = "target_cpu_next_occurrence_peak_ncu"
TARGET_MEMORY_COL = "target_memory_next_occurrence_peak_normalized"
TARGET_SIZE_COL = "target_next_occurrence_execution_count"
TARGET_COLUMNS = [
    TARGET_TIME_COL,
    TARGET_CPU_COL,
    TARGET_MEMORY_COL,
    TARGET_SIZE_COL,
]

EXECUTION_FEATURE_PATHS = {
    "train": GOOGLE_DATA_DIR / "train_features.parquet",
    "validation": GOOGLE_DATA_DIR / "val_features.parquet",
    "test": GOOGLE_DATA_DIR / "test_features.parquet",
}
N03_EXECUTION_PATH = GOOGLE_DATA_DIR / "job_metrics_v0.parquet"

# Frozen chronological 70/15/15 boundaries and row counts recorded before the
# Task 10 correction. The correction must not move them.
FROZEN_SPLIT_BOUNDARIES = {
    "train_start": 300000000,
    "train_end": 1812600000000,
    "val_start": 1813200000000,
    "val_end": 2261100000000,
    "test_start": 2262600000000,
    "test_end": 2678400000000,
}
FROZEN_EXECUTION_ROWS = {
    "train": 178858,
    "validation": 36703,
    "test": 38024,
}
FROZEN_OCCURRENCE_ROWS = {
    "train": 3473,
    "validation": 675,
    "test": 731,
}

# Expected effect of the Task 10 correction on these artifacts (findings F3
# and F4 in docs/data/google_subset_pipeline_analysis.md).
EXPECTED_CROSS_SPLIT_TARGETS_REMOVED = {
    "train": 338,
    "validation": 104,
    "test": 0,
}
EXPECTED_COMMON_VALIDATION_OCCURRENCES = 225


def _load_all_google_splits():
    return {
        split_name: load_google_occurrence_split(split_name)
        for split_name in OCCURRENCE_FILES
    }


def _load_google_metadata():
    if not METADATA_PATH.exists():
        pytest.skip(f"Google N04 metadata not available: {METADATA_PATH}")

    with METADATA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _in_split_period(times, split_name, boundaries):
    if split_name == "train":
        return times <= boundaries["train_end"]
    if split_name == "validation":
        return (times >= boundaries["val_start"]) & (
            times <= boundaries["val_end"]
        )
    if split_name == "test":
        return times >= boundaries["test_start"]
    raise ValueError(split_name)


def test_google_metadata_records_target_split_isolation():
    metadata = _load_google_metadata()

    assert metadata["target_split_isolation"] is True
    assert metadata["target_null_reason_field"] == "target_null_reason"
    assert metadata["target_null_reason_values"] == [
        "no_next_occurrence",
        "next_occurrence_in_other_split",
    ]
    assert (
        metadata["target_policy_version"]
        == "next_distinct_full_workload_occurrence_v4_split_isolated"
    )

    # Recorded removal counts match the expected correction and the saved
    # artifacts.
    assert (
        metadata["cross_split_targets_removed"]
        == EXPECTED_CROSS_SPLIT_TARGETS_REMOVED
    )
    assert (
        metadata["common_validation_population"]["occurrences"]
        == EXPECTED_COMMON_VALIDATION_OCCURRENCES
    )

    splits = _load_all_google_splits()
    assert metadata["cross_split_targets_removed"] == {
        split_name: int(
            (
                frame["target_null_reason"]
                == "next_occurrence_in_other_split"
            ).sum()
        )
        for split_name, frame in splits.items()
    }

    # The common validation population is the validation rows with both
    # split-isolated next-occurrence targets.
    validation = splits["validation"]
    assert metadata["common_validation_population"]["occurrences"] == int(
        validation[[TARGET_CPU_COL, TARGET_MEMORY_COL]]
        .notna()
        .all(axis=1)
        .sum()
    )


@pytest.mark.parametrize("split_name", ["train", "validation", "test"])
def test_google_targets_never_come_from_another_split(split_name):
    boundaries = _load_google_metadata()["split_boundaries"]
    frame = load_google_occurrence_split(split_name)

    has_target = frame[TARGET_TIME_COL].notna()
    assert _in_split_period(
        frame.loc[has_target, TARGET_TIME_COL],
        split_name,
        boundaries,
    ).all()

    # A row without a next occurrence in its split has no target values.
    for column in TARGET_COLUMNS:
        assert frame.loc[~has_target, column].isna().all()

    # Every null target has exactly one recorded reason.
    assert (frame["target_null_reason"].isna() == has_target).all()


def test_google_targets_point_to_a_later_occurrence_of_the_same_recurrence():
    splits = _load_all_google_splits()

    for split_name, frame in splits.items():
        has_target = frame[TARGET_TIME_COL].notna()
        targets = frame.loc[has_target].copy()

        assert (
            targets[TARGET_TIME_COL] > targets["execution_start_time_us"]
        ).all()

        targets["_target_start"] = targets[TARGET_TIME_COL].astype("int64")
        pointed = targets[
            ["occurrence_key", "recurrence_key", "_target_start"]
            + [TARGET_CPU_COL, TARGET_MEMORY_COL, TARGET_SIZE_COL]
        ].merge(
            frame[
                [
                    "occurrence_key",
                    "recurrence_key",
                    "execution_start_time_us",
                    "occurrence_peak_cpu_ncu",
                    "occurrence_peak_memory_normalized",
                    "occurrence_execution_count",
                ]
            ].rename(columns={"occurrence_key": "_target_occurrence_key"}),
            left_on=["recurrence_key", "_target_start"],
            right_on=["recurrence_key", "execution_start_time_us"],
            how="left",
            validate="many_to_one",
        )

        # The target occurrence exists in the same split and recurrence.
        assert pointed["_target_occurrence_key"].notna().all(), split_name
        assert (
            pointed["_target_occurrence_key"] != pointed["occurrence_key"]
        ).all()

        # Target values are that occurrence's full-workload values.
        np.testing.assert_array_equal(
            pointed[TARGET_CPU_COL],
            pointed["occurrence_peak_cpu_ncu"],
        )
        np.testing.assert_array_equal(
            pointed[TARGET_MEMORY_COL],
            pointed["occurrence_peak_memory_normalized"],
        )
        np.testing.assert_array_equal(
            pointed[TARGET_SIZE_COL],
            pointed["occurrence_execution_count"],
        )

        # It is the next occurrence: no occurrence of the same recurrence
        # starts strictly between the current occurrence and its target.
        ordered = frame.sort_values(
            ["recurrence_key", "execution_start_time_us"],
            kind="mergesort",
        )
        expected_next = ordered.groupby("recurrence_key", sort=False)[
            "execution_start_time_us"
        ].shift(-1)
        actual_next = ordered[TARGET_TIME_COL]
        assert (
            (expected_next == actual_next)
            | (expected_next.isna() & actual_next.isna())
        ).all(), split_name


@pytest.mark.parametrize("split_name", ["train", "validation", "test"])
def test_google_missing_memory_stays_nan(split_name):
    frame = load_google_occurrence_split(split_name)
    has_target = frame[TARGET_TIME_COL].notna()

    # Missing next-occurrence memory stays NaN; CPU is not affected by it.
    target_occurrences = frame.loc[
        has_target,
        ["recurrence_key", TARGET_TIME_COL, TARGET_MEMORY_COL],
    ].assign(_target_start=lambda df: df[TARGET_TIME_COL].astype("int64"))
    pointed = target_occurrences.merge(
        frame[
            [
                "recurrence_key",
                "execution_start_time_us",
                "occurrence_peak_memory_normalized",
            ]
        ],
        left_on=["recurrence_key", "_target_start"],
        right_on=["recurrence_key", "execution_start_time_us"],
        how="left",
        validate="many_to_one",
    )
    assert (
        pointed[TARGET_MEMORY_COL].isna()
        == pointed["occurrence_peak_memory_normalized"].isna()
    ).all()
    assert frame.loc[has_target, TARGET_CPU_COL].notna().all()

    # No placeholder value replaces a missing memory target.
    memory_target = frame[TARGET_MEMORY_COL].dropna()
    assert (memory_target >= 0).all()

    # Request recommendations keep missing memory requests as NaN.
    assert (
        frame["rec_memory_request"].isna()
        == frame["occurrence_requested_memory_normalized"].isna()
    ).all()

    # History recommendations are NaN only where history is not used and
    # the request is missing; nothing is filled.
    for policy in ["mean", "p90", "p95", "p99"]:
        recommendation = frame[f"rec_memory_{policy}"]
        uses_history = frame[f"uses_history_memory_{policy}"].astype(bool)
        expected = frame[f"occ_hist_peak_memory_{policy}"].where(
            uses_history,
            frame["occurrence_requested_memory_normalized"],
        )
        np.testing.assert_array_equal(
            recommendation.to_numpy(dtype=float),
            expected.to_numpy(dtype=float),
        )


def test_google_chronological_split_is_unchanged():
    from src.features.split_utils import chronological_split

    if not N03_EXECUTION_PATH.exists():
        pytest.skip(f"Notebook 03 artifact not available: {N03_EXECUTION_PATH}")

    metadata = _load_google_metadata()

    executions = pd.read_parquet(N03_EXECUTION_PATH)
    train, validation, test, split_metadata = chronological_split(
        executions,
        time_col="execution_start_time_us",
        id_col="execution_id",
        train_fraction=0.70,
        val_fraction=0.15,
    )

    # The shared split utility reproduces the recorded split exactly.
    assert json.loads(json.dumps(split_metadata, default=int)) == (
        metadata["split_boundaries"]
    )
    for key, value in FROZEN_SPLIT_BOUNDARIES.items():
        assert split_metadata[key] == value

    for split_name, split_rows in [
        ("train", train),
        ("validation", validation),
        ("test", test),
    ]:
        path = EXECUTION_FEATURE_PATHS[split_name]
        if not path.exists():
            pytest.skip(f"Google N04 artifact not available: {path}")

        saved = pd.read_parquet(path, columns=["execution_id"])
        assert len(split_rows) == FROZEN_EXECUTION_ROWS[split_name]
        assert len(saved) == FROZEN_EXECUTION_ROWS[split_name]
        assert set(saved["execution_id"]) == set(split_rows["execution_id"])

        occurrences = load_google_occurrence_split(split_name)
        assert len(occurrences) == FROZEN_OCCURRENCE_ROWS[split_name]

    # No occurrence crosses a split boundary.
    keys = {
        split_name: set(load_google_occurrence_split(split_name)["occurrence_key"])
        for split_name in OCCURRENCE_FILES
    }
    assert keys["train"].isdisjoint(keys["validation"])
    assert keys["train"].isdisjoint(keys["test"])
    assert keys["validation"].isdisjoint(keys["test"])
