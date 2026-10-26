"""Alibaba GPU 2020 (cluster-trace-gpu-v2020) adapter.

Turns the six official source tables into two validated canonical views and
a rejected output (adapter_framework.md §9.2):
- ``role_occurrence``: evaluation rows, one per task role of one job;
- ``instance``: audit rows, one per instance-table row, so every retry is its
  own row;
- rejected output: jobs without a submission time, rejected whole.

The adapter needs all six tables, so it runs only through ``adapt_sources()``.

The module has two marked sections (docs/design/alibaba_gpu_2020_adapter_design.md):
- Part A: joins, identity, timestamps, parent inheritance, rejection routing.
- Part B: exclusion rules, validity, resource mappings, aggregation. Part B
  reads only Part A's prepared frames and never changes identity, time,
  join or routing columns.
"""

from __future__ import annotations

import dataclasses
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from src.canonical.schema import (
    ALIBABA_GPU_2020_CAPABILITIES,
    ALIBABA_GPU_2020_EXCLUSION_REASONS,
    SCHEMA_VERSION,
    DatasetCapabilities,
)
from .base import BaseDatasetAdapter
from .validation import (
    AdapterValidationError,
    validate_rejected_output,
    validate_role_instance_linkage,
)


# Literal separator for every composite key (schema §5.2).
SEPARATOR = "||"

SOURCE_ROW_NUMBER = "source_row_number"

# Source times are seconds relative to the trace start (schema §7).
TIME_BASIS = "trace_relative"
MICROSECONDS_PER_SECOND = 1_000_000

# A job without a submission time is rejected whole (schema §9.5, D-23).
REJECTION_REASON = "missing_submission_time"

# Source tables, by manifest name.
JOB_TABLE = "pai_job_table"
TASK_TABLE = "pai_task_table"
INSTANCE_TABLE = "pai_instance_table"
SENSOR_TABLE = "pai_sensor_table"
GROUP_TAG_TABLE = "pai_group_tag_table"
MACHINE_SPEC_TABLE = "pai_machine_spec"

# Columns read from each table (design §4.1). Anything else is dropped:
# sensor read/write/read_count/write_count, gpu_name, machine and inst_id;
# group-tag user; lookup-table source_row_number.
SOURCE_COLUMNS = {
    JOB_TABLE: ("job_name", "inst_id", "user", "status", "start_time", "end_time"),
    TASK_TABLE: (
        "job_name", "task_name", "inst_num", "status", "start_time", "end_time",
        "plan_cpu", "plan_mem", "plan_gpu", "gpu_type",
    ),
    INSTANCE_TABLE: (
        "job_name", "task_name", "inst_name", "worker_name", "inst_id",
        "status", "start_time", "end_time", "machine", SOURCE_ROW_NUMBER,
    ),
    SENSOR_TABLE: (
        "job_name", "task_name", "worker_name", "cpu_usage", "gpu_wrk_util",
        "avg_mem", "max_mem", "avg_gpu_wrk_mem", "max_gpu_wrk_mem",
    ),
    GROUP_TAG_TABLE: ("inst_id", "group", "workload", "gpu_type_spec"),
    MACHINE_SPEC_TABLE: ("machine", "gpu_type", "cap_cpu", "cap_mem", "cap_gpu"),
}

# Optional on job and task tables: kept under a prefixed name when present,
# so the plain name always means an instance-file line (design §4.1).
OPTIONAL_ROW_NUMBER_TABLES = (JOB_TABLE, TASK_TABLE)

# Explicit renames for names that collide inside one prepared frame.
JOB_RENAMES = {
    "inst_id": "job_inst_id",
    "status": "job_status",
    "start_time": "job_start_time",
    "end_time": "job_end_time",
    SOURCE_ROW_NUMBER: "job_source_row_number",
}
TASK_RENAMES = {
    "status": "task_status",
    "start_time": "task_start_time",
    "end_time": "task_end_time",
    SOURCE_ROW_NUMBER: "task_source_row_number",
}
GROUP_TAG_RENAMES = {"inst_id": "job_inst_id"}
MACHINE_SPEC_RENAMES = {"gpu_type": "machine_gpu_type"}

ROLE_KEY_COLUMNS = ["job_name", "task_name"]
INSTANCE_SLOT_COLUMNS = ["job_name", "task_name", "inst_name"]
PARENT_IDENTITY_COLUMNS = ["workload_id", "recurrence_key", "occurrence_id", "role_key"]

# Columns the linkage check reads (validate_role_instance_linkage); passing
# only these keeps its internal copies small on the full instance table.
LINKAGE_ROLE_COLUMNS = PARENT_IDENTITY_COLUMNS + ["start_time_us"]
LINKAGE_INSTANCE_COLUMNS = PARENT_IDENTITY_COLUMNS + ["event_time_us", "instance_id"]
SENSOR_KEY_COLUMNS = ["job_name", "task_name", "worker_name"]


def _select_source(
    sources: Mapping[str, pd.DataFrame],
    table: str,
) -> pd.DataFrame:
    frame = sources[table]
    columns = list(SOURCE_COLUMNS[table])
    if table in OPTIONAL_ROW_NUMBER_TABLES and SOURCE_ROW_NUMBER in frame.columns:
        columns.append(SOURCE_ROW_NUMBER)

    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise AdapterValidationError(f"{table} is missing columns: {missing}")

    return frame[columns].copy()


def _check_instance_row_numbers(instances: pd.DataFrame) -> None:
    row_numbers = instances[SOURCE_ROW_NUMBER]
    if not pd.api.types.is_integer_dtype(row_numbers):
        raise AdapterValidationError(
            f"{INSTANCE_TABLE}: {SOURCE_ROW_NUMBER} must be an integer column"
        )
    if row_numbers.isna().any():
        raise AdapterValidationError(
            f"{INSTANCE_TABLE}: {SOURCE_ROW_NUMBER} has null values"
        )
    if row_numbers.duplicated().any():
        raise AdapterValidationError(
            f"{INSTANCE_TABLE}: {SOURCE_ROW_NUMBER} has duplicate values"
        )


def _check_lookup_keys(
    lookup: pd.DataFrame,
    keys: Sequence[str],
    name: str,
) -> None:
    keys = list(keys)
    null_keys = int(lookup[keys].isna().any(axis=1).sum())
    if null_keys:
        raise AdapterValidationError(
            f"{name}: {null_keys} rows have a null lookup key {keys}"
        )
    duplicate_keys = int(lookup.duplicated(keys).sum())
    if duplicate_keys:
        raise AdapterValidationError(
            f"{name}: {duplicate_keys} duplicate lookup keys {keys}"
        )


