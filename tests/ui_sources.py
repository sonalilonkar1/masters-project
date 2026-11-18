"""Small synthetic Google and Alibaba sources shared by the export tests, the API tests
and the fixture-bundle generator (Task 15).

Every edge case the UI must handle appears at least once: history and request
fallback, a workload with no scored run, a missing request, Hybrid without a
safeguard, an ineligible CPU target next to an available memory target, a
same-second tie, and CPU using history while memory falls back.
"""

import numpy as np
import pandas as pd

from src.service import export
from src.service.contract import POLICY_NAMES
from src.service.export import SourceReference, export_alibaba, export_google


def google_sources():
    """Workload A runs three times (histories 0, 1, 2); workload B runs once with no request.

    Recommendations are chosen so every basis case appears: A's first run falls
    back to its request, later runs use history, and B has no safeguard at all.
    """
    occurrences = pd.DataFrame(
        {
            "occurrence_key": ["a1", "a2", "a3", "b1"],
            "occurrence_id": ["a1", "a2", "a3", "b1"],
            "recurrence_key": ["u||A", "u||A", "u||A", "u/2||B"],  # hashed Google IDs can contain "/"
            "execution_start_time_us": pd.array([100, 200, 300, 150], dtype="Int64"),
            "occurrence_peak_cpu_ncu": [0.10, 0.30, 0.20, 0.05],
            "occurrence_peak_memory_normalized": [0.01, 0.03, 0.02, 0.005],
            "occ_hist_peak_cpu_count": [0, 1, 2, 0],
            "occ_hist_peak_memory_count": [0, 1, 2, 0],
            "target_next_occurrence_start_time_us": pd.array([200, 300, None, None], dtype="Int64"),
            "target_cpu_next_occurrence_peak_ncu": [0.30, 0.20, np.nan, np.nan],
            "target_memory_next_occurrence_peak_normalized": [0.03, 0.02, np.nan, np.nan],
            "rec_cpu_request": [0.50, 0.50, 0.50, np.nan],
            "rec_memory_request": [0.04, 0.04, 0.04, np.nan],
        }
    )
    for resource, history in (("cpu", [0.10, 0.25]), ("memory", [0.01, 0.025])):
        request = occurrences[f"rec_{resource}_request"]
        for suffix in ("mean", "p90", "p95", "p99"):
            occurrences[f"uses_history_{resource}_{suffix}"] = occurrences[f"occ_hist_peak_{resource}_count"] >= 1
            occurrences[f"rec_{resource}_{suffix}"] = [request[0], *history, request[3]]

    ml_predictions = pd.DataFrame(
        {
            "occurrence_id": ["b1", "a1", "a2", "a3"],
            "ml_pred_cpu": [0.07, 0.12, 0.40, 0.15],
            "ml_pred_memory": [0.006, 0.02, 0.01, 0.03],
        }
    )
    return occurrences, ml_predictions, stored_row_level(occurrences, ml_predictions)


def stored_row_level(occurrences, ml_predictions):
    """What the final test stored for the scored rows (a1 and a2), computed independently."""
    frame = occurrences.merge(ml_predictions, on="occurrence_id")
    rows = []
    for _, row in frame[frame["target_next_occurrence_start_time_us"].notna()].iterrows():
        for policy in POLICY_NAMES:
            record = {"occurrence_id": row["occurrence_id"], "recurrence_key": row["recurrence_key"], "policy_name": policy}
            for resource in ("cpu", "memory"):
                if policy == "ML":
                    value = row[f"ml_pred_{resource}"]
                elif policy == "Hybrid":
                    value = max(row[f"ml_pred_{resource}"], row[f"rec_{resource}_p95"])
                else:
                    value = row[f"rec_{resource}_{policy.lower() if policy != 'Request' else 'request'}"]
                actual = row["target_cpu_next_occurrence_peak_ncu" if resource == "cpu" else "target_memory_next_occurrence_peak_normalized"]
                record[f"recommended_{resource}"] = value
                record[f"{resource}_violation"] = float(actual > value)
            rows.append(record)
    return pd.DataFrame(rows)


ALIBABA_POLICY_COLUMNS = {
    "Request": "rec_{r}_request", "Mean": "rec_{r}_mean", "P90": "rec_{r}_p90", "P95": "rec_{r}_p95",
    "P99": "rec_{r}_p99", "ML": "ml_recommended_{r}", "Hybrid": "hybrid_recommended_{r}",
}


