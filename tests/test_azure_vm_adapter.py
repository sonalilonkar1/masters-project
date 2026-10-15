import pandas as pd
import pytest

from src.adapters.azure_vm import AzureVMAdapter


def make_vm_table():
    return pd.DataFrame([
        {
            "vm_id": "vm1",
            "subscription_id": "s1",
            "deployment_id": "d1",
            "vm_created": 0,
            "vm_deleted": 600,
            "max_cpu": 80.0,
            "avg_cpu": 35.0,
            "p95_max_cpu": 70.0,
            "vm_category": "Interactive",
            "vm_core_count_bucket": 4.0,
            "vm_memory_bucket": 14.0,
        },
        {
            "vm_id": "vm2",
            "subscription_id": "s1",
            "deployment_id": "d1",
            "vm_created": 0,
            "vm_deleted": 0,
            "max_cpu": 50.0,
            "avg_cpu": 20.0,
            "p95_max_cpu": 45.0,
            "vm_category": "Interactive",
            "vm_core_count_bucket": 2.0,
            "vm_memory_bucket": 7.0,
        },
    ])


def make_cpu():
    return pd.DataFrame([
        {
            "timestamp": 0,
            "vm_id": "vm1",
            "min_cpu": 10.0,
            "max_cpu": 60.0,
            "avg_cpu": 30.0,
        },
        {
            "timestamp": 300,
            "vm_id": "vm1",
            "min_cpu": 12.0,
            "max_cpu": 70.0,
            "avg_cpu": 34.0,
        },
    ])


def test_azure_vm_table_canonical_view():
    result = AzureVMAdapter().adapt_vm_table(
        make_vm_table()
    )
    out = result.canonical

    assert len(out) == 2
    assert set(out["workload_id"]) == {"d1"}
    assert out.loc[0, "allocated_cpu"] == 4.0
    assert out.loc[0, "allocated_memory"] == 14.0
    assert out.loc[0, "observed_cpu"] == 35.0
    assert out["observed_memory"].isna().all()


def test_azure_equal_create_delete_is_preserved():
    result = AzureVMAdapter().adapt_vm_table(
        make_vm_table()
    )
    out = result.canonical

    vm2 = out.loc[
        out["instance_id"] == "vm2"
    ].iloc[0]

    assert vm2["start_time_us"] == vm2["end_time_us"]
    assert bool(vm2["source_equal_create_delete"]) is True


def test_azure_cpu_intervals_map_to_canonical():
    result = AzureVMAdapter().adapt_cpu_readings(
        make_vm_table(),
        make_cpu(),
    )
    out = result.canonical

    assert len(out) == 2
    assert set(out["instance_id"]) == {"vm1"}
    assert out["aggregation_window_sec"].eq(300).all()
    assert list(out["event_time_us"]) == [
        0,
        300_000_000,
    ]
    assert list(out["observed_cpu"]) == [30.0, 34.0]
    assert list(out["peak_cpu"]) == [60.0, 70.0]
    assert out["observed_memory"].isna().all()


def test_azure_cpu_and_memory_semantics_remain_distinct():
    out = AzureVMAdapter().adapt_cpu_readings(
        make_vm_table(),
        make_cpu(),
    ).canonical

    assert out["allocated_memory"].notna().all()
    assert out["observed_memory"].isna().all()
    assert out["peak_memory"].isna().all()


def test_azure_zero_overlap_fails_clearly():
    cpu = make_cpu().copy()
    cpu["vm_id"] = "different-vm"

    with pytest.raises(ValueError, match="zero overlapping"):
        AzureVMAdapter().prepare_cpu_intervals(
            make_vm_table(),
            cpu,
        )

def test_azure_empty_vm_table_rejected():
    empty = pd.DataFrame(columns=[
        "vm_id",
        "subscription_id",
        "deployment_id",
        "vm_created",
        "vm_deleted",
        "max_cpu",
        "avg_cpu",
        "p95_max_cpu",
        "vm_category",
        "vm_core_count_bucket",
        "vm_memory_bucket",
    ])

    with pytest.raises(ValueError, match="empty"):
        AzureVMAdapter().adapt_vm_table(empty)

def test_azure_empty_vm_table_rejected():
    empty = pd.DataFrame(columns=[
        "vm_id",
        "subscription_id",
        "deployment_id",
        "vm_created",
        "vm_deleted",
        "max_cpu",
        "avg_cpu",
        "p95_max_cpu",
        "vm_category",
        "vm_core_count_bucket",
        "vm_memory_bucket",
    ])

    with pytest.raises(ValueError, match="empty"):
        AzureVMAdapter().adapt_vm_table(empty)


def test_azure_missing_capacity_marks_rows_partial():
    vm = make_vm_table()
    vm.loc[0, "vm_core_count_bucket"] = None
    vm.loc[0, "vm_memory_bucket"] = None

    adapter = AzureVMAdapter()

    lifecycle = adapter.adapt_vm_table(vm).canonical

    vm1_lifecycle = lifecycle.loc[
        lifecycle["instance_id"] == "vm1"
    ].iloc[0]

    assert vm1_lifecycle["validity_status"] == "partial"

    intervals = adapter.adapt_cpu_readings(
        vm,
        make_cpu(),
    ).canonical

    assert intervals["validity_status"].eq("partial").all()
    
    
def test_azure_duplicate_vm_metadata_rejected():
    vm = pd.concat(
        [make_vm_table(), make_vm_table().iloc[[0]]],
        ignore_index=True,
    )

    with pytest.raises(ValueError, match="unique vm_id"):
        AzureVMAdapter().adapt_vm_table(vm)
