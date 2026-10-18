import pandas as pd
import pytest

from src.adapters.reference import ReferenceOccurrenceAdapter
from src.adapters.validation import (
    AdapterValidationError,
    validate_adapter_output,
)
from src.canonical.schema import (
    ALIBABA_CAPABILITIES,
    ALIBABA_GPU_2020_CAPABILITIES,
    AZURE_VM_CAPABILITIES,
    GOOGLE_CAPABILITIES,
    SCHEMA_VERSION,
    validate_canonical_frame,
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


# ===========================================================================
# Schema 0.2.0 adapter-output validation (PR #70 follow-up).
# Test IDs (V-nn) refer to
# docs/planning/github_issues/pr70_schema_followup_review.md §7.2.
# ===========================================================================

def gpu_role_row(**overrides):
    """A valid Alibaba GPU 2020 role_occurrence row for a job with a group."""
    row = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": ALIBABA_GPU_2020_CAPABILITIES.dataset_id,
        "record_level": "role_occurrence",
        "workload_id": "g1",
        "recurrence_key": "g1||worker",
        "occurrence_id": "g1||job1",
        "role_key": "g1||job1||worker",
        "time_basis": "trace_relative",
        "start_time_us": 1_000,
        "end_time_us": 2_000,
        "validity_status": "valid",
        "requested_cpu": 600.0,
        "requested_cpu_unit": "percent_of_vcpu",
        "observed_cpu": 250.0,
        "observed_cpu_unit": "percent_of_vcpu",
        "exclusion_reason": None,
    }
    row.update(overrides)
    return row


def gpu_instance_row(**overrides):
    """A valid Alibaba GPU 2020 instance audit row whose parent is gpu_role_row()."""
    row = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": ALIBABA_GPU_2020_CAPABILITIES.dataset_id,
        "record_level": "instance",
        "workload_id": "g1",
        "recurrence_key": "g1||worker",
        "occurrence_id": "g1||job1",
        "role_key": "g1||job1||worker",
        "execution_id": "job1||worker",
        "instance_id": "job1||worker||inst1||1",
        "time_basis": "trace_relative",
        "event_time_us": 1_000,
        "validity_status": "valid",
    }
    row.update(overrides)
    return row


def validate_gpu(rows):
    validate_adapter_output(
        pd.DataFrame(rows),
        capabilities=ALIBABA_GPU_2020_CAPABILITIES,
    )


# --- role_occurrence uniqueness (V-01 to V-03) ------------------------------

def test_duplicate_role_key_rejected():  # V-01
    with pytest.raises(AdapterValidationError, match="Duplicate canonical role_occurrence"):
        validate_gpu([gpu_role_row(), gpu_role_row()])


def test_null_role_key_rejected():  # V-02
    with pytest.raises(AdapterValidationError, match="role_key must not be null"):
        validate_gpu([gpu_role_row(role_key=None)])


def test_missing_role_key_column_rejected():  # V-02
    row = gpu_role_row()
    del row["role_key"]
    with pytest.raises(AdapterValidationError, match="require a role_key column"):
        validate_gpu([row])


def test_two_roles_of_one_job_pass():  # V-03
    validate_gpu([
        gpu_role_row(),
        gpu_role_row(recurrence_key="g1||ps", role_key="g1||job1||ps"),
    ])


# --- profile-driven identity on instance rows (V-04, V-05) ------------------

@pytest.mark.parametrize("col", ["role_key", "instance_id"])
def test_gpu_instance_null_identity_rejected(col):  # V-04
    with pytest.raises(AdapterValidationError, match=f"{col} must not be null on instance"):
        validate_gpu([gpu_instance_row(**{col: None})])


def test_gpu_duplicate_instance_id_rejected():  # V-05
    with pytest.raises(AdapterValidationError, match="Duplicate canonical instance"):
        validate_gpu([gpu_instance_row(), gpu_instance_row()])


def test_gpu_instance_attempts_pass():  # V-05
    validate_gpu([
        gpu_instance_row(),
        gpu_instance_row(instance_id="job1||worker||inst1||2"),
    ])


