"""Alibaba GPU 2020 (cluster-trace-gpu-v2020) adapter.

Turns the six official source tables into two validated canonical views and
a rejected output (adapter_framework.md §9.2):
- ``role_occurrence``: evaluation rows, one per task role of one job;
- ``instance``: audit rows, one per instance-table row, so every retry is its
  own row;
- rejected output: jobs without a submission time, rejected whole.

The adapter needs all six tables, so it runs only through ``adapt_sources()``.

The module has two marked sections (docs/planning/task3_implementation_plan.md):
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

# Columns read from each table (plan §5.1). Anything else is dropped:
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
# so the plain name always means an instance-file line (plan §5.1).
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
    (schema §5.3, D-04, D-05; plan step A2).

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
    and the raw source_ columns (schema §5.4, D-21; plan step A3).

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
    parent role row (schema §5.5, D-08; plan step A4).

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
    """Add canonical microsecond timestamps (schema §7, D-22; plan step A5).

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
    (schema §9.5, D-23; plan step A6).

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
        # Set by each successful prepare_sources() call; the build script
        # passes it into provenance (base.py reads it from the caller).
        self.join_coverage_counts: dict[str, dict[str, int]] = {}

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
        frames (plan §5.1, step A1), then add role identity (step A2),
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
        """Check role/instance parent linkage (framework §9.2; plan step A7).

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
