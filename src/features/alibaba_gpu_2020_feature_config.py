from __future__ import annotations
from typing import List

# Task 7 (#89) feature contract for the Alibaba GPU 2020 ML models.
#
# Separate from the Google feature_config (not reused). Features are the
# pre-execution fields allowed by the output contract §8.2, plus the Task 4
# history counts and the Task 6 point-in-time history statistics. CPU target is
# the next-occurrence lifetime-AVERAGE CPU usage; memory target is the
# next-occurrence PEAK memory (the primary resource).

# ---------------------------------------------------------------------------
# Targets and target-availability statuses (from the Task 4 tables)
# ---------------------------------------------------------------------------
TARGET_CPU: str = "actual_cpu"
TARGET_MEMORY: str = "actual_memory"
CPU_TARGET_STATUS: str = "cpu_target_status"
MEMORY_TARGET_STATUS: str = "memory_target_status"
TARGET_AVAILABLE: str = "available"

# Key linking Task 4 rows to the Task 6 history statistics.
HISTORY_JOIN_KEY: str = "role_key"

# ---------------------------------------------------------------------------
# Allowed pre-execution features (output contract §8.2 + Task 4/Task 6 history)
# ---------------------------------------------------------------------------
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

# Categorical base features (one-hot encoded downstream).
ALIBABA_GPU_2020_CATEGORICAL_FEATURES: List[str] = [
    "gpu_type",
    "gpu_type_spec",
    "workload",
]

# Task 6 point-in-time history statistics. These names match the columns in the
# merged Task 6 handoff (history_statistics.parquet): hist_<resource>_<stat>.
ALIBABA_GPU_2020_HISTORY_FEATURES: List[str] = [
    "hist_cpu_mean",
    "hist_cpu_p90",
    "hist_cpu_p95",
    "hist_cpu_p99",
    "hist_memory_mean",
    "hist_memory_p90",
    "hist_memory_p95",
    "hist_memory_p99",
]

# A missing-indicator column is added for each history statistic before any
# NaN-fill, so "no history" stays distinguishable from a true zero.
MISSING_INDICATOR_SUFFIX: str = "_missing"
ALIBABA_GPU_2020_HISTORY_MISSING_INDICATORS: List[str] = [
    f"{column}{MISSING_INDICATOR_SUFFIX}"
    for column in ALIBABA_GPU_2020_HISTORY_FEATURES
]

ALIBABA_GPU_2020_FEATURES: List[str] = (
    ALIBABA_GPU_2020_BASE_FEATURES
    + ALIBABA_GPU_2020_HISTORY_FEATURES
    + ALIBABA_GPU_2020_HISTORY_MISSING_INDICATORS
)

# ---------------------------------------------------------------------------
# Recommendation units / scope (profile)
# ---------------------------------------------------------------------------
RESOURCE_UNIT = {"cpu": "percent_of_vcpu", "memory": "gb"}
RESOURCE_SCOPE = "task_role_per_instance"

# ---------------------------------------------------------------------------
# Leaky columns — must never appear in the feature matrix (issue #89 Phase 1)
# ---------------------------------------------------------------------------
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
