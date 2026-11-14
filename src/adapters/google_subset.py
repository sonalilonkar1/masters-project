"""Thin mapping of existing Google occurrence artifacts; no pipeline logic."""

from __future__ import annotations

import pandas as pd

from src.canonical.schema import GOOGLE_CAPABILITIES, SCHEMA_VERSION

from .base import BaseDatasetAdapter


class GoogleSubsetAdapter(BaseDatasetAdapter):
    """Map current occurrences through the shared single-view adapter path."""

    adapter_name = "google_subset"
    capabilities = GOOGLE_CAPABILITIES

    def to_canonical(self, source: pd.DataFrame) -> pd.DataFrame:
        canonical = pd.DataFrame(index=source.index)
        canonical["schema_version"] = SCHEMA_VERSION
        canonical["dataset_id"] = self.capabilities.dataset_id
        canonical["record_level"] = "occurrence"
        canonical["workload_id"] = source["recurrence_key"]
        canonical["occurrence_id"] = source["occurrence_key"]
        canonical["recurrence_key"] = source["recurrence_key"]
        canonical["time_basis"] = "trace_relative"
        canonical["start_time_us"] = source["execution_start_time_us"]
        canonical["end_time_us"] = source["occurrence_end_time_us"]
        canonical["duration_sec"] = (
            source["occurrence_runtime_us"].astype("Float64") / 1_000_000.0
        )
        canonical["requested_cpu"] = source["occurrence_requested_cpu_ncu"]
        canonical["requested_cpu_unit"] = "ncu"
        canonical["requested_memory"] = source[
            "occurrence_requested_memory_normalized"
        ]
        canonical["requested_memory_unit"] = "normalized"
        canonical["peak_cpu"] = source["occurrence_peak_cpu_ncu"]
        canonical["peak_cpu_unit"] = "ncu"
        canonical["peak_memory"] = source["occurrence_peak_memory_normalized"]
        canonical["peak_memory_unit"] = "normalized"
        canonical["validity_status"] = "valid"
        canonical["exclusion_reason"] = pd.NA
        return canonical


def attach_google_precomputed_targets(
    view: pd.DataFrame, occurrences: pd.DataFrame
) -> pd.DataFrame:
    """Join existing targets and source splits without recomputing either.

    Callers label each source file's rows with its split before concatenating
    them (``train``, ``validation``, ``test``). Pass a split-free source frame
    to ``adapt()`` and retain the labeled occurrences for this helper.
    The validated view's row order and index are preserved; neither input is
    modified. Source split labels must be non-null and one of the labels above.
    Missing matches are errors, whereas null target values remain
    null, including globally final occurrences and existing cross-split targets.
    """
    names = {
        "occurrence_key": "occurrence_id",
        "target_cpu_next_occurrence_peak_ncu": "actual_cpu",
        "target_memory_next_occurrence_peak_normalized": "actual_memory",
        "split": "split",
    }
    targets = occurrences[list(names)].rename(columns=names)
    if targets["split"].isna().any():
        raise ValueError("Source split labels must not be null")
    if not targets["split"].isin(["train", "validation", "test"]).all():
        raise ValueError(
            "Source split labels must be one of: train, validation, test"
        )
    attached_columns = {
        "actual_cpu", "actual_memory", "actual_cpu_unit", "actual_memory_unit",
        "split",
    }
    if attached_columns.intersection(view.columns):
        raise ValueError(
            "view must not already contain targets, target units or split"
        )
    for frame in (view, targets):
        if frame["occurrence_id"].isna().any():
            raise ValueError("occurrence_id must not be null when attaching targets")
    result = view.merge(
        targets, on="occurrence_id", how="left", sort=False,
        validate="one_to_one", indicator=True,
    )
    if not result["_merge"].eq("both").all():
        raise ValueError("Every view occurrence_id must match a source occurrence")
    result = result.drop(columns="_merge")
    result.index = view.index.copy()
    result["actual_cpu_unit"] = "ncu"
    result["actual_memory_unit"] = "normalized"
    return result
