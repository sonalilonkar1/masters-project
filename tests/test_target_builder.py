"""Task 4 synthetic contracts; no source data or generated datasets required."""

from dataclasses import replace
import json

import numpy as np
import pandas as pd
import pytest

from canonical.schema import ALIBABA_GPU_2020_CAPABILITIES as PROFILE, TARGET_STATUSES
from features.target_builder import DERIVED_COLUMNS, build_targets, write_target_tables


def make_roles(n=20):
    # One recurring role, submitted every two seconds and completed after one.
    # Increasing resource values make the source of each target easy to identify.
    # With 20 distinct timestamps, default splits are rows 0–13, 14–16, 17–19.
    return pd.DataFrame({
        "dataset_id": PROFILE.dataset_id,
        "record_level": "role_occurrence",
        "role_key": [f"role{i:03}" for i in range(n)],
        "occurrence_id": [f"job{i:03}" for i in range(n)],
        "recurrence_key": "group||worker",
        "start_time_us": pd.Series(np.arange(n) * 2_000_000, dtype="Int64"),
        "end_time_us": pd.Series(np.arange(n) * 2_000_000 + 1_000_000, dtype="Int64"),
        "exclusion_reason": pd.Series(pd.NA, index=range(n), dtype="string"),
        "observed_cpu": pd.Series(np.arange(n) + 10, dtype="Float64"),
        "peak_memory": pd.Series(np.arange(n) + 1, dtype="Float64"),
        "cpu_validity_status": "valid", "memory_validity_status": "valid",
        "requested_cpu": 100.0, "requested_memory": 8.0, "gpu_type": "T4",
    })


def unsupported(resource):
    # Alibaba supports both targets, so a synthetic profile exercises the fifth
    # status. Disable all related capability flags consistently with the schema.
    return replace(PROFILE, **{
        f"supports_{resource}": False, f"supports_observed_{resource}": False,
        f"has_{resource}_average": False, f"has_{resource}_peak": False,
        f"{resource}_target_semantics": None,
    })


def test_split_defaults_metadata_and_input_preservation():
    # Unique timestamps permit exact fractions; compare both input mutation and
    # preservation of canonical columns in the returned frame.
    source = make_roles(100)
    before = source.copy(deep=True)
    result = build_targets(source, PROFILE)
    pd.testing.assert_frame_equal(source, before)
    pd.testing.assert_frame_equal(result.rows[source.columns], source)
    assert result.rows["split"].value_counts().to_dict() == {
        "train": 70, "validation": 15, "test": 15}
    assert "_split" not in result.rows
    assert "val" not in result.rows["split"].unique()
    assert result.metadata["split"]["validation_rows"] == 15
    assert result.metadata["eligible_rows"] == 100
    assert result.metadata["excluded_rows"] == 0
    assert "c2ae87f" not in json.dumps(result.metadata)
    assert "source_provenance" not in result.metadata
    json.dumps(result.metadata)
    for split, meta in result.metadata["per_split"].items():
        part = result.rows.loc[result.rows["split"].eq(split)]
        assert len(part) == meta["rows"]
        for resource in ("cpu", "memory"):
            counts = meta[f"{resource}_status_counts"]
            assert set(counts) == TARGET_STATUSES
            assert sum(counts.values()) == len(part)
            assert counts["available"] == part[f"actual_{resource}"].notna().sum()
    assert result.metadata["split"]["train_end"] < result.metadata["split"]["validation_start"]
    assert result.metadata["split"]["validation_end"] < result.metadata["split"]["test_start"]


