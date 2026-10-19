import numpy as np
import pandas as pd
import pytest

from src.canonical.schema import (
    CanonicalSchemaError,
    GOOGLE_CAPABILITIES,
)

from dataclasses import replace

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

    for column in (
        "cpu_violation",
        "memory_violation",
        "any_resource_violation",
    ):
        np.testing.assert_array_equal(
            evaluated[column],
            [0, 1, 0],
        )

    np.testing.assert_allclose(
        evaluated["cpu_utilization"],
        [0.5, 1.0, 1.0],
    )
    np.testing.assert_allclose(
        evaluated["memory_utilization"],
        [0.5, 1.0, 0.5],
    )

    summary = evaluator.summarize(evaluated)

    expected_summary = {
        "row_count": 3,
        "valid_cpu_violation_count": 3,
        "valid_memory_violation_count": 3,
        "valid_any_resource_violation_count": 3,
        "valid_cpu_utilization_count": 3,
        "valid_memory_utilization_count": 3,
        "cpu_violation_pct": 100 / 3,
        "memory_violation_pct": 100 / 3,
        "any_resource_violation_pct": 100 / 3,
        "average_cpu_utilization": 5 / 6,
        "average_memory_utilization": 2 / 3,
        "average_cpu_waste": 2 / 3,
        "average_memory_waste": 2.0,
        "average_cpu_shortfall": 1 / 3,
        "average_memory_shortfall": 4 / 3,
    }

    for key, expected in expected_summary.items():
        assert key in summary
        assert np.isclose(summary[key], expected), key

def test_evaluator_does_not_modify_input():
    data = pd.DataFrame(
        {
            "execution_id": ["e1", "e2"],
            "peak_cpu": [2, 5],
            "peak_memory": [4, 8],
            "recommended_cpu": [4, 4],
            "recommended_memory": [8, 4],
        }
    )
    original = data.copy(deep=True)

    evaluator = RecommendationEvaluator()

    evaluated = evaluator.evaluate(
        data=data,
        actual_cpu_col="peak_cpu",
        actual_memory_col="peak_memory",
        recommended_cpu_col="recommended_cpu",
        recommended_memory_col="recommended_memory",
        policy_name="P95",
        id_cols=["execution_id"],
    )

    pd.testing.assert_frame_equal(data, original)
    assert evaluated["policy_name"].eq("P95").all()

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

def test_alibaba_gpu_suppresses_any_resource_metrics():
    from src.canonical.schema import ALIBABA_GPU_2020_CAPABILITIES

    # Synthetic rows include one non-violation and one violation per resource.
    data = pd.DataFrame(
        {
            "actual_cpu": [2, 5],
            "actual_memory": [4, 8],
            "recommended_cpu": [4, 4],
            "recommended_memory": [8, 4],
            # A stale combined metric must be removed from the output.
            "any_resource_violation": [1, 1],
        }
    )

    # This profile prohibits combining average CPU and peak memory results.
    evaluator = RecommendationEvaluator(
        capabilities=ALIBABA_GPU_2020_CAPABILITIES,
    )

    evaluated = evaluator.evaluate(
        data=data,
        actual_cpu_col="actual_cpu",
        actual_memory_col="actual_memory",
        recommended_cpu_col="recommended_cpu",
        recommended_memory_col="recommended_memory",
    )
    summary = evaluator.summarize(evaluated)

    # Suppression applies to row results, summary rates, and denominator counts.
    assert "any_resource_violation" not in evaluated.columns
    assert "any_resource_violation_pct" not in summary
    assert "valid_any_resource_violation_count" not in summary

    # Individual resource metrics must still be calculated.
    assert summary["cpu_violation_pct"] == 50.0
    assert summary["memory_violation_pct"] == 50.0
    
@pytest.fixture
def canonical_evaluation_data():
    """Synthetic Google-style input with explicit matching units."""
    return pd.DataFrame(
        {
            "dataset_id": ["google_clusterdata2019"],
            "workload_id": ["w1"],
            "policy_name": ["P95"],
            "actual_cpu": [2.0],
            "recommended_cpu": [4.0],
            "actual_cpu_unit": ["ncu"],
            "recommended_cpu_unit": ["ncu"],
            "actual_memory": [4.0],
            "recommended_memory": [8.0],
            "actual_memory_unit": ["normalized"],
            "recommended_memory_unit": ["normalized"],
            "resource_scope": ["full_workload"],
            "recommended_resource_scope": ["full_workload"],
        }
    )


