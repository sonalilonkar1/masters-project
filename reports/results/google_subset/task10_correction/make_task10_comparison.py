"""Task 10 (#115): before/after comparison and leakage audit for the Google subset.

"Before" is the published record committed in reports/results/google_subset/
(the run whose inputs are hashed in decision_manifest.json). "After" is the
corrected, split-isolated Notebook 04/05 output in data/processed/google_subset_v1/.

The script only reads those files, writes small CSV/JSON outputs next to itself,
and copies the corrected metadata and validation tables. It computes no test
metric. Test target columns are read only to count available targets per split.
Run with the locked environment:

    ~/venvs/traceadvisor-lock/bin/python reports/results/google_subset/task10_correction/make_task10_comparison.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd

OUT_DIR = Path(__file__).resolve().parent
REPO_ROOT = OUT_DIR.parents[3]
PUBLISHED_DIR = REPO_ROOT / "reports" / "results" / "google_subset"
DATA_DIR = REPO_ROOT / "data" / "processed" / "google_subset_v1"

TARGET_TIME_COL = "target_next_occurrence_start_time_us"
TARGET_CPU_COL = "target_cpu_next_occurrence_peak_ncu"
TARGET_MEMORY_COL = "target_memory_next_occurrence_peak_normalized"
NULL_REASON_COL = "target_null_reason"
OTHER_SPLIT = "next_occurrence_in_other_split"
NO_NEXT = "no_next_occurrence"

SPLIT_FILES = {
    "train": "train_occurrences.parquet",
    "validation": "val_occurrences.parquet",
    "test": "test_occurrences.parquet",
}

# Corrected artifacts whose checksums are recorded for this run.
CHECKSUMMED_ARTIFACTS = [
    "train_occurrences.parquet",
    "val_occurrences.parquet",
    "test_occurrences.parquet",
    "train_features.parquet",
    "val_features.parquet",
    "test_features.parquet",
    "metadata.json",
    "baseline_validation_comparison.csv",
    "ml_feature_manifest.json",
    "ml_tuning_results.csv",
    "ml_cv_summary.csv",
    "ml_validation_model_comparison.csv",
    "ml_metadata.json",
    "val_ml_predictions.parquet",
    "test_ml_predictions.parquet",
    "n05_locked_models/cpu_random_forest.joblib",
    "n05_locked_models/memory_random_forest.joblib",
]

# Corrected small files copied next to this script (source -> copy name).
COPIED_ARTIFACTS = {
    "metadata.json": "n04_metadata.json",
    "ml_metadata.json": "n05_ml_metadata.json",
    "baseline_validation_comparison.csv": "baseline_validation_comparison.csv",
    "ml_validation_model_comparison.csv": "ml_validation_model_comparison.csv",
}

BASELINE_METRICS = [
    "valid_any_resource_violation_count",
    "cpu_violation_pct",
    "memory_violation_pct",
    "any_resource_violation_pct",
    "average_cpu_waste",
    "average_memory_waste",
]
SELECTION_SORT = [
    "any_resource_violation_pct",
    "max_resource_violation_pct",
    "sum_resource_violation_pct",
    "average_cpu_waste",
    "average_memory_waste",
    "min_runs",
    "policy",
]
ML_METRICS = ["validation_rows", "mae", "rmse", "r2", "log_rmse", "log_r2"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def rank_baselines(comparison: pd.DataFrame) -> pd.DataFrame:
    """Notebook 04 validation-only selection order (cell 41), unchanged."""
    ranked = comparison.copy()
    ranked["max_resource_violation_pct"] = ranked[
        ["cpu_violation_pct", "memory_violation_pct"]
    ].max(axis=1)
    ranked["sum_resource_violation_pct"] = (
        ranked["cpu_violation_pct"] + ranked["memory_violation_pct"]
    )
    ranked = ranked.sort_values(SELECTION_SORT, kind="mergesort").reset_index(drop=True)
    ranked["selection_rank"] = range(1, len(ranked) + 1)
    return ranked


def baseline_before_after(before: pd.DataFrame, after: pd.DataFrame) -> pd.DataFrame:
    keys = ["min_runs", "policy"]
    rb = rank_baselines(before)[keys + ["selection_rank", "n_common_evaluation_occurrences"] + BASELINE_METRICS]
    ra = rank_baselines(after)[keys + ["selection_rank", "n_common_evaluation_occurrences"] + BASELINE_METRICS]
    merged = rb.merge(ra, on=keys, how="outer", suffixes=("_before", "_after"), validate="one_to_one")
    if merged.isna().any().any() or len(merged) != len(before) or len(merged) != len(after):
        raise RuntimeError("Before and after baseline tables do not cover the same configurations.")
    for metric in ["any_resource_violation_pct", "cpu_violation_pct", "memory_violation_pct"]:
        merged[f"{metric}_change"] = merged[f"{metric}_after"] - merged[f"{metric}_before"]
    return merged.sort_values(["min_runs", "policy"], kind="mergesort").reset_index(drop=True)


def ml_before_after(before: pd.DataFrame, after: pd.DataFrame) -> pd.DataFrame:
    keys = ["resource", "variant", "model", "selectable"]
    merged = before[keys + ML_METRICS].merge(
        after[keys + ML_METRICS], on=keys, how="outer",
        suffixes=("_before", "_after"), validate="one_to_one",
    )
    if merged.isna().any().any():
        raise RuntimeError("Before and after ML comparison tables differ in rows.")
    return merged


def leakage_audit(
    occurrences: dict[str, pd.DataFrame],
    boundaries: dict,
    before_metadata: dict,
    after_metadata: dict,
) -> pd.DataFrame:
    """Changed-row counts derived from the corrected artifacts alone.

    The true next occurrence of each recurrence is recomputed over the three
    splits together (audit only), so each removed target can be attributed to
    the period it came from.
    """
    combined = pd.concat(
        [frame.assign(_split=name) for name, frame in occurrences.items()],
        ignore_index=True,
    ).sort_values(["recurrence_key", "execution_start_time_us"], kind="mergesort")
    combined["_true_next_start"] = combined.groupby("recurrence_key", sort=False)[
        "execution_start_time_us"
    ].shift(-1)

    def period(times: pd.Series) -> pd.Series:
        labels = pd.Series("none", index=times.index, dtype="object")
        labels[times <= boundaries["train_end"]] = "train"
        labels[(times >= boundaries["val_start"]) & (times <= boundaries["val_end"])] = "validation"
        labels[times >= boundaries["test_start"]] = "test"
        labels[times.isna()] = "none"
        return labels

    combined["_true_next_period"] = period(combined["_true_next_start"])

    rows = []
    for split_name in SPLIT_FILES:
        part = combined[combined["_split"] == split_name]
        removed = part[part[NULL_REASON_COL] == OTHER_SPLIT]
        if (removed["_true_next_period"] == split_name).any():
            raise RuntimeError(f"[{split_name}] a removed target came from its own split.")
        both_targets = part[[TARGET_CPU_COL, TARGET_MEMORY_COL]].notna().all(axis=1)
        rows.append(
            {
                "split": split_name,
                "occurrences": len(part),
                "targets_before": int(part["_true_next_start"].notna().sum()),
                "targets_after": int(part[TARGET_TIME_COL].notna().sum()),
                "targets_nulled_cross_split": len(removed),
                "nulled_target_was_in_validation_period": int((removed["_true_next_period"] == "validation").sum()),
                "nulled_target_was_in_test_period": int((removed["_true_next_period"] == "test").sum()),
                "null_no_next_occurrence": int((part[NULL_REASON_COL] == NO_NEXT).sum()),
                "rows_with_both_targets_after": int(both_targets.sum()),
            }
        )
    audit = pd.DataFrame(rows)

    recorded = after_metadata["cross_split_targets_removed"]
    if audit.set_index("split")["targets_nulled_cross_split"].to_dict() != recorded:
        raise RuntimeError("Audit counts disagree with metadata.cross_split_targets_removed.")

    before_population = int(before_metadata["common_validation_population"]["occurrences"])
    after_population = int(after_metadata["common_validation_population"]["occurrences"])
    validation = audit.set_index("split").loc["validation"]
    if int(validation["rows_with_both_targets_after"]) != after_population:
        raise RuntimeError("Validation population in metadata disagrees with the artifact.")
    audit["validation_population_before"] = pd.NA
    audit["validation_population_after"] = pd.NA
    audit["rows_leaving_validation_population"] = pd.NA
    is_validation = audit["split"] == "validation"
    audit.loc[is_validation, "validation_population_before"] = before_population
    audit.loc[is_validation, "validation_population_after"] = after_population
    audit.loc[is_validation, "rows_leaving_validation_population"] = before_population - after_population
    return audit


def main() -> None:
    before_n04 = load_json(PUBLISHED_DIR / "n04_metadata.json")
    before_n05 = load_json(PUBLISHED_DIR / "n05_ml_metadata.json")
    after_n04 = load_json(DATA_DIR / "metadata.json")
    after_n05 = load_json(DATA_DIR / "ml_metadata.json")

    if after_n04.get("target_split_isolation") is not True:
        raise RuntimeError("data/processed/google_subset_v1 is not the split-isolated Task 10 output.")
    if before_n04.get("target_split_isolation") is True:
        raise RuntimeError("The published 'before' metadata is already split-isolated.")
    if before_n04["split_boundaries"] != after_n04["split_boundaries"]:
        raise RuntimeError("Split boundaries changed; the correction must not move them.")

    before_baselines = pd.read_csv(PUBLISHED_DIR / "tables" / "baseline_validation_comparison.csv")
    after_baselines = pd.read_csv(DATA_DIR / "baseline_validation_comparison.csv")
    baselines = baseline_before_after(before_baselines, after_baselines)

    before_ml = pd.read_csv(PUBLISHED_DIR / "tables" / "ml_validation_model_comparison.csv")
    after_ml = pd.read_csv(DATA_DIR / "ml_validation_model_comparison.csv")
    ml = ml_before_after(before_ml, after_ml)

    occurrences = {name: pd.read_parquet(DATA_DIR / file) for name, file in SPLIT_FILES.items()}
    audit = leakage_audit(occurrences, after_n04["split_boundaries"], before_n04, after_n04)

    selected = {
        "before": {
            "policy": before_n04["selected_baseline_policy"],
            "min_runs": before_n04["selected_min_runs"],
            "validation_population": before_n04["common_validation_population"]["occurrences"],
            "metrics": {k: before_n04["selected_validation_metrics"][k] for k in BASELINE_METRICS},
        },
        "after": {
            "policy": after_n04["selected_baseline_policy"],
            "min_runs": after_n04["selected_min_runs"],
            "validation_population": after_n04["common_validation_population"]["occurrences"],
            "metrics": {k: after_n04["selected_validation_metrics"][k] for k in BASELINE_METRICS},
        },
        "ml_selected_models": {"before": before_n05["selected_models"], "after": after_n05["selected_models"]},
        "ml_locked_params_unchanged": before_n05["locked_params"] == after_n05["locked_params"],
        "ml_training_rows": {"before": before_n05["training_rows"], "after": after_n05["training_rows"]},
        "ml_refit_rows": {"before": before_n05["refit"]["rows"], "after": after_n05["refit"]["rows"]},
        "split_boundaries_unchanged": True,
    }

    baselines.to_csv(OUT_DIR / "baseline_validation_before_after.csv", index=False)
    ml.to_csv(OUT_DIR / "ml_validation_before_after.csv", index=False)
    audit.to_csv(OUT_DIR / "leakage_audit.csv", index=False)
    with open(OUT_DIR / "selection_before_after.json", "w", encoding="utf-8") as file:
        json.dump(selected, file, indent=2)
        file.write("\n")

    for source, copy_name in COPIED_ARTIFACTS.items():
        shutil.copyfile(DATA_DIR / source, OUT_DIR / copy_name)

    lines = [f"{sha256(DATA_DIR / name)}  data/processed/google_subset_v1/{name}" for name in CHECKSUMMED_ARTIFACTS]
    (OUT_DIR / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(audit.to_string(index=False))
    print(json.dumps(selected, indent=2))


if __name__ == "__main__":
    main()
