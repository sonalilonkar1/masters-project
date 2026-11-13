# src/models/alibaba_gpu_2020_final_test.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from canonical.schema import DatasetCapabilities
from evaluation.evaluator import RecommendationEvaluator
from policies.hybrid import hybrid_recommendation

from features import alibaba_gpu_2020_feature_config as fc
from features.ml_prep import prepare_xy, validate_features
from features.alibaba_gpu_2020_ml_prep import (
    add_history_missing_indicators,
    attach_history_statistics,
    clip_negative_predictions,
    _sanitize_feature_name,
)
import baselines.alibaba_gpu_2020 as a6
import models.alibaba_gpu_2020_select as sel


FINAL_POLICIES: tuple[str, ...] = ("Request", "Mean", "P90", "P95", "P99", "ML", "Hybrid")

_FINAL_SUMMARY_KEYS: tuple[str, ...] = (
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


@dataclass(frozen=True)
class FinalTestResult:
    comparison: pd.DataFrame
    sensitivity: pd.DataFrame
    predictions: pd.DataFrame
    n_clipped: dict[str, int]
    safeguard_missing: dict[str, int]
    final_population_size: int


def validate_locked_manifest(manifest: Mapping[str, object]) -> None:
    required = (
        "task", "phase", "task6_selection", "task4_inputs", "selected_models",
        "model_artifacts", "feature_order", "hybrid_rule",
        "negative_prediction_rule", "cpu_result_semantics",
        "primary_resource", "any_resource_metric_reported",
    )
    missing = [key for key in required if key not in manifest]
    if missing:
        raise ValueError(f"Locked PR1 manifest missing fields: {missing}")

    if manifest["task"] != "task7_alibaba_gpu_2020_ml_hybrid":
        raise ValueError("Unexpected Task 7 manifest task")
    if manifest["phase"] != "pr1_validation_lock":
        raise ValueError("PR2 requires a PR1 validation-lock manifest")
    if manifest["hybrid_rule"] != sel.HYBRID_RULE:
        raise ValueError("Locked Hybrid rule does not match implementation")
    if manifest["negative_prediction_rule"] != sel.NEGATIVE_PREDICTION_RULE:
        raise ValueError("Locked negative-prediction rule does not match implementation")
    if manifest["cpu_result_semantics"] != "average_usage":
        raise ValueError("Alibaba CPU result semantics must remain average_usage")
    if manifest["primary_resource"] != "memory":
        raise ValueError("Alibaba memory must remain the primary resource")
    if bool(manifest["any_resource_metric_reported"]):
        raise ValueError("Alibaba final test must not report any-resource metrics")

    if set(manifest["selected_models"]) != {"cpu", "memory"}:
        raise ValueError("Locked manifest must contain independent CPU and memory models")

    feature_order = manifest["feature_order"]
    if not isinstance(feature_order, list) or not feature_order:
        raise ValueError("Locked feature_order must be a non-empty list")
    if len(feature_order) != len(set(feature_order)):
        raise ValueError("Locked feature_order contains duplicates")


def prepare_locked_test_features(
    test_rows: pd.DataFrame,
    history_statistics: pd.DataFrame,
    feature_order: Sequence[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = add_history_missing_indicators(
        attach_history_statistics(test_rows, history_statistics)
    )
    validate_features(
        rows,
        fc.ALIBABA_GPU_2020_FEATURES,
        "test",
        leaky_columns=fc.ALIBABA_GPU_2020_LEAKY_COLUMNS,
    )

    X_test, _ = prepare_xy(
        rows,
        fc.ALIBABA_GPU_2020_FEATURES,
        fc.TARGET_CPU,
    )
    renamed = [_sanitize_feature_name(c) for c in X_test.columns]
    if len(set(renamed)) != len(renamed):
        raise ValueError("Feature-name sanitization produced a collision")
    X_test.columns = renamed

    locked = list(feature_order)
    X_test = X_test.reindex(columns=locked, fill_value=0).astype("float64")
    if list(X_test.columns) != locked:
        raise RuntimeError("Failed to reproduce locked PR1 feature order")
    return X_test, rows


def _final_population(rows: pd.DataFrame) -> pd.DataFrame:
    required = ("split", fc.CPU_TARGET_STATUS, fc.MEMORY_TARGET_STATUS)
    missing = [c for c in required if c not in rows.columns]
    if missing:
        raise ValueError(f"Test rows missing final-evaluation columns: {missing}")

    eligible = rows["split"].eq("test")
    if "exclusion_reason" in rows.columns:
        eligible &= rows["exclusion_reason"].isna()
    has_target = (
        rows[fc.CPU_TARGET_STATUS].eq(fc.TARGET_AVAILABLE)
        | rows[fc.MEMORY_TARGET_STATUS].eq(fc.TARGET_AVAILABLE)
    )
    population = rows.loc[eligible & has_target].copy()
    if population.empty:
        raise ValueError("No final-test rows have an available CPU or memory target")
    return population


def _align_task6_recommendations(
    rows: pd.DataFrame,
    recommendations_test: pd.DataFrame,
) -> pd.DataFrame:
    rec_cols = [
        c for c in recommendations_test.columns
        if c.startswith(("rec_cpu_", "rec_memory_"))
    ]
    required = {
        "role_key",
        "selected_baseline_policy",
        "selected_min_runs",
        "rec_cpu_selected",
        "rec_memory_selected",
        *rec_cols,
    }
    missing = sorted(required - set(recommendations_test.columns))
    if missing:
        raise ValueError(f"Task 6 test handoff missing columns: {missing}")

    keep = [
        "role_key", "selected_baseline_policy", "selected_min_runs",
        *rec_cols,
    ]
    merged = rows.merge(
        recommendations_test[keep],
        on="role_key",
        how="left",
        validate="one_to_one",
    )
    if len(merged) != len(rows):
        raise RuntimeError("Task 6 recommendation join changed test row count")
    return merged


def _build_eval_frame(rows, cpu_values, memory_values, policy_name):
    frame = pd.DataFrame(index=rows.index)
    frame["dataset_id"] = rows["dataset_id"]
    frame["workload_id"] = rows["workload_id"]
    frame["policy_name"] = policy_name
    for column in ("role_key", "occurrence_id", "recurrence_key"):
        if column in rows.columns:
            frame[column] = rows[column]

    frame["actual_cpu"] = rows[fc.TARGET_CPU]
    frame["actual_cpu_unit"] = rows.get("actual_cpu_unit", fc.RESOURCE_UNIT["cpu"])
    frame["actual_memory"] = rows[fc.TARGET_MEMORY]
    frame["actual_memory_unit"] = rows.get("actual_memory_unit", fc.RESOURCE_UNIT["memory"])
    frame["recommended_cpu"] = np.asarray(cpu_values, dtype=float)
    frame["recommended_cpu_unit"] = fc.RESOURCE_UNIT["cpu"]
    frame["recommended_memory"] = np.asarray(memory_values, dtype=float)
    frame["recommended_memory_unit"] = fc.RESOURCE_UNIT["memory"]
    frame["resource_scope"] = fc.RESOURCE_SCOPE
    frame["recommended_resource_scope"] = fc.RESOURCE_SCOPE
    return frame


def _policy_arrays(rows: pd.DataFrame, policy: str):
    if policy in sel.BASELINE_POLICY_COLUMNS:
        cpu_col, mem_col = sel.BASELINE_POLICY_COLUMNS[policy]
    elif policy == "ML":
        cpu_col, mem_col = "ml_recommended_cpu", "ml_recommended_memory"
    elif policy == "Hybrid":
        cpu_col, mem_col = "hybrid_recommended_cpu", "hybrid_recommended_memory"
    else:
        raise ValueError(f"Unknown final-test policy {policy!r}")
    return (
        rows[cpu_col].to_numpy(dtype=float),
        rows[mem_col].to_numpy(dtype=float),
    )


def _score_policy(
    rows: pd.DataFrame,
    policy: str,
    evaluator: RecommendationEvaluator,
    *,
    group_weighted: bool = False,
) -> dict[str, object]:
    cpu_rec, mem_rec = _policy_arrays(rows, policy)
    evaluated = evaluator.evaluate_canonical(
        _build_eval_frame(rows, cpu_rec, mem_rec, policy)
    )
    record: dict[str, object] = {"policy": policy, "row_count": int(len(rows))}

    if group_weighted:
        record.update(a6.group_weighted_summary(evaluated))
    else:
        summary = evaluator.summarize(evaluated)
        for key in _FINAL_SUMMARY_KEYS:
            record[key] = summary.get(key, np.nan)

    metadata = evaluator.summary_metadata(evaluated)
    for key in ("cpu_result_semantics", "primary_resource", "any_resource_metric_reported"):
        record[key] = metadata.get(key)
    return record


def build_final_sensitivity(
    rows: pd.DataFrame,
    profile: DatasetCapabilities,
) -> pd.DataFrame:
    for column in ("next_occurrence_same_second", "inst_num"):
        if column not in rows.columns:
            raise ValueError(f"Final sensitivity requires column {column!r}")

    evaluator = RecommendationEvaluator(capabilities=profile)
    records: list[dict[str, object]] = []
    cuts = [
        ("occurrence_weighted", pd.Series(True, index=rows.index), False),
        ("same_second_excluded", ~rows["next_occurrence_same_second"].eq(True), False),
        ("same_second_only", rows["next_occurrence_same_second"].eq(True), False),
        ("multi_instance", rows["inst_num"] > 1, False),
        ("group_weighted", pd.Series(True, index=rows.index), True),
    ]
    for label, mask, group_weighted in cuts:
        subset = rows.loc[mask]
        for policy in FINAL_POLICIES:
            record = {
                "sensitivity": label,
                "policy": policy,
                "row_count": int(len(subset)),
            }
            if not subset.empty:
                record.update(
                    _score_policy(
                        subset,
                        policy,
                        evaluator,
                        group_weighted=group_weighted,
                    )
                )
                record["sensitivity"] = label
            records.append(record)

    return pd.DataFrame(records)


def evaluate_final_test(
    test_rows: pd.DataFrame,
    history_statistics: pd.DataFrame,
    recommendations_test: pd.DataFrame,
    models: Mapping[str, object],
    manifest: Mapping[str, object],
    profile: DatasetCapabilities,
) -> FinalTestResult:
    validate_locked_manifest(manifest)
    if set(models) != {"cpu", "memory"}:
        raise ValueError("Exactly the locked CPU and memory models are required")

    X_test, feature_rows = prepare_locked_test_features(
        test_rows,
        history_statistics,
        manifest["feature_order"],
    )
    rows = _align_task6_recommendations(feature_rows, recommendations_test)

    locked_policy = manifest["task6_selection"]["selected_policy"]
    locked_min_runs = int(manifest["task6_selection"]["selected_min_runs"])
    if locked_policy not in a6.SELECTABLE_POLICIES:
        raise ValueError(f"Locked Task 6 policy is invalid: {locked_policy!r}")

    policies = rows["selected_baseline_policy"].dropna().unique()
    min_runs = rows["selected_min_runs"].dropna().unique()
    if len(policies) != 1 or str(policies[0]) != str(locked_policy):
        raise ValueError("Task 6 test handoff baseline policy disagrees with PR1 manifest")
    if len(min_runs) != 1 or int(min_runs[0]) != locked_min_runs:
        raise ValueError("Task 6 test handoff min_runs disagrees with PR1 manifest")

    ml_predictions = {}
    n_clipped = {}
    hybrid_predictions = {}
    safeguard_missing = {}

    for resource in ("cpu", "memory"):
        prediction, clipped = clip_negative_predictions(models[resource].predict(X_test))
        ml_predictions[resource] = prediction
        n_clipped[resource] = int(clipped)

        safeguard = rows[f"rec_{resource}_selected"].to_numpy(dtype=float)
        hybrid, missing = hybrid_recommendation(prediction, safeguard)
        hybrid_predictions[resource] = hybrid
        safeguard_missing[resource] = int(np.count_nonzero(missing))

    rows["ml_recommended_cpu"] = ml_predictions["cpu"]
    rows["ml_recommended_memory"] = ml_predictions["memory"]
    rows["hybrid_recommended_cpu"] = hybrid_predictions["cpu"]
    rows["hybrid_recommended_memory"] = hybrid_predictions["memory"]

    population = _final_population(rows)
    evaluator = RecommendationEvaluator(capabilities=profile)
    comparison = pd.DataFrame(
        [_score_policy(population, policy, evaluator) for policy in FINAL_POLICIES]
    )
    sensitivity = build_final_sensitivity(population, profile)

    prediction_columns = [
        c for c in (
            "role_key", "occurrence_id", "recurrence_key",
            fc.CPU_TARGET_STATUS, fc.TARGET_CPU,
            fc.MEMORY_TARGET_STATUS, fc.TARGET_MEMORY,
            "rec_cpu_request", "rec_memory_request",
            "rec_cpu_mean", "rec_memory_mean",
            "rec_cpu_p90", "rec_memory_p90",
            "rec_cpu_p95", "rec_memory_p95",
            "rec_cpu_p99", "rec_memory_p99",
            "ml_recommended_cpu", "ml_recommended_memory",
            "hybrid_recommended_cpu", "hybrid_recommended_memory",
        )
        if c in rows.columns
    ]
    predictions = rows[prediction_columns].copy()
    predictions["recommended_cpu_unit"] = fc.RESOURCE_UNIT["cpu"]
    predictions["recommended_memory_unit"] = fc.RESOURCE_UNIT["memory"]
    predictions["recommended_resource_scope"] = fc.RESOURCE_SCOPE

    return FinalTestResult(
        comparison=comparison,
        sensitivity=sensitivity,
        predictions=predictions,
        n_clipped=n_clipped,
        safeguard_missing=safeguard_missing,
        final_population_size=int(len(population)),
    )
