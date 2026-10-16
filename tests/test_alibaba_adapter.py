import pandas as pd
import pytest

from src.adapters.alibaba import Alibaba2018Adapter
from src.adapters.validation import AdapterValidationError


def make_task():
    return pd.DataFrame(
        [
            {
                "task_name": "M1",
                "instance_num": 2,
                "job_name": "j1",
                "task_type": 1,
                "status": "Terminated",
                "start_time": 10,
                "end_time": 20,
                "plan_cpu": 100.0,
                "plan_mem": 0.5,
            }
        ]
    )


def make_instances():
    return pd.DataFrame(
        [
            {
                "instance_name": "i1",
                "task_name": "M1",
                "job_name": "j1",
                "task_type": 1,
                "status": "Terminated",
                "start_time": 10,
                "end_time": 20,
                "machine_id": "m1",
                "seq_no": 1,
                "total_seq_no": 1,
                "cpu_avg": 60.0,
                "cpu_max": 120.0,
                "mem_avg": 0.3,
                "mem_max": 0.45,
            },
            {
                "instance_name": "i2",
                "task_name": "M1",
                "job_name": "j1",
                "task_type": 1,
                "status": "Running",
                "start_time": 12,
                "end_time": 0,
                "machine_id": "m2",
                "seq_no": 1,
                "total_seq_no": 1,
                "cpu_avg": None,
                "cpu_max": None,
                "mem_avg": None,
                "mem_max": None,
            },
        ]
    )


def test_alibaba_tables_map_to_canonical():
    result = Alibaba2018Adapter().adapt_tables(
        make_task(),
        make_instances(),
    )
    out = result.canonical

    assert len(out) == 2
    assert set(out["workload_id"]) == {"j1"}
    assert set(out["execution_id"]) == {"j1|M1"}
    assert set(out["instance_id"]) == {"i1", "i2"}
    assert out.loc[0, "requested_cpu"] == 100.0
    assert out.loc[0, "peak_cpu"] == 120.0
    assert out.loc[0, "peak_memory"] == 0.45


def test_alibaba_recurrence_is_not_invented():
    out = Alibaba2018Adapter().adapt_tables(
        make_task(),
        make_instances(),
    ).canonical

    assert "recurrence_key" not in out.columns


def test_alibaba_running_missing_values_stay_null():
    out = Alibaba2018Adapter().adapt_tables(
        make_task(),
        make_instances(),
    ).canonical

    running = out.loc[
        out["instance_id"] == "i2"
    ].iloc[0]

    assert pd.isna(running["end_time_us"])
    assert pd.isna(running["observed_cpu"])
    assert pd.isna(running["peak_memory"])
    assert running["cpu_validity_status"] == "partial"
    assert running["memory_validity_status"] == "partial"
    assert running["validity_status"] == "partial"


def test_alibaba_unmatched_task_metadata_remains_null():
    instances = make_instances().copy()
    instances.loc[0, "job_name"] = "unmatched"

    out = Alibaba2018Adapter().adapt_tables(
        make_task(),
        instances,
    ).canonical

    row = out.loc[
        out["workload_id"] == "unmatched"
    ].iloc[0]

    assert pd.isna(row["requested_cpu"])
    assert pd.isna(row["requested_memory"])
    assert bool(row["source_task_metadata_matched"]) is False
    assert row["validity_status"] == "partial"


def test_alibaba_duplicate_task_plan_rejected():
    task = pd.concat(
        [make_task(), make_task()],
        ignore_index=True,
    )

    with pytest.raises(
        ValueError,
        match="duplicate",
    ):
        Alibaba2018Adapter().prepare_source(
            task,
            make_instances(),
        )