def _left_join(
    driving: pd.DataFrame,
    lookup: pd.DataFrame,
    keys: Sequence[str],
    flag: str,
    name: str,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Unique-key left join with a match flag and two-way coverage counts.

    Lookup keys are checked unique and non-null first. pandas would match a
    null key to a null key, so with no null on the lookup side a driving row
    with a null key part can never match.
    """
    keys = list(keys)
    _check_lookup_keys(lookup, keys, name)

    overlap = (set(driving.columns) & set(lookup.columns)) - set(keys)
    if flag in driving.columns or flag in lookup.columns:
        overlap.add(flag)
    if overlap:
        raise AdapterValidationError(
            f"{name}: column names would collide: {sorted(overlap)}"
        )

    merged = driving.merge(
        lookup,
        on=keys,
        how="left",
        validate="many_to_one",
        indicator="_join_indicator",
    )
    if len(merged) != len(driving):
        raise AdapterValidationError(
            f"{name}: join changed the row count "
            f"({len(driving)} -> {len(merged)})"
        )
    merged.index = driving.index
    merged[flag] = merged.pop("_join_indicator").eq("both").astype(bool)

    matched = merged[flag]
    lookup_used = len(merged.loc[matched, keys].drop_duplicates())
    counts = {
        "driving_matched": int(matched.sum()),
        "driving_unmatched": int((~matched).sum()),
        "driving_null_key": int(driving[keys].isna().any(axis=1).sum()),
        "lookup_used": lookup_used,
        "lookup_unused": len(lookup) - lookup_used,
    }
    return merged, counts


def _as_string(values: pd.Series) -> pd.Series:
    if isinstance(values.dtype, pd.StringDtype):
        return values
    return values.astype("string")


def _is_blank(values: pd.Series) -> pd.Series:
    """True where a value is null, empty or whitespace-only."""
    stripped = _as_string(values).str.strip()
    return (values.isna() | stripped.eq("").fillna(False)).astype(bool)


def _group_is_missing(frame: pd.DataFrame) -> pd.Series:
    """Missing `group`: null, empty or whitespace-only.

    Shared by role identity (A2) and exclusion rule 1, no_recurrence_key (B1).
    """
    return _is_blank(frame["group"])


def _check_key_parts(
    frame: pd.DataFrame,
    name: str,
    required: Sequence[str],
    separated: Sequence[str],
) -> None:
    """Raise if a required key part is blank, or if a key part contains
    the separator (which would let two different keys collide)."""
    for column in required:
        blank = int(_is_blank(frame[column]).sum())
        if blank:
            raise AdapterValidationError(
                f"{name}: {blank} rows have a blank {column}"
            )
    for column in separated:
        contains = int(
            _as_string(frame[column]).str.contains(SEPARATOR, regex=False)
            .fillna(False).sum()
        )
        if contains:
            raise AdapterValidationError(
                f"{name}: {contains} {column} values contain the key "
                f"separator {SEPARATOR!r}"
            )


def _add_role_identity(roles: pd.DataFrame) -> pd.DataFrame:
    """Add workload_id, recurrence_key, occurrence_id and role_key
    (schema §5.3, D-04, D-05; design step A2).

    A job without a group uses the fallback keys and a null recurrence_key.
    A missing group is never concatenated into a key, and a present group is
    used unchanged.
    """
    _check_key_parts(
        roles, "roles", ROLE_KEY_COLUMNS, ["group", *ROLE_KEY_COLUMNS]
    )

    missing = _group_is_missing(roles)
    group = _as_string(roles["group"])
    job = _as_string(roles["job_name"])
    task = _as_string(roles["task_name"])

    roles = roles.assign(
        workload_id=group.where(~missing, job),
        recurrence_key=(group + SEPARATOR + task).where(~missing, pd.NA),
        occurrence_id=(group + SEPARATOR + job).where(~missing, job),
        role_key=(group + SEPARATOR + job + SEPARATOR + task).where(
            ~missing, job + SEPARATOR + task
        ),
    )

    duplicates = int(roles["role_key"].duplicated().sum())
    if duplicates:
        raise AdapterValidationError(
            f"roles: {duplicates} duplicate role_key values"
        )
    return roles


def _add_instance_identity(instances: pd.DataFrame) -> pd.DataFrame:
    """Add the slot key, attempt index, instance_id, execution_id, worker_id
    and the raw source_ columns (schema §5.4, D-21; design step A3).

    Attempts within a slot are ordered by the instance's own start time
    ascending, nulls last, then source_row_number. worker_name, timestamps,
    the source inst_id and source_row_number are never part of the key.
    """
    _check_key_parts(
        instances, "instances", INSTANCE_SLOT_COLUMNS, INSTANCE_SLOT_COLUMNS
    )

    job = _as_string(instances["job_name"])
    task = _as_string(instances["task_name"])
    inst = _as_string(instances["inst_name"])
    slot = job + SEPARATOR + task + SEPARATOR + inst

    # Sort by position, not by index label, so duplicate input index labels
    # cannot mix rows up; then write each index back to its original row.
    order = pd.DataFrame(
        {
            "slot": slot.to_numpy(),
            "start": pd.to_numeric(instances["start_time"]).to_numpy(),
            "row": instances[SOURCE_ROW_NUMBER].to_numpy(),
            "position": np.arange(len(instances)),
        }
    ).sort_values(
        ["slot", "start", "row"], na_position="last", kind="mergesort"
    )
    attempt = np.empty(len(instances), dtype="int64")
    attempt[order["position"].to_numpy()] = (
        order.groupby("slot", sort=False).cumcount().to_numpy() + 1
    )
    attempt_index = pd.Series(attempt, index=instances.index)

    worker = _as_string(instances["worker_name"])
    instances = instances.assign(
        instance_slot_key=slot,
        instance_attempt_index=attempt_index,
        instance_id=slot + SEPARATOR + attempt_index.astype("string"),
        execution_id=job + SEPARATOR + task,
        worker_id=worker.where(~_is_blank(worker), pd.NA),
        source_inst_name=instances["inst_name"],
        source_worker_name=instances["worker_name"],
        source_status=instances["status"],
        source_machine=instances["machine"],
    )

    duplicates = int(instances["instance_id"].duplicated().sum())
    if duplicates:
        raise AdapterValidationError(
            f"instances: {duplicates} duplicate instance_id values"
        )
    return instances


def _inherit_parent_identity(
    instances: pd.DataFrame,
    roles: pd.DataFrame,
) -> pd.DataFrame:
    """Copy workload_id, recurrence_key, occurrence_id and role_key from the
    parent role row (schema §5.5, D-08; design step A4).

    Values are copied, never recomputed. An instance without a parent role
    keeps them null; the A7 linkage check reports it.
    """
    existing = [c for c in PARENT_IDENTITY_COLUMNS if c in instances.columns]
    if existing:
        raise AdapterValidationError(
            f"instances: parent identity columns already present: {existing}"
        )

    # Merge on a positional copy of the keys, so duplicate index labels
    # cannot mix rows up; a left merge keeps the left row order.
    parents = instances[ROLE_KEY_COLUMNS].reset_index(drop=True).merge(
        roles[ROLE_KEY_COLUMNS + PARENT_IDENTITY_COLUMNS],
        on=ROLE_KEY_COLUMNS,
        how="left",
        validate="many_to_one",
    )
    if len(parents) != len(instances):
        raise AdapterValidationError(
            "instances: parent inheritance changed the row count"
        )

    # A grouped role_key is workload_id||execution_id; a fallback role_key
    # is execution_id itself. Anything else means a wrong join.
    role_key = parents["role_key"]
    execution_id = pd.Series(instances["execution_id"].array)
    matched = role_key.notna()
    consistent = (role_key == execution_id) | (
        role_key == _as_string(parents["workload_id"]) + SEPARATOR + execution_id
    )
    inconsistent = int((matched & ~consistent.fillna(False)).sum())
    if inconsistent:
        raise AdapterValidationError(
            f"instances: {inconsistent} inherited role_key values do not "
            "match the instance execution_id"
        )

    return instances.assign(
        **{column: parents[column].array for column in PARENT_IDENTITY_COLUMNS}
    )


def _seconds_to_us(values: pd.Series, name: str) -> pd.Series:
    """Exact seconds x 1,000,000 as nullable Int64. Nulls stay null; a value
    that is not a whole number of microseconds raises instead of rounding."""
    microseconds = pd.to_numeric(values) * MICROSECONDS_PER_SECOND
    fractional = microseconds.notna() & (microseconds != microseconds.round())
    if fractional.any():
        raise AdapterValidationError(
            f"{name}: {int(fractional.sum())} values are not a whole number "
            "of microseconds"
        )
    return microseconds.astype("Int64")


def _add_timestamps(
    jobs: pd.DataFrame,
    roles: pd.DataFrame,
    instances: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add canonical microsecond timestamps (schema §7, D-22; design step A5).

    Roles: start = job submission, end = job completion, launch = task start.
    Instances: event = parent job submission, start/end = own times. A null
    source time stays null; nothing is inferred, filled or corrected.
    """
    for name, frame, columns in (
        ("roles", roles, ["start_time_us", "end_time_us", "launch_time_us", "time_basis"]),
        ("instances", instances, ["event_time_us", "start_time_us", "end_time_us", "time_basis"]),
    ):
        existing = [column for column in columns if column in frame.columns]
        if existing:
            raise AdapterValidationError(
                f"{name}: timestamp columns already present: {existing}"
            )

    roles = roles.assign(
        start_time_us=_seconds_to_us(roles["job_start_time"], "job start_time").array,
        end_time_us=_seconds_to_us(roles["job_end_time"], "job end_time").array,
        launch_time_us=_seconds_to_us(roles["task_start_time"], "task start_time").array,
        time_basis=TIME_BASIS,
    )

    # The parent job's submission, looked up by position so duplicate index
    # labels cannot mix rows up. Null when the job has no submission time.
    submission = instances[["job_name"]].reset_index(drop=True).merge(
        jobs[["job_name", "job_start_time"]],
        on="job_name",
        how="left",
        validate="many_to_one",
    )
    if len(submission) != len(instances):
        raise AdapterValidationError(
            "instances: event time lookup changed the row count"
        )

    instances = instances.assign(
        event_time_us=_seconds_to_us(
            submission["job_start_time"], "job start_time"
        ).array,
        start_time_us=_seconds_to_us(instances["start_time"], "instance start_time").array,
        end_time_us=_seconds_to_us(instances["end_time"], "instance end_time").array,
        time_basis=TIME_BASIS,
    )
    return roles, instances


def _job_rejection_flags(
    frame: pd.DataFrame,
    jobs: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    """Look up each row's job is_rejected flag by job_name, by position.

    Returns the flags (False when the job is missing) and whether the job
    was found.
    """
    lookup = frame[["job_name"]].reset_index(drop=True).merge(
        jobs[["job_name", "is_rejected"]],
        on="job_name",
        how="left",
        validate="many_to_one",
        indicator="_job_found",
    )
    if len(lookup) != len(frame):
        raise AdapterValidationError("rejection lookup changed the row count")
    found = lookup["_job_found"].eq("both").to_numpy()
    flags = lookup["is_rejected"].eq(True).to_numpy()
    return flags, found


def _route_rejections(
    jobs: pd.DataFrame,
    roles: pd.DataFrame,
    instances: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Flag every row of a job without a submission time as rejected
    (schema §9.5, D-23; design step A6).

    The whole job is rejected: its job row, all role rows and all instance
    rows, including instances that have their own start time. Rows stay in
    their frames; view assembly uses only the rows that are not rejected.
    """
    for name, frame in (("jobs", jobs), ("roles", roles), ("instances", instances)):
        if "is_rejected" in frame.columns:
            raise AdapterValidationError(f"{name}: is_rejected already present")

    jobs = jobs.assign(is_rejected=jobs["job_start_time"].isna().to_numpy())

    role_flags, _ = _job_rejection_flags(roles, jobs)
    if (role_flags != roles["start_time_us"].isna().to_numpy()).any():
        raise AdapterValidationError(
            "roles: is_rejected does not match a null start_time_us"
        )

    # An instance whose job is missing is not rejected; A7 reports it.
    instance_flags, found = _job_rejection_flags(instances, jobs)
    if (found & (instance_flags != instances["event_time_us"].isna().to_numpy())).any():
        raise AdapterValidationError(
            "instances: is_rejected does not match a null event_time_us"
        )

    return (
        jobs,
        roles.assign(is_rejected=role_flags),
        instances.assign(is_rejected=instance_flags),
    )


def _build_rejected(
    jobs: pd.DataFrame,
    roles: pd.DataFrame,
    instances: pd.DataFrame,
) -> pd.DataFrame:
    """Combine the rejected job, role and instance rows into one rejected
    output with rejection_level and rejection_reason (schema §9.5).

    Columns are the union of the three frames. A column a level does not
    have stays null; nothing is zero-filled.
    """
    parts = [
        frame.loc[frame["is_rejected"].to_numpy()].assign(
            rejection_level=level,
            rejection_reason=REJECTION_REASON,
        )
        for level, frame in (
            ("job", jobs),
            ("role_occurrence", roles),
            ("instance", instances),
        )
    ]
    parts = [part for part in parts if not part.empty]
    if not parts:
        return pd.DataFrame(columns=["rejection_level", "rejection_reason"])

    rejected = pd.concat(parts, ignore_index=True, sort=False)
    leading = ["rejection_level", "rejection_reason"]
    return rejected[leading + [c for c in rejected.columns if c not in leading]]


# ----------------------------------------------------------------------
# Part B: exclusions, validity, resource mappings, aggregation
#
# Part A built the rows (who each role and instance is, when it ran, how
# they link). Part B decides which roles can be evaluated and what their
# resource values are. It only adds columns; Part A columns never change.
#
# B1, exclusion rules: every accepted role is checked against 14 rules in a
# fixed order and gets the name of the first rule it breaks. A role that
# breaks no rule is eligible (null reason).
# ----------------------------------------------------------------------


def _equals(values: pd.Series, text: str) -> np.ndarray:
    """True where a text value equals ``text``; null is never equal."""
    return _as_string(values).eq(text).fillna(False).to_numpy(dtype=bool)


def _compare(left: pd.Series, op: str, right) -> np.ndarray:
    """Numeric comparison where a null on either side is not failed."""
    result = getattr(pd.to_numeric(left), op)(right)
    return result.fillna(False).to_numpy(dtype=bool)


def _role_instance_flags(
    roles: pd.DataFrame, instances: pd.DataFrame
) -> pd.DataFrame:
    """Check every instance, then sum the answers up per role.

    1. Each instance row gets yes/no answers: failed? interrupted? not
       finished? no worker name? same worker twice in the role? has a
       sensor row? peak memory above the machine's memory? bad memory
       values?
    2. The answers are grouped by role_key: "any instance" uses max (True
       counts as 1) and "every instance has a sensor row" uses min.
    3. The result is lined up with the roles frame row by row. A role with
       no instances gets False everywhere, so it is missing_sensor, never
       partial_sensor_coverage.
    """
    status = instances["status"]
    terminated = _equals(status, "Terminated")
    failed = _equals(status, "Failed")
    interrupted = _equals(status, "Interrupted")
    worker_id = instances["worker_id"]
    max_mem, avg_mem = instances["max_mem"], instances["avg_mem"]

    flags = pd.DataFrame(
        {
            "role_key": instances["role_key"].to_numpy(),
            "instance_failed": failed,
            "instance_interrupted": interrupted,
            # A null status is "not Terminated".
            "instance_incomplete": ~terminated & ~failed & ~interrupted,
            "missing_worker_name": _is_blank(instances["worker_name"]).to_numpy(),
            # The same worker name on two rows of one role (null ignored).
            "multi_attempt_worker": (
                worker_id.notna().to_numpy()
                & pd.DataFrame(
                    {"role": instances["role_key"].to_numpy(),
                     "worker": worker_id.to_numpy()}
                ).duplicated(keep=False).to_numpy()
            ),
            "has_sensor": instances["has_sensor"].to_numpy(dtype=bool),
            # Not failed when cap_mem is null (decision: rule 13 without
            # host capacity).
            "invalid_memory_exceeds_capacity": _compare(
                max_mem, "gt", pd.to_numeric(instances["cap_mem"])
            ),
            # Memory only: plan_mem is rule 5, GPU memory is descriptive.
            "invalid_resource": (
                _compare(max_mem, "lt", pd.to_numeric(avg_mem))
                | _compare(avg_mem, "lt", 0)
                | _compare(max_mem, "lt", 0)
            ),
        }
    )
    grouped = flags.groupby("role_key", sort=False)
    per_role = grouped.max().rename(columns={"has_sensor": "has_sensor_any"})
    per_role["has_sensor_all"] = grouped["has_sensor"].min()
    return per_role.reindex(roles["role_key"].to_numpy(), fill_value=False)


def _failed_rules(
    roles: pd.DataFrame, instances: pd.DataFrame
) -> dict[str, np.ndarray]:
    """Which of the 14 rules each role breaks: one yes/no array per rule.

    A role can break several rules; _assign_exclusion_reasons keeps only the
    first. The full results also give the B6 eligibility figures.
    """
    # Rules 6-14 need the role's instances; rules 1-5 need only the role.
    per_role = _role_instance_flags(roles, instances)
    job_status, task_status = roles["job_status"], roles["task_status"]
    failed_rules = {
        "no_recurrence_key": roles["recurrence_key"].isna().to_numpy(),
        "job_failed": _equals(job_status, "Failed"),
        # A null status is "not Terminated".
        "job_incomplete": (
            ~_equals(job_status, "Terminated")
            | roles["end_time_us"].isna().to_numpy()
        ),
        "task_not_terminated": ~_equals(task_status, "Terminated"),
        "missing_or_invalid_request": (
            ~_compare(roles["plan_cpu"], "gt", 0)
            | ~_compare(roles["plan_mem"], "gt", 0)
        ),
        "missing_sensor": ~per_role["has_sensor_any"].to_numpy(dtype=bool),
        "partial_sensor_coverage": (
            per_role["has_sensor_any"].to_numpy(dtype=bool)
            & ~per_role["has_sensor_all"].to_numpy(dtype=bool)
        ),
    }
    for rule in (
        "instance_failed", "instance_interrupted", "instance_incomplete",
        "missing_worker_name", "multi_attempt_worker",
        "invalid_memory_exceeds_capacity", "invalid_resource",
    ):
        failed_rules[rule] = per_role[rule].to_numpy(dtype=bool)
    if set(failed_rules) != set(ALIBABA_GPU_2020_EXCLUSION_REASONS):
        raise AdapterValidationError("exclusion rules do not match the schema")
    return failed_rules


def _assign_exclusion_reasons(
    roles: pd.DataFrame,
    instances: pd.DataFrame,
    failed_rules: Mapping[str, np.ndarray] | None = None,
) -> pd.DataFrame:
    """Decide whether each accepted role can be evaluated (schema §9.3; B1).

    Rules are checked in a fixed order (1–14, from the schema) and a role
    gets the name of the first rule it breaks. Roles that break no rule get
    null: they are eligible. Rejected roles are skipped (they go to the
    rejected output). Instances are never changed (schema §9.4).
    ``failed_rules`` may be passed in when the caller already has them.
    """
    if "exclusion_reason" in roles.columns:
        raise AdapterValidationError("roles: exclusion_reason already present")
    if failed_rules is None:
        failed_rules = _failed_rules(roles, instances)

    # Walk the rules in order. A role that already has a reason is skipped,
    # so each role keeps only its first broken rule.
    reason = np.full(len(roles), None, dtype=object)
    open_rows = ~roles["is_rejected"].to_numpy(dtype=bool)
    for rule in ALIBABA_GPU_2020_EXCLUSION_REASONS:
        hit = open_rows & failed_rules[rule]
        reason[hit] = rule
        open_rows &= ~hit
    return roles.assign(exclusion_reason=pd.array(reason, dtype="string"))


# B3, resource mappings (schema §6.2): canonical field -> (source column,
# unit). Values are copied as they are; nothing is filled, clipped or summed.
ROLE_RESOURCE_MAP = {
    "requested_cpu": ("plan_cpu", "percent_of_vcpu"),
    "requested_memory": ("plan_mem", "gb"),
    "requested_gpu": ("plan_gpu", "percent_of_gpu"),  # descriptive only
}
INSTANCE_RESOURCE_MAP = {
    "observed_cpu": ("cpu_usage", "percent_of_vcpu"),  # lifetime average
    "observed_memory": ("avg_mem", "gb"),
    "peak_memory": ("max_mem", "gb"),  # the primary evaluated value
    "observed_gpu": ("gpu_wrk_util", "percent_of_gpu"),  # descriptive only
    "peak_gpu_memory": ("max_gpu_wrk_mem", "gb"),  # descriptive only
}


def _copy_resources(
    frame: pd.DataFrame, mapping: Mapping[str, tuple[str, str]], name: str
) -> pd.DataFrame:
    """Copy each source column into its canonical field and add its unit.

    The unit is the same on every row: it describes the column's scale.
    """
    targets = [*mapping, *(f"{field}_unit" for field in mapping)]
    existing = [column for column in targets if column in frame.columns]
    if existing:
        raise AdapterValidationError(
            f"{name}: resource columns already present: {existing}"
        )
    columns = {}
    for field, (source, unit) in mapping.items():
        columns[field] = frame[source].to_numpy(copy=True)
        columns[f"{field}_unit"] = pd.array([unit] * len(frame), dtype="string")
    return frame.assign(**columns)


def _map_resources(
    roles: pd.DataFrame, instances: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Give roles their requests and instances their own usage (design step B3).

    Roles get requested_cpu / memory / gpu from the task request. Instances
    get each worker's own sensor values; an instance without a sensor row
    stays null. Role usage values are built from these in B4. peak_cpu is
    always null because the source has no CPU peak. Every row is mapped,
    accepted or rejected; source columns are kept.
    """
    roles = _copy_resources(roles, ROLE_RESOURCE_MAP, "roles")
    instances = _copy_resources(instances, INSTANCE_RESOURCE_MAP, "instances")
    if "peak_cpu" in instances.columns:
        raise AdapterValidationError("instances: peak_cpu already present")
    instances = instances.assign(
        peak_cpu=np.full(len(instances), np.nan),
        peak_cpu_unit=pd.array([pd.NA] * len(instances), dtype="string"),
    )
    return roles, instances


# B4, role aggregation and scope (schema §8).
ROLE_SCOPE = {
    "resource_scope": "task_role_per_instance",
    "request_aggregation_method": "none",
    "observed_aggregation_method": "maximum_over_instances",
}
INSTANCE_SCOPE = {
    "resource_scope": "instance",
    "request_aggregation_method": "none",
    "observed_aggregation_method": "none",
}


def _aggregate_role_resources(
    roles: pd.DataFrame, instances: pd.DataFrame
) -> pd.DataFrame:
    """Give each role one usage value per resource (design step B4).

    1. Keep the instances that have a sensor row.
    2. Per role, take the largest value of each field. If any of those
       instances lacks the value, the role value is null: a maximum over
       only some workers could understate the role. Values are never summed.
    3. Line the result up with the roles. A role with no sensor-covered
       instance gets null everywhere.

    Every role is aggregated, eligible, excluded or rejected. Retries carry
    their worker's single sensor row, so they cannot change the maximum.
    """
    fields = list(INSTANCE_RESOURCE_MAP)
    targets = [*fields, *(f"{field}_unit" for field in fields), "peak_cpu", "peak_cpu_unit"]
    existing = [column for column in targets if column in roles.columns]
    if existing:
        raise AdapterValidationError(
            f"roles: resource columns already present: {existing}"
        )

    covered = instances.loc[instances["has_sensor"].to_numpy(dtype=bool)]
    keys = covered["role_key"].to_numpy()
    maxima = covered[fields].groupby(keys, sort=False).max()
    any_missing = covered[fields].isna().groupby(keys, sort=False).any()
    aligned = maxima.mask(any_missing).reindex(roles["role_key"].to_numpy())

    columns = {}
    for field, (_, unit) in INSTANCE_RESOURCE_MAP.items():
        columns[field] = aligned[field].to_numpy(dtype=float)
        columns[f"{field}_unit"] = pd.array([unit] * len(roles), dtype="string")
    columns["peak_cpu"] = np.full(len(roles), np.nan)
    columns["peak_cpu_unit"] = pd.array([pd.NA] * len(roles), dtype="string")
    return roles.assign(**columns)


def _add_resource_scope(
    roles: pd.DataFrame, instances: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Say what each resource value covers: constants per frame (schema §8).

    Set on every row, also where a value is null, because the scope
    describes the row's level, not one value.
    """
    for name, frame in (("roles", roles), ("instances", instances)):
        existing = [column for column in ROLE_SCOPE if column in frame.columns]
        if existing:
            raise AdapterValidationError(
                f"{name}: scope columns already present: {existing}"
            )
    return tuple(
        frame.assign(**{
            column: pd.array([value] * len(frame), dtype="string")
            for column, value in scope.items()
        })
        for frame, scope in ((roles, ROLE_SCOPE), (instances, INSTANCE_SCOPE))
    )


# B2, validity (schema §9.1). Built after B3 and B4: it reads their values.
VALIDITY_COLUMNS = ("cpu_validity_status", "memory_validity_status", "validity_status")


def _status(invalid: np.ndarray, partial: np.ndarray) -> np.ndarray:
    """invalid wins over partial; anything else is valid."""
    return np.where(invalid, "invalid", np.where(partial, "partial", "valid"))


def _row_status(frame: pd.DataFrame, cpu: np.ndarray, memory: np.ndarray) -> np.ndarray:
    """Row validity_status from the per-resource statuses (schema §9.1).

    invalid if any resource is invalid; partial if no resource is
    populated; valid if every populated resource is valid; else partial.
    Populated means the canonical value exists. peak_cpu is never used: it
    is null by capability, not missing.
    """
    cpu_populated = frame["observed_cpu"].notna().to_numpy()
    memory_populated = (
        frame["observed_memory"].notna() | frame["peak_memory"].notna()
    ).to_numpy()
    invalid = (cpu == "invalid") | (memory == "invalid")
    none_populated = ~cpu_populated & ~memory_populated
    all_valid = (~cpu_populated | (cpu == "valid")) & (
        ~memory_populated | (memory == "valid")
    )
    return np.where(
        invalid, "invalid",
        np.where(none_populated, "partial", np.where(all_valid, "valid", "partial")),
    )


def _instance_validity(instances: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Stage 1: CPU and memory status from each worker's own values.

    Memory is invalid on the conditions of rules 13 and 14; CPU only when
    negative. A missing sensor row or value is partial. Null comparisons
    (for example a null cap_mem) are never invalid.
    """
    no_sensor = ~instances["has_sensor"].to_numpy(dtype=bool)
    cpu_value = instances["observed_cpu"]
    average, peak = instances["observed_memory"], instances["peak_memory"]

    cpu = _status(
        invalid=_compare(cpu_value, "lt", 0),
        partial=no_sensor | cpu_value.isna().to_numpy(),
    )
    memory = _status(
        invalid=(
            _compare(peak, "gt", pd.to_numeric(instances["cap_mem"]))
            | _compare(peak, "lt", pd.to_numeric(average))
            | _compare(average, "lt", 0)
            | _compare(peak, "lt", 0)
        ),
        partial=no_sensor | average.isna().to_numpy() | peak.isna().to_numpy(),
    )
    return cpu, memory


def _role_validity(
    roles: pd.DataFrame, instances: pd.DataFrame, cpu: np.ndarray, memory: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Stage 2: roll each resource status up from the role's instances.

    invalid if any instance is invalid; else partial if any is partial or
    the role has no instances; else valid.
    """
    flags = pd.DataFrame(
        {
            "cpu_invalid": cpu == "invalid", "cpu_partial": cpu == "partial",
            "memory_invalid": memory == "invalid", "memory_partial": memory == "partial",
            "has_instance": True,
        }
    )
    per_role = (
        flags.groupby(instances["role_key"].to_numpy(), sort=False).max()
        .reindex(roles["role_key"].to_numpy(), fill_value=False)
    )
    no_instance = ~per_role["has_instance"].to_numpy(dtype=bool)
    return tuple(
        _status(
            invalid=per_role[f"{name}_invalid"].to_numpy(dtype=bool),
            partial=per_role[f"{name}_partial"].to_numpy(dtype=bool) | no_instance,
        )
        for name in ("cpu", "memory")
    )


def _assign_validity(
    roles: pd.DataFrame, instances: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Record the data quality of every role and instance (design step B2).

    Validity is data quality only: it never reads exclusion_reason, so an
    excluded role can be valid. Requests and GPU values are not judged.
    Instances use their own values; roles roll their instances up, and each
    frame's row status uses its own canonical values.
    """
    for name, frame in (("roles", roles), ("instances", instances)):
        existing = [column for column in VALIDITY_COLUMNS if column in frame.columns]
        if existing:
            raise AdapterValidationError(
                f"{name}: validity columns already present: {existing}"
            )

    instance_cpu, instance_memory = _instance_validity(instances)
    role_cpu, role_memory = _role_validity(roles, instances, instance_cpu, instance_memory)

    def with_status(frame, cpu, memory):
        values = (cpu, memory, _row_status(frame, cpu, memory))
        return frame.assign(**{
            column: pd.array(value, dtype="string")
            for column, value in zip(VALIDITY_COLUMNS, values)
        })

    return (
        with_status(roles, role_cpu, role_memory),
        with_status(instances, instance_cpu, instance_memory),
    )


# B5, view assembly: the contract columns of each view, in order
# (docs/design/alibaba_gpu_2020_output_contract.md §4.1, §5).
CORE_COLUMNS = ["schema_version", "dataset_id", "record_level", "time_basis"]
USAGE_COLUMNS = [
    column
    for field in [*INSTANCE_RESOURCE_MAP, "peak_cpu"]
    for column in (field, f"{field}_unit")
]
REQUEST_COLUMNS = [
    column for field in ROLE_RESOURCE_MAP for column in (field, f"{field}_unit")
]
QUALITY_COLUMNS = [*VALIDITY_COLUMNS, "exclusion_reason"]
ROLE_VIEW_COLUMNS = [
    *CORE_COLUMNS,
    *PARENT_IDENTITY_COLUMNS, "execution_id", "instance_id",
    "start_time_us", "end_time_us",
    *REQUEST_COLUMNS, *USAGE_COLUMNS, *ROLE_SCOPE, *QUALITY_COLUMNS,
    "job_name", "task_name", "inst_num", "gpu_type", "gpu_type_spec",
    "workload", "launch_time_us", "source_job_status", "source_task_status",
]
INSTANCE_VIEW_COLUMNS = [
    *CORE_COLUMNS,
    "instance_id", "instance_slot_key", "instance_attempt_index",
    "execution_id", "worker_id",
    *PARENT_IDENTITY_COLUMNS,
    "event_time_us", "start_time_us", "end_time_us",
    *USAGE_COLUMNS, *INSTANCE_SCOPE, *QUALITY_COLUMNS,
    SOURCE_ROW_NUMBER, "source_inst_name", "source_worker_name",
    "source_status", "source_machine",
    "job_name", "task_name", "cap_cpu", "cap_mem", "cap_gpu",
    "machine_gpu_type", "avg_gpu_wrk_mem",
]


def _null_strings(length: int) -> pd.api.extensions.ExtensionArray:
    return pd.array([pd.NA] * length, dtype="string")


def _view(
    frame: pd.DataFrame, record_level: str, columns: Sequence[str], extra: Mapping
) -> pd.DataFrame:
    """Accepted rows only, with the core columns, trimmed to ``columns``."""
    accepted = frame.loc[~frame["is_rejected"].to_numpy(dtype=bool)]
    length = len(accepted)
    accepted = accepted.assign(
        schema_version=pd.array([SCHEMA_VERSION] * length, dtype="string"),
        dataset_id=pd.array(
            [ALIBABA_GPU_2020_CAPABILITIES.dataset_id] * length, dtype="string"
        ),
        record_level=pd.array([record_level] * length, dtype="string"),
        **{name: make(accepted) for name, make in extra.items()},
    )
    return accepted[list(columns)].reset_index(drop=True)


def _role_view(roles: pd.DataFrame) -> pd.DataFrame:
    """The role_occurrence view (contract §4.1).

    execution_id and instance_id are instance-level, so they are null here;
    job and task statuses are exposed under their source_ names.
    """
    return _view(roles, "role_occurrence", ROLE_VIEW_COLUMNS, {
        "execution_id": lambda frame: _null_strings(len(frame)),
        "instance_id": lambda frame: _null_strings(len(frame)),
        "source_job_status": lambda frame: frame["job_status"],
        "source_task_status": lambda frame: frame["task_status"],
    })


def _instance_view(instances: pd.DataFrame) -> pd.DataFrame:
    """The instance view (contract §5).

    exclusion_reason is present but always null: eligibility is decided at
    the role (schema §9.4), so a null here means not applicable.
    """
    return _view(instances, "instance", INSTANCE_VIEW_COLUMNS, {
        "exclusion_reason": lambda frame: _null_strings(len(frame)),
    })


def _rejected_dtypes(
    rejected: pd.DataFrame, sources: Sequence[pd.DataFrame]
) -> pd.DataFrame:
    """Give each rejected column a nullable form of its source dtype.

    Combining the job, role and instance levels leaves gaps, which turn
    integers into floats and flags into object columns. Each column gets
    back the dtype it has in the frame it came from, made nullable: flags
    become boolean, integers Int64, text string; other dtypes are kept.
    Values are unchanged. rejection_level and rejection_reason are text.
    """
    dtypes = {}
    for column in rejected.columns:
        source = next((frame[column] for frame in sources if column in frame.columns), None)
        dtype = source.dtype if source is not None else rejected[column].dtype
        if pd.api.types.is_bool_dtype(dtype):
            dtypes[column] = "boolean"
        elif pd.api.types.is_integer_dtype(dtype):
            dtypes[column] = "Int64"
        elif dtype == object or pd.api.types.is_string_dtype(dtype):
            dtypes[column] = "string"
        else:
            dtypes[column] = dtype
    return rejected.astype(dtypes)

def _eligibility_summary(
    roles: pd.DataFrame, failed_rules: Mapping[str, np.ndarray]
) -> dict[str, int]:
    """The Task 3 eligibility figures for metadata (design step B6).

    Counted over accepted roles. "All but multi_attempt_worker" ignores
    rule 10 only and applies the other 13, whatever rule 10 says.
    """
    accepted = ~roles["is_rejected"].to_numpy(dtype=bool)
    other_rules = np.zeros(len(roles), dtype=bool)
    for rule, failed in failed_rules.items():
        if rule != "multi_attempt_worker":
            other_rules |= failed
    eligible = accepted & roles["exclusion_reason"].isna().to_numpy()
    return {
        "accepted_roles": int(accepted.sum()),
        "pass_all_but_multi_attempt_worker": int((accepted & ~other_rules).sum()),
        "eligible": int(eligible.sum()),
        "eligible_missing_cpu": int((eligible & roles["observed_cpu"].isna().to_numpy()).sum()),
    }


class AlibabaGPU2020Adapter(BaseDatasetAdapter):
    adapter_name = "alibaba_gpu_v2020"
    adapter_version = "0.1.0"

    # Columns each rejected level must keep for source traceability
    # (schema §9.5; #79 Task 1 review notes). Rejected rows are never
    # zero-filled.
    rejected_required_columns = {
        "job": ("job_name",),
        "role_occurrence": ("job_name", "task_name"),
        "instance": ("source_row_number", "job_name", "task_name", "inst_name"),
    }

    def __init__(self) -> None:
        # Set by each successful prepare_sources() and map_prepared_sources()
        # call; build_multiview_metadata() adds them to metadata (design step B6).
        self.join_coverage_counts: dict[str, dict[str, int]] = {}
        self.eligibility_summary: dict[str, int] = {}

    @property
    def capabilities(self) -> DatasetCapabilities:
        return ALIBABA_GPU_2020_CAPABILITIES

    def to_canonical(self, source: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError(
            "Alibaba GPU 2020 needs its six source tables; use adapt_sources()"
        )

    # ------------------------------------------------------------------
    # Part A: joins, identity, timestamps, parent inheritance, rejection
    # ------------------------------------------------------------------

    def prepare_sources(
        self,
        sources: Mapping[str, pd.DataFrame],
    ) -> Mapping[str, pd.DataFrame]:
        """Join the six source tables into the jobs, roles and instances
        frames (design §4.1, step A1), then add role identity (step A2),
        instance identity (step A3), parent inheritance (step A4),
        timestamps (step A5) and rejection routing (step A6), then check
        role/instance linkage (step A7).

        Rejected rows stay in jobs, roles and instances with
        is_rejected = True and are also collected in the rejected frame.
        """
        missing = [table for table in SOURCE_COLUMNS if table not in sources]
        if missing:
            raise AdapterValidationError(f"missing source tables: {missing}")

        job = _select_source(sources, JOB_TABLE).rename(columns=JOB_RENAMES)
        task = _select_source(sources, TASK_TABLE).rename(columns=TASK_RENAMES)
        instance = _select_source(sources, INSTANCE_TABLE)
        sensor = _select_source(sources, SENSOR_TABLE)
        group_tag = _select_source(sources, GROUP_TAG_TABLE).rename(
            columns=GROUP_TAG_RENAMES
        )
        machine_spec = _select_source(sources, MACHINE_SPEC_TABLE).rename(
            columns=MACHINE_SPEC_RENAMES
        )

        _check_instance_row_numbers(instance)

        coverage: dict[str, dict[str, int]] = {}

        jobs, coverage["job_group_tag"] = _left_join(
            job, group_tag, ["job_inst_id"], "has_group_tag", "job <- group tag"
        )
        roles, coverage["task_job"] = _left_join(
            task, jobs, ["job_name"], "has_job", "task <- job"
        )
        instances, coverage["instance_task"] = _left_join(
            instance,
            task[ROLE_KEY_COLUMNS],
            ROLE_KEY_COLUMNS,
            "has_parent_role",
            "instance <- task",
        )
        # The sensor table is a unique lookup: every attempt of a worker
        # receives that worker's single sensor row; nothing is aggregated.
        instances, coverage["instance_sensor"] = _left_join(
            instances,
            sensor,
            SENSOR_KEY_COLUMNS,
            "has_sensor",
            "instance <- sensor",
        )
        instances, coverage["instance_machine_spec"] = _left_join(
            instances,
            machine_spec,
            ["machine"],
            "has_machine_spec",
            "instance <- machine spec",
        )

        # After every join, so the lookup-key checks run first.
        roles = _add_role_identity(roles)
        instances = _add_instance_identity(instances)
        instances = _inherit_parent_identity(instances, roles)
        roles, instances = _add_timestamps(jobs, roles, instances)
        jobs, roles, instances = _route_rejections(jobs, roles, instances)
        rejected = _build_rejected(jobs, roles, instances)
        validate_rejected_output(
            rejected, required_columns=self.rejected_required_columns
        )
        self._check_linkage(roles, instances)

        self.join_coverage_counts = coverage
        return {
            "jobs": jobs,
            "roles": roles,
            "instances": instances,
            "rejected": rejected,
        }

    def _check_linkage(
        self,
        roles: pd.DataFrame,
        instances: pd.DataFrame,
    ) -> None:
        """Check role/instance parent linkage (framework §9.2; design step A7).

        Accepted and rejected rows are checked as separate sets, so an
        orphan in either set fails, and an instance can never link to a
        parent role on the other side of the rejection split.

        Accepted rows use the full framework check, which with
        parent_job_submission semantics also requires each instance's
        event_time_us to be present and equal to its parent's
        start_time_us. Rejected rows have no submission time by
        definition, so the framework check runs with the event-time
        condition turned off (orphans and identity fields are still
        checked), and every rejected role and instance must instead have
        a null start_time_us / event_time_us. Nothing is changed or
        routed; a failure raises.
        """
        role_rejected = roles["is_rejected"].to_numpy(dtype=bool)
        instance_rejected = instances["is_rejected"].to_numpy(dtype=bool)
        rejected_capabilities = dataclasses.replace(
            self.capabilities, instance_event_time_semantics=None
        )

        for label, role_rows, instance_rows, capabilities in (
            ("accepted", ~role_rejected, ~instance_rejected, self.capabilities),
            ("rejected", role_rejected, instance_rejected, rejected_capabilities),
        ):
            try:
                validate_role_instance_linkage(
                    roles.loc[role_rows, LINKAGE_ROLE_COLUMNS],
                    instances.loc[instance_rows, LINKAGE_INSTANCE_COLUMNS],
                    capabilities=capabilities,
                )
            except AdapterValidationError as error:
                raise AdapterValidationError(
                    f"{label} rows: {error}"
                ) from error

        role_times = roles.loc[role_rejected, "start_time_us"]
        event_times = instances.loc[instance_rejected, "event_time_us"]
        if role_times.notna().any() or event_times.notna().any():
            sample = instances.loc[instance_rejected].loc[
                event_times.notna().to_numpy(), "instance_id"
            ].head(5).tolist()
            raise AdapterValidationError(
                "rejected rows: rejected roles and instances must have null "
                "start_time_us / event_time_us; "
                f"role_count={int(role_times.notna().sum())}, "
                f"instance_count={int(event_times.notna().sum())}, "
                f"sample_instance_ids={sample}"
            )

    # ------------------------------------------------------------------
    # Part B: exclusions, validity, resource mappings, aggregation
    # ------------------------------------------------------------------

    def map_prepared_sources(
        self, prepared: Mapping[str, pd.DataFrame]
    ) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
        """Build the two canonical views and the rejected output (design step B5).

        1. Run Part B in build order: B1 exclusions, B3 mappings, B4 role
           aggregation and scope, B2 validity (it reads B3 and B4 values).
        2. Rejected output: Part A's frame, built from the complete prepared
           frames; only its dtypes are cast.
        3. Views: accepted rows only, trimmed to the contract columns.

        adapt_sources() then validates the views, linkage and rejected output.
        """
        roles, instances = prepared["roles"], prepared["instances"]
        failed_rules = _failed_rules(roles, instances)
        roles = _assign_exclusion_reasons(roles, instances, failed_rules)
        roles, instances = _map_resources(roles, instances)
        roles = _aggregate_role_resources(roles, instances)
        roles, instances = _add_resource_scope(roles, instances)
        roles, instances = _assign_validity(roles, instances)
        self.eligibility_summary = _eligibility_summary(roles, failed_rules)

        rejected = _rejected_dtypes(
            prepared["rejected"],
            [prepared["jobs"], prepared["roles"], prepared["instances"]],
        )
        views = {
            "role_occurrence": _role_view(roles),
            "instance": _instance_view(instances),
        }
        return views, rejected

    def build_multiview_metadata(
        self,
        *,
        sources: Mapping[str, pd.DataFrame],
        views: Mapping[str, pd.DataFrame],
        rejected: pd.DataFrame,
        primary_view: str,
        provenance: Mapping,
    ) -> dict:
        """Framework metadata plus the Alibaba GPU 2020 figures (design step B6).

        - join_coverage_counts: the adapter's own Part A counts. They are
          computed in prepare_sources(), so a caller-supplied value raises.
        - exclusion_reason_counts: rule order, every reason including zeros,
          then <null> (eligible) last.
        - eligibility_summary: accepted, all-but-rule-10, eligible, and
          eligible with missing CPU.
        """
        if not self.join_coverage_counts or not self.eligibility_summary:
            raise AdapterValidationError(
                "metadata needs prepare_sources() and map_prepared_sources() first"
            )
        if provenance and provenance.get("join_coverage_counts"):
            raise AdapterValidationError(
                "join_coverage_counts come from the adapter, not provenance"
            )
        metadata = dict(super().build_multiview_metadata(
            sources=sources, views=views, rejected=rejected,
            primary_view=primary_view, provenance=provenance,
        ))

        counts = metadata["exclusion_reason_counts"]
        unknown = set(counts) - {*ALIBABA_GPU_2020_EXCLUSION_REASONS, "<null>"}
        if unknown:
            raise AdapterValidationError(f"unknown exclusion reasons: {sorted(unknown)}")
        metadata["exclusion_reason_counts"] = {
            reason: int(counts.get(reason, 0))
            for reason in (*ALIBABA_GPU_2020_EXCLUSION_REASONS, "<null>")
        }
        metadata["join_coverage_counts"] = {
            join: dict(values) for join, values in self.join_coverage_counts.items()
        }
        metadata["eligibility_summary"] = dict(self.eligibility_summary)
        return metadata
