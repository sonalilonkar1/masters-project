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

    @staticmethod
    def _strict_numeric(
        series: pd.Series,
        *,
        field_name: str,
    ) -> pd.Series:
        parsed = pd.to_numeric(
            series,
            errors="coerce",
        )

        invalid = series.notna() & parsed.isna()

        if invalid.any():
            examples = (
                series.loc[invalid]
                .astype(str)
                .head(5)
                .tolist()
            )

            raise ValueError(
                f"{field_name} contains non-numeric values: {examples}"
            )

        return parsed
    
    @staticmethod
    def _parse_capacity_bucket(
        series: pd.Series,
        *,
        field_name: str,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """
        Parse Azure capacity buckets without inventing exact values.

        Exact numeric buckets such as "4" or "14" become numeric values.

        Open-ended buckets such as ">24" are preserved as open-ended:
        - canonical numeric value remains NaN
        - open-ended flag is True
        - lower bound is recorded separately

        Unexpected labels still raise.
        """
        text = series.astype("string").str.strip()

        missing = series.isna() | text.eq("")

        open_ended = text.str.fullmatch(
            r">\s*\d+(?:\.\d+)?",
            na=False,
        )

        exact_text = text.mask(open_ended)

        parsed = pd.to_numeric(
            exact_text,
            errors="coerce",
        )

        invalid = (
            ~missing
            & ~open_ended
            & parsed.isna()
        )

        if invalid.any():
            examples = (
                text.loc[invalid]
                .head(5)
                .tolist()
            )

            raise ValueError(
                f"{field_name} contains unsupported bucket values: "
                f"{examples}"
            )

        lower_bound = pd.to_numeric(
            text.str.replace(
                ">",
                "",
                regex=False,
            ),
            errors="coerce",
        ).where(open_ended)

        return (
            parsed,
            open_ended,
            lower_bound,
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

        input_cpu_row_count = int(len(cpu_readings))

        prepared = cpu_readings.copy(deep=True).merge(
            vm_lookup,
            how="left",
            on="vm_id",
            validate="many_to_one",
            indicator="_vm_join",
        )

        matched_mask = prepared["_vm_join"] == "both"

        matched_cpu_row_count = int(
            matched_mask.sum()
        )

        unmatched_cpu_row_count = int(
            (~matched_mask).sum()
        )

        if matched_cpu_row_count == 0:
            raise ValueError(
                "Azure CPU readings and VM table have zero overlapping vm_id "
                "values. Use matching source partitions or a targeted VM sample."
            )

        if unmatched_cpu_row_count > 0:
            raise ValueError(
                "Azure CPU readings contain VM IDs missing from VM metadata: "
                f"{unmatched_cpu_row_count} unmatched of "
                f"{input_cpu_row_count} rows"
            )

        prepared = prepared.drop(
            columns=["_vm_join"]
        )

        prepared.attrs["input_cpu_row_count"] = (
            input_cpu_row_count
        )
        prepared.attrs["matched_cpu_row_count"] = (
            matched_cpu_row_count
        )
        prepared.attrs["unmatched_cpu_row_count"] = (
            unmatched_cpu_row_count
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
        timestamp = self._strict_numeric(
            source["timestamp"],
            field_name="timestamp",
        )

        out["event_time_us"] = (
            timestamp * 1_000_000
        )
        out["aggregation_window_sec"] = 300

        (
            allocated_cpu,
            cpu_bucket_open_ended,
            cpu_bucket_lower_bound,
        ) = self._parse_capacity_bucket(
            source["vm_core_count_bucket"],
            field_name="vm_core_count_bucket",
        )

        out["allocated_cpu"] = allocated_cpu

        out["source_vm_core_count_bucket"] = (
            source["vm_core_count_bucket"]
        )

        out["source_allocated_cpu_bucket_open_ended"] = (
            cpu_bucket_open_ended
        )

        out["source_allocated_cpu_bucket_lower_bound"] = (
            cpu_bucket_lower_bound
        )
        out["allocated_cpu_unit"] = np.where(
            out["allocated_cpu"].notna(),
            "vcpu",
            None,
        )

        (
            allocated_memory,
            memory_bucket_open_ended,
            memory_bucket_lower_bound,
        ) = self._parse_capacity_bucket(
            source["vm_memory_bucket"],
            field_name="vm_memory_bucket",
        )

        out["allocated_memory"] = allocated_memory

        out["source_vm_memory_bucket"] = (
            source["vm_memory_bucket"]
        )

        out["source_allocated_memory_bucket_open_ended"] = (
            memory_bucket_open_ended
        )

        out["source_allocated_memory_bucket_lower_bound"] = (
            memory_bucket_lower_bound
        )
        out["allocated_memory_unit"] = np.where(
            out["allocated_memory"].notna(),
            "gb",
            None,
        )

        out["observed_cpu"] = self._strict_numeric(
            source["avg_cpu"],
            field_name="avg_cpu",
        )
        out["observed_cpu_unit"] = np.where(
            out["observed_cpu"].notna(),
            "percent",
            None,
        )

        out["peak_cpu"] = self._strict_numeric(
            source["max_cpu"],
            field_name="max_cpu",
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
        out["source_min_cpu"] = self._strict_numeric(
            source["min_cpu"],
            field_name="min_cpu",
        )

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
        vm_created = self._strict_numeric(
            vm_table["vm_created"],
            field_name="vm_created",
        )

        vm_deleted = self._strict_numeric(
            vm_table["vm_deleted"],
            field_name="vm_deleted",
        )

        out["start_time_us"] = (
            vm_created * 1_000_000
        )

        out["end_time_us"] = (
            vm_deleted * 1_000_000
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

        (
            allocated_cpu,
            cpu_bucket_open_ended,
            cpu_bucket_lower_bound,
        ) = self._parse_capacity_bucket(
            vm_table["vm_core_count_bucket"],
            field_name="vm_core_count_bucket",
        )

        out["allocated_cpu"] = allocated_cpu

        out["source_vm_core_count_bucket"] = (
            vm_table["vm_core_count_bucket"]
        )

        out["source_allocated_cpu_bucket_open_ended"] = (
            cpu_bucket_open_ended
        )

        out["source_allocated_cpu_bucket_lower_bound"] = (
            cpu_bucket_lower_bound
        )
        out["allocated_cpu_unit"] = np.where(
            out["allocated_cpu"].notna(),
            "vcpu",
            None,
        )

        (
            allocated_memory,
            memory_bucket_open_ended,
            memory_bucket_lower_bound,
        ) = self._parse_capacity_bucket(
            vm_table["vm_memory_bucket"],
            field_name="vm_memory_bucket",
        )

        out["allocated_memory"] = allocated_memory

        out["source_vm_memory_bucket"] = (
            vm_table["vm_memory_bucket"]
        )

        out["source_allocated_memory_bucket_open_ended"] = (
            memory_bucket_open_ended
        )

        out["source_allocated_memory_bucket_lower_bound"] = (
            memory_bucket_lower_bound
        )
        out["allocated_memory_unit"] = np.where(
            out["allocated_memory"].notna(),
            "gb",
            None,
        )

        out["observed_cpu"] = self._strict_numeric(
            vm_table["avg_cpu"],
            field_name="avg_cpu",
        )
        out["observed_cpu_unit"] = np.where(
            out["observed_cpu"].notna(),
            "percent",
            None,
        )

        out["peak_cpu"] = self._strict_numeric(
            vm_table["max_cpu"],
            field_name="max_cpu",
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
        out["source_p95_max_cpu"] = self._strict_numeric(
            vm_table["p95_max_cpu"],
            field_name="p95_max_cpu",
        )
        out["source_equal_create_delete"] = equal_lifetime

        validate_adapter_output(
            out,
            capabilities=self.capabilities,
        )

        metadata = {
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "dataset_id": self.capabilities.dataset_id,
            "capabilities": self.capabilities.to_dict(),
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
            "allocated_cpu_open_ended_bucket_count": int(
                out[
                    "source_allocated_cpu_bucket_open_ended"
                ].sum()
            ),
            "allocated_memory_open_ended_bucket_count": int(
                out[
                    "source_allocated_memory_bucket_open_ended"
                ].sum()
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
                "input_cpu_row_count": int(
                    source.attrs.get(
                        "input_cpu_row_count",
                        len(source),
                    )
                ),
                "matched_cpu_row_count": int(
                    source.attrs.get(
                        "matched_cpu_row_count",
                        len(source),
                    )
                ),
                "unmatched_cpu_row_count": int(
                    source.attrs.get(
                        "unmatched_cpu_row_count",
                        0,
                    )
                ),
                "allocated_cpu_open_ended_bucket_count": int(
                    canonical[
                        "source_allocated_cpu_bucket_open_ended"
                    ].sum()
                ),
                "allocated_memory_open_ended_bucket_count": int(
                    canonical[
                        "source_allocated_memory_bucket_open_ended"
                    ].sum()
                ),
            }
        )
        return base
