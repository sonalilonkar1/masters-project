from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping
import pandas as pd

SCHEMA_VERSION = "0.1.0"
RECORD_LEVELS = {"workload","occurrence","execution","instance","interval"}
TIME_BASES = {"unix_epoch","trace_relative","unknown"}
VALIDITY_STATUSES = {"valid","partial","invalid","unknown","unsupported"}
CORE_REQUIRED_COLUMNS = {"schema_version","dataset_id","record_level","workload_id","time_basis","validity_status"}
RESOURCE_VALUE_FIELDS = [
    "requested_cpu","requested_memory","allocated_cpu","allocated_memory",
    "observed_cpu","observed_memory","peak_cpu","peak_memory",
    "actual_cpu","actual_memory","recommended_cpu","recommended_memory",
]
RESOURCE_UNIT_FIELDS = {f: f"{f}_unit" for f in RESOURCE_VALUE_FIELDS}

@dataclass(frozen=True)
class DatasetCapabilities:
    dataset_id: str
    supports_cpu: bool
    supports_memory: bool
    supports_request: bool
    supports_recurrence: bool
    supports_targets: bool
    supports_ml: bool
    supports_observed_cpu: bool
    supports_observed_memory: bool
    supports_allocated_cpu: bool
    supports_allocated_memory: bool
    notes: str = ""
    def to_dict(self) -> dict:
        return asdict(self)

GOOGLE_CAPABILITIES = DatasetCapabilities(
    "google_clusterdata2019", True, True, True, True, True, True,
    True, True, False, False,
    "Reference corrected Google occurrence pipeline."
)
ALIBABA_CAPABILITIES = DatasetCapabilities(
    "alibaba_clustertrace2018", True, True, True, False, False, False,
    True, True, False, False,
    "Recurrence/targets remain disabled until a derived rule is validated."
)
AZURE_VM_CAPABILITIES = DatasetCapabilities(
    "azure_public_vm_v2", True, True, False, False, False, False,
    True, False, True, True,
    "CPU telemetry and VM capacity supported; observed memory unavailable."
)
DEFAULT_CAPABILITY_REGISTRY = {x.dataset_id: x for x in (
    GOOGLE_CAPABILITIES, ALIBABA_CAPABILITIES, AZURE_VM_CAPABILITIES
)}

class CanonicalSchemaError(ValueError):
    pass

def records_to_frame(records: Iterable[Mapping]) -> pd.DataFrame:
    return pd.DataFrame(list(records))

def _nonnull(df, col):
    return df[col].notna() if col in df.columns else pd.Series(False, index=df.index)

def _reject_populated(df, cols, reason):
    bad = [c for c in cols if c in df.columns and df[c].notna().any()]
    if bad:
        raise CanonicalSchemaError(f"Unsupported fields populated ({reason}): {bad}")

def validate_canonical_frame(df: pd.DataFrame, capabilities: DatasetCapabilities) -> None:
    missing = sorted(CORE_REQUIRED_COLUMNS - set(df.columns))
    if missing:
        raise CanonicalSchemaError(f"Missing required columns: {missing}")
    if df.empty:
        return
    if (df["schema_version"] != SCHEMA_VERSION).any():
        raise CanonicalSchemaError(f"Expected schema_version={SCHEMA_VERSION}")
    if (df["dataset_id"] != capabilities.dataset_id).any():
        raise CanonicalSchemaError("dataset_id does not match capability specification")
    if (~df["record_level"].isin(RECORD_LEVELS)).any():
        raise CanonicalSchemaError("Unsupported record_level")
    if (~df["time_basis"].isin(TIME_BASES)).any():
        raise CanonicalSchemaError("Unsupported time_basis")
    if (~df["validity_status"].isin(VALIDITY_STATUSES)).any():
        raise CanonicalSchemaError("Unsupported validity_status")
    if df["workload_id"].isna().any():
        raise CanonicalSchemaError("workload_id must not be null")
    if (~(_nonnull(df,"event_time_us") | _nonnull(df,"start_time_us"))).any():
        raise CanonicalSchemaError("Each row needs event_time_us or start_time_us")
    if "start_time_us" in df.columns and "end_time_us" in df.columns:
        mask = df["start_time_us"].notna() & df["end_time_us"].notna()
        if (mask & (pd.to_numeric(df["end_time_us"], errors="coerce") < pd.to_numeric(df["start_time_us"], errors="coerce"))).any():
            raise CanonicalSchemaError("end_time_us must be >= start_time_us")
    for value_col, unit_col in RESOURCE_UNIT_FIELDS.items():
        if value_col not in df.columns:
            continue
        supplied = df[value_col].notna()
        vals = pd.to_numeric(df[value_col], errors="coerce")
        if (supplied & vals.isna()).any():
            raise CanonicalSchemaError(f"{value_col} contains non-numeric values")
        if (supplied & (vals < 0)).any():
            raise CanonicalSchemaError(f"{value_col} must be non-negative")
        if supplied.any() and (unit_col not in df.columns or (supplied & df[unit_col].isna()).any()):
            raise CanonicalSchemaError(f"{unit_col} required whenever {value_col} is populated")
    if not capabilities.supports_recurrence:
        _reject_populated(df, ["recurrence_key"], "recurrence unsupported")
    if not capabilities.supports_request:
        _reject_populated(df, ["requested_cpu","requested_memory"], "request unsupported")
    if not capabilities.supports_observed_cpu:
        _reject_populated(df, ["observed_cpu","peak_cpu"], "observed CPU unsupported")
    if not capabilities.supports_observed_memory:
        _reject_populated(df, ["observed_memory","peak_memory"], "observed memory unsupported")
    if not capabilities.supports_allocated_cpu:
        _reject_populated(df, ["allocated_cpu"], "allocated CPU unsupported")
    if not capabilities.supports_allocated_memory:
        _reject_populated(df, ["allocated_memory"], "allocated memory unsupported")

def validate_evaluator_view(df: pd.DataFrame) -> None:
    required = {
        "dataset_id","workload_id","policy_name",
        "actual_cpu","actual_memory","recommended_cpu","recommended_memory",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise CanonicalSchemaError(f"Missing evaluator columns: {missing}")
    cpu_pair = df["actual_cpu"].notna() & df["recommended_cpu"].notna()
    mem_pair = df["actual_memory"].notna() & df["recommended_memory"].notna()
    if (~(cpu_pair | mem_pair)).any():
        raise CanonicalSchemaError("Each evaluator row needs at least one actual/recommendation pair")
    for resource, pair in (("cpu",cpu_pair),("memory",mem_pair)):
        if not pair.any():
            continue
        au, ru = f"actual_{resource}_unit", f"recommended_{resource}_unit"
        if au not in df.columns or ru not in df.columns:
            raise CanonicalSchemaError(f"Unit columns required for {resource}")
        if (pair & (df[au].astype("string") != df[ru].astype("string"))).any():
            raise CanonicalSchemaError(f"{resource} actual/recommendation units must match")
