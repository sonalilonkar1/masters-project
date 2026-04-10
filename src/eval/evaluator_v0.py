# src/eval/evaluator_v0.py

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from src.baselines.baseline1_percentile_margin import Baseline1PercentileMargin


@dataclass
class EvalResult:
    method: str
    split: str
    tier: str
    n_exec: int
    vr_cpu: float
    vr_mem: float
    vr_any: float
    waste_cpu: float
    waste_mem: float
    slack_reduction_cpu_pct: float
    slack_reduction_mem_pct: float


def compute_metrics(df: pd.DataFrame, rec_cpu: pd.Series, rec_mem: pd.Series) -> Dict[str, float]:
    # violations
    viol_cpu = (df["peak_cpu"] > rec_cpu).astype(int)
    viol_mem = (df["peak_mem"] > rec_mem).astype(int)
    viol_any = ((viol_cpu == 1) | (viol_mem == 1)).astype(int)

    # waste (positive slack)
    waste_cpu = np.maximum(0.0, rec_cpu.to_numpy() - df["peak_cpu"].to_numpy()).sum()
    waste_mem = np.maximum(0.0, rec_mem.to_numpy() - df["peak_mem"].to_numpy()).sum()

    return {
        "n_exec": int(len(df)),
        "vr_cpu": float(viol_cpu.mean()) if len(df) else 0.0,
        "vr_mem": float(viol_mem.mean()) if len(df) else 0.0,
        "vr_any": float(viol_any.mean()) if len(df) else 0.0,
        "waste_cpu": float(waste_cpu),
        "waste_mem": float(waste_mem),
    }


def assign_tier(n_hist: pd.Series) -> pd.Series:
    # confidence tiers based on history count (train-based)
    # high: >=10, medium: 3-9, low: <=2
    def _tier(x: int) -> str:
        if x >= 10:
            return "high"
        if x >= 3:
            return "medium"
        return "low"

    return n_hist.apply(lambda x: _tier(int(x)))


