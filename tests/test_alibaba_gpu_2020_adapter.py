"""Fixture tests for the Alibaba GPU 2020 adapter (Task 3, #79)."""

import pandas as pd
import pytest

from src.adapters import AdapterValidationError, AlibabaGPU2020Adapter
from src.adapters.alibaba_gpu_2020 import (
    INSTANCE_VIEW_COLUMNS,
    ROLE_VIEW_COLUMNS,
    _add_role_identity,
    _add_resource_scope,
    _aggregate_role_resources,
    _assign_exclusion_reasons,
    _assign_validity,
    _eligibility_summary,
    _failed_rules,
    _map_resources,
    _build_rejected,
    _inherit_parent_identity,
    _route_rejections,
)
from src.adapters.validation import validate_rejected_output
from src.canonical.schema import (
    ALIBABA_GPU_2020_CAPABILITIES,
    ALIBABA_GPU_2020_EXCLUSION_REASONS,
)


def _frame(rows, columns):
    frame = pd.DataFrame(rows, columns=columns)
    frame["source_row_number"] = range(1, len(frame) + 1)
    return frame


def make_sources():
    """Small six-table fixture, shaped like the Task 2 loader output.

    - job j1 has a group tag; job j2 has none.
    - j1/worker has two attempts of worker w1 (a retry) and one unplaced
      instance with no worker_name and no machine.
    - the sensor table has one row for w1 and one unused row (w9).
    - the group-tag table has one unused row (i9).
    """
    job = _frame(
        [
            ["j1", "i1", "u1", "Terminated", 100.0, 200.0],
            ["j2", "i2", "u2", "Terminated", 110.0, 210.0],
        ],
        ["job_name", "inst_id", "user", "status", "start_time", "end_time"],
    )
    task = _frame(
        [
            ["j1", "worker", 2.0, "Terminated", 101.0, 199.0, 600.0, 29.0, 50.0, "T4"],
            ["j2", "tensorflow", 1.0, "Terminated", 111.0, 209.0, 400.0, 10.0, None, "MISC"],
        ],
        [
            "job_name", "task_name", "inst_num", "status", "start_time",
            "end_time", "plan_cpu", "plan_mem", "plan_gpu", "gpu_type",
        ],
    )
    instance = _frame(
        [
            ["j1", "worker", "a", "w1", "i1", "Failed", 101.0, 120.0, "m1"],
            ["j1", "worker", "a", "w1", "i1", "Terminated", 121.0, 199.0, "m1"],
            ["j1", "worker", "b", None, "i1", "Waiting", None, None, None],
            ["j2", "tensorflow", "c", "w2", "i2", "Terminated", 111.0, 209.0, "m2"],
        ],
        [
            "job_name", "task_name", "inst_name", "worker_name", "inst_id",
            "status", "start_time", "end_time", "machine",
        ],
    )
    sensor = _frame(
        [
            ["j1", "worker", "w1", "i1", "m1", "/dev/nvidia0", 1.5, 20.0, 3.0, 4.0, 1.0, 2.0, 10.0, 11.0, 1.0, 2.0],
            ["j1", "worker", "w9", "i1", "m1", "/dev/nvidia1", 0.5, 10.0, 1.0, 2.0, 0.5, 1.0, 5.0, 6.0, 1.0, 1.0],
        ],
        [
            "job_name", "task_name", "worker_name", "inst_id", "machine",
            "gpu_name", "cpu_usage", "gpu_wrk_util", "avg_mem", "max_mem",
            "avg_gpu_wrk_mem", "max_gpu_wrk_mem", "read", "write",
            "read_count", "write_count",
        ],
    )
    group_tag = _frame(
        [
            ["i1", "u1", "T4", "g1", "bert"],
            ["i9", "u9", "", "g9", None],
        ],
        ["inst_id", "user", "gpu_type_spec", "group", "workload"],
    )
    machine_spec = _frame(
        [
            ["m1", "T4", 96.0, 512.0, 2.0],
            ["m2", "CPU", 96.0, 512.0, 0.0],
        ],
        ["machine", "gpu_type", "cap_cpu", "cap_mem", "cap_gpu"],
    )
    return {
        "pai_job_table": job,
        "pai_task_table": task,
        "pai_instance_table": instance,
        "pai_sensor_table": sensor,
        "pai_group_tag_table": group_tag,
        "pai_machine_spec": machine_spec,
    }


def prepare(sources=None):
    adapter = AlibabaGPU2020Adapter()
    prepared = adapter.prepare_sources(sources or make_sources())
    return adapter, prepared


def test_adapter_uses_the_alibaba_gpu_2020_profile():
    adapter = AlibabaGPU2020Adapter()

    assert adapter.capabilities is ALIBABA_GPU_2020_CAPABILITIES
    assert adapter.capabilities.dataset_id == "alibaba_gpu_v2020"


def test_rejected_required_columns_cover_every_rejected_level():
    assert AlibabaGPU2020Adapter.rejected_required_columns == {
        "job": ("job_name",),
        "role_occurrence": ("job_name", "task_name"),
        "instance": ("source_row_number", "job_name", "task_name", "inst_name"),
    }


def test_single_table_path_is_not_supported():
    with pytest.raises(NotImplementedError, match="adapt_sources"):
        AlibabaGPU2020Adapter().to_canonical(pd.DataFrame())


# --- Class 2: prepare_sources joins (design §4.1) ---


def test_prepare_sources_returns_jobs_roles_instances_and_rejected():
    _, prepared = prepare()

    assert set(prepared) == {"jobs", "roles", "instances", "rejected"}


def test_job_without_group_tag_is_kept_with_flag_false():
    _, prepared = prepare()
    jobs = prepared["jobs"].set_index("job_name")

    assert jobs.loc["j1", "has_group_tag"]
    assert jobs.loc["j1", "group"] == "g1"
    assert not jobs.loc["j2", "has_group_tag"]
    assert pd.isna(jobs.loc["j2", "group"])
    roles = prepared["roles"].set_index("job_name")
    assert roles["has_job"].all()
    assert not roles.loc["j2", "has_group_tag"]


def test_null_driving_keys_never_match():
    # Instance row 3 has no worker_name and no machine. Lookup-side nulls
    # raise (test_null_lookup_key_raises), so it cannot match anything.
    _, prepared = prepare()
    unplaced = prepared["instances"].iloc[2]

    assert not unplaced["has_sensor"]
    assert not unplaced["has_machine_spec"]
    assert pd.isna(unplaced["max_mem"])
    assert pd.isna(unplaced["cap_mem"])
    assert unplaced["has_parent_role"]


def test_unmatched_sensor_key_keeps_sensor_values_null():
    # Instance c has worker_name w2, which has no sensor row.
    _, prepared = prepare()
    c = prepared["instances"].iloc[3]

    assert c["worker_name"] == "w2"
    assert not c["has_sensor"]
    for column in ("cpu_usage", "gpu_wrk_util", "avg_mem", "max_mem",
                   "avg_gpu_wrk_mem", "max_gpu_wrk_mem"):
        assert pd.isna(c[column])


def test_matched_machine_spec_values_are_copied():
    _, prepared = prepare()
    instances = prepared["instances"]
    placed = instances[instances["has_machine_spec"]]

    assert placed["machine"].tolist() == ["m1", "m1", "m2"]
    assert placed["cap_cpu"].tolist() == [96.0, 96.0, 96.0]
    assert placed["cap_mem"].tolist() == [512.0, 512.0, 512.0]
    assert placed["cap_gpu"].tolist() == [2.0, 2.0, 0.0]
    assert placed["machine_gpu_type"].tolist() == ["T4", "T4", "CPU"]
    # The spec gpu_type is kept apart from the task gpu_type.
    assert "gpu_type" not in instances.columns
    assert prepared["roles"]["gpu_type"].tolist() == ["T4", "MISC"]


@pytest.mark.parametrize(
    "table, row",
    [
        ("pai_job_table", 0),
        ("pai_task_table", 0),
        ("pai_sensor_table", 0),
        ("pai_group_tag_table", 0),
        ("pai_machine_spec", 0),
    ],
)
def test_duplicate_lookup_key_raises(table, row):
    sources = make_sources()
    frame = sources[table]
    sources[table] = pd.concat([frame, frame.iloc[[row]]], ignore_index=True)

    with pytest.raises(AdapterValidationError, match="duplicate lookup keys"):
        prepare(sources)


