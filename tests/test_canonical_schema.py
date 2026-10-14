import json
from pathlib import Path
import pandas as pd
import pytest
from src.canonical.schema import (
    ALIBABA_CAPABILITIES, AZURE_VM_CAPABILITIES, GOOGLE_CAPABILITIES,
    CanonicalSchemaError, records_to_frame, validate_canonical_frame, validate_evaluator_view,
)
EXAMPLE_PATH = Path(__file__).resolve().parents[1] / "examples" / "canonical_records.jsonl"

def load_examples():
    return [json.loads(x) for x in EXAMPLE_PATH.read_text().splitlines() if x.strip()]

@pytest.mark.parametrize("idx,caps", [
    (0, GOOGLE_CAPABILITIES), (1, ALIBABA_CAPABILITIES), (2, AZURE_VM_CAPABILITIES)
])
def test_examples_validate(idx, caps):
    validate_canonical_frame(records_to_frame([load_examples()[idx]]), caps)

def test_azure_observed_memory_rejected():
    r = load_examples()[2]
    r["observed_memory"], r["observed_memory_unit"] = 2.0, "gb"
    with pytest.raises(CanonicalSchemaError):
        validate_canonical_frame(records_to_frame([r]), AZURE_VM_CAPABILITIES)

def test_alibaba_unvalidated_recurrence_rejected():
    r = load_examples()[1]
    r["recurrence_key"] = "guessed-family"
    with pytest.raises(CanonicalSchemaError):
        validate_canonical_frame(records_to_frame([r]), ALIBABA_CAPABILITIES)

def test_missing_optional_value_not_zero_filled():
    f = records_to_frame([load_examples()[2]])
    validate_canonical_frame(f, AZURE_VM_CAPABILITIES)
    assert pd.isna(f.loc[0, "observed_memory"])

def test_negative_resource_rejected():
    r = load_examples()[0]
    r["peak_cpu"] = -1
    with pytest.raises(CanonicalSchemaError):
        validate_canonical_frame(records_to_frame([r]), GOOGLE_CAPABILITIES)

def test_resource_requires_unit():
    r = load_examples()[0]
    r["peak_cpu_unit"] = None
    with pytest.raises(CanonicalSchemaError):
        validate_canonical_frame(records_to_frame([r]), GOOGLE_CAPABILITIES)

def test_evaluator_cpu_only_valid():
    f = pd.DataFrame([{
        "dataset_id":"azure_public_vm_v2","workload_id":"d1","policy_name":"P95",
        "actual_cpu":2.4,"actual_cpu_unit":"vcpu","recommended_cpu":2.8,"recommended_cpu_unit":"vcpu",
        "actual_memory":None,"actual_memory_unit":None,"recommended_memory":None,"recommended_memory_unit":None,
    }])
    validate_evaluator_view(f)

def test_evaluator_unit_mismatch_rejected():
    f = pd.DataFrame([{
        "dataset_id":"example","workload_id":"w1","policy_name":"P95",
        "actual_cpu":2.0,"actual_cpu_unit":"vcpu","recommended_cpu":70.0,"recommended_cpu_unit":"percent",
        "actual_memory":None,"recommended_memory":None,
    }])
    with pytest.raises(CanonicalSchemaError):
        validate_evaluator_view(f)
