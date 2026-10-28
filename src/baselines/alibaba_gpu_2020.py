# src/baselines/alibaba_gpu_2020.py
#
# Task 6: Alibaba GPU 2020 baselines, point-in-time history statistics, and
# validation-only, memory-first baseline/min_runs selection.
#
# Dataset semantics (from the capability profile and output contract §8):
#   - Memory peak is the PRIMARY resource (peak_memory, unit "gb").
#   - CPU is LIFETIME-AVERAGE usage (observed_cpu, unit "percent_of_vcpu").
#     CPU results are average-usage sizing and must never be described as
#     peak-safe CPU provisioning.
#   - Any-resource and GPU metrics are suppressed.
#   - Requests/observations/recommendations are per instance of a task role
#     (resource_scope = "task_role_per_instance").
#
# This module computes history statistics and recommendations only. All
# violation / utilization / waste / shortfall metrics are produced by the
# shared RecommendationEvaluator; this module never reimplements evaluator
# formulas. The TEST split is never scored here (Task 7 owns the only
# final-test evaluation).

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from canonical.schema import DatasetCapabilities
from evaluation.evaluator import RecommendationEvaluator
from features.target_builder import iter_resource_history

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Matches the current Google baseline candidate grid (issue decision D-5).
MIN_RUNS_CANDIDATES: tuple[int, ...] = (1, 3, 5, 10)

# Historical-statistic policies plus the request status quo.
PERCENTILE_POLICIES: Mapping[str, float] = {"P90": 90.0, "P95": 95.0, "P99": 99.0}
HISTORY_POLICIES: tuple[str, ...] = ("Mean", "P90", "P95", "P99")
BASELINE_POLICIES: tuple[str, ...] = ("Request", *HISTORY_POLICIES)

# Per-policy recommendation-column suffix.
_POLICY_SUFFIX: Mapping[str, str] = {
    "Request": "request",
    "Mean": "mean",
    "P90": "p90",
    "P95": "p95",
    "P99": "p99",
}

# Canonical resource sources (output contract §8.3).
RESOURCE_SOURCE_FIELD: Mapping[str, str] = {
    "cpu": "observed_cpu",
    "memory": "peak_memory",
}
REQUEST_FIELD: Mapping[str, str] = {
    "cpu": "requested_cpu",
    "memory": "requested_memory",
}
RESOURCE_UNIT: Mapping[str, str] = {
    "cpu": "percent_of_vcpu",
    "memory": "gb",
}
RESOURCE_SCOPE = "task_role_per_instance"

# Deterministic, memory-first ranking (issue decision D-2). Every key is sorted
# ascending: lower violation and waste win; min_runs and policy break ties.
SELECTION_SORT_ORDER: tuple[str, ...] = (
    "memory_violation_pct",
    "average_memory_waste",
    "cpu_violation_pct",
    "average_cpu_waste",
    "min_runs",
    "policy",
)

# numpy.percentile interpolation method used for P90/P95/P99.
PERCENTILE_METHOD = "linear"


# ---------------------------------------------------------------------------
# Point-in-time history statistics
# ---------------------------------------------------------------------------

def _resource_statistics(values: Sequence[float]) -> dict[str, float]:
    """Mean and P90/P95/P99 of one role's point-in-time history snapshot.

    ``values`` is a completed-predecessor history view for a single resource.
    An empty history yields NaN statistics (the caller falls back to request).
    """
    count = len(values)
    if count == 0:
        return {
            "count": 0,
            "mean": np.nan,
            "p90": np.nan,
            "p95": np.nan,
            "p99": np.nan,
        }
    # Materialize only the current snapshot, compute, then discard it so no
    # per-row history table is retained (the full history is ~176M values per
    # resource). Values are unordered, so percentiles must sort internally.
    array = np.fromiter(values, dtype=float, count=count)
    p90, p95, p99 = np.percentile(array, [90.0, 95.0, 99.0], method=PERCENTILE_METHOD)
    return {
        "count": count,
        "mean": float(array.mean()),
        "p90": float(p90),
        "p95": float(p95),
        "p99": float(p99),
    }


