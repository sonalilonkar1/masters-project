"""Task 12 PR 1 uses fabricated summaries, never evaluates target rows."""

from collections import Counter
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from scripts import build_final_cross_dataset_report as report


@pytest.fixture
def inputs(tmp_path):
    datasets = {}
    for dataset in report.ORDER:
        spec = {"completion": "deferred", "reason": "Synthetic test scope only"}
        if dataset in (report.GOOGLE, report.ALIBABA):
            metadata = tmp_path / f"{dataset}.json"
            metadata.write_text(json.dumps({
                "dataset_id": dataset,
                "profile": report.DEFAULT_CAPABILITY_REGISTRY[dataset].to_dict(),
            }))
            frame = pd.DataFrame({
                "policy": list(reversed(report.POLICIES)),
                "row_count": [10] * 7,
                "valid_cpu_violation_count": [8] * 7,
                "valid_memory_violation_count": [9] * 7,
                "valid_cpu_utilization_count": [7] * 7,
                "valid_memory_utilization_count": [8] * 7,
                "cpu_violation_pct": [25.0] * 7,
                "memory_violation_pct": [100 / 9] * 7,
                "average_cpu_utilization": [None, .4, .3, .4, .5, .6, .7],
                "average_memory_utilization": [.5] * 7,
                "average_cpu_waste": [.1] * 7,
                "average_memory_waste": [.2] * 7,
            })
            if dataset == report.ALIBABA:
                frame["cpu_result_semantics"] = "average_usage"
                frame["primary_resource"] = "memory"
                frame["any_resource_metric_reported"] = False
            else:
                frame["any_resource_violation_pct"] = 30.0
                frame["valid_any_resource_violation_count"] = 8
            result = tmp_path / f"{dataset}.csv"
            frame.to_csv(result, index=False)
            spec.update(completion="pipeline_artifacts_available", metadata=str(metadata), results=str(result))
        datasets[dataset] = spec
    return {"datasets": datasets}


def build(config, out, **kwargs):
    return report.build_report(config, report.REPO_ROOT, out, **kwargs)


def snapshot(directory):
    return {p.relative_to(directory).as_posix(): p.read_bytes()
            for p in directory.rglob("*") if p.is_file()}


def test_deterministic_outputs_and_unchanged_inputs(inputs, tmp_path):
    originals = {Path(s[k]): Path(s[k]).read_bytes() for s in inputs["datasets"].values()
                 for k in ("results", "metadata") if k in s}
    build(inputs, tmp_path / "a")
    build(inputs, tmp_path / "b")
    assert snapshot(tmp_path / "a") == snapshot(tmp_path / "b")
    assert all(p.read_bytes() == data for p, data in originals.items())


def test_labels_units_denominators_and_memory_first(inputs, tmp_path):
    out = tmp_path / "report"
    build(inputs, out)
    text = (out / "report.md").read_text()
    alibaba = text.split("## alibaba_gpu_v2020")[1]
    assert alibaba.index("### memory") < alibaba.index("### cpu")
    table = pd.read_csv(out / report.ALIBABA / "results.csv")
    assert list(table.resource.drop_duplicates()) == ["memory", "cpu"]
    assert list(table.policy.drop_duplicates()) == list(report.POLICIES)
    assert table.loc[table.resource.eq("cpu"), "semantics"].eq(report.CPU_LABEL).all()
    assert table.loc[table.resource.eq("memory") & table.metric.eq("violation_pct"), "denominator"].eq(9).all()
    assert table.loc[table.resource.eq("cpu") & table.metric.eq("violation_pct"), "denominator"].eq(8).all()
    assert table.loc[table.metric.eq("average_waste") & table.resource.eq("cpu"), "unit"].eq("percent_of_vcpu").all()
    assert table.loc[table.metric.eq("average_waste") & table.resource.eq("memory"), "unit"].eq("gb").all()
    cpu_figure = (out / report.ALIBABA / "02_cpu.svg").read_text()
    assert report.CPU_LABEL in cpu_figure
    assert all(line == line.rstrip() for line in cpu_figure.splitlines())
    google = pd.read_csv(out / report.GOOGLE / "results.csv")
    waste = google.loc[google.metric.eq("average_waste")]
    assert set(waste.unit) == {"ncu", "normalized"}
    assert google.loc[google.resource.eq("cpu") & google.metric.eq("average_utilization"), "value"].isna().sum() == 1
    assert waste.denominator.isna().all()
    assert waste.denominator_status.eq("not reported by source").all()


