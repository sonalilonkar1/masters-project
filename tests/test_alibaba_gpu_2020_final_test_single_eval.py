from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from canonical.schema import ALIBABA_GPU_2020_CAPABILITIES as PROFILE
from models import alibaba_gpu_2020_final_test as ft


class CountingEvaluator:
    def __init__(self):
        self.calls = 0

    def evaluate_canonical(self, frame):
        self.calls += 1
        result = frame.copy()
        # Minimal row-level columns used by summaries/sensitivities.
        result["cpu_violation"] = False
        result["memory_violation"] = False
        result["cpu_utilization"] = 1.0
        result["memory_utilization"] = 1.0
        result["cpu_waste"] = 0.0
        result["memory_waste"] = 0.0
        result["cpu_shortfall"] = 0.0
        result["memory_shortfall"] = 0.0
        return result


def test_all_final_policies_use_one_evaluator_call():
    rows = pd.DataFrame({
        "dataset_id": ["alibaba_gpu_v2020", "alibaba_gpu_v2020"],
        "workload_id": ["w1", "w2"],
        "role_key": ["r1", "r2"],
        "occurrence_id": ["o1", "o2"],
        "recurrence_key": ["k1", "k2"],
        "actual_cpu": [10.0, 20.0],
        "actual_memory": [1.0, 2.0],
        "actual_cpu_unit": ["percent_of_vcpu"] * 2,
        "actual_memory_unit": ["gb"] * 2,
        "next_occurrence_same_second": [False, True],
        "inst_num": [1, 2],
        "rec_cpu_request": [10.0, 20.0],
        "rec_memory_request": [1.0, 2.0],
        "rec_cpu_mean": [10.0, 20.0],
        "rec_memory_mean": [1.0, 2.0],
        "rec_cpu_p90": [10.0, 20.0],
        "rec_memory_p90": [1.0, 2.0],
        "rec_cpu_p95": [10.0, 20.0],
        "rec_memory_p95": [1.0, 2.0],
        "rec_cpu_p99": [10.0, 20.0],
        "rec_memory_p99": [1.0, 2.0],
        "ml_recommended_cpu": [10.0, 20.0],
        "ml_recommended_memory": [1.0, 2.0],
        "hybrid_recommended_cpu": [10.0, 20.0],
        "hybrid_recommended_memory": [1.0, 2.0],
    })

    evaluator = CountingEvaluator()
    evaluated = ft._evaluate_all_policies_once(rows, evaluator)

    assert evaluator.calls == 1
    assert len(evaluated) == len(rows) * len(ft.FINAL_POLICIES)
    assert tuple(evaluated["policy_name"].drop_duplicates()) == ft.FINAL_POLICIES



def test_execution_tracker_measures_and_rejects_second_evaluator_call():
    rows = pd.DataFrame({
        "dataset_id": ["alibaba_gpu_v2020"],
        "workload_id": ["w1"],
        "role_key": ["r1"],
        "occurrence_id": ["o1"],
        "recurrence_key": ["k1"],
        "actual_cpu": [10.0],
        "actual_memory": [1.0],
        "actual_cpu_unit": ["percent_of_vcpu"],
        "actual_memory_unit": ["gb"],
        "next_occurrence_same_second": [False],
        "inst_num": [1],
        "rec_cpu_request": [10.0],
        "rec_memory_request": [1.0],
        "rec_cpu_mean": [10.0],
        "rec_memory_mean": [1.0],
        "rec_cpu_p90": [10.0],
        "rec_memory_p90": [1.0],
        "rec_cpu_p95": [10.0],
        "rec_memory_p95": [1.0],
        "rec_cpu_p99": [10.0],
        "rec_memory_p99": [1.0],
        "ml_recommended_cpu": [10.0],
        "ml_recommended_memory": [1.0],
        "hybrid_recommended_cpu": [10.0],
        "hybrid_recommended_memory": [1.0],
    })
    tracker = ft.FinalTestExecutionTracker()
    evaluator = CountingEvaluator()
    ft._evaluate_all_policies_once(rows, evaluator, execution_tracker=tracker)
    assert tracker.evaluator_call_count == 1
    with pytest.raises(RuntimeError, match="more than once"):
        ft._evaluate_all_policies_once(rows, evaluator, execution_tracker=tracker)
    assert evaluator.calls == 1


def test_single_evaluation_preserves_policy_and_sensitivity_results():
    rows = pd.DataFrame({
        "dataset_id": ["alibaba_gpu_v2020"] * 4,
        "workload_id": ["g1", "g1", "g2", "g2"],
        "role_key": ["r1", "r2", "r3", "r4"],
        "occurrence_id": ["o1", "o2", "o3", "o4"],
        "recurrence_key": ["k1", "k2", "k3", "k4"],
        "actual_cpu": [8.0, 20.0, 12.0, 40.0],
        "actual_memory": [1.0, 2.0, 3.0, 4.0],
        "actual_cpu_unit": ["percent_of_vcpu"] * 4,
        "actual_memory_unit": ["gb"] * 4,
        "next_occurrence_same_second": [False, True, False, True],
        "inst_num": [1, 2, 3, 1],
        "rec_cpu_request": [10.0, 18.0, 14.0, 38.0],
        "rec_memory_request": [1.1, 2.1, 2.8, 4.1],
        "rec_cpu_mean": [9.0, 19.0, 13.0, 39.0],
        "rec_memory_mean": [1.0, 2.0, 3.2, 3.8],
        "rec_cpu_p90": [10.0, 21.0, 13.0, 41.0],
        "rec_memory_p90": [1.2, 2.2, 3.1, 4.2],
        "rec_cpu_p95": [11.0, 22.0, 14.0, 42.0],
        "rec_memory_p95": [1.3, 2.3, 3.3, 4.3],
        "rec_cpu_p99": [12.0, 23.0, 15.0, 43.0],
        "rec_memory_p99": [1.4, 2.4, 3.4, 4.4],
        "ml_recommended_cpu": [8.5, 20.5, 11.5, 39.5],
        "ml_recommended_memory": [0.9, 2.1, 2.9, 4.0],
        "hybrid_recommended_cpu": [12.0, 23.0, 15.0, 43.0],
        "hybrid_recommended_memory": [1.4, 2.4, 3.4, 4.4],
    })

    evaluator = ft.RecommendationEvaluator(capabilities=PROFILE)
    tracker = ft.FinalTestExecutionTracker()
    evaluated = ft._evaluate_all_policies_once(
        rows,
        evaluator,
        execution_tracker=tracker,
    )
    one_pass_comparison = ft.build_final_comparison_from_evaluated(
        evaluated,
        evaluator,
    )
    one_pass_sensitivity = ft.build_final_sensitivity_from_evaluated(
        evaluated,
        evaluator,
    )

    legacy_comparison = pd.DataFrame([
        ft._score_policy(
            rows,
            policy,
            ft.RecommendationEvaluator(capabilities=PROFILE),
        )
        for policy in ft.FINAL_POLICIES
    ])
    legacy_sensitivity = ft.build_final_sensitivity(rows, PROFILE)

    pd.testing.assert_frame_equal(
        one_pass_comparison.reset_index(drop=True),
        legacy_comparison.reset_index(drop=True),
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )
    pd.testing.assert_frame_equal(
        one_pass_sensitivity.reset_index(drop=True),
        legacy_sensitivity.reset_index(drop=True),
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )
    assert tracker.evaluator_call_count == 1