# Column names produced by compute_history_statistics (independent of Task 4
# history-count columns, which are kept for cross-checking).
HISTORY_STAT_COLUMNS: tuple[str, ...] = (
    "hist_cpu_count", "hist_cpu_mean", "hist_cpu_p90", "hist_cpu_p95", "hist_cpu_p99",
    "hist_memory_count", "hist_memory_mean", "hist_memory_p90", "hist_memory_p95", "hist_memory_p99",
)


def compute_history_statistics(
    role_occurrences: pd.DataFrame,
    profile: DatasetCapabilities,
) -> pd.DataFrame:
    """Stream point-in-time Mean/P90/P95/P99 per resource for every eligible row.

    History is delegated to ``iter_resource_history`` (the Task 4 rule): a
    predecessor counts only when it shares the recurrence, its resource value
    is populated and not invalid, and it completed at or before the current
    row's submission (``end_time_us <= start_time_us``). The current row never
    counts itself.

    Pass the union of every partition whose history should be visible. Because
    the rule only admits completed predecessors, passing the full eligible
    frame (train + validation + test history inputs) gives each row exactly its
    point-in-time history and reproduces the Task 4 history counts, for any
    split, without leaking future or current outcomes.

    Returns a frame indexed by ``role_key`` with HISTORY_STAT_COLUMNS. CPU and
    memory statistics are computed independently; a missing CPU value never
    removes a row from memory history.
    """
    records: dict[str, dict[str, float]] = {}
    for history in iter_resource_history(role_occurrences, profile):
        cpu = _resource_statistics(history.cpu_values)
        memory = _resource_statistics(history.memory_values)
        records[history.role_key] = {
            "hist_cpu_count": cpu["count"],
            "hist_cpu_mean": cpu["mean"],
            "hist_cpu_p90": cpu["p90"],
            "hist_cpu_p95": cpu["p95"],
            "hist_cpu_p99": cpu["p99"],
            "hist_memory_count": memory["count"],
            "hist_memory_mean": memory["mean"],
            "hist_memory_p90": memory["p90"],
            "hist_memory_p95": memory["p95"],
            "hist_memory_p99": memory["p99"],
        }

    stats = pd.DataFrame.from_dict(records, orient="index", columns=list(HISTORY_STAT_COLUMNS))
    stats.index.name = "role_key"
    # Integer counts, float statistics (typed even when the input is empty).
    for column in ("hist_cpu_count", "hist_memory_count"):
        stats[column] = stats[column].astype("int64")
    return stats


def attach_history_statistics(
    rows: pd.DataFrame,
    statistics: pd.DataFrame,
    *,
    verify_counts: bool = True,
) -> pd.DataFrame:
    """Left-join history statistics onto rows by ``role_key``.

    When ``verify_counts`` is True and the Task 4 history-count columns are
    present, the streamed counts must equal them exactly. Eligible rows always
    receive statistics; this is a hard guard against a mismatched history rule.
    """
    if "role_key" not in rows.columns:
        raise ValueError("rows must contain role_key")
    merged = rows.merge(statistics, how="left", on="role_key")

    if verify_counts:
        eligible = merged["exclusion_reason"].isna() if "exclusion_reason" in merged else pd.Series(
            True, index=merged.index
        )
        for resource in ("cpu", "memory"):
            streamed = merged.loc[eligible, f"hist_{resource}_count"]
            if streamed.isna().any():
                raise ValueError(
                    f"Eligible rows missing streamed {resource} history statistics"
                )
            task4_column = f"{resource}_history_count"
            if task4_column in merged.columns:
                task4 = merged.loc[eligible, task4_column]
                if not streamed.astype("int64").eq(task4.astype("int64")).all():
                    raise ValueError(
                        f"Streamed {resource} history count disagrees with Task 4 "
                        f"{task4_column}; the history rule must match exactly"
                    )
    return merged


# ---------------------------------------------------------------------------
# Baseline recommendations
# ---------------------------------------------------------------------------

