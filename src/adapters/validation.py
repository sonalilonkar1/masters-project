"""Validation helpers shared by all TraceAdvisor adapters."""
from __future__ import annotations
import math
import pandas as pd
from src.canonical.schema import CanonicalSchemaError, DatasetCapabilities, validate_canonical_frame

class AdapterValidationError(ValueError):
    pass

def _validate_record_uniqueness(df: pd.DataFrame) -> None:
    if df.empty or "record_level" not in df.columns:
        return

    for record_level, group in df.groupby(
        "record_level",
        dropna=False,
    ):
        keys = None

        if record_level == "occurrence":
            keys = ["occurrence_id"]

        elif record_level == "interval":
            keys = ["instance_id", "event_time_us"]

        elif record_level == "instance":
            if "source_seq_no" in group.columns:
                keys = ["instance_id", "source_seq_no"]
            else:
                keys = ["instance_id"]

        elif record_level == "execution":
            if "start_time_us" in group.columns:
                keys = ["execution_id", "start_time_us"]
            else:
                keys = ["execution_id"]

        if not keys:
            continue

        if any(key not in group.columns for key in keys):
            continue

        eligible = group[keys].notna().all(axis=1)

        duplicated = group.loc[
            eligible
        ].duplicated(
            subset=keys,
            keep=False,
        )

        if duplicated.any():
            examples = (
                group.loc[eligible]
                .loc[duplicated, keys]
                .head(5)
                .to_dict("records")
            )

            raise AdapterValidationError(
                f"Duplicate canonical {record_level} records "
                f"for key {keys}: {examples}"
            )

def validate_adapter_output(df: pd.DataFrame, *, capabilities: DatasetCapabilities) -> None:
    if not isinstance(df, pd.DataFrame):
        raise AdapterValidationError("adapter output must be a pandas DataFrame")

    duplicate_columns = df.columns[df.columns.duplicated()].tolist()
    if duplicate_columns:
        raise AdapterValidationError(f"Duplicate canonical columns: {duplicate_columns}")

    _validate_record_uniqueness(df)
    
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
