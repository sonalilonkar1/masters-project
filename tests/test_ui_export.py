import hashlib
import json
from pathlib import Path

import pytest

from src.service import export
from src.service.export import (
    ALIBABA_ARTIFACT_MANIFEST,
    ALIBABA_INPUTS,
    ALIBABA_LOCAL_RUN_RECORD,
    ALIBABA_RUN_RECORD,
    GOOGLE_DECISION_MANIFEST,
    GOOGLE_INPUTS,
    SourceVerificationError,
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