def _require_requests(rows: pd.DataFrame) -> None:
    """Fail loudly if an eligible row is missing a canonical request.

    The adapter excludes ``missing_or_invalid_request`` rows, so an eligible
    row without a request is an input error, not something to impute.
    """
    eligible = rows["exclusion_reason"].isna() if "exclusion_reason" in rows else pd.Series(
        True, index=rows.index
    )
    for resource, column in REQUEST_FIELD.items():
        if column not in rows.columns:
            raise ValueError(f"rows must contain canonical request column {column!r}")
        if rows.loc[eligible, column].isna().any():
            raise ValueError(
                f"Unexpected missing {column} on an eligible row; requests are "
                "never imputed (see missing_or_invalid_request exclusion)"
            )


def add_baseline_recommendations(rows: pd.DataFrame, min_runs: int) -> pd.DataFrame:
    """Add Request/Mean/P90/P95/P99 recommendation columns for CPU and memory.

    A history statistic is used only when the resource history count is at
    least ``min_runs`` and the statistic is non-null; otherwise the row falls
    back to its current canonical request for that resource. CPU and memory are
    handled independently, so missing CPU never affects a memory recommendation.
    Requires history statistics to have been attached first.
    """
    if min_runs < 1:
        raise ValueError("min_runs must be at least 1")
    missing_stats = [c for c in HISTORY_STAT_COLUMNS if c not in rows.columns]
    if missing_stats:
        raise ValueError(f"History statistics not attached: {missing_stats}")
    _require_requests(rows)

    result = rows.copy()

    for resource in ("cpu", "memory"):
        request = result[REQUEST_FIELD[resource]]
        count = result[f"hist_{resource}_count"]

        # Request status quo.
        result[f"rec_{resource}_request"] = request

        for policy in HISTORY_POLICIES:
            suffix = _POLICY_SUFFIX[policy]
            statistic = result[f"hist_{resource}_{suffix}"]
            use_history = (count >= min_runs) & statistic.notna()
            result[f"uses_history_{resource}_{suffix}"] = use_history
            result[f"rec_{resource}_{suffix}"] = statistic.where(use_history, request)

    return result


def recommendation_columns(policy: str) -> tuple[str, str]:
    """Return (cpu_rec_col, memory_rec_col) for a baseline policy name."""
    if policy not in BASELINE_POLICIES:
        raise ValueError(f"Unknown baseline policy {policy!r}")
    suffix = _POLICY_SUFFIX[policy]
    return f"rec_cpu_{suffix}", f"rec_memory_{suffix}"


# ---------------------------------------------------------------------------
# Evaluation (delegated to the shared evaluator)
# ---------------------------------------------------------------------------

# Identity columns carried through evaluation for traceability and group
# weighting. They are not required by the evaluator but survive evaluate().
_EVAL_ID_COLUMNS: tuple[str, ...] = ("role_key", "occurrence_id", "recurrence_key")


def build_canonical_eval_frame(
    rows: pd.DataFrame,
    cpu_rec_col: str,
    memory_rec_col: str,
    policy_name: str,
) -> pd.DataFrame:
    """Assemble the canonical evaluator view for one policy.

    The actual columns are the Task 4 next-occurrence targets (``actual_cpu`` /
    ``actual_memory`` with their unit columns). The recommended columns are the
    policy's recommendation with the profile units and resource scope.
    """
    required = {"dataset_id", "workload_id", "actual_cpu", "actual_memory", cpu_rec_col, memory_rec_col}
    missing = sorted(required - set(rows.columns))
    if missing:
        raise ValueError(f"Cannot build evaluator view, missing columns: {missing}")

    frame = pd.DataFrame(index=rows.index)
    frame["dataset_id"] = rows["dataset_id"]
    frame["workload_id"] = rows["workload_id"]
    frame["policy_name"] = policy_name
    for column in _EVAL_ID_COLUMNS:
        if column in rows.columns:
            frame[column] = rows[column]

    frame["actual_cpu"] = rows["actual_cpu"]
    frame["actual_cpu_unit"] = rows.get("actual_cpu_unit", RESOURCE_UNIT["cpu"])
    frame["actual_memory"] = rows["actual_memory"]
    frame["actual_memory_unit"] = rows.get("actual_memory_unit", RESOURCE_UNIT["memory"])

    frame["recommended_cpu"] = rows[cpu_rec_col]
    frame["recommended_cpu_unit"] = RESOURCE_UNIT["cpu"]
    frame["recommended_memory"] = rows[memory_rec_col]
    frame["recommended_memory_unit"] = RESOURCE_UNIT["memory"]

    frame["resource_scope"] = RESOURCE_SCOPE
    frame["recommended_resource_scope"] = RESOURCE_SCOPE
    return frame


