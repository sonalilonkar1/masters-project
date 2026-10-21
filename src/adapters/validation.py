"""Validation helpers shared by all TraceAdvisor adapters."""
from __future__ import annotations
import math
import pandas as pd
from src.canonical.schema import CanonicalSchemaError, DatasetCapabilities, validate_canonical_frame

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
            # 0.2.0: one row per role of one job, identified by role_key.
            # Unlike the levels above, a missing key column or a null key is
            # an error rather than a skip: a role row without role_key could
            # never be matched to its instance rows, and a duplicate would be
            # evaluated twice. Two roles of one job (same occurrence_id,
            # different role_key) are separate rows and pass.
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

        duplicated = group.loc[
            eligible
        ].duplicated(
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


def _validate_profile_identity(df: pd.DataFrame, capabilities: DatasetCapabilities) -> None:
    """Profile-driven identity checks (schema §5.4).

    Apply only to profiles that declare ``role_occurrence`` in
    ``supported_record_levels`` (today only Alibaba GPU 2020). Every instance
    row of such a dataset must name its parent role (``role_key``) and carry
    its own key (``instance_id``). Role rows are covered by the uniqueness
    check above.

    Other profiles are skipped, so Alibaba 2018 and Azure keep the 0.1.0
    behavior, where an instance row with a null ``instance_id`` is allowed.
    This function only reads keys already on the rows; it never builds them.
    """
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


def _validate_recurrence_keys(df: pd.DataFrame, capabilities: DatasetCapabilities) -> None:
    """Recurrence keys are never invented and never silently missing (framework §7.2).

    - ``recurrence_key_origin = none``: every ``recurrence_key`` must be null.
    - Any other origin: on evaluation rows (``occurrence`` and
      ``role_occurrence``), ``recurrence_key`` may be null only on rows
      excluded with ``exclusion_reason = no_recurrence_key`` (for example an
      Alibaba GPU 2020 job without a ``group``).

    Instance rows are not checked here. They copy their parent role's key,
    which may legitimately be null, and that match is checked by the Task 1
    linkage interface.
    """
    if capabilities.recurrence_key_origin == "none":
        if "recurrence_key" in df.columns and df["recurrence_key"].notna().any():
            raise AdapterValidationError(
                "recurrence_key must be null when recurrence_key_origin is none"
            )
        return

    evaluation_rows = df["record_level"].isin(["occurrence", "role_occurrence"])
    if "exclusion_reason" in df.columns:
        excluded_no_key = df["exclusion_reason"] == "no_recurrence_key"
    else:
        excluded_no_key = pd.Series(False, index=df.index)
    missing_key = evaluation_rows & _null_mask(df, "recurrence_key") & ~excluded_no_key
    if missing_key.any():
        raise AdapterValidationError(
            "recurrence_key may be null on occurrence and role_occurrence "
            "records only when exclusion_reason is no_recurrence_key"
        )


# Columns written only by the Task 4 target builder (schema §11).
TARGET_BUILDER_COLUMNS = [
    "split",
    "actual_cpu",
    "actual_memory",
    "cpu_target_status",
    "memory_target_status",
]


def _reject_target_builder_columns(df: pd.DataFrame) -> None:
    """Adapters must not emit splits or targets (framework §3, §7.2).

    Splits and next-occurrence targets are built by the shared target builder,
    which enforces split isolation. An adapter that emitted them could skip
    that rule. The Google contract view keeps its precomputed targets because
    it calls ``validate_canonical_frame`` directly, not this function.
    """
    populated = [c for c in TARGET_BUILDER_COLUMNS if c in df.columns and df[c].notna().any()]
    if populated:
        raise AdapterValidationError(
            f"Adapter output must not populate target-builder columns: {populated}"
        )

def validate_adapter_output(df: pd.DataFrame, *, capabilities: DatasetCapabilities) -> None:
    if not isinstance(df, pd.DataFrame):
        raise AdapterValidationError("adapter output must be a pandas DataFrame")

    duplicate_columns = df.columns[df.columns.duplicated()].tolist()
    if duplicate_columns:
        raise AdapterValidationError(f"Duplicate canonical columns: {duplicate_columns}")

    _validate_record_uniqueness(df)

    if not df.empty and "dataset_id" in df.columns:
        ids = set(df["dataset_id"].dropna().astype(str).unique())
        if ids != {capabilities.dataset_id}:
            raise AdapterValidationError(
                f"Adapter output dataset_id must equal {capabilities.dataset_id!r}; found {sorted(ids)!r}"
            )

    resource_prefixes = ("requested_","allocated_","observed_","peak_","actual_","recommended_")
    for col in df.columns:
        if not col.startswith(resource_prefixes) or col.endswith("_unit"):
            continue
        values = pd.to_numeric(df[col], errors="coerce")
        supplied = df[col].notna()
        nonfinite = supplied & ~values.map(lambda x: True if pd.isna(x) else math.isfinite(float(x)))
        if nonfinite.any():
            raise AdapterValidationError(f"{col} contains non-finite values")

    try:
        validate_canonical_frame(df, capabilities)
    except CanonicalSchemaError as exc:
        raise AdapterValidationError(str(exc)) from exc

    # 0.2.0 adapter-output checks. They run last, so every frame that broke a
    # 0.1.0 rule still fails with the same message as before (for example an
    # Alibaba 2018 recurrence_key still fails with "recurrence unsupported").
    if df.empty:
        return
    _validate_profile_identity(df, capabilities)
    _validate_recurrence_keys(df, capabilities)
    _reject_target_builder_columns(df)


def validate_rejected_output(
    rejected: pd.DataFrame,
) -> None:
    """
    Validate the minimal shared rejected-record contract.

    Rejected rows are intentionally not canonical rows and therefore do
    not pass through validate_canonical_frame().

    The framework requires only a primary rejection reason. Dataset
    adapters retain whatever identity and source-traceability fields are
    available from the source record.
    """
    if not isinstance(
        rejected,
        pd.DataFrame,
    ):
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
            f"Duplicate rejected-output columns: "
            f"{duplicate_columns}"
        )

    if rejected.empty:
        return

    if (
        "rejection_reason"
        not in rejected.columns
    ):
        raise AdapterValidationError(
            "rejected output requires a rejection_reason column"
        )

    if (
        rejected[
            "rejection_reason"
        ]
        .isna()
        .any()
    ):
        raise AdapterValidationError(
            "rejection_reason must not be null"
        )

    blank_reason = (
        rejected[
            "rejection_reason"
        ]
        .astype("string")
        .str.strip()
        .eq("")
    )

    if blank_reason.any():
        raise AdapterValidationError(
            "rejection_reason must not be blank"
        )