@pytest.mark.parametrize(
    "table, column",
    [
        ("pai_job_table", "job_name"),
        ("pai_task_table", "task_name"),
        ("pai_sensor_table", "worker_name"),
        ("pai_group_tag_table", "inst_id"),
        ("pai_machine_spec", "machine"),
    ],
)
def test_null_lookup_key_raises(table, column):
    sources = make_sources()
    sources[table].loc[0, column] = None

    with pytest.raises(AdapterValidationError, match="null lookup key"):
        prepare(sources)


def test_retried_worker_attempts_share_one_sensor_row_without_aggregation():
    _, prepared = prepare()
    instances = prepared["instances"]
    w1 = instances[instances["worker_name"] == "w1"]

    assert len(w1) == 2
    assert w1["has_sensor"].all()
    assert w1["max_mem"].tolist() == [4.0, 4.0]
    assert w1["cpu_usage"].tolist() == [1.5, 1.5]


def test_row_counts_order_and_instance_row_numbers_are_kept():
    sources = make_sources()
    _, prepared = prepare(sources)

    assert len(prepared["jobs"]) == len(sources["pai_job_table"])
    assert len(prepared["roles"]) == len(sources["pai_task_table"])
    assert len(prepared["instances"]) == len(sources["pai_instance_table"])
    assert prepared["instances"]["source_row_number"].tolist() == [1, 2, 3, 4]
    assert prepared["instances"]["status"].tolist() == [
        "Failed", "Terminated", "Waiting", "Terminated",
    ]


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda f: f.drop(columns="source_row_number"), "missing columns"),
        (lambda f: f.assign(source_row_number=[1, 2, None, 4]), "integer|null"),
        (lambda f: f.assign(source_row_number=[1, 2, 2, 4]), "duplicate"),
    ],
)
def test_instance_source_row_number_is_required(change, message):
    sources = make_sources()
    sources["pai_instance_table"] = change(sources["pai_instance_table"])

    with pytest.raises(AdapterValidationError, match=message):
        prepare(sources)


def test_job_and_task_row_numbers_are_optional_and_prefixed():
    _, prepared = prepare()
    assert prepared["jobs"]["job_source_row_number"].tolist() == [1, 2]
    assert prepared["roles"]["task_source_row_number"].tolist() == [1, 2]
    assert prepared["roles"]["job_source_row_number"].tolist() == [1, 2]

    sources = make_sources()
    for table in ("pai_job_table", "pai_task_table"):
        sources[table] = sources[table].drop(columns="source_row_number")
    _, prepared = prepare(sources)
    assert "job_source_row_number" not in prepared["jobs"].columns
    assert "task_source_row_number" not in prepared["roles"].columns
    assert "source_row_number" not in prepared["roles"].columns


def test_dropped_and_prefixed_columns():
    _, prepared = prepare()
    jobs, roles, instances = (
        prepared["jobs"], prepared["roles"], prepared["instances"]
    )

    for column in ("read", "write", "read_count", "write_count", "gpu_name"):
        assert column not in instances.columns
    assert "source_row_number" not in jobs.columns
    assert "source_row_number" not in roles.columns
    assert list(jobs.columns) == [
        "job_name", "job_inst_id", "user", "job_status", "job_start_time",
        "job_end_time", "job_source_row_number", "group", "workload",
        "gpu_type_spec", "has_group_tag", "is_rejected",
    ]
    assert list(roles.columns) == [
        "job_name", "task_name", "inst_num", "task_status", "task_start_time",
        "task_end_time", "plan_cpu", "plan_mem", "plan_gpu", "gpu_type",
        "task_source_row_number", "job_inst_id", "user", "job_status",
        "job_start_time", "job_end_time", "job_source_row_number", "group",
        "workload", "gpu_type_spec", "has_group_tag", "has_job",
        "workload_id", "recurrence_key", "occurrence_id", "role_key",
        "start_time_us", "end_time_us", "launch_time_us", "time_basis",
        "is_rejected",
    ]
    assert list(instances.columns) == [
        "job_name", "task_name", "inst_name", "worker_name", "inst_id",
        "status", "start_time", "end_time", "machine", "source_row_number",
        "has_parent_role", "cpu_usage", "gpu_wrk_util", "avg_mem", "max_mem",
        "avg_gpu_wrk_mem", "max_gpu_wrk_mem", "has_sensor",
        "machine_gpu_type", "cap_cpu", "cap_mem", "cap_gpu",
        "has_machine_spec", "instance_slot_key", "instance_attempt_index",
        "instance_id", "execution_id", "worker_id", "source_inst_name",
        "source_worker_name", "source_status", "source_machine",
        "workload_id", "recurrence_key", "occurrence_id", "role_key",
        "event_time_us", "start_time_us", "end_time_us", "time_basis",
        "is_rejected",
    ]


def test_join_coverage_counts_both_directions():
    adapter, _ = prepare()

    assert adapter.join_coverage_counts == {
        "job_group_tag": {
            "driving_matched": 1, "driving_unmatched": 1,
            "driving_null_key": 0, "lookup_used": 1, "lookup_unused": 1,
        },
        "task_job": {
            "driving_matched": 2, "driving_unmatched": 0,
            "driving_null_key": 0, "lookup_used": 2, "lookup_unused": 0,
        },
        "instance_task": {
            "driving_matched": 4, "driving_unmatched": 0,
            "driving_null_key": 0, "lookup_used": 2, "lookup_unused": 0,
        },
        "instance_sensor": {
            "driving_matched": 2, "driving_unmatched": 2,
            "driving_null_key": 1, "lookup_used": 1, "lookup_unused": 1,
        },
        "instance_machine_spec": {
            "driving_matched": 3, "driving_unmatched": 1,
            "driving_null_key": 1, "lookup_used": 2, "lookup_unused": 0,
        },
    }


def test_join_coverage_is_rebuilt_on_each_call_and_kept_on_failure():
    adapter, _ = prepare()
    first = adapter.join_coverage_counts
    adapter.prepare_sources(make_sources())
    assert adapter.join_coverage_counts == first

    broken = make_sources()
    broken["pai_machine_spec"] = pd.concat(
        [broken["pai_machine_spec"]] * 2, ignore_index=True
    )
    with pytest.raises(AdapterValidationError):
        adapter.prepare_sources(broken)
    assert adapter.join_coverage_counts == first


def test_missing_source_table_raises():
    sources = make_sources()
    del sources["pai_sensor_table"]

    with pytest.raises(AdapterValidationError, match="missing source tables"):
        prepare(sources)


def test_missing_source_column_raises():
    sources = make_sources()
    sources["pai_instance_table"] = sources["pai_instance_table"].drop(columns="machine")

    with pytest.raises(AdapterValidationError, match="is missing columns: \\['machine'\\]"):
        prepare(sources)


def test_prepare_sources_does_not_modify_inputs():
    sources = make_sources()
    before = {name: frame.copy() for name, frame in sources.items()}
    prepare(sources)

    for name, frame in sources.items():
        pd.testing.assert_frame_equal(frame, before[name])


# --- Class 3: role identity (design step A2) ---

IDENTITY_COLUMNS = ["workload_id", "recurrence_key", "occurrence_id", "role_key"]


def _roles(sources=None):
    _, prepared = prepare(sources)
    return prepared["roles"].set_index(["job_name", "task_name"], drop=False)


def _with_group(value):
    sources = make_sources()
    sources["pai_group_tag_table"].loc[0, "group"] = value
    return sources


def test_grouped_role_identity():
    role = _roles().loc[("j1", "worker")]

    assert role["workload_id"] == "g1"
    assert role["recurrence_key"] == "g1||worker"
    assert role["occurrence_id"] == "g1||j1"
    assert role["role_key"] == "g1||j1||worker"


def test_fallback_role_identity_for_job_without_group():
    role = _roles().loc[("j2", "tensorflow")]

    assert role["workload_id"] == "j2"
    assert pd.isna(role["recurrence_key"])
    assert role["occurrence_id"] == "j2"
    assert role["role_key"] == "j2||tensorflow"


def test_required_identity_fields_are_never_null():
    roles = _roles()

    for column in ("workload_id", "occurrence_id", "role_key"):
        assert roles[column].notna().all()


def test_role_key_is_unique():
    assert _roles()["role_key"].is_unique


