# scripts/report_summary.py
"""
Report generator: reads summary CSVs and prints a comparison table.
Usage: python scripts/report_summary.py --eval_dir reports/eval/GoogleCluster2019 --split 1d
"""
import argparse
import pandas as pd
from pathlib import Path

def main():
    ap = argparse.ArgumentParser(description="TraceAdvisor: Print summary comparison table")
    ap.add_argument("--eval_dir", default="reports/eval/GoogleCluster2019")
    ap.add_argument("--split", default="1d", help="e.g. 1d or 1w")
    args = ap.parse_args()

    path = Path(args.eval_dir) / f"summary_{args.split}.csv"
    if not path.exists():
        print(f"[ERROR] File not found: {path}. Has the team run evaluations yet?")
        return

    df = pd.read_csv(path)
    print(f"\n=== TraceAdvisor Evaluation Summary | Split: {args.split} ===\n")
    
    # Overall rows only
    overall = df[df["tier"] == "all"].copy()
    
    # Select columns that exist in the CSV
    cols = ["method", "n_exec", "vr_any", "vr_cpu", "vr_mem",
            "slack_reduction_cpu_pct", "slack_reduction_mem_pct"]
    cols = [c for c in cols if c in overall.columns]
    
    # Round numbers to 4 decimal places for clean reading
    for c in cols:
        if pd.api.types.is_numeric_dtype(overall[c]):
            overall[c] = overall[c].round(4)
            
    print(overall[cols].to_string(index=False))
    
    print("\n=== By Confidence Tier ===\n")
    tiered = df[df["tier"] != "all"].copy()
    
    for c in cols:
        if pd.api.types.is_numeric_dtype(tiered[c]):
            tiered[c] = tiered[c].round(4)
            
    # Include tier in the column so it's readable
    tiered_cols = ["tier"] + cols
    print(tiered[tiered_cols].to_string(index=False))
    print("\n")

if __name__ == "__main__":
    main()
