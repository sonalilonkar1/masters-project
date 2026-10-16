"""Alibaba Cluster Trace 2018 adapter.

The adapter preserves source semantics:
- job_name is a source workload/job ID, not a recurrence key.
- task_name identifies a task within a job.
- instance_name identifies a task instance.
- plan_cpu / plan_mem are planned/requested resource fields.
- cpu_avg / cpu_max and mem_avg / mem_max are observed instance outcomes.
- missing observations remain null.
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.canonical.schema import (
    ALIBABA_CAPABILITIES,
    SCHEMA_VERSION,
    DatasetCapabilities,
)
from .base import AdapterResult, BaseDatasetAdapter


ALIBABA_TASK_COLUMNS = [
    "task_name",
    "instance_num",
    "job_name",
    "task_type",
    "status",
    "start_time",
    "end_time",
    "plan_cpu",
    "plan_mem",
]

ALIBABA_INSTANCE_COLUMNS = [
    "instance_name",
    "task_name",
    "job_name",
    "task_type",
    "status",
    "start_time",
    "end_time",
    "machine_id",
    "seq_no",
    "total_seq_no",
    "cpu_avg",
    "cpu_max",
    "mem_avg",
    "mem_max",
]


class Alibaba2018Adapter(BaseDatasetAdapter):
    adapter_name = "alibaba_clustertrace2018"
    adapter_version = "0.1.0"

    @property
    def capabilities(self) -> DatasetCapabilities:
        return ALIBABA_CAPABILITIES

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

    def prepare_source(
        self,
        task_df: pd.DataFrame,
        instance_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Join task plan metadata onto batch-instance observations.

        The join preserves every instance row. Missing task metadata remains
        null rather than being fabricated.
        """

        self._require_columns(
            task_df,
            {
                "job_name",
                "task_name",
                "instance_num",
                "plan_cpu",
                "plan_mem",
            },
            table_name="Alibaba batch_task",
        )

        self._require_columns(
            instance_df,
            set(ALIBABA_INSTANCE_COLUMNS),
            table_name="Alibaba batch_instance",
        )

        task_plan = task_df[
            [
                "job_name",
                "task_name",
                "instance_num",
                "plan_cpu",
                "plan_mem",
            ]
        ].copy()

        if task_plan.duplicated(["job_name", "task_name"]).any():
            raise ValueError(
                "Alibaba batch_task contains duplicate "
                "(job_name, task_name) plan rows"
            )

        prepared = instance_df.copy(deep=True).merge(
            task_plan,
            how="left",
            on=["job_name", "task_name"],
            validate="many_to_one",
            indicator="_task_join",
        )

        prepared["task_metadata_matched"] = (
            prepared["_task_join"] == "both"
        )
        prepared = prepared.drop(columns=["_task_join"])

        return prepared

    def to_canonical(self, source: pd.DataFrame) -> pd.DataFrame:
        required = set(ALIBABA_INSTANCE_COLUMNS) | {
            "instance_num",
            "plan_cpu",
            "plan_mem",
            "task_metadata_matched",
        }
        self._require_columns(
            source,
            required,
            table_name="Prepared Alibaba source",
        )

        out = pd.DataFrame(index=source.index)

        out["schema_version"] = SCHEMA_VERSION
        out["dataset_id"] = self.capabilities.dataset_id
        out["record_level"] = "instance"

        out["workload_id"] = source["job_name"].astype("string")
        out["execution_id"] = (
            source["job_name"].astype("string")
            + "|"
            + source["task_name"].astype("string")
        )
        out["instance_id"] = source["instance_name"].astype("string")

        # Recurrence is intentionally not populated. Alibaba exposes job/task/
        # instance identity, but Issue 1 did not validate a recurrence rule.
        out["time_basis"] = "trace_relative"

        start_sec = self._strict_numeric(
            source["start_time"],
            field_name="start_time",
        )

        end_sec = self._strict_numeric(
            source["end_time"],
            field_name="end_time",
        )

        out["start_time_us"] = start_sec * 1_000_000

        # Running/incomplete rows may use 0 or otherwise non-final end values.
        valid_end = (
            end_sec.notna()
            & start_sec.notna()
            & (end_sec >= start_sec)
            & ~((end_sec == 0) & (start_sec > 0))
        )
        out["end_time_us"] = np.where(
            valid_end,
            end_sec * 1_000_000,
            np.nan,
        )

        duration = end_sec - start_sec
        out["duration_sec"] = np.where(
            valid_end,
            duration,
            np.nan,
        )

        out["requested_cpu"] = self._strict_numeric(
            source["plan_cpu"],
            field_name="plan_cpu",
        )

        out["requested_cpu_unit"] = np.where(
            out["requested_cpu"].notna(),
            "alibaba_plan_cpu_100_per_core",
            None,
        )

        out["requested_memory"] = self._strict_numeric(
            source["plan_mem"],
            field_name="plan_mem",
        )

        out["requested_memory_unit"] = np.where(
            out["requested_memory"].notna(),
            "alibaba_memory_source_normalized",
            None,
        )

        out["observed_cpu"] = self._strict_numeric(
            source["cpu_avg"],
            field_name="cpu_avg",
        )

        out["observed_cpu_unit"] = np.where(
            out["observed_cpu"].notna(),
            "alibaba_cpu_usage_source_unit",
            None,
        )

        out["peak_cpu"] = self._strict_numeric(
            source["cpu_max"],
            field_name="cpu_max",
        )

        out["peak_cpu_unit"] = np.where(
            out["peak_cpu"].notna(),
            "alibaba_cpu_usage_source_unit",
            None,
        )

        out["observed_memory"] = self._strict_numeric(
            source["mem_avg"],
            field_name="mem_avg",
        )

        out["observed_memory_unit"] = np.where(
            out["observed_memory"].notna(),
            "alibaba_memory_source_normalized",
            None,
        )

        out["peak_memory"] = self._strict_numeric(
            source["mem_max"],
            field_name="mem_max",
        )

        out["peak_memory_unit"] = np.where(
            out["peak_memory"].notna(),
            "alibaba_memory_source_normalized",
            None,
        )

        complete_timing = (
            out["start_time_us"].notna()
            & out["end_time_us"].notna()
        )

        matched_plan = (
            source["task_metadata_matched"]
            .fillna(False)
        )

        cpu_complete = (
            out["observed_cpu"].notna()
            & out["peak_cpu"].notna()
        )

        memory_complete = (
            out["observed_memory"].notna()
            & out["peak_memory"].notna()
        )

        cpu_avg_gt_max = (
            cpu_complete
            & (
                out["observed_cpu"]
                > out["peak_cpu"]
            )
        )

        memory_avg_gt_max = (
            memory_complete
            & (
                out["observed_memory"]
                > out["peak_memory"]
            )
        )

        out["cpu_validity_status"] = np.select(
            [
                cpu_avg_gt_max,
                cpu_complete,
            ],
            [
                "invalid",
                "valid",
            ],
            default="partial",
        )

        out["memory_validity_status"] = np.select(
            [
                memory_avg_gt_max,
                memory_complete,
            ],
            [
                "invalid",
                "valid",
            ],
            default="partial",
        )

        out["source_cpu_avg_gt_max"] = (
            cpu_avg_gt_max
        )

        out["source_memory_avg_gt_max"] = (
            memory_avg_gt_max
        )

        any_invalid = (
            cpu_avg_gt_max
            | memory_avg_gt_max
        )

        fully_valid = (
            complete_timing
            & matched_plan
            & (out["cpu_validity_status"] == "valid")
            & (out["memory_validity_status"] == "valid")
        )

        out["validity_status"] = np.select(
            [
                any_invalid,
                fully_valid,
            ],
            [
                "invalid",
                "valid",
            ],
            default="partial",
        )

        # Dataset-specific extensions are preserved for traceability. Shared
        # downstream code must not depend on them.
        out["source_job_name"] = source["job_name"]
        out["source_task_name"] = source["task_name"]
        out["source_status"] = source["status"]
        out["source_task_type"] = source["task_type"]
        out["source_machine_id"] = source["machine_id"]
        out["source_seq_no"] = source["seq_no"]
        out["source_total_seq_no"] = source["total_seq_no"]
        out["source_instance_num"] = source["instance_num"]
        out["source_task_metadata_matched"] = (
            source["task_metadata_matched"].astype(bool)
        )

        return out

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
                "record_level": "instance",
                "recurrence_supported": False,
                "task_metadata_match_count": int(
                    source["task_metadata_matched"].fillna(False).sum()
                ),
                "task_metadata_missing_count": int(
                    (~source["task_metadata_matched"].fillna(False)).sum()
                ),
                "observed_cpu_missing_count": int(
                    canonical["observed_cpu"].isna().sum()
                ),
                "observed_memory_missing_count": int(
                    canonical["observed_memory"].isna().sum()
                ),
                "peak_memory_missing_count": int(
                    canonical["peak_memory"].isna().sum()
                ),
                "cpu_valid_count": int(
                    (canonical["cpu_validity_status"] == "valid").sum()
                ),
                "cpu_partial_count": int(
                    (canonical["cpu_validity_status"] == "partial").sum()
                ),
                "cpu_invalid_count": int(
                    (canonical["cpu_validity_status"] == "invalid").sum()
                ),
                "memory_valid_count": int(
                    (canonical["memory_validity_status"] == "valid").sum()
                ),
                "memory_partial_count": int(
                    (canonical["memory_validity_status"] == "partial").sum()
                ),
                "memory_invalid_count": int(
                    (canonical["memory_validity_status"] == "invalid").sum()
                ),
                "cpu_avg_gt_max_count": int(
                    canonical["source_cpu_avg_gt_max"].sum()
                ),
                "memory_avg_gt_max_count": int(
                    canonical["source_memory_avg_gt_max"].sum()
                ),
            }
        )
        return base

    def adapt_tables(
        self,
        task_df: pd.DataFrame,
        instance_df: pd.DataFrame,
    ) -> AdapterResult:
        return self.adapt(
            self.prepare_source(
                task_df,
                instance_df,
            )
        )
