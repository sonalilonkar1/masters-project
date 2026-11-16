#!/usr/bin/env python3
"""Task 12: render existing summaries, never execute a pipeline.

Input paths in the JSON configuration are relative to --root (repository by
default). Executable provenance always identifies the running checkout.
Use a new output directory on every run. PR 1 pipeline results remain provisional.
Source receipts establish reporting traceability, not experimental reproducibility.
"""

from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import version
import inspect
import io
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from src.canonical import schema as capability_schema
from src.reporting import artifact_provenance, summary_validation, metadata_schema

# The Python module constructs these profiles; no capability JSON is loaded.
DEFAULT_CAPABILITY_REGISTRY = capability_schema.DEFAULT_CAPABILITY_REGISTRY

GOOGLE = "google_clusterdata2019"
ALIBABA = "alibaba_gpu_v2020"
ORDER = (GOOGLE, ALIBABA, "alibaba_clustertrace2018", "azure_public_vm_v2")
POLICIES = ("Request", "Mean", "P90", "P95", "P99", "ML", "Hybrid")
CUTS = ("occurrence_weighted", "same_second_excluded", "same_second_only",
        "multi_instance", "group_weighted")
CPU_LABEL = "average-usage sizing, not peak safety"
RECEIPT_KIND = "PR1 reporting receipt; not the final release manifest"
FINAL_RECEIPT_KIND = "Task 12 final reporting receipt v2"
FINAL_MANIFEST_KIND = "Task 12 reporting artifact manifest v2"
NONCOMPARABILITY = (
    "Raw violation, utilization, accuracy and CPU percentages must not be "
    "compared or ranked across datasets: units, workload scope and targets differ."
)
# Scope and aggregation definitions absent from some legacy metadata are taken
# from canonical_workload_schema.md, whose exact bytes enter the source receipt.
DOCUMENTED_CONTRACT = {
    GOOGLE: ("full_workload", "aligned-window sum across parallel executions, then peak"),
    ALIBABA: ("task_role_per_instance", "maximum across covered workers; worker peaks never summed"),
    "alibaba_clustertrace2018": ("instance", "source instance summaries"),
    "azure_public_vm_v2": ("VM / CPU interval (identity unresolved)", "source VM CPU readings; no observed memory"),
}
METRICS = (
    ("violation_pct", "{r}_violation_pct", "valid_{r}_violation_count", "%"),
    ("average_utilization", "average_{r}_utilization", "valid_{r}_utilization_count", "ratio"),
    ("average_waste", "average_{r}_waste", "valid_{r}_waste_count", "resource"),
    ("average_shortfall", "average_{r}_shortfall", "valid_{r}_shortfall_count", "resource"),
)


