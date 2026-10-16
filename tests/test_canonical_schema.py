import json
from pathlib import Path

import pandas as pd
import pytest

from src.canonical.schema import (
    ALIBABA_CAPABILITIES,
    AZURE_VM_CAPABILITIES,
    DEFAULT_CAPABILITY_REGISTRY,
    GOOGLE_CAPABILITIES,
    SCHEMA_VERSION,
    CanonicalSchemaError,
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