def test_every_reported_value_traces_to_exact_source_cell(inputs, tmp_path):
    out = tmp_path / "out"
    provenance = build(inputs, out)
    receipts = {s["path"]: s["sha256"] for s in provenance["sources"]}
    for dataset in (report.GOOGLE, report.ALIBABA):
        table = pd.read_csv(out / dataset / "results.csv")
        for _, row in table.iterrows():
            assert receipts[row.source_path] == row.source_sha256
            source = pd.read_csv(row.source_path)
            expected = source.loc[int(row.source_csv_row) - 2, row.source_column]
            if pd.isna(expected):
                assert pd.isna(row.value)
            else:
                assert row.value == pytest.approx(expected, rel=1e-15)
    for output in provenance["outputs"]:
        assert report.sha256(out / output["path"]) == output["sha256"]


@pytest.mark.parametrize("column", ["gpu_violation_pct", "any_resource_violation_pct"])
def test_unsupported_alibaba_metrics_fail_without_writing(inputs, tmp_path, column):
    path = Path(inputs["datasets"][report.ALIBABA]["results"])
    frame = pd.read_csv(path)
    frame[column] = 1.0
    frame.to_csv(path, index=False)
    with pytest.raises(report.ReportError, match="unsupported metrics"):
        build(inputs, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_no_combined_scores_or_rankings(inputs, tmp_path):
    out = tmp_path / "out"
    build(inputs, out)
    for name in ("contract_comparison.csv", "comparability.csv", "dataset_status.csv"):
        frame = pd.read_csv(out / name)
        assert not any("rank" in c or "violation" in c or "utilization" in c or "accuracy" in c
                       for c in frame.columns)
    assert not list(out.glob("*.svg"))
    for path in out.glob("*/results.csv"):
        frame = pd.read_csv(path)
        assert frame.dataset_id.nunique() == 1
        assert "rank" not in frame
    assert report.NONCOMPARABILITY in (out / "report.md").read_text()


def test_missing_results_are_pending_or_strict_error(inputs, tmp_path):
    Path(inputs["datasets"][report.GOOGLE]["results"]).unlink()
    build(inputs, tmp_path / "pending")
    statuses = pd.read_csv(tmp_path / "pending/dataset_status.csv").set_index("dataset_id")
    assert statuses.loc[report.GOOGLE, "report_status"] == "pending"
    assert not (tmp_path / "pending" / report.GOOGLE).exists()
    with pytest.raises(report.ReportError, match="missing final results"):
        build(inputs, tmp_path / "strict", strict=True)


@pytest.mark.parametrize("defect", ["column", "policy", "duplicate", "denominator", "cpu_label"])
def test_incomplete_or_invalid_summaries_fail(inputs, tmp_path, defect):
    path = Path(inputs["datasets"][report.ALIBABA]["results"])
    frame = pd.read_csv(path)
    if defect == "column":
        frame = frame.drop(columns="valid_memory_violation_count")
    elif defect == "policy":
        frame = frame.iloc[:-1]
    elif defect == "duplicate":
        frame = pd.concat([frame, frame.iloc[:1]])
    elif defect == "denominator":
        frame["valid_memory_violation_count"] = 11
    else:
        frame["cpu_result_semantics"] = "peak"
    frame.to_csv(path, index=False)
    with pytest.raises(report.ReportError):
        build(inputs, tmp_path / "out")


def test_sensitivity_cuts_and_group_counts_preserved(inputs, tmp_path):
    spec = inputs["datasets"][report.ALIBABA]
    frame = pd.read_csv(spec["results"])
    sensitivity = pd.concat([frame.assign(sensitivity=cut, n_groups=2) for cut in report.CUTS])
    path = tmp_path / "sensitivity.csv"
    sensitivity.to_csv(path, index=False)
    spec["sensitivity"] = str(path)
    build(inputs, tmp_path / "out")
    result = pd.read_csv(tmp_path / "out" / report.ALIBABA / "sensitivity.csv")
    assert set(result.sensitivity) == set(report.CUTS)
    assert result.source_n_groups.eq(2).all()
    assert result.loc[result.resource.eq("cpu"), "semantics"].eq(report.CPU_LABEL).all()
    assert Counter(Path(name).suffix for name in snapshot(tmp_path / "out")) == {
        ".csv": 12, ".md": 12, ".svg": 5, ".json": 1,
    }


def test_upstream_verification_requires_matching_complete_checksums(inputs, tmp_path):
    spec = inputs["datasets"][report.ALIBABA]
    manifest = {"dataset_id": report.ALIBABA, "verified": True,
                "checks": [{"name": "fixture", "ok": True}],
                "artifacts": [{"path": spec[k], "sha256": report.sha256(Path(spec[k]))}
                              for k in ("results", "metadata")]}
    path = tmp_path / "verification.json"
    path.write_text(json.dumps(manifest))
    spec["verification_manifest"] = str(path)
    build(inputs, tmp_path / "ok")
    statuses = pd.read_csv(tmp_path / "ok/dataset_status.csv").set_index("dataset_id")
    assert statuses.loc[report.ALIBABA, "report_status"] == "upstream_verified_inputs"
    manifest["artifacts"][0]["sha256"] = "0" * 64
    path.write_text(json.dumps(manifest))
    with pytest.raises(report.ReportError, match="does not match"):
        build(inputs, tmp_path / "bad")


@pytest.mark.parametrize("defect", ["missing_inventory", "no_checks", "failed_check", "failed_verification"])
def test_incomplete_upstream_verification_cannot_promote_inputs(inputs, tmp_path, defect):
    spec = inputs["datasets"][report.ALIBABA]
    manifest = {"dataset_id": report.ALIBABA, "verified": True,
                "checks": [{"name": "fixture", "ok": True}],
                "artifacts": [{"path": spec[k], "sha256": report.sha256(Path(spec[k]))}
                              for k in ("results", "metadata")]}
    if defect == "missing_inventory":
        manifest["artifacts"] = []
    elif defect == "no_checks":
        manifest["checks"] = []
    elif defect == "failed_check":
        manifest["checks"][0]["ok"] = False
    else:
        manifest["verified"] = False
    path = tmp_path / "verification.json"
    path.write_text(json.dumps(manifest))
    spec["verification_manifest"] = str(path)
    with pytest.raises(report.ReportError):
        build(inputs, tmp_path / "out")


def test_optional_datasets_only_report_scope_and_cannot_accept_scores(inputs, tmp_path):
    inputs["datasets"]["azure_public_vm_v2"]["results"] = inputs["datasets"][report.GOOGLE]["results"]
    with pytest.raises(report.ReportError, match="scope evidence only"):
        build(inputs, tmp_path / "out")


def test_no_overwrite_and_metadata_identity_required(inputs, tmp_path):
    out = tmp_path / "out"
    build(inputs, out)
    old = snapshot(out)
    with pytest.raises(report.ReportError, match="new or empty"):
        build(inputs, out)
    assert snapshot(out) == old
    path = Path(inputs["datasets"][report.GOOGLE]["metadata"])
    path.write_text(json.dumps({"dataset_id": report.ALIBABA}))
    with pytest.raises(report.ReportError, match="dataset_id mismatch"):
        build(inputs, tmp_path / "bad")


def alternate_inputs(inputs, tmp_path):
    root = tmp_path / "alternate-checkout"
    config = json.loads(json.dumps(inputs))
    for spec in config["datasets"].values():
        for key in ("results", "metadata"):
            if key in spec:
                original = Path(spec[key])
                relative = Path("artifacts") / original.name
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(original.read_bytes())
                spec[key] = relative.as_posix()
    # Distinguish the selected artifact root from the original fixture inputs.
    csv = root / config["datasets"][report.GOOGLE]["results"]
    frame = pd.read_csv(csv)
    frame["cpu_violation_pct"] = 37.5
    frame.to_csv(csv, index=False)
    return root, config


def test_alternate_root_cli_records_executing_code_and_resolves_artifacts(inputs, tmp_path):
    root, config = alternate_inputs(inputs, tmp_path)
    decoys = {
        "scripts/build_final_cross_dataset_report.py": "raise AssertionError('decoy generator executed')\n",
        "src/canonical/schema.py": 'DEFAULT_CAPABILITY_REGISTRY = {"decoy": "not the imported registry"}\n',
        "config/dataset_capabilities.json": '{"decoy": "this configuration is not loaded"}\n',
        "docs/design/canonical_workload_schema.md": "Decoy contract document\n",
    }
    for relative, text in decoys.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    config_path = root / "inputs.json"
    config_path.write_text(json.dumps(config))
    original_inputs = snapshot(root)
    for name in ("first", "second"):
        out = tmp_path / name
        # Reproduce the second run from the first receipt's saved configuration.
        selected_config = config_path if name == "first" else tmp_path / "first/report_provenance.json"
        result = subprocess.run(
            [sys.executable, str(Path(report.__file__).resolve()), "--root", str(root),
             "--config", str(selected_config), "--out-dir", str(out)],
            cwd=root, text=True, capture_output=True,
        )
        assert result.returncode == 0, result.stderr
    out = tmp_path / "first"
    receipt = json.loads((out / "report_provenance.json").read_text())
    code = {entry["role"]: entry for entry in receipt["executable_code"]["files"]}
    from src.canonical import schema
    actual_files = {
        "generator": Path(report.__file__).resolve(),
        "schema_and_capability_definitions": Path(schema.__file__).resolve(),
    }
    for role, actual in actual_files.items():
        entry = code[role]
        assert entry["path_base"] == "executing_checkout"
        assert (report.REPO_ROOT / entry["path"]).resolve() == actual
        assert entry["sha256"] == report.sha256(actual)
        assert entry["sha256"] != report.sha256(root / entry["path"])
    registry = receipt["executable_code"]["capability_registry"]
    profiles = {key: value.to_dict() for key, value in schema.DEFAULT_CAPABILITY_REGISTRY.items()}
    assert registry["effective_profiles"] == profiles
    encoded = json.dumps(profiles, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    import hashlib
    assert registry["sha256"] == hashlib.sha256(encoded).hexdigest()
    assert registry["definition_module"] == schema.__name__
    assert registry["definition_path"] == code["schema_and_capability_definitions"]["path"]
    assert registry["configuration_source"] == "Python definitions; config/dataset_capabilities.json is not loaded"
    refs = receipt["reference_documents"]
    assert len(refs) == 1 and refs[0]["path_base"] == "executing_checkout"
    assert refs[0]["sha256"] == report.sha256(report.REPO_ROOT / refs[0]["path"])
    assert refs[0]["sha256"] != report.sha256(root / refs[0]["path"])
    assert {entry["path"] for entry in receipt["sources"]} == {
        spec[key] for spec in config["datasets"].values()
        for key in ("results", "metadata") if key in spec
    }
    for entry in receipt["sources"]:
        assert entry["path_base"] == "input_artifact_root"
        assert entry["sha256"] == report.sha256(root / entry["path"])
    inventory = pd.read_csv(out / "report_sources.csv")
    assert len(inventory) == len(receipt["sources"]) + len(code) + len(refs)
    assert set(inventory.category) == {"input_artifact", "executable_code", "reference_document"}
    for entry in inventory.itertuples(index=False):
        base = root if entry.path_base == "input_artifact_root" else report.REPO_ROOT
        assert entry.sha256 == report.sha256(base / entry.path)
    rows = pd.read_csv(out / report.GOOGLE / "results.csv")
    assert rows.loc[rows.resource.eq("cpu") & rows.metric.eq("violation_pct"), "value"].eq(37.5).all()
    assert snapshot(tmp_path / "first") == snapshot(tmp_path / "second")
    assert snapshot(root) == original_inputs


def test_artifact_root_does_not_require_schema_or_generator_files(inputs, tmp_path):
    root, config = alternate_inputs(inputs, tmp_path)
    assert not (root / "src").exists()
    receipt = report.build_report(config, root, tmp_path / "out")
    assert {entry["role"] for entry in receipt["executable_code"]["files"]} == {
        "generator", "schema_and_capability_definitions",
    }
    assert all(entry["path"].startswith("artifacts/") for entry in receipt["sources"])


def verified_alibaba_inputs(inputs, tmp_path):
    spec = inputs["datasets"][report.ALIBABA]
    frame = pd.read_csv(spec["results"])
    sensitivity = tmp_path / "sensitivity.csv"
    pd.concat([frame.assign(sensitivity=cut, n_groups=2) for cut in report.CUTS]).to_csv(
        sensitivity, index=False,
    )
    spec["sensitivity"] = str(sensitivity)
    manifest = {
        "dataset_id": report.ALIBABA, "verified": True,
        "checks": [{"name": "synthetic fixture verification", "ok": True}],
        "artifacts": [{"path": spec[key], "sha256": report.sha256(Path(spec[key]))}
                      for key in ("results", "metadata", "sensitivity")],
    }
    verification = tmp_path / "verification.json"
    verification.write_text(json.dumps(manifest))
    spec["verification_manifest"] = str(verification)
    return spec


def test_unchanged_inputs_allow_repeated_access_and_resolved_aliases(inputs, tmp_path):
    spec = verified_alibaba_inputs(inputs, tmp_path)
    metadata = Path(spec["metadata"])
    alias = tmp_path / "metadata-alias.json"
    alias.symlink_to(metadata)
    spec["evidence"] = [str(metadata), str(alias)]
    initial = report.sha256(metadata)
    out = tmp_path / "out"
    receipt = build(inputs, out)
    matches = [ref for ref in receipt["sources"] if Path(ref["path"]).resolve() == metadata.resolve()]
    assert len(matches) == 1 and matches[0]["sha256"] == initial
    sensitivity = pd.read_csv(out / report.ALIBABA / "sensitivity.csv")
    assert sensitivity.status.eq("upstream_verified_inputs").all()


def test_sensitivity_input_change_after_manifest_verification_is_rejected(inputs, tmp_path, monkeypatch):
    spec = verified_alibaba_inputs(inputs, tmp_path)
    path = Path(spec["sensitivity"])
    initial = report.sha256(path)
    mutated = []

    def render(table, resource, dataset, status):
        if dataset == report.ALIBABA and not mutated:
            assert status == "upstream_verified_inputs"  # Manifest check already succeeded.
            frame = pd.read_csv(path)
            frame.loc[0, "memory_violation_pct"] += 0.125
            frame.to_csv(path, index=False)
            mutated.append(True)
        return "<svg/>\n"

    monkeypatch.setattr(report, "figure", render)
    out = tmp_path / "out"
    with pytest.raises(report.ReportError, match="Input integrity error") as error:
        build(inputs, out)
    assert mutated and report.sha256(path) != initial
    assert initial in str(error.value)  # The first digest remains the expected baseline.
    assert report.sha256(path) in str(error.value)
    assert not out.exists()  # No changed data or verified status can be published.


def test_sensitivity_symlink_cannot_change_target_after_verification(inputs, tmp_path, monkeypatch):
    spec = verified_alibaba_inputs(inputs, tmp_path)
    original = Path(spec["sensitivity"])
    replacement = tmp_path / "replacement.csv"
    frame = pd.read_csv(original)
    frame.loc[0, "memory_violation_pct"] += 0.125
    frame.to_csv(replacement, index=False)
    alias = tmp_path / "sensitivity-alias.csv"
    alias.symlink_to(original)
    spec["sensitivity"] = str(alias)
    retargeted = []

    def render(table, resource, dataset, status):
        if dataset == report.ALIBABA and not retargeted:
            assert status == "upstream_verified_inputs"
            alias.unlink()
            alias.symlink_to(replacement)
            retargeted.append(True)
        return "<svg/>\n"

    monkeypatch.setattr(report, "figure", render)
    with pytest.raises(report.ReportError, match="Input integrity error"):
        build(inputs, tmp_path / "out")
    assert retargeted and alias.resolve() == replacement.resolve()
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("key", ["results", "metadata", "verification_manifest"])
def test_other_input_changes_during_reporting_are_rejected(inputs, tmp_path, monkeypatch, key):
    spec = verified_alibaba_inputs(inputs, tmp_path)
    path = Path(spec[key])
    initial = report.sha256(path)
    mutated = []

    def render(table, resource, dataset, status):
        if dataset == report.ALIBABA and not mutated:
            assert status == "upstream_verified_inputs"
            path.write_bytes(path.read_bytes() + b"\n")
            mutated.append(True)
        return "<svg/>\n"

    monkeypatch.setattr(report, "figure", render)
    with pytest.raises(report.ReportError, match="Input integrity error") as error:
        build(inputs, tmp_path / "out")
    assert mutated and initial in str(error.value)
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("key", ["results", "metadata", "verification_manifest"])
def test_consumed_bytes_must_match_initial_digest(inputs, tmp_path, monkeypatch, key):
    spec = verified_alibaba_inputs(inputs, tmp_path)
    path = Path(spec[key]).resolve()
    initial = report.sha256(path)
    original_read = Path.read_bytes
    intercepted = []

    def changed_read(physical):
        raw = original_read(physical)
        if physical.resolve() == path:
            intercepted.append(True)
            return raw + b"\n"  # Simulate different bytes between hashing and reading.
        return raw

    monkeypatch.setattr(Path, "read_bytes", changed_read)
    with pytest.raises(report.ReportError, match="Input integrity error") as error:
        build(inputs, tmp_path / "out")
    assert intercepted and initial in str(error.value)
    assert report.sha256(path) == initial  # Even a restored on-disk file cannot hide a bad read.
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("shape,bad", [
    ("top", []), ("top", None),
    ("datasets", []), ("datasets", None),
    ("spec", []), ("spec", None), ("spec", "invalid"), ("spec", 42),
    ("receipt", []), ("receipt", None),
])
def test_malformed_configuration_shapes_report_clean_errors(inputs, tmp_path, capsys, shape, bad):
    if shape == "top":
        config = bad
    elif shape == "datasets":
        config = {"datasets": bad}
    elif shape == "receipt":
        config = {"kind": report.RECEIPT_KIND, "configuration": bad}
    else:
        config = inputs
        config["datasets"][report.GOOGLE] = bad
    path = tmp_path / "bad-config.json"
    path.write_text(json.dumps(config))
    out = tmp_path / "out"
    assert report.main(["--config", str(path), "--out-dir", str(out)]) == 1
    error = capsys.readouterr().err
    assert error.startswith("REPORT FAILED:") and "JSON object" in error
    assert "Traceback" not in error
    assert not out.exists()
