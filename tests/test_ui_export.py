import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.service import export
from src.service.contract import POLICY_NAMES, RECOMMENDATION_COLUMNS, validate_frame
from src.service.export import (
    ALIBABA_ARTIFACT_MANIFEST,
    ALIBABA_INPUTS,
    ALIBABA_LOCAL_RUN_RECORD,
    ALIBABA_RUN_RECORD,
    GOOGLE_DECISION_MANIFEST,
    GOOGLE_INPUTS,
    ExportValidationError,
    SourceVerificationError,
    export_alibaba,
    export_google,
    source_status,
    verify_dataset_sources,
)

RUN_ID = "run-agreed"
DECISION_SHA = "d" * 64


def write(repo: Path, relative: str, content: bytes) -> str:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def run_record_bytes(**overrides) -> bytes:
    record = {
        "run_id": RUN_ID,
        "decision_manifest_sha256": DECISION_SHA,
        "test_target_read_count": 1,
        "test_evaluator_call_count": 1,
    }
    record.update(overrides)
    return json.dumps(record).encode()


@pytest.fixture
def alibaba_repo(tmp_path):
    """A repository whose local Alibaba inputs match the committed references."""
    artifacts = []
    for path in ALIBABA_INPUTS:
        content = run_record_bytes() if path == ALIBABA_LOCAL_RUN_RECORD else f"data {path}".encode()
        artifacts.append({"path": path, "sha256": write(tmp_path, path, content)})
    manifest = {
        "status": "PASS",
        "verified": True,
        "final_run_identity": {"run_id": RUN_ID, "decision_manifest_sha256": DECISION_SHA},
        "artifacts": artifacts,
    }
    write(tmp_path, ALIBABA_ARTIFACT_MANIFEST, json.dumps(manifest).encode())
    write(tmp_path, ALIBABA_RUN_RECORD, run_record_bytes())
    return tmp_path


@pytest.fixture
def google_repo(tmp_path):
    hashes = {path: write(tmp_path, path, f"data {path}".encode()) for path in GOOGLE_INPUTS}
    manifest = {"status": "final", "input_sha256": {"data/processed/google_subset_v1/other.parquet": "0" * 64, **hashes}}
    write(tmp_path, GOOGLE_DECISION_MANIFEST, json.dumps(manifest).encode())
    return tmp_path


def rewrite_manifest(repo: Path, relative: str, change) -> None:
    path = repo / relative
    manifest = json.loads(path.read_text())
    change(manifest)
    path.write_text(json.dumps(manifest))


def reasons(mismatches):
    return sorted((m.path, m.reason) for m in mismatches)


# --- matching inputs -------------------------------------------------------


def test_matching_alibaba_inputs_are_verified(alibaba_repo):
    reference, mismatches = verify_dataset_sources("alibaba_gpu_v2020", alibaba_repo)

    assert mismatches == []
    assert source_status(mismatches, allow_unverified_source=False) == "verified"
    assert reference.run_id == RUN_ID
    assert [item.path for item in reference.inputs] == list(ALIBABA_INPUTS)


def test_matching_google_inputs_are_verified(google_repo):
    reference, mismatches = verify_dataset_sources("google_clusterdata2019", google_repo)

    assert mismatches == []
    assert [item.path for item in reference.inputs] == list(GOOGLE_INPUTS)
    assert reference.decision_manifest_sha256 == export.file_sha256(google_repo / GOOGLE_DECISION_MANIFEST)


# --- differing or missing inputs ---------------------------------------------


def test_changed_input_is_refused(alibaba_repo):
    changed = "data/processed/alibaba_gpu_v2020_targets/test.parquet"
    (alibaba_repo / changed).write_bytes(b"older run")

    _, mismatches = verify_dataset_sources("alibaba_gpu_v2020", alibaba_repo)

    assert reasons(mismatches) == [(changed, "checksum")]
    with pytest.raises(SourceVerificationError, match="targets/test.parquet: checksum"):
        source_status(mismatches, allow_unverified_source=False)


