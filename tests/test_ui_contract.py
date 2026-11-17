import json
from pathlib import Path

import pandas as pd
import pytest

from src.canonical.schema import TARGET_STATUSES
from src.service.contract import (
    ALIBABA,
    DATASET_IDS,
    DATASETS,
    GOOGLE,
    POLICY_BY_ID,
    POLICY_IDS,
    POLICY_NAMES,
    RECOMMENDATION_COLUMNS,
    WORKLOAD_COLUMNS,
    BundleContractError,
    error_body,
    validate_frame,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_CONFIG_PATH = REPO_ROOT / "config" / "dataset_capabilities.json"
SUMMARY_CSVS = {
    GOOGLE: REPO_ROOT / "reports/results/google_subset/tables/final_test_policy_comparison.csv",
    ALIBABA: REPO_ROOT / "reports/results/alibaba_gpu_2020/final_test/final_test_policy_comparison.csv",
}


def recommendation_frame():
    """Two valid rows: an Alibaba history row and a Google fallback row without a next run."""
    return pd.DataFrame(
        {
            "workload_id": ["g1||t1", "user||job"],
            "occurrence_id": ["g1||j1", "occ-1"],
            "role_key": pd.Series(["g1||j1||t1", None], dtype="string"),
            "start_time_us": [1_000, 2_000],
            "target_start_time_us": pd.Series([1_500, None], dtype="Int64"),
            "target_occurrence_id": pd.Series(["g1||j2", None], dtype="string"),
            "policy": ["Hybrid", "P95"],
            "recommended_cpu": [120.0, 0.05],
            "recommended_memory": [8.0, 0.02],
            "request_cpu": [600.0, 0.05],
            "request_memory": [29.0, 0.02],
            "actual_cpu": [100.0, None],
            "actual_memory": [7.5, None],
            "cpu_target_status": ["available", "no_next_occurrence"],
            "memory_target_status": ["available", "no_next_occurrence"],
            "cpu_exceeded": pd.Series([False, None], dtype="boolean"),
            "memory_exceeded": pd.Series([False, None], dtype="boolean"),
            "cpu_basis": ["history", "request_fallback"],
            "memory_basis": ["history", "request_fallback"],
            "cpu_history_run_count": pd.Series([12, 0], dtype="Int64"),
            "memory_history_run_count": pd.Series([12, 0], dtype="Int64"),
            "is_latest": [False, True],
        }
    )


def workload_frame():
    return pd.DataFrame(
        {
            "workload_id": ["g1||t1"],
            "display_name": ["g1 / t1"],
            "test_run_count": [3],
            "scored_run_count": [2],
            "first_start_time_us": [1_000],
            "last_start_time_us": [3_000],
            "latest_occurrence_id": ["g1||j3"],
            "latest_uses_history": [True],
            "has_scored_history": [True],
        }
    )


def test_dataset_ids_and_specs_agree():
    assert set(DATASETS) == set(DATASET_IDS) == {"google_clusterdata2019", "alibaba_gpu_v2020"}
    assert DATASETS[ALIBABA].primary_resource == "memory"
    assert DATASETS[GOOGLE].primary_resource is None


def test_units_and_semantics_match_capability_profiles():
    with open(CAPABILITY_CONFIG_PATH, encoding="utf-8") as handle:
        profiles = {entry["dataset_id"]: entry for entry in json.load(handle)["datasets"]}

    for dataset_id, spec in DATASETS.items():
        profile = profiles[dataset_id]
        assert spec.cpu.unit == profile["cpu_unit"]
        assert spec.memory.unit == profile["memory_unit"]
        assert spec.cpu.semantics == profile["cpu_target_semantics"]
        assert spec.memory.semantics == profile["memory_target_semantics"]


@pytest.mark.parametrize("dataset_id", [GOOGLE, ALIBABA])
def test_policy_names_match_committed_summary_csv(dataset_id):
    policies = pd.read_csv(SUMMARY_CSVS[dataset_id], usecols=["policy"])["policy"].tolist()

    assert policies == list(POLICY_NAMES)


def test_policy_ids_round_trip():
    assert POLICY_IDS["Hybrid"] == "hybrid"
    assert all(POLICY_BY_ID[POLICY_IDS[name]] == name for name in POLICY_NAMES)


def test_target_statuses_reuse_canonical_vocabulary():
    status_columns = [spec for spec in RECOMMENDATION_COLUMNS if spec.name.endswith("_target_status")]

    assert len(status_columns) == 2
    assert all(spec.allowed == frozenset(TARGET_STATUSES) for spec in status_columns)


def test_column_lists_match_issue():
    assert len(RECOMMENDATION_COLUMNS) == 22
    assert len(WORKLOAD_COLUMNS) == 9
    assert len({spec.name for spec in RECOMMENDATION_COLUMNS}) == 22


def test_error_body():
    assert error_body("not_found", "unknown workload") == {
        "error": {"code": "not_found", "message": "unknown workload"}
    }
    with pytest.raises(ValueError):
        error_body("teapot", "no")


def test_valid_frames_pass():
    validate_frame(recommendation_frame(), RECOMMENDATION_COLUMNS, "recommendations")
    validate_frame(workload_frame(), WORKLOAD_COLUMNS, "workloads")


def test_missing_column_rejected():
    frame = recommendation_frame().drop(columns=["is_latest"])

    with pytest.raises(BundleContractError, match=r"missing \['is_latest'\]"):
        validate_frame(frame, RECOMMENDATION_COLUMNS, "recommendations")


def test_extra_column_rejected():
    frame = workload_frame().assign(score=1.0)

    with pytest.raises(BundleContractError, match=r"extra \['score'\]"):
        validate_frame(frame, WORKLOAD_COLUMNS, "workloads")


def test_wrong_order_rejected():
    frame = workload_frame()
    frame = frame[[frame.columns[1], frame.columns[0], *frame.columns[2:]]]

    with pytest.raises(BundleContractError, match="wrong order"):
        validate_frame(frame, WORKLOAD_COLUMNS, "workloads")


def test_wrong_type_rejected():
    frame = recommendation_frame().assign(start_time_us=[1.0, 2.0])

    with pytest.raises(BundleContractError, match="start_time_us: expected int64"):
        validate_frame(frame, RECOMMENDATION_COLUMNS, "recommendations")


def test_null_in_non_nullable_column_rejected():
    frame = recommendation_frame()
    frame["workload_id"] = pd.Series(["g1||t1", None], dtype="string")

    with pytest.raises(BundleContractError, match="workload_id: 1 nulls"):
        validate_frame(frame, RECOMMENDATION_COLUMNS, "recommendations")


def test_null_actual_is_kept_not_zero():
    frame = recommendation_frame()

    validate_frame(frame, RECOMMENDATION_COLUMNS, "recommendations")
    assert pd.isna(frame.loc[1, "actual_cpu"])


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("policy", "P80"),
        ("cpu_basis", "guess"),
        ("memory_target_status", "next_occurrence_missing_value"),
    ],
)
def test_value_outside_allowed_list_rejected(column, value):
    frame = recommendation_frame()
    frame.loc[0, column] = value

    with pytest.raises(BundleContractError, match=f"{column}: values not allowed"):
        validate_frame(frame, RECOMMENDATION_COLUMNS, "recommendations")


def test_non_string_in_string_column_rejected():
    frame = workload_frame().astype({"display_name": object})
    frame.loc[0, "display_name"] = 7

    with pytest.raises(BundleContractError, match="display_name: non-string"):
        validate_frame(frame, WORKLOAD_COLUMNS, "workloads")
