import pandas as pd
import pytest

from src.adapters.reference import ReferenceOccurrenceAdapter
from src.adapters.validation import (
    AdapterValidationError,
    validate_adapter_output,
)
from src.canonical.schema import (
    AZURE_VM_CAPABILITIES,
    SCHEMA_VERSION,
)


def make_source():
    return pd.DataFrame(
        [
            {
                "source_workload": "w1",
                "source_occurrence": "w1||100",
                "source_start_us": 100,
                "source_end_us": 200,
                "source_request_cpu": 2.0,
                "source_peak_cpu": 1.4,
            },
            {
                "source_workload": "w1",
                "source_occurrence": "w1||300",
                "source_start_us": 300,
                "source_end_us": 420,
                "source_request_cpu": 2.0,
                "source_peak_cpu": 1.6,
            },
        ]
    )


def test_reference_adapter_returns_valid_result():
    result = ReferenceOccurrenceAdapter().adapt(make_source())

    assert len(result.canonical) == 2
    assert result.metadata["source_row_count"] == 2
    assert result.metadata["canonical_row_count"] == 2
    assert "capabilities" in result.metadata


def test_adapter_is_deterministic():
    adapter = ReferenceOccurrenceAdapter()

    pd.testing.assert_frame_equal(
        adapter.adapt(make_source()).canonical,
        adapter.adapt(make_source()).canonical,
    )


def test_adapter_does_not_mutate_source():
    adapter = ReferenceOccurrenceAdapter()
    source = make_source()
    before = source.copy(deep=True)

    adapter.adapt(source)

    pd.testing.assert_frame_equal(source, before)


def test_missing_source_column_fails_clearly():
    source = make_source().drop(columns=["source_peak_cpu"])

    with pytest.raises(
        ValueError,
        match="missing required columns",
    ):
        ReferenceOccurrenceAdapter().adapt(source)


def test_wrong_dataset_id_rejected():
    frame = pd.DataFrame(
        [
            {
                "schema_version": SCHEMA_VERSION,
                "dataset_id": "wrong",
                "record_level": "interval",
                "workload_id": "d1",
                "execution_id": "vm1",
                "instance_id": "vm1",
                "time_basis": "trace_relative",
                "event_time_us": 0,
                "validity_status": "valid",
                "allocated_cpu": 4.0,
                "allocated_cpu_unit": "vcpu",
                "allocated_memory": 14.0,
                "allocated_memory_unit": "gb",
                "observed_cpu": 25.0,
                "observed_cpu_unit": "percent",
            }
        ]
    )

    with pytest.raises(
        AdapterValidationError,
        match="dataset_id",
    ):
        validate_adapter_output(
            frame,
            capabilities=AZURE_VM_CAPABILITIES,
        )


def test_unsupported_azure_observed_memory_rejected():
    frame = pd.DataFrame(
        [
            {
                "schema_version": SCHEMA_VERSION,
                "dataset_id": AZURE_VM_CAPABILITIES.dataset_id,
                "record_level": "interval",
                "workload_id": "d1",
                "execution_id": "vm1",
                "instance_id": "vm1",
                "time_basis": "trace_relative",
                "event_time_us": 0,
                "validity_status": "valid",
                "allocated_cpu": 4.0,
                "allocated_cpu_unit": "vcpu",
                "allocated_memory": 14.0,
                "allocated_memory_unit": "gb",
                "observed_cpu": 25.0,
                "observed_cpu_unit": "percent",
                "observed_memory": 3.2,
                "observed_memory_unit": "gb",
            }
        ]
    )

    with pytest.raises(
        AdapterValidationError,
        match="observed memory",
    ):
        validate_adapter_output(
            frame,
            capabilities=AZURE_VM_CAPABILITIES,
        )


def test_missing_optional_values_stay_null():
    out = ReferenceOccurrenceAdapter().adapt(
        make_source()
    ).canonical

    assert out["requested_memory"].isna().all()
    assert out["peak_memory"].isna().all()


def test_nonfinite_resource_rejected():
    source = make_source()
    source.loc[0, "source_peak_cpu"] = float("inf")

    with pytest.raises(
        AdapterValidationError,
        match="non-finite",
    ):
        ReferenceOccurrenceAdapter().adapt(source)


def test_raw_source_names_do_not_leak_downstream():
    out = ReferenceOccurrenceAdapter().adapt(
        make_source()
    ).canonical

    assert "source_workload" not in out.columns
    assert "source_occurrence" not in out.columns
    assert "source_peak_cpu" not in out.columns

    assert {
        "workload_id",
        "occurrence_id",
        "peak_cpu",
    } <= set(out.columns)


def test_duplicate_interval_records_rejected():
    row = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": AZURE_VM_CAPABILITIES.dataset_id,
        "record_level": "interval",
        "workload_id": "deployment-1",
        "execution_id": "vm-1",
        "instance_id": "vm-1",
        "time_basis": "trace_relative",
        "event_time_us": 0,
        "validity_status": "valid",
        "allocated_cpu": 4.0,
        "allocated_cpu_unit": "vcpu",
        "allocated_memory": 14.0,
        "allocated_memory_unit": "gb",
        "observed_cpu": 20.0,
        "observed_cpu_unit": "percent",
    }

    frame = pd.DataFrame([row, row])

    with pytest.raises(
        AdapterValidationError,
        match="Duplicate canonical interval",
    ):
        validate_adapter_output(
            frame,
            capabilities=AZURE_VM_CAPABILITIES,
        )
