"""Validate published evidence without claiming unavailable bytes were inspected."""

import hashlib
import json
import re
from pathlib import Path, PurePosixPath

from src.reporting import metadata_schema

ALIBABA = "alibaba_gpu_v2020"
DATASETS = {ALIBABA, "google_clusterdata2019", "azure_public_vm_v2", "alibaba_clustertrace2018"}
BINDINGS = {
    "metadata": ("task7_pr1_ml", "decision_manifest.json"),
    "results": ("task7_pr2_final_test", "final_test_policy_comparison.csv"),
    "sensitivity": ("task7_pr2_final_test", "final_test_sensitivity.csv"),
    "run_record": ("task7_pr2_final_test", "run_record.json"),
    "final_metadata": ("task7_pr2_final_test", "metadata.json"),
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_path(value):
    require(isinstance(value, str) and bool(value), "artifact path must be nonempty")
    path = PurePosixPath(value)
    require(not path.is_absolute() and ".." not in path.parts and "\\" not in value,
            f"unsafe artifact path: {value!r}")
    return path


VERIFICATION_SCOPE = {
    "published_reporting_bytes": "verified against pinned source hashes",
    "published_metadata": "consistency checked against pinned Task 8 sources",
    "external_physical_artifact_bytes": "UNVERIFIED",
    "historical_execution": "UNVERIFIED",
    "model_inference_reproduction": "UNVERIFIED",
    "task4_test_value_isolation": "UNVERIFIED",
    "configuration_annotations": "Unverified operator notes; excluded from authoritative rendered reporting",
}


# Reviewed scientific context; configuration annotations cannot supply reporting claims.
REPORTING_CONTEXT = {'alibaba_clustertrace2018': 'Task 9 demonstration outcome and validated sample metadata are not '
                             'supplied. No next-occurrence or recommendation results are reported.',
 'alibaba_gpu_v2020': 'Authoritative published November 15 Alibaba run. Published reporting bytes '
                      'and metadata are validated; unavailable physical artifacts, inference '
                      'reproduction and historical execution are not independently reproduced.',
 'azure_public_vm_v2': 'Existing feasibility analysis supports deferring integration. Dataset '
                       'V1/V2 identity needs reconciliation; observed memory and official '
                       'recurrence are unavailable. No Task 11 Stage 2 results are reported.',
 'google_clusterdata2019': 'Existing frozen Google results are displayed with F3/F4 contamination '
                           'and F7/F8 limitations. Reporting treatment is governed by the '
                           'validated dataset decision record.'}


def reporting_context(dataset):
    return REPORTING_CONTEXT[dataset]


def completion_statement(complete):
    return ("Dataset reporting decisions are documented." if complete else
            "Final project completion remains pending documented dataset decisions.")


def decision_summary(dataset, status, outcome):
    if status == "decision_pending":
        return "No documented team approval supplied. Decision remains pending."
    if status == "accepted_published_run":
        return "Published Task 8 acceptance only; no new scientific verification."
    return f"Documented reporting outcome for {dataset}: {outcome}."


def decisions_complete(decisions):
    require({r["dataset_id"] for r in decisions} == DATASETS, "complete decision population required")
    return all(r["decision_status"] != "decision_pending" for r in decisions)


def validate_decision(dataset, spec, read_json, read_input):
    record, ref = read_json(spec["decision_record"])
    metadata_schema.validate_shape(record, metadata_schema.RECORD, "$.decision_record")
    require(record.get("schema_version") == 1 and record.get("dataset_id") == dataset,
            f"{dataset}: decision record dataset/schema mismatch")
    status = spec["decision_status"]
    require(record.get("status") == status, f"{dataset}: decision status contradicts record")
    outcomes = {"google_clusterdata2019": {"retain_provisional"},
                "azure_public_vm_v2": {"feasibility_only"},
                "alibaba_clustertrace2018": {"deferred"}, ALIBABA: {"accepted_published_run"}}
    outcome = record.get("outcome")
    require(outcome == "pending" if status == "decision_pending" else outcome in outcomes[dataset],
            f"{dataset}: invalid decision outcome")
    require(spec.get("decision_outcome") == outcome, f"{dataset}: configured outcome mismatch")
    require(spec.get("decision_evidence") == [record["evidence_path"]],
            "configured decision evidence disagrees with structured record")
    safe_path(record["evidence_path"])
    evidence, evidence_ref = read_json(record["evidence_path"])
    metadata_schema.validate_shape(evidence, metadata_schema.EVIDENCE, "$.decision_evidence")
    require(evidence_ref["sha256"] == record.get("evidence_sha256"), "decision evidence checksum mismatch")
    require(evidence.get("dataset_id") == dataset and evidence.get("status") == status
            and evidence.get("outcome") == outcome, f"{dataset}: contradictory decision evidence")
    summary = decision_summary(dataset, status, outcome)
    require(record.get("summary") == summary, "decision summary contradicts validated decision state")
    require(evidence.get("basis") == summary, "decision evidence basis contradicts validated decision state")
    if status == "decision_pending":
        require(not evidence.get("approval_reference"), "pending evidence cannot claim approval")
    if status == "documented_outcome":
        require(spec.get("decision_summary") == summary, "configured summary contradicts decision state")
        reference = evidence.get("approval_reference")
        safe_path(reference)
        require(record.get("approval_reference") == spec.get("approval_reference") == reference,
                "approval reference disagrees across configuration, record and evidence")
        approval, approval_ref = read_json(reference)
        metadata_schema.validate_shape(approval, metadata_schema.APPROVAL, "$.approval")
        require(approval_ref["sha256"] == evidence.get("approval_sha256") == record.get("approval_sha256"),
                "approval evidence checksum mismatch")
        expected = {"schema_version": 1, "dataset_id": dataset, "status": status,
                    "outcome": outcome, "approval_reference": reference, "summary": summary}
        require(isinstance(approval, dict) and type(approval.get("schema_version")) is int
                and approval == expected, "approval evidence dataset/status/outcome/reference or summary mismatch")
        require(set(evidence) == {"dataset_id", "status", "outcome", "basis", "approval_reference", "approval_sha256"},
                "unexpected completed decision evidence fields")
    return {"dataset_id": dataset, "decision_status": status, "outcome": outcome,
            "decision_summary": summary, "record_sha256": ref["sha256"],
            "evidence_sha256": evidence_ref["sha256"]}


def limitations_text(config, upstream, order, decisions):
    lines = ["# Reporting limitations", "",
             "Verified published bytes and metadata do not establish historical execution or inference reproduction.", "",
             completion_statement(decisions_complete(decisions)), ""]
    for dataset in order:
        lines += [f"## {dataset}", "", reporting_context(dataset), ""]
        evidence = upstream.get(dataset, {})
        for item in evidence.get("unverified_items", []):
            lines.append(f"- **UNVERIFIED:** {item['item']} — {item['reason']}")
        for field in ("external_physical_artifact_bytes", "historical_exactly_once_execution",
                      "scientific_inference_reproduction", "november_10_byte_equivalence"):
            if field in evidence:
                lines.append(f"- {field}: {evidence[field]}")
        lines.extend(f"- {item}" for item in evidence.get("followups", []) + evidence.get("limitations", []))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def validate_final_configuration(config):
    metadata_schema.validate_configuration(config)
    require(isinstance(config, dict) and type(config.get("report_version")) is int
            and config["report_version"] == 2, "unsupported final report version")
    datasets = config.get("datasets")
    require(isinstance(datasets, dict) and set(datasets) == DATASETS,
            "final configuration must state all four datasets")
    for dataset, spec in datasets.items():
        require(isinstance(spec, dict), f"{dataset}: invalid specification")
        allowed = {"accepted_published_run"} if dataset == ALIBABA else {"decision_pending", "documented_outcome"}
        require(spec.get("decision_status") in allowed, f"{dataset}: invalid decision status")
        safe_path(spec.get("decision_record"))
        if spec.get("decision_status") == "documented_outcome":
            require(bool(spec.get("decision_evidence")) and bool(spec.get("decision_summary")),
                    f"{dataset}: documented outcome requires decision evidence and summary")
    spec = datasets[ALIBABA]
    identity = spec.get("expected_identity", {})
    require(isinstance(identity, dict) and set(identity) == {"decision_manifest_sha256", "run_id", "code_commit"},
            "Alibaba expected identity is required")
    require(bool(re.fullmatch(r"[0-9a-f]{64}", identity.get("decision_manifest_sha256", "")))
            and bool(re.fullmatch(r"[0-9a-f]{40}", identity.get("code_commit", "")))
            and isinstance(identity.get("run_id"), str) and bool(identity["run_id"].strip()),
            "invalid Alibaba expected identity")
    require(bool(re.fullmatch(r"[0-9a-f]{64}", spec.get("verification_manifest_sha256", ""))),
            "expected Task 8 manifest digest is required")
    bindings = spec.get("artifact_bindings")
    require(isinstance(bindings, list) and len(bindings) == len(BINDINGS), "complete artifact bindings required")
    require({b.get("logical_artifact") for b in bindings if isinstance(b, dict)} == set(BINDINGS),
            "duplicate or missing logical artifact binding")
    for binding in bindings:
        logical = binding["logical_artifact"]
        stage, name = BINDINGS[logical]
        require(binding.get("dataset_id") == ALIBABA and binding.get("stage") == stage,
                f"{logical}: wrong dataset/stage")
        path = safe_path(binding.get("manifest_path"))
        require(path.name == name, f"{logical}: wrong manifest artifact")
        safe_path(binding.get("published_path"))
        require(binding["published_path"] == spec.get(logical), f"{logical}: published path disagrees")
        require(bool(re.fullmatch(r"[0-9a-f]{64}", binding.get("sha256", ""))), f"{logical}: invalid digest")


def validate_alibaba_evidence(spec, read_json, read_input):
    """Bind small published copies to pinned Task 8 evidence, never open targets."""
    manifest, ref = read_json(spec["verification_manifest"])
    require(ref["sha256"] == spec["verification_manifest_sha256"], "Task 8 manifest digest mismatch")
    require(manifest.get("dataset_id") == ALIBABA and manifest.get("schema_version") == "0.2.0",
            "Task 8 dataset/schema mismatch")
    require(manifest.get("status") == "PASS" and manifest.get("verified") is True
            and manifest.get("error") is None, "Task 8 verification did not pass")
    checks = manifest.get("checks")
    require(isinstance(checks, list) and bool(checks) and all(
        isinstance(c, dict) and c.get("ok") is True and isinstance(c.get("name"), str) for c in checks),
        "Task 8 checks must be successful JSON booleans")
    require(len({c["name"] for c in checks}) == len(checks), "duplicate Task 8 checks")
    expected = spec["expected_identity"]
    identity = manifest.get("final_run_identity", {})
    require(all(identity.get(k) == value for k, value in expected.items()), "Task 8 frozen run identity mismatch")
    require(manifest.get("decision_manifest_sha256") == expected["decision_manifest_sha256"],
            "Task 8 decision digest mismatch")
    generation = manifest.get("generation_id")
    require(isinstance(generation, str) and bool(generation), "Task 8 generation missing")
    companions = manifest.get("companion_files", {})
    require(set(companions) == {"verification_report.md", "reproduction_metadata.json"},
            "Task 8 companion inventory mismatch")
    parent = PurePosixPath(spec["verification_manifest"]).parent
    for name, checksum in companions.items():
        raw, _ = read_input(str(parent / name))
        require(digest(raw) == checksum, f"Task 8 companion hash mismatch: {name}")
    reproduction, _ = read_json(str(parent / "reproduction_metadata.json"))
    require(reproduction.get("generation_id") == generation
            and reproduction.get("verification_status") == "PASS", "Task 8 companion generation mismatch")
    raw_report, _ = read_input(str(parent / "verification_report.md"))
    require(f"`{generation}`" in raw_report.decode("utf-8"), "Task 8 report generation mismatch")

    entries = manifest.get("artifacts", [])
    require(isinstance(entries, list) and all(isinstance(e, dict) for e in entries), "invalid Task 8 artifacts")
    keys = [(e.get("stage"), e.get("path")) for e in entries]
    require(len(set(keys)) == len(keys), "ambiguous Task 8 artifact entries")
    receipts = []
    published = {}
    for binding in spec["artifact_bindings"]:
        selected = [e for e in entries if e.get("stage") == binding["stage"]
                    and e.get("path") == binding["manifest_path"]]
        require(len(selected) == 1, f"{binding['logical_artifact']}: no unique stage/artifact match")
        raw, published_ref = read_input(binding["published_path"])
        actual = digest(raw)
        require(actual == binding["sha256"] == selected[0].get("sha256"),
                f"{binding['logical_artifact']}: published artifact checksum mismatch")
        receipts.append({**binding, "observed_sha256": actual, "verification": "published_bytes_verified"})
        if binding["logical_artifact"] in {"metadata", "run_record", "final_metadata"}:
            published[binding["logical_artifact"]], _ = read_json(binding["published_path"])
    decision, record, metadata = (published[k] for k in ("metadata", "run_record", "final_metadata"))
    require(digest(read_input(spec["metadata"])[0]) == expected["decision_manifest_sha256"],
            "published frozen decision hash mismatch")
    for label, item in (("run record", record), ("final metadata", metadata)):
        require(item.get("dataset_id") == ALIBABA and item.get("schema_version") == "0.2.0",
                f"{label}: dataset/schema mismatch")
        require(item.get("run_id") == expected["run_id"]
                and item.get("decision_manifest_sha256") == expected["decision_manifest_sha256"],
                f"{label}: frozen identity mismatch")
        for field in ("test_target_read_count", "test_evaluator_call_count"):
            require(type(item.get(field)) is int and item[field] == 1, f"{label}: invalid {field}")
    require(record.get("code_commit") == metadata.get("build", {}).get("code_commit")
            == decision.get("build", {}).get("code_commit") == expected["code_commit"],
            "execution commit identity mismatch")
    population = record.get("final_population_size")
    require(type(population) is int and population > 0 and metadata.get("final_population_size") == population,
            "final population mismatch")
    raw_log, _ = read_input(spec["run_log"])
    require(digest(raw_log) == spec.get("run_log_sha256"), "pre-read log checksum mismatch")
    logs = [json.loads(line) for line in raw_log.decode().splitlines() if line.strip()]
    matches = [x for x in logs if x.get("run_id") == expected["run_id"]]
    require(len(matches) == 1 and all(matches[0].get(k) == value for k, value in expected.items()),
            "pre-read log identity mismatch")
    for stage, locked in (("task4_targets", decision.get("task4_inputs", {}).get("targets_manifest")),
                          ("task6_baselines", decision.get("task6_selection", {}).get("baselines_manifest"))):
        stage_entries = {PurePosixPath(e["path"]).name: e["sha256"] for e in entries if e.get("stage") == stage}
        require(isinstance(locked, dict) and bool(locked) and stage_entries == locked,
                f"{stage}: decision/Task 8 input hashes disagree")
    require(record.get("task6_checksums") == decision["task6_selection"]["baselines_manifest"],
            "Task 6 run-record binding mismatch")
    require(record.get("task4_test_sha256") == decision["task4_inputs"]["targets_manifest"]["test.parquet"],
            "Task 4 run-record binding mismatch")
    pr1 = {PurePosixPath(e["path"]).name: e["sha256"] for e in entries if e.get("stage") == "task7_pr1_ml"}
    require(record.get("pr1_checksums") == pr1, "PR1 run-record binding mismatch")
    for resource in ("cpu", "memory"):
        model = decision.get("model_artifacts", {}).get(resource, {})
        require(model.get("sha256") == pr1.get(model.get("file")) and bool(model.get("sha256")),
                f"{resource}: recorded model hash mismatch")
    require(record.get("selected_models") == decision.get("selected_models"), "model selection mismatch")
    selection = decision["task6_selection"]
    require(record.get("selected_baseline_policy") == selection.get("selected_policy")
            and record.get("selected_min_runs") == selection.get("selected_min_runs"), "baseline selection mismatch")
    limitations = manifest.get("unverified_items")
    require(isinstance(limitations, list) and len(limitations) >= 2
            and all(isinstance(x, dict) and isinstance(x.get("item"), str)
                    and isinstance(x.get("reason"), str) for x in limitations), "Task 8 limitations missing")
    return {
        "dataset_id": ALIBABA, "identity": expected, "generation_id": generation,
        "manifest_sha256": ref["sha256"], "bindings": receipts,
        "published_metadata_consistency": "verified", "published_artifact_bytes": "verified",
        "external_physical_artifact_bytes": "UNVERIFIED: not inspected by reporting",
        "historical_exactly_once_execution": "recorded integer-one counters; not independently observed",
        "scientific_inference_reproduction": "UNVERIFIED",
        "november_10_byte_equivalence": "UNVERIFIED: old and new physical bundles not compared",
        "unverified_items": limitations, "final_population_size": population,
        "upstream_reporting_environment": reproduction,
        "followups": ["Run history across earlier decisions remains an upstream follow-up.",
                      "Scientific execution environment differs from the repository lock file.",
                      "Task 8 reporting receipt records a dirty source tree; no clean reproduction is claimed."],
    }


def validate_google_evidence(spec, read_json, read_input):
    """Validate legacy Google identity without certifying contamination fixes."""
    require(spec.get("producer_dataset_id") == "google_subset_v1", "Google producer alias mismatch")
    expected = spec.get("expected_artifacts")
    require(isinstance(expected, dict) and set(expected) == {"metadata", "results", "run_record", "decision_manifest"},
            "Google frozen source digests required")
    for key, checksum in expected.items():
        raw, _ = read_input(spec[key])
        require(digest(raw) == checksum, f"Google {key}: frozen source checksum mismatch")
    decision, decision_ref = read_json(spec["decision_manifest"])
    record, _ = read_json(spec["run_record"])
    require(decision.get("dataset") == spec["producer_dataset_id"], "Google decision dataset mismatch")
    require(record.get("decision_manifest_sha256") == decision_ref["sha256"], "Google decision/run binding mismatch")
    require(record.get("code_state", {}).get("commit") == decision.get("code_state", {}).get("commit")
            and bool(record.get("code_state", {}).get("commit")), "Google execution identity mismatch")
    population = record.get("evaluated_occurrences")
    require(type(population) is int and population > 0, "Google evaluated population invalid")
    require(type(record.get("test_occurrences")) is int and record["test_occurrences"] >= population,
            "Google test/evaluated populations invalid")
    return {"dataset_id": "google_clusterdata2019", "producer_dataset_id": spec["producer_dataset_id"],
            "decision_manifest_sha256": decision_ref["sha256"],
            "execution_commit": record["code_state"]["commit"], "final_population_size": population,
            "published_metadata_consistency": "verified", "published_artifact_bytes": "verified",
            "external_physical_artifact_bytes": "UNVERIFIED: not inspected by reporting",
            "scientific_inference_reproduction": "UNVERIFIED", "historical_exactly_once_execution": "not independently observed",
            "limitations": ["F3/F4: cross-split targets and contaminated validation; not leakage-safe final results.",
                            "F7/F8: abnormal/incomplete records and multi-machine aggregation remain limitations.",
                            "Task 10 correction or documented retention is governed by the validated dataset decision record."]}


def trace_metric_cells(contents, config, read_input):
    """Independently check rendered cells against source rows, not their declared mapping.

    Source CSV decoding matches the reporting pandas reader; output decimal text
    must round-trip to that exact decoded value. No tolerance or imputation is used.
    Canonical rendering separately enforces byte-exact tables and Markdown copies.
    """
    import csv
    import io
    import pandas as pd
    from src.canonical.schema import DEFAULT_CAPABILITY_REGISTRY

    metrics = {"violation_pct": ("{r}_violation_pct", "valid_{r}_violation_count", "%"),
               "average_utilization": ("average_{r}_utilization", "valid_{r}_utilization_count", "ratio"),
               "average_waste": ("average_{r}_waste", "valid_{r}_waste_count", None),
               "average_shortfall": ("average_{r}_shortfall", "valid_{r}_shortfall_count", None)}
    policies = {"Request", "Mean", "P90", "P95", "P99", "ML", "Hybrid"}
    frames, expected = {}, set()
    for dataset in ("google_clusterdata2019", ALIBABA):
        for kind in ("results", "sensitivity"):
            path = config["datasets"][dataset].get(kind)
            if not path:
                continue
            raw, ref = read_input(path)
            frame = pd.read_csv(io.BytesIO(raw))
            frames[(dataset, kind)] = (frame, path, ref["sha256"])
            for _, source in frame.iterrows():
                cut = source["sensitivity"] if kind == "sensitivity" else "all"
                for resource in ("cpu", "memory", "any_resource"):
                    for metric, (column, _, _) in metrics.items():
                        if column.format(r=resource) in frame:
                            expected.add((dataset, cut, resource, source["policy"], metric))
    seen, primary, rendered, conclusions = set(), set(), 0, 0
    def number(text, value, label):
        require((text == "" if pd.isna(value) else text != "" and float(text) == float(value)),
                f"metric source-cell mismatch: {label}")
    for name, text in contents.items():
        if not name.endswith(".csv"):
            continue
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or not {"metric", "value", "source_csv_row"}.issubset(reader.fieldnames):
            continue
        local = set()
        for row in reader:
            dataset, cut, resource, policy, metric = (row[k] for k in
                ("dataset_id", "sensitivity", "resource", "policy", "metric"))
            key = (dataset, cut, resource, policy, metric)
            require(key in expected and key not in local and policy in policies, "metric identity/duplicate mismatch")
            local.add(key); seen.add(key); rendered += 1
            kind = "results" if cut == "all" else "sensitivity"
            if name == f"{dataset}/{kind}.csv":
                primary.add(key)
            frame, path, checksum = frames[(dataset, kind)]
            selected = frame[frame.policy.eq(policy)]
            if kind == "sensitivity":
                selected = selected[selected.sensitivity.eq(cut)]
            require(len(selected) == 1, "ambiguous metric source row")
            index, source = next(selected.iterrows())
            column, denominator, unit = metrics[metric]
            column, denominator = column.format(r=resource), denominator.format(r=resource)
            require(row["source_path"] == path and row["source_sha256"] == checksum
                    and row["source_csv_row"] == str(int(index) + 2)
                    and row["source_column"] == column, "metric source-cell mapping mismatch")
            number(row["value"], source[column], key)
            require(row["denominator_column"] == (denominator if denominator in frame else ""),
                    "metric denominator mapping mismatch")
            number(row["denominator"], source.get(denominator), "denominator")
            require(row["denominator_status"] == ("reported" if pd.notna(source.get(denominator)) else "not reported by source"),
                    "metric denominator missing-value mismatch")
            for field, source_field in (("population_rows", "row_count"), ("source_n_groups", "n_groups"),
                                        ("source_n_common_occurrences", "n_common_occurrences")):
                number(row[field], source.get(source_field), field)
            unit = unit or getattr(DEFAULT_CAPABILITY_REGISTRY[dataset], f"{resource}_unit")
            require(row["unit"] == unit, "metric unit mismatch")
    require(seen == primary == expected, "incomplete generated metric population")
    for row in csv.DictReader(io.StringIO(contents["conclusion_evidence.csv"])):
        frame, path, checksum = frames[(row["dataset_id"], "results")]
        column = f"{row['resource']}_violation_pct"
        require(row["source_path"] == path and row["source_sha256"] == checksum
                and row["source_column"] == column, "conclusion source mapping mismatch")
        for policy in ("Request", "Hybrid"):
            number(row[f"{policy.lower()}_violation_pct"], frame.loc[frame.policy.eq(policy), column].iloc[0], "conclusion")
            conclusions += 1
    return {"unique_source_metric_cells": len(expected), "rendered_metric_cells": rendered,
            "conclusion_metric_cells": conclusions}


def validate_bundle(directory, artifact_root, executing_root):
    """Verify receipt consistency and all accessible bytes, not experiment validity."""
    directory, artifact_root, executing_root = (Path(p).resolve() for p in (directory, artifact_root, executing_root))
    manifest = metadata_schema.loads((directory / "artifact_manifest.json").read_text())
    metadata_schema.validate_metadata(manifest, "manifest")
    require(manifest.get("kind") == "Task 12 reporting artifact manifest v2"
            and manifest.get("schema_version") == 2 and manifest.get("reporting_validation") == "PASS",
            "invalid final reporting manifest")
    validate_final_configuration(manifest["configuration"])
    pending = any(s["decision_status"] == "decision_pending" for s in manifest["configuration"]["datasets"].values())
    require(manifest.get("project_completion") is (not pending)
            and manifest.get("reporting_status") == ("DECISION_PENDING" if pending else "COMPLETE"),
            "reporting decision/completion inconsistency")
    outputs = manifest.get("outputs", [])
    require(isinstance(outputs, list) and len({e["path"] for e in outputs}) == len(outputs),
            "duplicate output inventory")
    expected_files = {"artifact_manifest.json"}
    for entry in outputs:
        relative = safe_path(entry["path"])
        path = (directory / relative).resolve()
        require(path.is_relative_to(directory) and path.is_file(), "missing/unsafe generated output")
        require(digest(path.read_bytes()) == entry["sha256"], f"output checksum mismatch: {relative}")
        expected_files.add(str(relative))
    actual_files = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
    require(actual_files == expected_files, "output inventory does not cover complete bundle")
    receipt = metadata_schema.loads((directory / "report_provenance.json").read_text())
    metadata_schema.validate_metadata(receipt, "receipt")
    for key in ("configuration", "environment", "executable_code", "upstream_evidence", "sources",
                "reporting_status", "project_completion", "verification_scope", "dataset_decisions", "metric_traceability"):
        require(receipt.get(key) == manifest.get(key), f"receipt/manifest disagree: {key}")
    require(receipt.get("kind") == "Task 12 final reporting receipt v2", "invalid final receipt kind")
    output_map = {e["path"]: e["sha256"] for e in outputs}
    require({e["path"]: e["sha256"] for e in receipt["outputs"]} == {
        p: h for p, h in output_map.items() if p != "report_provenance.json"}, "receipt output inventory mismatch")
    from scripts import build_final_cross_dataset_report as reporting
    require(executing_root == reporting.REPO_ROOT.resolve(), "executing checkout must identify running reporting code")
    actual_code, actual_references, _ = reporting.executing_provenance()
    require(manifest["executable_code"] == actual_code, "executable inventory or effective capability registry mismatch")
    require(receipt["reference_documents"] == actual_references, "reference document inventory mismatch")
    for entry in manifest["sources"] + manifest["executable_code"]["files"] + receipt["reference_documents"]:
        base = entry["path_base"]
        if base == "absolute":
            path = Path(entry["path"])
            require(path.is_absolute(), "absolute source path required")
        else:
            require(base in {"input_artifact_root", "executing_checkout"}, "unknown source path base")
            path = (artifact_root if base == "input_artifact_root" else executing_root) / safe_path(entry["path"])
        require(path.is_file() and digest(path.read_bytes()) == entry["sha256"],
                f"source checksum mismatch: {entry['path']}")
    require(manifest.get("verification_scope") == VERIFICATION_SCOPE, "unsupported verification_scope")
    config = manifest["configuration"]
    source_map = {e["path"]: e for e in manifest["sources"]}
    def read_input(name):
        safe_path(name)
        raw = (artifact_root / name).read_bytes()
        require(name in source_map and source_map[name]["sha256"] == digest(raw),
                f"missing or inconsistent evidence source: {name}")
        return raw, source_map[name]
    def read_json(name):
        raw, ref = read_input(name)
        return metadata_schema.loads(raw), ref
    order = ("google_clusterdata2019", ALIBABA, "alibaba_clustertrace2018", "azure_public_vm_v2")
    decisions = [validate_decision(d, config["datasets"][d], read_json, read_input) for d in order]
    require(manifest.get("dataset_decisions") == decisions, "dataset decisions disagree with validated records")
    upstream = {ALIBABA: validate_alibaba_evidence(config["datasets"][ALIBABA], read_json, read_input),
                "google_clusterdata2019": validate_google_evidence(config["datasets"]["google_clusterdata2019"], read_json, read_input)}
    require(manifest.get("upstream_evidence") == upstream, "unsupported upstream verification claims")
    require((directory / "limitations.md").read_text() == limitations_text(config, upstream, order, decisions),
            "human-readable limitations disagree with provenance")
    # Re-render reporting artifacts from validated inputs; never publish or evaluate models.
    # Exact document comparison rejects extra conflicting prose anywhere in either document.
    import tempfile
    from scripts.build_final_cross_dataset_report import build_report
    with tempfile.TemporaryDirectory(prefix="task12-canonical-documents-") as temporary:
        canonical = build_report(config, artifact_root, Path(temporary) / "unused", _validation_only=True)
    require(manifest["sources"] == canonical["sources"], "source inventory differs from consumed authoritative inputs")
    texts = canonical["contents"]
    require(expected_files == set(texts) | {"report_provenance.json", "artifact_manifest.json"},
            "generated artifact inventory differs from canonical output")
    rendered = {name: (directory / name).read_text() for name in texts}
    audit = trace_metric_cells(rendered, config, read_input)
    require(manifest.get("metric_traceability") == audit, "metric traceability receipt mismatch")
    for name, text in texts.items():
        require((directory / name).read_text() == text,
                f"canonical reporting document or rendered table disagrees with validated state: {name}")
    import pandas as pd
    def markdown_rows(rows):
        columns = list(rows[0])
        def cell(value):
            return str(value).replace("|", "\\|").replace("\n", " ")
        return "\n".join(["| " + " | ".join(columns) + " |",
                           "| " + " | ".join("---" for _ in columns) + " |"] +
                          ["| " + " | ".join(cell(row[c]) for c in columns) + " |" for row in rows]) + "\n"
    require((directory / "reporting_decisions.md").read_text() == markdown_rows(decisions),
            "rendered dataset decisions disagree with records")
    expected_decisions = pd.DataFrame(decisions).to_csv(index=False, lineterminator="\n")
    require((directory / "reporting_decisions.csv").read_text() == expected_decisions,
            "rendered dataset decisions disagree with records")
    claims = ("published_metadata_consistency", "published_artifact_bytes", "external_physical_artifact_bytes",
              "historical_exactly_once_execution", "scientific_inference_reproduction")
    rows = [{"dataset_id": d, "claim": claim,
             "status": upstream.get(d, {}).get(claim, "not applicable: no scientific results")}
            for d in order for claim in claims]
    require((directory / "evidence_status.csv").read_text() == pd.DataFrame(rows).to_csv(index=False, lineterminator="\n"),
            "rendered verification claims disagree with provenance")
    require((directory / "evidence_status.md").read_text() == markdown_rows(rows),
            "rendered verification claims disagree with provenance")
    return manifest