def test_duplicate_role_key_raises():
    # Duplicate task keys raise earlier in prepare_sources, so the guard is
    # tested on the helper directly with one role row repeated.
    _, prepared = prepare()
    roles = prepared["roles"].drop(columns=IDENTITY_COLUMNS)
    repeated = pd.concat([roles, roles.iloc[[0]]], ignore_index=True)

    with pytest.raises(AdapterValidationError, match="duplicate role_key"):
        _add_role_identity(repeated)


def test_roles_of_one_job_share_occurrence_but_not_role_key():
    sources = make_sources()
    task = sources["pai_task_table"]
    ps = task.iloc[[0]].assign(task_name="ps", source_row_number=3)
    sources["pai_task_table"] = pd.concat([task, ps], ignore_index=True)
    roles = _roles(sources)
    worker, ps = roles.loc[("j1", "worker")], roles.loc[("j1", "ps")]

    assert worker["occurrence_id"] == ps["occurrence_id"] == "g1||j1"
    assert worker["role_key"] != ps["role_key"]
    assert worker["recurrence_key"] != ps["recurrence_key"]


def test_job_without_submission_time_still_gets_identity():
    sources = make_sources()
    sources["pai_job_table"].loc[0, "start_time"] = None
    role = _roles(sources).loc[("j1", "worker")]

    assert role["role_key"] == "g1||j1||worker"


@pytest.mark.parametrize("missing", ["", "   ", "\t"])
def test_empty_or_whitespace_group_uses_fallback(missing):
    roles = _roles(_with_group(missing))
    role = roles.loc[("j1", "worker")]

    assert role["has_group_tag"]
    assert role["workload_id"] == "j1"
    assert pd.isna(role["recurrence_key"])
    assert role["occurrence_id"] == "j1"
    assert role["role_key"] == "j1||worker"


@pytest.mark.parametrize("missing", [None, "", "  "])
def test_missing_group_is_never_concatenated_into_a_key(missing):
    roles = _roles(_with_group(missing))

    for column in IDENTITY_COLUMNS:
        values = roles[column].dropna().astype(str)
        assert not values.str.contains("nan").any()
        assert not values.str.startswith("||").any()
        assert not values.str.contains("||||", regex=False).any()
        assert not values.str.startswith(" ").any()


@pytest.mark.parametrize(
    "table, column, row",
    [
        ("pai_group_tag_table", "group", 0),
        ("pai_job_table", "job_name", 1),
        ("pai_task_table", "task_name", 1),
    ],
)
def test_separator_inside_a_key_part_raises(table, column, row):
    sources = make_sources()
    frame = sources[table]
    value = frame.loc[row, column]
    frame.loc[row, column] = f"{value}||x"
    if table == "pai_job_table":
        sources["pai_task_table"].loc[1, "job_name"] = f"{value}||x"
        sources["pai_instance_table"].loc[3, "job_name"] = f"{value}||x"
    if table == "pai_task_table":
        sources["pai_instance_table"].loc[3, "task_name"] = f"{value}||x"

    with pytest.raises(AdapterValidationError, match="separator"):
        prepare(sources)


@pytest.mark.parametrize("column", ["job_name", "task_name"])
@pytest.mark.parametrize("blank", ["", "  "])
def test_blank_job_or_task_name_raises(column, blank):
    sources = make_sources()
    sources["pai_task_table"].loc[1, column] = blank

    with pytest.raises(AdapterValidationError, match=f"blank {column}"):
        prepare(sources)


def test_role_identity_changes_no_other_column():
    sources = make_sources()
    adapter = AlibabaGPU2020Adapter()
    task = sources["pai_task_table"]
    with_identity = adapter.prepare_sources(sources)

    roles = with_identity["roles"]
    assert list(roles.columns[-9:-5]) == IDENTITY_COLUMNS
    for column in IDENTITY_COLUMNS:
        assert column not in with_identity["jobs"].columns
    pd.testing.assert_series_equal(
        roles["task_name"], task["task_name"], check_names=False
    )
    assert roles["group"].tolist()[0] == "g1"
    assert pd.isna(roles["group"].tolist()[1])


# --- Class 4: instance identity (design step A3) ---

INSTANCE_IDENTITY_COLUMNS = [
    "instance_slot_key", "instance_attempt_index", "instance_id",
    "execution_id", "worker_id", "source_inst_name", "source_worker_name",
    "source_status", "source_machine",
]


def _sources_with_slot_a(starts):
    """Replace slot j1/worker/a with one attempt per start time, in the
    given row order (source_row_number follows row order)."""
    sources = make_sources()
    instance = sources["pai_instance_table"]
    template = instance.iloc[0]
    slot_rows = [
        template.copy().to_dict() | {"start_time": start, "worker_name": f"w{n}"}
        for n, start in enumerate(starts)
    ]
    others = instance[instance["inst_name"] != "a"].drop(
        columns="source_row_number"
    )
    rows = pd.concat(
        [pd.DataFrame(slot_rows).drop(columns="source_row_number"), others],
        ignore_index=True,
    )
    rows["source_row_number"] = range(1, len(rows) + 1)
    sources["pai_instance_table"] = rows
    sources["pai_sensor_table"] = sources["pai_sensor_table"].iloc[0:0]
    return sources


def _instances(sources=None):
    _, prepared = prepare(sources)
    return prepared["instances"]


def _slot_a(instances):
    slot = instances[instances["inst_name"] == "a"]
    return dict(zip(slot["source_row_number"], slot["instance_attempt_index"]))


def test_instance_key_formats():
    instances = _instances()
    first = instances.iloc[0]

    assert first["instance_slot_key"] == "j1||worker||a"
    assert first["execution_id"] == "j1||worker"
    assert first["instance_id"] == "j1||worker||a||1"
    assert instances.iloc[1]["instance_id"] == "j1||worker||a||2"
    assert instances.iloc[3]["instance_id"] == "j2||tensorflow||c||1"
    assert instances["instance_attempt_index"].dtype == "int64"


def test_retries_are_numbered_by_start_time_ascending():
    # Rows 1, 2, 3 start at 300, 100, 200.
    instances = _instances(_sources_with_slot_a([300.0, 100.0, 200.0]))

    assert _slot_a(instances) == {1: 3, 2: 1, 3: 2}


def test_null_start_time_is_ordered_last():
    instances = _instances(_sources_with_slot_a([None, 200.0, 100.0]))

    assert _slot_a(instances) == {1: 3, 2: 2, 3: 1}


def test_equal_start_times_are_ordered_by_source_row_number():
    instances = _instances(_sources_with_slot_a([100.0, 100.0, None, None]))

    assert _slot_a(instances) == {1: 1, 2: 2, 3: 3, 4: 4}


def test_attempt_order_does_not_depend_on_input_row_order():
    sources = _sources_with_slot_a([300.0, None, 100.0, 100.0])
    expected = _instances(sources).set_index("source_row_number")["instance_id"]

    shuffled = make_sources()
    shuffled.update(sources)
    shuffled["pai_instance_table"] = sources["pai_instance_table"].sample(
        frac=1, random_state=7
    )
    result = _instances(shuffled)

    assert result["source_row_number"].tolist() == (
        shuffled["pai_instance_table"]["source_row_number"].tolist()
    )
    pd.testing.assert_series_equal(
        result.set_index("source_row_number")["instance_id"].sort_index(),
        expected.sort_index(),
    )


def test_duplicate_input_index_labels_keep_rows_aligned():
    sources = _sources_with_slot_a([300.0, 100.0, 200.0])
    instance = sources["pai_instance_table"]
    instance.index = [0] * len(instance)
    instances = _instances(sources)

    assert _slot_a(instances) == {1: 3, 2: 1, 3: 2}
    assert instances["source_inst_name"].tolist() == instance["inst_name"].tolist()


def test_instance_id_is_unique_and_row_order_is_kept():
    sources = _sources_with_slot_a([300.0, 100.0, 200.0])
    instances = _instances(sources)

    assert instances["instance_id"].is_unique
    assert instances["source_row_number"].tolist() == (
        sources["pai_instance_table"]["source_row_number"].tolist()
    )


@pytest.mark.parametrize("missing", [None, "", "   "])
def test_worker_id_is_null_for_missing_worker_name(missing):
    sources = make_sources()
    sources["pai_instance_table"].loc[3, "worker_name"] = missing
    row = _instances(sources).iloc[3]

    assert pd.isna(row["worker_id"])
    if missing is None:
        assert pd.isna(row["source_worker_name"])
    else:
        assert row["source_worker_name"] == missing


def test_worker_id_copies_present_worker_name():
    instances = _instances()

    assert instances["worker_id"].tolist()[:2] == ["w1", "w1"]