@pytest.mark.parametrize("commit", ["c2ae87f4aa357384a3cc8bdc72f776f1012c3ab7", "a" * 40])
def test_explicit_source_metadata_controls_provenance_without_changing_results(commit, tmp_path):
    # The caller supplies metadata only after checking the input artifact's
    # manifest. These fixture identities test the API without reading Task 3 data.
    source_metadata = {
        "dataset_id": PROFILE.dataset_id, "primary_view": "role_occurrence",
        "build": {"code_commit": commit, "code_dirty": False},
    }
    source = make_roles()
    baseline = build_targets(source, PROFILE)
    result = build_targets(source, PROFILE, verified_source_metadata=source_metadata)
    pd.testing.assert_frame_equal(result.rows, baseline.rows)
    expected_metadata = dict(baseline.metadata)
    expected_metadata.update({
        "source_provenance": source_metadata,
        "results_documentation": result.metadata["results_documentation"],
    })
    assert result.metadata == expected_metadata
    assert f"data built from {commit[:7]}" in result.metadata["results_documentation"]
    if not commit.startswith("c2ae87f"):
        assert "c2ae87f" not in json.dumps(result.metadata)
    # Preserve explicit provenance when writing, without retaining mutable input.
    source_metadata["build"]["code_commit"] = "b" * 40
    assert result.metadata["source_provenance"]["build"]["code_commit"] == commit
    written = write_target_tables(result, tmp_path / "targets")
    assert written["source_provenance"] == result.metadata["source_provenance"]
    assert json.loads((tmp_path / "targets" / "metadata.json").read_text()) == written


@pytest.mark.parametrize("updates,message", [
    ({"dataset_id": "other"}, "dataset_id"),
    ({"primary_view": "instance"}, "primary_view"),
    ({"build": None}, "build block"),
    ({"build": {}}, "code_commit"),
    ({"build": {"code_commit": "c2ae87f", "code_dirty": False}}, "code_commit"),
    ({"build": {"code_commit": "z" * 40, "code_dirty": False}}, "code_commit"),
    ({"build": {"code_commit": "a" * 40}}, "code_dirty"),
    ({"build": {"code_commit": "a" * 40, "code_dirty": True}}, "code_dirty"),
])
def test_incomplete_or_mismatched_source_metadata_is_rejected(updates, message):
    source_metadata = {
        "dataset_id": PROFILE.dataset_id, "primary_view": "role_occurrence",
        "build": {"code_commit": "a" * 40, "code_dirty": False},
        **updates,
    }
    with pytest.raises(ValueError, match=message):
        build_targets(make_roles(), PROFILE, verified_source_metadata=source_metadata)


def test_unknown_source_provenance_stays_unknown_when_written(tmp_path):
    result = build_targets(make_roles(), PROFILE)
    written = write_target_tables(result, tmp_path / "unknown")
    assert written["results_documentation"] == "Source provenance not supplied."
    assert "source_provenance" not in written
    assert "c2ae87f" not in json.dumps(written)


