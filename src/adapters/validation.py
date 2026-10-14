"""Validation helpers shared by all TraceAdvisor adapters."""
from __future__ import annotations
import math
import pandas as pd
from src.canonical.schema import CanonicalSchemaError, DatasetCapabilities, validate_canonical_frame

class AdapterValidationError(ValueError):
    pass

def validate_adapter_output(df: pd.DataFrame, *, capabilities: DatasetCapabilities) -> None:
    if not isinstance(df, pd.DataFrame):
        raise AdapterValidationError("adapter output must be a pandas DataFrame")

    duplicate_columns = df.columns[df.columns.duplicated()].tolist()
    if duplicate_columns:
        raise AdapterValidationError(f"Duplicate canonical columns: {duplicate_columns}")

    if not df.empty and "dataset_id" in df.columns:
        ids = set(df["dataset_id"].dropna().astype(str).unique())
        if ids != {capabilities.dataset_id}:
            raise AdapterValidationError(
                f"Adapter output dataset_id must equal {capabilities.dataset_id!r}; found {sorted(ids)!r}"
            )

    resource_prefixes = ("requested_","allocated_","observed_","peak_","actual_","recommended_")
    for col in df.columns:
        if not col.startswith(resource_prefixes) or col.endswith("_unit"):
            continue
        values = pd.to_numeric(df[col], errors="coerce")
        supplied = df[col].notna()
        nonfinite = supplied & ~values.map(lambda x: True if pd.isna(x) else math.isfinite(float(x)))
        if nonfinite.any():
            raise AdapterValidationError(f"{col} contains non-finite values")

    try:
        validate_canonical_frame(df, capabilities)
    except CanonicalSchemaError as exc:
        raise AdapterValidationError(str(exc)) from exc