def test_missing_input_is_refused(google_repo):
    (google_repo / GOOGLE_INPUTS[1]).unlink()

    _, mismatches = verify_dataset_sources("google_clusterdata2019", google_repo)

    assert reasons(mismatches) == [(GOOGLE_INPUTS[1], "missing")]
    with pytest.raises(SourceVerificationError, match="1 input"):
        source_status(mismatches, allow_unverified_source=False)


def test_every_mismatch_is_listed(alibaba_repo):
    for path in ALIBABA_INPUTS[0], ALIBABA_INPUTS[2]:
        (alibaba_repo / path).write_bytes(b"older run")

    _, mismatches = verify_dataset_sources("alibaba_gpu_v2020", alibaba_repo)

    with pytest.raises(SourceVerificationError) as error:
        source_status(mismatches, allow_unverified_source=False)
    assert "2 input(s)" in str(error.value)
    assert ALIBABA_INPUTS[0] in str(error.value) and ALIBABA_INPUTS[2] in str(error.value)


# --- local run record --------------------------------------------------------


def replace_local_run_record(repo: Path, content: bytes) -> None:
    """Replace the local run record and update its committed checksum, so only the field check can fail."""
    sha = write(repo, ALIBABA_LOCAL_RUN_RECORD, content)

    def change(manifest):
        for artifact in manifest["artifacts"]:
            if artifact["path"] == ALIBABA_LOCAL_RUN_RECORD:
                artifact["sha256"] = sha

    rewrite_manifest(repo, ALIBABA_ARTIFACT_MANIFEST, change)


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"run_id": "run-older"}, "run_record:run_id"),
        ({"decision_manifest_sha256": "e" * 64}, "run_record:decision_manifest_sha256"),
        ({"test_target_read_count": 2}, "run_record:test_target_read_count"),
        ({"test_evaluator_call_count": True}, "run_record:test_evaluator_call_count"),
        ({"test_evaluator_call_count": "1"}, "run_record:test_evaluator_call_count"),
    ],
)
def test_run_record_fields_are_checked(alibaba_repo, overrides, reason):
    replace_local_run_record(alibaba_repo, run_record_bytes(**overrides))

    _, mismatches = verify_dataset_sources("alibaba_gpu_v2020", alibaba_repo)

    assert reasons(mismatches) == [(ALIBABA_LOCAL_RUN_RECORD, reason)]


def test_run_record_without_run_id_is_a_mismatch_not_a_crash(alibaba_repo):
    record = json.loads(run_record_bytes())
    del record["run_id"]
    (alibaba_repo / ALIBABA_LOCAL_RUN_RECORD).write_text(json.dumps(record))

    _, mismatches = verify_dataset_sources("alibaba_gpu_v2020", alibaba_repo)

    assert reasons(mismatches) == [
        (ALIBABA_LOCAL_RUN_RECORD, "checksum"),
        (ALIBABA_LOCAL_RUN_RECORD, "run_record:run_id"),
    ]


# --- committed references ----------------------------------------------------


def test_unverified_manifest_is_refused(alibaba_repo):
    rewrite_manifest(alibaba_repo, ALIBABA_ARTIFACT_MANIFEST, lambda m: m.update(verified=False))

    with pytest.raises(SourceVerificationError, match="not a passing verification"):
        verify_dataset_sources("alibaba_gpu_v2020", alibaba_repo)


def test_references_that_disagree_are_refused(alibaba_repo):
    write(alibaba_repo, ALIBABA_RUN_RECORD, run_record_bytes(run_id="run-other"))

    with pytest.raises(SourceVerificationError, match="disagree on run_id"):
        verify_dataset_sources("alibaba_gpu_v2020", alibaba_repo)


def test_manifest_without_an_input_checksum_is_refused(alibaba_repo):
    rewrite_manifest(
        alibaba_repo,
        ALIBABA_ARTIFACT_MANIFEST,
        lambda m: m.update(artifacts=[a for a in m["artifacts"] if "targets" not in a["path"]]),
    )

    with pytest.raises(SourceVerificationError, match="no checksum"):
        verify_dataset_sources("alibaba_gpu_v2020", alibaba_repo)