def evaluate_policy(
    rows: pd.DataFrame,
    policy: str,
    evaluator: RecommendationEvaluator,
) -> pd.DataFrame:
    """Return the evaluator's row-level output for one baseline policy."""
    cpu_rec_col, memory_rec_col = recommendation_columns(policy)
    frame = build_canonical_eval_frame(rows, cpu_rec_col, memory_rec_col, policy)
    return evaluator.evaluate_canonical(frame)


# ---------------------------------------------------------------------------
# Common validation population
# ---------------------------------------------------------------------------

def freeze_common_validation_population(validation_rows: pd.DataFrame) -> pd.DataFrame:
    """Return the eligible validation rows with at least one available target.

    Frozen once, before any scoring, and shared by every policy/min_runs
    candidate (issue decision D-3). A row qualifies when its CPU or memory
    next-occurrence target is available; the evaluator then applies per-resource
    denominators. This reads validation target statuses only, never test.
    """
    for column in ("split", "cpu_target_status", "memory_target_status"):
        if column not in validation_rows.columns:
            raise ValueError(f"validation rows must contain {column!r}")

    eligible = validation_rows["split"].eq("validation")
    if "exclusion_reason" in validation_rows.columns:
        eligible &= validation_rows["exclusion_reason"].isna()
    has_target = (
        validation_rows["cpu_target_status"].eq("available")
        | validation_rows["memory_target_status"].eq("available")
    )
    common = validation_rows.loc[eligible & has_target].copy()
    if common.empty:
        raise ValueError("No validation rows have an available CPU or memory target")
    return common


# ---------------------------------------------------------------------------
# Validation comparison and selection
# ---------------------------------------------------------------------------

# summarize() keys retained in the validation comparison (Alibaba suppresses
# the any-resource keys).
_SUMMARY_KEYS: tuple[str, ...] = (
    "row_count",
    "valid_cpu_violation_count",
    "valid_memory_violation_count",
    "valid_cpu_utilization_count",
    "valid_memory_utilization_count",
    "cpu_violation_pct",
    "memory_violation_pct",
    "average_cpu_utilization",
    "average_memory_utilization",
    "average_cpu_waste",
    "average_memory_waste",
    "average_cpu_shortfall",
    "average_memory_shortfall",
)


def build_validation_comparison(
    validation_common: pd.DataFrame,
    statistics: pd.DataFrame,
    profile: DatasetCapabilities,
    *,
    min_runs_candidates: Sequence[int] = MIN_RUNS_CANDIDATES,
) -> pd.DataFrame:
    """Score every policy x min_runs candidate on the frozen validation set.

    ``validation_common`` is the frozen common population (one fixed row set);
    recommendations change with ``min_runs`` but the scored rows never do.
    Returns one row per (policy, min_runs) with the evaluator's summary metrics.
    """
    with_stats = attach_history_statistics(validation_common, statistics)
    evaluator = RecommendationEvaluator(capabilities=profile)

    comparison_rows: list[dict[str, object]] = []
    for min_runs in min_runs_candidates:
        candidate = add_baseline_recommendations(with_stats, min_runs=min_runs)
        for policy in BASELINE_POLICIES:
            evaluated = evaluate_policy(candidate, policy, evaluator)
            summary = evaluator.summarize(evaluated)
            record: dict[str, object] = {"policy": policy, "min_runs": int(min_runs)}
            for key in _SUMMARY_KEYS:
                record[key] = summary.get(key, np.nan)
            comparison_rows.append(record)

    return pd.DataFrame(comparison_rows)


@dataclass(frozen=True)
class BaselineSelection:
    """The single locked baseline policy and min_runs chosen on validation."""

    selected_policy: str
    selected_min_runs: int
    sort_order: tuple[str, ...]
    validation_metrics: dict[str, float]
    validation_population_size: int


