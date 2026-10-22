"""Validation helpers shared by all TraceAdvisor adapters."""

from __future__ import annotations

import math
from typing import Mapping, Sequence

import pandas as pd

from src.canonical.schema import (
    CanonicalSchemaError,
    DatasetCapabilities,
    validate_canonical_frame,
)


class AdapterValidationError(ValueError):
    pass


def _validate_record_uniqueness(df: pd.DataFrame) -> None:
    if df.empty or "record_level" not in df.columns:
        return

    for record_level, group in df.groupby(
        "record_level",
        dropna=False,
    ):
        keys = None

        if record_level == "occurrence":
            keys = ["occurrence_id"]

        elif record_level == "interval":
            keys = ["instance_id", "event_time_us"]

        elif record_level == "instance":
            if "source_seq_no" in group.columns:
                keys = ["instance_id", "source_seq_no"]
            else:
                keys = ["instance_id"]

        elif record_level == "execution":
            if "start_time_us" in group.columns:
                keys = ["execution_id", "start_time_us"]
            else:
                keys = ["execution_id"]

        elif record_level == "role_occurrence":
            if "role_key" not in group.columns:
                raise AdapterValidationError(
                    "role_occurrence records require a role_key column"
                )

            if group["role_key"].isna().any():
                raise AdapterValidationError(
                    "role_key must not be null on role_occurrence records"
                )

            keys = ["role_key"]

        if not keys:
            continue

        if any(key not in group.columns for key in keys):
            continue

        eligible = group[keys].notna().all(axis=1)
        duplicated = group.loc[eligible].duplicated(
            subset=keys,
            keep=False,
        )

        if duplicated.any():
            examples = (
                group.loc[eligible]
                .loc[duplicated, keys]
                .head(5)
                .to_dict("records")
            )

            raise AdapterValidationError(
                f"Duplicate canonical {record_level} records "
                f"for key {keys}: {examples}"
            )


def _null_mask(df: pd.DataFrame, col: str) -> pd.Series:
    """True where ``col`` is null; an absent column counts as all null."""
    if col not in df.columns:
        return pd.Series(True, index=df.index)

    return df[col].isna()


def _validate_profile_identity(
    df: pd.DataFrame,
    capabilities: DatasetCapabilities,
) -> None:
    """Apply profile-driven role/instance identity checks."""
    levels = capabilities.supported_record_levels

    if not levels or "role_occurrence" not in levels:
        return

    instance_rows = df["record_level"] == "instance"

    if not instance_rows.any():
        return

    for col in ("role_key", "instance_id"):
        if (instance_rows & _null_mask(df, col)).any():
            raise AdapterValidationError(
                f"{col} must not be null on instance records "
                f"for {capabilities.dataset_id}"
            )


def _validate_recurrence_keys(
    df: pd.DataFrame,
    capabilities: DatasetCapabilities,
) -> None:
    """Validate recurrence-key presence against the dataset profile."""
    if capabilities.recurrence_key_origin == "none":
        if (
            "recurrence_key" in df.columns
            and df["recurrence_key"].notna().any()
        ):
            raise AdapterValidationError(
                "recurrence_key must be null when "
                "recurrence_key_origin is none"
            )

        return

    evaluation_rows = df["record_level"].isin(
        ["occurrence", "role_occurrence"]
    )

    if "exclusion_reason" in df.columns:
        excluded_no_key = (
            df["exclusion_reason"] == "no_recurrence_key"
        )
    else:
        excluded_no_key = pd.Series(
            False,
            index=df.index,
        )

    missing_key = (
        evaluation_rows
        & _null_mask(df, "recurrence_key")
        & ~excluded_no_key
    )

    if missing_key.any():
        raise AdapterValidationError(
            "recurrence_key may be null on occurrence and "
            "role_occurrence records only when exclusion_reason "
            "is no_recurrence_key"
        )


TARGET_BUILDER_COLUMNS = [
    "split",
    "actual_cpu",
    "actual_memory",
    "cpu_target_status",
    "memory_target_status",
]


def _reject_target_builder_columns(df: pd.DataFrame) -> None:
    """Adapters must not emit split or target-builder values."""
    populated = [
        column
        for column in TARGET_BUILDER_COLUMNS
        if column in df.columns
        and df[column].notna().any()
    ]

    if populated:
        raise AdapterValidationError(
            "Adapter output must not populate "
            f"target-builder columns: {populated}"
        )


