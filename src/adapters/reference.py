"""Reference adapter for the Issue-3 contract; not a production dataset adapter."""
from __future__ import annotations
import pandas as pd
from src.canonical.schema import GOOGLE_CAPABILITIES, SCHEMA_VERSION, DatasetCapabilities
from .base import BaseDatasetAdapter

class ReferenceOccurrenceAdapter(BaseDatasetAdapter):
    adapter_name = "reference_occurrence"
    adapter_version = "0.1.0"

    @property
    def capabilities(self) -> DatasetCapabilities:
        return GOOGLE_CAPABILITIES

    def to_canonical(self, source: pd.DataFrame) -> pd.DataFrame:
        required = {
            "source_workload","source_occurrence","source_start_us",
            "source_end_us","source_request_cpu","source_peak_cpu",
        }
        missing = sorted(required - set(source.columns))
        if missing:
            raise ValueError(f"Reference source is missing required columns: {missing}")

        out = pd.DataFrame(index=source.index)
        out["schema_version"] = SCHEMA_VERSION
        out["dataset_id"] = self.capabilities.dataset_id
        out["record_level"] = "occurrence"
        out["workload_id"] = source["source_workload"]
        out["occurrence_id"] = source["source_occurrence"]
        out["recurrence_key"] = source["source_workload"]
        out["time_basis"] = "trace_relative"
        out["start_time_us"] = source["source_start_us"]
        out["end_time_us"] = source["source_end_us"]
        out["requested_cpu"] = source["source_request_cpu"]
        out["requested_cpu_unit"] = "ncu"
        out["peak_cpu"] = source["source_peak_cpu"]
        out["peak_cpu_unit"] = "ncu"
        out["requested_memory"] = None
        out["requested_memory_unit"] = None
        out["peak_memory"] = None
        out["peak_memory_unit"] = None
        out["validity_status"] = "valid"
        return out