def test_google_manifest_must_be_final(google_repo):
    rewrite_manifest(google_repo, GOOGLE_DECISION_MANIFEST, lambda m: m.update(status="draft"))

    with pytest.raises(SourceVerificationError, match="not 'final'"):
        verify_dataset_sources("google_clusterdata2019", google_repo)


def test_missing_reference_file_is_refused(google_repo):
    (google_repo / GOOGLE_DECISION_MANIFEST).unlink()

    with pytest.raises(SourceVerificationError, match="reference file missing"):
        verify_dataset_sources("google_clusterdata2019", google_repo)


def test_reference_values_are_read_not_hard_coded(google_repo):
    replacement = b"a newly agreed run"
    sha = write(google_repo, GOOGLE_INPUTS[0], replacement)
    rewrite_manifest(google_repo, GOOGLE_DECISION_MANIFEST, lambda m: m["input_sha256"].update({GOOGLE_INPUTS[0]: sha}))

    _, mismatches = verify_dataset_sources("google_clusterdata2019", google_repo)

    assert mismatches == []


# --- development mode --------------------------------------------------------


def test_development_mode_keeps_every_mismatch(alibaba_repo):
    (alibaba_repo / ALIBABA_INPUTS[0]).unlink()
    (alibaba_repo / ALIBABA_INPUTS[3]).write_bytes(b"older run")

    _, mismatches = verify_dataset_sources("alibaba_gpu_v2020", alibaba_repo)

    assert source_status(mismatches, allow_unverified_source=True) == "development"
    assert reasons(mismatches) == sorted([(ALIBABA_INPUTS[0], "missing"), (ALIBABA_INPUTS[3], "checksum")])


def test_unknown_dataset():
    with pytest.raises(ValueError, match="unknown dataset"):
        verify_dataset_sources("azure_vm", Path("."))


# --- Google export -------------------------------------------------------------

