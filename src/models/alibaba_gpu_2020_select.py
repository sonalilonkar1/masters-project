# src/models/alibaba_gpu_2020_select.py
#
# Task 7 (#89) PR1: train candidate regressors (train only), select CPU and
# memory models INDEPENDENTLY on validation, validate the fixed Hybrid rule,
# and refit the selected models on train+validation. Builds on Sonali's
# feature_config / ml_prep / candidates foundation (PR #98).
#
# Hybrid is fixed: hybrid = max(ML prediction, selected Task 6 baseline),
# applied per resource. Negative predictions are clipped to zero. All
# violation/utilization/waste/shortfall metrics come from the shared
# RecommendationEvaluator. This module never reads the test split.

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from canonical.schema import DatasetCapabilities
from evaluation.evaluator import RecommendationEvaluator
from policies.hybrid import hybrid_recommendation

from features import alibaba_gpu_2020_feature_config as fc
from features.alibaba_gpu_2020_ml_prep import FeatureMatrices, clip_negative_predictions
from models.alibaba_gpu_2020_candidates import build_candidate_models, RANDOM_SEED

RESOURCES = ("cpu", "memory")
TARGET_COL = {"cpu": fc.TARGET_CPU, "memory": fc.TARGET_MEMORY}
TARGET_STATUS_COL = {"cpu": fc.CPU_TARGET_STATUS, "memory": fc.MEMORY_TARGET_STATUS}
HYBRID_SAFEGUARD_COL = {"cpu": "rec_cpu_selected", "memory": "rec_memory_selected"}

HYBRID_RULE = "max(ml_prediction, selected_task6_baseline)"
NEGATIVE_PREDICTION_RULE = "clip_to_zero"

# Validation-only model-selection order (all ascending). Accuracy leads (the ML
# model predicts next-occurrence usage; under-provisioning risk is handled by
# the Hybrid safeguard), then risk signals, then a deterministic name tie-break.
# Leading with violation would select the mean DummyRegressor, which is recorded
# only as a floor. Recorded in the manifest; easy to revise here.
MODEL_SELECTION_ORDER: tuple[str, ...] = (
    "rmse",
    "mae",
    "violation_pct",
    "average_shortfall",
    "model",
)

_EVAL_ID_COLUMNS = ("role_key", "occurrence_id", "recurrence_key")


def model_hyperparameters(model) -> dict[str, object]:
    """JSON-friendly hyperparameters for the manifest/candidate record."""
    return {k: (v if isinstance(v, (int, float, str, bool)) or v is None else str(v))
            for k, v in model.get_params().items()}


def _regression_metrics(y_true, y_pred) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)),
    }


def _available_mask(rows: pd.DataFrame, resource: str) -> pd.Series:
    return rows[TARGET_STATUS_COL[resource]].eq(fc.TARGET_AVAILABLE)


def _eval_frame(rows: pd.DataFrame, cpu_rec, memory_rec, policy_name: str) -> pd.DataFrame:
    """Canonical evaluator view; pass None for an unevaluated resource."""
    frame = pd.DataFrame(index=rows.index)
    frame["dataset_id"] = rows["dataset_id"]
    frame["workload_id"] = rows["workload_id"]
    frame["policy_name"] = policy_name
    for column in _EVAL_ID_COLUMNS:
        if column in rows.columns:
            frame[column] = rows[column]
    frame["actual_cpu"] = rows["actual_cpu"]
    frame["actual_cpu_unit"] = rows.get("actual_cpu_unit", fc.RESOURCE_UNIT["cpu"])
    frame["actual_memory"] = rows["actual_memory"]
    frame["actual_memory_unit"] = rows.get("actual_memory_unit", fc.RESOURCE_UNIT["memory"])
    frame["recommended_cpu"] = np.nan if cpu_rec is None else np.asarray(cpu_rec, dtype=float)
    frame["recommended_cpu_unit"] = fc.RESOURCE_UNIT["cpu"]
    frame["recommended_memory"] = np.nan if memory_rec is None else np.asarray(memory_rec, dtype=float)
    frame["recommended_memory_unit"] = fc.RESOURCE_UNIT["memory"]
    frame["resource_scope"] = fc.RESOURCE_SCOPE
    frame["recommended_resource_scope"] = fc.RESOURCE_SCOPE
    return frame