def select_baseline(
    validation_comparison: pd.DataFrame,
    *,
    sort_order: Sequence[str] = SELECTION_SORT_ORDER,
    validation_population_size: int | None = None,
) -> BaselineSelection:
    """Pick one policy and one min_runs using validation results only.

    Deterministic memory-first ascending sort (NaN metrics sort last, so a
    candidate with no valid denominator can never win over a scored one).
    """
    if validation_comparison.empty:
        raise ValueError("validation_comparison is empty")
    ranked = validation_comparison.sort_values(
        by=list(sort_order), ascending=True, kind="mergesort", na_position="last"
    ).reset_index(drop=True)
    winner = ranked.iloc[0]

    metrics = {
        key: (float(winner[key]) if pd.notna(winner[key]) else float("nan"))
        for key in _SUMMARY_KEYS
        if key in ranked.columns
    }
    population = (
        int(validation_population_size)
        if validation_population_size is not None
        else int(winner.get("row_count", 0))
    )
    return BaselineSelection(
        selected_policy=str(winner["policy"]),
        selected_min_runs=int(winner["min_runs"]),
        sort_order=tuple(sort_order),
        validation_metrics=metrics,
        validation_population_size=population,
    )


# ---------------------------------------------------------------------------
# Locked recommendations for all splits
# ---------------------------------------------------------------------------

def build_locked_recommendations(
    rows: pd.DataFrame,
    statistics: pd.DataFrame,
    selection: BaselineSelection,
) -> pd.DataFrame:
    """Produce all five baseline recommendations at the selected min_runs.

    Used for train, validation, and test rows after the selection is locked.
    The selected policy's recommendation is surfaced in ``rec_cpu_selected`` /
    ``rec_memory_selected`` and ``selected_baseline_policy``. This touches only
    history statistics, requests, and features; it reads no target and scores
    nothing, so it is safe for the test split.
    """
    with_stats = attach_history_statistics(rows, statistics)
    recommended = add_baseline_recommendations(with_stats, min_runs=selection.selected_min_runs)

    cpu_col, memory_col = recommendation_columns(selection.selected_policy)
    recommended["selected_baseline_policy"] = selection.selected_policy
    recommended["selected_min_runs"] = selection.selected_min_runs
    recommended["rec_cpu_selected"] = recommended[cpu_col]
    recommended["rec_memory_selected"] = recommended[memory_col]
    recommended["recommended_cpu_unit"] = RESOURCE_UNIT["cpu"]
    recommended["recommended_memory_unit"] = RESOURCE_UNIT["memory"]
    recommended["recommended_resource_scope"] = RESOURCE_SCOPE

    # Emit a focused, leakage-proof handoff: identity, pre-execution requests,
    # point-in-time history counts, and the recommendations only. Current-run
    # observations (observed_cpu, peak_memory, the always-null peak_cpu), the
    # next-occurrence targets/statuses, and split/quality columns are
    # deliberately excluded so the artifact is uniform across train/val/test
    # and cannot carry a realized outcome. Targets live in the Task 4 tables.
    identity = [c for c in (
        "dataset_id", "workload_id", "role_key", "occurrence_id",
        "recurrence_key", "start_time_us",
    ) if c in recommended.columns]
    requests = [c for c in ("requested_cpu", "requested_memory") if c in recommended.columns]
    counts = [c for c in ("cpu_history_count", "memory_history_count") if c in recommended.columns]
    rec_cols = [c for c in recommended.columns
                if c.startswith(("rec_cpu_", "rec_memory_", "uses_history_"))]
    selected = ["selected_baseline_policy", "selected_min_runs", "rec_cpu_selected", "rec_memory_selected"]
    units = ["recommended_cpu_unit", "recommended_memory_unit", "recommended_resource_scope"]

    ordered: list[str] = []
    for column in (*identity, *requests, *counts, *rec_cols, *selected, *units):
        if column not in ordered:
            ordered.append(column)
    return recommended[ordered].copy()


# ---------------------------------------------------------------------------
# Sensitivity analyses (reported separately; never change the selection)
# ---------------------------------------------------------------------------

