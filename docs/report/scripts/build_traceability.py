"""Build docs/report/REPORT_TRACEABILITY.md and verify every claim.

Each claim records:
  - the exact text as it appears in the report Markdown (checked: must be present);
  - its source; and
  - an automatic check against that source when possible:
      art   - value recomputed from a saved artifact in data/processed/google_subset_v1/
      nbout - substring of a notebook's saved outputs (main, or a PR branch via git)
      file  - substring of a repository file (main, or a PR branch via git)
      pdf   - backlog PDF page (not in the repository): checked manually, marked "manual"
      run   - command run for this draft (recorded, not re-run)

Run from the repository root:
  .venv/bin/python docs/report/scripts/build_traceability.py
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "data" / "processed" / "google_subset_v1"
REPORT_MD = REPO / "docs" / "report" / "TraceAdvisor_295B_Final_Report_Ch2-9_DRAFT.md"
OUT = REPO / "docs" / "report" / "REPORT_TRACEABILITY.md"
PR61 = "origin/feature/google-subset-n05-ml-eval"
PR70 = None  # PR #70 is merged; its files are read from the working tree (main, a0b3c77)
NB = "pipelines/google_subset/"


def read_file(path: str, ref: str | None = None) -> str:
    if ref:
        return subprocess.run(["git", "show", f"{ref}:{path}"], cwd=REPO, capture_output=True,
                              text=True, check=True).stdout
    return (REPO / path).read_text()


def nb_outputs(path: str, ref: str | None = None) -> str:
    nb = json.loads(read_file(path, ref))
    chunks = []
    for cell in nb["cells"]:
        chunks.append("".join(cell.get("source", "")))
        for o in cell.get("outputs", []):
            if "text" in o:
                chunks.append("".join(o["text"]))
            elif "data" in o and "text/plain" in o["data"]:
                chunks.append("".join(o["data"]["text/plain"]))
    return re.sub(r"\s+", " ", "\n".join(chunks))


report = REPORT_MD.read_text()
report_flat = re.sub(r"\s+", " ", report)

# ---- artifacts -----------------------------------------------------------
meta = json.loads((DATA / "metadata.json").read_text())
ml_meta = json.loads((DATA / "ml_metadata.json").read_text())
manifest = json.loads((DATA / "ml_feature_manifest.json").read_text())
exe = pd.read_parquet(DATA / "google_subset_executions_v1.parquet",
                      columns=["execution_id", "episode_number", "recurrence_key"])
prof = pd.read_parquet(DATA / "job_profiles_google_subset_history_v1.parquet")
occ = {s: pd.read_parquet(DATA / f"{s}_occurrences.parquet") for s in ("train", "val", "test")}
bvc = pd.read_csv(DATA / "baseline_validation_comparison.csv")
mvc = pd.read_csv(DATA / "ml_validation_model_comparison.csv")
cv = pd.read_csv(DATA / "ml_cv_summary.csv")
test_pred = pd.read_parquet(DATA / "test_ml_predictions.parquet")
val_pred = pd.read_parquet(DATA / "val_ml_predictions.parquet")
raw_cols = len(pd.read_csv(REPO / "subset" / "borg_traces_data.csv", nrows=0).columns)


def b(policy, min_runs, col):
    return bvc[(bvc.policy == policy) & (bvc.min_runs == min_runs)][col].iloc[0]


def m(resource, variant, model, col):
    return mvc[(mvc.resource == resource) & (mvc.variant == variant) & (mvc.model == model)][col].iloc[0]


def c(resource, model, col):
    return cv[(cv.resource == resource) & (cv.model == model)][col].iloc[0]


val = occ["val"]
both_val = val.target_cpu_next_occurrence_peak_ncu.notna() & val.target_memory_next_occurrence_peak_normalized.notna()
ep = exe.episode_number.value_counts()
per_key = exe.groupby("recurrence_key").size()
occ_per_key = prof.groupby("recurrence_key").size()
multi_exec_occ = sum(int((d.occurrence_execution_count > 1).sum()) for d in occ.values())

nbo = {
    "N00": nb_outputs(NB + "00_dataQualityReview.ipynb"),
    "N01": nb_outputs(NB + "01_dataIngestion.ipynb"),
    "N02": nb_outputs(NB + "02_reconstructExecutions.ipynb"),
    "N03": nb_outputs(NB + "03_buildProfilesAndMetrics.ipynb"),
    "N04": nb_outputs(NB + "04_splitAndBaselines.ipynb"),
    "N05": nb_outputs(NB + "05_evaluateRecommendations.ipynb", PR61),
}

# (id, report section, report text, source label, kind, check)
#   kind "art": check = (computed value, expected value)
#   kind "nbout": check = (notebook key, substring)
#   kind "file": check = (path, ref or None, substring)
#   kind "pdf"/"run": check = None (manual)
C = []


def add(section, text, source, kind, check=None):
    C.append((len(C) + 1, section, text, source, kind, check))


# --- Data and pipeline counts
add("3.3.1, 5.1.1, Fig 2.1", "405,894 rows and 34 columns", "N00 output 'Dataset size'; raw CSV header", "nbout", ("N00", "Dataset size: 405,894 rows × 34 columns"))
add("3.3.1", "34 columns", "subset/borg_traces_data.csv header", "art", (raw_cols, 34))
add("3.3.1", "30.9965 days", "N00 output, start-time span as microseconds", "nbout", ("N00", "microseconds: 30.9965 days"))
add("5.1.1", "774 rows (0.19%)", "N01 output, nested resource-field audit / missing %", "nbout", ("N01", "resource_request 774 774 774"))
add("5.1.1", "4,927 rows (1.21%)", "N01 output, maximum_usage missing memory 4927; raw_peak_memory 1.213864%", "nbout", ("N01", "maximum_usage 0 0 4927"))
add("5.1.1", "203,459 rows", "N01 output 'CPU rows where peak > request'", "nbout", ("N01", "CPU rows where peak > request: 203459"))
add("5.1.1", "73,310 rows", "N01 output 'Memory rows where peak > request'", "nbout", ("N01", "Memory rows where peak > request: 73310"))
add("5.1.1", "152,037 of the 405,120 rows", "N01 output memory comparison", "nbout", ("N01", "Request memory equals assigned memory: 152037"))
add("5.1.1", "differs in 253,083", "N01 output memory comparison", "nbout", ("N01", "Request memory differs from assigned memory: 253083"))
add("5.1.1", "Three event times", "N01 output 'Invalid event timestamps converted to missing: 3'", "nbout", ("N01", "Invalid event timestamps converted to missing: 3"))
add("5.1.1", "thirteen event times", "N00 output 'Rows with event time after the latest usage end time: 13'", "nbout", ("N00", "Rows with event time after the latest usage end time: 13"))
add("5.1.1", "between 1 and 300 seconds (median 300 seconds)", "N00 output usage-window durations (microseconds interpretation)", "nbout", ("N00", "microseconds: minimum = 1, median = 300, maximum = 300"))
add("5.1.1", "1,506 of 405,894 rows (0.37%)", "N01 output", "nbout", ("N01", "Rows with time inside usage window: 1506 of 405894 Percentage: 0.37%"))
add("5.1.1", "uniquely identifies all 405,894 rows", "N01 output 'Unique observation keys: 405894'", "nbout", ("N01", "Unique observation keys: 405894"))
add("5.1.2", "242,946 candidate", "N02 output", "nbout", ("N02", "Unique candidate collection-instance groups: 242946"))
add("5.1.2", "7,704 observations on 6,640 machines", "N02 output (largest candidate groups)", "nbout", ("N02", "116646838687||17 7704 6640"))
add("5.1.2", "about 22 days apart", "N01 output time_span_sec 1927723.0 for 116646838687_17 (= 22.3 days)", "nbout", ("N01", "1927723.0"))
add("5.1.2", "10,639 positive gaps", "N02 output", "nbout", ("N02", "Positive temporal gaps: 10639"))
add("5.1.2", "the smallest is 25 minutes", "N02 output", "nbout", ("N02", "Minimum positive gap in minutes: 25.0"))
add("5.1.2", "the median is about 4 days", "N02 output gap_days 50% = 4.006944", "nbout", ("N02", "50% 4.006944"))
add("5.1.2, 9.1, Fig 2.1", "253,585 executions", "google_subset_executions_v1.parquet rows", "art", (len(exe), 253585))
add("5.1.2", "242,946 first episodes, 10,291 second, 340 third, and 8 fourth", "executions parquet episode_number counts", "art", ((int(ep[1]), int(ep[2]), int(ep[3]), int(ep[4])), (242946, 10291, 340, 8)))
add("5.1.2, 9.1, Fig 2.1", "2,280 recurrence keys", "executions parquet recurrence_key nunique", "art", (int(exe.recurrence_key.nunique()), 2280))
add("5.1.2", "1,504 have more than one execution and 776 have one", "executions parquet", "art", ((int((per_key > 1).sum()), int((per_key == 1).sum())), (1504, 776)))
add("5.1.2", "25,180 executions", "executions parquet max per key", "art", (int(per_key.max()), 25180))
add("5.1.3, 9.1, Fig 2.1", "4,879 full-workload occurrences", "job_profiles_google_subset_history_v1.parquet rows", "art", (len(prof), 4879))
add("5.1.3", "6,921 executions", "N04 regression constant KNOWN_OCCURRENCE_EXECUTION_COUNT and output", "nbout", ("N04", "KNOWN_OCCURRENCE_EXECUTION_COUNT = 6921"))
add("5.1.3, 6.1, 7.3", "91.877289", "N04 output 'Authoritative full-workload CPU peak'", "nbout", ("N04", "91.877289"))
add("5.1.3, 7.3", "0.013275", "N04 output 'Largest individual execution CPU peak: 0.013275146484375'", "nbout", ("N04", "Largest individual execution CPU peak: 0.013275"))
add("5.1.3, 9.3", "73 have a missing request", "N03 output 'Missing requested CPU occurrences: 73'", "nbout", ("N03", "Missing requested CPU occurrences: 73"))
add("5.1.3, 9.3", "60 have a missing memory peak", "occurrence profile parquet", "art", (int(prof.occurrence_peak_memory_normalized.isna().sum()), 60))
add("5.1.3", "2,280 cold-start occurrences", "occurrence profile parquet prior_occurrence_count == 0", "art", (int((prof.prior_occurrence_count == 0).sum()), 2280))
add("5.1.3", "80,801 rows are cold starts and 172,784 have history", "N03 output merge validation", "nbout", ("N03", "Cold-start executions: 80801 Executions with history: 172784"))
add("9.3", "the median is one occurrence per key", "occurrence profile parquet occurrences per recurrence_key (median)", "art", (float(occ_per_key.median()), 1.0))
add("6.1", "87,822 historical metrics", "N03 output", "nbout", ("N03", "Historical metrics checked: 87,822"))
add("6.1", "0 unmatched", "N03 output", "nbout", ("N03", "Unmatched: 0"))
add("Table 6.1", "3,473", "train_occurrences.parquet rows", "art", (len(occ["train"]), 3473))
add("Table 6.1, 5.2", "675", "val_occurrences.parquet rows", "art", (len(val), 675))
add("Table 6.1, 5.3.2", "731", "test_occurrences.parquet rows; test_ml_predictions.parquet rows", "art", ((len(occ["test"]), len(test_pred)), (731, 731)))
add("Table 6.1", "178,858", "metadata.json split_boundaries.train_rows", "art", (meta["split_boundaries"]["train_rows"], 178858))
add("Table 6.1", "36,703", "metadata.json split_boundaries.val_rows", "art", (meta["split_boundaries"]["val_rows"], 36703))
add("Table 6.1", "38,024", "metadata.json split_boundaries.test_rows", "art", (meta["split_boundaries"]["test_rows"], 38024))
add("Table 6.1", "1,812,600", "metadata.json train_end 1812600000000 us", "art", (meta["split_boundaries"]["train_end"], 1812600000000))
add("Table 6.1", "2,262,600", "metadata.json test_start 2262600000000 us", "art", (meta["split_boundaries"]["test_start"], 2262600000000))
add("Table 6.1", "2,277", "multi-execution occurrences, train (N04 output also 2277)", "art", (int((occ["train"].occurrence_execution_count > 1).sum()), 2277))
add("(consistency)", "3,307", "multi-execution occurrences across splits = N04 output 3307 (not stated in report text; checked for consistency)", "art", (multi_exec_occ, 3307))
add("5.2, 6.2", "330 have a CPU target, 329 have a memory target", "val_occurrences.parquet target availability", "art", ((int(val.target_cpu_next_occurrence_peak_ncu.notna().sum()), int(val.target_memory_next_occurrence_peak_normalized.notna().sum())), (330, 329)))
add("5.2, 5.3.3, 7.1.1", "329 occurrences", "metadata.json common_validation_population.occurrences; val_occurrences both-target count", "art", ((meta["common_validation_population"]["occurrences"], int(both_val.sum()), len(val_pred)), (329, 329, 329)))
add("6.2", "2,010 training, 330 validation, and 259 test targets", "N04 output target chronology checks", "nbout", ("N04", "Train target chronology check passed: 2010 targets Validation target chronology check passed: 330 targets Test target chronology check passed: 259 targets"))
add("5.2.2, 7.1.1, 9.1", "P99 with `min_runs = 1`", "metadata.json selected_baseline_policy / selected_min_runs", "art", ((meta["selected_baseline_policy"], meta["selected_min_runs"]), ("P99", 1)))
add("4.2.1", "`min_runs` ∈ {1, 3, 5, 10}", "metadata.json min_runs_candidates", "art", (meta["min_runs_candidates"], [1, 3, 5, 10]))
add("4.3", "70/15/15", "metadata.json requested fractions", "art", ((meta["split"]["requested_train_fraction"], meta["split"]["requested_validation_fraction"], meta["split"]["requested_test_fraction"]), (0.7, 0.15, 0.15)))
add("5.2.3", "35.4% at `min_runs = 1`, 56.0% at 3, 64.6% at 5, and 75.0% at 10", "N04 output cpu_fallback_pct 35.407407 / 56.0 / 64.592593 / 74.962963", "nbout", ("N04", "0 35.407407 242 35.851852 1 56.000000 384 56.888889 2 64.592593 440 65.185185 3 74.962963 510 75.555556"))
add("5.2.3", "35.9%, 56.9%, 65.2%, and 75.6%", "N04 output memory_fallback_pct 35.851852 / 56.888889 / 65.185185 / 75.555556", "nbout", ("N04", "0 35.407407 242 35.851852 1 56.000000 384 56.888889 2 64.592593 440 65.185185 3 74.962963 510 75.555556"))
add("5.2.3", "26 occurrences have no prior history", "N05 output (PR #61)", "nbout", ("N05", "Common occurrences with no prior history: 26"))
# --- Baseline validation results
add("7.1.1, 7.3, Table 7.1", "55.52%", "baseline_validation_comparison.csv Request min_runs=1 any_resource_violation_pct", "art", (round(b("Request", 1, "any_resource_violation_pct"), 2), 55.52))
add("7.1.1, Table 7.1", "21.95%", "baseline_validation_comparison.csv P99 min_runs=1 any_resource_violation_pct", "art", (round(b("P99", 1, "any_resource_violation_pct"), 2), 21.95))
add("7.1.1", "from 0.623 to 0.298", "baseline_validation_comparison.csv average_cpu_utilization Request / P99", "art", ((round(b("Request", 1, "average_cpu_utilization"), 3), round(b("P99", 1, "average_cpu_utilization"), 3)), (0.623, 0.298)))
add("7.1.1", "from 0.957 to 19.041", "baseline_validation_comparison.csv average_cpu_waste Request / P99", "art", ((round(b("Request", 1, "average_cpu_waste"), 3), round(b("P99", 1, "average_cpu_waste"), 3)), (0.957, 19.041)))
add("7.1.1", "22.39% at 3, 23.31% at 5, and 30.98% at 10", "baseline_validation_comparison.csv P99 any_resource_violation_pct by min_runs", "art", (tuple(round(b("P99", k, "any_resource_violation_pct"), 2) for k in (3, 5, 10)), (22.39, 23.31, 30.98)))
add("6.4.3", "326 valid rows for each violation metric, 315 valid rows for CPU utilization, and 326 for memory utilization", "baseline_validation_comparison.csv Request min_runs=1 valid counts", "art", (tuple(int(b("Request", 1, k)) for k in ("valid_cpu_violation_count", "valid_memory_violation_count", "valid_any_resource_violation_count", "valid_cpu_utilization_count", "valid_memory_utilization_count")), (326, 326, 326, 315, 326)))
add("Table 7.1", "Table 7.1 (all cells)", "generated from baseline_validation_comparison.csv by make_report_artifacts.py (figures/table_7_1_baseline_validation.md)", "file", ("docs/report/figures/table_7_1_baseline_validation.md", None, "| P99 | 16.77 | 17.07 | 21.95 | 328 | 0.298 | 0.337 | 19.041 | 3.346 | 0.972 | 0.086 |"))
add("5.2.1", "identical across all four `min_runs` candidates", "N04 output 'Request baseline is invariant across min_runs candidates.'", "nbout", ("N04", "Request baseline is invariant across min_runs candidates."))
# --- ML (PR #61)
add("5.3.1", "24 features", "ml_feature_manifest.json feature_order length", "art", (len(manifest["feature_order"]), 24))
add("5.3.1", "1,672 CPU and 1,649 memory training rows", "ml_metadata.json training_rows (train_period_only)", "art", ((ml_meta["training_rows"]["cpu/train_period_only"], ml_meta["training_rows"]["memory/train_period_only"]), (1672, 1649)))
add("5.3.1, 6.2", "338 CPU labels", "N05 output (PR #61)", "nbout", ("N05", "CPU labels excluded because the target lies after the training period: 338"))
add("5.3.1", "all 2,010 CPU and 1,983 memory training labels", "ml_metadata.json training_rows (all_available)", "art", ((ml_meta["training_rows"]["cpu/all_available"], ml_meta["training_rows"]["memory/all_available"]), (2010, 1983)))
add("5.3.2", "16 Decision Tree, 27 Random Forest, and 32 XGBoost combinations", "N05 output (PR #61)", "nbout", ("N05", "decision_tree: 16 hyperparameter combinations random_forest: 27 hyperparameter combinations xgboost: 32 hyperparameter combinations"))
add("5.3.2", "CPU 0.839, memory 0.471", "ml_cv_summary.csv random_forest tss_mean_log_rmse", "art", ((round(c("cpu", "random_forest", "tss_mean_log_rmse"), 3), round(c("memory", "random_forest", "tss_mean_log_rmse"), 3)), (0.839, 0.471)))
add("5.3.2", "CPU 0.781, memory 0.442", "ml_cv_summary.csv random_forest groupkfold_mean_log_rmse", "art", ((round(c("cpu", "random_forest", "groupkfold_mean_log_rmse"), 3), round(c("memory", "random_forest", "groupkfold_mean_log_rmse"), 3)), (0.781, 0.442)))
add("5.3.2", "CPU 0.285, memory 0.188", "ml_cv_summary.csv random_forest groupkfold_std_log_rmse", "art", ((round(c("cpu", "random_forest", "groupkfold_std_log_rmse"), 3), round(c("memory", "random_forest", "groupkfold_std_log_rmse"), 3)), (0.285, 0.188)))
add("5.3.2, 9.1", "Random Forest for both CPU and memory", "ml_metadata.json selected_models", "art", (ml_meta["selected_models"], {"cpu": "random_forest", "memory": "random_forest"}))
add("5.3.2", "300 trees, `max_features = \"sqrt\"`, `min_samples_leaf = 10`, and `max_depth` 10 for CPU and 6 for memory", "ml_metadata.json locked_params", "art", (tuple((ml_meta["locked_params"][r]["n_estimators"], ml_meta["locked_params"][r]["max_features"], ml_meta["locked_params"][r]["min_samples_leaf"], ml_meta["locked_params"][r]["max_depth"]) for r in ("cpu", "memory")), ((300, "sqrt", 10, 10), (300, "sqrt", 10, 6))))
add("5.3.2", "2,108 CPU rows and 2,082 memory rows", "ml_metadata.json refit.rows", "art", ((ml_meta["refit"]["rows"]["cpu"], ml_meta["refit"]["rows"]["memory"]), (2108, 2082)))
add("5.3.2", "missing for 2 test occurrences per resource", "test_ml_predictions.parquet p95 NaN counts", "art", ((int(test_pred.p95_cpu.isna().sum()), int(test_pred.p95_memory.isna().sum())), (2, 2)))
add("5.3.2", "No test metric was computed", "ml_metadata.json test_metrics_computed = false", "art", (ml_meta["test_metrics_computed"], False))
add("5.3.3, 7.3", "CPU (0.850) and memory (0.387)", "ml_validation_model_comparison.csv tuned random_forest log_rmse", "art", ((round(m("cpu", "tuned", "random_forest", "log_rmse"), 3), round(m("memory", "tuned", "random_forest", "log_rmse"), 3)), (0.850, 0.387)))
add("5.3.3", "raw R² is −0.005 for CPU and 0.107 for memory", "ml_validation_model_comparison.csv tuned random_forest r2", "art", ((round(m("cpu", "tuned", "random_forest", "r2"), 3), round(m("memory", "tuned", "random_forest", "r2"), 3)), (-0.005, 0.107)))
add("5.3.3", "median reference has a lower raw MAE than every model", "ml_validation_model_comparison.csv mae (reference_median vs all models, both resources)", "art", (all(mvc[(mvc.resource == r) & (mvc.model == "reference_median")].mae.iloc[0] < mvc[(mvc.resource == r) & (mvc.model != "reference_median")].mae.min() for r in ("cpu", "memory")), True))
add("Table 5.1", "Table 5.1 (all cells)", "generated from ml_validation_model_comparison.csv (figures/table_5_1_ml_validation.md)", "file", ("docs/report/figures/table_5_1_ml_validation.md", None, "| CPU | tuned | Random Forest | yes | 1672 | 329 | 2.824 | 9.559 | -0.005 | 0.850 | 0.137 |"))
add("5.5, 6.3", "reproduced exactly", "N05 output (PR #61)", "nbout", ("N05", "All N04 baseline validation metrics reproduced exactly (min_runs=1, 5 policies)."))
add("3.1", "Python 3.12.15, pandas 2.3.3, NumPy 2.5.4, scikit-learn 1.9.1, and XGBoost 3.4.1", "ml_metadata.json versions", "art", (tuple(ml_meta["versions"][k] for k in ("python", "pandas", "numpy", "scikit-learn", "xgboost")), ("3.12.15", "2.3.3", "2.5.4", "1.9.1", "3.4.1")))
add("3.1", "Python 3.12.4", "docs/data/subsetSetup.md", "file", ("docs/data/subsetSetup.md", None, "Python 3.12.4"))
add("3.5, 8.2", "`random_state = 42`", "ml_metadata.json random_state", "art", (ml_meta["random_state"], 42))
add("4.2.2", "`log1p(target)`", "ml_feature_manifest.json target_transform", "art", (manifest["target_transform"], "log1p for training; expm1 then clip at 0 for predictions"))
add("6.4.1", "*r* ≤ 10⁻¹²", "src/evaluation/metrics.py DEFAULT_EPSILON", "file", ("src/evaluation/metrics.py", None, "DEFAULT_EPSILON = 1e-12"))
add("6.4.1", "Equality is not a violation", "src/evaluation/metrics.py (actual > recommended); tests/test_evaluation.py", "file", ("tests/test_evaluation.py", None, "def test_equal_actual_and_recommended_is_not_a_violation"))
add("6.3", "81 tests passed and 1 failed", "pytest on main a0b3c77 with local artifacts, 2026-10-16: '1 failed, 81 passed' (PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q)", "run")
add("6.3", "the suite has 82 tests in eight files", "pytest --collect-only on main a0b3c77: 17+7+14+10+12+15+2+5 = 82", "run")
add("6.3", "all 5 of them fail with missing-file errors (77 of 82 pass)", "pytest on a `git archive` copy of a0b3c77 without data/, 2026-10-16: '5 failed, 77 passed'", "run")
add("6.3", "expects 1,801 missing CPU targets", "tests/test_google_canonical_contract.py (== 1801); train recurrence keys in train_occurrences.parquet", "art", (int(occ["train"].recurrence_key.nunique()), 1801))
add("6.3", "The artifact has 1,463", "train_occurrences.parquet null target_cpu_next_occurrence_peak_ncu", "art", (int(occ["train"].target_cpu_next_occurrence_peak_ncu.isna().sum()), 1463))
add("6.3", "The difference of 338", "train_occurrences.parquet targets starting after metadata train_end", "art", (int((occ["train"].target_next_occurrence_start_time_us > meta["split_boundaries"]["train_end"]).sum()), 338))
add("6.3", "38 tests, all of which passed when run on 2026-10-15", "pytest run on a `git archive` snapshot of the PR #61 branch, 2026-10-15: '38 passed'", "run")
add("8.2", "PR #61 adds `xgboost` to `requirements.txt`", "git diff origin/main...PR #61 requirements.txt", "file", ("requirements.txt", PR61, "xgboost>=2.0.0"))
# --- PR #70
add("2.2.1, 3.4", "version 0.1.0", "docs/data/canonical_workload_schema.md", "file", ("docs/data/canonical_workload_schema.md", PR70, "**Schema version:** `0.1.0`"))
add("3.3.2", "about 4,000 machines over 8 days", "docs/data/dataset_semantics_study_FINAL.md (citing official Alibaba documentation)", "file", ("docs/data/dataset_semantics_study_FINAL.md", PR70, "The trace covers about 4,000 machines over 8 days"))
add("3.3.2", "spans 30 days", "docs/data/dataset_semantics_study_FINAL.md", "file", ("docs/data/dataset_semantics_study_FINAL.md", PR70, "The trace spans 30 consecutive days."))
add("3.3.2", "not a direct export of the internal Resource Central service", "docs/data/dataset_semantics_study_FINAL.md", "file", ("docs/data/dataset_semantics_study_FINAL.md", PR70, "It is **not** a direct export of the internal Resource Central service."))
add("3.4", "Azure VM V2 supports CPU and memory capacity", "config/dataset_capabilities.json", "file", ("config/dataset_capabilities.json", PR70, '"dataset_id": "azure_public_vm_v2"'))
add("5.1.2", "`aggregation_window_sec = 300`", "docs/data/external_dataset_integration.md", "file", ("docs/data/external_dataset_integration.md", PR70, "`aggregation_window_sec = 300`"))
# --- Findings of docs/data/google_subset_pipeline_analysis.md (merged with PR #72), reproduced here
import numpy as np  # noqa: E402
import sys  # noqa: E402
sys.path.insert(0, str(REPO / "src"))
from evaluation.evaluator import RecommendationEvaluator  # noqa: E402

_sb = meta["split_boundaries"]
_T = "target_next_occurrence_start_time_us"
_v = val[both_val]
_ev = RecommendationEvaluator()


def _p99_any(df):
    r = _ev.summarize(_ev.evaluate(df, "target_cpu_next_occurrence_peak_ncu",
                                   "target_memory_next_occurrence_peak_normalized", "rec_cpu_p99", "rec_memory_p99"))
    return round(r["any_resource_violation_pct"], 2)


_v_in = _v[_v[_T] < _sb["test_start"]]
_obs = pd.read_parquet(DATA / "google_subset_observations_reconstructed_v1.parquet",
                       columns=["execution_id", "collection_id", "instance_index", "machine_id",
                                "usage_start_time_us", "usage_end_time_us", "peak_cpu_ncu", "event"])
_ex = pd.read_parquet(DATA / "google_subset_executions_v1.parquet",
                      columns=["execution_id", "recurrence_key", "execution_start_time_us"])
_o = _obs.merge(_ex, on="execution_id")
_k = ["recurrence_key", "execution_start_time_us", "usage_start_time_us", "usage_end_time_us"]


def _occ_peak(df):
    w = df.groupby(_k)["peak_cpu_ncu"].agg(lambda x: x.sum() if x.notna().all() else np.nan).reset_index()
    return w.groupby(_k[:2])["peak_cpu_ncu"].agg(lambda x: x.max() if x.notna().all() else np.nan)


_full = _occ_peak(_o)
_dedup = _occ_peak(_o.drop_duplicates(["collection_id", "instance_index", "usage_start_time_us", "usage_end_time_us"]))
_changed = int((~np.isclose(_full.values, _dedup.reindex(_full.index).values, equal_nan=True)).sum())
_iw = _obs.groupby(["collection_id", "instance_index", "usage_start_time_us", "usage_end_time_us"]).machine_id.nunique()
_abn = _o[_o.event.isin(["FAIL", "KILL", "EVICT", "LOST"])].groupby(_k[:2]).size()
GPA = "docs/data/google_subset_pipeline_analysis.md"
add("6.2, 7.1.1, 9.3", "104 of the 330 validation targets fall in the test period", "val_occurrences.parquet (target start >= test_start), scored population; analysis F3", "art", ((int((val[_T] >= _sb["test_start"]).sum()), int((_v[_T] >= _sb["test_start"]).sum()), int(val[_T].notna().sum())), (104, 104, 330)))
add("6.2", "104 of the 330 validation targets fall in the test period", "analysis F3 table", "file", (GPA, None, "| Validation | 675 | 330 | 330 | 104 |"))
add("6.2, 7.1.1", "225 occurrences", "scored validation rows with target before test_start", "art", (len(_v_in), 225))
add("6.2, 7.1.1", "18.30%", "shared evaluator, P99 min_runs=1 on the 225 rows (recomputed); analysis F4", "art", (_p99_any(_v_in), 18.30))
add("6.2", "selected policy (P99, `min_runs = 1`) is unchanged", "analysis F4 table", "file", (GPA, None, "| Targets inside the validation period only | 225 | P99, `min_runs = 1` | 18.30% |"))
add("5.1.2", "38,146 of 253,594 instance-windows", "reconstructed observations: instance-windows with >1 machine (recomputed); analysis F8", "art", ((int((_iw > 1).sum()), len(_iw)), (38146, 253594)))
add("5.1.2, 9.3", "1,159", "occurrence CPU peaks changed by keeping one row per (collection, instance, window) (recomputed); analysis F8", "art", (_changed, 1159))
add("5.1.2", "suspected but not proven duplicates", "analysis F8 status", "file", (GPA, None, "That the rows are duplicates is suspected, but strongly supported."))
add("5.1.3, 9.3", "2,584 of the 4,879 occurrences", "occurrences with any FAIL/KILL/EVICT/LOST observation (recomputed); analysis F7", "art", (len(_abn), 2584))
# --- PR #72 documentation and PR #70 follow-up (d852630)
ADF = "docs/data/alibaba_dataset_selection_feasibility.md"
CCD = "docs/data/canonical_contract_decisions.md"
add("3.3.2", "the sample data actually used is the 2017 V1 trace", f"{ADF} Section 8.1", "file", (ADF, None, "the data actually used is the 2017 V1 trace."))
add("3.3.2", "Both versions span 30 consecutive days", f"{ADF} Section 8.2 table", "file", (ADF, None, "| Period | 30 consecutive days in 2019 (month undocumented) | 30 consecutive days in 2017 |"))
add("3.3.2", "99.86% of jobs", f"{CCD} Section 2", "file", (CCD, None, "It covers 99.86% of jobs."))
add("3.3.2", "defer Azure", f"{ADF} Section 1 / {CCD} Section 1", "file", (CCD, None, "- Azure is deferred."))
add("3.3.2", "none of its decisions is implemented", f"{CCD} Implementation Status", "file", (CCD, None, "none of the decisions above is implemented"))
add("3.3.2", "once the team accepts it", f"{CCD} Section 1 Readiness", "file", (CCD, None, "once the team accepts it"))
add("3.3.2", "no any-resource metric would be reported", f"{CCD} Section 3 Metrics row", "file", (CCD, None, "**No any-resource metric.**"))
add("2.2.1, Table 2.1", "it changes no code", "git show --stat 57b6956 (PR #72): docs/data only", "file", (ADF, None, "Nothing was implemented in producing this analysis."))
add("3.4", "`alibaba_plan_cpu_100_per_core`", "src/canonical/schema.py ALLOWED_RESOURCE_UNITS", "file", ("src/canonical/schema.py", None, '"alibaba_plan_cpu_100_per_core",'))
add("3.4", "populated actual values when a dataset does not support targets", "src/canonical/schema.py capability enforcement", "file", ("src/canonical/schema.py", None, '"targets unsupported",'))
add("5.1.1", "interval records (by their identifier keys)", "src/adapters/validation.py _validate_record_uniqueness", "file", ("src/adapters/validation.py", None, "Duplicate canonical {record_level} records"))
add("5.1.1", "`cpu_validity_status`, `memory_validity_status`", "src/adapters/alibaba.py", "file", ("src/adapters/alibaba.py", None, 'out["memory_validity_status"] = np.select('))
add("5.1.1", "`source_cpu_avg_gt_max`, `source_memory_avg_gt_max`", "src/adapters/alibaba.py", "file", ("src/adapters/alibaba.py", None, 'out["source_memory_avg_gt_max"] = ('))
add("5.1.1", "missing from the VM table", "src/adapters/azure_vm.py (raises on VM IDs missing from VM metadata)", "file", ("src/adapters/azure_vm.py", None, "Azure CPU readings contain VM IDs missing from VM metadata"))
add("5.1.1", "Open-ended capacity buckets such as `>24`", "src/adapters/azure_vm.py _parse_capacity_bucket docstring", "file", ("src/adapters/azure_vm.py", None, 'Open-ended buckets such as ">24" are preserved as open-ended:'))
add("5.1.1", "(d852630)", "git log 69f3a42..a0b3c77 -- src: only d852630 changes src/", "run")
# --- Non-obvious definitions
add("2.1, Glossary", "`occurrence_key = recurrence_key || execution_start_time_us`", "metadata.json occurrence_key_definition", "art", (meta["occurrence_key_definition"], "occurrence_key = recurrence_key || execution_start_time_us"))
add("5.1.2", "`recurrence_key = user_clean || logical_workload_name`", "N02 markdown 'recurrence_key = user_clean || logical_workload_name'", "nbout", ("N02", "recurrence_key = user_clean || logical_workload_name"))
add("4.2.1", "lexicographic, violation-first ranking", "metadata.json baseline_selection_objective", "art", (meta["baseline_selection_objective"].startswith("Lexicographic violation-focused ranking"), True))
add("4.2.2", "lower raw MAE as the tie-breaker", "ml_metadata.json selection_rule", "art", (ml_meta["selection_rule"], "Per resource, lowest validation RMSE on the log1p scale among tuned candidates trained on train-period labels; tie-breaker lower raw MAE."))
add("4.3", "Targets are built once on the complete occurrence table before splitting", "metadata.json target_definition", "art", (meta["target_definition"].startswith("Targets are created once on the complete occurrence table before splitting"), True))
add("6.2", "inside each frozen split so labels never cross split boundaries", "N04 cell 0 markdown (inconsistent with implementation)", "nbout", ("N04", "inside each frozen split so labels never cross split boundaries"))
add("2.2.4, 4.2.3", "HybridCPU = max(MLPredictedCPU, P95CPU)", "backlog PDF p. 25 (New Issue 6)", "pdf")
add("3.3.2", "Active work becomes New Issues 1 and 4 for Alibaba and Azure VM", "backlog PDF p. 21 (issue mapping)", "pdf")
add("3.3.2", "outside the active external-dataset implementation until the team or advisor confirms that they are mandatory", "backlog PDF p. 31 (scope pending work)", "pdf")
add("3.3.1, 8.1, 9.3", "(backlog, p. 20)", "backlog PDF p. 20 (explicitly not required)", "pdf")
add("7.1", "the only source of final Google report numbers", "backlog PDF p. 15 (Issue 12 acceptance criteria)", "pdf")
add("4.2.3, 8.3", "Conservative, Balanced, or Efficient", "backlog PDF pp. 25–27 (New Issues 6, 8, 9)", "pdf")
add("4.4", "provenance, history count, confidence, fallback reason, capability status, validity status, and artifact version", "backlog PDF p. 25 (New Issue 5 tasks)", "pdf")
add("2.2.4, 4.2.3, 5.4", "Under the team's notebook split", "team decision quoted in docs/planning/295b_scope_and_done.md Section 5", "file", ("docs/planning/295b_scope_and_done.md", None, "Notebook 6 (final) → evaluate Request/Mean/P90/P95/P99 → receive ML predictions → construct Hybrid recommendations"))
add("3.3.2", "This conflict is open in the 295B scope document (Section 7)", "docs/planning/295b_scope_and_done.md Section 7", "file", ("docs/planning/295b_scope_and_done.md", None, "## 7. Open Questions and Known Conflicts"))


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------
def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s)


rows, failures = [], []
for cid, section, text, source, kind, check in C:
    in_report = "n/a" if section.startswith("(") or text.startswith("Table ") else ("yes" if norm(text) in report_flat else "NO")
    if kind == "art":
        got, exp = check
        ok = got == exp or (isinstance(exp, float) and abs(float(got) - exp) < 1e-9)
        status = "verified" if ok else f"MISMATCH (got {got!r})"
    elif kind == "nbout":
        key, sub = check
        status = "verified" if norm(sub) in nbo[key] else "NOT FOUND"
    elif kind == "file":
        path, ref, sub = check
        status = "verified" if sub in read_file(path, ref) else "NOT FOUND"
    elif kind == "pdf":
        status = "manual (PDF not in repo)"
    else:
        status = "recorded run"
    if in_report == "NO" or status.startswith(("MISMATCH", "NOT FOUND")):
        failures.append((cid, text, status, in_report))
    rows.append((cid, section, text, source, kind, status, in_report))

# Placeholders
tbds = [t for t in re.findall(r"\[TBD[^\]]*\]", report) if t != "[TBD — …]"]  # skip the format example in the draft note


def tbd_issue(t: str) -> str:
    found = [f.strip(" ,") for f in re.findall(r"((?:New )?Issues? \d+(?:[–-]\d+)?(?:(?:, | and )(?:New Issues? )?\d+)*|Notebook 06|PR #70)", t)]
    return "; ".join(dict.fromkeys(found)) or "team decision / documentation update (no backlog issue named)"


def esc(s: str) -> str:
    return s.replace("|", "\\|")


lines = []
lines.append("# Report Traceability: TraceAdvisor 295B Final Report, Chapters 2–9 (Draft)\n")
lines.append("Generated by `docs/report/scripts/build_traceability.py`, which checks each claim against its source and confirms the claim text appears in `TraceAdvisor_295B_Final_Report_Ch2-9_DRAFT.md`. Re-run it after any edit to the report or any artifact regeneration.\n")
lines.append("**Sources.** Artifacts: `data/processed/google_subset_v1/` (gitignored; produced by running Notebooks 01–04 on `main` and Notebook 05 from PR #61). Notebook outputs: saved outputs in `pipelines/google_subset/*.ipynb` on `main`, and Notebook 05 on `origin/feature/google-subset-n05-ml-eval` (PR #61). PR #70 files: `origin/feature/external-dataset-canonical-pipeline`. Backlog: *TraceAdvisor 295B Project Completion GitHub Issue Backlog* PDF (not in the repository; pages cited). Generated tables and the figure: `docs/report/figures/`, from `docs/report/scripts/make_report_artifacts.py`.\n")
lines.append(f"**Check summary.** {len(C)} claims; {sum(1 for r in rows if r[5] == 'verified')} verified automatically; {sum(1 for r in rows if r[5].startswith('manual'))} manual (backlog PDF); {sum(1 for r in rows if r[5] == 'recorded run')} recorded test runs; failures: {len(failures)}.\n")
if failures:
    lines.append("**FAILURES:**\n")
    for f in failures:
        lines.append(f"- #{f[0]} `{esc(f[1])}`: source check = {f[2]}; present in report = {f[3]}")
    lines.append("")
lines.append("## 1. Claims and sources\n")
lines.append("| # | Section | Claim text in report | Source (file / output / page) | Kind | Source check | In report |")
lines.append("|---|---|---|---|---|---|---|")
for r in rows:
    lines.append("| " + " | ".join([str(r[0]), r[1], esc(r[2]), esc(r[3]), r[4], r[5], r[6]]) + " |")
lines.append("")
lines.append("Validation-only values: every result number in Sections 5.3, 6.4.3, 7.1, and 7.3 and in Tables 5.1 and 7.1 comes from the validation split. No test-split metric appears in the report. Test-split counts (731 occurrences, 259 with targets, 731 prediction rows, 2 missing P95 inputs) are row counts, not performance results.\n")
lines.append("## 2. Figures and tables\n")
lines.append("| Item | File | Generated by | Inputs |")
lines.append("|---|---|---|---|")
lines.append("| Figure 2.1 | `figures/fig_2_1_pipeline.png` | `scripts/make_report_artifacts.py` | raw CSV header; observations, executions, occurrence-profile, split-occurrence parquet files; `metadata.json`; `val_ml_predictions.parquet`; `test_ml_predictions.parquet` |")
lines.append("| Table 2.1 | inline in report | written from `docs/planning/295b_scope_and_done.md` (Sections 5–6), PR #61 (open), PR #70 (merged), PR #72 docs (`alibaba_dataset_selection_feasibility.md`, `canonical_contract_decisions.md`), backlog pp. 21–31 | — |")
lines.append("| Table 5.1 | `figures/table_5_1_ml_validation.md` / `.csv` | `scripts/make_report_artifacts.py` | `ml_validation_model_comparison.csv` |")
lines.append("| Table 6.1 | `figures/table_6_1_split_summary.md` / `.csv` | `scripts/make_report_artifacts.py` | `metadata.json`; `{train,val,test}_occurrences.parquet` |")
lines.append("| Table 7.1 | `figures/table_7_1_baseline_validation.md` / `.csv` | `scripts/make_report_artifacts.py` | `baseline_validation_comparison.csv` (min_runs = 1 rows) |")
lines.append("")
lines.append("All values used by the figure and tables are also dumped to `figures/artifact_values.json`.\n")
lines.append("## 3. Placeholders\n")
lines.append(f"{len(tbds)} placeholders in the report. Each will be filled by the item named.\n")
lines.append("| # | Placeholder | Filled by |")
lines.append("|---|---|---|")
for i, t in enumerate(tbds, 1):
    lines.append(f"| {i} | {esc(t)} | {tbd_issue(t)} |")
lines.append("")


lines.append("## 4. Status claims (implemented / in review / planned)\n")
lines.append("| Claim | Source |")
lines.append("|---|---|")
lines.append("| N00–N04, `src/evaluation/`, `src/features/split_utils.py` implemented on `main` | files present on `origin/main` (commit 184f204); `docs/planning/295b_scope_and_done.md` Section 6 |")
lines.append("| N05 in review in PR #61 | branch `origin/feature/google-subset-n05-ml-eval` (commit 0a3cf8e); scope doc Section 6 snapshot (2026-10-14): N05 on `main` is an empty placeholder |")
lines.append("| External semantics, schema, adapters implemented (PR #70 merged) | `origin/main` a0b3c77 = merge of PR #70 (includes 0109d02, 223e257, c3e2673, 69f3a42 and follow-up d852630) |")
lines.append("| New Issue 4 (GitHub #66) open for downstream history/profile/ML-ready preparation; #62, #64, #65 closed | GitHub issue state as relayed by the coordinator on 2026-10-16 (PR #70 description: \"Part of #66\"); not independently checked (no GitHub CLI available) |")
lines.append("| PR #72 merged as documentation only | `git show --stat 57b6956`: only docs/data/ files changed |")
lines.append("| N06 not yet created; Hybrid and all-policy comparison planned there | scope doc Section 6 snapshot; team decision in scope doc Section 5 |")
lines.append("| Issues 11, 12, 13, 16, 18 and New Issues 5–9 planned; dataset-specific ML Issues 06–08 for Alibaba/Azure planned | backlog pp. 21–31; scope doc Section 5 (no GitHub issue for several of these as of 2026-10-14) |")
lines.append("")
lines.append("## 5. Issue 17 technical consistency checklist\n")
lines.append("Acceptance criteria copied from backlog Issue 17 (PDF pp. 18–19), with the status of this draft.\n")
lines.append("| Acceptance criterion (backlog Issue 17) | Status for this draft |")
lines.append("|---|---|")
lines.append("| Chapters 2–9 are complete and match the submitted TOC. | **Partial.** All 64 chapter and section headings for Chapters 2–9 match `CMPE295B_TOC_TraceAdvisor_formatted.docx` verbatim (checked by script comparison). Content for unbuilt work is marked [TBD] (Section 3 above). |")
lines.append("| Chapter 1 remains consistent with the final system and is not silently rewritten. | **Not touched.** Chapter 1 is not part of this draft. A consistency read of Chapter 1 against this draft is still needed (Chapter 1 text was not among the sources used). |")
lines.append("| Every quantitative claim maps to a saved final artifact or external source. | **Met for current claims** (Section 1, 0 failures), but the sources are validation and pipeline artifacts, not *final* frozen artifacts. Final numbers await Issues 11–12. |")
lines.append("| No stale pre-refactor metric, execution-target definition, or outdated scope claim remains. | **Met in this draft.** No 295A result (for example `reports/eval/`, README historical numbers) is used. The occurrence-level next-occurrence target is used throughout. Scope conflicts are presented as open (Section 6 below). |")
lines.append("| Cross-platform validation covers Resource Central, Splitwise, ModServe, and Alibaba accurately, including supported fields, native units, and limitations. | **Not met / conflicting scope.** The revised plan makes Alibaba and Azure VM active and Splitwise/ModServe scope-pending. PR #70 (merged) provides Alibaba 2018 and Azure VM adapters, but no external results exist, and PR #72 proposes a different scope (Alibaba GPU v2020; Azure deferred). Sections 3.3.2 and 7.2 describe this; results are placeholders. |")
lines.append("| Figures/tables have captions/numbers and source scripts/artifacts. | **Met** for Figure 2.1 and Tables 5.1, 6.1, 7.1 (Section 2 above). Table 2.1 is a status table written from planning sources. |")
lines.append("| A technical review confirms report terminology/metrics match main. | **Pending.** Terminology follows `main` (a0b3c77, with PR #70 merged) and the PR #61 code. A team technical review is still required; PR #61 content must be re-checked after merge. The open Google-pipeline findings in `docs/data/google_subset_pipeline_analysis.md` (F3/F4 target crossing, F7 abnormal records, F8 possible duplicate summing) and the failing test `test_google_train_target_nulls_are_preserved` are reported as open items, not resolved. |")
lines.append("")
lines.append("## 6. Source conflicts found while drafting\n")
for item in [
    "TOC Section 3.3.2 and Issue 17 acceptance criteria (PDF p. 19) name Resource Central, Splitwise, ModServe, and Alibaba as validation datasets; the revised plan (PDF pp. 21, 31) makes Alibaba and Azure VM active and Splitwise/ModServe scope-pending. Open per scope doc Section 7. The draft keeps the TOC heading verbatim and states the conflict.",
    "Backlog Issue 08 (PDF pp. 29–30) places tuning, TimeSeriesSplit/GroupKFold, model selection, refit, and prediction generation in Notebook 6; the team decision and PR #61 place them in Notebook 05. The draft follows the team decision.",
    "Backlog Issue 08 (PDF p. 30) refers to previously assumed Google winners \"Random Forest CPU or XGBoost memory\"; the validation-based selection in PR #61 chose Random Forest for memory as well. Issue 08 itself (PDF p. 13) says to update the lock if winners change. The draft reports the PR #61 result.",
    "The Notebook 04 introduction (cell 0) says targets are built \"inside each frozen split so labels never cross split boundaries\"; the Notebook 04 code, its cell-24 markdown, and `metadata.json` (`target_split_isolation`) build targets before splitting and allow them to cross boundaries. The draft describes the implementation and flags the text (Section 6.2).",
    "The original backlog Hybrid rule is \"max(ML prediction, selected historical safeguard)\" (PDF p. 14), while the revised plan fixes the starting safeguard at P95 (PDF p. 25), and Notebook 04 selected P99 as the best baseline. Which safeguard the final Hybrid uses is open (New Issue 6 calibration). The draft states the revised-plan rule as the starting point only.",
    "README (295A, historical section) lists the \"Kaggle Subset (1.3M rows)\"; the current Notebook 00/01 outputs show 405,894 rows. The README labels that section historical; the draft uses only the current notebook outputs.",
    "The team meeting log (2026-09-24) mentions a 70/20/10 split; the implemented split (`metadata.json`) is 70/15/15. The draft uses the implemented split.",
    "`main` `src/features/feature_config.py` `FEATURE_COLS` is the legacy execution-level feature set (e.g., `peak_mem_gb`); PR #61 adds the occurrence-level `OCCURRENCE_FEATURE_COLS`. The draft describes only the PR #61 contract.",
    "`requirements.txt` on `main` lacks `xgboost`, which Notebook 05 needs; PR #61 adds it.",
    "Environment: `docs/data/subsetSetup.md` records Python 3.12.4; `ml_metadata.json` records Python 3.12.15. Both are reported; the final pinned environment is a placeholder (Issue 16).",
    "README claims explicit confidence tiers (295A `docs/planning/assumptions.md`); the current occurrence-level pipeline does not implement confidence tiers. New Issue 5 lists a confidence field. The draft does not claim confidence tiers.",
    "External-dataset scope: the revised backlog plan (pp. 21–31) makes Alibaba 2018 and Azure VM active (implemented as adapters in PR #70); the PR #72 documents (`docs/data/alibaba_dataset_selection_feasibility.md`, `docs/data/canonical_contract_decisions.md`) recommend Alibaba GPU v2020 as the required second dataset, Alibaba 2018 as optional, and deferring Azure, and state the design awaits team acceptance. The draft presents this as an open decision.",
    "Azure trace version: PR #70 labels the dataset Azure Public Dataset V2 (2019) (`azure_public_vm_v2`, semantics-study title); `docs/data/alibaba_dataset_selection_feasibility.md` Section 8.1 reports the sample actually used is the 2017 V1 trace. The draft states both and leaves the version as a placeholder.",
    "Google pipeline validity: `docs/data/google_subset_pipeline_analysis.md` (merged) reports that validation targets cross into the test period (F3/F4), that abnormal-event records are included (F7), and that repeated instance-window rows are summed across machines (F8). These were not in the first draft; the counts were reproduced for this update and are reported as open limitations. The same document's statement that Notebook 05 is a 0-byte file refers to `main`; the implementation is in open PR #61.",
    "Test behavior: the coordinator note stated that `test_google_train_target_nulls_are_preserved` skips without local artifacts; on a `git archive` copy of a0b3c77 without `data/`, all 5 Google canonical-contract tests fail (FileNotFoundError / assertion), 77 pass. With artifacts: 1 failed (1,463 vs expected 1,801), 81 passed. The draft reports the observed behavior.",
    "`test_google_train_target_nulls_are_preserved` assumes within-split targets (expects null CPU targets = 1,801 training recurrence keys), which conflicts with Notebook 04's before-split target construction (1,801 − 338 = 1,463). Same root issue as the Notebook 04 introduction text conflict above.",
    "Citations: Azure Public Dataset V2, the Kaggle ClusterData 2019 sample, Splitwise, and ModServe are not in `docs/references/References.md`; the draft marks citation placeholders instead of citing them.",
]:
    lines.append(f"- {item}")
lines.append("")

OUT.write_text("\n".join(lines) + "\n")
print(f"claims={len(C)} failures={len(failures)} placeholders={len(tbds)}")
for f in failures:
    print("FAIL", f)
