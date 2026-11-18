import copy
import json
from pathlib import Path

import pytest

from src.reporting.artifact_provenance import digest, validate_alibaba_evidence, validate_final_configuration

ROOT = Path(__file__).resolve().parents[1]


def configuration():
    return json.loads((ROOT / "config/cross_dataset_report_final.json").read_text())


def test_final_configuration_preserves_pending_decisions_and_identity():
    config = configuration()
    validate_final_configuration(config)
    assert all(config["datasets"][d]["decision_status"] == "decision_pending" for d in
               ("google_clusterdata2019", "azure_public_vm_v2", "alibaba_clustertrace2018"))


@pytest.mark.parametrize("defect", ["identity", "dataset", "stage", "duplicate", "traversal", "decision"])
def test_final_configuration_rejects_ambiguous_or_unapproved_contract(defect):
    config = copy.deepcopy(configuration())
    spec = config["datasets"]["alibaba_gpu_v2020"]
    if defect == "identity":
        spec.pop("expected_identity")
    elif defect in {"dataset", "stage"}:
        spec["artifact_bindings"][0]["dataset_id" if defect == "dataset" else "stage"] = "wrong"
    elif defect == "duplicate":
        spec["artifact_bindings"][1] = spec["artifact_bindings"][0]
    elif defect == "traversal":
        spec["artifact_bindings"][0]["manifest_path"] = "../decision_manifest.json"
    else:
        config["datasets"]["google_clusterdata2019"]["decision_status"] = "documented_outcome"
    with pytest.raises(ValueError):
        validate_final_configuration(config)


def reader(root=ROOT, overrides=None):
    overrides = overrides or {}
    def raw(path):
        data = overrides.get(path, (root / path).read_bytes())
        return data, {"path": path, "sha256": digest(data)}
    def parsed(path):
        data, ref = raw(path)
        return json.loads(data), ref
    return parsed, raw


def test_real_task8_manifest_links_published_copies_without_physical_bundle():
    spec = configuration()["datasets"]["alibaba_gpu_v2020"]
    result = validate_alibaba_evidence(spec, *reader())
    assert len(result["bindings"]) == 5
    assert result["published_artifact_bytes"] == "verified"
    assert result["external_physical_artifact_bytes"].startswith("UNVERIFIED")
    assert len(result["unverified_items"]) >= 2


@pytest.mark.parametrize("defect", ["dataset", "stage", "duplicate", "identity", "boolean", "generation", "companion", "published"])
def test_task8_evidence_rejects_contradictions(defect):
    spec = configuration()["datasets"]["alibaba_gpu_v2020"]
    path = spec["verification_manifest"]
    manifest = json.loads((ROOT / path).read_text())
    overrides = {}
    if defect == "dataset":
        manifest["dataset_id"] = "wrong"
    elif defect == "stage":
        next(e for e in manifest["artifacts"] if e["path"] == spec["artifact_bindings"][0]["manifest_path"])["stage"] = "wrong"
    elif defect == "duplicate":
        manifest["artifacts"].append(manifest["artifacts"][0])
    elif defect == "identity":
        manifest["final_run_identity"]["run_id"] = "wrong"
    elif defect == "boolean":
        manifest["checks"][0]["ok"] = "True"
    elif defect == "generation":
        manifest["generation_id"] = "wrong"
    elif defect == "companion":
        manifest["companion_files"]["verification_report.md"] = "0" * 64
    else:
        overrides[spec["results"]] = (ROOT / spec["results"]).read_bytes() + b"\n"
    overrides[path] = json.dumps(manifest).encode()
    spec["verification_manifest_sha256"] = digest(overrides[path])
    with pytest.raises(ValueError):
        validate_alibaba_evidence(spec, *reader(overrides=overrides))