def test_raw_source_columns_are_unchanged():
    sources = make_sources()
    sources["pai_instance_table"].loc[3, "status"] = ""
    raw = sources["pai_instance_table"]
    instances = _instances(sources)

    for source, column in [
        ("source_inst_name", "inst_name"),
        ("source_worker_name", "worker_name"),
        ("source_status", "status"),
        ("source_machine", "machine"),
    ]:
        pd.testing.assert_series_equal(
            instances[source], raw[column], check_names=False
        )
    assert instances.iloc[3]["source_status"] == ""
    assert pd.isna(instances.iloc[2]["source_machine"])


def test_no_source_seq_no_column():
    assert "source_seq_no" not in _instances().columns


@pytest.mark.parametrize("bad", [None, "", "  ", "a||b"])
def test_bad_inst_name_raises(bad):
    sources = make_sources()
    sources["pai_instance_table"].loc[0, "inst_name"] = bad

    with pytest.raises(AdapterValidationError, match="blank inst_name|separator"):
        prepare(sources)


@pytest.mark.parametrize("column", ["job_name", "task_name"])
def test_blank_instance_job_or_task_name_raises(column):
    sources = make_sources()
    sources["pai_instance_table"].loc[0, column] = "  "

    with pytest.raises(AdapterValidationError, match=f"instances: 1 rows have a blank {column}"):
        prepare(sources)


def test_instance_identity_changes_no_other_column():
    sources = make_sources()
    _, prepared = prepare(sources)
    instances = prepared["instances"]

    assert list(instances.columns[-18:-9]) == INSTANCE_IDENTITY_COLUMNS
    for column in INSTANCE_IDENTITY_COLUMNS:
        assert column not in prepared["jobs"].columns
        assert column not in prepared["roles"].columns
    for column in sources["pai_instance_table"].columns:
        pd.testing.assert_series_equal(
            instances[column],
            sources["pai_instance_table"][column],
            check_names=False,
        )


# --- Class 5: parent inheritance (design step A4) ---


def _parent_values(prepared):
    roles = prepared["roles"].set_index(["job_name", "task_name"])
    return roles[IDENTITY_COLUMNS]


def test_grouped_job_instances_inherit_parent_identity():
    instances = _instances()
    first = instances.iloc[0]

    assert first["workload_id"] == "g1"
    assert first["recurrence_key"] == "g1||worker"
    assert first["occurrence_id"] == "g1||j1"
    assert first["role_key"] == "g1||j1||worker"


def test_fallback_job_instances_inherit_fallback_identity():
    row = _instances().iloc[3]

    assert row["workload_id"] == "j2"
    assert pd.isna(row["recurrence_key"])
    assert row["occurrence_id"] == "j2"
    assert row["role_key"] == "j2||tensorflow"


@pytest.mark.parametrize("missing", ["", "   "])
def test_blank_group_fallback_is_inherited(missing):
    instances = _instances(_with_group(missing))

    for _, row in instances[instances["job_name"] == "j1"].iterrows():
        assert row["workload_id"] == "j1"
        assert pd.isna(row["recurrence_key"])
        assert row["occurrence_id"] == "j1"
        assert row["role_key"] == "j1||worker"


def test_inherited_values_equal_parent_values_exactly():
    _, prepared = prepare()
    parents = _parent_values(prepared)
    instances = prepared["instances"]
    expected = parents.loc[
        list(zip(instances["job_name"], instances["task_name"]))
    ].reset_index(drop=True)

    pd.testing.assert_frame_equal(
        instances[IDENTITY_COLUMNS].reset_index(drop=True),
        expected,
        check_dtype=False,
    )


def test_retries_and_unplaced_instances_inherit_the_same_role():
    instances = _instances()
    j1 = instances[instances["job_name"] == "j1"]

    assert len(j1) == 3
    assert j1["role_key"].nunique() == 1
    assert j1.iloc[2]["role_key"] == "g1||j1||worker"
    assert pd.isna(j1.iloc[2]["worker_id"])


def test_orphan_instance_keeps_parent_fields_null():
    # A4 alone: prepare_sources would stop at the A7 linkage check, so the
    # helper is called directly with j2's role removed.
    _, prepared = prepare()
    instances = prepared["instances"].drop(columns=IDENTITY_COLUMNS)
    roles = prepared["roles"][prepared["roles"]["job_name"] != "j2"]
    row = _inherit_parent_identity(instances, roles).iloc[3]

    for column in IDENTITY_COLUMNS:
        assert pd.isna(row[column])


def test_existing_parent_identity_column_raises():
    # role_key is not a source column (it is dropped on selection), so the
    # helper is called directly on frames that already carry it.
    _, prepared = prepare()

    with pytest.raises(AdapterValidationError, match="already present"):
        _inherit_parent_identity(prepared["instances"], prepared["roles"])


def test_inherited_role_key_must_match_execution_id():
    _, prepared = prepare()
    instances = prepared["instances"].drop(columns=IDENTITY_COLUMNS)
    roles = prepared["roles"].copy()
    roles.loc[roles["job_name"] == "j2", "role_key"] = "j2||other"

    with pytest.raises(AdapterValidationError, match="do not match"):
        _inherit_parent_identity(instances, roles)


def test_inheritance_keeps_rows_aligned_with_duplicate_or_shuffled_index():
    sources = make_sources()
    instance = sources["pai_instance_table"].iloc[[3, 0, 2, 1]]
    instance.index = [5, 5, 5, 5]
    sources["pai_instance_table"] = instance
    instances = _instances(sources)

    assert instances["source_row_number"].tolist() == [4, 1, 3, 2]
    assert instances["role_key"].tolist() == [
        "j2||tensorflow", "g1||j1||worker", "g1||j1||worker", "g1||j1||worker",
    ]


def test_inheritance_changes_nothing_else():
    sources = make_sources()
    _, prepared = prepare(sources)
    instances = prepared["instances"]

    assert list(instances.columns[-9:-5]) == IDENTITY_COLUMNS
    for column in IDENTITY_COLUMNS:
        assert column not in prepared["jobs"].columns
    assert list(prepared["roles"].columns[-9:-5]) == IDENTITY_COLUMNS
    for column in sources["pai_instance_table"].columns:
        pd.testing.assert_series_equal(
            instances[column],
            sources["pai_instance_table"][column],
            check_names=False,
        )


# --- Class 6: timestamps (design step A5) ---

ROLE_TIME_COLUMNS = ["start_time_us", "end_time_us", "launch_time_us", "time_basis"]
INSTANCE_TIME_COLUMNS = ["event_time_us", "start_time_us", "end_time_us", "time_basis"]
RAW_TIME_COLUMNS = {
    "roles": ["job_start_time", "job_end_time", "task_start_time", "task_end_time"],
    "instances": ["start_time", "end_time"],
}


def test_role_timestamps_are_job_times_and_task_launch():
    roles = _roles()
    j1 = roles.loc[("j1", "worker")]

    assert j1["start_time_us"] == 100_000_000
    assert j1["end_time_us"] == 200_000_000
    assert j1["launch_time_us"] == 101_000_000


def test_null_job_end_gives_null_role_end():
    sources = make_sources()
    sources["pai_job_table"].loc[1, "end_time"] = None
    role = _roles(sources).loc[("j2", "tensorflow")]

    assert pd.isna(role["end_time_us"])
    assert role["start_time_us"] == 110_000_000
    assert role["launch_time_us"] == 111_000_000


def test_roles_have_no_event_time():
    assert "event_time_us" not in _roles().columns


def test_instance_event_time_is_parent_job_submission():
    instances = _instances()

    assert instances["event_time_us"].tolist() == [
        100_000_000, 100_000_000, 100_000_000, 110_000_000,
    ]


def test_null_instance_start_is_not_filled():
    row = _instances().iloc[2]

    assert pd.isna(row["start_time_us"])
    assert pd.isna(row["end_time_us"])
    assert row["event_time_us"] == 100_000_000


def test_job_without_submission_leaves_times_null_without_error():
    sources = make_sources()
    sources["pai_job_table"].loc[0, "start_time"] = None
    _, prepared = prepare(sources)
    role = prepared["roles"].iloc[0]
    j1 = prepared["instances"][prepared["instances"]["job_name"] == "j1"]

    assert pd.isna(role["start_time_us"])
    assert role["launch_time_us"] == 101_000_000
    assert j1["event_time_us"].isna().all()
    assert j1["start_time_us"].tolist()[:2] == [101_000_000, 121_000_000]