def test_all_roles_and_timestamp_groups_stay_in_one_split():
    source = make_roles(100)
    # Four rows per timestamp, comprising two jobs with two distinct roles each.
    # Both timestamp groups and whole jobs must survive boundary selection.
    source["start_time_us"] = (np.arange(100) // 4) * 2_000_000
    source["end_time_us"] = source["start_time_us"] + 1
    source["occurrence_id"] = [f"job{i // 2}" for i in range(100)]
    source["recurrence_key"] = [f"group||role{i % 2}" for i in range(100)]
    rows = build_targets(source, PROFILE).rows
    assert rows.groupby("start_time_us")["split"].nunique().eq(1).all()
    assert rows.groupby("occurrence_id")["split"].nunique().eq(1).all()


@pytest.mark.parametrize("resource,field,other", [
    ("cpu", "observed_cpu", "memory"), ("memory", "peak_memory", "cpu")])
@pytest.mark.parametrize("state", sorted(TARGET_STATUSES))
def test_all_five_statuses_independently(resource, field, other, state):
    # The parameter product checks every status for each resource while also
    # verifying that a resource-only problem leaves the other target available.
    source = make_roles()
    profile = PROFILE
    index = 0
    if state == "unsupported_resource":
        profile = unsupported(resource)
        source[field] = pd.NA
    elif state == "no_next_occurrence":
        source.loc[0, "recurrence_key"] = "singleton"
    elif state == "next_occurrence_in_other_split":
        index = 13
        # Missing value must not override the cross-split status.
        source.loc[14, field] = pd.NA
    elif state == "next_occurrence_ineligible_resource":
        source.loc[1, field] = pd.NA
    rows = build_targets(source, profile).rows
    assert rows.loc[index, f"{resource}_target_status"] == state
    assert pd.notna(rows.loc[index, f"actual_{resource}"]) == (state == "available")
    expected_other = state if state in {"no_next_occurrence", "next_occurrence_in_other_split"} else "available"
    assert rows.loc[index, f"{other}_target_status"] == expected_other
    for r in ("cpu", "memory"):
        assert rows[f"actual_{r}"].notna().eq(rows[f"{r}_target_status"].eq("available")).all()


@pytest.mark.parametrize("resource,field", [("cpu", "observed_cpu"), ("memory", "peak_memory")])
@pytest.mark.parametrize("missing", [True, False])
def test_invalid_successor_never_skipped_and_current_value_does_not_gate_target(resource, field, missing):
    source = make_roles()
    # A -> B -> C: A cannot borrow C's usable value when B is missing/invalid.
    # B can still receive C as its target despite B's own observation problem.
    if missing:
        source.loc[1, field] = pd.NA
    else:
        source.loc[1, f"{resource}_validity_status"] = "invalid"
    rows = build_targets(source, PROFILE).rows
    assert rows.loc[0, f"{resource}_target_status"] == "next_occurrence_ineligible_resource"
    assert pd.isna(rows.loc[0, f"actual_{resource}"])
    assert rows.loc[1, f"actual_{resource}"] == source.loc[2, field]
    assert rows.loc[2, f"{resource}_history_count"] == 1


def test_excluded_rows_have_no_derived_values_and_never_contribute():
    source = make_roles()
    # An excluded row with an extreme value and an early timestamp would visibly
    # affect targets, history, or boundaries if it entered any calculation.
    source.loc[1, "exclusion_reason"] = "job_failed"
    source.loc[1, ["observed_cpu", "peak_memory"]] = 9999
    source.loc[1, "start_time_us"] = -500_000_000
    source.loc[1, "end_time_us"] = -499_000_000
    rows = build_targets(source, PROFILE).rows
    assert rows.loc[1, list(DERIVED_COLUMNS)].isna().all()
    assert rows.loc[0, "actual_cpu"] == source.loc[2, "observed_cpu"]
    assert rows.loc[2, "cpu_history_count"] == 1
    assert 9999 not in rows["actual_cpu"].dropna().values
    eligible_only = build_targets(source.drop(index=1), PROFILE).rows
    pd.testing.assert_frame_equal(rows.drop(index=1), eligible_only)


def test_history_completion_boundary_nulls_overlap_and_resource_independence():
    source = make_roles()
    # At row 3's submission: row 0 is still running, row 1 has just completed,
    # and row 2 has no known completion. Only row 1's memory is usable history.
    source.loc[0, "end_time_us"] = source.loc[3, "start_time_us"] + 1
    source.loc[1, "end_time_us"] = source.loc[3, "start_time_us"]
    source.loc[2, "end_time_us"] = pd.NA
    source.loc[1, "observed_cpu"] = pd.NA
    rows = build_targets(source, PROFILE).rows
    assert rows.loc[3, "cpu_history_count"] == 0
    assert rows.loc[3, "memory_history_count"] == 1
    assert rows.loc[4, "cpu_history_count"] == 2  # rows 0 and 3
    assert rows.loc[4, "memory_history_count"] == 3


@pytest.mark.parametrize("resource,field", [("cpu", "observed_cpu"), ("memory", "peak_memory")])
def test_populated_partial_values_are_usable(resource, field):
    source = make_roles()
    source.loc[1, f"{resource}_validity_status"] = "partial"
    source["validity_status"] = "invalid"  # row-level status cannot gate resources
    rows = build_targets(source, PROFILE).rows
    assert rows.loc[0, f"actual_{resource}"] == source.loc[1, field]
    assert rows.loc[2, f"{resource}_history_count"] == 2


def test_history_crosses_earlier_splits_but_targets_do_not():
    # Counts accumulate across boundaries because earlier completed runs are
    # known at submission; labels cannot use a successor from the next split.
    rows = build_targets(make_roles(), PROFILE).rows
    assert rows.loc[14, "split"] == "validation"
    assert rows.loc[17, "split"] == "test"
    for r in ("cpu", "memory"):
        assert rows.loc[14, f"{r}_history_count"] == 14
        assert rows.loc[15, f"{r}_history_count"] == 15
        assert rows.loc[17, f"{r}_history_count"] == 17
        for boundary in (13, 16):
            assert rows.loc[boundary, f"{r}_target_status"] == "next_occurrence_in_other_split"
            assert pd.isna(rows.loc[boundary, f"actual_{r}"])
    open_rows = build_targets(make_roles(), replace(PROFILE, target_split_isolation=False)).rows
    assert open_rows.loc[13, "actual_cpu"] == 24
    assert open_rows.loc[16, "actual_memory"] == 18


def test_deterministic_ties_indexes_and_zero_duration_predecessors():
    source = make_roles()
    # Identical start/end times force tie-breaking by occurrence_id, then
    # role_key: row 2 precedes row 1, which precedes row 0.
    source.loc[:2, "start_time_us"] = 0
    source.loc[:2, "end_time_us"] = 0
    source.loc[:2, "occurrence_id"] = ["b", "a", "a"]
    source.loc[:2, "role_key"] = ["z", "y", "x"]
    result = build_targets(source, PROFILE)
    rows = result.rows
    assert rows.loc[2, "actual_cpu"] == source.loc[1, "observed_cpu"]
    assert rows.loc[1, "actual_cpu"] == source.loc[0, "observed_cpu"]
    assert rows.loc[2, "cpu_history_count"] == 0
    assert rows.loc[1, "cpu_history_count"] == 1
    assert rows.loc[0, "cpu_history_count"] == 2
    # Input order and duplicate index labels must not change identity-based
    # results or metadata; compare frames using the unique role_key instead.
    shuffled = source.sample(frac=1, random_state=81)
    shuffled.index = [7] * len(shuffled)
    other = build_targets(shuffled, PROFILE)
    pd.testing.assert_frame_equal(rows.set_index("role_key").sort_index(),
                                  other.rows.set_index("role_key").sort_index())
    assert result.metadata == other.metadata


def test_same_second_uses_buckets_and_keeps_missing_resource_targets():
    source = make_roles()
    # The first three starts share second 0. The last pair crosses into second 1
    # despite being just one microsecond apart, so that pair must not be flagged.
    source.loc[:3, "start_time_us"] = [100_000, 800_000, 999_999, 1_000_000]
    source.loc[:3, "end_time_us"] = source.loc[:3, "start_time_us"]
    source.loc[1, "observed_cpu"] = pd.NA
    result = build_targets(source, PROFILE)
    assert result.rows.loc[:3, "next_occurrence_same_second"].tolist() == [True, True, False, False]
    assert not result.rows.loc[19, "next_occurrence_same_second"]
    assert result.metadata["per_split"]["train"]["same_second_successor_rows"] == 2
    assert result.metadata["per_split"]["train"]["same_second_available_cpu_targets"] == 1
    assert result.metadata["per_split"]["train"]["same_second_available_memory_targets"] == 2
    assert len(result.rows) == len(source)


def test_successor_timestamp_shift_preserves_integer_precision():
    source = make_roles()
    # Above 2**53, a float shift could round the final microsecond of this second
    # into the next one and incorrectly clear the same-second flag.
    source["start_time_us"] += 9_007_199_254_000_000
    source["end_time_us"] = source["start_time_us"]
    source.loc[1, "start_time_us"] = 9_007_199_254_999_999
    source.loc[1, "end_time_us"] = source.loc[1, "start_time_us"]
    rows = build_targets(source, PROFILE).rows
    assert rows.loc[0, "next_occurrence_same_second"]


def test_null_adapter_placeholders_are_replaced_without_changing_input():
    source = make_roles()
    for column in DERIVED_COLUMNS:
        source[column] = pd.NA
    rows = build_targets(source, PROFILE).rows
    assert rows.loc[0, "actual_cpu"] == 11
    assert source[list(DERIVED_COLUMNS)].isna().all().all()


def test_group_isolation_and_history_against_independent_brute_force_oracle():
    source = make_roles(100)
    # Reproducible overlaps, missing values, invalid resources, and exclusions
    # exercise multiple recurrence groups without depending on real artifacts.
    rng = np.random.default_rng(81)
    source["recurrence_key"] = [f"group{i % 4}||role{i % 3}" for i in range(100)]
    source["end_time_us"] += rng.integers(0, 40_000_000, size=100)
    source.loc[::11, "end_time_us"] = pd.NA
    source.loc[::7, "observed_cpu"] = pd.NA
    source.loc[::9, "memory_validity_status"] = "invalid"
    source.loc[::13, "exclusion_reason"] = "job_failed"
    result = build_targets(source.sample(frac=1, random_state=9), PROFILE).rows
    eligible = source.loc[source["exclusion_reason"].isna()].sort_values(
        ["start_time_us", "occurrence_id", "role_key"])
    # The deliberately simple reference scans every predecessor rather than
    # reproducing the production heap algorithm, so it can catch sweep errors.
    previous = []
    for index, current in eligible.iterrows():
        for resource, field in (("cpu", "observed_cpu"), ("memory", "peak_memory")):
            expected = sum(
                prior["recurrence_key"] == current["recurrence_key"]
                and pd.notna(prior["end_time_us"])
                and prior["end_time_us"] <= current["start_time_us"]
                and pd.notna(prior[field]) and prior[f"{resource}_validity_status"] != "invalid"
                for prior in previous)
            assert result.loc[index, f"{resource}_history_count"] == expected
        previous.append(current)


def test_later_split_measurements_cannot_change_earlier_features_or_targets():
    source = make_roles(100)
    baseline = build_targets(source, PROFILE).rows
    # Alter future outcomes without changing submission order or eligibility.
    # Any earlier output change would reveal dependence on those future values.
    for split, prior in (("validation", ["train"]), ("test", ["train", "validation"])):
        changed = source.copy()
        future = baseline["split"].eq(split)
        changed.loc[future, ["observed_cpu", "peak_memory"]] = 10000
        changed.loc[future, "end_time_us"] += 100_000_000
        rebuilt = build_targets(changed, PROFILE).rows
        before = baseline["split"].isin(prior)
        pd.testing.assert_frame_equal(baseline.loc[before], rebuilt.loc[before])


@pytest.mark.parametrize("mutation,message", [
    (lambda x: x.drop(columns="recurrence_key"), "Missing required"),
    (lambda x: x.assign(record_level="instance"), "record_level"),
    (lambda x: x.assign(record_level=pd.NA), "record_level"),
    (lambda x: x.assign(dataset_id="other"), "dataset_id"),
    (lambda x: x.assign(role_key="duplicate"), "unique"),
    (lambda x: x.assign(role_key=pd.NA), "non-null"),
    (lambda x: x.assign(recurrence_key=pd.NA), "recurrence_key"),
    (lambda x: x.assign(occurrence_id=pd.NA), "occurrence_id"),
    (lambda x: x.assign(start_time_us=pd.NA), "start_time_us"),
    (lambda x: x.assign(start_time_us=0.5), "integer microseconds"),
    (lambda x: x.assign(end_time_us=-1), "cannot precede"),
    (lambda x: x.assign(split="train"), "already populated"),
    (lambda x: x.assign(cpu_validity_status="unknown"), "validity_status"),
    (lambda x: x.assign(observed_cpu=np.inf), "finite"),
    (lambda x: x.assign(occurrence_id="one job"), "share start_time_us"),
])
def test_invalid_inputs_fail_clearly(mutation, message):
    with pytest.raises(ValueError, match=message):
        build_targets(mutation(make_roles()), PROFILE)


def test_mixed_excluded_audit_row_is_still_rejected():
    source = make_roles()
    source.loc[0, "record_level"] = "instance"
    source.loc[0, "exclusion_reason"] = "job_failed"
    with pytest.raises(ValueError, match="audit rows"):
        build_targets(source, PROFILE)


@pytest.mark.parametrize("n", [0, 1, 2])
def test_insufficient_eligible_rows(n):
    with pytest.raises(ValueError, match="At least 3 rows"):
        build_targets(make_roles(n), PROFILE)


def test_insufficient_eligible_timestamp_groups():
    with pytest.raises(ValueError, match="3 distinct timestamps"):
        build_targets(make_roles().assign(start_time_us=0), PROFILE)


def test_profile_level_and_capabilities_drive_behavior():
    with pytest.raises(ValueError, match="evaluation_record_level"):
        build_targets(make_roles(), replace(PROFILE, evaluation_record_level="occurrence"))
    with pytest.raises(ValueError, match="supports_recurrence"):
        build_targets(make_roles(), replace(PROFILE, supports_recurrence=False))
    rows = build_targets(make_roles(), replace(PROFILE, supports_targets=False)).rows
    assert rows["cpu_target_status"].eq("unsupported_resource").all()
    assert rows["memory_target_status"].eq("unsupported_resource").all()
    assert rows["actual_cpu"].isna().all()
    # A peak profile must use peak_cpu, not observed_cpu.
    source = make_roles().assign(peak_cpu=555.)
    peak = replace(PROFILE, has_cpu_peak=True, cpu_target_semantics="next_occurrence_peak")
    assert build_targets(source, peak).rows.loc[0, "actual_cpu"] == 555


def test_writer_round_trip_excluded_rows_paths_and_existing_destination(tmp_path):
    # All writes use pytest's temporary directory. The in-memory audit row stays
    # in the result, but the three persisted modeling tables contain only 19 rows.
    source = make_roles()
    source.loc[0, "exclusion_reason"] = "job_failed"
    result = build_targets(source, PROFILE)
    destination = tmp_path / "targets"
    metadata = write_target_tables(result, destination)
    assert sorted(p.name for p in destination.iterdir()) == [
        "metadata.json", "test.parquet", "train.parquet", "validation.parquet"]
    assert json.loads((destination / "metadata.json").read_text()) == metadata
    total = 0
    for split in ("train", "validation", "test"):
        part = pd.read_parquet(metadata["output_paths"][split])
        expected = result.rows.loc[result.rows["split"].eq(split)].reset_index(drop=True)
        pd.testing.assert_frame_equal(part, expected)
        assert part["exclusion_reason"].isna().all()
        total += len(part)
    assert total == 19
    assert result.metadata["output_paths"] == {}
    with pytest.raises(FileExistsError):
        write_target_tables(result, destination)


def test_writer_failure_does_not_publish_partial_tables(tmp_path, monkeypatch):
    result = build_targets(make_roles(), PROFILE)
    calls = 0
    real = pd.DataFrame.to_parquet

    # Fail after one successful Parquet write to check cleanup of a genuinely
    # partial staging directory, not just failure before any output exists.
    def fail_second(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated write failure")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "to_parquet", fail_second)
    with pytest.raises(OSError, match="simulated"):
        write_target_tables(result, tmp_path / "targets")
    assert list(tmp_path.iterdir()) == []