def _resource_summary(rows, resource, prediction, evaluator) -> dict[str, float]:
    """Violation % and average shortfall for one resource on available rows."""
    mask = _available_mask(rows, resource)
    subset = rows.loc[mask]
    preds = pd.Series(prediction, index=rows.index).loc[mask]
    cpu_rec = preds.to_numpy() if resource == "cpu" else None
    mem_rec = preds.to_numpy() if resource == "memory" else None
    evaluated = evaluator.evaluate_canonical(_eval_frame(subset, cpu_rec, mem_rec, "ml"))
    summary = evaluator.summarize(evaluated)
    return {
        "violation_pct": summary[f"{resource}_violation_pct"],
        "average_shortfall": summary[f"average_{resource}_shortfall"],
    }


@dataclass(frozen=True)
class ModelSelection:
    resource: str
    selected_model: str
    hyperparameters: dict
    validation_metrics: dict
    n_clipped_validation: int
    selection_order: tuple


def compare_and_select(
    matrices: FeatureMatrices,
    profile: DatasetCapabilities,
    *,
    seed: int = RANDOM_SEED,
):
    """Train every candidate on TRAIN only, score on validation, select per resource.

    Returns (candidate_table, selection_by_resource, train_only_fitted_models).
    """
    evaluator = RecommendationEvaluator(capabilities=profile)
    records: list[dict[str, object]] = []
    selections: dict[str, ModelSelection] = {}
    fitted_by_resource: dict[str, dict[str, object]] = {}

    for resource in RESOURCES:
        target = TARGET_COL[resource]
        train_mask = _available_mask(matrices.train_rows, resource)
        val_mask = _available_mask(matrices.val_rows, resource)

        X_tr = matrices.X_train.loc[train_mask]
        y_tr = matrices.train_rows.loc[train_mask, target].astype(float)
        y_va = matrices.val_rows.loc[val_mask, target].astype(float)

        fitted: dict[str, object] = {}
        resource_records: list[dict[str, object]] = []
        for name, model in build_candidate_models().items():
            model.fit(X_tr, y_tr)
            fitted[name] = model
            pred_all, n_clipped = clip_negative_predictions(model.predict(matrices.X_val))
            pred_available = pd.Series(pred_all, index=matrices.val_rows.index).loc[val_mask]
            reg = _regression_metrics(y_va, pred_available)
            summ = _resource_summary(matrices.val_rows, resource, pred_all, evaluator)
            record = {
                "resource": resource, "model": name,
                "n_train": int(len(y_tr)), "n_val": int(len(y_va)),
                "n_clipped_validation": int(n_clipped),
                **reg, **summ,
            }
            records.append(record)
            resource_records.append(record)

        best = sorted(resource_records, key=lambda r: tuple(r[k] for k in MODEL_SELECTION_ORDER))[0]
        selections[resource] = ModelSelection(
            resource=resource,
            selected_model=best["model"],
            hyperparameters=model_hyperparameters(fitted[best["model"]]),
            validation_metrics={k: best[k] for k in ("mae", "rmse", "r2", "violation_pct", "average_shortfall")},
            n_clipped_validation=int(best["n_clipped_validation"]),
            selection_order=MODEL_SELECTION_ORDER,
        )
        fitted_by_resource[resource] = fitted

    candidate_table = pd.DataFrame(records)
    candidate_table["selected"] = candidate_table.apply(
        lambda r: selections[r["resource"]].selected_model == r["model"], axis=1
    )
    return candidate_table, selections, fitted_by_resource


BASELINE_POLICY_COLUMNS: Mapping[str, tuple[str, str]] = {
    "Request": ("rec_cpu_request", "rec_memory_request"),
    "Mean": ("rec_cpu_mean", "rec_memory_mean"),
    "P90": ("rec_cpu_p90", "rec_memory_p90"),
    "P95": ("rec_cpu_p95", "rec_memory_p95"),
    "P99": ("rec_cpu_p99", "rec_memory_p99"),
}

_VAL_SUMMARY_KEYS = (
    "row_count", "valid_cpu_violation_count", "valid_memory_violation_count",
    "cpu_violation_pct", "memory_violation_pct",
    "average_cpu_utilization", "average_memory_utilization",
    "average_cpu_waste", "average_memory_waste",
    "average_cpu_shortfall", "average_memory_shortfall",
)


@dataclass(frozen=True)
class ValidationHybrid:
    comparison: pd.DataFrame
    ml_predictions: dict
    hybrid_recommendations: dict
    safeguard_missing: dict


