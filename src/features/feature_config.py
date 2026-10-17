# src/features/feature_config.py
#
# Single source of truth for ML feature definitions used across
# the TraceAdvisor pipeline (Notebooks 5, 6, and any future ML work).
#
# This module centralizes:
# - The canonical ML feature column list
# - Categorical vs. numeric feature classification
# - Prediction target names
# - The rename map from raw profile columns to hist_* columns

from __future__ import annotations

from typing import Dict, List

# ---------------------------------------------------------------------------
# Prediction targets
# ---------------------------------------------------------------------------

TARGET_CPU: str = "peak_cpu"
TARGET_MEM: str = "peak_mem_gb"

# ---------------------------------------------------------------------------
# Canonical ML feature columns
# ---------------------------------------------------------------------------
# These are the features used as inputs to all ML models.
# Every feature must be available at pre-execution time (no leaky fields).
# Historical features use the hist_* prefix to indicate they are computed
# from executions E1...Et-1 only (never the current or future executions).

FEATURE_COLS: List[str] = [
    # Known at submission time
    "req_cpu",
    "req_mem_gb",

    # Recurrence / history
    "hist_run_count",
    "hist_is_recurring",
    "hist_mean_duration",

    # Historical CPU behavior
    "hist_mean_peak_cpu",
    "hist_std_peak_cpu",
    "hist_cv_cpu",
    "hist_p90_cpu",
    "hist_p95_cpu",
    "hist_p99_cpu",

    # Historical memory behavior
    "hist_mean_peak_mem",
    "hist_std_peak_mem",
    "hist_cv_mem",
    "hist_p90_mem",
    "hist_p95_mem",
    "hist_p99_mem",

    # Historical categorical / profile features
    "hist_confidence_tier",
    "hist_resource_profile",
    "hist_duration_profile",
    "hist_recurrence_profile",
    "hist_stability_profile",
    "hist_stability",
]

# ---------------------------------------------------------------------------
# Feature type classification
# ---------------------------------------------------------------------------
# Categorical features need one-hot encoding before modeling.
# Numeric features are used as-is (with NaN fill).

CATEGORICAL_FEATURES: List[str] = [
    "hist_confidence_tier",
    "hist_resource_profile",
    "hist_duration_profile",
    "hist_recurrence_profile",
    "hist_stability_profile",
]

NUMERIC_FEATURES: List[str] = [
    c for c in FEATURE_COLS if c not in CATEGORICAL_FEATURES
]

# ---------------------------------------------------------------------------
# Rename map: raw profile columns → hist_* columns
# ---------------------------------------------------------------------------
# Used when attaching train-only job profiles to execution DataFrames.
# The rename ensures that historical features are clearly distinguished
# from current-execution fields.

HIST_RENAME_MAP: Dict[str, str] = {
    "run_count": "hist_run_count",
    "mean_peak_cpu": "hist_mean_peak_cpu",
    "std_peak_cpu": "hist_std_peak_cpu",
    "mean_peak_mem": "hist_mean_peak_mem",
    "std_peak_mem": "hist_std_peak_mem",
    "mean_duration": "hist_mean_duration",
    "cv_cpu": "hist_cv_cpu",
    "cv_mem": "hist_cv_mem",
    "stability": "hist_stability",
    "is_recurring": "hist_is_recurring",
    "confidence_tier": "hist_confidence_tier",
    "resource_profile": "hist_resource_profile",
    "duration_profile": "hist_duration_profile",
    "recurrence_profile": "hist_recurrence_profile",
    "stability_profile": "hist_stability_profile",
    "p90_cpu": "hist_p90_cpu",
    "p95_cpu": "hist_p95_cpu",
    "p99_cpu": "hist_p99_cpu",
    "p90_mem": "hist_p90_mem",
    "p95_mem": "hist_p95_mem",
    "p99_mem": "hist_p99_mem",
}

# ---------------------------------------------------------------------------
# Leaky columns that must NEVER appear in ML feature matrices
# ---------------------------------------------------------------------------
# These fields contain information from the current execution and would
# cause data leakage if used as model inputs.

LEAKY_COLUMNS: List[str] = [
    "duration",
    "slack_req_cpu",
    "slack_req_mem_gb",
    "peak_cpu",
    "peak_mem_gb",
    "peak_mem",
]

# ===========================================================================
# Google subset occurrence-level contract (pipelines/google_subset, N05+)
# ===========================================================================
# The definitions above belong to the legacy notebooks/subset pipeline.
# The definitions below match the canonical N04 occurrence artifacts
# (train/val/test_occurrences.parquet), where one row is one full-workload
# occurrence: recurrence_key || execution_start_time_us.
#
# Prediction-time convention (from N04): each row is the state available at
# the start of the current occurrence, and the target is the peak of the next
# distinct occurrence of the same recurrence_key.

OCCURRENCE_TARGET_CPU: str = "target_cpu_next_occurrence_peak_ncu"
OCCURRENCE_TARGET_MEMORY: str = "target_memory_next_occurrence_peak_normalized"
OCCURRENCE_TARGET_TIME: str = "target_next_occurrence_start_time_us"

# Inputs known at the start of the current occurrence.
OCCURRENCE_FEATURE_COLS: List[str] = [
    # Submitted with the current occurrence
    "occurrence_requested_cpu_ncu",
    "occurrence_requested_memory_normalized",
    "occurrence_execution_count",
    "occurrence_cpu_request_nunique",
    "occurrence_memory_request_nunique",

    # Completed-occurrence history (Notebook 03, point-in-time)
    "prior_completed_occurrence_count",
    "occ_hist_peak_cpu_count",
    "occ_hist_peak_cpu_mean",
    "occ_hist_peak_cpu_std",
    "occ_hist_peak_cpu_p90",
    "occ_hist_peak_cpu_p95",
    "occ_hist_peak_cpu_p99",
    "occ_hist_peak_memory_count",
    "occ_hist_peak_memory_mean",
    "occ_hist_peak_memory_std",
    "occ_hist_peak_memory_p90",
    "occ_hist_peak_memory_p95",
    "occ_hist_peak_memory_p99",
    "occ_hist_runtime_count",
    "occ_hist_runtime_mean",
    "occ_hist_runtime_std",
    "occ_hist_runtime_p90",
    "occ_hist_runtime_p95",
    "occ_hist_runtime_p99",
]

# Exact columns that must never be model inputs: outcomes of the current
# occurrence (unknown at its start) and everything describing the target.
OCCURRENCE_LEAKY_COLUMNS: List[str] = [
    "occurrence_peak_cpu_ncu",
    "occurrence_peak_memory_normalized",
    "occurrence_end_time_us",
    "occurrence_runtime_us",
    OCCURRENCE_TARGET_TIME,
    OCCURRENCE_TARGET_CPU,
    OCCURRENCE_TARGET_MEMORY,
    "target_next_occurrence_execution_count",
]

# Column-name prefixes that must never be model inputs. Any column starting
# with these is a target, a baseline recommendation, or a baseline flag.
OCCURRENCE_LEAKY_PREFIXES: List[str] = [
    "target_",
    "rec_",
    "uses_history_",
]