@pytest.mark.parametrize(
    "table, column",
    [
        ("pai_job_table", "start_time"),
        ("pai_task_table", "start_time"),
        ("pai_instance_table", "end_time"),
    ],
)
def test_fractional_microsecond_raises(table, column):
    sources = make_sources()
    sources[table].loc[0, column] = 1.0000005

    with pytest.raises(AdapterValidationError, match="whole number of microseconds"):
        prepare(sources)


def test_timestamp_dtypes_and_time_basis():
    _, prepared = prepare()

    for column in ROLE_TIME_COLUMNS[:3]:
        assert prepared["roles"][column].dtype == "Int64"
    for column in INSTANCE_TIME_COLUMNS[:3]:
        assert prepared["instances"][column].dtype == "Int64"
    assert (prepared["roles"]["time_basis"] == "trace_relative").all()
    assert (prepared["instances"]["time_basis"] == "trace_relative").all()


def test_timestamps_change_nothing_else():
    sources = make_sources()
    _, prepared = prepare(sources)
    roles, instances = prepared["roles"], prepared["instances"]

    assert list(roles.columns[-5:-1]) == ROLE_TIME_COLUMNS
    assert list(instances.columns[-5:-1]) == INSTANCE_TIME_COLUMNS
    for column in ROLE_TIME_COLUMNS + INSTANCE_TIME_COLUMNS:
        assert column not in prepared["jobs"].columns
    assert roles["job_start_time"].tolist() == [100.0, 110.0]
    assert roles["task_start_time"].tolist() == [101.0, 111.0]
    for column in sources["pai_instance_table"].columns:
        pd.testing.assert_series_equal(
            instances[column],
            sources["pai_instance_table"][column],
            check_names=False,
        )


def test_timestamps_stay_aligned_with_duplicate_or_shuffled_index():
    sources = make_sources()
    instance = sources["pai_instance_table"].iloc[[3, 0, 2, 1]]
    instance.index = [9, 9, 9, 9]
    sources["pai_instance_table"] = instance
    instances = _instances(sources)

    assert instances["source_row_number"].tolist() == [4, 1, 3, 2]
    assert instances["event_time_us"].tolist() == [
        110_000_000, 100_000_000, 100_000_000, 100_000_000,
    ]
    assert instances["start_time_us"].tolist()[:2] == [111_000_000, 101_000_000]


# --- Class 7: rejection routing (design step A6) ---


def _sources_with_rejected_j1():
    """j1 has no submission time; its first two instances have own starts."""
    sources = make_sources()
    sources["pai_job_table"].loc[0, "start_time"] = None
    return sources


def test_whole_job_without_submission_is_flagged():
    _, prepared = prepare(_sources_with_rejected_j1())

    assert prepared["jobs"]["is_rejected"].tolist() == [True, False]
    assert prepared["roles"]["is_rejected"].tolist() == [True, False]
    assert prepared["instances"]["is_rejected"].tolist() == [True, True, True, False]


def test_rejected_instance_with_own_start_is_still_rejected():
    _, prepared = prepare(_sources_with_rejected_j1())
    first = prepared["instances"].iloc[0]

    assert first["start_time_us"] == 101_000_000
    assert first["is_rejected"]


def test_rejected_output_has_rows_at_each_level():
    _, prepared = prepare(_sources_with_rejected_j1())
    rejected = prepared["rejected"]

    assert rejected["rejection_level"].tolist() == [
        "job", "role_occurrence", "instance", "instance", "instance",
    ]
    assert (rejected["rejection_reason"] == "missing_submission_time").all()
    assert list(rejected.columns[:2]) == ["rejection_level", "rejection_reason"]


def test_rejected_output_passes_framework_check():
    _, prepared = prepare(_sources_with_rejected_j1())

    validate_rejected_output(
        prepared["rejected"],
        required_columns=AlibabaGPU2020Adapter.rejected_required_columns,
    )


def test_rejected_rows_keep_source_values_without_filling():
    _, prepared = prepare(_sources_with_rejected_j1())
    rejected = prepared["rejected"]
    job = rejected[rejected["rejection_level"] == "job"].iloc[0]
    role = rejected[rejected["rejection_level"] == "role_occurrence"].iloc[0]
    instances = rejected[rejected["rejection_level"] == "instance"]

    assert job["job_name"] == "j1"
    assert pd.isna(job["source_row_number"])
    assert pd.isna(job["role_key"])
    assert pd.isna(job["job_start_time"])
    assert role["role_key"] == "g1||j1||worker"
    assert role["task_source_row_number"] == 1
    assert pd.isna(role["source_row_number"])
    assert pd.isna(role["start_time_us"])
    assert instances["source_row_number"].tolist() == [1, 2, 3]
    assert instances["instance_id"].tolist() == [
        "j1||worker||a||1", "j1||worker||a||2", "j1||worker||b||1",
    ]
    assert instances["role_key"].eq("g1||j1||worker").all()
    assert pd.isna(instances.iloc[2]["worker_name"])
    assert pd.isna(instances.iloc[2]["machine"])


def test_no_rejected_jobs_gives_empty_rejected_output():
    _, prepared = prepare()

    assert prepared["rejected"].empty
    for name in ("jobs", "roles", "instances"):
        assert not prepared[name]["is_rejected"].any()


def test_role_flag_and_start_time_must_agree():
    _, prepared = prepare()
    jobs, roles, instances = (
        prepared[name].drop(columns="is_rejected")
        for name in ("jobs", "roles", "instances")
    )
    roles.loc[roles.index[0], "start_time_us"] = pd.NA

    with pytest.raises(AdapterValidationError, match="null start_time_us"):
        _route_rejections(jobs, roles, instances)


def test_instance_flag_and_event_time_must_agree():
    _, prepared = prepare()
    jobs, roles, instances = (
        prepared[name].drop(columns="is_rejected")
        for name in ("jobs", "roles", "instances")
    )
    instances.loc[instances.index[0], "event_time_us"] = pd.NA

    with pytest.raises(AdapterValidationError, match="null event_time_us"):
        _route_rejections(jobs, roles, instances)


def test_accepted_keys_never_appear_in_rejected_output():
    _, prepared = prepare(_sources_with_rejected_j1())
    rejected = prepared["rejected"]
    roles, instances = prepared["roles"], prepared["instances"]

    accepted_roles = set(roles.loc[~roles["is_rejected"], "role_key"])
    accepted_instances = set(instances.loc[~instances["is_rejected"], "instance_id"])
    assert accepted_roles.isdisjoint(rejected["role_key"].dropna())
    assert accepted_instances.isdisjoint(rejected["instance_id"].dropna())


def test_routing_keeps_rows_and_changes_nothing_else():
    sources = _sources_with_rejected_j1()
    _, prepared = prepare(sources)

    for name in ("jobs", "roles", "instances"):
        assert prepared[name].columns[-1] == "is_rejected"
    assert len(prepared["roles"]) == 2
    assert len(prepared["instances"]) == 4
    assert prepared["instances"]["source_row_number"].tolist() == [1, 2, 3, 4]
    for column in sources["pai_instance_table"].columns:
        pd.testing.assert_series_equal(
            prepared["instances"][column],
            sources["pai_instance_table"][column],
            check_names=False,
        )


def test_build_rejected_requires_no_zero_filling():
    _, prepared = prepare(_sources_with_rejected_j1())
    rejected = _build_rejected(
        prepared["jobs"], prepared["roles"], prepared["instances"]
    )
    job_rows = rejected[rejected["rejection_level"] == "job"]

    for column in ("plan_cpu", "max_mem", "cap_mem", "start_time_us"):
        assert job_rows[column].isna().all()


# ----------------------------------------------------------------------
# Role/instance linkage (A7)


def _linkage_frames(sources=None):
    adapter, prepared = prepare(sources)
    return adapter, prepared["roles"].copy(), prepared["instances"].copy()


def test_linkage_passes_for_accepted_rows():
    adapter, roles, instances = _linkage_frames()

    assert not roles["is_rejected"].any()
    adapter._check_linkage(roles, instances)


def test_linkage_passes_for_a_rejected_job():
    adapter, roles, instances = _linkage_frames(_sources_with_rejected_j1())

    assert instances["event_time_us"].isna().tolist() == [True, True, True, False]
    adapter._check_linkage(roles, instances)