def _null_equal(
    left: pd.Series,
    right: pd.Series,
) -> pd.Series:
    """
    Equality where null/null is treated as equal.
    """
    return (
        left.eq(right)
        | (
            left.isna()
            & right.isna()
        )
    ).fillna(False)


def validate_role_instance_linkage(
    role_view: pd.DataFrame,
    instance_view: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Validate instance-to-role parent linkage.

    Returns:
        valid_instances, rejected_instances

    This function validates existing identity fields only. It does not
    construct, copy, infer, repair, or modify role/instance identity
    fields.

    Rejection reasons:
    - missing_parent_role
    - parent_identity_mismatch
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

    # Explicit column selection keeps Pandas/Pylance typing unambiguous.
    parent_lookup = pd.DataFrame(
        role_view[
            [
                "role_key",
                "workload_id",
                "recurrence_key",
                "occurrence_id",
            ]
        ]
    ).copy(deep=True)

    parent_lookup = parent_lookup.rename(
        columns={
            "workload_id": "_parent_workload_id",
            "recurrence_key": "_parent_recurrence_key",
            "occurrence_id": "_parent_occurrence_id",
        }
    )

    # Preserve the original row position so we can return the exact
    # original instance rows without depending on index labels.
    instance_working = instance_view.copy(
        deep=True
    )

    linked: pd.DataFrame = instance_working.merge(
        parent_lookup,
        how="left",
        on="role_key",
        indicator="_parent_merge_status",
        validate="many_to_one",
        sort=False,
    )

    missing_parent = (
        linked["role_key"].isna()
        | (
            linked["_parent_merge_status"]
            != "both"
        )
    )

    mismatch = pd.Series(
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

        mismatch = (
            mismatch
            | (
                ~missing_parent
                & ~same
            )
        )

    rejected_mask = (
        missing_parent
        | mismatch
    )

    valid_positions = [
        position
        for position, is_rejected in enumerate(
            rejected_mask.tolist()
        )
        if not bool(is_rejected)
    ]



    rejected_positions = [
        position
        for position, is_rejected in enumerate(
            rejected_mask.tolist()
        )
        if bool(is_rejected)
    ]

    valid_instances = pd.DataFrame(
        instance_view.iloc[
            valid_positions,
            :,
        ]
    ).copy(deep=True)

    rejected_instances = pd.DataFrame(
        instance_view.iloc[
            rejected_positions,
            :,
        ]
    ).copy(deep=True)

    rejection_reasons = [
        (
            "missing_parent_role"
            if bool(
                missing_parent.iloc[position]
            )
            else "parent_identity_mismatch"
        )
        for position in rejected_positions
    ]

    rejected_instances[
        "rejection_reason"
    ] = rejection_reasons

    return (
        valid_instances,
        rejected_instances,
    )