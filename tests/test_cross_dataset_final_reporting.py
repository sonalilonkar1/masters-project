import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from scripts import build_final_cross_dataset_report as report
from src.reporting.artifact_provenance import digest, trace_metric_cells, validate_bundle

ROOT = Path(__file__).resolve().parents[1]


def config():
    return json.loads((ROOT / "config/cross_dataset_report_final.json").read_text())


@pytest.fixture
def quick_figures(monkeypatch):
    monkeypatch.setattr(report, "figure", lambda *args: "<svg/>\n")


def test_final_reporting_preserves_identity_limitations_and_pending_decisions(tmp_path, quick_figures):
    out = tmp_path / "report"
    receipt = report.build_report(config(), ROOT, out, strict=True)
    assert receipt["kind"] == report.FINAL_RECEIPT_KIND
    assert receipt["project_completion"] is False
    assert receipt["reporting_status"] == "DECISION_PENDING"
    evidence = receipt["upstream_evidence"][report.ALIBABA]
    assert evidence["identity"] == config()["datasets"][report.ALIBABA]["expected_identity"]
    assert evidence["external_physical_artifact_bytes"].startswith("UNVERIFIED")
    text = (out / "limitations.md").read_text()
    for limitation in evidence["unverified_items"]:
        assert limitation["item"] in text and limitation["reason"] in text
    summary = (out / "report.md").read_text()
    for dataset in (report.ALIBABA, report.GOOGLE):
        for limitation in config()["datasets"][dataset]["limitations"]:
            assert limitation in text and limitation in summary
    assert "Run history" in text and "lock file" in text
    statuses = pd.read_csv(out / "dataset_status.csv").set_index("dataset_id")
    assert statuses.loc[report.ALIBABA, "report_status"] == "published_evidence_validated"
    assert all(statuses.loc[d, "report_status"] == "decision_pending" for d in
               (report.GOOGLE, "azure_public_vm_v2", "alibaba_clustertrace2018"))
    manifest = json.loads((out / "artifact_manifest.json").read_text())
    assert manifest["reporting_validation"] == "PASS" and manifest["project_completion"] is False
    assert {e["path"] for e in manifest["outputs"]} == {
        p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()
    } - {"artifact_manifest.json"}
    for entry in manifest["outputs"]:
        assert hashlib.sha256((out / entry["path"]).read_bytes()).hexdigest() == entry["sha256"]
    validate_bundle(out, ROOT, ROOT)