def test_orphan_instance_fails_linkage():
    sources = make_sources()
    sources["pai_instance_table"].loc[3, "task_name"] = "missing_task"

    with pytest.raises(AdapterValidationError, match="accepted rows: .*orphan_count=1"):
        prepare(sources)


def test_rejected_orphan_instance_fails_linkage():
    sources = _sources_with_rejected_j1()
    sources["pai_instance_table"].loc[2, "task_name"] = "missing_task"

    with pytest.raises(AdapterValidationError, match="rejected rows: .*orphan_count=1"):
        prepare(sources)


@pytest.mark.parametrize("column", ["workload_id", "recurrence_key", "occurrence_id"])
def test_tampered_identity_field_fails_linkage(column):
    adapter, roles, instances = _linkage_frames()
    instances.loc[0, column] = "tampered"

    with pytest.raises(AdapterValidationError, match="identity_mismatch_count=1"):
        adapter._check_linkage(roles, instances)


def test_tampered_event_time_fails_linkage():
    adapter, roles, instances = _linkage_frames()
    instances.loc[0, "event_time_us"] = 1

    with pytest.raises(AdapterValidationError, match="event_time_mismatch_count=1"):
        adapter._check_linkage(roles, instances)


def test_accepted_instance_with_rejected_parent_fails_linkage():
    adapter, roles, instances = _linkage_frames(_sources_with_rejected_j1())
    instances.loc[0, "is_rejected"] = False

    with pytest.raises(AdapterValidationError, match="accepted rows: .*orphan_count=1"):
        adapter._check_linkage(roles, instances)


def test_rejected_instance_with_accepted_parent_fails_linkage():
    adapter, roles, instances = _linkage_frames()
    instances.loc[3, "is_rejected"] = True

    with pytest.raises(AdapterValidationError, match="rejected rows: .*orphan_count=1"):
        adapter._check_linkage(roles, instances)


def test_rejected_rows_with_a_time_fail_linkage():
    adapter, roles, instances = _linkage_frames(_sources_with_rejected_j1())
    instances.loc[0, "event_time_us"] = 100_000_000

    with pytest.raises(AdapterValidationError, match="must have null"):
        adapter._check_linkage(roles, instances)


# ----------------------------------------------------------------------
# Exclusion rules (B1)

B1_ROLE = {
    "role_key": "r1", "recurrence_key": "g1", "job_status": "Terminated",
    "end_time_us": 200, "task_status": "Terminated", "plan_cpu": 600.0,
    "plan_mem": 29.0, "is_rejected": False,
}
B1_INSTANCE = {
    "role_key": "r1", "status": "Terminated", "has_sensor": True,
    "cpu_usage": 1.5, "avg_mem": 3.0, "max_mem": 4.0, "cap_mem": 512.0,
    "is_rejected": False,
}
TEXT = "string"


def _b1_frames(role=None, instances=None):
    """One eligible role "r1" with two good instances (workers w0, w1).

    ``role`` changes role fields; ``instances`` is one dict of changes per
    instance row (``[]`` gives a role with no instances).
    """
    role_row = dict(B1_ROLE, **(role or {}))
    rows = [
        {**B1_INSTANCE, "worker_name": f"w{n}", "worker_id": f"w{n}",
         "is_rejected": role_row["is_rejected"], **changes}
        for n, changes in enumerate([{}, {}] if instances is None else instances)
    ]
    roles = pd.DataFrame([role_row]).astype(
        {"role_key": TEXT, "recurrence_key": TEXT, "job_status": TEXT,
         "task_status": TEXT, "end_time_us": "Int64"})
    columns = list(B1_INSTANCE) + ["worker_name", "worker_id"]
    instance_frame = pd.DataFrame(rows, columns=columns).astype(
        {"role_key": TEXT, "status": TEXT, "worker_name": TEXT, "worker_id": TEXT,
         "has_sensor": bool, "is_rejected": bool, "max_mem": float,
         "avg_mem": float, "cap_mem": float, "cpu_usage": float})
    return roles, instance_frame


SAME_WORKER = {"worker_name": "w1", "worker_id": "w1"}
NO_WORKER = {"worker_name": None, "worker_id": None}


@pytest.mark.parametrize(
    "expected, role, instances",
    [
        # Each rule on its own condition.
        ("no_recurrence_key", {"recurrence_key": None}, None),
        ("job_failed", {"job_status": "Failed"}, None),
        ("job_incomplete", {"job_status": "Running"}, None),
        ("job_incomplete", {"end_time_us": None}, None),
        ("task_not_terminated", {"task_status": "Waiting"}, None),
        ("missing_or_invalid_request", {"plan_cpu": None}, None),
        ("missing_or_invalid_request", {"plan_mem": 0.0}, None),
        ("instance_failed", None, [{"status": "Failed"}, {}]),
        ("instance_interrupted", None, [{"status": "Interrupted"}, {}]),
        ("instance_incomplete", None, [{"status": "Running"}, {}]),
        ("missing_worker_name", None, [{"worker_name": " ", "worker_id": None}, {}]),
        ("multi_attempt_worker", None, [SAME_WORKER, SAME_WORKER]),
        ("missing_sensor", None, [{"has_sensor": False}, {"has_sensor": False}]),
        ("partial_sensor_coverage", None, [{"has_sensor": False}, {}]),
        ("invalid_memory_exceeds_capacity", None, [{"max_mem": 600.0}, {}]),
        ("invalid_resource", None, [{"max_mem": 2.0}, {}]),
        ("invalid_resource", None, [{"avg_mem": -1.0}, {}]),
        # The first broken rule wins.
        ("job_failed", {"job_status": "Failed"}, [{"status": "Failed", "has_sensor": False}, {}]),
        # A null status is "not Terminated".
        ("job_incomplete", {"job_status": None}, None),
        ("task_not_terminated", {"task_status": None}, None),
        ("instance_incomplete", None, [{"status": None}, {}]),
        # No instances is missing_sensor, never partial_sensor_coverage.
        ("missing_sensor", None, []),
        # Null worker ids are not duplicates.
        ("missing_worker_name", None, [NO_WORKER, NO_WORKER]),
        # Eligible: numeric nulls and missing CPU never exclude.
        (None, None, None),
        (None, None, [{"cap_mem": None, "max_mem": 9999.0}, {}]),
        (None, None, [{"max_mem": None}, {"avg_mem": None}]),
        (None, None, [{"cpu_usage": None}, {"cpu_usage": None}]),
        # Rejected roles are skipped.
        (None, {"is_rejected": True, "job_status": "Waiting"}, None),
    ],
)
def test_exclusion_reason(expected, role, instances):
    result = _assign_exclusion_reasons(*_b1_frames(role, instances))
    reason = result["exclusion_reason"].iloc[0]

    assert (pd.isna(reason) and expected is None) or reason == expected


def test_same_worker_in_different_roles_is_not_multi_attempt():
    roles, instances = _b1_frames(None, [SAME_WORKER])
    other = {"role_key": pd.array(["r2"], dtype=TEXT)}

    result = _assign_exclusion_reasons(
        pd.concat([roles, roles.assign(**other)], ignore_index=True),
        pd.concat([instances, instances.assign(**other)], ignore_index=True),
    )

    assert result["exclusion_reason"].isna().all()


def test_exclusion_reason_is_string_and_inputs_are_unchanged():
    roles, instances = _b1_frames(None, [{"status": "Failed"}, {}])
    roles_before, instances_before = roles.copy(), instances.copy()

    result = _assign_exclusion_reasons(roles, instances)

    assert result["exclusion_reason"].dtype == TEXT
    pd.testing.assert_frame_equal(result.drop(columns="exclusion_reason"), roles_before)
    pd.testing.assert_frame_equal(instances, instances_before)


def test_existing_exclusion_reason_raises():
    roles, instances = _b1_frames()
    roles["exclusion_reason"] = pd.NA

    with pytest.raises(AdapterValidationError, match="exclusion_reason already present"):
        _assign_exclusion_reasons(roles, instances)


def test_exclusion_reasons_on_the_prepared_fixture():
    _, prepared = prepare()

    result = _assign_exclusion_reasons(prepared["roles"], prepared["instances"])

    # j1/worker has a failed retry of w1; j2 has no group tag.
    assert dict(zip(result["job_name"], result["exclusion_reason"])) == {
        "j1": "instance_failed", "j2": "no_recurrence_key"}


# ----------------------------------------------------------------------
# Resource mappings (B3)

ROLE_SOURCES = {"requested_cpu": "plan_cpu", "requested_memory": "plan_mem",
                "requested_gpu": "plan_gpu"}