def test_canonical_evaluation_accepts_valid_input(canonical_evaluation_data):
    evaluator = RecommendationEvaluator(
        capabilities=GOOGLE_CAPABILITIES,
    )

    evaluated = evaluator.evaluate_canonical(
        canonical_evaluation_data,
    )
    summary = evaluator.summarize(evaluated)

    assert evaluated["policy_name"].tolist() == ["P95"]
    assert summary["cpu_violation_pct"] == 0.0
    assert summary["memory_violation_pct"] == 0.0
    assert summary["any_resource_violation_pct"] == 0.0
    assert summary["average_cpu_utilization"] == 0.5
    assert summary["average_memory_utilization"] == 0.5
    assert "cpu_usage_label" not in evaluated.columns
    assert "cpu_usage_label" not in summary


@pytest.mark.parametrize(
    "unit,error",
    [
        ("vcpu", "units must match"),
        (None, "units must be populated"),
    ],
)
def test_canonical_evaluation_rejects_invalid_units(canonical_evaluation_data,unit,error):
    canonical_evaluation_data["recommended_cpu_unit"] = unit
    evaluator = RecommendationEvaluator(
        capabilities=GOOGLE_CAPABILITIES,
    )

    with pytest.raises(CanonicalSchemaError, match=error):
        evaluator.evaluate_canonical(canonical_evaluation_data)


def test_canonical_evaluation_requires_profile(canonical_evaluation_data):
    evaluator = RecommendationEvaluator()

    with pytest.raises(ValueError, match="capability profile"):
        evaluator.evaluate_canonical(canonical_evaluation_data)


def test_canonical_evaluation_rejects_wrong_dataset(canonical_evaluation_data):
    canonical_evaluation_data["dataset_id"] = "another_dataset"
    evaluator = RecommendationEvaluator(
        capabilities=GOOGLE_CAPABILITIES,
    )

    with pytest.raises(ValueError, match="dataset_id must match"):
        evaluator.evaluate_canonical(canonical_evaluation_data)

def test_canonical_evaluation_rejects_scope_mismatch(
    canonical_evaluation_data,
):
    # A per-instance recommendation cannot be scored against a workload total.
    canonical_evaluation_data["recommended_resource_scope"] = "instance"
    evaluator = RecommendationEvaluator(
        capabilities=GOOGLE_CAPABILITIES,
    )

    with pytest.raises(ValueError, match="scopes must match"):
        evaluator.evaluate_canonical(canonical_evaluation_data)


@pytest.mark.parametrize(
    "column",
    ["resource_scope", "recommended_resource_scope"],
)
def test_canonical_evaluation_requires_scope_columns(
    canonical_evaluation_data,
    column,
):
    data = canonical_evaluation_data.drop(columns=[column])
    evaluator = RecommendationEvaluator(
        capabilities=GOOGLE_CAPABILITIES,
    )

    with pytest.raises(ValueError, match=f"requires {column}"):
        evaluator.evaluate_canonical(data)


@pytest.mark.parametrize(
    "column",
    ["resource_scope", "recommended_resource_scope"],
)
@pytest.mark.parametrize("scope", [None, "unknown_scope"])
def test_canonical_evaluation_rejects_invalid_scope(
    canonical_evaluation_data,
    column,
    scope,
):
    canonical_evaluation_data[column] = scope
    evaluator = RecommendationEvaluator(
        capabilities=GOOGLE_CAPABILITIES,
    )

    with pytest.raises(
        ValueError,
        match="supported, non-null scope",
    ):
        evaluator.evaluate_canonical(canonical_evaluation_data)

def test_canonical_alibaba_cpu_results_are_labeled(
    canonical_evaluation_data,
):
    from src.canonical.schema import ALIBABA_GPU_2020_CAPABILITIES

    data = canonical_evaluation_data.copy(deep=True)
    data["dataset_id"] = ALIBABA_GPU_2020_CAPABILITIES.dataset_id

    # Alibaba CPU represents lifetime-average usage per role instance.
    data["actual_cpu_unit"] = "percent_of_vcpu"
    data["recommended_cpu_unit"] = "percent_of_vcpu"
    data["actual_memory_unit"] = "gb"
    data["recommended_memory_unit"] = "gb"
    data["resource_scope"] = "task_role_per_instance"
    data["recommended_resource_scope"] = "task_role_per_instance"

    evaluator = RecommendationEvaluator(
        capabilities=ALIBABA_GPU_2020_CAPABILITIES,
    )

    evaluated = evaluator.evaluate_canonical(data)
    summary = evaluator.summarize(evaluated)

    assert evaluated["cpu_usage_label"].eq("average_usage").all()
    assert summary["cpu_usage_label"] == "average_usage"

    # Labeling preserves the underlying metric calculation.
    assert summary["average_cpu_utilization"] == 0.5

    # The canonical path must also suppress combined resource metrics.
    assert "any_resource_violation" not in evaluated.columns
    assert "any_resource_violation_pct" not in summary
    
