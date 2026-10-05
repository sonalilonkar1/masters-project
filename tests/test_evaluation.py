import numpy as np
import pandas as pd
import pytest

from evaluation.evaluator import RecommendationEvaluator
from evaluation.metrics import (
    any_resource_violation,
    bounded_utilization,
    cpu_violation,
    memory_violation,
    shortfall,
    waste,
)


def test_bounded_utilization():
    result = bounded_utilization(
        actual=[2, 5, 4],
        recommended=[4, 4, 4],
    )

    expected = np.array([0.5, 1.0, 1.0])

    np.testing.assert_allclose(result, expected)


def test_zero_recommendation_returns_nan():
    result = bounded_utilization(
        actual=[0, 2],
        recommended=[0, 0],
    )

    assert np.isnan(result[0])
    assert np.isnan(result[1])


def test_any_resource_violation():
    result = any_resource_violation(
        actual_cpu=[2, 5, 2],
        recommended_cpu=[4, 4, 4],
        actual_memory=[2, 2, 8],
        recommended_memory=[4, 4, 4],
    )

    expected = np.array([False, True, True])

    np.testing.assert_array_equal(result, expected)


def test_equal_actual_and_recommended_is_not_a_violation():
    cpu_result = cpu_violation(
        actual_cpu=[4],
        recommended_cpu=[4],
    )

    memory_result = memory_violation(
        actual_memory=[8],
        recommended_memory=[8],
    )

    assert not bool(cpu_result[0])
    assert not bool(memory_result[0])


def test_cpu_only_violation():
    result = any_resource_violation(
        actual_cpu=[5],
        recommended_cpu=[4],
        actual_memory=[2],
        recommended_memory=[4],
    )

    np.testing.assert_array_equal(
        result,
        np.array([True]),
    )


def test_memory_only_violation():
    result = any_resource_violation(
        actual_cpu=[2],
        recommended_cpu=[4],
        actual_memory=[8],
        recommended_memory=[4],
    )

    np.testing.assert_array_equal(
        result,
        np.array([True]),
    )


def test_zero_recommendation_can_still_be_a_violation():
    result = cpu_violation(
        actual_cpu=[2],
        recommended_cpu=[0],
    )

    assert bool(result[0])


def test_zero_recommendation_is_included_in_violation_summary():
    data = pd.DataFrame(
        {
            "peak_cpu": [2, 1],
            "peak_memory": [1, 1],
            "recommended_cpu": [0, 2],
            "recommended_memory": [2, 2],
        }
    )

    evaluator = RecommendationEvaluator()

    evaluated = evaluator.evaluate(
        data=data,
        actual_cpu_col="peak_cpu",
        actual_memory_col="peak_memory",
        recommended_cpu_col="recommended_cpu",
        recommended_memory_col="recommended_memory",
    )

    summary = evaluator.summarize(evaluated)

    assert np.isclose(
        summary["cpu_violation_pct"],
        50.0,
    )

    assert np.isclose(
        summary["average_cpu_utilization"],
        0.5,
    )


def test_evaluator_rejects_missing_required_columns():
    data = pd.DataFrame(
        {
            "actual_cpu": [2],
            "actual_memory": [4],
            "recommended_cpu": [4],
        }
    )

    evaluator = RecommendationEvaluator()

    with pytest.raises(ValueError, match="missing"):
        evaluator.evaluate(
            data=data,
            actual_cpu_col="actual_cpu",
            actual_memory_col="actual_memory",
            recommended_cpu_col="recommended_cpu",
            recommended_memory_col="recommended_memory",
        )


def test_waste():
    result = waste(
        actual=[6, 12, 10],
        recommended=[10, 10, 10],
    )

    expected = np.array([4, 0, 0])

    np.testing.assert_array_equal(result, expected)


def test_shortfall():
    result = shortfall(
        actual=[6, 12, 10],
        recommended=[10, 10, 10],
    )

    expected = np.array([0, 2, 0])

    np.testing.assert_array_equal(result, expected)


def test_evaluator_returns_standard_metric_columns():
    data = pd.DataFrame(
        {
            "execution_id": ["e1", "e2", "e3"],
            "recurrence_key": ["r1", "r1", "r2"],
            "peak_cpu": [2, 5, 4],
            "peak_memory": [4, 8, 2],
            "recommended_cpu": [4, 4, 4],
            "recommended_memory": [8, 4, 4],
        }
    )

    evaluator = RecommendationEvaluator()

    result = evaluator.evaluate(
        data=data,
        actual_cpu_col="peak_cpu",
        actual_memory_col="peak_memory",
        recommended_cpu_col="recommended_cpu",
        recommended_memory_col="recommended_memory",
        policy_name="P95",
        id_cols=["execution_id", "recurrence_key"],
    )

    expected_columns = [
        "cpu_violation",
        "memory_violation",
        "any_resource_violation",
        "cpu_utilization",
        "memory_utilization",
        "cpu_waste",
        "memory_waste",
        "cpu_shortfall",
        "memory_shortfall",
        "policy_name",
    ]

    for column in expected_columns:
        assert column in result.columns

    assert result["policy_name"].eq("P95").all()
    assert result["execution_id"].tolist() == ["e1", "e2", "e3"]