INSTANCE_SOURCES = {"observed_cpu": "cpu_usage", "observed_memory": "avg_mem",
                    "peak_memory": "max_mem", "observed_gpu": "gpu_wrk_util",
                    "peak_gpu_memory": "max_gpu_wrk_mem"}
UNITS = {"requested_cpu": "percent_of_vcpu", "requested_memory": "gb",
         "requested_gpu": "percent_of_gpu", "observed_cpu": "percent_of_vcpu",
         "observed_memory": "gb", "peak_memory": "gb",
         "observed_gpu": "percent_of_gpu", "peak_gpu_memory": "gb"}


def _mapped(sources=None):
    _, prepared = prepare(sources)
    return _map_resources(prepared["roles"], prepared["instances"])


def test_values_are_copied_from_their_source_columns():
    roles, instances = _mapped()

    for frame, sources in ((roles, ROLE_SOURCES), (instances, INSTANCE_SOURCES)):
        for field, source in sources.items():
            pd.testing.assert_series_equal(
                frame[field], frame[source], check_names=False)
            assert (frame[f"{field}_unit"] == UNITS[field]).all()
    assert instances["peak_cpu"].isna().all()
    assert instances["peak_cpu_unit"].isna().all()
    # Requests stay on roles; usage reaches roles only in B4.
    assert not set(INSTANCE_SOURCES) & set(roles.columns)
    assert not set(ROLE_SOURCES) & set(instances.columns)


def test_instance_without_sensor_row_keeps_null_usage():
    _, instances = _mapped()
    no_sensor = instances.loc[~instances["has_sensor"]]

    assert len(no_sensor) == 2
    assert no_sensor[list(INSTANCE_SOURCES)].isna().all().all()
    # The unit is still set: it describes the column, not one value.
    assert (no_sensor["peak_memory_unit"] == "gb").all()


def test_missing_values_stay_null_and_rejected_rows_are_mapped():
    roles, _ = _mapped(_sources_with_rejected_j1())

    assert roles["is_rejected"].any()
    # j2 has no plan_gpu in the fixture.
    assert roles.loc[roles["job_name"] == "j2", "requested_gpu"].isna().all()
    assert roles["requested_cpu"].notna().all()


def test_mapping_leaves_inputs_unchanged_and_refuses_to_run_twice():
    _, prepared = prepare()
    roles, instances = prepared["roles"], prepared["instances"]
    before = roles.copy(), instances.copy()

    mapped_roles, mapped_instances = _map_resources(roles, instances)

    pd.testing.assert_frame_equal(roles, before[0])
    pd.testing.assert_frame_equal(instances, before[1])
    with pytest.raises(AdapterValidationError, match="already present"):
        _map_resources(mapped_roles, mapped_instances)


# ----------------------------------------------------------------------
# Role aggregation and scope (B4)

USAGE = list(INSTANCE_SOURCES)


def _b4_frames(instance_rows, role_keys=("r1",)):
    """Roles by key; instances as (role_key, has_sensor, cpu, avg, peak)."""
    roles = pd.DataFrame({"role_key": pd.array(list(role_keys), dtype=TEXT)})
    instances = pd.DataFrame(
        instance_rows,
        columns=["role_key", "has_sensor", "observed_cpu", "observed_memory",
                 "peak_memory"],
    ).astype({"role_key": TEXT, "has_sensor": bool, "observed_cpu": float,
              "observed_memory": float, "peak_memory": float})
    instances["observed_gpu"] = instances["peak_memory"] * 10
    instances["peak_gpu_memory"] = instances["peak_memory"] / 2
    return roles, instances


def _role_values(instance_rows, role_keys=("r1",)):
    return _aggregate_role_resources(*_b4_frames(instance_rows, role_keys))


def test_role_value_is_the_maximum_never_the_sum():
    # r2 has no instances at all.
    result = _role_values(
        [("r1", True, 50.0, 3.0, 4.0), ("r1", True, 80.0, 2.0, 6.0)],
        role_keys=("r1", "r2"),
    )

    assert result[["observed_cpu", "observed_memory", "peak_memory"]].iloc[0].tolist() == [80.0, 3.0, 6.0]
    assert result[["observed_gpu", "peak_gpu_memory"]].iloc[0].tolist() == [60.0, 3.0]
    assert result[USAGE].iloc[1].isna().all()
    for field in USAGE:
        assert (result[f"{field}_unit"] == UNITS[field]).all()
    assert result["peak_cpu"].isna().all() and result["peak_cpu_unit"].isna().all()


def test_missing_value_on_a_covered_worker_makes_the_role_value_null():
    result = _role_values([("r1", True, None, None, 4.0), ("r1", True, 80.0, 2.0, 6.0)])

    assert result[["observed_cpu", "observed_memory"]].isna().all(axis=None)
    assert result["peak_memory"].iloc[0] == 6.0


def test_instances_without_a_sensor_row_are_ignored():
    result = _role_values([("r1", True, 50.0, 3.0, 4.0), ("r1", False, None, None, None)])

    assert result[["observed_cpu", "peak_memory"]].iloc[0].tolist() == [50.0, 4.0]


def test_a_retry_does_not_change_the_maximum():
    single = _role_values([("r1", True, 50.0, 3.0, 4.0)])
    retried = _role_values([("r1", True, 50.0, 3.0, 4.0), ("r1", True, 50.0, 3.0, 4.0)])

    pd.testing.assert_frame_equal(single, retried)


def test_aggregation_on_the_mapped_fixture():
    roles, instances = _mapped()

    result = _aggregate_role_resources(roles, instances)
    values = result.set_index("job_name")

    # j1/worker: both attempts of w1 carry its one sensor row; j2 has none.
    assert values.loc["j1", "peak_memory"] == 4.0
    assert values.loc["j1", "observed_cpu"] == 1.5
    assert values.loc["j2", USAGE].isna().all()


def test_scope_columns_are_constants_per_frame():
    roles, instances = _add_resource_scope(*_b4_frames([("r1", False, None, None, None)]))

    assert roles[["resource_scope", "request_aggregation_method",
                  "observed_aggregation_method"]].iloc[0].tolist() == [
        "task_role_per_instance", "none", "maximum_over_instances"]
    assert instances[["resource_scope", "request_aggregation_method",
                      "observed_aggregation_method"]].iloc[0].tolist() == [
        "instance", "none", "none"]


def test_b4_leaves_inputs_unchanged_and_refuses_to_run_twice():
    roles, instances = _b4_frames([("r1", True, 50.0, 3.0, 4.0)])
    before = roles.copy(), instances.copy()

    aggregated = _aggregate_role_resources(roles, instances)
    scoped = _add_resource_scope(roles, instances)

    pd.testing.assert_frame_equal(roles, before[0])
    pd.testing.assert_frame_equal(instances, before[1])
    with pytest.raises(AdapterValidationError, match="already present"):
        _aggregate_role_resources(aggregated, instances)
    with pytest.raises(AdapterValidationError, match="already present"):
        _add_resource_scope(*scoped)


# ----------------------------------------------------------------------
# Validity (B2)

STATUS_COLUMNS = ["cpu_validity_status", "memory_validity_status", "validity_status"]


def _validity(instance_rows, role_keys=("r1",), cap_mem=512.0):
    """Run B4 then B2; instance rows as in _b4_frames, all on one host."""
    roles, instances = _b4_frames(instance_rows, role_keys)
    instances["cap_mem"] = cap_mem
    roles = _aggregate_role_resources(roles, instances)
    return _assign_validity(roles, instances)


GOOD = ("r1", True, 50.0, 3.0, 4.0)


@pytest.mark.parametrize(
    "row, expected",
    [
        # (cpu, memory, row); one instance, so role and instance agree.
        (GOOD, ["valid", "valid", "valid"]),
        # No sensor row: nothing is populated.
        (("r1", False, None, None, None), ["partial", "partial", "partial"]),
        # CPU missing: CPU is not populated, so the row stays valid.
        (("r1", True, None, 3.0, 4.0), ["partial", "valid", "valid"]),
        # avg_mem missing: memory is still populated through peak_memory.
        (("r1", True, 50.0, None, 4.0), ["valid", "partial", "partial"]),
        (("r1", True, 50.0, 3.0, 600.0), ["valid", "invalid", "invalid"]),  # above cap_mem
        (("r1", True, 50.0, 5.0, 4.0), ["valid", "invalid", "invalid"]),  # peak < average
        (("r1", True, -1.0, 3.0, 4.0), ["invalid", "valid", "invalid"]),  # negative CPU
    ],
)
def test_validity_of_one_worker(row, expected):
    roles, instances = _validity([row])

    assert instances[STATUS_COLUMNS].iloc[0].tolist() == expected
    assert roles[STATUS_COLUMNS].iloc[0].tolist() == expected


