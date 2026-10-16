"""Generate the figure and tables used in the Chapters 2-9 report draft.

Every value is read from saved pipeline artifacts; nothing is typed by hand.

Inputs (gitignored, produced by running the pipeline notebooks):
  subset/borg_traces_data.csv                         (header only)
  data/processed/google_subset_v1/
      google_subset_observations_v1.parquet           (Notebook 01)
      google_subset_executions_v1.parquet             (Notebook 02)
      job_profiles_google_subset_history_v1.parquet   (Notebook 03)
      {train,val,test}_occurrences.parquet            (Notebook 04)
      metadata.json, baseline_validation_comparison.csv (Notebook 04)
      ml_metadata.json, ml_validation_model_comparison.csv,
      val_ml_predictions.parquet, test_ml_predictions.parquet
                                                       (Notebook 05, PR #61)

Outputs (docs/report/figures/):
  fig_2_1_pipeline.png
  table_6_1_split_summary.md / .csv
  table_7_1_baseline_validation.md / .csv
  table_5_1_ml_validation.md / .csv
  artifact_values.json   (every number used, for REPORT_TRACEABILITY.md)

Run from the repository root:
  .venv/bin/python docs/report/scripts/make_report_artifacts.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402
import pandas as pd  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "data" / "processed" / "google_subset_v1"
RAW_CSV = REPO / "subset" / "borg_traces_data.csv"
OUT = REPO / "docs" / "report" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

values: dict[str, object] = {}


def md_table(df: pd.DataFrame) -> str:
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(v) for v in row.tolist()) + " |")
    return "\n".join(lines) + "\n"


def fmt_int(x) -> str:
    return f"{int(x):,}"


# ---------------------------------------------------------------------------
# Collect counts
# ---------------------------------------------------------------------------
raw_cols = len(pd.read_csv(RAW_CSV, nrows=0).columns)
obs = pd.read_parquet(DATA / "google_subset_observations_v1.parquet", columns=["observation_id"])
exe = pd.read_parquet(DATA / "google_subset_executions_v1.parquet", columns=["execution_id", "recurrence_key"])
prof = pd.read_parquet(DATA / "job_profiles_google_subset_history_v1.parquet")
meta = json.loads((DATA / "metadata.json").read_text())
ml_meta = json.loads((DATA / "ml_metadata.json").read_text())
splits = {s: pd.read_parquet(DATA / f"{s}_occurrences.parquet") for s in ("train", "val", "test")}
val_pred = pd.read_parquet(DATA / "val_ml_predictions.parquet")
test_pred = pd.read_parquet(DATA / "test_ml_predictions.parquet")

values.update(
    raw_columns=raw_cols,
    observation_rows=len(obs),
    execution_rows=len(exe),
    recurrence_keys=int(exe["recurrence_key"].nunique()),
    occurrences=len(prof),
    cold_start_occurrences=int((prof["prior_occurrence_count"] == 0).sum()),
    occurrences_missing_memory_peak=int(prof["occurrence_peak_memory_normalized"].isna().sum()),
    selected_baseline_policy=meta["selected_baseline_policy"],
    selected_min_runs=meta["selected_min_runs"],
    common_validation_occurrences=meta["common_validation_population"]["occurrences"],
    ml_selected_models=ml_meta["selected_models"],
    val_prediction_rows=len(val_pred),
    test_prediction_rows=len(test_pred),
)

# ---------------------------------------------------------------------------
# Table 6.1: chronological split summary
# ---------------------------------------------------------------------------
sb = meta["split_boundaries"]
rows = []
for name, key, exec_rows, start, end in [
    ("Train", "train", sb["train_rows"], sb["train_start"], sb["train_end"]),
    ("Validation", "val", sb["val_rows"], sb["val_start"], sb["val_end"]),
    ("Test", "test", sb["test_rows"], sb["test_start"], sb["test_end"]),
]:
    d = splits[key]
    cpu_t = d["target_cpu_next_occurrence_peak_ncu"].notna()
    mem_t = d["target_memory_next_occurrence_peak_normalized"].notna()
    rows.append(
        {
            "Split": name,
            "Execution rows": fmt_int(exec_rows),
            "Execution share": f"{exec_rows / sb['total_rows']:.1%}",
            "Occurrences": fmt_int(len(d)),
            "Multi-execution occurrences": fmt_int((d["occurrence_execution_count"] > 1).sum()),
            "With CPU target": fmt_int(cpu_t.sum()),
            "With memory target": fmt_int(mem_t.sum()),
            "First start (s)": f"{start / 1e6:,.0f}",
            "Last start (s)": f"{end / 1e6:,.0f}",
        }
    )
    values[f"split_{key}"] = {k: v for k, v in rows[-1].items()}
t41 = pd.DataFrame(rows)
t41.to_csv(OUT / "table_6_1_split_summary.csv", index=False)
(OUT / "table_6_1_split_summary.md").write_text(md_table(t41))

# ---------------------------------------------------------------------------
# Table 7.1: validation baseline comparison at the selected min_runs
# ---------------------------------------------------------------------------
bvc = pd.read_csv(DATA / "baseline_validation_comparison.csv")
sel = bvc[bvc["min_runs"] == meta["selected_min_runs"]].copy()
order = ["Request", "Mean", "P90", "P95", "P99"]
sel["policy"] = pd.Categorical(sel["policy"], order, ordered=True)
sel = sel.sort_values("policy")
t71 = pd.DataFrame(
    {
        "Policy": sel["policy"].astype(str),
        "CPU viol. %": sel["cpu_violation_pct"].map("{:.2f}".format),
        "Mem. viol. %": sel["memory_violation_pct"].map("{:.2f}".format),
        "Any-resource viol. %": sel["any_resource_violation_pct"].map("{:.2f}".format),
        "Valid n (any)": sel["valid_any_resource_violation_count"].astype(int),
        "Avg CPU util.": sel["average_cpu_utilization"].map("{:.3f}".format),
        "Avg mem. util.": sel["average_memory_utilization"].map("{:.3f}".format),
        "Avg CPU waste (NCU)": sel["average_cpu_waste"].map("{:.3f}".format),
        "Avg mem. waste": sel["average_memory_waste"].map("{:.3f}".format),
        "Avg CPU shortfall (NCU)": sel["average_cpu_shortfall"].map("{:.3f}".format),
        "Avg mem. shortfall": sel["average_memory_shortfall"].map("{:.3f}".format),
    }
)
t71.to_csv(OUT / "table_7_1_baseline_validation.csv", index=False)
(OUT / "table_7_1_baseline_validation.md").write_text(md_table(t71))
values["table_7_1"] = t71.to_dict(orient="records")

# Any-resource violation by policy and min_runs (used in prose, Section 7.1.1)
pivot = bvc.pivot(index="policy", columns="min_runs", values="any_resource_violation_pct").loc[order]
values["any_violation_by_min_runs"] = pivot.round(2).to_dict()

# ---------------------------------------------------------------------------
# Table 5.1: ML validation model comparison (Notebook 05, PR #61)
# ---------------------------------------------------------------------------
mvc = pd.read_csv(DATA / "ml_validation_model_comparison.csv")
name_map = {
    "decision_tree": "Decision Tree",
    "random_forest": "Random Forest",
    "xgboost": "XGBoost",
    "reference_median": "Median reference",
}
var_order = {"tuned": 0, "starting": 1, "reference": 2}
mvc = mvc.assign(_v=mvc["variant"].map(var_order)).sort_values(["resource", "_v", "model"])
t72 = pd.DataFrame(
    {
        "Resource": mvc["resource"].str.upper().str.replace("MEMORY", "Memory"),
        "Variant": mvc["variant"],
        "Model": mvc["model"].map(name_map),
        "Selectable": mvc["selectable"].map({True: "yes", False: "no"}),
        "Train rows": mvc["training_rows"],
        "Val. rows": mvc["validation_rows"],
        "MAE": mvc["mae"].map("{:.3f}".format),
        "RMSE": mvc["rmse"].map("{:.3f}".format),
        "R²": mvc["r2"].map("{:.3f}".format),
        "log1p RMSE": mvc["log_rmse"].map("{:.3f}".format),
        "log1p R²": mvc["log_r2"].map("{:.3f}".format),
    }
)
t72.to_csv(OUT / "table_5_1_ml_validation.csv", index=False)
(OUT / "table_5_1_ml_validation.md").write_text(md_table(t72))
values["table_5_1"] = t72.to_dict(orient="records")

cv = pd.read_csv(DATA / "ml_cv_summary.csv")
values["ml_cv_summary"] = cv.round(3).to_dict(orient="records")
values["ml_refit_rows"] = ml_meta["refit"]["rows"]
values["ml_training_rows"] = ml_meta["training_rows"]
values["ml_versions"] = ml_meta["versions"]

# ---------------------------------------------------------------------------
# Figure 2.1: pipeline / data-flow diagram with real counts
# ---------------------------------------------------------------------------
INK, MUTED, BLUE = "#0b0b0b", "#52514e", "#2a78d6"
fig, ax = plt.subplots(figsize=(7.0, 8.6), dpi=200)
ax.set_xlim(0, 100)
ax.set_ylim(0, 112)
ax.axis("off")

stages = [
    ("Raw input: Kaggle sample of Google ClusterData 2019",
     f"subset/borg_traces_data.csv  |  {len(obs):,} rows x {raw_cols} columns", "done"),
    ("N00  Data quality review",
     "audits only; no artifact written", "done"),
    ("N01  Ingestion",
     f"{len(obs):,} machine/time-window observations (no rows dropped)", "done"),
    ("N02  Execution reconstruction",
     f"{len(exe):,} executions  |  {exe['recurrence_key'].nunique():,} recurrence keys", "done"),
    ("N03  Occurrences and point-in-time history",
     f"{len(prof):,} full-workload occurrences  |  completed-occurrence profiles", "done"),
    ("N04  Chronological split, targets, baselines",
     f"{len(splits['train']):,} train / {len(splits['val']):,} val. / {len(splits['test']):,} test occurrences  |  "
     f"{meta['selected_baseline_policy']}, min_runs = {meta['selected_min_runs']} (validation)", "done"),
    ("N05  ML tuning, model lock, predictions  [PR #61, in review]",
     f"Random Forest (CPU, memory)  |  {len(val_pred):,} validation / {len(test_pred):,} test prediction rows", "review"),
    ("N06  Hybrid and all-policy comparison  [planned]",
     "Request, Mean, P90, P95, P99, ML-only, Hybrid  |  results: Issue 12", "planned"),
]

box_h, gap, x0, w = 9.6, 3.6, 2, 66
y = 108
centers = []
for title, sub, status in stages:
    y_bottom = y - box_h
    style = {"done": ("-", INK, 1.2), "review": ("--", INK, 1.2), "planned": (":", MUTED, 1.2)}[status]
    patch = FancyBboxPatch((x0, y_bottom), w, box_h, boxstyle="round,pad=0.3,rounding_size=1.2",
                           linewidth=style[2], linestyle=style[0], edgecolor=style[1], facecolor="white")
    ax.add_patch(patch)
    ax.text(x0 + 2, y_bottom + box_h * 0.66, title, fontsize=7.2, fontweight="bold",
            color=INK if status != "planned" else MUTED, va="center")
    ax.text(x0 + 2, y_bottom + box_h * 0.28, sub, fontsize=6.0, color=MUTED, va="center")
    centers.append((x0 + w / 2, y, y_bottom))
    y = y_bottom - gap

for (cx, _, yb), (_, yt, _) in zip(centers[:-1], centers[1:]):
    ax.add_patch(FancyArrowPatch((cx, yb - 0.4), (cx, yt + 0.4), arrowstyle="-|>", mutation_scale=8,
                                 color=MUTED, linewidth=0.9))

# Shared evaluator side box (used by N04 and N05; planned for N06)
ev_x, ev_w = 78, 21
ev_top = centers[5][1]
ev_bottom = centers[7][2]
ax.add_patch(FancyBboxPatch((ev_x, ev_bottom), ev_w, ev_top - ev_bottom, boxstyle="round,pad=0.3,rounding_size=1.2",
                            linewidth=1.2, edgecolor=BLUE, facecolor="white"))
ax.text(ev_x + ev_w / 2, (ev_top + ev_bottom) / 2,
        "Shared evaluator\nsrc/evaluation/\n(metrics.py,\nevaluator.py)\n\nviolation,\nbounded utilization,\nwaste, shortfall,\nvalid denominators",
        fontsize=6.3, color=INK, ha="center", va="center", linespacing=1.25)
for i in (5, 6, 7):
    cy = (centers[i][1] + centers[i][2]) / 2
    ax.add_patch(FancyArrowPatch((x0 + w + 0.6, cy), (ev_x - 0.6, cy), arrowstyle="<|-|>", mutation_scale=7,
                                 color=BLUE, linewidth=0.8, linestyle="-" if i < 7 else ":"))

# Legend for line styles (status is encoded by line style AND by bracketed text)
ly = 2.2
for label, ls, col, lx in [("implemented on main", "-", INK, 2), ("open PR, in review", "--", INK, 32),
                           ("planned", ":", MUTED, 62)]:
    ax.plot([lx, lx + 6], [ly, ly], linestyle=ls, color=col, linewidth=1.2)
    ax.text(lx + 7.5, ly, label, fontsize=6.6, color=MUTED, va="center")

fig.savefig(OUT / "fig_2_1_pipeline.png", bbox_inches="tight", facecolor="white")
plt.close(fig)

(OUT / "artifact_values.json").write_text(json.dumps(values, indent=2, default=str))
print(json.dumps(values, indent=2, default=str))
