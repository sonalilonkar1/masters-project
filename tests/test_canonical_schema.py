import json
from pathlib import Path

import pandas as pd
import pytest

from src.canonical.schema import (
    ALIBABA_CAPABILITIES,
    ALIBABA_GPU_2020_CAPABILITIES,
    ALIBABA_GPU_2020_EXCLUSION_REASONS,
    AZURE_VM_CAPABILITIES,
    DEFAULT_CAPABILITY_REGISTRY,
    GOOGLE_CAPABILITIES,
    RECORD_LEVELS,
    SCHEMA_VERSION,
    TARGET_STATUSES,
    CanonicalSchemaError,
    DatasetCapabilities,
    records_to_frame,
    validate_canonical_frame,
    validate_evaluator_view,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PATH = REPO_ROOT / "examples" / "canonical_records.jsonl"
CAPABILITY_CONFIG_PATH = REPO_ROOT / "config" / "dataset_capabilities.json"


def load_examples():
    return [
        json.loads(line)
        for line in EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.mark.parametrize(
    "idx,caps",
    [
        (0, GOOGLE_CAPABILITIES),
        (1, ALIBABA_CAPABILITIES),
        (2, AZURE_VM_CAPABILITIES),
    ],
)
def test_examples_validate(idx, caps):
    validate_canonical_frame(
        records_to_frame([load_examples()[idx]]),
        caps,
    )


def test_azure_observed_memory_rejected():
    record = load_examples()[2]
    record["observed_memory"] = 2.0
    record["observed_memory_unit"] = "gb"

    with pytest.raises(
        CanonicalSchemaError,
        match="observed memory unsupported",
    ):
        validate_canonical_frame(
            records_to_frame([record]),
            AZURE_VM_CAPABILITIES,
        )


def test_alibaba_unvalidated_recurrence_rejected():
    record = load_examples()[1]
    record["recurrence_key"] = "guessed-family"

    with pytest.raises(
        CanonicalSchemaError,
        match="recurrence unsupported",
    ):
        validate_canonical_frame(
            records_to_frame([record]),
            ALIBABA_CAPABILITIES,
        )


def test_missing_optional_value_not_zero_filled():
    frame = records_to_frame([load_examples()[2]])

    validate_canonical_frame(
        frame,
        AZURE_VM_CAPABILITIES,
    )

    assert pd.isna(frame.loc[0, "observed_memory"])


def test_negative_resource_rejected():
    record = load_examples()[0]
    record["peak_cpu"] = -1

    with pytest.raises(
        CanonicalSchemaError,
        match="must be non-negative",
    ):
        validate_canonical_frame(
            records_to_frame([record]),
            GOOGLE_CAPABILITIES,
        )


def test_resource_requires_unit():
    record = load_examples()[0]
    record["peak_cpu_unit"] = None

    with pytest.raises(
        CanonicalSchemaError,
        match="required whenever",
    ):
        validate_canonical_frame(
            records_to_frame([record]),
            GOOGLE_CAPABILITIES,
        )


def test_unknown_resource_unit_rejected():
    record = load_examples()[0]
    record["peak_cpu_unit"] = "made_up_unit"

    with pytest.raises(
        CanonicalSchemaError,
        match="unsupported units",
    ):
        validate_canonical_frame(
            records_to_frame([record]),
            GOOGLE_CAPABILITIES,
        )


def test_azure_actual_memory_rejected_when_targets_unsupported():
    record = load_examples()[2]
    record["actual_memory"] = 0.0
    record["actual_memory_unit"] = "gb"

    with pytest.raises(
        CanonicalSchemaError,
        match="targets unsupported",
    ):
        validate_canonical_frame(
            records_to_frame([record]),
            AZURE_VM_CAPABILITIES,
        )


def test_alibaba_actual_cpu_rejected_when_targets_unsupported():
    record = load_examples()[1]
    record["actual_cpu"] = 100.0
    record["actual_cpu_unit"] = "alibaba_cpu_usage_source_unit"

    with pytest.raises(
        CanonicalSchemaError,
        match="targets unsupported",
    ):
        validate_canonical_frame(
            records_to_frame([record]),
            ALIBABA_CAPABILITIES,
        )


def test_evaluator_cpu_only_valid():
    frame = pd.DataFrame(
        [
            {
                "dataset_id": "azure_public_vm_v2",
                "workload_id": "d1",
                "policy_name": "P95",
                "actual_cpu": 2.4,
                "actual_cpu_unit": "vcpu",
                "recommended_cpu": 2.8,
                "recommended_cpu_unit": "vcpu",
                "actual_memory": None,
                "actual_memory_unit": None,
                "recommended_memory": None,
                "recommended_memory_unit": None,
            }
        ]
    )

    validate_evaluator_view(frame)


def test_evaluator_unit_mismatch_rejected():
    frame = pd.DataFrame(
        [
            {
                "dataset_id": "google_clusterdata2019",
                "workload_id": "rk1",
                "policy_name": "P95",
                "actual_cpu": 1.0,
                "actual_cpu_unit": "ncu",
                "recommended_cpu": 2.0,
                "recommended_cpu_unit": "vcpu",
                "actual_memory": None,
                "actual_memory_unit": None,
                "recommended_memory": None,
                "recommended_memory_unit": None,
            }
        ]
    )

    with pytest.raises(
        CanonicalSchemaError,
        match="units must match",
    ):
        validate_evaluator_view(frame)


def test_capability_json_matches_python_registry():
    config = json.loads(
        CAPABILITY_CONFIG_PATH.read_text(encoding="utf-8")
    )

    assert config["schema_version"] == SCHEMA_VERSION

    configured = {
        item["dataset_id"]: item
        for item in config["datasets"]
    }

    assert set(configured) == set(DEFAULT_CAPABILITY_REGISTRY)

    for dataset_id, capabilities in DEFAULT_CAPABILITY_REGISTRY.items():
        expected = capabilities.to_dict().copy()

        # notes are documentation in Python, but intentionally not duplicated
        # in the machine-readable JSON capability config.
        expected.pop("notes", None)

        assert configured[dataset_id] == expected


# ===========================================================================
# Schema 0.2.0 tests (PR #70 follow-up).
# Test IDs (S-nn) refer to
# docs/planning/github_issues/pr70_schema_followup_review.md §7.1.
# ===========================================================================

# The ten 0.1.0 flags, used to check they did not change.
TEN_FLAGS = [
    "supports_cpu", "supports_memory", "supports_request", "supports_recurrence",
    "supports_targets", "supports_ml", "supports_observed_cpu",
    "supports_observed_memory", "supports_allocated_cpu", "supports_allocated_memory",
]


def base_row(caps, **overrides):
    """Smallest valid row for ``caps``; overrides add or replace fields."""
    row = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": caps.dataset_id,
        "record_level": "occurrence",
        "workload_id": "w1",
        "time_basis": "trace_relative",
        "start_time_us": 0,
        "validity_status": "valid",
    }
    row.update(overrides)
    return row


def gpu_row(**overrides):
    """A valid Alibaba GPU 2020 role_occurrence row."""
    fields = {"record_level": "role_occurrence", "role_key": "g1||job1||worker"}
    fields.update(overrides)
    return base_row(ALIBABA_GPU_2020_CAPABILITIES, **fields)


def validate(caps, *rows):
    validate_canonical_frame(pd.DataFrame(list(rows)), caps)


def make_caps(**overrides):
    """A test profile built positionally (like the 0.1.0 profiles) plus keywords."""
    return DatasetCapabilities(
        "test_dataset", True, True, True, True, True, True,
        True, True, False, False, "test profile", **overrides,
    )


# --- S-01 version ------------------------------------------------------------

def test_version_is_020_everywhere():
    assert SCHEMA_VERSION == "0.2.0"
    config = json.loads(CAPABILITY_CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["schema_version"] == "0.2.0"
    lines = EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()
    assert lines
    assert {json.loads(line)["schema_version"] for line in lines if line.strip()} == {"0.2.0"}


# --- S-02 record level -------------------------------------------------------

def test_role_occurrence_record_level_accepted():
    assert "role_occurrence" in RECORD_LEVELS
    validate(ALIBABA_GPU_2020_CAPABILITIES, gpu_row())


# --- S-03 / S-04 capability construction -------------------------------------

def test_positional_construction_resolves_average_and_peak_flags():
    # Same shape as the 0.1.0 Azure profile: observed CPU yes, observed memory no.
    caps = DatasetCapabilities(
        "positional", True, True, False, False, False, False,
        True, False, True, True, "notes",
    )
    assert caps.notes == "notes"
    assert caps.has_cpu_average is True and caps.has_cpu_peak is True
    assert caps.has_memory_average is False and caps.has_memory_peak is False


@pytest.mark.parametrize(
    "overrides",
    [
        # Observed CPU supported, but neither an average nor a peak.
        {"has_cpu_average": False, "has_cpu_peak": False},
        {"has_memory_average": False, "has_memory_peak": False},
    ],
)
def test_supported_observed_without_average_or_peak_rejected(overrides):
    with pytest.raises(CanonicalSchemaError, match="must equal"):
        make_caps(**overrides)


@pytest.mark.parametrize("resource", ["cpu", "memory"])
def test_peak_without_supported_observed_rejected(resource):
    # The reverse case: observed not supported, but a peak is declared.
    args = ["reverse", True, True, True, True, True, True, True, True, False, False]
    args[7 if resource == "cpu" else 8] = False
    with pytest.raises(CanonicalSchemaError, match="must equal"):
        DatasetCapabilities(*args, **{f"has_{resource}_peak": True})


# --- S-05 to_dict and JSON ---------------------------------------------------

def test_to_dict_returns_lists_and_matches_json_for_all_profiles():
    config = json.loads(CAPABILITY_CONFIG_PATH.read_text(encoding="utf-8"))
    configured = {item["dataset_id"]: item for item in config["datasets"]}
    assert set(configured) == set(DEFAULT_CAPABILITY_REGISTRY)
    assert len(configured) == 4
    for dataset_id, caps in DEFAULT_CAPABILITY_REGISTRY.items():
        data = caps.to_dict()
        assert isinstance(data["allowed_exclusion_reasons"], list)
        assert data["supported_record_levels"] is None or isinstance(data["supported_record_levels"], list)
        data.pop("notes")
        assert configured[dataset_id] == data


# --- S-06 profile values -----------------------------------------------------

def test_alibaba_gpu_2020_profile_values():
    caps = ALIBABA_GPU_2020_CAPABILITIES
    assert caps.dataset_id == "alibaba_gpu_v2020"
    assert all(getattr(caps, f) for f in TEN_FLAGS if not f.startswith("supports_allocated"))
    assert not caps.supports_allocated_cpu and not caps.supports_allocated_memory
    assert (caps.has_cpu_average, caps.has_cpu_peak) == (True, False)
    assert (caps.has_memory_average, caps.has_memory_peak) == (True, True)
    assert caps.recurrence_key_origin == "official_with_role"
    assert caps.observed_cpu_semantics == "lifetime_average"
    assert caps.peak_cpu_semantics is None
    assert caps.peak_memory_semantics == "lifetime_peak"
    assert caps.cpu_target_semantics == "next_occurrence_lifetime_average"
    assert caps.memory_target_semantics == "next_occurrence_lifetime_peak"
    assert caps.instance_event_time_semantics == "parent_job_submission"
    assert (caps.cpu_unit, caps.memory_unit) == ("percent_of_vcpu", "gb")
    assert caps.supported_record_levels == ("role_occurrence", "instance")
    assert caps.evaluation_record_level == "role_occurrence"
    assert caps.evaluation_mode == "next_occurrence_memory_peak_cpu_average"
    assert caps.allowed_exclusion_reasons == ALIBABA_GPU_2020_EXCLUSION_REASONS
    assert len(caps.allowed_exclusion_reasons) == 14
    assert caps.allowed_exclusion_reasons[0] == "no_recurrence_key"
    assert caps.allowed_exclusion_reasons[-1] == "invalid_resource"
    assert caps.any_resource_metric_valid is False
    assert caps.target_split_isolation is True


def test_google_profile_values():
    caps = GOOGLE_CAPABILITIES
    assert [getattr(caps, f) for f in TEN_FLAGS] == [True] * 8 + [False, False]
    assert (caps.has_cpu_average, caps.has_cpu_peak) == (False, True)
    assert (caps.has_memory_average, caps.has_memory_peak) == (False, True)
    assert caps.recurrence_key_origin == "constructed"
    assert (caps.cpu_unit, caps.memory_unit) == ("ncu", "normalized")
    assert caps.supported_record_levels == ("occurrence",)
    assert caps.evaluation_mode == "full_next_occurrence"
    assert caps.allowed_exclusion_reasons == ()
    assert caps.any_resource_metric_valid is True
    assert caps.target_split_isolation is False


def test_alibaba_2018_profile_values():
    caps = ALIBABA_CAPABILITIES
    assert [getattr(caps, f) for f in TEN_FLAGS] == [
        True, True, True, False, False, False, True, True, False, False,
    ]
    assert all([caps.has_cpu_average, caps.has_cpu_peak,
                caps.has_memory_average, caps.has_memory_peak])
    assert caps.recurrence_key_origin == "none"
    assert caps.cpu_unit is None
    assert caps.memory_unit == "alibaba_memory_source_normalized"
    assert caps.supported_record_levels == ("instance",)
    assert caps.evaluation_mode == "instance_request_versus_observed"


def test_azure_profile_holds_defaults():
    caps = AZURE_VM_CAPABILITIES
    assert [getattr(caps, f) for f in TEN_FLAGS] == [
        True, True, False, False, False, False, True, False, True, True,
    ]
    assert (caps.has_cpu_average, caps.has_cpu_peak) == (True, True)
    assert (caps.has_memory_average, caps.has_memory_peak) == (False, False)
    assert caps.recurrence_key_origin == "none"
    assert caps.supported_record_levels is None
    assert caps.allowed_exclusion_reasons == ()
    assert caps.any_resource_metric_valid is True
    assert caps.target_split_isolation is False
    assert caps.cpu_unit is None and caps.evaluation_mode is None


# --- S-07 to S-09 average versus peak ----------------------------------------

def test_gpu_peak_cpu_rejected():  # S-07
    with pytest.raises(CanonicalSchemaError, match="CPU peak unsupported"):
        validate(ALIBABA_GPU_2020_CAPABILITIES, gpu_row(peak_cpu=80.0, peak_cpu_unit="percent_of_vcpu"))


def test_gpu_average_cpu_with_null_peak_passes():  # S-08
    validate(
        ALIBABA_GPU_2020_CAPABILITIES,
        gpu_row(observed_cpu=50.0, observed_cpu_unit="percent_of_vcpu", peak_cpu=None),
    )


def test_google_observed_cpu_rejected():  # S-09
    with pytest.raises(CanonicalSchemaError, match="CPU average unsupported"):
        validate(GOOGLE_CAPABILITIES, base_row(GOOGLE_CAPABILITIES, observed_cpu=1.0, observed_cpu_unit="ncu"))


# --- S-10 to S-12 units and GPU fields ---------------------------------------

@pytest.mark.parametrize(
    "fields",
    [
        {"requested_cpu": 600.0, "requested_cpu_unit": "percent_of_vcpu"},
        {"requested_gpu": 50.0, "requested_gpu_unit": "percent_of_gpu"},
        {"observed_gpu": 25.0, "observed_gpu_unit": "percent_of_gpu"},
        {"peak_gpu_memory": 3.5, "peak_gpu_memory_unit": "gb"},
    ],
)
def test_new_units_and_gpu_fields_accepted(fields):  # S-10
    validate(ALIBABA_GPU_2020_CAPABILITIES, gpu_row(**fields))


def test_unknown_unit_still_rejected():  # S-10
    with pytest.raises(CanonicalSchemaError, match="unsupported units"):
        validate(ALIBABA_GPU_2020_CAPABILITIES, gpu_row(requested_gpu=50.0, requested_gpu_unit="gpu_cards"))


def test_gpu_value_without_unit_rejected():  # S-11
    with pytest.raises(CanonicalSchemaError, match="requested_gpu_unit required"):
        validate(ALIBABA_GPU_2020_CAPABILITIES, gpu_row(requested_gpu=50.0))


def test_negative_gpu_value_rejected():  # S-11
    with pytest.raises(CanonicalSchemaError, match="observed_gpu must be non-negative"):
        validate(ALIBABA_GPU_2020_CAPABILITIES, gpu_row(observed_gpu=-1.0, observed_gpu_unit="percent_of_gpu"))


def test_null_gpu_values_pass_and_stay_null():  # S-12
    frame = pd.DataFrame([gpu_row(requested_gpu=None, observed_gpu=None, peak_gpu_memory=None)])
    validate_canonical_frame(frame, ALIBABA_GPU_2020_CAPABILITIES)
    assert frame[["requested_gpu", "observed_gpu", "peak_gpu_memory"]].isna().all().all()


# --- S-13 to S-16 column vocabularies ----------------------------------------

@pytest.mark.parametrize(
    "col,good",
    [
        ("resource_scope", "task_role_per_instance"),
        ("request_aggregation_method", "none"),
        ("observed_aggregation_method", "maximum_over_instances"),
        ("cpu_validity_status", "partial"),
        ("memory_validity_status", "valid"),
    ],
)
def test_column_vocabularies(col, good):  # S-13, S-14
    validate(ALIBABA_GPU_2020_CAPABILITIES, gpu_row(**{col: good}))
    validate(ALIBABA_GPU_2020_CAPABILITIES, gpu_row(**{col: None}))
    with pytest.raises(CanonicalSchemaError, match=f"Unsupported {col} values"):
        validate(ALIBABA_GPU_2020_CAPABILITIES, gpu_row(**{col: "not_a_value"}))


def test_absent_vocabulary_columns_pass():  # S-13
    validate(ALIBABA_GPU_2020_CAPABILITIES, gpu_row())


@pytest.mark.parametrize("reason", ALIBABA_GPU_2020_EXCLUSION_REASONS)
def test_each_gpu_exclusion_reason_passes(reason):  # S-15
    validate(ALIBABA_GPU_2020_CAPABILITIES, gpu_row(exclusion_reason=reason))


def test_unknown_gpu_exclusion_reason_rejected():  # S-15
    with pytest.raises(CanonicalSchemaError, match="Unsupported exclusion_reason"):
        validate(ALIBABA_GPU_2020_CAPABILITIES, gpu_row(exclusion_reason="too_small"))


@pytest.mark.parametrize(
    "caps,record_level",
    [(GOOGLE_CAPABILITIES, "occurrence"), (AZURE_VM_CAPABILITIES, "interval")],
)
def test_exclusion_reason_rejected_without_profile_reasons(caps, record_level):  # S-15
    row = base_row(caps, record_level=record_level, exclusion_reason="no_recurrence_key")
    with pytest.raises(CanonicalSchemaError, match="Unsupported exclusion_reason"):
        validate(caps, row)


@pytest.mark.parametrize("col", ["cpu_target_status", "memory_target_status"])
def test_target_status_vocabulary(col):  # S-16
    # Uses the Google profile through validate_canonical_frame, where
    # precomputed targets are allowed.
    for status in sorted(TARGET_STATUSES):
        validate(GOOGLE_CAPABILITIES, base_row(GOOGLE_CAPABILITIES, **{col: status}))
    with pytest.raises(CanonicalSchemaError, match=f"Unsupported {col} values"):
        validate(GOOGLE_CAPABILITIES, base_row(GOOGLE_CAPABILITIES, **{col: "availble"}))


# --- S-17 supported record levels --------------------------------------------

def test_record_level_outside_profile_rejected():
    with pytest.raises(CanonicalSchemaError, match="Unsupported record_level values"):
        validate(ALIBABA_GPU_2020_CAPABILITIES, gpu_row(record_level="occurrence"))


def test_unrestricted_profile_allows_instance_and_interval():
    validate(
        AZURE_VM_CAPABILITIES,
        base_row(AZURE_VM_CAPABILITIES, record_level="instance", instance_id="vm1"),
        base_row(AZURE_VM_CAPABILITIES, record_level="interval", instance_id="vm1", event_time_us=0),
    )


# --- S-18 to S-20 instance event time ----------------------------------------

def gpu_instance_row(**overrides):
    row = base_row(
        ALIBABA_GPU_2020_CAPABILITIES,
        record_level="instance",
        role_key="g1||job1||worker",
        instance_id="job1||worker||inst1||1",
    )
    row.update(overrides)
    return row


def test_gpu_instance_without_event_time_rejected():  # S-18
    with pytest.raises(CanonicalSchemaError, match="event_time_us required on instance rows"):
        validate(ALIBABA_GPU_2020_CAPABILITIES, gpu_instance_row(start_time_us=5))


def test_gpu_instance_with_event_time_and_null_start_passes():  # S-19
    validate(ALIBABA_GPU_2020_CAPABILITIES, gpu_instance_row(event_time_us=0, start_time_us=None))


@pytest.mark.parametrize("caps", [ALIBABA_CAPABILITIES, AZURE_VM_CAPABILITIES])
def test_other_instance_rows_keep_0_1_0_time_rule(caps):  # S-20
    validate(caps, base_row(caps, record_level="instance", instance_id="i1", start_time_us=5))


# --- S-23 profile declarations -----------------------------------------------

@pytest.mark.parametrize(
    "overrides",
    [
        {"supported_record_levels": ("occurrence", "job")},
        {"evaluation_record_level": "job"},
        {"observed_cpu_semantics": "average"},
        {"cpu_target_semantics": "next_peak"},
        {"time_semantics": "submit"},
        {"instance_event_time_semantics": "instance_start"},
        {"recurrence_key_origin": "derived"},
        {"recurrence_key_origin": None},
        {"evaluation_mode": "full"},
        {"cpu_unit": "cores"},
        {"memory_unit": "mb"},
    ],
)
def test_invalid_profile_declaration_rejected(overrides):
    with pytest.raises(CanonicalSchemaError, match="unsupported|unknown"):
        make_caps(**overrides)


def test_all_registry_profiles_construct():
    assert set(DEFAULT_CAPABILITY_REGISTRY) == {
        "google_clusterdata2019",
        "alibaba_clustertrace2018",
        "azure_public_vm_v2",
        "alibaba_gpu_v2020",
    }
    for caps in DEFAULT_CAPABILITY_REGISTRY.values():
        DatasetCapabilities(**caps.__dict__)


# --- S-21 / S-22 Alibaba GPU 2020 example rows -------------------------------
# Rows 4-7 of examples/canonical_records.jsonl (indices 3-6): grouped role,
# fallback role, missing-CPU role, and an instance row whose parent is row 4.

GPU_EXAMPLE_INDICES = [3, 4, 5, 6]


def gpu_examples():
    return [load_examples()[i] for i in GPU_EXAMPLE_INDICES]


def test_gpu_examples_present():
    examples = gpu_examples()
    assert [e["dataset_id"] for e in examples] == ["alibaba_gpu_v2020"] * 4
    assert [e["record_level"] for e in examples] == [
        "role_occurrence", "role_occurrence", "role_occurrence", "instance",
    ]


@pytest.mark.parametrize("idx", GPU_EXAMPLE_INDICES)
def test_gpu_example_validates(idx):  # S-21
    # Examples are adapter output, so they must pass both the frame checks
    # and the adapter-output checks.
    from src.adapters.validation import validate_adapter_output

    frame = records_to_frame([load_examples()[idx]])
    validate_canonical_frame(frame, ALIBABA_GPU_2020_CAPABILITIES)
    validate_adapter_output(frame, capabilities=ALIBABA_GPU_2020_CAPABILITIES)


def test_gpu_examples_validate_together():  # S-21
    from src.adapters.validation import validate_adapter_output

    validate_adapter_output(
        records_to_frame(gpu_examples()),
        capabilities=ALIBABA_GPU_2020_CAPABILITIES,
    )


def test_gpu_example_rows_follow_the_contract():  # S-21
    grouped, fallback, _, instance = gpu_examples()
    # CPU is an average only; the trace has no CPU peak.
    assert grouped["observed_cpu"] is not None and grouped["peak_cpu"] is None
    assert grouped["resource_scope"] == "task_role_per_instance"
    assert grouped["request_aggregation_method"] == "none"
    # The only allowed null recurrence_key on a role row.
    assert fallback["recurrence_key"] is None
    assert fallback["exclusion_reason"] == "no_recurrence_key"
    # The instance row copies its parent's identity and carries the parent's
    # submission time as event_time_us.
    for col in ("workload_id", "recurrence_key", "occurrence_id", "role_key"):
        assert instance[col] == grouped[col]
    assert instance["event_time_us"] == grouped["start_time_us"]
    assert "source_seq_no" not in instance
    # Examples are adapter output: no splits or targets.
    for row in gpu_examples():
        assert not {"split", "actual_cpu", "actual_memory",
                    "cpu_target_status", "memory_target_status"} & set(row)


def test_gpu_missing_cpu_example_keeps_cpu_null():  # S-22
    row = gpu_examples()[2]
    assert row["observed_cpu"] is None
    assert row["observed_cpu_unit"] is None
    assert row["cpu_validity_status"] == "partial"
    assert row["memory_validity_status"] == "valid"
    assert row["validity_status"] == "partial"
    assert row["observed_memory"] is not None and row["peak_memory"] is not None
    assert row["exclusion_reason"] is None
    frame = records_to_frame([row])
    validate_canonical_frame(frame, ALIBABA_GPU_2020_CAPABILITIES)
    assert frame["observed_cpu"].isna().all()

@pytest.mark.parametrize(
    "actual_unit,recommended_unit",
    [
        (None, "ncu"),
        ("ncu", None),
        (None, None),
    ],
)
def test_evaluator_rejects_missing_unit_values(
    actual_unit,
    recommended_unit,
):
    # CPU is evaluated; memory is unavailable for this synthetic row.
    frame = pd.DataFrame(
        {
            "dataset_id": ["google_clusterdata2019"],
            "workload_id": ["w1"],
            "policy_name": ["P95"],
            "actual_cpu": [2.0],
            "recommended_cpu": [4.0],
            "actual_cpu_unit": [actual_unit],
            "recommended_cpu_unit": [recommended_unit],
            "actual_memory": [None],
            "recommended_memory": [None],
        }
    )

    with pytest.raises(
        CanonicalSchemaError,
        match="units must be populated",
    ):
        validate_evaluator_view(frame)