def validate_adapter_output(
    df: pd.DataFrame,
    *,
    capabilities: DatasetCapabilities,
) -> None:
    if not isinstance(df, pd.DataFrame):
        raise AdapterValidationError(
            "adapter output must be a pandas DataFrame"
        )

    duplicate_columns = (
        df.columns[df.columns.duplicated()].tolist()
    )

    if duplicate_columns:
        raise AdapterValidationError(
            f"Duplicate canonical columns: {duplicate_columns}"
        )

    _validate_record_uniqueness(df)

    if not df.empty and "dataset_id" in df.columns:
        ids = set(
            df["dataset_id"]
            .dropna()
            .astype(str)
            .unique()
        )

        if ids != {capabilities.dataset_id}:
            raise AdapterValidationError(
                "Adapter output dataset_id must equal "
                f"{capabilities.dataset_id!r}; found {sorted(ids)!r}"
            )

    resource_prefixes = (
        "requested_",
        "allocated_",
        "observed_",
        "peak_",
        "actual_",
        "recommended_",
    )

    for col in df.columns:
        if (
            not col.startswith(resource_prefixes)
            or col.endswith("_unit")
        ):
            continue

        values = pd.to_numeric(
            df[col],
            errors="coerce",
        )
        supplied = df[col].notna()

        nonfinite = supplied & ~values.map(
            lambda x: (
                True
                if pd.isna(x)
                else math.isfinite(float(x))
            )
        )

        if nonfinite.any():
            raise AdapterValidationError(
                f"{col} contains non-finite values"
            )

    try:
        validate_canonical_frame(
            df,
            capabilities,
        )
    except CanonicalSchemaError as exc:
        raise AdapterValidationError(
            str(exc)
        ) from exc

    if df.empty:
        return

    _validate_profile_identity(
        df,
        capabilities,
    )
    _validate_recurrence_keys(
        df,
        capabilities,
    )
    _reject_target_builder_columns(df)


def validate_rejected_output(
    rejected: pd.DataFrame,
    *,
    required_columns: Mapping[str, Sequence[str]] | None = None,
) -> None:
    """Validate the shared rejected-record contract.

    Every non-empty rejected output must contain ``rejection_level`` and
    ``rejection_reason``. Adapters may require additional source/identity
    columns per rejection level.
    """
    if not isinstance(rejected, pd.DataFrame):
        raise AdapterValidationError(
            "rejected output must be a pandas DataFrame"
        )

    duplicate_columns = (
        rejected.columns[
            rejected.columns.duplicated()
        ]
        .tolist()
    )

    if duplicate_columns:
        raise AdapterValidationError(
            "Duplicate rejected-output columns: "
            f"{duplicate_columns}"
        )

    if rejected.empty:
        return

    for column in (
        "rejection_level",
        "rejection_reason",
    ):
        if column not in rejected.columns:
            raise AdapterValidationError(
                f"rejected output requires a {column} column"
            )

        if rejected[column].isna().any():
            raise AdapterValidationError(
                f"{column} must not be null"
            )

        blank = (
            rejected[column]
            .astype("string")
            .str.strip()
            .eq("")
        )

        if blank.any():
            raise AdapterValidationError(
                f"{column} must not be blank"
            )

    requirements = dict(
        required_columns or {}
    )

    for level, columns in requirements.items():
        rows = (
            rejected["rejection_level"]
            .astype(str)
            .eq(str(level))
        )

        if not rows.any():
            continue

        missing_columns = [
            column
            for column in columns
            if column not in rejected.columns
        ]

        if missing_columns:
            raise AdapterValidationError(
                "Rejected "
                f"{level!r} rows require columns: "
                f"{sorted(missing_columns)}"
            )


def _null_equal(
    left: pd.Series,
    right: pd.Series,
) -> pd.Series:
    """Return equality with null/null treated as equal."""
    return (
        left.eq(right)
        | (
            left.isna()
            & right.isna()
        )
    ).fillna(False)


def _sample_instance_ids(
    linked: pd.DataFrame,
    mask: pd.Series,
) -> list[str]:
    if "instance_id" not in linked.columns:
        return []

    return (
        linked.loc[
            mask,
            "instance_id",
        ]
        .dropna()
        .astype(str)
        .head(5)
        .tolist()
    )


