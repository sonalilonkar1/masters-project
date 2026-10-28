"""Task 6 Alibaba GPU 2020 baseline tests.

Synthetic fixtures only; no source data or generated datasets required. Task 4
rows are produced with build_targets(make_roles(...)) so the tests exercise the
real derived schema (splits, history counts, next-occurrence targets, units).
"""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from canonical.schema import ALIBABA_GPU_2020_CAPABILITIES as PROFILE
from evaluation.evaluator import RecommendationEvaluator
from features.target_builder import build_targets

from test_target_builder import make_roles

import baselines.alibaba_gpu_2020 as a6


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def task4_rows(n=60, inst_num=1):
    """Build Task 4-style rows with the columns Task 6 and the evaluator need."""
    source = make_roles(n)
    # Canonical columns the evaluator/sensitivity use that make_roles omits.
    source["workload_id"] = "wl-" + source["recurrence_key"].astype(str)
    source["inst_num"] = inst_num
    return build_targets(source, PROFILE).rows


def hand_rows(**columns):
    """A minimal eligible-rows frame for unit-testing recommendation logic."""
    base = {
        "dataset_id": PROFILE.dataset_id,
        "exclusion_reason": pd.Series([pd.NA], dtype="string"),
        "requested_cpu": 100.0,
        "requested_memory": 8.0,
    }
    base.update(columns)
    return pd.DataFrame(base)


# ---------------------------------------------------------------------------
# History statistics
# ---------------------------------------------------------------------------

def test_history_counts_equal_task4_counts():
    rows = task4_rows(60)
    stats = a6.compute_history_statistics(rows, PROFILE)
    merged = rows.merge(stats, on="role_key", how="left")
    assert merged["hist_cpu_count"].astype("int64").equals(
        merged["cpu_history_count"].astype("int64")
    )
    assert merged["hist_memory_count"].astype("int64").equals(
        merged["memory_history_count"].astype("int64")
    )


def test_attach_history_statistics_rejects_count_mismatch():
    rows = task4_rows(30)
    stats = a6.compute_history_statistics(rows, PROFILE)
    stats.loc[stats.index[5], "hist_memory_count"] += 1  # corrupt one count
    with pytest.raises(ValueError, match="history count disagrees"):
        a6.attach_history_statistics(rows, stats)


def test_cpu_uses_observed_cpu_and_memory_uses_peak_memory():
    # make_roles: observed_cpu = index+10, peak_memory = index+1, one recurrence.
    rows = task4_rows(10)
    stats = a6.compute_history_statistics(rows, PROFILE)
    # Row 5 sees completed predecessors 0..4 (end at start-ish); counts == 5.
    row5 = stats.loc["role005"]
    assert row5["hist_cpu_count"] == 5
    # CPU history values are observed_cpu of rows 0..4 = [10,11,12,13,14].
    assert row5["hist_cpu_mean"] == pytest.approx(12.0)
    # Memory history values are peak_memory of rows 0..4 = [1,2,3,4,5].
    assert row5["hist_memory_mean"] == pytest.approx(3.0)
    assert row5["hist_memory_p95"] == pytest.approx(np.percentile([1, 2, 3, 4, 5], 95))


def test_empty_history_yields_nan_statistics():
    rows = task4_rows(10)
    stats = a6.compute_history_statistics(rows, PROFILE)
    first = stats.loc["role000"]  # no predecessors
    assert first["hist_cpu_count"] == 0
    assert np.isnan(first["hist_cpu_mean"])
    assert np.isnan(first["hist_memory_p99"])


# ---------------------------------------------------------------------------
# Baseline recommendations and fallback
# ---------------------------------------------------------------------------

def test_request_policy_equals_canonical_requests():
    rows = hand_rows(
        role_key=["r0"],
        hist_cpu_count=[5], hist_cpu_mean=[20.0], hist_cpu_p90=[30.0], hist_cpu_p95=[33.0], hist_cpu_p99=[35.0],
        hist_memory_count=[5], hist_memory_mean=[4.0], hist_memory_p90=[6.0], hist_memory_p95=[6.5], hist_memory_p99=[7.0],
    )
    out = a6.add_baseline_recommendations(rows, min_runs=1)
    assert out["rec_cpu_request"].iloc[0] == 100.0
    assert out["rec_memory_request"].iloc[0] == 8.0


def test_below_min_runs_falls_back_to_request_per_resource():
    rows = hand_rows(
        role_key=["r0"],
        hist_cpu_count=[2], hist_cpu_mean=[20.0], hist_cpu_p90=[30.0], hist_cpu_p95=[33.0], hist_cpu_p99=[35.0],
        hist_memory_count=[9], hist_memory_mean=[4.0], hist_memory_p90=[6.0], hist_memory_p95=[6.5], hist_memory_p99=[7.0],
    )
    out = a6.add_baseline_recommendations(rows, min_runs=5)
    # CPU count 2 < 5 -> fall back to request; memory count 9 >= 5 -> use history.
    assert out["rec_cpu_p95"].iloc[0] == 100.0
    assert out["uses_history_cpu_p95"].iloc[0] == False  # noqa: E712
    assert out["rec_memory_p95"].iloc[0] == 6.5
    assert out["uses_history_memory_p95"].iloc[0] == True  # noqa: E712