class ReportError(ValueError):
    """Invalid or insufficient reporting inputs."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def executing_provenance():
    """Identify actual module files and effective profiles, independently of --root.

    Keep portable paths relative to the executing checkout, not the input root.
    An imported module outside that checkout is identified by its absolute path.
    The effective registry snapshot also records the values actually consumed,
    rather than claiming the mirrored capability JSON was loaded.
    """
    backing_files = []

    def record(path, role):
        physical = Path(path).resolve()
        local = physical.is_relative_to(REPO_ROOT)
        ref = {
            "role": role,
            "path": physical.relative_to(REPO_ROOT).as_posix() if local else str(physical),
            "path_base": "executing_checkout" if local else "absolute",
            "sha256": sha256(physical),
        }
        backing_files.append((physical, ref))
        return ref

    generator = record(__file__, "generator")
    # Inspect the imported module itself, not an assumed file below --root.
    schema = record(inspect.getsourcefile(capability_schema), "schema_and_capability_definitions")
    record(inspect.getsourcefile(artifact_provenance), "published_evidence_validator")
    record(inspect.getsourcefile(summary_validation), "scientific_summary_validator")
    record(inspect.getsourcefile(metadata_schema), "report_metadata_schema")
    record(inspect.getsourcefile(summary_validation.task8), "audited_task8_csv_contract")
    profiles = {key: value.to_dict() for key, value in DEFAULT_CAPABILITY_REGISTRY.items()}
    encoded = json.dumps(profiles, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    code = {
        "path_base_description": "executing_checkout is the checkout containing the running generator; it is independent of --root",
        "files": [ref for _, ref in backing_files],
        "capability_registry": {
            "definition_module": capability_schema.__name__,
            "definition_path": schema["path"],
            "definition_path_base": schema["path_base"],
            "configuration_source": "Python definitions; config/dataset_capabilities.json is not loaded",
            "effective_profiles": profiles,
            "sha256": hashlib.sha256(encoded).hexdigest(),
        },
    }
    reference = record(REPO_ROOT / "docs/design/canonical_workload_schema.md", "scope_aggregation_reference")
    return code, [reference], backing_files


def display(value):
    if value is None or pd.isna(value):
        return "—"
    if isinstance(value, float):
        return format(value, ".17g")
    return str(value).replace("|", "\\|").replace("\n", " ")


def markdown(frame: pd.DataFrame) -> str:
    rows = ["| " + " | ".join(frame.columns) + " |",
            "| " + " | ".join("---" for _ in frame.columns) + " |"]
    rows.extend("| " + " | ".join(display(v) for v in row) + " |"
                for row in frame.itertuples(index=False, name=None))
    return "\n".join(rows) + "\n"


def validate_summary(frame: pd.DataFrame, dataset: str, sensitivity=False,
                     comparison=None, final_population=None):
    from src.reporting.summary_validation import validate_summary as validate
    try:
        validate(frame, dataset, sensitivity, comparison, final_population)
    except (ValueError, KeyError, TypeError) as exc:
        raise ReportError(str(exc)) from exc


def result_rows(frame, dataset, source, status, sensitivity=False):
    """Reshape reported values only. Never fill or calculate missing metrics."""
    records = []
    resources = ("memory", "cpu") if dataset == ALIBABA else ("cpu", "memory")
    if dataset == GOOGLE and "any_resource_violation_pct" in frame:
        resources += ("any_resource",)
    cuts = CUTS if sensitivity else ("all",)
    for resource in resources:
        unit = getattr(DEFAULT_CAPABILITY_REGISTRY[dataset], f"{resource}_unit", None)
        semantics = CPU_LABEL if dataset == ALIBABA and resource == "cpu" else (
            "lifetime peak" if dataset == ALIBABA else "full-workload occurrence peak")
        if resource == "any_resource":
            semantics = "CPU or memory peak violation"
        for cut in cuts:
            for policy in POLICIES:
                mask = frame.policy.eq(policy)
                if sensitivity:
                    mask &= frame.sensitivity.eq(cut)
                idx = frame.index[mask][0]
                row = frame.loc[idx]
                for metric, template, denominator, metric_unit in METRICS:
                    col, denom = template.format(r=resource), denominator.format(r=resource)
                    if col not in frame:
                        continue
                    records.append({
                        "dataset_id": dataset, "status": status, "sensitivity": cut,
                        "resource": resource, "semantics": semantics, "policy": policy,
                        "metric": metric, "unit": unit if metric_unit == "resource" else metric_unit,
                        "value": row[col], "denominator": row.get(denom),
                        "denominator_status": "reported" if pd.notna(row.get(denom)) else "not reported by source",
                        "population_rows": row.row_count,
                        "source_n_groups": row.get("n_groups"),
                        "source_n_common_occurrences": row.get("n_common_occurrences"),
                        "source_path": source["path"], "source_sha256": source["sha256"],
                        "source_csv_row": int(idx) + 2, "source_column": col,
                        "denominator_column": denom if denom in frame else None,
                    })
    return pd.DataFrame(records)


def figure(table, resource, dataset, status):
    """A separate within-dataset chart; SVG metadata and IDs are deterministic."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import io

    values = table.loc[table.resource.eq(resource) & table.metric.eq("violation_pct")]
    title = f"{dataset}: {resource} — {status}"
    if dataset == ALIBABA and resource == "cpu":
        title += f"\n{CPU_LABEL}"
    with matplotlib.rc_context({"svg.hashsalt": "task12-pr1", "font.family": "DejaVu Sans"}):
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.bar(values.policy, pd.to_numeric(values.value), color="#3274a1")
        ax.set_title(title)
        ax.set_ylabel("Average CPU usage exceedance (%)" if dataset == ALIBABA and resource == "cpu"
                      else "Peak violation (%)")
        ax.set_ylim(bottom=0)
        fig.tight_layout()
        stream = io.StringIO()
        fig.savefig(stream, format="svg", metadata={"Date": None})
        plt.close(fig)
        # Matplotlib emits trailing spaces in multiline SVG path attributes.
        # Newlines still separate the path tokens after whitespace normalization.
        return "\n".join(line.rstrip() for line in stream.getvalue().splitlines()) + "\n"


