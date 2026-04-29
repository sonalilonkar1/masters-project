"""Unit tests for scripts/traceadvisor.py.

Tests run against synthetic frames written into a tmp_path; they don't need
the real subset-06 parquet/CSV outputs to exist. This means the suite is
runnable on any developer's machine without the Drive data mounted.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import traceadvisor as ta  # noqa: E402


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_recs_df() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "recurrence_key": "alpha-job-key",
            "run_count": 100,
            "rec_cpu": 0.05, "rec_mem_gb": 1.2,
            "p95_cpu": 0.04, "p95_mem": 1.0,
            "confidence_cpu": "High", "confidence_mem": "High",
            "violation_risk_cpu": "Low", "violation_risk_mem": "Low",
        },
        {
            "recurrence_key": "alpha-job-key",  # duplicate row, same job
            "run_count": 100,
            "rec_cpu": 0.05, "rec_mem_gb": 1.2,
            "p95_cpu": 0.04, "p95_mem": 1.0,
            "confidence_cpu": "High", "confidence_mem": "High",
            "violation_risk_cpu": "Low", "violation_risk_mem": "Low",
        },
        {
            "recurrence_key": "beta-job-key",
            "run_count": 7,
            "rec_cpu": 0.001, "rec_mem_gb": 0.05,
            "p95_cpu": 0.0009, "p95_mem": 0.04,
            "confidence_cpu": "Low", "confidence_mem": "Low",
            "violation_risk_cpu": "Medium", "violation_risk_mem": "High",
        },
    ])


@pytest.fixture
def populated_dirs(tmp_path: Path, fake_recs_df: pd.DataFrame):
    data_dir = tmp_path / "data"
    tables_dir = tmp_path / "tables"
    data_dir.mkdir()
    tables_dir.mkdir()

    fake_recs_df.to_parquet(data_dir / ta.RECS_FILE, index=False)

    pd.DataFrame([
        {"resource": "cpu", "model": "RandomForest", "split": "val",
         "best_params": "{}", "mae": 0.003, "rmse": 0.012, "r2": 0.94},
        {"resource": "cpu", "model": "XGBoost", "split": "val",
         "best_params": "{}", "mae": 0.004, "rmse": 0.013, "r2": 0.93},
        {"resource": "mem", "model": "XGBoost", "split": "val",
         "best_params": "{}", "mae": 0.001, "rmse": 0.005, "r2": 0.75},
    ]).to_csv(tables_dir / ta.TUNING_FILE, index=False)

    pd.DataFrame([
        {"model": "X", "cv": "TimeSeriesSplit(5)",
         "mean_rmse": 0.008, "std_rmse": 0.004,
         "min_rmse": 0.003, "max_rmse": 0.015},
    ]).to_csv(tables_dir / ta.CV_FILE, index=False)

    pd.DataFrame([
        {"resource": "cpu", "rows": 100,
         "violation_rate": 0.32, "coverage": 0.68,
         "avg_slack": 0.01, "avg_overprovision": 0.02,
         "avg_underprovision": 0.005, "mae": 0.01},
    ]).to_csv(tables_dir / ta.FINAL_FILE, index=False)

    pd.DataFrame([
        {"Workload": "TraceAdvisor", "Method": "ML Only",
         "Safety (%)": 53.7, "Violation (%)": 46.3,
         "Utilization capped (%)": 80.2, "Utilization median (%)": 98.5},
        {"Workload": "TraceAdvisor", "Method": "Hybrid",
         "Safety (%)": 68.2, "Violation (%)": 31.8,
         "Utilization capped (%)": 56.7, "Utilization median (%)": 61.9},
    ]).to_csv(tables_dir / ta.PAPER_FILE, index=False)

    return data_dir, tables_dir


# ---------------------------------------------------------------------------
# loaders + helpers
# ---------------------------------------------------------------------------

def test_load_recommendations_returns_none_when_missing(tmp_path):
    assert ta.load_recommendations(tmp_path) is None


def test_load_csv_returns_none_when_missing(tmp_path):
    assert ta.load_csv(tmp_path, "does-not-exist.csv") is None


def test_find_job_row_exact_match(fake_recs_df):
    row = ta.find_job_row(fake_recs_df, "beta-job-key")
    assert row is not None
    assert row["recurrence_key"] == "beta-job-key"


def test_find_job_row_prefix_match(fake_recs_df):
    row = ta.find_job_row(fake_recs_df, "alpha-job")
    assert row is not None
    # duplicate alpha rows have run_count=100; pick is deterministic
    assert row["recurrence_key"] == "alpha-job-key"
    assert row["run_count"] == 100


def test_find_job_row_no_match(fake_recs_df):
    assert ta.find_job_row(fake_recs_df, "no-such-job") is None


def test_render_recommendation_includes_all_fields(fake_recs_df):
    out = ta.render_recommendation(fake_recs_df.iloc[0])
    assert "Recommended CPU" in out
    assert "Recommended Memory" in out
    assert "Confidence" in out
    assert "violation risk" in out.lower()
    assert "100 prior runs" in out


def test_render_recommendation_truncates_long_key():
    row = pd.Series({
        "recurrence_key": "x" * 50,
        "run_count": 5,
        "rec_cpu": 0.1, "rec_mem_gb": 0.2,
        "p95_cpu": 0.09, "p95_mem": 0.18,
        "confidence_cpu": "Low", "confidence_mem": "Medium",
        "violation_risk_cpu": "Low", "violation_risk_mem": "Low",
    })
    out = ta.render_recommendation(row)
    assert "…" in out  # ellipsis indicates truncation
    assert "x" * 50 not in out


# ---------------------------------------------------------------------------
# subcommands
# ---------------------------------------------------------------------------

def test_recommend_happy_path(populated_dirs, capsys):
    data_dir, tables_dir = populated_dirs
    rc = ta.main([
        "--data-dir", str(data_dir),
        "--tables-dir", str(tables_dir),
        "recommend", "--job", "alpha-job-key",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "alpha-job-key" in out
    assert "Recommended CPU" in out


def test_recommend_unknown_job(populated_dirs, capsys):
    data_dir, tables_dir = populated_dirs
    rc = ta.main([
        "--data-dir", str(data_dir),
        "--tables-dir", str(tables_dir),
        "recommend", "--job", "zzz",
    ])
    err = capsys.readouterr().err
    assert rc == 2
    assert "no recurring job matched" in err


def test_metrics(populated_dirs, capsys):
    data_dir, tables_dir = populated_dirs
    rc = ta.main([
        "--data-dir", str(data_dir),
        "--tables-dir", str(tables_dir),
        "metrics",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Hybrid" in out
    assert "ML Only" in out


def test_top_jobs_dedupes_and_sorts(populated_dirs, capsys):
    data_dir, tables_dir = populated_dirs
    rc = ta.main([
        "--data-dir", str(data_dir),
        "--tables-dir", str(tables_dir),
        "top-jobs", "--limit", "5",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    # alpha appears twice in the data but should be deduped to one row
    assert out.count("alpha") == 1
    # sorted by run_count desc, alpha (100) printed before beta (7)
    assert out.index("alpha") < out.index("beta")


def test_summary_handles_partial_data(tmp_path, capsys):
    data_dir = tmp_path / "d"
    tables_dir = tmp_path / "t"
    data_dir.mkdir()
    tables_dir.mkdir()
    rc = ta.main([
        "--data-dir", str(data_dir),
        "--tables-dir", str(tables_dir),
        "summary",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "TraceAdvisor pipeline summary" in out


def test_summary_full_output(populated_dirs, capsys):
    data_dir, tables_dir = populated_dirs
    rc = ta.main([
        "--data-dir", str(data_dir),
        "--tables-dir", str(tables_dir),
        "summary",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Hyperparameter tuning" in out
    assert "Cross-validation" in out
    assert "Final recommender on test split" in out
    assert "Paper-style CPU metrics" in out