def test_alibaba_2018_null_instance_id_still_allowed():
    # The identity rule is gated on role_occurrence, so Alibaba 2018 keeps
    # its 0.1.0 behavior.
    row = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": ALIBABA_CAPABILITIES.dataset_id,
        "record_level": "instance",
        "workload_id": "j1",
        "execution_id": "j1|M1",
        "instance_id": None,
        "time_basis": "trace_relative",
        "start_time_us": 0,
        "validity_status": "valid",
    }
    validate_adapter_output(pd.DataFrame([row]), capabilities=ALIBABA_CAPABILITIES)


# --- recurrence-key rule (V-06 to V-08) -------------------------------------

def test_fallback_role_without_key_passes():  # V-06
    validate_gpu([gpu_role_row(
        workload_id="job2",
        occurrence_id="job2",
        role_key="job2||worker",
        recurrence_key=None,
        exclusion_reason="no_recurrence_key",
    )])


def test_grouped_role_without_key_rejected():  # V-07
    with pytest.raises(AdapterValidationError, match="recurrence_key may be null"):
        validate_gpu([gpu_role_row(recurrence_key=None)])


def test_instance_row_null_key_not_checked_here():
    # Instance rows of a no-group job inherit a null key and carry no
    # exclusion reason; linkage is checked in Task 1, not here.
    validate_gpu([gpu_instance_row(recurrence_key=None)])


def test_alibaba_2018_recurrence_key_keeps_existing_message():  # V-08
    row = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": ALIBABA_CAPABILITIES.dataset_id,
        "record_level": "instance",
        "workload_id": "j1",
        "instance_id": "i1",
        "recurrence_key": "invented",
        "time_basis": "trace_relative",
        "start_time_us": 0,
        "validity_status": "valid",
    }
    with pytest.raises(AdapterValidationError, match="recurrence unsupported"):
        validate_adapter_output(pd.DataFrame([row]), capabilities=ALIBABA_CAPABILITIES)


def test_azure_recurrence_key_keeps_existing_message():  # V-08
    row = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": AZURE_VM_CAPABILITIES.dataset_id,
        "record_level": "interval",
        "workload_id": "d1",
        "instance_id": "vm1",
        "recurrence_key": "invented",
        "time_basis": "trace_relative",
        "event_time_us": 0,
        "validity_status": "valid",
    }
    with pytest.raises(AdapterValidationError, match="recurrence unsupported"):
        validate_adapter_output(pd.DataFrame([row]), capabilities=AZURE_VM_CAPABILITIES)


# --- adapters must not emit splits or targets (V-09, V-10) ------------------

@pytest.mark.parametrize(
    "extra",
    [
        {"split": "train"},
        {"actual_cpu": 240.0, "actual_cpu_unit": "percent_of_vcpu"},
        {"actual_memory": 12.0, "actual_memory_unit": "gb"},
        {"cpu_target_status": "available"},
        {"memory_target_status": "no_next_occurrence"},
    ],
)
def test_adapter_target_builder_columns_rejected(extra):  # V-09
    with pytest.raises(AdapterValidationError, match="target-builder columns"):
        validate_gpu([gpu_role_row(**extra)])


def test_google_contract_view_keeps_precomputed_targets():  # V-10
    row = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": GOOGLE_CAPABILITIES.dataset_id,
        "record_level": "occurrence",
        "workload_id": "rk1",
        "occurrence_id": "rk1||100",
        "recurrence_key": "rk1",
        "time_basis": "trace_relative",
        "start_time_us": 100,
        "validity_status": "valid",
        "peak_cpu": 1.2,
        "peak_cpu_unit": "ncu",
        "actual_cpu": 1.4,
        "actual_cpu_unit": "ncu",
        "actual_memory": 0.3,
        "actual_memory_unit": "normalized",
    }
    validate_canonical_frame(pd.DataFrame([row]), GOOGLE_CAPABILITIES)