def test_null_cap_mem_is_not_invalid():
    roles, _ = _validity([("r1", True, 50.0, 3.0, 9999.0)], cap_mem=None)

    assert roles[STATUS_COLUMNS].iloc[0].tolist() == ["valid", "valid", "valid"]


def test_role_rolls_up_its_instances():
    # r1: one invalid worker; r2: one worker without a sensor row; r3: none.
    roles, _ = _validity(
        [("r1", True, 50.0, 3.0, 600.0), GOOD,
         ("r2", False, None, None, None), ("r2", True, 50.0, 3.0, 4.0)],
        role_keys=("r1", "r2", "r3"),
    )

    assert roles[STATUS_COLUMNS].values.tolist() == [
        ["valid", "invalid", "invalid"],
        ["partial", "partial", "partial"],
        ["partial", "partial", "partial"],
    ]


def test_validity_ignores_exclusion_reason():
    roles, instances = _b4_frames([GOOD])
    instances["cap_mem"] = 512.0
    roles = _aggregate_role_resources(roles, instances).assign(
        exclusion_reason=pd.array(["job_failed"], dtype=TEXT))

    result, _ = _assign_validity(roles, instances)

    assert result["validity_status"].iloc[0] == "valid"


def test_validity_on_the_aggregated_fixture():
    _, prepared = prepare()
    roles, instances = _map_resources(prepared["roles"], prepared["instances"])
    roles = _aggregate_role_resources(roles, instances)

    roles, instances = _assign_validity(roles, instances)
    by_job = roles.set_index("job_name")

    # j1/worker: w1's two attempts are valid; slot b has no sensor row.
    assert by_job.loc["j1", STATUS_COLUMNS].tolist() == ["partial", "partial", "partial"]
    assert by_job.loc["j2", STATUS_COLUMNS].tolist() == ["partial", "partial", "partial"]
    assert instances.loc[instances["worker_name"] == "w1", "validity_status"].eq("valid").all()


def test_validity_columns_are_complete_strings_and_inputs_unchanged():
    roles, instances = _b4_frames([GOOD, ("r1", False, None, None, None)])
    instances["cap_mem"] = 512.0
    roles = _aggregate_role_resources(roles, instances)
    before = roles.copy(), instances.copy()

    result_roles, result_instances = _assign_validity(roles, instances)

    for frame in (result_roles, result_instances):
        for column in STATUS_COLUMNS:
            assert frame[column].dtype == TEXT and frame[column].notna().all()
    pd.testing.assert_frame_equal(roles, before[0])
    pd.testing.assert_frame_equal(instances, before[1])
    with pytest.raises(AdapterValidationError, match="already present"):
        _assign_validity(result_roles, result_instances)


# ----------------------------------------------------------------------
# View assembly (B5)

PROVENANCE = {
    "source_version": "cluster-trace-gpu-v2020",
    "source_files": {"pai_job_table": "pai_job_table.csv"},
    "source_checksums": {"pai_job_table": "sha256:0"},
    "telemetry_window": {"description": "fixture"},
}


def _adapt(sources=None):
    return AlibabaGPU2020Adapter().adapt_sources(
        sources or make_sources(), primary_view="role_occurrence", provenance=PROVENANCE)


def test_adapt_sources_builds_both_views():
    result = _adapt()
    roles, instances = result.views["role_occurrence"], result.views["instance"]

    assert result.primary_view == "role_occurrence"
    assert result.canonical is roles
    assert list(roles.columns) == ROLE_VIEW_COLUMNS
    assert list(instances.columns) == INSTANCE_VIEW_COLUMNS
    assert (len(roles), len(instances)) == (2, 4)
    assert roles[["schema_version", "dataset_id", "record_level"]].iloc[0].tolist() == [
        "0.2.0", "alibaba_gpu_v2020", "role_occurrence"]
    assert instances["record_level"].eq("instance").all()


def test_views_keep_only_contract_fields():
    result = _adapt()
    roles, instances = result.views["role_occurrence"], result.views["instance"]

    # Requests stay on roles; working columns never reach a view.
    assert not {"requested_cpu", "requested_memory", "requested_gpu"} & set(instances.columns)
    for frame in (roles, instances):
        assert not {"is_rejected", "has_sensor", "plan_cpu", "cpu_usage", "job_status"} & set(frame.columns)
    assert roles[["execution_id", "instance_id"]].isna().all(axis=None)
    assert instances["exclusion_reason"].isna().all()
    assert instances["exclusion_reason"].dtype == TEXT
    assert roles["source_job_status"].eq("Terminated").all()


def test_views_hold_accepted_rows_only():
    result = _adapt(_sources_with_rejected_j1())
    roles, instances = result.views["role_occurrence"], result.views["instance"]

    assert roles["job_name"].tolist() == ["j2"]
    assert instances["job_name"].eq("j2").all()
    rejected_roles = result.rejected.loc[
        result.rejected["rejection_level"] == "role_occurrence", "role_key"]
    assert not set(rejected_roles) & set(roles["role_key"])


def test_rejected_output_keeps_values_with_nullable_dtypes():
    _, prepared = prepare(_sources_with_rejected_j1())

    rejected = _adapt(_sources_with_rejected_j1()).rejected

    assert not (rejected.dtypes == object).any()
    assert rejected["has_sensor"].dtype == "boolean"
    assert rejected["source_row_number"].dtype == "Int64"
    # Same values as Part A's rejected frame; only the dtypes changed.
    pd.testing.assert_frame_equal(
        rejected.astype(object).where(rejected.notna(), None),
        prepared["rejected"].astype(object).where(prepared["rejected"].notna(), None),
        check_dtype=False,
    )


# ----------------------------------------------------------------------
# Metadata (B6)


def test_metadata_takes_join_coverage_from_the_adapter():
    adapter = AlibabaGPU2020Adapter()
    result = adapter.adapt_sources(
        make_sources(), primary_view="role_occurrence", provenance=PROVENANCE)

    coverage = result.metadata["join_coverage_counts"]
    assert coverage == adapter.join_coverage_counts
    assert set(coverage) == {"job_group_tag", "task_job", "instance_task",
                             "instance_sensor", "instance_machine_spec"}


def test_exclusion_counts_are_in_rule_order_with_zeros():
    counts = _adapt().metadata["exclusion_reason_counts"]

    assert list(counts) == [*ALIBABA_GPU_2020_EXCLUSION_REASONS, "<null>"]
    # j1/worker: instance_failed; j2: no_recurrence_key; none eligible.
    assert {reason: n for reason, n in counts.items() if n} == {
        "no_recurrence_key": 1, "instance_failed": 1}
    assert counts["<null>"] == 0


def test_eligibility_summary_on_the_fixture():
    summary = _adapt().metadata["eligibility_summary"]

    assert summary == {"accepted_roles": 2, "pass_all_but_multi_attempt_worker": 0,
                       "eligible": 0, "eligible_missing_cpu": 0}


def test_eligibility_summary_ignores_only_rule_10():
    # Rule 10 alone: passes "all but rule 10", but is not eligible.
    roles, instances = _b1_frames(None, [SAME_WORKER, SAME_WORKER])
    failed = _failed_rules(roles, instances)
    roles = _assign_exclusion_reasons(roles, instances, failed).assign(observed_cpu=50.0)

    assert _eligibility_summary(roles, failed) == {
        "accepted_roles": 1, "pass_all_but_multi_attempt_worker": 1,
        "eligible": 0, "eligible_missing_cpu": 0}


def test_caller_supplied_join_coverage_raises():
    with pytest.raises(AdapterValidationError, match="come from the adapter"):
        AlibabaGPU2020Adapter().adapt_sources(
            make_sources(), primary_view="role_occurrence",
            provenance={**PROVENANCE, "join_coverage_counts": {"x": {}}})


def test_metadata_before_preparation_raises():
    with pytest.raises(AdapterValidationError, match="prepare_sources"):
        AlibabaGPU2020Adapter().build_multiview_metadata(
            sources={}, views={}, rejected=pd.DataFrame(),
            primary_view="role_occurrence", provenance=PROVENANCE)