def test_evaluator_summary():
    data = pd.DataFrame(
        {
            "peak_cpu": [2, 5, 4],
            "peak_memory": [4, 8, 2],
            "recommended_cpu": [4, 4, 4],
            "recommended_memory": [8, 4, 4],
        }
    )

    evaluator = RecommendationEvaluator()

    evaluated = evaluator.evaluate(
        data=data,
        actual_cpu_col="peak_cpu",
        actual_memory_col="peak_memory",
        recommended_cpu_col="recommended_cpu",
        recommended_memory_col="recommended_memory",
    )

    summary = evaluator.summarize(evaluated)

    assert np.isclose(
        summary["cpu_violation_pct"],
        (1 / 3) * 100,
    )

    assert np.isclose(
        summary["memory_violation_pct"],
        (1 / 3) * 100,
    )

    assert np.isclose(
        summary["any_resource_violation_pct"],
        (1 / 3) * 100,
    )

    assert np.isclose(
        summary["average_cpu_utilization"],
        np.mean([0.5, 1.0, 1.0]),
    )


def test_nonfinite_values_return_unknown_violation():
    cpu_result = cpu_violation(
        actual_cpu=[np.nan, 2, np.inf],
        recommended_cpu=[4, np.nan, 4],
    )

    memory_result = memory_violation(
        actual_memory=[np.nan, 2, 8],
        recommended_memory=[4, 4, np.inf],
    )

    assert np.isnan(cpu_result[0])
    assert np.isnan(cpu_result[1])
    assert np.isnan(cpu_result[2])

    assert np.isnan(memory_result[0])
    assert not np.isnan(memory_result[1])
    assert np.isnan(memory_result[2])


def test_any_resource_violation_preserves_unknown_state():
    result = any_resource_violation(
        actual_cpu=[np.nan, 2, 5, 2],
        recommended_cpu=[4, 4, 4, 4],
        actual_memory=[2, np.nan, np.nan, 2],
        recommended_memory=[4, 4, 4, 4],
    )

    assert np.isnan(result[0])
    assert np.isnan(result[1])
    assert result[2] == 1.0
    assert result[3] == 0.0


def test_summary_returns_valid_denominator_counts():
    data = pd.DataFrame(
        {
            "peak_cpu": [np.nan, 5, 1, 2],
            "peak_memory": [1, np.nan, 1, 1],
            "recommended_cpu": [4, 4, 2, 0],
            "recommended_memory": [2, 2, 2, 2],
        }
    )

    evaluator = RecommendationEvaluator()

    evaluated = evaluator.evaluate(
        data=data,
        actual_cpu_col="peak_cpu",
        actual_memory_col="peak_memory",
        recommended_cpu_col="recommended_cpu",
        recommended_memory_col="recommended_memory",
    )

    summary = evaluator.summarize(evaluated)

    assert summary["row_count"] == 4
    assert summary["valid_cpu_violation_count"] == 3
    assert summary["valid_memory_violation_count"] == 3
    assert summary["valid_any_resource_violation_count"] == 3
    assert summary["valid_cpu_utilization_count"] == 2
    assert summary["valid_memory_utilization_count"] == 3

    assert np.isclose(
        summary["cpu_violation_pct"],
        (2 / 3) * 100,
    )

    assert np.isclose(
        summary["any_resource_violation_pct"],
        (2 / 3) * 100,
    )


def test_nonfinite_recommendation_is_not_counted_as_non_violation():
    data = pd.DataFrame(
        {
            "peak_cpu": [2, 5],
            "peak_memory": [1, 1],
            "recommended_cpu": [np.nan, 4],
            "recommended_memory": [2, 2],
        }
    )

    evaluator = RecommendationEvaluator()

    evaluated = evaluator.evaluate(
        data=data,
        actual_cpu_col="peak_cpu",
        actual_memory_col="peak_memory",
        recommended_cpu_col="recommended_cpu",
        recommended_memory_col="recommended_memory",
    )

    summary = evaluator.summarize(evaluated)

    assert summary["valid_cpu_violation_count"] == 1
    assert summary["cpu_violation_pct"] == 100.0