@pytest.mark.parametrize("resource", ["cpu", "memory"])
def test_canonical_evaluation_excludes_unsupported_resource(
    canonical_evaluation_data,
    resource,
):
    # Derive a synthetic profile with one unsupported resource.
    capabilities = replace(
        GOOGLE_CAPABILITIES,
        **{f"supports_{resource}": False},
    )
    evaluator = RecommendationEvaluator(
        capabilities=capabilities,
    )
    original = canonical_evaluation_data.copy(deep=True)

    evaluated = evaluator.evaluate_canonical(
        canonical_evaluation_data,
    )
    summary = evaluator.summarize(evaluated)

    # Unsupported values contribute to no resource metrics or denominators.
    for metric in (
        "violation",
        "utilization",
        "waste",
        "shortfall",
    ):
        assert evaluated[f"{resource}_{metric}"].isna().all()

    assert summary[f"valid_{resource}_violation_count"] == 0
    assert summary[f"valid_{resource}_utilization_count"] == 0
    assert np.isnan(summary[f"{resource}_violation_pct"])
    assert np.isnan(summary[f"average_{resource}_utilization"])
    assert np.isnan(summary[f"average_{resource}_waste"])
    assert np.isnan(summary[f"average_{resource}_shortfall"])

    # The other resource remains evaluable.
    other = "memory" if resource == "cpu" else "cpu"
    assert summary[f"valid_{other}_violation_count"] == 1
    assert summary[f"average_{other}_utilization"] == 0.5

    pd.testing.assert_frame_equal(
        canonical_evaluation_data,
        original,
    )


def test_canonical_evaluation_requires_a_supported_pair(
    canonical_evaluation_data,
):
    capabilities = replace(
        GOOGLE_CAPABILITIES,
        supports_memory=False,
    )
    data = canonical_evaluation_data.copy(deep=True)

    # Memory is unsupported, and CPU has no actual value.
    data["actual_cpu"] = np.nan
    evaluator = RecommendationEvaluator(
        capabilities=capabilities,
    )

    with pytest.raises(
        CanonicalSchemaError,
        match="at least one actual/recommendation pair",
    ):
        evaluator.evaluate_canonical(data)

@pytest.mark.parametrize("metric", [waste, shortfall])
def test_waste_and_shortfall_preserve_nonfinite_inputs(metric):
    actual = [np.nan, np.inf, -np.inf, 2, 2, 2]
    recommended = [4, 4, 4, np.nan, np.inf, -np.inf]

    # Invalid arithmetic must remain unknown without emitting warnings.
    with np.errstate(invalid="raise"):
        result = metric(actual, recommended)

    assert np.isnan(result).all()


def test_summary_excludes_nonfinite_waste_and_shortfall():
    data = pd.DataFrame(
        {
            "actual_cpu": [2, np.inf, 6, 2],
            "recommended_cpu": [4, 4, 4, np.inf],
            "actual_memory": [1, 1, 1, 1],
            "recommended_memory": [2, 2, 2, 2],
        }
    )
    evaluator = RecommendationEvaluator()

    evaluated = evaluator.evaluate(
        data=data,
        actual_cpu_col="actual_cpu",
        actual_memory_col="actual_memory",
        recommended_cpu_col="recommended_cpu",
        recommended_memory_col="recommended_memory",
    )
    summary = evaluator.summarize(evaluated)

    np.testing.assert_allclose(
        evaluated["cpu_waste"],
        [2, np.nan, 0, np.nan],
        equal_nan=True,
    )
    np.testing.assert_allclose(
        evaluated["cpu_shortfall"],
        [0, np.nan, 2, np.nan],
        equal_nan=True,
    )

    # Only the two finite CPU pairs contribute to these averages.
    assert summary["average_cpu_waste"] == 1.0
    assert summary["average_cpu_shortfall"] == 1.0