from __future__ import annotations

import numpy as np
import pandas as pd

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