def google_sources():
    """Workload A runs three times (histories 0, 1, 2); workload B runs once with no request.

    Recommendations are chosen so every basis case appears: A's first run falls
    back to its request, later runs use history, and B has no safeguard at all.
    """
    occurrences = pd.DataFrame(
        {
            "occurrence_key": ["a1", "a2", "a3", "b1"],
            "occurrence_id": ["a1", "a2", "a3", "b1"],
            "recurrence_key": ["u||A", "u||A", "u||A", "u||B"],
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


def row(recommendations, occurrence_id, policy):
    match = recommendations[(recommendations["occurrence_id"] == occurrence_id) & (recommendations["policy"] == policy)]
    assert len(match) == 1
    return match.iloc[0]


def test_google_export_shape_and_contract():
    result = export_google(*google_sources())
    recommendations = result.recommendations

    assert len(recommendations) == 4 * len(POLICY_NAMES)
    assert list(recommendations["policy"].unique()) == list(POLICY_NAMES)
    validate_frame(recommendations, RECOMMENDATION_COLUMNS, "google")
    assert recommendations["role_key"].isna().all()


def test_google_target_identity_and_status():
    recommendations = export_google(*google_sources()).recommendations

    first = row(recommendations, "a1", "P95")
    assert first["target_occurrence_id"] == "a2"
    assert first["target_start_time_us"] == 200
    assert first["cpu_target_status"] == "available"
    last = row(recommendations, "a3", "P95")
    assert pd.isna(last["target_occurrence_id"]) and pd.isna(last["actual_cpu"])
    assert last["cpu_target_status"] == "no_next_occurrence"


def test_google_one_latest_run_per_workload():
    recommendations = export_google(*google_sources()).recommendations
    latest = recommendations[recommendations["is_latest"]]

    assert sorted(latest["occurrence_id"].unique()) == ["a3", "b1"]
    assert latest.groupby("policy").size().eq(2).all()


def test_google_basis_and_history_counts():
    recommendations = export_google(*google_sources()).recommendations

    assert row(recommendations, "a1", "P95")["cpu_basis"] == "request_fallback"
    assert row(recommendations, "a1", "P95")["recommended_cpu"] == 0.50
    assert row(recommendations, "a2", "P90")["memory_basis"] == "history"
    assert row(recommendations, "a2", "P90")["memory_history_run_count"] == 1
    assert row(recommendations, "a2", "Request")["cpu_basis"] == "request"
    assert pd.isna(row(recommendations, "a2", "Request")["cpu_history_run_count"])
    assert row(recommendations, "a2", "ML")["cpu_basis"] == "model"
    assert row(recommendations, "a2", "Hybrid")["cpu_basis"] == "history"


def test_google_hybrid_applies_rule_including_unscored_rows():
    recommendations = export_google(*google_sources()).recommendations

    assert row(recommendations, "a2", "Hybrid")["recommended_cpu"] == 0.40  # ML above P95
    assert row(recommendations, "a3", "Hybrid")["recommended_cpu"] == 0.25  # unscored latest run, P95 above ML


def test_google_hybrid_without_safeguard_is_ml_with_model_basis():
    result = export_google(*google_sources())
    hybrid = row(result.recommendations, "b1", "Hybrid")

    assert hybrid["recommended_cpu"] == 0.07
    assert hybrid["cpu_basis"] == "model" and hybrid["memory_basis"] == "model"
    assert pd.isna(row(result.recommendations, "b1", "P95")["recommended_cpu"])
    assert result.notes["hybrid_safeguard_missing"] == {"cpu": 1, "memory": 1}


def test_google_exceeded_copied_and_null_when_unscored():
    occurrences, ml_predictions, row_level = google_sources()
    # A stored flag that disagrees with actual > recommended proves it is copied, not recomputed.
    pick = (row_level["occurrence_id"] == "a2") & (row_level["policy_name"] == "Mean")
    row_level.loc[pick, "cpu_violation"] = 1.0 - row_level.loc[pick, "cpu_violation"]

    recommendations = export_google(occurrences, ml_predictions, row_level).recommendations

    assert row(recommendations, "a2", "Mean")["cpu_exceeded"] == bool(row_level.loc[pick, "cpu_violation"].iloc[0])
    assert pd.isna(row(recommendations, "a3", "P95")["cpu_exceeded"])


def test_google_null_request_keeps_null_not_zero():
    recommendations = export_google(*google_sources()).recommendations

    assert pd.isna(row(recommendations, "b1", "Request")["request_cpu"])
    assert pd.isna(row(recommendations, "b1", "Request")["recommended_cpu"])


def test_google_stored_hybrid_mismatch_is_refused():
    occurrences, ml_predictions, row_level = google_sources()
    row_level.loc[row_level["policy_name"] == "Hybrid", "recommended_memory"] += 0.001

    with pytest.raises(ExportValidationError, match=r"memory recommendations differ .*Hybrid"):
        export_google(occurrences, ml_predictions, row_level)


def test_google_target_not_matching_next_run_is_refused():
    occurrences, ml_predictions, row_level = google_sources()
    occurrences.loc[0, "target_next_occurrence_start_time_us"] = 250

    with pytest.raises(ExportValidationError, match="start times differ"):
        export_google(occurrences, ml_predictions, row_level)


def test_google_target_value_not_matching_next_peak_is_refused():
    occurrences, ml_predictions, row_level = google_sources()
    occurrences.loc[0, "target_cpu_next_occurrence_peak_ncu"] = 0.99

    with pytest.raises(ExportValidationError, match="cpu targets differ"):
        export_google(occurrences, ml_predictions, row_level)


def test_google_duplicate_or_unmatched_predictions_are_refused():
    occurrences, ml_predictions, row_level = google_sources()

    with pytest.raises(ExportValidationError, match="duplicate"):
        export_google(occurrences, pd.concat([ml_predictions, ml_predictions.iloc[[0]]]), row_level)
    with pytest.raises(ExportValidationError, match="different occurrences"):
        export_google(occurrences, ml_predictions.iloc[1:], row_level)


# --- Alibaba export ------------------------------------------------------------

ALIBABA_POLICY_COLUMNS = {
    "Request": "rec_{r}_request", "Mean": "rec_{r}_mean", "P90": "rec_{r}_p90", "P95": "rec_{r}_p95",
    "P99": "rec_{r}_p99", "ML": "ml_recommended_{r}", "Hybrid": "hybrid_recommended_{r}",
}


def alibaba_sources():
    """Workload A runs three times (a2 and a3 start in the same second); workload B runs once.

    a1 -> a2 has both targets; a2 -> a3 has a memory target but an ineligible CPU target;
    a3 and b1 have no next run. a2 and a3 have at least 10 earlier runs, a1 and b1 none.
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
            "cpu_history_count": pd.array([0, 11, 10, 0], dtype="Int64"),
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


def test_alibaba_export_shape_and_contract():
    recommendations = export_alibaba(*alibaba_sources()).recommendations

    assert len(recommendations) == 4 * len(POLICY_NAMES)
    validate_frame(recommendations, RECOMMENDATION_COLUMNS, "alibaba")
    assert recommendations["role_key"].notna().all()
    assert set(recommendations["workload_id"]) == {"G||A", "G||B"}


def test_alibaba_successor_follows_task4_order_with_same_second_tie():
    recommendations = export_alibaba(*alibaba_sources()).recommendations

    first = row(recommendations, "G||J1", "P99")
    assert first["target_occurrence_id"] == "G||J2" and first["target_start_time_us"] == 200
    tied = row(recommendations, "G||J2", "P99")  # same second as J3; J2 sorts first by occurrence_id
    assert tied["target_occurrence_id"] == "G||J3"
    assert tied["cpu_target_status"] == "next_occurrence_ineligible_resource"
    assert pd.isna(tied["actual_cpu"]) and pd.isna(tied["cpu_exceeded"])
    assert tied["memory_target_status"] == "available" and tied["actual_memory"] == 2.0


def test_alibaba_latest_rows():
    recommendations = export_alibaba(*alibaba_sources()).recommendations
    latest = recommendations[recommendations["is_latest"]]

    assert sorted(latest["occurrence_id"].unique()) == ["G||J3", "G||J4"]
    assert latest["target_occurrence_id"].isna().all()


def test_alibaba_basis_and_counts():
    recommendations = export_alibaba(*alibaba_sources()).recommendations

    assert row(recommendations, "G||J1", "P99")["memory_basis"] == "request_fallback"
    assert row(recommendations, "G||J2", "P99")["memory_basis"] == "history"
    assert row(recommendations, "G||J2", "P99")["memory_history_run_count"] == 10
    assert row(recommendations, "G||J2", "Hybrid")["cpu_basis"] == "history"
    assert row(recommendations, "G||J4", "Hybrid")["cpu_basis"] == "request_fallback"
    assert row(recommendations, "G||J2", "ML")["cpu_basis"] == "model"
    assert pd.isna(row(recommendations, "G||J2", "Request")["cpu_history_run_count"])


def test_alibaba_values_copied_and_exceeded_follows_rule():
    recommendations = export_alibaba(*alibaba_sources()).recommendations
    first = row(recommendations, "G||J1", "ML")

    assert first["recommended_memory"] == 5.0
    assert bool(first["memory_exceeded"]) is False  # 3.0 > 5.0 is false
    assert bool(row(recommendations, "G||J1", "Mean")["memory_exceeded"]) is False
    assert bool(row(recommendations, "G||J2", "ML")["memory_exceeded"]) is True  # 2.0 > 1.25


def test_alibaba_summary_mismatch_is_refused():
    predictions, targets, baselines, summary = alibaba_sources()
    summary.loc[summary["policy"] == "P95", "memory_violation_pct"] += 1.0

    with pytest.raises(ExportValidationError, match="P95 memory"):
        export_alibaba(predictions, targets, baselines, summary)


def test_alibaba_hybrid_not_max_of_ml_and_p99_is_refused():
    predictions, targets, baselines, summary = alibaba_sources()
    predictions.loc[0, "hybrid_recommended_cpu"] += 1.0

    with pytest.raises(ExportValidationError, match="Hybrid is not max"):
        export_alibaba(predictions, targets, baselines, summary)


def test_alibaba_baseline_copy_mismatch_is_refused():
    predictions, targets, baselines, summary = alibaba_sources()
    baselines.loc[1, "rec_memory_p90"] += 1.0

    with pytest.raises(ExportValidationError, match="rec_memory_p90 differs"):
        export_alibaba(predictions, targets, baselines, summary)


def test_alibaba_target_not_matching_next_run_is_refused():
    predictions, targets, baselines, summary = alibaba_sources()
    targets.loc[targets["role_key"] == "G||J2||A", "peak_memory"] = 9.0

    with pytest.raises(ExportValidationError, match="memory targets differ"):
        export_alibaba(predictions, targets, baselines, summary)


def test_alibaba_status_disagreement_is_refused():
    predictions, targets, baselines, summary = alibaba_sources()
    targets.loc[0, "memory_target_status"] = "no_next_occurrence"

    with pytest.raises(ExportValidationError, match="memory_target_status differs"):
        export_alibaba(predictions, targets, baselines, summary)


def test_alibaba_duplicate_or_unmatched_runs_are_refused():
    predictions, targets, baselines, summary = alibaba_sources()

    with pytest.raises(ExportValidationError, match="duplicate"):
        export_alibaba(predictions, pd.concat([targets, targets.iloc[[0]]]), baselines, summary)
    with pytest.raises(ExportValidationError, match="cover different runs"):
        export_alibaba(predictions, targets, baselines.iloc[1:], summary)


# --- Bundle contents -------------------------------------------------------------


def test_google_workloads_summary():
    recommendations = export_google(*google_sources()).recommendations
    workloads = export.build_workloads(recommendations, "google_clusterdata2019", "Hybrid").set_index("workload_id")

    assert list(workloads.index) == ["u||A", "u||B"]
    a = workloads.loc["u||A"]
    assert (a["test_run_count"], a["scored_run_count"]) == (3, 2)
    assert (a["first_start_time_us"], a["last_start_time_us"]) == (100, 300)
    assert a["latest_occurrence_id"] == "a3" and a["latest_uses_history"] and a["has_scored_history"]
    b = workloads.loc["u||B"]
    assert not b["latest_uses_history"] and not b["has_scored_history"]  # Hybrid basis is "model", not history
    assert a["display_name"] == "u||A"


def test_alibaba_display_name_reads_as_group_and_task():
    recommendations = export_alibaba(*alibaba_sources()).recommendations
    workloads = export.build_workloads(recommendations, "alibaba_gpu_v2020", "Hybrid")

    assert list(workloads["display_name"]) == ["G / A", "G / B"]
    assert list(workloads["latest_occurrence_id"]) == ["G||J3", "G||J4"]


def test_fallback_counts_match_source_flags():
    occurrences, ml_predictions, row_level = google_sources()
    result = export_google(occurrences, ml_predictions, row_level)
    counts = export.bundle_fallback_counts(result.recommendations)

    assert counts["P95"] == {"cpu": 1, "memory": 1}  # b1 has no history
    assert counts["Hybrid"] == {"cpu": 0, "memory": 0}  # b1's Hybrid has no safeguard: basis "model"
    export.check_fallback_counts(
        counts, export.google_source_fallback_counts(occurrences), "P95", result.notes["hybrid_safeguard_missing"]
    )


def test_alibaba_fallback_counts_match_source_flags():
    predictions, targets, baselines, summary = alibaba_sources()
    counts = export.bundle_fallback_counts(export_alibaba(predictions, targets, baselines, summary).recommendations)

    assert counts["P99"] == {"cpu": 1, "memory": 1}  # J4 has no history; J3 has 11 earlier runs
    export.check_fallback_counts(counts, export.alibaba_source_fallback_counts(targets, baselines), "P99", {})


def test_fallback_count_difference_is_refused():
    occurrences, ml_predictions, row_level = google_sources()
    counts = export.bundle_fallback_counts(export_google(occurrences, ml_predictions, row_level).recommendations)
    counts["P90"]["memory"] += 1

    with pytest.raises(ExportValidationError, match="latest-run fallback for P90"):
        export.check_fallback_counts(counts, export.google_source_fallback_counts(occurrences), "P95", {"cpu": 1, "memory": 1})


def write_summary(path: Path, rows: list[str]) -> Path:
    path.write_text("policy,row_count,cpu_violation_pct,memory_violation_pct,any_resource_metric_reported\n" + "\n".join(rows) + "\n")
    return path


def test_policy_metrics_copy_exactly(tmp_path):
    rows = [f"{name},10,{i}.125,,False" for i, name in enumerate(POLICY_NAMES)]
    rows[-1] = "Hybrid,10,3.621296401407651,3.17799014823054,False"
    metrics = export.build_policy_metrics(write_summary(tmp_path / "summary.csv", rows), "alibaba_gpu_v2020")

    hybrid = metrics["policies"][-1]
    assert hybrid == {
        "policy": "Hybrid", "row_count": 10, "cpu_violation_pct": 3.621296401407651,
        "memory_violation_pct": 3.17799014823054, "any_resource_metric_reported": False, "policy_id": "hybrid",
    }
    assert metrics["policies"][0]["memory_violation_pct"] is None  # empty cell stays null, not 0


def test_policy_metrics_wrong_policies_refused(tmp_path):
    rows = [f"{name},10,1.0,1.0,False" for name in POLICY_NAMES if name != "Mean"]

    with pytest.raises(ExportValidationError, match="expected"):
        export.build_policy_metrics(write_summary(tmp_path / "summary.csv", rows), "google_clusterdata2019")


def test_committed_summaries_copy_exactly():
    root = Path(__file__).resolve().parents[1]
    for dataset_id, path in (("google_clusterdata2019", export.GOOGLE_SUMMARY_CSV), ("alibaba_gpu_v2020", export.ALIBABA_SUMMARY_CSV)):
        metrics = export.build_policy_metrics(root / path, dataset_id)
        assert [row["policy"] for row in metrics["policies"]] == list(POLICY_NAMES)


def test_rules_from_committed_records():
    rules = export.build_rules(Path(__file__).resolve().parents[1])

    assert rules["google_clusterdata2019"]["min_runs"] == 1
    assert rules["google_clusterdata2019"]["hybrid_safeguard_policy"] == "P95"
    assert rules["alibaba_gpu_v2020"]["min_runs"] == 10
    assert rules["alibaba_gpu_v2020"]["hybrid_safeguard_policy"] == "P99"


def test_dataset_info_and_risk_levels():
    recommendations = export_alibaba(*alibaba_sources()).recommendations
    workloads = export.build_workloads(recommendations, "alibaba_gpu_v2020", "Hybrid")
    info = export.build_dataset_info("alibaba_gpu_v2020", recommendations, workloads)

    assert info["resources"]["cpu"]["semantics"] == "next_occurrence_lifetime_average"
    assert info["primary_resource"] == "memory"
    assert info["population"] == {
        "test_runs": 4, "workloads": 2, "scored_runs_cpu": 1, "scored_runs_memory": 2, "workloads_with_history_latest": 1,
    }
    risk_levels = export.build_risk_levels()
    assert risk_levels["datasets"]["google_clusterdata2019"]["restrictive"] == {"policy": "Hybrid", "policy_id": "hybrid"}


def test_metadata_records_status_and_mismatches(alibaba_repo):
    (alibaba_repo / ALIBABA_INPUTS[2]).write_bytes(b"older run")
    reference, mismatches = verify_dataset_sources("alibaba_gpu_v2020", alibaba_repo)
    result = export_alibaba(*alibaba_sources())
    workloads = export.build_workloads(result.recommendations, "alibaba_gpu_v2020", "Hybrid")

    metadata = export.build_metadata(
        reference, mismatches, source_status(mismatches, True), {}, {}, result, workloads,
        export.bundle_fallback_counts(result.recommendations),
    )

    assert metadata["bundle_status"] == "development"
    assert metadata["source_mismatches"][0]["path"] == ALIBABA_INPUTS[2]
    assert metadata["source_run_id"] == RUN_ID
    assert metadata["row_counts"] == {"recommendations": 28, "workloads": 2, "test_runs": 4}
    json.dumps(metadata)  # serialisable as is