# Row-level evaluator column behind each group-weighted summary metric.
_GROUP_WEIGHTED_METRICS: Mapping[str, str] = {
    "cpu_violation_pct": "cpu_violation",
    "memory_violation_pct": "memory_violation",
    "average_cpu_utilization": "cpu_utilization",
    "average_memory_utilization": "memory_utilization",
    "average_cpu_waste": "cpu_waste",
    "average_memory_waste": "memory_waste",
    "average_cpu_shortfall": "cpu_shortfall",
    "average_memory_shortfall": "memory_shortfall",
}


def group_weighted_summary(
    evaluated: pd.DataFrame,
    group_col: str = "recurrence_key",
) -> dict[str, float]:
    """Weight each recurrence group equally (issue decision D-4).

    Metrics are averaged within each group (NaN rows excluded), then averaged
    across groups. Violation fractions are scaled to percentages to match the
    occurrence-weighted summary keys.
    """
    if group_col not in evaluated.columns:
        raise ValueError(f"evaluated frame must carry {group_col!r} for group weighting")
    summary: dict[str, float] = {"n_groups": int(evaluated[group_col].nunique())}
    for out_key, column in _GROUP_WEIGHTED_METRICS.items():
        if column not in evaluated.columns:
            summary[out_key] = float("nan")
            continue
        group_means = evaluated.groupby(group_col)[column].mean()
        value = group_means.mean()
        if out_key.endswith("_violation_pct") and pd.notna(value):
            value = value * 100.0
        summary[out_key] = float(value) if pd.notna(value) else float("nan")
    return summary


def _score_subset(
    recommended: pd.DataFrame,
    mask: pd.Series,
    label: str,
    evaluator: RecommendationEvaluator,
    *,
    group_weighted: bool = False,
) -> list[dict[str, object]]:
    """Occurrence- or group-weighted scores for all policies on a row subset."""
    subset = recommended.loc[mask]
    rows: list[dict[str, object]] = []
    for policy in BASELINE_POLICIES:
        record: dict[str, object] = {"sensitivity": label, "policy": policy, "row_count": int(len(subset))}
        if subset.empty:
            rows.append(record)
            continue
        evaluated = evaluate_policy(subset, policy, evaluator)
        if group_weighted:
            record.update(group_weighted_summary(evaluated))
        else:
            summary = evaluator.summarize(evaluated)
            for key in _SUMMARY_KEYS:
                record[key] = summary.get(key, np.nan)
        rows.append(record)
    return rows


def build_sensitivity_tables(
    validation_common: pd.DataFrame,
    statistics: pd.DataFrame,
    profile: DatasetCapabilities,
    selection: BaselineSelection,
) -> pd.DataFrame:
    """Validation sensitivity cuts for all policies at the selected min_runs.

    Cuts (each reported separately, none of which changed the selection):
      - occurrence_weighted: the full frozen common population (per-row weight);
      - same_second_excluded: rows without the Task 4 same-second flag;
      - same_second_only: rows with the same-second flag;
      - multi_instance: the eligible inst_num > 1 subgroup;
      - group_weighted: full population, each recurrence_key weighted equally.
    """
    with_stats = attach_history_statistics(validation_common, statistics)
    recommended = add_baseline_recommendations(with_stats, min_runs=selection.selected_min_runs)
    evaluator = RecommendationEvaluator(capabilities=profile)

    all_rows = pd.Series(True, index=recommended.index)
    records: list[dict[str, object]] = []
    records += _score_subset(recommended, all_rows, "occurrence_weighted", evaluator)

    if "next_occurrence_same_second" in recommended.columns:
        flagged = recommended["next_occurrence_same_second"].eq(True)
        records += _score_subset(recommended, ~flagged, "same_second_excluded", evaluator)
        records += _score_subset(recommended, flagged, "same_second_only", evaluator)

    if "inst_num" in recommended.columns:
        multi = recommended["inst_num"] > 1
        records += _score_subset(recommended, multi, "multi_instance", evaluator)

    records += _score_subset(recommended, all_rows, "group_weighted", evaluator, group_weighted=True)

    frame = pd.DataFrame(records)
    frame.insert(1, "min_runs", int(selection.selected_min_runs))
    return frame
