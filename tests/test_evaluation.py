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
    """
    Utilization should be actual / recommended,
    but it must not exceed 100%.
    """
    result = bounded_utilization(
        actual=[2, 5, 4],
        recommended=[4, 4, 4],
    )

    expected = np.array([0.5, 1.0, 1.0])

    np.testing.assert_allclose(result, expected)


def test_zero_recommendation_returns_nan():
    """
    A zero recommendation must not create infinity.
    """
    result = bounded_utilization(
        actual=[0, 2],
        recommended=[0, 0],
    )

    assert np.isnan(result[0])
    assert np.isnan(result[1])


def test_any_resource_violation():
    """
    Any-resource violation is true when either CPU or memory
    exceeds its recommendation.
    """
    result = any_resource_violation(
        actual_cpu=[2, 5, 2],
        recommended_cpu=[4, 4, 4],
        actual_memory=[2, 2, 8],
        recommended_memory=[4, 4, 4],
    )

    expected = np.array([False, True, True])

    np.testing.assert_array_equal(result, expected)


def test_equal_actual_and_recommended_is_not_a_violation():
    """
    Equal actual and recommended values do not count as violations.

    The rule is strictly:

        actual > recommended
    """
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
    """
    A CPU violation should be detected when memory is within
    its recommendation.
    """
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
    """
    A memory violation should be detected when CPU is within
    its recommendation.
    """
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
    """
    A zero recommendation is still a violation when actual usage
    is greater than zero.

    Utilization is undefined for zero recommendations, but the
    violation rule still applies.
    """
    result = cpu_violation(
        actual_cpu=[2],
        recommended_cpu=[0],
    )

    assert bool(result[0])


def test_zero_recommendation_is_included_in_violation_summary():
    """
    A zero recommendation should still count in the violation rate,
    while its utilization remains undefined.
    """
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

    # First row violates CPU: 2 > 0.
    # Second row does not: 1 <= 2.
    assert np.isclose(
        summary["cpu_violation_pct"],
        50.0,
    )

    # The first row has undefined utilization.
    # Only the second row contributes: 1 / 2 = 0.5.
    assert np.isclose(
        summary["average_cpu_utilization"],
        0.5,
    )


def test_evaluator_rejects_missing_required_columns():
    """
    The evaluator should clearly report missing required columns.
    """
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
    """
    Waste is positive only when the recommendation is larger
    than actual usage.
    """
    result = waste(
        actual=[6, 12, 10],
        recommended=[10, 10, 10],
    )

    expected = np.array([4, 0, 0])

    np.testing.assert_array_equal(result, expected)


def test_shortfall():
    """
    Shortfall is positive only when actual usage exceeds
    the recommendation.
    """
    result = shortfall(
        actual=[6, 12, 10],
        recommended=[10, 10, 10],
    )

    expected = np.array([0, 2, 0])

    np.testing.assert_array_equal(result, expected)


def test_evaluator_returns_standard_metric_columns():
    """
    The evaluator should return the same metric columns regardless
    of the recommendation method.
    """
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
    """
    Verify violation percentages and average utilization.
    """
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

    # One of three rows violated CPU.
    assert np.isclose(
        summary["cpu_violation_pct"],
        (1 / 3) * 100,
    )

    # One of three rows violated memory.
    assert np.isclose(
        summary["memory_violation_pct"],
        (1 / 3) * 100,
    )

    # One of three rows violated at least one resource.
    assert np.isclose(
        summary["any_resource_violation_pct"],
        (1 / 3) * 100,
    )

    # CPU utilization is [0.5, 1.0, 1.0].
    assert np.isclose(
        summary["average_cpu_utilization"],
        np.mean([0.5, 1.0, 1.0]),
    )