def test_final_bundle_is_deterministic_and_tampering_is_detected(tmp_path, quick_figures):
    for name in ("a", "b"):
        report.build_report(config(), ROOT, tmp_path / name)
    snapshot = lambda root: {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert snapshot(tmp_path / "a") == snapshot(tmp_path / "b")
    (tmp_path / "a/conclusions.md").write_text("tampered\n")
    with pytest.raises(ValueError, match="checksum"):
        validate_bundle(tmp_path / "a", ROOT, ROOT)


def test_failed_final_publication_exposes_no_success_manifest(tmp_path, quick_figures, monkeypatch):
    def fail(*args):
        raise OSError("simulated bundle publication failure")
    monkeypatch.setattr(report.os, "replace", fail)
    with pytest.raises(OSError, match="publication failure"):
        report.build_report(config(), ROOT, tmp_path / "out")
    assert not (tmp_path / "out").exists()
    assert not list(tmp_path.glob(".out.*"))


def test_standalone_final_generation_and_receipt_reproduction(tmp_path):
    import os
    import subprocess
    import sys
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["MPLCONFIGDIR"] = str(tmp_path / "mpl")
    script = ROOT / "scripts/build_final_cross_dataset_report.py"
    for name, selected in (("a", ROOT / "config/cross_dataset_report_final.json"),
                           ("b", tmp_path / "a/report_provenance.json")):
        run = subprocess.run([sys.executable, str(script), "--config", str(selected), "--root", str(ROOT),
                              "--out-dir", str(tmp_path / name), "--strict"],
                             cwd=tmp_path, env=env, text=True, capture_output=True)
        assert run.returncode == 0, run.stderr
    snapshot = lambda root: {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert snapshot(tmp_path / "a") == snapshot(tmp_path / "b")
    run = subprocess.run([sys.executable, str(script), "--validate-bundle", str(tmp_path / "a"),
                          "--root", str(ROOT)], cwd=tmp_path, env=env, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    assert "project_completion=False" in run.stdout


def test_pending_decisions_block_requested_final_completion(tmp_path, quick_figures):
    with pytest.raises(report.ReportError, match="decision_pending"):
        report.build_report(config(), ROOT, tmp_path / "out", require_complete=True)
    assert not (tmp_path / "out").exists()


def test_optional_datasets_have_no_invented_scientific_outputs(tmp_path, quick_figures):
    report.build_report(config(), ROOT, tmp_path / "out")
    out = tmp_path / "out"
    for dataset in ("azure_public_vm_v2", "alibaba_clustertrace2018"):
        assert not (out / dataset).exists()
    decisions = pd.read_csv(out / "reporting_decisions.csv").set_index("dataset_id")
    assert decisions.loc[report.GOOGLE, "decision_status"] == "decision_pending"
    text = (out / "limitations.md").read_text()
    assert "F3/F4" in text and "F7/F8" in text


@pytest.mark.parametrize("key", ["run_id", "code_commit", "decision_manifest_sha256"])
def test_final_reporting_rejects_wrong_frozen_identity(tmp_path, key, quick_figures):
    cfg = config()
    cfg["datasets"][report.ALIBABA]["expected_identity"][key] = (
        "wrong" if key == "run_id" else "0" * (40 if key == "code_commit" else 64))
    with pytest.raises(report.ReportError, match="identity|digest"):
        report.build_report(cfg, ROOT, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("defect", ["utilization", "denominator", "missing", "null", "population"])
def test_invalid_scientific_summary_cannot_publish_final_bundle(tmp_path, defect, quick_figures):
    # Keep all authoritative provenance checks intact, isolating numerical validation.
    original = report.validate_summary
    def altered(frame, dataset, **kwargs):
        if dataset == report.ALIBABA and not kwargs.get("sensitivity"):
            frame = frame.copy()
            if defect == "utilization":
                frame.loc[0, "average_cpu_utilization"] = 50
            elif defect == "denominator":
                frame.loc[0, "valid_cpu_violation_count"] = 1
            elif defect == "missing":
                frame = frame.drop(columns="average_memory_shortfall")
            elif defect == "null":
                frame.loc[0, "cpu_violation_pct"] = float("nan")
            else:
                frame.loc[0, "row_count"] += 1
        return original(frame, dataset, **kwargs)
    from unittest.mock import patch
    with patch.object(report, "validate_summary", altered), pytest.raises(report.ReportError):
        report.build_report(config(), ROOT, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_documented_outcome_cannot_use_actual_pending_record(tmp_path, quick_figures):
    cfg = config()
    spec = cfg['datasets'][report.GOOGLE]
    spec.update(decision_status='documented_outcome', decision_summary='Claimed approval')
    with pytest.raises(ValueError, match='status contradicts'):
        report.build_report(cfg, ROOT, tmp_path / 'out', require_complete=True)
    assert not (tmp_path / 'out').exists()


def completed_fixture(tmp_path):
    """A synthetic approval document is an input, never an approval of real work."""
    import shutil
    from src.reporting.artifact_provenance import decision_summary
    root = tmp_path / "inputs"
    root.mkdir()
    original_manifest = json.loads((ROOT / "reports/results/cross_dataset_final/artifact_manifest.json").read_text())
    for source in original_manifest["sources"]:
        target = root / source["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / source["path"], target)
    cfg = config()
    for dataset, outcome in {report.GOOGLE: "retain_provisional", "azure_public_vm_v2": "feasibility_only",
                             "alibaba_clustertrace2018": "deferred"}.items():
        spec = cfg["datasets"][dataset]
        summary = decision_summary(dataset, "documented_outcome", outcome)
        reference = f"config/reporting_decisions/{dataset}.synthetic-approval.json"
        approval = {"schema_version": 1, "dataset_id": dataset, "status": "documented_outcome",
                    "outcome": outcome, "approval_reference": reference, "summary": summary}
        path = root / reference
        path.write_text(json.dumps(approval))
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        spec.update(decision_status="documented_outcome", decision_outcome=outcome,
                    decision_summary=summary, approval_reference=reference)
        rp = root / spec["decision_record"]
        record = json.loads(rp.read_text())
        evidence_path = root / record["evidence_path"]
        evidence_path.write_text(json.dumps({"dataset_id": dataset, "status": "documented_outcome",
            "outcome": outcome, "basis": summary, "approval_reference": reference, "approval_sha256": checksum}))
        record.update(status="documented_outcome", outcome=outcome, summary=summary,
                      approval_reference=reference, approval_sha256=checksum,
                      evidence_sha256=hashlib.sha256(evidence_path.read_bytes()).hexdigest())
        rp.write_text(json.dumps(record))
    return cfg, root


def test_valid_documented_outcomes_render_complete(tmp_path, quick_figures):
    cfg, root = completed_fixture(tmp_path)
    out = tmp_path / "out"
    receipt = report.build_report(cfg, root, out, require_complete=True)
    assert receipt["project_completion"] is True
    for name in ("report.md", "conclusions.md", "limitations.md"):
        assert "Dataset reporting decisions are documented." in (out / name).read_text()
        assert "Decision remains pending" not in (out / name).read_text()
    assert "Decision remains pending" not in (out / "reporting_decisions.csv").read_text()
    validate_bundle(out, root, ROOT)
    inputs = {ref["path"] for ref in receipt["sources"]}
    assert all(spec["approval_reference"] in inputs for spec in cfg["datasets"].values()
               if spec["decision_status"] == "documented_outcome")


@pytest.mark.parametrize("defect", ["record_summary", "configured_summary", "pending_basis", "pending_evidence",
    "missing_reference", "unreadable_reference", "approval_dataset", "approval_status", "approval_outcome",
    "approval_reference", "approval_summary", "approval_hash", "record_reference", "configured_reference"])
def test_completed_approval_evidence_rejects_contradictions(tmp_path, quick_figures, defect):
    cfg, root = completed_fixture(tmp_path)
    spec = cfg["datasets"][report.GOOGLE]
    rp = root / spec["decision_record"]; rec = json.loads(rp.read_text())
    ep = root / rec["evidence_path"]; ev = json.loads(ep.read_text())
    ap = root / ev["approval_reference"]; approval = json.loads(ap.read_text())
    pending = "No documented team approval supplied. Decision remains pending."
    if defect == "record_summary": rec["summary"] = pending
    elif defect == "configured_summary": spec["decision_summary"] = pending
    elif defect == "pending_basis": ev["basis"] = pending
    elif defect == "pending_evidence": ev["status"] = "decision_pending"
    elif defect == "missing_reference": ap.unlink()
    elif defect == "unreadable_reference": ap.unlink(); ap.mkdir()
    elif defect == "record_reference": rec["approval_reference"] = "pending.json"
    elif defect == "configured_reference": spec["approval_reference"] = "pending.json"
    elif defect == "approval_hash": ev["approval_sha256"] = "0" * 64
    else:
        field = defect.removeprefix("approval_")
        approval[{"dataset": "dataset_id"}.get(field, field)] = "decision_pending" if field == "status" else "wrong"
        ap.write_text(json.dumps(approval))
        ev["approval_sha256"] = rec["approval_sha256"] = hashlib.sha256(ap.read_bytes()).hexdigest()
    ep.write_text(json.dumps(ev)); rec["evidence_sha256"] = hashlib.sha256(ep.read_bytes()).hexdigest()
    rp.write_text(json.dumps(rec))
    with pytest.raises((ValueError, OSError)):
        report.build_report(cfg, root, tmp_path / "out", require_complete=True)
    assert not (tmp_path / "out").exists()


def rewrite_bundle(out, mutate):
    manifest = json.loads((out / 'artifact_manifest.json').read_text())
    receipt = json.loads((out / 'report_provenance.json').read_text())
    mutate(manifest, receipt)
    for entry in receipt["outputs"]:
        entry["sha256"] = hashlib.sha256((out / entry["path"]).read_bytes()).hexdigest()
    (out / 'report_provenance.json').write_text(json.dumps(receipt))
    for entry in manifest['outputs']:
        entry['sha256'] = hashlib.sha256((out / entry['path']).read_bytes()).hexdigest()
    (out / 'artifact_manifest.json').write_text(json.dumps(manifest))


@pytest.mark.parametrize('defect', ['decisions', 'scope_missing', 'scope_false', 'physical', 'historical', 'inference', 'upstream_limitations'])
def test_bundle_rejects_rehashed_false_claims(tmp_path, quick_figures, defect):
    out = tmp_path / 'out'; report.build_report(config(), ROOT, out)
    def corrupt(manifest, receipt):
        for obj in (manifest, receipt):
            if defect == 'decisions': obj['dataset_decisions'][0]['outcome'] = 'approved'
            elif defect == 'scope_missing': obj['verification_scope'].pop('historical_execution')
            elif defect == 'scope_false': obj['verification_scope']['external_physical_artifact_bytes'] = 'verified'
            elif defect == 'upstream_limitations': obj['upstream_evidence'][report.ALIBABA]['unverified_items'] = []
            else:
                field = {'physical':'external_physical_artifact_bytes', 'historical':'historical_exactly_once_execution', 'inference':'scientific_inference_reproduction'}[defect]
                obj['upstream_evidence'][report.ALIBABA][field] = 'independently verified'
    rewrite_bundle(out, corrupt)
    with pytest.raises(ValueError): validate_bundle(out, ROOT, ROOT)


@pytest.mark.parametrize("name", ["limitations.md", "evidence_status.md", "evidence_status.csv", "reporting_decisions.md", "reporting_decisions.csv"])
def test_rehashed_rendered_claims_must_agree_with_sources(tmp_path, quick_figures, name):
    out = tmp_path / "out"
    report.build_report(config(), ROOT, out)
    (out / name).write_text("All physical models independently verified; every decision approved.\n")
    rewrite_bundle(out, lambda manifest, receipt: None)
    with pytest.raises(ValueError, match="limitations|rendered"):
        validate_bundle(out, ROOT, ROOT)


@pytest.mark.parametrize("name", ["report.md", "conclusions.md"])
@pytest.mark.parametrize("position", ["append", "prepend"])
def test_rehashed_contradictory_completion_documents_rejected(tmp_path, quick_figures, name, position):
    out = tmp_path / "out"
    report.build_report(config(), ROOT, out)
    original = (out / name).read_text()
    claim = "All dataset decisions approved. Project completion: COMPLETE.\n"
    (out / name).write_text(original + claim if position == "append" else claim + original)
    rewrite_bundle(out, lambda manifest, receipt: None)
    with pytest.raises(ValueError, match="canonical reporting document"):
        validate_bundle(out, ROOT, ROOT)


@pytest.mark.parametrize('filename,field,replacement', [
    ('alibaba_gpu_v2020/02_cpu.csv', 'value', '0'),
    ('alibaba_gpu_v2020/01_memory.csv', 'value', '99'),
    ('google_clusterdata2019/01_cpu.csv', 'denominator', '1'),
    ('alibaba_gpu_v2020/sensitivity.csv', 'policy', 'Hybrid'),
    ('alibaba_gpu_v2020/results.csv', 'source_column', 'cpu_violation_pct'),
    ('alibaba_gpu_v2020/results.csv', 'source_csv_row', '3'),
    ('alibaba_gpu_v2020/results.csv', 'source_sha256', '0' * 64),
    ('alibaba_gpu_v2020/results.csv', 'unit', 'GHz'),
    ('alibaba_gpu_v2020/results.csv', 'population_rows', '1'),
    ('alibaba_gpu_v2020/sensitivity.csv', 'source_n_groups', '999'),
    ('alibaba_gpu_v2020/results.csv', 'denominator_status', 'not reported by source'),
])
def test_repaired_generated_metric_forgery_rejected(tmp_path, quick_figures, filename, field, replacement):
    import csv
    import io
    out = tmp_path / 'out'
    report.build_report(config(), ROOT, out)
    rows = list(csv.DictReader(io.StringIO((out / filename).read_text())))
    rows[0][field] = replacement
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader(); writer.writerows(rows)
    (out / filename).write_text(text.getvalue())
    rewrite_bundle(out, lambda manifest, receipt: None)
    with pytest.raises(ValueError, match='metric|canonical|source-cell'):
        validate_bundle(out, ROOT, ROOT)


@pytest.mark.parametrize('defect', ['empty', 'incomplete', 'wrong_role', 'readme_generator', 'hash',
    'profiles', 'profile_hash', 'definition', 'references', 'metric_receipt', 'source_inventory'])
def test_repaired_provenance_forgery_rejected(tmp_path, quick_figures, defect):
    out = tmp_path / 'out'; report.build_report(config(), ROOT, out)
    def mutate(manifest, receipt):
        if defect == 'references': receipt['reference_documents'] = []
        for obj in (manifest, receipt):
            code = obj['executable_code']
            if defect == 'empty': code['files'] = []
            elif defect == 'incomplete': code['files'].pop()
            elif defect == 'wrong_role': code['files'][0]['role'] = 'unrelated'
            elif defect == 'readme_generator':
                code['files'][0].update(path='README.md', sha256=hashlib.sha256((ROOT / 'README.md').read_bytes()).hexdigest())
            elif defect == 'hash': code['files'][0]['sha256'] = '0' * 64
            elif defect == 'profiles':
                registry = code['capability_registry']
                registry['effective_profiles'][report.ALIBABA]['cpu_unit'] = 'invented_GHz'
                registry['sha256'] = hashlib.sha256(json.dumps(registry['effective_profiles'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            elif defect == 'profile_hash': code['capability_registry']['sha256'] = '0' * 64
            elif defect == 'definition': code['capability_registry']['definition_module'] = 'invented'
            elif defect == 'metric_receipt': obj['metric_traceability']['unique_source_metric_cells'] = 1
            elif defect == 'source_inventory': obj['sources'].append(dict(obj['sources'][0]))
    rewrite_bundle(out, mutate)
    with pytest.raises(ValueError, match='inventory|registry|traceability'):
        validate_bundle(out, ROOT, ROOT)


@pytest.mark.parametrize('claim', [
    'All dataset decisions approved. Project completion: COMPLETE.',
    'All physical model bytes independently verified.',
    'Inference was independently reproduced.',
    'Historical execution independently verified.',
    '<!-- pending --> All approvals complete.\n# Authoritative verification: PASS',
    'Useful operator note about future work.',
])
def test_configuration_annotations_cannot_supply_authoritative_claims(tmp_path, quick_figures, claim):
    cfg = config()
    for spec in cfg['datasets'].values():
        spec['reason'] = claim
        spec['annotation'] = claim
    out = tmp_path / 'out'
    receipt = report.build_report(cfg, ROOT, out)
    assert receipt['project_completion'] is False
    for name in ('report.md', 'conclusions.md', 'limitations.md', 'dataset_status.csv', 'dataset_status.md'):
        assert claim not in (out / name).read_text()
    assert receipt['verification_scope']['configuration_annotations'].startswith('Unverified operator notes')
    validate_bundle(out, ROOT, ROOT)


def test_all_metric_cells_traced_and_svg_forgery_rejected(tmp_path, quick_figures):
    out = tmp_path / 'out'; receipt = report.build_report(config(), ROOT, out)
    assert receipt['metric_traceability'] == {
        'unique_source_metric_cells': 399, 'rendered_metric_cells': 518, 'conclusion_metric_cells': 8}
    (out / 'alibaba_gpu_v2020/02_cpu.svg').write_text('<svg>All violations zero</svg>\n')
    rewrite_bundle(out, lambda manifest, receipt: None)
    with pytest.raises(ValueError, match='canonical reporting'):
        validate_bundle(out, ROOT, ROOT)


def test_metric_trace_rejects_rounded_source_text(tmp_path, quick_figures):
    out = tmp_path / "out"
    cfg = config()
    report.build_report(cfg, ROOT, out)
    contents = {p.relative_to(out).as_posix(): p.read_text() for p in out.rglob("*.csv")}
    name = f"{report.ALIBABA}/results.csv"
    exact = "0.19704480677699449"
    assert exact in contents[name]
    contents[name] = contents[name].replace(exact, "0.1970448067769944", 1)

    def read_input(path):
        raw = (ROOT / path).read_bytes()
        return raw, {"sha256": digest(raw)}

    with pytest.raises(ValueError, match="metric source-cell mismatch"):
        trace_metric_cells(contents, cfg, read_input)


@pytest.mark.parametrize('target', ['manifest', 'receipt', 'both'])
@pytest.mark.parametrize('claim,value', [
    ('verified', True), ('completion_status', 'COMPLETE'),
    ('external_physical_artifact_bytes', 'independently verified'),
    ('scientific_inference_reproduction', 'independently verified'),
    ('historical_exactly_once_execution', 'independently verified'),
])
def test_closed_authoritative_envelopes_reject_rehashed_claims(tmp_path, quick_figures, target, claim, value):
    out = tmp_path / 'out'; report.build_report(config(), ROOT, out)
    def mutate(manifest, receipt):
        for obj in ([manifest] if target == 'manifest' else [receipt] if target == 'receipt' else [manifest, receipt]):
            obj[claim] = value
    rewrite_bundle(out, mutate)
    with pytest.raises(ValueError, match='metadata schema.*undeclared'):
        validate_bundle(out, ROOT, ROOT)


@pytest.mark.parametrize('path', [
    ('environment',), ('verification_scope',), ('metric_traceability',), ('dataset_decisions', 0),
    ('executable_code',), ('executable_code', 'files', 0), ('executable_code', 'capability_registry'),
    ('executable_code', 'capability_registry', 'effective_profiles', report.ALIBABA),
    ('upstream_evidence', report.ALIBABA), ('upstream_evidence', report.ALIBABA, 'identity'),
    ('upstream_evidence', report.ALIBABA, 'upstream_reporting_environment'),
    ('upstream_evidence', report.ALIBABA, 'bindings', 0),
    ('upstream_evidence', report.ALIBABA, 'unverified_items', 0),
    ('upstream_evidence', report.GOOGLE), ('sources', 0), ('outputs', 0),
    ('configuration',), ('configuration', 'datasets', report.GOOGLE),
    ('configuration', 'datasets', report.ALIBABA, 'expected_identity'),
    ('configuration', 'datasets', report.ALIBABA, 'artifact_bindings', 0),
])
def test_nested_metadata_boundaries_are_closed_after_rehash(tmp_path, quick_figures, path):
    out = tmp_path / 'out'; report.build_report(config(), ROOT, out)
    def mutate(manifest, receipt):
        for obj in (manifest, receipt):
            nested = obj
            for key in path: nested = nested[key]
            nested['historical_execution_independently_verified'] = True
    rewrite_bundle(out, mutate)
    with pytest.raises(ValueError, match='metadata schema.*undeclared'):
        validate_bundle(out, ROOT, ROOT)


@pytest.mark.parametrize('path', [('environment', 'python'), ('project_completion',), ('metric_traceability', 'unique_source_metric_cells')])
def test_metadata_types_cannot_be_replaced_by_claim_objects(tmp_path, quick_figures, path):
    out = tmp_path / 'out'; report.build_report(config(), ROOT, out)
    def mutate(manifest, receipt):
        for obj in (manifest, receipt):
            for key in path[:-1]: obj = obj[key]
            obj[path[-1]] = {'verified': True}
    rewrite_bundle(out, mutate)
    with pytest.raises(ValueError, match='metadata schema.*invalid type'):
        validate_bundle(out, ROOT, ROOT)


def test_optional_unverified_annotations_preserve_valid_metadata(tmp_path, quick_figures):
    cfg = config(); note = 'Operator note claims completion; this is explicitly unverified.'
    cfg['unverified_annotations'] = {'scope': 'unverified', 'notes': [note]}
    cfg['datasets'][report.GOOGLE]['unverified_annotations'] = {'scope': 'unverified', 'notes': ['Future work']}
    receipt = report.build_report(cfg, ROOT, tmp_path / 'out')
    assert receipt['unverified_annotations'] == cfg['unverified_annotations']
    assert receipt['project_completion'] is False
    for name in ('report.md', 'conclusions.md', 'limitations.md'):
        assert note not in (tmp_path / 'out' / name).read_text()
    validate_bundle(tmp_path / 'out', ROOT, ROOT)


@pytest.mark.parametrize('defect', ['scope', 'verified', 'nested_claim'])
def test_annotations_cannot_be_promoted_to_authoritative_objects(tmp_path, quick_figures, defect):
    cfg = config(); cfg['unverified_annotations'] = {'scope': 'unverified', 'notes': ['Future work']}
    if defect == 'scope': cfg['unverified_annotations']['scope'] = 'verified'
    elif defect == 'verified': cfg['unverified_annotations']['verified'] = True
    else: cfg['unverified_annotations']['notes'] = [{'completion_status': 'COMPLETE'}]
    with pytest.raises(ValueError, match='metadata schema'):
        report.build_report(cfg, ROOT, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_generation_validates_receipt_schema_before_publication(tmp_path, quick_figures, monkeypatch):
    original = report.executing_provenance
    def forged():
        code, refs, files = original()
        code['verified'] = True
        return code, refs, files
    monkeypatch.setattr(report, 'executing_provenance', forged)
    with pytest.raises(ValueError, match='metadata schema.*undeclared'):
        report.build_report(config(), ROOT, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_schema_preserves_task8_nullable_producer_fields():
    from src.reporting import metadata_schema
    receipt = json.loads((ROOT / 'reports/results/cross_dataset_final/report_provenance.json').read_text())
    environment = receipt['upstream_evidence'][report.ALIBABA]['upstream_reporting_environment']
    environment['code_commit'] = None; environment['code_dirty'] = None
    metadata_schema.validate_metadata(receipt, 'receipt')


@pytest.mark.parametrize('raw', ['{"project_completion":true,"project_completion":false}',
    '{"environment":{"python":"3","python":"4"}}', '{"verified":NaN}'])
def test_ambiguous_metadata_json_is_rejected(raw):
    from src.reporting import metadata_schema
    with pytest.raises(ValueError, match='duplicate property|non-JSON constant'):
        metadata_schema.loads(raw)


def test_legitimate_optional_configuration_fields_may_be_absent(tmp_path, quick_figures):
    cfg = config(); cfg.pop('report_name'); cfg.pop('historical_report')
    report.build_report(cfg, ROOT, tmp_path / 'out')
    validate_bundle(tmp_path / 'out', ROOT, ROOT)