def build_report(config: dict, root: Path, out_dir: Path, *, strict=False, require_complete=False, _validation_only=False):
    if not isinstance(config, dict):
        raise ReportError("Configuration must be a JSON object")
    datasets = config.get("datasets")
    if not isinstance(datasets, dict):
        raise ReportError("Configuration datasets must be a JSON object")
    if set(datasets) != set(ORDER):
        raise ReportError("Configuration must state all four dataset IDs")
    for dataset, spec in datasets.items():
        if not isinstance(spec, dict):
            raise ReportError(f"{dataset}: dataset specification must be a JSON object")
    if "report_version" in config and config["report_version"] != 2:
        raise ReportError("unsupported report version")
    final_mode = config.get("report_version") == 2
    if final_mode:
        try:
            artifact_provenance.validate_final_configuration(config)
        except (ValueError, TypeError) as exc:
            raise ReportError(str(exc)) from exc
    elif require_complete:
        raise ReportError("Final completion requires a version 2 configuration")
    root, out_dir = root.resolve(), out_dir.resolve()
    if out_dir.exists() and any(out_dir.iterdir()):
        raise ReportError("Output directory must be new or empty")
    code, references, backing_files = executing_provenance()
    sources, contents, statuses, contracts = {}, {}, [], []
    source_bindings = {}
    upstream_evidence = {}
    evidence_rows = []
    decision_rows = []
    conclusion_rows = []

    def check_digest(ref, actual):
        if actual != ref["sha256"]:
            raise ReportError(
                f"Input integrity error: {ref['path']}: expected initial SHA-256 "
                f"{ref['sha256']}, got {actual}"
            )

    def source(path):
        requested = (root / path).absolute()
        physical = requested.resolve()
        if requested in source_bindings and source_bindings[requested] != physical:
            raise ReportError(f"Input integrity error: {requested}: changed physical target")
        if physical == out_dir or out_dir in physical.parents or physical in out_dir.parents:
            raise ReportError("Output must be separate from input files")
        if not physical.is_file():
            raise ReportError(f"Missing input artifact: {path}")
        source_bindings.setdefault(requested, physical)
        local = physical.is_relative_to(root)
        label = physical.relative_to(root).as_posix() if local else str(physical)
        actual = sha256(physical)
        if label in sources:
            check_digest(sources[label], actual)
        else:
            sources[label] = {
                "path": label, "path_base": "input_artifact_root" if local else "absolute",
                "sha256": actual,
            }
        return physical, sources[label]

    def read_input(path):
        physical, receipt = source(path)
        raw = physical.read_bytes()
        # Parse precisely these checked bytes, not a subsequent filesystem read.
        check_digest(receipt, hashlib.sha256(raw).hexdigest())
        return raw, receipt

    def read_json(path):
        raw, receipt = read_input(path)
        return metadata_schema.loads(raw), receipt

    def read_csv(path):
        raw, receipt = read_input(path)
        return pd.read_csv(io.BytesIO(raw)), receipt

    def table(name, frame):
        contents[name + ".csv"] = frame.to_csv(index=False, na_rep="", float_format="%.17g", lineterminator="\n")
        contents[name + ".md"] = markdown(frame)

    sections = ["# Cross-dataset reporting — PR 1", "", NONCOMPARABILITY, "",
                "These are source renderings. Source hash checks do not certify final experimental "
                "reproducibility. Final release verification and conclusions remain pending.", "",
                "PR 1 keeps all pipeline results provisional, including when an upstream manifest "
                "passes the supplied consistency checks. Authoritative upstream verification and "
                "any promotion of reporting status are deferred to PR 2.", "",
                "Receipts separate input artifacts resolved under `--root` from the actual "
                "executing generator, imported Python capability definitions and effective profile "
                "values. The mirrored capability JSON is not loaded.", "",
                "[Dataset status](dataset_status.md) · [Contract comparison](contract_comparison.md) · "
                "[Comparability](comparability.md) · [Source inventory](report_sources.csv) · "
                "[Reporting receipts](report_provenance.json)", "",
                "Regenerate from the same source files in a new empty output directory "
                "using the configuration embedded in the receipt (input paths resolve under `--root`):", "",
                "```text", "python scripts/build_final_cross_dataset_report.py "
                "--config <report>/report_provenance.json --root <artifact-root> --out-dir <new-directory>",
                "```", ""]
    if final_mode:
        sections = ["# Cross-dataset reporting — Task 12 PR 2", "", NONCOMPARABILITY, "",
                    "Reporting validation is separate from experimental verification. Published bytes and metadata "
                    "are checked; external physical artifacts and historical execution are not independently reproduced.", "",
                    artifact_provenance.completion_statement(all(s["decision_status"] != "decision_pending" for s in datasets.values())), "",
                    "[Dataset status](dataset_status.md) · [Contract comparison](contract_comparison.md) · "
                    "[Comparability](comparability.md) · [Evidence](evidence_status.md) · "
                    "[Limitations](limitations.md) · [Conclusions](conclusions.md) · "
                    "[Artifact manifest](artifact_manifest.json)", ""]
    for dataset in ORDER:
        spec = datasets[dataset]
        profile = DEFAULT_CAPABILITY_REGISTRY[dataset]
        metadata, metadata_ref = read_json(spec["metadata"]) if spec.get("metadata") else ({}, None)
        for key in ("dataset_id",):
            if key in metadata and metadata[key] != dataset:
                raise ReportError(f"{dataset}: metadata dataset_id mismatch")
        embedded_profile = metadata.get("profile", metadata.get("capabilities"))
        if embedded_profile is not None and embedded_profile != profile.to_dict():
            raise ReportError(f"{dataset}: metadata profile disagrees with registry")
        for evidence in spec.get("evidence", []):
            source(evidence)
        if final_mode:
            for evidence in spec.get("decision_evidence", []):
                source(evidence)
            decision_rows.append(artifact_provenance.validate_decision(dataset, spec, read_json, read_input))
            try:
                if dataset == ALIBABA:
                    upstream_evidence[dataset] = artifact_provenance.validate_alibaba_evidence(spec, read_json, read_input)
                elif dataset == GOOGLE:
                    upstream_evidence[dataset] = artifact_provenance.validate_google_evidence(spec, read_json, read_input)
            except (ValueError, KeyError, TypeError) as exc:
                raise ReportError(str(exc)) from exc
        mode = spec.get("completion", "not_attempted")
        if mode not in {"pipeline_artifacts_available", "adapter_demonstration", "feasibility_only",
                        "not_attempted", "deferred"}:
            raise ReportError(f"{dataset}: unsupported completion status")
        status, reason = "provisional", (artifact_provenance.reporting_context(dataset) if final_mode else
                                         spec.get("reason", "Verification not supplied"))
        if final_mode:
            status = "published_evidence_validated" if dataset == ALIBABA else spec["decision_status"]
            for claim in ("published_metadata_consistency", "published_artifact_bytes", "external_physical_artifact_bytes",
                          "historical_exactly_once_execution", "scientific_inference_reproduction"):
                evidence_rows.append({"dataset_id": dataset, "claim": claim,
                                      "status": upstream_evidence.get(dataset, {}).get(claim, "not applicable: no scientific results")})
        sections += [f"## {dataset}", "", reason, ""]
        if dataset == GOOGLE:
            google_decision = ("Task 10 before/after comparison: **pending approved artifacts**. "
                               if not final_mode or decision_rows[-1]["decision_status"] == "decision_pending" else
                               "Task 10 before/after comparison: not supplied. Documented reporting outcome: "
                               + decision_rows[-1]["outcome"] + ". ")
            sections += [google_decision + "Earlier results may contain cross-split targets and contaminated validation "
                         "(F3/F4); they are not leakage-safe final results.", ""]
        contracts.append({
            "dataset_id": dataset, "modeling_unit": metadata.get("canonical_modeling_unit", profile.evaluation_record_level),
            "resource_scope": metadata.get("resource_scope", DOCUMENTED_CONTRACT[dataset][0]),
            "aggregation": metadata.get("occurrence_resource_definition", metadata.get("observed_aggregation_method", DOCUMENTED_CONTRACT[dataset][1])),
            "cpu_unit": profile.cpu_unit, "memory_unit": profile.memory_unit,
            "cpu_semantics": profile.cpu_target_semantics or profile.observed_cpu_semantics,
            "memory_semantics": profile.memory_target_semantics or profile.observed_memory_semantics,
            "recurrence_identity": profile.recurrence_key_origin,
            "supports_targets": profile.supports_targets,
            "target_split_isolation_profile": profile.target_split_isolation if profile.supports_targets else None,
            "target_isolation_metadata": metadata.get("target_split_isolation"),
            "evaluation_mode": profile.evaluation_mode, "cpu_observed": profile.supports_observed_cpu,
            "memory_observed": profile.supports_observed_memory,
            "any_resource_evaluation": profile.any_resource_metric_valid if profile.supports_targets else False,
            "profile_source": code["capability_registry"]["definition_path"], "metadata_source": metadata_ref["path"] if metadata_ref else None,
            "scope_aggregation_reference": references[0]["path"],
        })
        result_path = spec.get("results")
        has_results = bool(result_path and (root / result_path).is_file())
        if dataset not in (GOOGLE, ALIBABA) and (result_path or spec.get("sensitivity")):
            raise ReportError(f"{dataset}: PR 1 accepts scope evidence only, no invented scores")
        if not has_results:
            if strict and dataset in (GOOGLE, ALIBABA):
                raise ReportError(f"{dataset}: missing final results")
            if spec.get("verification_manifest"):
                raise ReportError(f"{dataset}: cannot verify missing results")
            status = "pending" if dataset in (GOOGLE, ALIBABA) else mode
            if dataset in (GOOGLE, ALIBABA):
                mode = "pending_artifacts"
            sections += ["No evaluation numbers reported.", ""]
        else:
            if mode != "pipeline_artifacts_available" or metadata_ref is None:
                raise ReportError(f"{dataset}: results require pipeline status and metadata")
            frame, result_ref = read_csv(result_path)
            validate_summary(frame, dataset, final_population=upstream_evidence.get(dataset, {}).get("final_population_size"))
            if final_mode:
                for resource in (("memory", "cpu") if dataset == ALIBABA else ("cpu", "memory")):
                    indexed = frame.set_index("policy")
                    column = f"{resource}_violation_pct"
                    conclusion_rows.append({"dataset_id": dataset, "resource": resource,
                                            "request_violation_pct": indexed.loc["Request", column],
                                            "hybrid_violation_pct": indexed.loc["Hybrid", column],
                                            "source_path": result_ref["path"], "source_sha256": result_ref["sha256"],
                                            "source_column": column})
            # Validate supplied manifest consistency only. Self-reported checks and
            # matching hashes cannot establish authoritative upstream verification.
            if spec.get("verification_manifest") and not final_mode:
                manifest, _ = read_json(spec["verification_manifest"])
                if manifest.get("verified") is not True or manifest.get("dataset_id") != dataset:
                    raise ReportError(f"{dataset}: upstream verification did not pass")
                checks = manifest.get("checks", [])
                if not checks or any(c.get("ok") is not True for c in checks):
                    raise ReportError(f"{dataset}: absent or failed upstream checks")
                entries = {e["path"]: e["sha256"] for e in manifest.get("artifacts", [])}
                needed = [result_ref, metadata_ref]
                if spec.get("sensitivity"):
                    _, ref = source(spec["sensitivity"])
                    needed.append(ref)
                if any(entries.get(ref["path"]) != ref["sha256"] for ref in needed):
                    raise ReportError(f"{dataset}: upstream manifest does not match all reported artifacts")
            table_rows = result_rows(frame, dataset, result_ref, status)
            table(f"{dataset}/results", table_rows)
            resources = ("memory", "cpu") if dataset == ALIBABA else ("cpu", "memory", "any_resource")
            for i, resource in enumerate(resources, 1):
                subset = table_rows.loc[table_rows.resource.eq(resource)]
                if subset.empty:
                    continue
                stem = f"{dataset}/{i:02d}_{resource}"
                table(stem, subset)
                contents[stem + ".svg"] = figure(table_rows, resource, dataset, status)
                sections += [f"### {resource}: {CPU_LABEL if dataset == ALIBABA and resource == 'cpu' else 'peak outcomes'}",
                             "", f"Status: **{status}**. [Table]({stem}.md) · [Figure]({stem}.svg)", ""]
            if spec.get("sensitivity"):
                if dataset != ALIBABA:
                    raise ReportError("Only Alibaba sensitivity tables are supported in PR 1")
                sensitivity, ref = read_csv(spec["sensitivity"])
                validate_summary(sensitivity, dataset, sensitivity=True, comparison=frame)
                table(f"{dataset}/sensitivity", result_rows(sensitivity, dataset, ref, status, True))
                sections += [f"[Sensitivity results]({dataset}/sensitivity.md): same-second, "
                             "multi-instance and group-weighted source summaries.", ""]
            elif dataset == ALIBABA:
                sections += ["Sensitivity results: **pending supplied artifact**.", ""]
        if final_mode and spec["decision_status"] == "decision_pending" and dataset not in (GOOGLE, ALIBABA):
            mode = "decision_pending"
            status = "decision_pending"
        statuses.append({"dataset_id": dataset, "completion": mode, "report_status": status,
                         "reason": reason, "metadata_source": metadata_ref["path"] if metadata_ref else None})
    table("dataset_status", pd.DataFrame(statuses))
    table("contract_comparison", pd.DataFrame(contracts))
    table("comparability", pd.DataFrame([
        {"item": "Capabilities, units, scope, recurrence and adapter contracts", "comparison": "Contract comparison only"},
        {"item": "Policy ordering", "comparison": "Within each dataset and evaluation population only"},
        {"item": "Raw accuracy, violation, utilization and CPU percentages", "comparison": "No cross-dataset numeric comparison or ranking"},
    ]))
    reporting_complete = final_mode and artifact_provenance.decisions_complete(decision_rows)
    if require_complete and not reporting_complete:
        raise ReportError("Final completion blocked: dataset decision_pending")
    if final_mode:
        table("evidence_status", pd.DataFrame(evidence_rows))
        table("reporting_decisions", pd.DataFrame(decision_rows))
        table("conclusion_evidence", pd.DataFrame(conclusion_rows))
        contents["limitations.md"] = artifact_provenance.limitations_text(config, upstream_evidence, ORDER, decision_rows)
        contents["conclusions.md"] = ("# Reporting conclusions\n\n"
            "Alibaba reports the authoritative published November 15 run, with memory peak outcomes first "
            "and CPU average-usage sizing, not peak safety. This is evidence-linked reporting, not reproduced inference.\n\n"
            "Google results remain subject to the recorded reporting decision and F3/F4/F7/F8 limitations. "
            "Azure and Alibaba 2018 have no recommendation scores in this bundle.\n\n"
            "No dataset-wide numeric ranking or claim of common resource units is supported. "
            "Coverage and legacy slack-reduction metrics are not inferred from these summaries.\n\n"
            "[Within-dataset Request and Hybrid source values](conclusion_evidence.md) provide "
            "descriptive evidence only, without causal claims, new metrics or cross-dataset ranking.\n\n"
            + (artifact_provenance.completion_statement(reporting_complete) + "\n"))
    contents["report.md"] = "\n".join(sections).rstrip() + "\n"
    inventory = [{"category": "input_artifact", "role": "artifact", **ref}
                 for ref in sorted(sources.values(), key=lambda s: s["path"])]
    inventory.extend({"category": "executable_code", **ref} for ref in code["files"])
    inventory.extend({"category": "reference_document", **ref} for ref in references)
    contents["report_sources.csv"] = pd.DataFrame(inventory).to_csv(index=False, lineterminator="\n")
    if _validation_only:
        if not final_mode:
            raise ReportError("Canonical final documents require a version 2 configuration")
        return {"contents": contents, "sources": sorted(sources.values(), key=lambda s: s["path"])}
    provenance = {"kind": FINAL_RECEIPT_KIND if final_mode else RECEIPT_KIND,
                  "environment": {"python": platform.python_version(), "pandas": pd.__version__,
                                  "matplotlib": version("matplotlib"), "numpy": version("numpy"),
                                  "pyarrow": version("pyarrow")},
                  "executable_code": code, "reference_documents": references,
                  "configuration": config, "sources": sorted(sources.values(), key=lambda s: s["path"]),
                  "outputs": [{"path": name, "sha256": hashlib.sha256(data.encode()).hexdigest()}
                              for name, data in sorted(contents.items())]}
    if final_mode:
        provenance["metric_traceability"] = artifact_provenance.trace_metric_cells(contents, config, read_input)
        provenance["verification_scope"] = artifact_provenance.VERIFICATION_SCOPE
        provenance["dataset_decisions"] = decision_rows
        provenance["upstream_evidence"] = upstream_evidence
        provenance["reporting_status"] = "COMPLETE" if reporting_complete else "DECISION_PENDING"
        provenance["project_completion"] = reporting_complete
    if final_mode:
        if "unverified_annotations" in config:
            provenance["unverified_annotations"] = config["unverified_annotations"]
        metadata_schema.validate_metadata(provenance, "receipt")
    contents["report_provenance.json"] = json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if final_mode:
        # No self-hash cycle: the final manifest covers every other output.
        manifest = {"kind": FINAL_MANIFEST_KIND, "schema_version": 2,
                    "reporting_validation": "PASS", "project_completion": reporting_complete,
                    "reporting_status": provenance["reporting_status"],
                    "verification_scope": artifact_provenance.VERIFICATION_SCOPE,
                    "metric_traceability": provenance["metric_traceability"],
                    "configuration": config, "environment": provenance["environment"],
                    "executable_code": code, "upstream_evidence": upstream_evidence,
                    "dataset_decisions": decision_rows, "sources": provenance["sources"],
                    "outputs": [{"path": name, "sha256": hashlib.sha256(data.encode()).hexdigest()}
                                for name, data in sorted(contents.items())]}
        if "unverified_annotations" in config:
            manifest["unverified_annotations"] = config["unverified_annotations"]
        metadata_schema.validate_metadata(manifest, "manifest")
        contents["artifact_manifest.json"] = json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n"
    # Recheck inputs before writing; never let a report silently describe changed bytes.
    for requested, physical in source_bindings.items():
        if requested.resolve() != physical:
            raise ReportError(f"Input integrity error: {requested}: changed physical target")
    for ref in sources.values():
        check_digest(ref, sha256(root / ref["path"]))
    if any(sha256(path) != ref["sha256"] for path, ref in backing_files):
        raise ReportError("Executable code or contract reference changed while reporting")
    if {key: value.to_dict() for key, value in DEFAULT_CAPABILITY_REGISTRY.items()} != code["capability_registry"]["effective_profiles"]:
        raise ReportError("Effective capability registry changed while reporting")
    if final_mode:
        # Build the entire bundle on the destination filesystem, then publish a
        # directory atomically. A failed write never exposes a successful manifest.
        out_dir.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.", dir=out_dir.parent))
        try:
            for name, data in sorted(contents.items()):
                path = staging / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(data, encoding="utf-8")
            os.replace(staging, out_dir)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    else:
        for name, data in sorted(contents.items()):
            path = out_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data, encoding="utf-8")
    return provenance


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="Input configuration JSON or an existing report receipt")
    parser.add_argument("--validate-bundle", type=Path, help="Validate a final bundle and its accessible sources")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Input artifact root; does not select executable code")
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--require-complete", action="store_true", help="Refuse final completion while decisions are pending")
    parser.add_argument("--strict", action="store_true", help="Fail if either pipeline result table is missing")
    args = parser.parse_args(argv)
    try:
        if args.validate_bundle:
            validated = artifact_provenance.validate_bundle(args.validate_bundle, args.root, REPO_ROOT)
            if args.require_complete and not validated["project_completion"]:
                raise ReportError("Final completion blocked: dataset decision_pending")
            print(f"Reporting bundle valid: {validated['reporting_status']}; project_completion={validated['project_completion']}")
            return 0
        if args.config is None or args.out_dir is None:
            raise ReportError("--config and --out-dir are required for generation")
        config = metadata_schema.loads(args.config.read_text())
        if not isinstance(config, dict):
            raise ReportError("Configuration must be a JSON object")
        if config.get("kind") in (RECEIPT_KIND, FINAL_RECEIPT_KIND, FINAL_MANIFEST_KIND):
            config = config["configuration"]
        build_report(config, args.root, args.out_dir, strict=args.strict, require_complete=args.require_complete)
    except (ReportError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"REPORT FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote reporting tables, figures and source receipts to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
