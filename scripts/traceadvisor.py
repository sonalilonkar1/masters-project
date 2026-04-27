# scripts/traceadvisor.py
"""TraceAdvisor command-line tool.

Wraps the subset-06 final recommender outputs so a developer can:

  - look up the recommendation for a specific recurring job
  - view the paper-style ML-Only vs Hybrid metrics table
  - list the most-run recurring jobs in the trace
  - print a one-shot summary of every artifact the pipeline produces

The CLI reads pre-generated artifacts from `data/processed/` and
`reports/eval/subset/`. Files are produced by the subset-06 notebook;
each subcommand prints a clear message when an artifact is missing
instead of crashing.

Usage:
  python scripts/traceadvisor.py recommend --job <recurrence_key>
  python scripts/traceadvisor.py metrics
  python scripts/traceadvisor.py top-jobs --limit 10
  python scripts/traceadvisor.py summary
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "processed"
DEFAULT_TABLES_DIR = REPO_ROOT / "reports" / "eval" / "subset" / "tables"

RECS_FILE = "job_metrics_test_with_final_recommendations_v0.parquet"
TUNING_FILE = "ml_tuning_summary_v0.csv"
CV_FILE = "ml_cv_summary_v0.csv"
FINAL_FILE = "final_recommender_test_v0.csv"
PAPER_FILE = "traceadvisor_cpu_metrics_v0.csv"


# ---------------------------------------------------------------------------
# loaders
# ---------------------------------------------------------------------------

def load_recommendations(data_dir: Path) -> Optional[pd.DataFrame]:
    path = data_dir / RECS_FILE
    if not path.exists():
        print(f"[error] recommendations parquet not found at {path}", file=sys.stderr)
        print("        Run the subset-06 notebook first to produce it.", file=sys.stderr)
        return None
    return pd.read_parquet(path)


def load_csv(tables_dir: Path, name: str) -> Optional[pd.DataFrame]:
    path = tables_dir / name
    if not path.exists():
        print(f"[error] {name} not found at {path}", file=sys.stderr)
        return None
    return pd.read_csv(path)


# ---------------------------------------------------------------------------
# renderers
# ---------------------------------------------------------------------------

def render_recommendation(row: pd.Series) -> str:
    """Format one recommendation row exactly the way the notebook does."""
    based_on = int(row.get("run_count", 0) or 0)
    key = str(row.get("recurrence_key", "<unknown>"))
    key_short = (key[:32] + "…") if len(key) > 33 else key
    p95_cpu = row.get("p95_cpu", float("nan"))
    p95_mem = row.get("p95_mem", float("nan"))
    return (
        f"TraceAdvisor recommendation for job: {key_short}\n"
        f"  Recommended CPU   : {row['rec_cpu']:.4f}    "
        f"(historical p95 = {p95_cpu:.4f})\n"
        f"  Recommended Memory: {row['rec_mem_gb']:.4f} GB "
        f"(historical p95 = {p95_mem:.4f} GB)\n"
        f"  Confidence (CPU/Mem): {row['confidence_cpu']} / {row['confidence_mem']}\n"
        f"  Expected violation risk (CPU/Mem): "
        f"{row['violation_risk_cpu']} / {row['violation_risk_mem']}\n"
        f"  Based on: {based_on} prior runs"
    )


def find_job_row(df: pd.DataFrame, job_query: str) -> Optional[pd.Series]:
    """Match a recurrence_key by exact string or by prefix.

    Picks the row with the highest run_count when several runs of the same
    recurring job are present (the test split is grouped, so duplicates are
    common).
    """
    if "recurrence_key" not in df.columns:
        return None
    keys = df["recurrence_key"].astype(str)
    exact = df[keys == job_query]
    matches = exact if len(exact) else df[keys.str.startswith(job_query)]
    if not len(matches):
        return None
    if "run_count" in matches.columns:
        matches = matches.sort_values("run_count", ascending=False)
    return matches.iloc[0]


# ---------------------------------------------------------------------------
# subcommands
# ---------------------------------------------------------------------------

def cmd_recommend(args: argparse.Namespace) -> int:
    df = load_recommendations(Path(args.data_dir))
    if df is None:
        return 1
    row = find_job_row(df, args.job)
    if row is None:
        print(f"[error] no recurring job matched '{args.job}'", file=sys.stderr)
        print("        Try `traceadvisor top-jobs` to see available keys.", file=sys.stderr)
        return 2
    print(render_recommendation(row))
    return 0


def cmd_metrics(args: argparse.Namespace) -> int:
    df = load_csv(Path(args.tables_dir), PAPER_FILE)
    if df is None:
        return 1
    print("=== TraceAdvisor CPU recommendation metrics (test split) ===\n")
    print(df.to_string(index=False))
    return 0


def cmd_top_jobs(args: argparse.Namespace) -> int:
    df = load_recommendations(Path(args.data_dir))
    if df is None:
        return 1
    if "recurrence_key" not in df.columns:
        print("[error] recommendations file has no recurrence_key column", file=sys.stderr)
        return 1
    cols = [c for c in [
        "recurrence_key", "run_count",
        "rec_cpu", "rec_mem_gb",
        "confidence_cpu", "confidence_mem",
    ] if c in df.columns]
    top = (
        df[cols]
        .drop_duplicates("recurrence_key")
        .sort_values("run_count", ascending=False)
        .head(args.limit)
    ).copy()
    if "recurrence_key" in top.columns:
        top["recurrence_key"] = top["recurrence_key"].astype(str).str[:32] + "…"
    print(f"=== top {args.limit} recurring jobs by run_count ===\n")
    print(top.to_string(index=False))
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    tables_dir = Path(args.tables_dir)
    data_dir = Path(args.data_dir)

    print("=== TraceAdvisor pipeline summary ===\n")

    # tuning
    tuning = load_csv(tables_dir, TUNING_FILE)
    if tuning is not None:
        val = tuning[tuning["split"] == "val"].sort_values("rmse")
        print("Hyperparameter tuning (best per resource on val):")
        for _, r in val.groupby("resource", as_index=False).first().iterrows():
            print(f"  {r['resource']:3s}  {r['model']:13s}  RMSE={r['rmse']:.4f}  R2={r['r2']:.3f}")
        print()

    # cross-validation
    cv = load_csv(tables_dir, CV_FILE)
    if cv is not None:
        print("Cross-validation (mean RMSE ± std):")
        for _, r in cv.iterrows():
            print(f"  {r['model']:35s}  {r['cv']:35s}  "
                  f"{r['mean_rmse']:.4f} ± {r['std_rmse']:.4f}")
        print()

    # final test metrics
    final = load_csv(tables_dir, FINAL_FILE)
    if final is not None:
        print("Final recommender on test split:")
        for _, r in final.iterrows():
            print(f"  {r['resource']:11s}  violation={r['violation_rate']*100:5.1f}%  "
                  f"coverage={r['coverage']*100:5.1f}%  "
                  f"avg_overprov={r['avg_overprovision']:.4f}")
        print()

    # paper-style table
    paper = load_csv(tables_dir, PAPER_FILE)
    if paper is not None:
        print("Paper-style CPU metrics (ML Only vs Hybrid):")
        print(paper.to_string(index=False))
        print()

    # recommendations parquet existence (don't load — could be large)
    recs_path = data_dir / RECS_FILE
    if recs_path.exists():
        size_mb = recs_path.stat().st_size / 1024 / 1024
        print(f"Per-job recommendations parquet: {recs_path}  ({size_mb:.1f} MB)")
    else:
        print(f"Per-job recommendations parquet not found at {recs_path}")
    return 0


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="traceadvisor",
        description="TraceAdvisor CLI — query the subset-06 final recommender outputs.",
    )
    ap.add_argument(
        "--data-dir", default=str(DEFAULT_DATA_DIR),
        help="folder containing the recommendations parquet (default: data/processed)",
    )
    ap.add_argument(
        "--tables-dir", default=str(DEFAULT_TABLES_DIR),
        help="folder containing pipeline summary CSVs",
    )

    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("recommend", help="show recommendation for one recurring job")
    r.add_argument("--job", required=True, help="full or prefix recurrence_key")
    r.set_defaults(func=cmd_recommend)

    m = sub.add_parser("metrics", help="paper-style ML Only vs Hybrid table")
    m.set_defaults(func=cmd_metrics)

    t = sub.add_parser("top-jobs", help="list most-run recurring jobs")
    t.add_argument("--limit", type=int, default=10)
    t.set_defaults(func=cmd_top_jobs)

    s = sub.add_parser("summary", help="overview of all pipeline outputs")
    s.set_defaults(func=cmd_summary)

    return ap


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