def alibaba_sources():
    """Workload G||A runs three times (jobs J2 and J3 start in the same second); G||B runs once (J4).

    J1 -> J2 has both targets; J2 -> J3 has a memory target but an ineligible CPU target;
    J3 and J4 have no next run. J3 has 11 earlier runs; J2 has 9 for CPU (falls back) and
    10 for memory (history); J1 and J4 have none.
    """
    runs = pd.DataFrame(
        {
            "role_key": ["G||J1||A", "G||J3||A", "G||J2||A", "G||J4||B"],  # deliberately unsorted
            "occurrence_id": ["G||J1", "G||J3", "G||J2", "G||J4"],
            "recurrence_key": ["G||A", "G||A", "G||A", "G||B"],
            "start_time_us": [100, 200, 200, 150],
            "observed_cpu": [10.0, np.nan, 30.0, 5.0],
            "peak_memory": [1.0, 2.0, 3.0, 0.5],
            "cpu_target_status": ["available", "no_next_occurrence", "next_occurrence_ineligible_resource", "no_next_occurrence"],
            "memory_target_status": ["available", "no_next_occurrence", "available", "no_next_occurrence"],
            "actual_cpu": [30.0, np.nan, np.nan, np.nan],
            "actual_memory": [3.0, np.nan, 2.0, np.nan],
            "cpu_history_count": pd.array([0, 11, 9, 0], dtype="Int64"),
            "memory_history_count": pd.array([0, 11, 10, 0], dtype="Int64"),
        }
    )
    for resource, request, history in (("cpu", [50.0, 50.0, 50.0, 20.0], 25.0), ("memory", [4.0, 4.0, 4.0, 1.0], 2.5)):
        runs[f"rec_{resource}_request"] = request
        uses_history = runs[f"{resource}_history_count"] >= 10
        for step, suffix in enumerate(("mean", "p90", "p95", "p99")):
            runs[f"uses_history_{resource}_{suffix}"] = uses_history.astype(bool)
            runs[f"rec_{resource}_{suffix}"] = np.where(uses_history, history + step, request)
        runs[f"ml_recommended_{resource}"] = [history * 2, history / 2, history / 2, history / 4]
        runs[f"hybrid_recommended_{resource}"] = np.fmax(runs[f"ml_recommended_{resource}"], runs[f"rec_{resource}_p99"])

    predictions = runs[["role_key", "occurrence_id", "recurrence_key", "cpu_target_status", "actual_cpu",
                        "memory_target_status", "actual_memory",
                        *[c for c in runs.columns if c.startswith(("rec_", "ml_", "hybrid_"))]]].copy()
    targets = runs[["role_key", "occurrence_id", "recurrence_key", "start_time_us", "observed_cpu", "peak_memory",
                    "cpu_target_status", "memory_target_status", "actual_cpu", "actual_memory"]].copy()
    baselines = runs[["role_key", "start_time_us", "cpu_history_count", "memory_history_count",
                      *[c for c in runs.columns if c.startswith(("uses_history_", "rec_"))]]].copy()
    return predictions, targets, baselines, alibaba_summary(predictions)


def alibaba_summary(predictions):
    """Violation rate and valid count per policy, computed independently of the export."""
    records = []
    for policy, template in ALIBABA_POLICY_COLUMNS.items():
        record = {"policy": policy}
        for resource in ("cpu", "memory"):
            actual = predictions[f"actual_{resource}"]
            valid = actual.notna()
            exceeded = actual[valid] > predictions.loc[valid, template.format(r=resource)]
            record[f"valid_{resource}_violation_count"] = int(valid.sum())
            record[f"{resource}_violation_pct"] = float(exceeded.mean() * 100) if valid.any() else np.nan
        records.append(record)
    return pd.DataFrame(records)


def synthetic_contents(status="verified"):
    """A complete bundle built from the synthetic Google and Alibaba sources."""
    datasets = {}
    for dataset_id, result in (
        ("google_clusterdata2019", export_google(*google_sources())),
        ("alibaba_gpu_v2020", export_alibaba(*alibaba_sources())),
    ):
        workloads = export.build_workloads(result.recommendations, dataset_id, "Hybrid")
        datasets[dataset_id] = export.DatasetBundle(
            dataset_info=export.build_dataset_info(dataset_id, result.recommendations, workloads),
            policy_metrics={"dataset_id": dataset_id, "policies": []},
            workloads=workloads,
            recommendations=result.recommendations,
            metadata={"bundle_status": status, "source_run_id": None, "source_mismatches": [],
                      "row_counts": {"workloads": len(workloads), "recommendations": len(result.recommendations)}},
        )
    manifest = export.build_manifest(datasets, {"code_commit": "abc", "code_dirty": False, "timestamp_utc": "2026-11-16T00:00:00Z"})
    return export.BundleContents(manifest=manifest, risk_levels=export.build_risk_levels(), rules={}, datasets=datasets)


FIXTURE_EXPORT_INFO = {
    "code_commit": None,
    "code_dirty": None,
    "timestamp_utc": "2026-11-16T00:00:00Z",
    "python_version": "fixture",
    "pandas_version": "fixture",
    "pyarrow_version": "fixture",
}
FIXTURE_NOTE = "Synthetic test fixture (tests/ui_sources.py); not pipeline results."


def fixture_contents(repo):
    """The committed fixture bundle: synthetic rows with the real committed rules and policy metrics.

    Marked development so it can never be taken for a verified bundle.
    """
    risk_levels = export.build_risk_levels()
    occurrences, ml_predictions, row_level = google_sources()
    predictions, targets, baselines, summary = alibaba_sources()
    sources = {
        "google_clusterdata2019": (
            export_google(occurrences, ml_predictions, row_level),
            export.google_source_fallback_counts(occurrences), "P95", export.GOOGLE_SUMMARY_CSV,
        ),
        "alibaba_gpu_v2020": (
            export_alibaba(predictions, targets, baselines, summary),
            export.alibaba_source_fallback_counts(targets, baselines), "P99", export.ALIBABA_SUMMARY_CSV,
        ),
    }
    datasets = {}
    for dataset_id, (result, source_counts, safeguard, summary_csv) in sources.items():
        reference = SourceReference(dataset_id, (), (), None, None)
        bundle = export._assemble(
            reference, [], "development", result, repo, summary_csv, {}, source_counts, safeguard,
            export._default_policy(risk_levels, dataset_id),
        )
        bundle.metadata["notes"]["fixture"] = FIXTURE_NOTE
        datasets[dataset_id] = bundle
    manifest = export.build_manifest(datasets, {})
    manifest["export"] = dict(FIXTURE_EXPORT_INFO)
    manifest["fixture"] = FIXTURE_NOTE
    return export.BundleContents(manifest=manifest, risk_levels=risk_levels, rules=export.build_rules(repo), datasets=datasets)