def test_alibaba_uses_dataset_specific_units():
    out = Alibaba2018Adapter().adapt_tables(
        make_task(),
        make_instances(),
    ).canonical

    row = out.iloc[0]

    assert (
        row["requested_cpu_unit"]
        == "alibaba_plan_cpu_100_per_core"
    )
    assert (
        row["observed_cpu_unit"]
        == "alibaba_cpu_usage_source_unit"
    )
    assert (
        row["peak_cpu_unit"]
        == "alibaba_cpu_usage_source_unit"
    )
    assert (
        row["requested_memory_unit"]
        == "alibaba_memory_source_normalized"
    )
    assert (
        row["observed_memory_unit"]
        == "alibaba_memory_source_normalized"
    )
    assert (
        row["peak_memory_unit"]
        == "alibaba_memory_source_normalized"
    )


def test_alibaba_resource_validity_is_independent():
    instances = make_instances().copy()
    instances.loc[0, "mem_max"] = None

    out = Alibaba2018Adapter().adapt_tables(
        make_task(),
        instances,
    ).canonical

    row = out.loc[
        out["instance_id"] == "i1"
    ].iloc[0]

    assert row["cpu_validity_status"] == "valid"
    assert row["memory_validity_status"] == "partial"
    assert row["validity_status"] == "partial"


def test_alibaba_avg_greater_than_max_is_flagged():
    instances = make_instances().copy()

    instances.loc[0, "cpu_avg"] = 150.0
    instances.loc[0, "cpu_max"] = 120.0

    out = Alibaba2018Adapter().adapt_tables(
        make_task(),
        instances,
    ).canonical

    row = out.loc[
        out["instance_id"] == "i1"
    ].iloc[0]

    assert bool(row["source_cpu_avg_gt_max"]) is True
    assert row["cpu_validity_status"] == "invalid"
    assert row["validity_status"] == "invalid"


def test_alibaba_memory_avg_greater_than_max_is_flagged():
    instances = make_instances().copy()

    instances.loc[0, "mem_avg"] = 0.6
    instances.loc[0, "mem_max"] = 0.45

    out = Alibaba2018Adapter().adapt_tables(
        make_task(),
        instances,
    ).canonical

    row = out.loc[
        out["instance_id"] == "i1"
    ].iloc[0]

    assert bool(row["source_memory_avg_gt_max"]) is True
    assert row["memory_validity_status"] == "invalid"
    assert row["validity_status"] == "invalid"


def test_alibaba_duplicate_instance_retry_record_rejected():
    instances = make_instances()

    duplicate = instances.iloc[[0]].copy()

    instances = pd.concat(
        [instances, duplicate],
        ignore_index=True,
    )

    with pytest.raises(
        AdapterValidationError,
        match="Duplicate canonical instance",
    ):
        Alibaba2018Adapter().adapt_tables(
            make_task(),
            instances,
        )


def test_alibaba_invalid_numeric_resource_rejected():
    instances = make_instances().copy()
    instances["cpu_max"] = instances["cpu_max"].astype("object")
    instances.loc[0, "cpu_max"] = "not-a-number"

    with pytest.raises(
        ValueError,
        match="cpu_max contains non-numeric",
    ):
        Alibaba2018Adapter().adapt_tables(
            make_task(),
            instances,
        )


def test_alibaba_metadata_contains_capabilities_and_validity_counts():
    result = Alibaba2018Adapter().adapt_tables(
        make_task(),
        make_instances(),
    )

    capabilities = result.metadata["capabilities"]

    assert capabilities["supports_cpu"] is True
    assert capabilities["supports_memory"] is True
    assert capabilities["supports_recurrence"] is False
    assert capabilities["supports_targets"] is False
    assert capabilities["supports_ml"] is False

    assert result.metadata["cpu_valid_count"] == 1
    assert result.metadata["cpu_partial_count"] == 1
    assert result.metadata["cpu_invalid_count"] == 0

    assert result.metadata["memory_valid_count"] == 1
    assert result.metadata["memory_partial_count"] == 1
    assert result.metadata["memory_invalid_count"] == 0
