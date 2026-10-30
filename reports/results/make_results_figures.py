#!/usr/bin/env python3
"""Regenerate the results figures from the committed CSVs in reports/results/.

Reads only files in this folder (no data/processed inputs), so the figures can
be rebuilt from a fresh checkout:

    ~/venvs/traceadvisor-lock/bin/python reports/results/make_results_figures.py

Writes PNGs to reports/results/alibaba_gpu_2020/figures/ and
reports/results/google_subset/figures/.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ALIBABA = HERE / "alibaba_gpu_2020"
GOOGLE = HERE / "google_subset"

CORE_POLICIES = ["Request", "Mean", "P90", "P95", "P99", "ML", "Hybrid"]
HISTORY_POLICIES = ["Mean", "P90", "P95", "P99"]
COLORS = {
    "Request": "#7f7f7f", "Mean": "#bcbd22", "P90": "#9ecae1", "P95": "#4292c6",
    "P99": "#08519c", "ML": "#ff7f0e", "Hybrid": "#d62728",
}
DPI = 200

# Label offsets (points) for markers that would otherwise overlap.
ML_LABEL_OFFSETS = {
    "memory": {"hist_gradient_boosting": (0, -14), "xgboost": (6, 5), "random_forest": (8, -4),
               "decision_tree": (6, 4), "dummy_mean": (-6, 6)},
    "cpu": {"hist_gradient_boosting": (6, -10), "xgboost": (6, 3), "random_forest": (-6, 6),
            "decision_tree": (6, 4), "dummy_mean": (-6, 6)},
}

plt.rcParams.update({
    "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
    "axes.spines.top": False, "axes.spines.right": False,
})


def _save(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=DPI, facecolor="white")
    plt.close(fig)
    print(f"wrote {path.relative_to(HERE.parents[1])}")


def _tradeoff_panel(ax, frame, waste_col, viol_col, title, xlabel, ylabel, offsets=None):
    offsets = offsets or {}
    for _, row in frame.iterrows():
        policy = row["policy"]
        ax.scatter(row[waste_col], row[viol_col], s=55, color=COLORS[policy],
                   edgecolor="black", linewidth=0.5, zorder=3)
        dx, dy = offsets.get(policy, (6, 4))
        ax.annotate(policy, (row[waste_col], row[viol_col]), textcoords="offset points",
                    xytext=(dx, dy), fontsize=8, ha=_ha(dx))
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_ylim(0, frame[viol_col].max() * 1.12)
    ax.set_xlim(left=0)
    ax.grid(alpha=0.3)


def _ha(dx):
    return "center" if dx == 0 else ("right" if dx < 0 else "left")


def _candidate_lines(ax, frame, waste_col, viol_col, selected):
    for policy in HISTORY_POLICIES:
        sub = frame[frame["policy"] == policy].sort_values("min_runs")
        ax.plot(sub[waste_col], sub[viol_col], marker="o", ms=4, color=COLORS[policy], label=policy)
        for _, row in sub[sub["min_runs"].isin([sub["min_runs"].min(), sub["min_runs"].max()])].iterrows():
            ax.annotate(str(int(row["min_runs"])), (row[waste_col], row[viol_col]),
                        textcoords="offset points", xytext=(4, 4), fontsize=6, color="#444444")
    request = frame[frame["policy"] == "Request"].iloc[0]
    ax.scatter(request[waste_col], request[viol_col], marker="s", s=45, color=COLORS["Request"],
               edgecolor="black", linewidth=0.5, label="Request", zorder=3)
    sel = frame[(frame["policy"] == selected[0]) & (frame["min_runs"] == selected[1])].iloc[0]
    ax.scatter(sel[waste_col], sel[viol_col], s=160, facecolor="none", edgecolor="#d62728",
               linewidth=1.5, zorder=4, label=f"Selected: {selected[0]}, min_runs = {selected[1]}")
    ax.set_ylim(bottom=0)
    ax.set_xlim(left=0)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, frameon=False)


def _val_vs_test(ax, val, test, col, title):
    x = np.arange(len(CORE_POLICIES))
    v = val.set_index("policy").loc[CORE_POLICIES, col]
    t = test.set_index("policy").loc[CORE_POLICIES, col]
    ax.bar(x - 0.2, v, 0.4, label="Validation", color="#c6dbef", edgecolor="black", linewidth=0.4)
    ax.bar(x + 0.2, t, 0.4, label="Final test", color="#2171b5", edgecolor="black", linewidth=0.4)
    for i, value in enumerate(t):
        ax.annotate(f"{value:.1f}", (x[i] + 0.2, value), textcoords="offset points",
                    xytext=(0, 2), ha="center", fontsize=6)
    ax.set_xticks(x, CORE_POLICIES)
    ax.set_ylabel("Violation rate (%)")
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.3)
    ax.legend(fontsize=7, frameon=False)


def alibaba_figures() -> None:
    out = ALIBABA / "figures"
    test = pd.read_csv(ALIBABA / "final_test/final_test_policy_comparison.csv")
    val = pd.read_csv(ALIBABA / "ml/validation_policy_comparison.csv")
    baselines = pd.read_csv(ALIBABA / "baselines/validation_comparison.csv")
    candidates = pd.read_csv(ALIBABA / "ml/candidate_models.csv")

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8))
    _tradeoff_panel(axes[0], test, "average_memory_waste", "memory_violation_pct",
                    "Memory (primary resource)", "Average memory waste (GB)", "Memory violation rate (%)",
                    offsets={"P99": (-8, -10), "Hybrid": (8, -10), "P95": (-8, 2), "P90": (-8, 2)})
    _tradeoff_panel(axes[1], test, "average_cpu_waste", "cpu_violation_pct",
                    "CPU (lifetime-average usage)", "Average CPU waste (% of vCPU)", "CPU violation rate (%)")
    fig.suptitle("Alibaba GPU 2020, final test (44,053 rows): violation rate against waste", fontsize=10)
    _save(fig, out / "fig_alibaba_test_tradeoff.png")

    fig, ax = plt.subplots(figsize=(6, 4))
    _candidate_lines(ax, baselines, "average_memory_waste", "memory_violation_pct", ("P99", 10))
    ax.set_xlabel("Average memory waste (GB)")
    ax.set_ylabel("Memory violation rate (%)")
    ax.set_title("Alibaba GPU 2020, validation: baseline candidates (labels = min_runs)")
    _save(fig, out / "fig_alibaba_baseline_candidates.png")

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8))
    labels = {"dummy_mean": "Dummy (mean)", "decision_tree": "Decision tree", "random_forest": "Random forest",
              "hist_gradient_boosting": "HistGB", "xgboost": "XGBoost"}
    for ax, resource, unit in ((axes[0], "memory", "GB"), (axes[1], "cpu", "% of vCPU")):
        sub = candidates[candidates["resource"] == resource]
        offsets = ML_LABEL_OFFSETS[resource]
        for _, row in sub.iterrows():
            color = "#d62728" if row["selected"] else ("#7f7f7f" if row["model"] == "dummy_mean" else "#2171b5")
            ax.scatter(row["rmse"], row["violation_pct"], s=55, color=color, edgecolor="black", linewidth=0.5, zorder=3)
            dx, dy = offsets.get(row["model"], (6, 3))
            ax.annotate(labels[row["model"]] + (" (selected)" if row["selected"] else ""),
                        (row["rmse"], row["violation_pct"]), textcoords="offset points", xytext=(dx, dy),
                        fontsize=7, ha=_ha(dx))
        ax.set_xlabel(f"Validation RMSE ({unit})")
        ax.set_ylabel("ML-only violation rate (%)")
        ax.set_title("Memory" if resource == "memory" else "CPU")
        ax.set_ylim(0, 65)
        ax.grid(alpha=0.3)
    fig.suptitle("Alibaba GPU 2020, validation: ML candidates, accuracy against violation rate", fontsize=10)
    _save(fig, out / "fig_alibaba_ml_candidates.png")

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    _val_vs_test(axes[0], val, test, "memory_violation_pct", "Memory violation rate")
    _val_vs_test(axes[1], val, test, "cpu_violation_pct", "CPU violation rate")
    fig.suptitle("Alibaba GPU 2020: validation (42,069 rows) and final test (44,053 rows)", fontsize=10)
    _save(fig, out / "fig_alibaba_val_vs_test.png")


def google_figures() -> None:
    out = GOOGLE / "figures"
    test = pd.read_csv(GOOGLE / "tables/final_test_policy_comparison.csv")
    val = pd.read_csv(GOOGLE / "tables/validation_policy_comparison.csv")
    val = val[~val["supplementary"]]
    baselines = pd.read_csv(GOOGLE / "tables/baseline_validation_comparison.csv")

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8))
    _tradeoff_panel(axes[0], test, "average_cpu_waste", "cpu_violation_pct",
                    "CPU", "Average CPU waste (normalized units)", "CPU violation rate (%)")
    _tradeoff_panel(axes[1], test, "average_memory_waste", "memory_violation_pct",
                    "Memory", "Average memory waste (normalized units)", "Memory violation rate (%)",
                    offsets={"Request": (6, 5), "Mean": (6, -10)})
    fig.suptitle("Google ClusterData 2019 subset, final test (259 occurrences): violation rate against waste", fontsize=10)
    _save(fig, out / "fig_google_test_tradeoff.png")

    fig, ax = plt.subplots(figsize=(6, 4))
    _candidate_lines(ax, baselines, "average_cpu_waste", "any_resource_violation_pct", ("P99", 1))
    ax.set_xlabel("Average CPU waste (normalized units)")
    ax.set_ylabel("Any-resource violation rate (%)")
    ax.set_title("Google subset, validation: baseline candidates (labels = min_runs)")
    _save(fig, out / "fig_google_baseline_candidates.png")

    fig, ax = plt.subplots(figsize=(6, 3.6))
    _val_vs_test(ax, val, test, "any_resource_violation_pct", "Google subset: any-resource violation rate")
    _save(fig, out / "fig_google_val_vs_test.png")


if __name__ == "__main__":
    alibaba_figures()
    google_figures()
