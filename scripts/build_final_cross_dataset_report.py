#!/usr/bin/env python3
"""Task 12 PR 1: render existing summaries, never execute a pipeline.

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
import math
from pathlib import Path
import platform
import sys

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from src.canonical import schema as capability_schema

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
    profiles = {key: value.to_dict() for key, value in DEFAULT_CAPABILITY_REGISTRY.items()}
    encoded = json.dumps(profiles, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    code = {
        "path_base_description": "executing_checkout is the checkout containing the running generator; it is independent of --root",
        "files": [generator, schema],
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


def validate_summary(frame: pd.DataFrame, dataset: str, sensitivity=False):
    if frame.empty:
        raise ReportError(f"{dataset}: empty result table")
    forbidden = [c for c in frame if "gpu" in c.lower() or (
        dataset == ALIBABA and "any_resource" in c.lower()
        and c != "any_resource_metric_reported")]
    if forbidden:
        raise ReportError(f"{dataset}: unsupported metrics {forbidden}")
    required = {"policy", "row_count"}
    for r in ("cpu", "memory"):
        required.update({f"{r}_violation_pct", f"valid_{r}_violation_count",
                         f"average_{r}_utilization", f"valid_{r}_utilization_count"})
    if sensitivity:
        required.add("sensitivity")
    if "any_resource_violation_pct" in frame:
        required.add("valid_any_resource_violation_count")
    if not required.issubset(frame.columns):
        raise ReportError(f"{dataset}: missing columns {sorted(required - set(frame.columns))}")
    keys = ["sensitivity", "policy"] if sensitivity else ["policy"]
    if frame[keys].isna().any().any() or frame.duplicated(keys).any():
        raise ReportError(f"{dataset}: null or duplicate policy/cut")
    groups = frame.groupby("sensitivity", sort=False) if sensitivity else [("all", frame)]
    for cut, group in groups:
        if set(group.policy) != set(POLICIES):
            raise ReportError(f"{dataset}: {cut} must contain exactly seven policies")
    if sensitivity and set(frame.sensitivity) != set(CUTS):
        raise ReportError(f"{dataset}: incomplete or unknown sensitivity cuts")
    for col in frame:
        if col == "row_count" or col.startswith("valid_") or col.endswith("_pct") or col.startswith("average_"):
            values = pd.to_numeric(frame[col], errors="raise")
            if ((values.notna() & ~values.map(lambda x: pd.isna(x) or math.isfinite(x)))
                    | (values < 0)).any():
                raise ReportError(f"{dataset}: invalid numeric values in {col}")
            if col == "row_count" or col.startswith("valid_"):
                if (values.dropna() % 1 != 0).any():
                    raise ReportError(f"{dataset}: noninteger count in {col}")
                if col.startswith("valid_") and (values > frame.row_count).any():
                    raise ReportError(f"{dataset}: denominator exceeds row_count")
            if col.endswith("_pct") and (values > 100).any():
                raise ReportError(f"{dataset}: percentage exceeds 100")
    if frame.row_count.isna().any():
        raise ReportError(f"{dataset}: missing row_count")
    if dataset == ALIBABA:
        for col, expected in (("cpu_result_semantics", "average_usage"),
                              ("primary_resource", "memory")):
            # Empty sensitivity cuts have no metadata or metrics.
            populated = frame.loc[frame.row_count.gt(0)]
            if col not in frame or not populated[col].eq(expected).all():
                raise ReportError(f"Alibaba requires {col}={expected}")
        if "any_resource_metric_reported" in frame:
            if not frame.any_resource_metric_reported.dropna().eq(False).all():
                raise ReportError("Alibaba any-resource reporting must be false")


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


def build_report(config: dict, root: Path, out_dir: Path, *, strict=False):
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
    root, out_dir = root.resolve(), out_dir.resolve()
    if out_dir.exists() and any(out_dir.iterdir()):
        raise ReportError("Output directory must be new or empty")
    code, references, backing_files = executing_provenance()
    sources, contents, statuses, contracts = {}, {}, [], []
    source_bindings = {}

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
        return json.loads(raw), receipt

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
        mode = spec.get("completion", "not_attempted")
        if mode not in {"pipeline_artifacts_available", "adapter_demonstration", "feasibility_only",
                        "not_attempted", "deferred"}:
            raise ReportError(f"{dataset}: unsupported completion status")
        status, reason = "provisional", spec.get("reason", "Verification not supplied")
        sections += [f"## {dataset}", "", reason, ""]
        if dataset == GOOGLE:
            sections += ["Task 10 before/after comparison: **pending approved artifacts**. "
                         "Earlier results may contain cross-split targets and contaminated validation "
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
            validate_summary(frame, dataset)
            # Validate supplied manifest consistency only. Self-reported checks and
            # matching hashes cannot establish authoritative upstream verification.
            if spec.get("verification_manifest"):
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
                validate_summary(sensitivity, dataset, sensitivity=True)
                table(f"{dataset}/sensitivity", result_rows(sensitivity, dataset, ref, status, True))
                sections += [f"[Sensitivity results]({dataset}/sensitivity.md): same-second, "
                             "multi-instance and group-weighted source summaries.", ""]
            elif dataset == ALIBABA:
                sections += ["Sensitivity results: **pending supplied artifact**.", ""]
        statuses.append({"dataset_id": dataset, "completion": mode, "report_status": status,
                         "reason": reason, "metadata_source": metadata_ref["path"] if metadata_ref else None})
    table("dataset_status", pd.DataFrame(statuses))
    table("contract_comparison", pd.DataFrame(contracts))
    table("comparability", pd.DataFrame([
        {"item": "Capabilities, units, scope, recurrence and adapter contracts", "comparison": "Contract comparison only"},
        {"item": "Policy ordering", "comparison": "Within each dataset and evaluation population only"},
        {"item": "Raw accuracy, violation, utilization and CPU percentages", "comparison": "No cross-dataset numeric comparison or ranking"},
    ]))
    contents["report.md"] = "\n".join(sections)
    inventory = [{"category": "input_artifact", "role": "artifact", **ref}
                 for ref in sorted(sources.values(), key=lambda s: s["path"])]
    inventory.extend({"category": "executable_code", **ref} for ref in code["files"])
    inventory.extend({"category": "reference_document", **ref} for ref in references)
    contents["report_sources.csv"] = pd.DataFrame(inventory).to_csv(index=False, lineterminator="\n")
    provenance = {"kind": RECEIPT_KIND,
                  "environment": {"python": platform.python_version(), "pandas": pd.__version__,
                                  "matplotlib": version("matplotlib")},
                  "executable_code": code, "reference_documents": references,
                  "configuration": config, "sources": sorted(sources.values(), key=lambda s: s["path"]),
                  "outputs": [{"path": name, "sha256": hashlib.sha256(data.encode()).hexdigest()}
                              for name, data in sorted(contents.items())]}
    contents["report_provenance.json"] = json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False) + "\n"
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
    for name, data in sorted(contents.items()):
        path = out_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
    return provenance


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="Input configuration JSON or an existing report receipt")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Input artifact root; does not select executable code")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--strict", action="store_true", help="Fail if either pipeline result table is missing")
    args = parser.parse_args(argv)
    try:
        config = json.loads(args.config.read_text())
        if not isinstance(config, dict):
            raise ReportError("Configuration must be a JSON object")
        if config.get("kind") == RECEIPT_KIND:
            config = config["configuration"]
        build_report(config, args.root, args.out_dir, strict=args.strict)
    except (ReportError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"REPORT FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote reporting tables, figures and source receipts to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