def test_null_statistic_triggers_request_fallback():
    rows = hand_rows(
        role_key=["r0"],
        hist_cpu_count=[9], hist_cpu_mean=[np.nan], hist_cpu_p90=[np.nan], hist_cpu_p95=[np.nan], hist_cpu_p99=[np.nan],
        hist_memory_count=[9], hist_memory_mean=[4.0], hist_memory_p90=[6.0], hist_memory_p95=[6.5], hist_memory_p99=[7.0],
    )
    out = a6.add_baseline_recommendations(rows, min_runs=1)
    assert out["rec_cpu_mean"].iloc[0] == 100.0  # null stat -> request
    assert out["rec_memory_mean"].iloc[0] == 4.0


def test_missing_cpu_never_changes_memory_recommendation():
    # CPU history absent, memory present: memory recs must be unaffected.
    rows = hand_rows(
        role_key=["r0"],
        hist_cpu_count=[0], hist_cpu_mean=[np.nan], hist_cpu_p90=[np.nan], hist_cpu_p95=[np.nan], hist_cpu_p99=[np.nan],
        hist_memory_count=[6], hist_memory_mean=[4.0], hist_memory_p90=[6.0], hist_memory_p95=[6.5], hist_memory_p99=[7.0],
    )
    out = a6.add_baseline_recommendations(rows, min_runs=3)
    assert out["rec_cpu_p95"].iloc[0] == 100.0  # CPU fell back
    assert out["rec_memory_p95"].iloc[0] == 6.5  # memory used history


def test_missing_request_on_eligible_row_is_input_error():
    rows = hand_rows(
        role_key=["r0"],
        requested_memory=[np.nan],
        hist_cpu_count=[5], hist_cpu_mean=[20.0], hist_cpu_p90=[30.0], hist_cpu_p95=[33.0], hist_cpu_p99=[35.0],
        hist_memory_count=[5], hist_memory_mean=[4.0], hist_memory_p90=[6.0], hist_memory_p95=[6.5], hist_memory_p99=[7.0],
    )
    with pytest.raises(ValueError, match="missing requested_memory"):
        a6.add_baseline_recommendations(rows, min_runs=1)


# ---------------------------------------------------------------------------
# Evaluation: profile semantics
# ---------------------------------------------------------------------------

def test_evaluation_reports_average_cpu_memory_primary_and_no_any_resource():
    rows = task4_rows(60)
    stats = a6.compute_history_statistics(rows, PROFILE)
    common = a6.freeze_common_validation_population(rows)
    with_stats = a6.attach_history_statistics(common, stats)
    recommended = a6.add_baseline_recommendations(with_stats, min_runs=1)

    evaluator = RecommendationEvaluator(capabilities=PROFILE)
    evaluated = a6.evaluate_policy(recommended, "P95", evaluator)
    summary = evaluator.summarize(evaluated)
    metadata = evaluator.summary_metadata(evaluated)

    assert "any_resource_violation_pct" not in summary
    assert "any_resource_violation" not in evaluated.columns
    assert metadata["cpu_result_semantics"] == "average_usage"
    assert metadata["primary_resource"] == "memory"
    assert metadata["any_resource_metric_reported"] is False
    assert (evaluated["cpu_usage_label"] == "average_usage").all()


def test_recommendation_units_and_scope_match_profile():
    rows = task4_rows(60)
    stats = a6.compute_history_statistics(rows, PROFILE)
    selection = a6.BaselineSelection("P95", 1, a6.SELECTION_SORT_ORDER, {}, 0)
    locked = a6.build_locked_recommendations(rows, stats, selection)
    assert (locked["recommended_cpu_unit"] == "percent_of_vcpu").all()
    assert (locked["recommended_memory_unit"] == "gb").all()
    assert (locked["recommended_resource_scope"] == "task_role_per_instance").all()


# ---------------------------------------------------------------------------
# Validation comparison, selection, determinism
# ---------------------------------------------------------------------------

def test_every_candidate_uses_the_same_validation_population():
    rows = task4_rows(80)
    stats = a6.compute_history_statistics(rows, PROFILE)
    common = a6.freeze_common_validation_population(rows)
    comparison = a6.build_validation_comparison(common, stats, PROFILE)
    # One row per policy x min_runs, and a constant evaluated population size.
    assert len(comparison) == len(a6.BASELINE_POLICIES) * len(a6.MIN_RUNS_CANDIDATES)
    assert comparison["row_count"].nunique() == 1
    assert comparison["row_count"].iloc[0] == len(common)