def validate_role_instance_linkage(
    role_view: pd.DataFrame,
    instance_view: pd.DataFrame,
    *,
    capabilities: DatasetCapabilities,
) -> None:
    """Validate role/instance parent linkage without modifying identity.

    Orphan or mismatched rows are framework errors. They are not converted
    into rejected-output rows.
    """
    if not isinstance(role_view, pd.DataFrame):
        raise AdapterValidationError(
            "role_view must be a pandas DataFrame"
        )

    if not isinstance(instance_view, pd.DataFrame):
        raise AdapterValidationError(
            "instance_view must be a pandas DataFrame"
        )

    required_linkage_columns = {
        "role_key",
        "workload_id",
        "recurrence_key",
        "occurrence_id",
    }

    missing_role = sorted(
        required_linkage_columns
        - set(role_view.columns)
    )

    if missing_role:
        raise AdapterValidationError(
            "role view missing linkage columns: "
            f"{missing_role}"
        )

    missing_instance = sorted(
        required_linkage_columns
        - set(instance_view.columns)
    )

    if missing_instance:
        raise AdapterValidationError(
            "instance view missing linkage columns: "
            f"{missing_instance}"
        )

    if role_view["role_key"].isna().any():
        raise AdapterValidationError(
            "role view contains null role_key"
        )

    if role_view["role_key"].duplicated().any():
        raise AdapterValidationError(
            "role view contains duplicate role_key values"
        )

    parent_columns = [
        "role_key",
        "workload_id",
        "recurrence_key",
        "occurrence_id",
    ]

    check_event_time = (
        capabilities.instance_event_time_semantics
        == "parent_job_submission"
    )

    if check_event_time:
        if "start_time_us" not in role_view.columns:
            raise AdapterValidationError(
                "role view requires start_time_us when "
                "instance_event_time_semantics is "
                "'parent_job_submission'"
            )

        if "event_time_us" not in instance_view.columns:
            raise AdapterValidationError(
                "instance view requires event_time_us when "
                "instance_event_time_semantics is "
                "'parent_job_submission'"
            )

        parent_columns.append(
            "start_time_us"
        )

    parent_lookup = pd.DataFrame(
        role_view[
            parent_columns
        ]
    ).copy(deep=True)

    rename_columns = {
        "workload_id": "_parent_workload_id",
        "recurrence_key": "_parent_recurrence_key",
        "occurrence_id": "_parent_occurrence_id",
    }

    if check_event_time:
        rename_columns[
            "start_time_us"
        ] = "_parent_start_time_us"

    parent_lookup = parent_lookup.rename(
        columns=rename_columns
    )

    linked = (
        instance_view.copy(
            deep=True
        )
        .merge(
            parent_lookup,
            how="left",
            on="role_key",
            indicator="_parent_merge_status",
            validate="many_to_one",
            sort=False,
        )
    )

    missing_parent = (
        linked["role_key"].isna()
        | (
            linked["_parent_merge_status"]
            != "both"
        )
    )

    identity_mismatch = pd.Series(
        False,
        index=linked.index,
        dtype=bool,
    )

    field_pairs = [
        (
            "workload_id",
            "_parent_workload_id",
        ),
        (
            "recurrence_key",
            "_parent_recurrence_key",
        ),
        (
            "occurrence_id",
            "_parent_occurrence_id",
        ),
    ]

    for child_field, parent_field in field_pairs:
        same = _null_equal(
            linked[child_field],
            linked[parent_field],
        )

        identity_mismatch = (
            identity_mismatch
            | (
                ~missing_parent
                & ~same
            )
        )

    event_time_mismatch = pd.Series(
        False,
        index=linked.index,
        dtype=bool,
    )

    if check_event_time:
        event_time_present = (
            linked["event_time_us"]
            .notna()
        )

        same_event_time = _null_equal(
            linked["event_time_us"],
            linked["_parent_start_time_us"],
        )

        event_time_mismatch = (
            ~missing_parent
            & (
                ~event_time_present
                | ~same_event_time
            )
        )

    if (
        missing_parent.any()
        or identity_mismatch.any()
        or event_time_mismatch.any()
    ):
        details = []

        if missing_parent.any():
            details.append(
                "orphan_count="
                f"{int(missing_parent.sum())}, "
                "sample_instance_ids="
                f"{_sample_instance_ids(linked, missing_parent)}"
            )

        if identity_mismatch.any():
            details.append(
                "identity_mismatch_count="
                f"{int(identity_mismatch.sum())}, "
                "sample_instance_ids="
                f"{_sample_instance_ids(linked, identity_mismatch)}"
            )

        if event_time_mismatch.any():
            details.append(
                "event_time_mismatch_count="
                f"{int(event_time_mismatch.sum())}, "
                "sample_instance_ids="
                f"{_sample_instance_ids(linked, event_time_mismatch)}"
            )

        raise AdapterValidationError(
            "Role/instance linkage validation failed: "
            + "; ".join(details)
        )