def evaluate_validation_policies(
    matrices: FeatureMatrices,
    baselines_validation: pd.DataFrame,
    selections: Mapping[str, ModelSelection],
    fitted_by_resource: Mapping[str, dict],
    profile: DatasetCapabilities,
    *,
    common_population: pd.DataFrame | None = None,
) -> ValidationHybrid:
    """Score Request/Mean/P90/P95/P99/ML/Hybrid on validation.

    ML and Hybrid use predictions from the TRAIN-ONLY selected models (never the
    refit models). Baselines and the Hybrid safeguard come from the Task 6
    validation recommendations, aligned by role_key.
    """
    evaluator = RecommendationEvaluator(capabilities=profile)
    rec_cols = [c for c in baselines_validation.columns if c.startswith(("rec_cpu_", "rec_memory_"))]
    merged = matrices.val_rows.merge(
        baselines_validation[["role_key", *rec_cols]], on="role_key", how="left", validate="one_to_one"
    )
    merged.index = matrices.val_rows.index

    ml_pred: dict[str, np.ndarray] = {}
    hybrid_rec: dict[str, np.ndarray] = {}
    guard_missing: dict[str, np.ndarray] = {}
    for resource in RESOURCES:
        model = fitted_by_resource[resource][selections[resource].selected_model]
        pred, _ = clip_negative_predictions(model.predict(matrices.X_val))
        ml_pred[resource] = pred
        safeguard = merged[HYBRID_SAFEGUARD_COL[resource]].to_numpy(dtype=float)
        hybrid_values, missing = hybrid_recommendation(pred, safeguard)
        hybrid_rec[resource] = hybrid_values
        guard_missing[resource] = missing

    available = (
        merged[fc.CPU_TARGET_STATUS].eq(fc.TARGET_AVAILABLE)
        | merged[fc.MEMORY_TARGET_STATUS].eq(fc.TARGET_AVAILABLE)
    )
    rows = merged.loc[available]
    if common_population is not None:
        rows = rows.loc[rows["role_key"].isin(set(common_population["role_key"]))]
    row_index = rows.index

    def slice_pred(pred: np.ndarray) -> np.ndarray:
        return pd.Series(pred, index=matrices.val_rows.index).loc[row_index].to_numpy()

    records: list[dict[str, object]] = []

    def score(policy_name: str, cpu_rec, mem_rec) -> None:
        evaluated = evaluator.evaluate_canonical(_eval_frame(rows, cpu_rec, mem_rec, policy_name))
        summary = evaluator.summarize(evaluated)
        record = {"policy": policy_name}
        record.update({k: summary.get(k, np.nan) for k in _VAL_SUMMARY_KEYS})
        metadata = evaluator.summary_metadata(evaluated)
        for key in ("cpu_result_semantics", "primary_resource", "any_resource_metric_reported"):
            record[key] = metadata.get(key)
        records.append(record)

    for policy, (cpu_col, mem_col) in BASELINE_POLICY_COLUMNS.items():
        score(policy, rows[cpu_col].to_numpy(dtype=float), rows[mem_col].to_numpy(dtype=float))
    score("ML", slice_pred(ml_pred["cpu"]), slice_pred(ml_pred["memory"]))
    score("Hybrid", slice_pred(hybrid_rec["cpu"]), slice_pred(hybrid_rec["memory"]))

    return ValidationHybrid(
        comparison=pd.DataFrame(records),
        ml_predictions=ml_pred,
        hybrid_recommendations=hybrid_rec,
        safeguard_missing=guard_missing,
    )


def refit_on_train_plus_validation(
    matrices: FeatureMatrices,
    selections: Mapping[str, ModelSelection],
    *,
    seed: int = RANDOM_SEED,
) -> dict:
    """Refit each selected model on train+validation available rows.

    These locked models are for the one-shot final test; validation numbers
    always use the train-only models.
    """
    X_all = pd.concat([matrices.X_train, matrices.X_val], ignore_index=True)
    rows_all = pd.concat([matrices.train_rows, matrices.val_rows], ignore_index=True)
    refit: dict[str, object] = {}
    for resource in RESOURCES:
        mask = _available_mask(rows_all, resource).to_numpy()
        target = rows_all[TARGET_COL[resource]].astype(float).to_numpy()
        model = build_candidate_models()[selections[resource].selected_model]
        model.fit(X_all.loc[mask], target[mask])
        refit[resource] = model
    return refit
