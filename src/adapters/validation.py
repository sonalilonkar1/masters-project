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
