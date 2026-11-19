"""The UI bundle format, fixed in one place (Task 15).

The export validates every table it writes against these specifications, and
the API and its tests read the same constants, so the two cannot drift apart.
Column lists follow the Task 15 issue (``recommendations.parquet`` and
``workloads.parquet``); target statuses reuse the canonical vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.canonical.schema import TARGET_STATUSES

BUNDLE_SCHEMA_VERSION = "1.0"

GOOGLE = "google_clusterdata2019"
ALIBABA = "alibaba_gpu_v2020"
DATASET_IDS = (GOOGLE, ALIBABA)


@dataclass(frozen=True)
class ResourceSpec:
    unit: str
    semantics: str
    description: str


@dataclass(frozen=True)
class DatasetSpec:
    dataset_id: str
    display_name: str
    cpu: ResourceSpec
    memory: ResourceSpec
    # Resource listed first in the UI; None when CPU and memory are equal.
    primary_resource: str | None


# Units and semantics equal cpu/memory_unit and cpu/memory_target_semantics in
# config/dataset_capabilities.json (checked by tests).
DATASETS = {
    GOOGLE: DatasetSpec(
        dataset_id=GOOGLE,
        display_name="Google ClusterData 2019",
        cpu=ResourceSpec("ncu", "next_occurrence_peak", "Peak CPU of the next run, in normalized compute units"),
        memory=ResourceSpec("normalized", "next_occurrence_peak", "Peak memory of the next run, normalized by the trace publisher"),
        primary_resource=None,
    ),
    ALIBABA: DatasetSpec(
        dataset_id=ALIBABA,
        display_name="Alibaba GPU 2020",
        cpu=ResourceSpec("percent_of_vcpu", "next_occurrence_lifetime_average", "Average CPU usage of the next run, not its peak"),
        memory=ResourceSpec("gb", "next_occurrence_lifetime_peak", "Peak memory of the next run, in GB"),
        primary_resource="memory",
    ),
}

# Policy names as written in both datasets' final-test summary CSVs, in
# display order, with the lowercase IDs used in API paths and parameters.
POLICY_NAMES = ("Request", "Mean", "P90", "P95", "P99", "ML", "Hybrid")
POLICY_IDS = {name: name.lower() for name in POLICY_NAMES}
POLICY_BY_ID = {policy_id: name for name, policy_id in POLICY_IDS.items()}

# Violation metrics each dataset's summary reports and the export checks against
# the exceeded flags. Only the Google final test reports the any-resource metric.
VIOLATION_METRICS = {GOOGLE: ("cpu", "memory", "any_resource"), ALIBABA: ("cpu", "memory")}
GOOGLE_ANY_RESOURCE_COLUMNS = ("any_resource_violation_pct", "valid_any_resource_violation_count")

# history          - the policy used the workload's earlier runs
# request_fallback - a history policy with too few earlier runs, so the request is kept
# request          - the Request policy itself
# model            - the ML policy
BASIS_VALUES = frozenset({"history", "request_fallback", "request", "model"})

BUNDLE_STATUSES = frozenset({"verified", "development"})

# API error codes; the body is {"error": {"code": ..., "message": ...}}.
ERROR_CODES = frozenset({"invalid_parameter", "not_found", "method_not_allowed", "internal_error"})


def error_body(code: str, message: str) -> dict:
    if code not in ERROR_CODES:
        raise ValueError(f"unknown error code: {code}")
    return {"error": {"code": code, "message": message}}


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    dtype: str  # "string", "int64", "float64" or "bool"
    nullable: bool
    allowed: frozenset | None = None


RECOMMENDATION_COLUMNS = (
    ColumnSpec("workload_id", "string", False),
    ColumnSpec("occurrence_id", "string", False),
    ColumnSpec("role_key", "string", True),  # Alibaba only
    ColumnSpec("start_time_us", "int64", False),
    ColumnSpec("target_start_time_us", "int64", True),
    ColumnSpec("target_occurrence_id", "string", True),
    ColumnSpec("policy", "string", False, frozenset(POLICY_NAMES)),
    ColumnSpec("recommended_cpu", "float64", True),
    ColumnSpec("recommended_memory", "float64", True),
    ColumnSpec("request_cpu", "float64", True),
    ColumnSpec("request_memory", "float64", True),
    ColumnSpec("actual_cpu", "float64", True),
    ColumnSpec("actual_memory", "float64", True),
    ColumnSpec("cpu_target_status", "string", False, frozenset(TARGET_STATUSES)),
    ColumnSpec("memory_target_status", "string", False, frozenset(TARGET_STATUSES)),
    ColumnSpec("cpu_exceeded", "bool", True),
    ColumnSpec("memory_exceeded", "bool", True),
    ColumnSpec("cpu_basis", "string", False, BASIS_VALUES),
    ColumnSpec("memory_basis", "string", False, BASIS_VALUES),
    ColumnSpec("cpu_history_run_count", "int64", True),  # null for Request and ML
    ColumnSpec("memory_history_run_count", "int64", True),
    ColumnSpec("is_latest", "bool", False),
)

WORKLOAD_COLUMNS = (
    ColumnSpec("workload_id", "string", False),
    ColumnSpec("display_name", "string", False),
    ColumnSpec("test_run_count", "int64", False),
    ColumnSpec("scored_run_count", "int64", False),
    ColumnSpec("first_start_time_us", "int64", False),
    ColumnSpec("last_start_time_us", "int64", False),
    ColumnSpec("latest_occurrence_id", "string", False),
    ColumnSpec("latest_uses_history", "bool", False),
    ColumnSpec("has_scored_history", "bool", False),
)


class BundleContractError(ValueError):
    """Raised when a table does not match the bundle format."""


_DTYPE_CHECKS = {
    "string": lambda s: pd.api.types.is_string_dtype(s) or pd.api.types.is_object_dtype(s),
    "int64": pd.api.types.is_integer_dtype,
    "float64": pd.api.types.is_float_dtype,
    "bool": pd.api.types.is_bool_dtype,
}


def validate_frame(df: pd.DataFrame, columns: tuple[ColumnSpec, ...], table: str) -> None:
    """Check columns, order, types, nulls and allowed values; raise on the first table-level problem."""
    expected = [spec.name for spec in columns]
    if list(df.columns) != expected:
        missing = [name for name in expected if name not in df.columns]
        extra = [name for name in df.columns if name not in expected]
        raise BundleContractError(f"{table}: columns differ (missing {missing}, extra {extra}, or wrong order)")

    problems = []
    for spec in columns:
        series = df[spec.name]
        if not _DTYPE_CHECKS[spec.dtype](series):
            problems.append(f"{spec.name}: expected {spec.dtype}, got {series.dtype}")
            continue
        present = series.dropna()
        if spec.dtype == "string" and not all(isinstance(value, str) for value in present):
            problems.append(f"{spec.name}: non-string values")
        if not spec.nullable and len(present) != len(series):
            problems.append(f"{spec.name}: {len(series) - len(present)} nulls in a non-nullable column")
        if spec.allowed is not None:
            unexpected = sorted(set(present) - spec.allowed)
            if unexpected:
                problems.append(f"{spec.name}: values not allowed {unexpected}")
    if problems:
        raise BundleContractError(f"{table}: " + "; ".join(problems))
