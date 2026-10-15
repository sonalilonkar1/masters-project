"""Azure 2019 Public Dataset V2 adapter.

Two canonical views are supported:

1. VM lifecycle/capacity view from the VM table.
2. Five-minute CPU interval view after joining CPU readings to VM metadata.

Observed memory is intentionally never populated because the selected public
trace does not provide observed memory telemetry.
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.canonical.schema import (
    AZURE_VM_CAPABILITIES,
    SCHEMA_VERSION,
    DatasetCapabilities,
)
from src.adapters.validation import validate_adapter_output
from .base import AdapterResult, BaseDatasetAdapter


AZURE_VM_COLUMNS = [
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
]

AZURE_CPU_COLUMNS = [
    "timestamp",
    "vm_id",
    "min_cpu",
    "max_cpu",
    "avg_cpu",
]


class AzureVMAdapter(BaseDatasetAdapter):
    adapter_name = "azure_public_vm_v2"
    adapter_version = "0.1.0"

    @property
    def capabilities(self) -> DatasetCapabilities:
        return AZURE_VM_CAPABILITIES

    @staticmethod
    def _require_columns(
        df: pd.DataFrame,
        required: set[str],
        *,
        table_name: str,
    ) -> None:
        missing = sorted(required - set(df.columns))
        if missing:
            raise ValueError(
                f"{table_name} is missing required columns: {missing}"
            )

    def prepare_cpu_intervals(
        self,
        vm_table: pd.DataFrame,
        cpu_readings: pd.DataFrame,
    ) -> pd.DataFrame:
        self._require_columns(
            vm_table,
            set(AZURE_VM_COLUMNS),
            table_name="Azure VM table",
        )
        self._require_columns(
            cpu_readings,
            set(AZURE_CPU_COLUMNS),
            table_name="Azure CPU readings",
        )

        if vm_table["vm_id"].duplicated().any():
            raise ValueError(
                "Azure VM table must contain unique vm_id values"
            )

        vm_lookup = vm_table[
            [
                "vm_id",
                "subscription_id",
                "deployment_id",
                "vm_category",
                "vm_core_count_bucket",
                "vm_memory_bucket",
            ]
        ].copy()

        prepared = cpu_readings.copy(deep=True).merge(
            vm_lookup,
            how="inner",
            on="vm_id",
            validate="many_to_one",
        )

        if prepared.empty:
            raise ValueError(
                "Azure CPU readings and VM table have zero overlapping vm_id "
                "values. Use matching source partitions or a targeted VM sample."
            )

        return prepared

    def to_canonical(
        self,
        source: pd.DataFrame,
    ) -> pd.DataFrame:
        """Map a prepared Azure five-minute CPU interval source."""

        required = set(AZURE_CPU_COLUMNS) | {
            "subscription_id",
            "deployment_id",
            "vm_category",
            "vm_core_count_bucket",
            "vm_memory_bucket",
        }
        self._require_columns(
            source,
            required,
            table_name="Prepared Azure CPU source",
        )

        out = pd.DataFrame(index=source.index)

        out["schema_version"] = SCHEMA_VERSION
        out["dataset_id"] = self.capabilities.dataset_id
        out["record_level"] = "interval"

        out["workload_id"] = source[
            "deployment_id"
        ].astype("string")
        out["execution_id"] = source[
            "vm_id"
        ].astype("string")
        out["instance_id"] = source[
            "vm_id"
        ].astype("string")

        # Recurrence remains unsupported.
        out["time_basis"] = "trace_relative"
        out["event_time_us"] = (
            pd.to_numeric(
                source["timestamp"],
                errors="coerce",
            )
            * 1_000_000
        )
        out["aggregation_window_sec"] = 300

        out["allocated_cpu"] = pd.to_numeric(
            source["vm_core_count_bucket"],
            errors="coerce",
        )
        out["allocated_cpu_unit"] = np.where(
            out["allocated_cpu"].notna(),
            "vcpu",
            None,
        )

        out["allocated_memory"] = pd.to_numeric(
            source["vm_memory_bucket"],
            errors="coerce",
        )
        out["allocated_memory_unit"] = np.where(
            out["allocated_memory"].notna(),
            "gb",
            None,
        )

        out["observed_cpu"] = pd.to_numeric(
            source["avg_cpu"],
            errors="coerce",
        )
        out["observed_cpu_unit"] = np.where(
            out["observed_cpu"].notna(),
            "percent",
            None,
        )

        out["peak_cpu"] = pd.to_numeric(
            source["max_cpu"],
            errors="coerce",
        )
        out["peak_cpu_unit"] = np.where(
            out["peak_cpu"].notna(),
            "percent",
            None,
        )

        # Selected Azure V2 trace has no observed-memory telemetry.
        out["observed_memory"] = np.nan
        out["observed_memory_unit"] = None
        out["peak_memory"] = np.nan
        out["peak_memory_unit"] = None

        complete = (
            out["event_time_us"].notna()
            & out["workload_id"].notna()
            & out["instance_id"].notna()
            & out["allocated_cpu"].notna()
            & out["allocated_memory"].notna()
            & out["observed_cpu"].notna()
            & out["peak_cpu"].notna()
        )
        
        out["validity_status"] = np.where(
            complete,
            "valid",
            "partial",
        )

        out["source_subscription_id"] = source[
            "subscription_id"
        ]
        out["source_deployment_id"] = source[
            "deployment_id"
        ]
        out["source_vm_id"] = source["vm_id"]
        out["source_vm_category"] = source[
            "vm_category"
        ]
        out["source_min_cpu"] = source["min_cpu"]

        return out

    def adapt_cpu_readings(
        self,
        vm_table: pd.DataFrame,
        cpu_readings: pd.DataFrame,
    ) -> AdapterResult:
        return self.adapt(
            self.prepare_cpu_intervals(
                vm_table,
                cpu_readings,
            )
        )

    def adapt_vm_table(
        self,
        vm_table: pd.DataFrame,
    ) -> AdapterResult:
        """Build a VM lifecycle/capacity canonical view.

        The VM-table CPU summaries are lifetime/post-observation outcomes.
        They are safe as descriptive outcomes, but must not be used as
        pre-execution features for that same VM.
        """
        
        self._require_columns(
            vm_table,
            set(AZURE_VM_COLUMNS),
            table_name="Azure VM table",
        )

        if vm_table.empty:
            raise ValueError(
                "Azure VM table is empty; cannot build canonical lifecycle artifact"
            )

        if vm_table["vm_id"].duplicated().any():
            raise ValueError(
                "Azure VM table must contain unique vm_id values"
            )

        out = pd.DataFrame(index=vm_table.index)

        out["schema_version"] = SCHEMA_VERSION
        out["dataset_id"] = self.capabilities.dataset_id
        out["record_level"] = "instance"

        out["workload_id"] = vm_table[
            "deployment_id"
        ].astype("string")
        out["execution_id"] = vm_table[
            "vm_id"
        ].astype("string")
        out["instance_id"] = vm_table[
            "vm_id"
        ].astype("string")

        out["time_basis"] = "trace_relative"
        out["start_time_us"] = (
            pd.to_numeric(
                vm_table["vm_created"],
                errors="coerce",
            )
            * 1_000_000
        )
        out["end_time_us"] = (
            pd.to_numeric(
                vm_table["vm_deleted"],
                errors="coerce",
            )
            * 1_000_000
        )

        # Azure documentation treats equal create/delete timestamps as at
        # least one five-minute lifetime interval. Keep source timestamps
        # unchanged and do not fabricate a later end time.
        equal_lifetime = (
            out["start_time_us"].notna()
            & out["end_time_us"].notna()
            & (
                out["start_time_us"]
                == out["end_time_us"]
            )
        )

        out["allocated_cpu"] = pd.to_numeric(
            vm_table["vm_core_count_bucket"],
            errors="coerce",
        )
        out["allocated_cpu_unit"] = np.where(
            out["allocated_cpu"].notna(),
            "vcpu",
            None,
        )

        out["allocated_memory"] = pd.to_numeric(
            vm_table["vm_memory_bucket"],
            errors="coerce",
        )
        out["allocated_memory_unit"] = np.where(
            out["allocated_memory"].notna(),
            "gb",
            None,
        )

        out["observed_cpu"] = pd.to_numeric(
            vm_table["avg_cpu"],
            errors="coerce",
        )
        out["observed_cpu_unit"] = np.where(
            out["observed_cpu"].notna(),
            "percent",
            None,
        )

        out["peak_cpu"] = pd.to_numeric(
            vm_table["max_cpu"],
            errors="coerce",
        )
        out["peak_cpu_unit"] = np.where(
            out["peak_cpu"].notna(),
            "percent",
            None,
        )

        out["observed_memory"] = np.nan
        out["observed_memory_unit"] = None
        out["peak_memory"] = np.nan
        out["peak_memory_unit"] = None

        complete = (
            out["workload_id"].notna()
            & out["instance_id"].notna()
            & out["start_time_us"].notna()
            & out["end_time_us"].notna()
            & out["allocated_cpu"].notna()
            & out["allocated_memory"].notna()
            & out["observed_cpu"].notna()
            & out["peak_cpu"].notna()
        )
        
        out["validity_status"] = np.where(
            complete,
            "valid",
            "partial",
        )

        out["source_subscription_id"] = vm_table[
            "subscription_id"
        ]
        out["source_deployment_id"] = vm_table[
            "deployment_id"
        ]
        out["source_vm_id"] = vm_table["vm_id"]
        out["source_vm_category"] = vm_table[
            "vm_category"
        ]
        out["source_p95_max_cpu"] = vm_table[
            "p95_max_cpu"
        ]
        out["source_equal_create_delete"] = equal_lifetime

        validate_adapter_output(
            out,
            capabilities=self.capabilities,
        )

        metadata = {
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "dataset_id": self.capabilities.dataset_id,
            "view": "vm_lifecycle",
            "source_row_count": int(len(vm_table)),
            "canonical_row_count": int(len(out)),
            "observed_memory_supported": False,
            "equal_create_delete_count": int(
                equal_lifetime.sum()
            ),
            "cpu_summary_semantics": (
                "lifetime/post-observation VM summary; not a "
                "pre-execution feature for the same VM"
            ),
            "allocated_cpu_missing_count": int(
                out["allocated_cpu"].isna().sum()
            ),
            "allocated_memory_missing_count": int(
                out["allocated_memory"].isna().sum()
            ),
        }

        return AdapterResult(
            canonical=out,
            metadata=metadata,
        )

    def build_metadata(
        self,
        *,
        source: pd.DataFrame,
        canonical: pd.DataFrame,
    ) -> Mapping[str, Any]:
        base = dict(
            super().build_metadata(
                source=source,
                canonical=canonical,
            )
        )
        base.update(
            {
                "view": "cpu_interval",
                "record_level": "interval",
                "aggregation_window_sec": 300,
                "recurrence_supported": False,
                "observed_memory_supported": False,
                "observed_cpu_missing_count": int(
                    canonical["observed_cpu"].isna().sum()
                ),
                "allocated_cpu_missing_count": int(
                    canonical["allocated_cpu"].isna().sum()
                ),
                "allocated_memory_missing_count": int(
                    canonical["allocated_memory"].isna().sum()
                ),
            }
        )
        return base