def test_selection_is_deterministic_and_memory_first():
    rows = task4_rows(80)
    stats = a6.compute_history_statistics(rows, PROFILE)
    common = a6.freeze_common_validation_population(rows)

    comparison_a = a6.build_validation_comparison(common, stats, PROFILE)
    comparison_b = a6.build_validation_comparison(common, stats, PROFILE)
    pd.testing.assert_frame_equal(comparison_a, comparison_b)

    selection_a = a6.select_baseline(comparison_a, validation_population_size=len(common))
    selection_b = a6.select_baseline(comparison_b, validation_population_size=len(common))
    assert selection_a == selection_b
    assert selection_a.selected_policy in a6.BASELINE_POLICIES
    assert selection_a.selected_min_runs in a6.MIN_RUNS_CANDIDATES
    assert selection_a.sort_order[0] == "memory_violation_pct"


def test_selection_sort_order_prefers_lower_memory_violation():
    comparison = pd.DataFrame([
        {"policy": "A", "min_runs": 1, "memory_violation_pct": 10.0, "average_memory_waste": 1.0,
         "cpu_violation_pct": 5.0, "average_cpu_waste": 1.0, "row_count": 100},
        {"policy": "B", "min_runs": 1, "memory_violation_pct": 2.0, "average_memory_waste": 9.0,
         "cpu_violation_pct": 50.0, "average_cpu_waste": 9.0, "row_count": 100},
    ])
    selection = a6.select_baseline(comparison)
    # B wins on memory violation despite worse waste and CPU.
    assert selection.selected_policy == "B"


def test_selection_ignores_candidates_without_a_valid_denominator():
    comparison = pd.DataFrame([
        {"policy": "NaNpolicy", "min_runs": 1, "memory_violation_pct": np.nan, "average_memory_waste": 0.0,
         "cpu_violation_pct": np.nan, "average_cpu_waste": 0.0, "row_count": 100},
        {"policy": "Real", "min_runs": 3, "memory_violation_pct": 7.0, "average_memory_waste": 2.0,
         "cpu_violation_pct": 3.0, "average_cpu_waste": 2.0, "row_count": 100},
    ])
    selection = a6.select_baseline(comparison)
    assert selection.selected_policy == "Real"


# ---------------------------------------------------------------------------
# Locked recommendations / leakage controls
# ---------------------------------------------------------------------------

def test_locked_recommendations_cover_all_policies_and_mark_selected():
    rows = task4_rows(60)
    stats = a6.compute_history_statistics(rows, PROFILE)
    selection = a6.BaselineSelection("P95", 3, a6.SELECTION_SORT_ORDER, {}, 0)
    locked = a6.build_locked_recommendations(rows, stats, selection)
    for policy in a6.BASELINE_POLICIES:
        cpu_col, mem_col = a6.recommendation_columns(policy)
        assert cpu_col in locked.columns and mem_col in locked.columns
    assert (locked["selected_baseline_policy"] == "P95").all()
    assert (locked["selected_min_runs"] == 3).all()
    assert locked["rec_cpu_selected"].equals(locked["rec_cpu_p95"])
    assert locked["rec_memory_selected"].equals(locked["rec_memory_p95"])


def test_locked_recommendations_do_not_require_or_produce_test_targets():
    # Simulate a column-selected test read: drop every target/status column.
    rows = task4_rows(60)
    stats = a6.compute_history_statistics(rows, PROFILE)
    test_like = rows.drop(columns=[
        "actual_cpu", "actual_memory", "actual_cpu_unit", "actual_memory_unit",
        "cpu_target_status", "memory_target_status",
    ])
    selection = a6.BaselineSelection("P95", 1, a6.SELECTION_SORT_ORDER, {}, 0)
    locked = a6.build_locked_recommendations(test_like, stats, selection)
    # No evaluator/metric columns are produced, and no target column reappears.
    for forbidden in ("cpu_violation", "memory_violation", "actual_cpu", "cpu_target_status"):
        assert forbidden not in locked.columns
    assert "rec_memory_selected" in locked.columns


# ---------------------------------------------------------------------------
# Sensitivity
# ---------------------------------------------------------------------------

def test_sensitivity_tables_are_reproducible_and_cover_expected_cuts():
    rows = task4_rows(80, inst_num=2)  # all multi-instance so the subgroup is non-empty
    stats = a6.compute_history_statistics(rows, PROFILE)
    common = a6.freeze_common_validation_population(rows)
    selection = a6.BaselineSelection("P95", 1, a6.SELECTION_SORT_ORDER, {}, len(common))

    table_a = a6.build_sensitivity_tables(common, stats, PROFILE, selection)
    table_b = a6.build_sensitivity_tables(common, stats, PROFILE, selection)
    pd.testing.assert_frame_equal(table_a, table_b)

    cuts = set(table_a["sensitivity"].unique())
    assert {"occurrence_weighted", "multi_instance", "group_weighted"} <= cuts
    assert (table_a["min_runs"] == 1).all()
    # group-weighted rows report a group count rather than evaluator denominators.
    group_rows = table_a[table_a["sensitivity"] == "group_weighted"]
    assert "n_groups" in group_rows.columns and group_rows["n_groups"].notna().any()
