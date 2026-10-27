"""Shared role-occurrence splits, completed history counts and next targets.

Canonical columns are retained for audit/label construction, not declared to be
predictive features. Only cpu_history_count and memory_history_count are new
point-in-time features. Targets, flags, statuses and current-run measurements
must not be used as submission-time features.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import heapq
import json
from pathlib import Path
import shutil
import tempfile

import numpy as np
import pandas as pd

from canonical.schema import DatasetCapabilities, SCHEMA_VERSION, TARGET_STATUSES
from features.split_utils import chronological_split


SPLITS = ("train", "validation", "test")
# Canonical input columns are left untouched;
# null placeholders are permitted, but populated values signal an earlier build.
DERIVED_COLUMNS = (
    "split", "cpu_history_count", "memory_history_count", "actual_cpu",
    "actual_memory", "actual_cpu_unit", "actual_memory_unit",
    "cpu_target_status", "memory_target_status", "next_occurrence_same_second",
)


@dataclass(frozen=True)
class TargetBuildResult:
    """All input rows plus derived columns, and JSON-compatible metadata."""

    rows: pd.DataFrame
    metadata: dict[str, object]


def _resource_field(profile: DatasetCapabilities, resource: str) -> str | None:
    """Resolve resource support and source field from the declared semantics."""
    if not (profile.supports_targets and getattr(profile, f"supports_{resource}")):
        return None
    semantics = getattr(profile, f"{resource}_target_semantics")
    if semantics is None:
        return None
    # Select an average or a peak from the profile's meaning, not the dataset ID.
    # For Alibaba GPU 2020 this resolves to observed_cpu and peak_memory.
    average = semantics == "next_occurrence_lifetime_average"
    kind = "average" if average else "peak"
    if not (getattr(profile, f"supports_observed_{resource}")
            and getattr(profile, f"has_{resource}_{kind}")):
        return None
    if getattr(profile, f"{resource}_unit") is None:
        raise ValueError(f"Supported {resource} target requires a profile unit")
    return f"{'observed' if average else 'peak'}_{resource}"


def _validate(rows: pd.DataFrame, profile: DatasetCapabilities,
              fields: dict[str, str | None]) -> None:
    if profile.evaluation_record_level != "role_occurrence":
        raise ValueError("This builder requires evaluation_record_level='role_occurrence'")
    if not profile.supports_recurrence:
        raise ValueError("Target building requires supports_recurrence")
    required = {
        "dataset_id", "record_level", "role_key", "occurrence_id", "recurrence_key",
        "start_time_us", "end_time_us", "exclusion_reason",
    }
    for resource, field in fields.items():
        if field:
            required.update((field, f"{resource}_validity_status"))
    missing = sorted(required.difference(rows.columns))
    if missing:
        raise ValueError(f"Missing required target-builder columns: {missing}")
    if not rows["record_level"].eq(profile.evaluation_record_level).fillna(False).all():
        raise ValueError("Every input row must have record_level='role_occurrence'; audit rows are forbidden")
    if not rows["dataset_id"].eq(profile.dataset_id).fillna(False).all():
        raise ValueError("Input dataset_id does not match the dataset profile")
    existing = [c for c in (*DERIVED_COLUMNS, "_split")
                if c in rows and rows[c].notna().any()]
    if existing:
        raise ValueError(f"Builder columns already populated: {existing}")
    if rows["role_key"].isna().any() or rows["role_key"].duplicated().any():
        raise ValueError("role_key must be non-null and unique")
    # Excluded rows stay in the returned audit frame, but their missing resource values and recurrence keys must not affect processing of eligible rows.
    eligible = rows.loc[rows["exclusion_reason"].isna()]
    for column in ("occurrence_id", "recurrence_key", "start_time_us"):
        if eligible[column].isna().any():
            raise ValueError(f"Eligible rows require non-null {column}")
    for column in ("start_time_us", "end_time_us"):
        values = eligible[column].dropna()
        if (not pd.api.types.is_integer_dtype(values.dtype)
                and (not pd.api.types.is_numeric_dtype(values.dtype)
                     or not np.isfinite(values).all() or (values % 1 != 0).any())):
            raise ValueError(f"{column} must contain integer microseconds")
    timed = eligible["end_time_us"].notna()
    if (eligible.loc[timed, "end_time_us"] < eligible.loc[timed, "start_time_us"]).any():
        raise ValueError("end_time_us cannot precede start_time_us")
    if eligible.groupby("occurrence_id")["start_time_us"].nunique().gt(1).any():
        raise ValueError("All roles of an occurrence must share start_time_us")
    for resource, field in fields.items():
        if field:
            status = eligible[f"{resource}_validity_status"]
            if not status.isin(("valid", "partial", "invalid")).all():
                raise ValueError(f"Eligible {resource}_validity_status must be valid, partial or invalid")
            values = eligible[field].dropna()
            if (not pd.api.types.is_numeric_dtype(values.dtype)
                    or not np.isfinite(values).all() or values.lt(0).any()):
                raise ValueError(f"{field} must contain finite non-negative numbers or null")


def _history(ordered: pd.DataFrame, usable: dict[str, pd.Series]) -> dict[str, pd.Series]:
    """Sweep predecessors; release their resource values only upon completion.

    The current row is queried before insertion, including zero-duration rows.
    Complexity is O(n log n), with no pairwise joins or dependence on split.
    """
    counts = {r: pd.Series(0, index=ordered.index, dtype="Int64") for r in usable}
    masks = {r: s.to_dict() for r, s in usable.items()}
    for _, group in ordered.groupby("recurrence_key", sort=False):
        # Start order and completion order can differ when runs overlap. The
        # heap exposes the earliest completion among predecessors seen so far.
        # Each entry stores (end time, unique row position, CPU usable, memory
        # usable); the row position makes equal completion times deterministic.
        pending: list[tuple[int, int, bool, bool]] = []
        completed = [0, 0]
        for index, start, end in zip(group.index, group["start_time_us"], group["end_time_us"]):
            # Completion exactly at submission is allowed by schema §11.
            # Adding booleans increments each resource's count independently.
            while pending and pending[0][0] <= start:
                _, _, cpu, memory = heapq.heappop(pending)
                completed[0] += cpu
                completed[1] += memory
            for pos, resource in enumerate(("cpu", "memory")):
                counts[resource].at[index] = completed[pos]
            # Insert only after recording this row's history: a zero-duration
            # Run cannot count itself, but can count for a later tied row.
            # A missing completion time never establishes availability.
            if pd.notna(end):
                heapq.heappush(pending, (int(end), int(index),
                                        bool(masks["cpu"][index]), bool(masks["memory"][index])))
    return counts


def build_targets(role_occurrences: pd.DataFrame,
                  profile: DatasetCapabilities) -> TargetBuildResult:
    """Build 70/15/15 splits, history and targets without mutating input.

    History requires a deterministic predecessor with end <= current start.
    Excluded rows have null derived columns. Unsupported resources take status
    precedence, then no successor, split isolation, invalid resource, available.
    Same-second means equal integer second buckets of submission timestamps.
    At least three eligible timestamp groups are required by chronological_split.
    """
    fields = {r: _resource_field(profile, r) for r in ("cpu", "memory")}
    _validate(role_occurrences, profile, fields)
    # Internal unique positions prevent ambiguous pandas alignment when the caller supplies duplicate indexes. Restore the caller's index at return.
    original_index = role_occurrences.index.copy()
    rows = role_occurrences.reset_index(drop=True).copy()
    rows = rows.drop(columns=[c for c in (*DERIVED_COLUMNS, "_split") if c in rows])
    eligible = rows.loc[rows["exclusion_reason"].isna()].copy()
    # Preserve whole submission-timestamp groups using the unchanged helper.
    # Its default fractions are approximate when a group straddles a boundary.
    train, validation, test, split_meta = chronological_split(
        eligible, time_col="start_time_us", id_col="role_key")
    split_by_key = pd.concat((train, validation, test)).set_index("role_key")["_split"]
    # Translate Google's internal helper label locally. Excluded keys are absent from this lookup, so their canonical split remains null.
    rows["split"] = rows["role_key"].map(split_by_key).replace({"val": "validation"}).astype("string")
    # This total order defines both predecessors and immediate successors.
    # Resource missingness never removes an eligible row from the sequence.
    ordered = rows.loc[rows["exclusion_reason"].isna()].sort_values(
        ["recurrence_key", "start_time_us", "occurrence_id", "role_key"], kind="mergesort")
    usable = {}
    for resource, field in fields.items():
        # A populated partial observation is usable; row-level validity does not gate both resources. Missing CPU therefore leaves memory unaffected.
        usable[resource] = (ordered[field].notna()
                            & ordered[f"{resource}_validity_status"].ne("invalid")) if field else pd.Series(
                                False, index=ordered.index)
    # History intentionally spans earlier and current splits, subject to the completion check. Target isolation below is a separate restriction.
    counts = _history(ordered, usable)
    # Nullable integers avoid float rounding at a second boundary when shift, introduces a missing successor (including timestamps above 2**53).
    successor = ordered.assign(start_time_us=ordered["start_time_us"].astype("Int64")).groupby("recurrence_key", sort=False)[
        ["start_time_us", "split", "role_key"]].shift(-1)
    has_next = successor["role_key"].notna()
    crosses = has_next & successor["split"].ne(ordered["split"])
    # This describes successor timing even if its resource target is unavailable.
    # Equal second buckets differ from an elapsed-time gap of less than a second.
    rows["next_occurrence_same_second"] = pd.Series(pd.NA, index=rows.index, dtype="boolean")
    same_second = has_next & (successor["start_time_us"] // 1_000_000).eq(
        ordered["start_time_us"] // 1_000_000)
    rows.loc[ordered.index, "next_occurrence_same_second"] = same_second.astype("boolean")
    for resource, field in fields.items():
        # Reindexing eligible-only calculations introduces nulls for excluded rows; eligible rows without history retain an explicit zero count.
        rows[f"{resource}_history_count"] = counts[resource].reindex(rows.index).astype("Int64")
        status = pd.Series("unsupported_resource", index=ordered.index, dtype="string")
        actual = pd.Series(pd.NA, index=ordered.index, dtype="Float64")
        if field:
            # Shift the full eligible sequence, not just usable measurements.
            # Otherwise a missing immediate successor could be skipped silently.
            next_value = ordered.groupby("recurrence_key", sort=False)[field].shift(-1)
            next_usable = usable[resource].groupby(ordered["recurrence_key"], sort=False).shift(-1).eq(True)
            status[:] = "no_next_occurrence"
            status.loc[has_next] = "next_occurrence_ineligible_resource"
            available = has_next & next_usable
            # Cross-split status overrides resource invalidity. The value is copied only after isolation is applied, so it stays null here.
            if profile.target_split_isolation:
                available &= ~crosses
                status.loc[crosses] = "next_occurrence_in_other_split"
            status.loc[available] = "available"
            actual.loc[available] = next_value.loc[available]
        rows[f"{resource}_target_status"] = status.reindex(rows.index)
        rows[f"actual_{resource}"] = actual.reindex(rows.index)
        rows[f"actual_{resource}_unit"] = pd.Series(pd.NA, index=rows.index, dtype="string")
        if field:
            rows.loc[ordered.index, f"actual_{resource}_unit"] = getattr(profile, f"{resource}_unit")
        if not actual.notna().eq(status.eq("available")).all():
            raise RuntimeError(f"{resource} status/value invariant failed")
    if rows.loc[ordered.index].groupby("occurrence_id")["split"].nunique().gt(1).any():
        raise RuntimeError("An occurrence spans multiple splits")

    # Canonical labels throughout metadata; keep helper boundary values intact.
    split_meta = {key.replace("val_", "validation_"): value for key, value in split_meta.items()}
    split_meta = {k: v.item() if isinstance(v, np.generic) else v for k, v in split_meta.items()}
    per_split = {}
    for split in SPLITS:
        part = rows.loc[rows["split"].eq(split)]
        # Structural successor counts and resource-available target counts have different denominators when, for example, next-run CPU is missing.
        per_split[split] = {
            "rows": len(part), "occurrences": int(part["occurrence_id"].nunique()),
            "in_split_successor_rows": int((has_next & ~crosses).reindex(part.index).sum()),
            "same_second_successor_rows": int(part["next_occurrence_same_second"].sum()),
        }
        for resource in fields:
            # Include zero counts so downstream reports share a fixed vocabulary.
            per_split[split][f"{resource}_status_counts"] = {
                s: int(part[f"{resource}_target_status"].eq(s).sum()) for s in sorted(TARGET_STATUSES)}
            per_split[split][f"same_second_available_{resource}_targets"] = int(
                (part["next_occurrence_same_second"] & part[f"{resource}_target_status"].eq("available")).sum())
    references = {}
    # Dataset-specific reference figures affect reporting only, never assignment of splits, histories, or targets. Final exclusions can change these counts.
    if profile.dataset_id == "alibaba_gpu_v2020":
        for split, population, flags in (("validation", 42104, 245), ("test", 44087, 251)):
            actual = per_split[split]["in_split_successor_rows"]
            references[split] = {
                "reference_in_split_successor_rows": population,
                "actual_in_split_successor_rows": actual, "population_difference": actual - population,
                "reference_same_second_rows": flags,
                "same_second_difference": per_split[split]["same_second_successor_rows"] - flags,
            }
    metadata = {
        "schema_version": SCHEMA_VERSION, "dataset_id": profile.dataset_id,
        "capabilities": asdict(profile), "input_rows": len(rows),
        "eligible_rows": len(ordered), "excluded_rows": len(rows) - len(ordered),
        "split": split_meta, "per_split": per_split,
        "target_order": ["start_time_us", "occurrence_id", "role_key"],
        "resource_fields": fields,
        "history_policy": "eligible deterministic predecessors; resource non-null and not invalid; end_time_us <= start_time_us; earlier or same split",
        "predictive_feature_columns": ["cpu_history_count", "memory_history_count"],
        "same_second_policy": "equal start_time_us // 1000000; immediate eligible successor; independent of resource availability",
        "reference_comparison": references,
        "reference_notes": "References predate the final 256-row multi_attempt_worker exclusion. Exclusion can remove rows, change successors and move split boundaries. Structural successor counts and available CPU/memory counts are reported separately; exact historical attribution is unavailable from the final eligible population alone.",
        "output_paths": {},
    }
    if references:
        metadata["results_documentation"] = "data built from c2ae87f; Task 4 consumes the validated Task 3 role_occurrence view without rebuilding it."
    rows.index = original_index
    return TargetBuildResult(rows=rows, metadata=metadata)


def write_target_tables(result: TargetBuildResult, output_dir: Path) -> dict[str, object]:
    """Publish eligible split tables and metadata to a new, separate directory.

    Never pass the Task 3 canonical directory. Existing directories are refused.
    No audit or rejected artifact is read. Staging is removed on failure.
    """
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to replace existing output: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    # Copy metadata before adding paths so writing does not mutate the build result. JSON conversion also checks that the metadata can be serialized.
    metadata = json.loads(json.dumps(result.metadata))
    metadata["output_paths"] = {
        **{s: str(output_dir / f"{s}.parquet") for s in SPLITS},
        "metadata": str(output_dir / "metadata.json"),
    }
    # A failure leaves no published partial set and cleans up its staging files.
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    try:
        for split in SPLITS:
            result.rows.loc[result.rows["split"].eq(split)].to_parquet(
                staging / f"{split}.parquet", index=False)
        (staging / "metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        staging.rename(output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return metadata
