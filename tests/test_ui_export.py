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
