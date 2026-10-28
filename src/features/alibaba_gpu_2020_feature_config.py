from __future__ import annotations

from typing import List

ALIBABA_GPU_2020_BASE_FEATURES: List[str] = [
    "requested_cpu",
    "requested_memory",
    "requested_gpu",
    "inst_num",
    "gpu_type",
    "gpu_type_spec",
    "workload",
    "cpu_history_count",
    "memory_history_count",
]

# Task 6 will supply these point-in-time history statistics.
ALIBABA_GPU_2020_HISTORY_FEATURES: List[str] = [
    "cpu_history_mean",
    "cpu_history_p90",
    "cpu_history_p95",
    "cpu_history_p99",
    "memory_history_mean",
    "memory_history_p90",
    "memory_history_p95",
    "memory_history_p99",
]

ALIBABA_GPU_2020_HISTORY_MISSING_INDICATORS: List[str] = [
    f"{column}_missing"
    for column in ALIBABA_GPU_2020_HISTORY_FEATURES
]

ALIBABA_GPU_2020_FEATURES: List[str] = (
    ALIBABA_GPU_2020_BASE_FEATURES
    + ALIBABA_GPU_2020_HISTORY_FEATURES
    + ALIBABA_GPU_2020_HISTORY_MISSING_INDICATORS
)

ALIBABA_GPU_2020_LEAKY_COLUMNS: List[str] = [
    # Targets and target status
    "actual_cpu",
    "actual_memory",
    "actual_cpu_unit",
    "actual_memory_unit",
    "cpu_target_status",
    "memory_target_status",

    # Current-run observations
    "observed_cpu",
    "observed_memory",
    "observed_gpu",
    "peak_memory",
    "peak_gpu_memory",
    "peak_cpu",
    "end_time_us",
    "launch_time_us",
    "source_job_status",
    "source_task_status",

    # Labels and flags
    "split",
    "exclusion_reason",
    "validity_status",
    "cpu_validity_status",
    "memory_validity_status",
    "next_occurrence_same_second",

    # Identifiers
    "role_key",
    "occurrence_id",
    "execution_id",
    "instance_id",
    "job_name",
    "task_name",
    "workload_id",
    "recurrence_key",
]