import json
from pathlib import Path

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


def test_google_train_target_nulls_are_preserved():
    source = pd.read_parquet(
        SPLIT_PATHS["train"]
    )

    canonical = build_google_canonical_contract_view(
        source
    )

    # N04 semantics:
    # final occurrence of each recurrence has no next-occurrence CPU target.
    assert source["recurrence_key"].nunique() == 1801

    assert (
        source[
            "target_cpu_next_occurrence_peak_ncu"
        ].isna().sum()
        == 1801
    )

    assert (
        canonical["actual_cpu"].isna().sum()
        == 1801
    )

    # Memory has the same final-occurrence nulls plus additional
    # source memory missingness. It must NOT be filled with zero.
    assert (
        canonical["actual_memory"].isna().sum()
        == source[
            "target_memory_next_occurrence_peak_normalized"
        ].isna().sum()
    )

    assert (
        canonical["actual_memory"].isna().sum()
        >= canonical["actual_cpu"].isna().sum()
    )