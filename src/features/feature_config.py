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