def load_parquet(input_path: str) -> pd.DataFrame:
    if input_path.startswith("gs://"):
        return pd.read_parquet(input_path)
    return pd.read_parquet(input_path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Parquet input path (e.g., gs://.../1d_jobmetrics/)")
    ap.add_argument("--split", required=True, help="Split label for outputs (e.g., 1d, 1w)")
    ap.add_argument("--out_dir", default="reports/eval", help="Output directory")
    ap.add_argument("--split_ratio", type=float, default=0.7, help="Train/test ratio by time (default 0.7)")
    ap.add_argument("--min_history", type=int, default=3, help="Min history for quantile estimates")
    ap.add_argument("--methods", default="baseline0,baseline1_p95,baseline1_p99",
                    help="Comma-separated: baseline0,baseline1_p95,baseline1_p99")
    ap.add_argument("--margin_cpu", type=float, default=0.0, help="Additive CPU margin for baseline1")
    ap.add_argument("--margin_mem", type=float, default=0.0, help="Additive MEM margin for baseline1")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    df = load_parquet(args.input)

    required = {
        "recurring_job_id", "collection_id", "instance_index",
        "start_time", "end_time",
        "req_cpu", "req_mem", "peak_cpu", "peak_mem",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Input missing required columns: {sorted(missing)}")

    # Clean + derive execution_id
    df = df.copy()
    df["execution_id"] = df["collection_id"].astype(str) + "_" + df["instance_index"].astype(str)

    # Filter to valid rows (important)
    df = df.dropna(subset=["start_time", "end_time", "req_cpu", "req_mem", "peak_cpu", "peak_mem"])
    df = df.sort_values("start_time").reset_index(drop=True)

    # Time-aware split
    min_t = int(df["start_time"].min())
    max_t = int(df["start_time"].max())
    split_t = int(min_t + args.split_ratio * (max_t - min_t))

    train = df[df["start_time"] < split_t].copy()
    test = df[df["start_time"] >= split_t].copy()

    methods = [m.strip() for m in args.methods.split(",") if m.strip()]

    summary_rows: List[EvalResult] = []

    # Baseline0 reference waste for slack reduction
    base0_rec_cpu = test["req_cpu"]
    base0_rec_mem = test["req_mem"]
    base0_metrics = compute_metrics(test, base0_rec_cpu, base0_rec_mem)
    base0_waste_cpu = base0_metrics["waste_cpu"]
    base0_waste_mem = base0_metrics["waste_mem"]

    def slack_reduction(base: float, cur: float) -> float:
        return float(100.0 * (base - cur) / (base + 1e-9))

    # Helper to write per-exec
    def write_per_exec(method_name: str, df_eval: pd.DataFrame, rec_cpu: pd.Series, rec_mem: pd.Series,
                       tier: Optional[pd.Series] = None) -> None:
        out = df_eval[[
            "execution_id", "recurring_job_id", "start_time",
            "req_cpu", "req_mem", "peak_cpu", "peak_mem"
        ]].copy()
        out = out.rename(columns={"start_time": "timestamp"})
        out["rec_cpu"] = rec_cpu.values
        out["rec_mem"] = rec_mem.values
        
        # Slack and waste calculations (aligned to v0 spec)
        out["slack_req_cpu"] = out["req_cpu"] - out["peak_cpu"]
        out["slack_req_mem"] = out["req_mem"] - out["peak_mem"]
        out["slack_rec_cpu"] = out["rec_cpu"] - out["peak_cpu"]
        out["slack_rec_mem"] = out["rec_mem"] - out["peak_mem"]
        out["waste_req_cpu"] = np.maximum(0.0, out["slack_req_cpu"])
        out["waste_req_mem"] = np.maximum(0.0, out["slack_req_mem"])
        out["waste_rec_cpu"] = np.maximum(0.0, out["slack_rec_cpu"])
        out["waste_rec_mem"] = np.maximum(0.0, out["slack_rec_mem"])
        
        # Violations and under-provisioning
        out["viol_cpu"] = (out["peak_cpu"] > out["rec_cpu"]).astype(int)
        out["viol_mem"] = (out["peak_mem"] > out["rec_mem"]).astype(int)
        out["viol_any"] = ((out["viol_cpu"] == 1) | (out["viol_mem"] == 1)).astype(int)
        out["under_prov_cpu"] = np.maximum(0.0, out["peak_cpu"] - out["rec_cpu"])
        out["under_prov_mem"] = np.maximum(0.0, out["peak_mem"] - out["rec_mem"])
        
        # Confidence tier
        if tier is not None:
            out["confidence_tier"] = tier.values
        else:
            out["confidence_tier"] = "all"

        out_path = os.path.join(args.out_dir, f"per_execution_{method_name}_{args.split}.csv")
        out.to_csv(out_path, index=False)

    # Run requested methods
    for method in methods:
        if method == "baseline0":
            rec_cpu = test["req_cpu"]
            rec_mem = test["req_mem"]
            metrics = compute_metrics(test, rec_cpu, rec_mem)

            write_per_exec("baseline0_as_is", test, rec_cpu, rec_mem)

            summary_rows.append(EvalResult(
                method="baseline0_as_is",
                split=args.split,
                tier="all",
                n_exec=int(metrics["n_exec"]),
                vr_cpu=metrics["vr_cpu"],
                vr_mem=metrics["vr_mem"],
                vr_any=metrics["vr_any"],
                waste_cpu=metrics["waste_cpu"],
                waste_mem=metrics["waste_mem"],
                slack_reduction_cpu_pct=0.0,  # baseline reference
                slack_reduction_mem_pct=0.0,
            ))

        elif method in ("baseline1_p95", "baseline1_p99"):
            q = 0.95 if method.endswith("p95") else 0.99
            model = Baseline1PercentileMargin().fit(train, q=q, min_history=args.min_history)
            rec_cpu, rec_mem, n_hist = model.predict(test, margin_cpu=args.margin_cpu, margin_mem=args.margin_mem)
            metrics = compute_metrics(test, rec_cpu, rec_mem)

            tier = assign_tier(n_hist)
            write_per_exec(method, test, rec_cpu, rec_mem, tier=tier)

            summary_rows.append(EvalResult(
                method=method,
                split=args.split,
                tier="all",
                n_exec=int(metrics["n_exec"]),
                vr_cpu=metrics["vr_cpu"],
                vr_mem=metrics["vr_mem"],
                vr_any=metrics["vr_any"],
                waste_cpu=metrics["waste_cpu"],
                waste_mem=metrics["waste_mem"],
                slack_reduction_cpu_pct=slack_reduction(base0_waste_cpu, metrics["waste_cpu"]),
                slack_reduction_mem_pct=slack_reduction(base0_waste_mem, metrics["waste_mem"]),
            ))

            # Tiered summary rows (high/medium/low)
            for tier_name in ["high", "medium", "low"]:
                mask = (tier == tier_name)
                if not mask.any():
                    continue
                m = compute_metrics(test.loc[mask], rec_cpu.loc[mask], rec_mem.loc[mask])
                
                # Compute baseline0 waste for the same tier subset for fair comparison
                base0_tier_waste_cpu = np.maximum(0.0, test.loc[mask, "req_cpu"] - test.loc[mask, "peak_cpu"]).sum()
                base0_tier_waste_mem = np.maximum(0.0, test.loc[mask, "req_mem"] - test.loc[mask, "peak_mem"]).sum()
                
                summary_rows.append(EvalResult(
                    method=method,
                    split=args.split,
                    tier=tier_name,
                    n_exec=int(m["n_exec"]),
                    vr_cpu=m["vr_cpu"],
                    vr_mem=m["vr_mem"],
                    vr_any=m["vr_any"],
                    waste_cpu=m["waste_cpu"],
                    waste_mem=m["waste_mem"],
                    slack_reduction_cpu_pct=slack_reduction(base0_tier_waste_cpu, m["waste_cpu"]),
                    slack_reduction_mem_pct=slack_reduction(base0_tier_waste_mem, m["waste_mem"]),
                ))
        else:
            raise ValueError(f"Unknown method: {method}")

    # Write summary CSV
    summary_df = pd.DataFrame([r.__dict__ for r in summary_rows])
    summary_path = os.path.join(args.out_dir, f"summary_{args.split}.csv")
    summary_df.to_csv(summary_path, index=False)

    print(f"Saved per-exec + summary to: {args.out_dir}")
    print(f"Split boundary used (start_time): {split_t}")
    print(summary_df)


if __name__ == "__main__":
    main()