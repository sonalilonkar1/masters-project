from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from src.canonical.schema import (
    CanonicalSchemaError,
    GOOGLE_CAPABILITIES,
)
from evaluation.evaluator import RecommendationEvaluator
from evaluation.metrics import (
    any_resource_violation,
    bounded_utilization,
    cpu_violation,
    memory_violation,
    shortfall,
    waste,
)

@pytest.mark.parametrize("resource", ["cpu", "memory"])
def test_single_resource_evaluation(resource):
    data = pd.DataFrame(
        {
            "usage": [2.0, 5.0],
            "recommendation": [4.0, 4.0],
        }
    )
    evaluator = RecommendationEvaluator()

    evaluated = evaluator.evaluate(
        data,
        **{
            f"actual_{resource}_col": "usage",
            f"recommended_{resource}_col": "recommendation",
        },
    )
    summary = evaluator.summarize(evaluated)

    other = "memory" if resource == "cpu" else "cpu"

    np.testing.assert_array_equal(
        evaluated[f"{resource}_violation"],
        [0, 1],
    )
    assert summary[f"{resource}_violation_pct"] == 50.0
    assert summary[f"valid_{other}_violation_count"] == 0
    assert summary[f"valid_{other}_utilization_count"] == 0

    for metric in ("violation", "utilization", "waste", "shortfall"):
        assert evaluated[f"{other}_{metric}"].isna().all()

    assert "any_resource_violation" not in evaluated.columns
    assert "any_resource_violation_pct" not in summary
    assert "valid_any_resource_violation_count" not in summary
    assert not any(
        column.startswith("__unevaluated_")
        for column in evaluated.columns
    )


def test_evaluation_requires_a_resource_pair():
    with pytest.raises(ValueError, match="At least one"):
        RecommendationEvaluator().evaluate(pd.DataFrame())


@pytest.mark.parametrize("resource", ["cpu", "memory"])
def test_evaluation_rejects_incomplete_column_pair(resource):
    data = pd.DataFrame({"usage": [2.0]})

    with pytest.raises(ValueError, match="requires both"):
        RecommendationEvaluator().evaluate(
            data,
            **{f"actual_{resource}_col": "usage"},
        )
        
@pytest.mark.parametrize("resource", ["cpu", "memory"])
def test_profile_single_resource_with_null_canonical_columns(resource):
    from src.canonical.schema import GOOGLE_CAPABILITIES

    other = "memory" if resource == "cpu" else "cpu"

    data = pd.DataFrame(
        {
            "dataset_id": [GOOGLE_CAPABILITIES.dataset_id],
            "workload_id": ["w1"],
            "policy_name": ["synthetic"],
            "actual_cpu": [2.0],
            "recommended_cpu": [4.0],
            "actual_memory": [2.0],
            "recommended_memory": [4.0],
            "actual_cpu_unit": ["ncu"],
            "recommended_cpu_unit": ["ncu"],
            "actual_memory_unit": ["normalized"],
            "recommended_memory_unit": ["normalized"],
            "resource_scope": ["full_workload"],
            "recommended_resource_scope": ["full_workload"],
        }
    )
    data[f"actual_{other}"] = np.nan
    data[f"recommended_{other}"] = np.nan

    evaluator = RecommendationEvaluator(
        capabilities=GOOGLE_CAPABILITIES,
    )
    evaluated = evaluator.evaluate_canonical(data)
    summary = evaluator.summarize(evaluated)

    assert summary[f"valid_{resource}_violation_count"] == 1
    assert summary[f"valid_{other}_violation_count"] == 0
    assert "any_resource_violation" not in evaluated.columns
    assert "any_resource_violation_pct" not in summary
    assert "valid_any_resource_violation_count" not in summary

    # Canonical resource columns remain present and unevaluated values null.
    assert evaluated[f"actual_{other}"].isna().all()
    assert evaluated[f"recommended_{other}"].isna().all()

def test_evaluator_summary_regression():
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
    data["dataset_id"] = ALIBABA_GPU_2020_CAPABILITIES.dataset_id
    data["workload_id"] = ["w1", "w2"]
    data["policy_name"] = "synthetic"
    data["actual_cpu_unit"] = "percent_of_vcpu"
    data["recommended_cpu_unit"] = "percent_of_vcpu"
    data["actual_memory_unit"] = "gb"
    data["recommended_memory_unit"] = "gb"
    data["resource_scope"] = "task_role_per_instance"
    data["recommended_resource_scope"] = "task_role_per_instance"
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
def test_recommendation_scope_requires_actual_scope(
    canonical_evaluation_data,
    column,
):
    data = canonical_evaluation_data.drop(columns=[column])
    evaluator = RecommendationEvaluator(
        capabilities=GOOGLE_CAPABILITIES,
    )

    if column == "resource_scope":
        with pytest.raises(ValueError, match="resource_scope required"):
            evaluator.evaluate_canonical(data)
    else:
        # A shared resource_scope is sufficient for both values.
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
    assert evaluator.summary_metadata(evaluated)["cpu_result_semantics"] == "average_usage"

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


@pytest.mark.parametrize(
    "actual_unit,recommended_unit",
    [
        (None, "ncu"),
        ("ncu", None),
        (None, None),
    ],
)
def test_evaluator_rejects_missing_unit_values(
    actual_unit,
    recommended_unit,
):
    # CPU is evaluated; memory is unavailable for this synthetic row.
    frame = pd.DataFrame(
        {
            "dataset_id": ["google_clusterdata2019"],
            "workload_id": ["w1"],
            "policy_name": ["P95"],
            "actual_cpu": [2.0],
            "recommended_cpu": [4.0],
            "actual_cpu_unit": [actual_unit],
            "recommended_cpu_unit": [recommended_unit],
            "actual_memory": [None],
            "recommended_memory": [None],
        }
    )

    frame["resource_scope"] = "full_workload"
    frame["recommended_resource_scope"] = "full_workload"

    with pytest.raises(
        CanonicalSchemaError,
        match="units must be populated",
    ):
        RecommendationEvaluator(
            capabilities=GOOGLE_CAPABILITIES,
        ).evaluate_canonical(frame)


@pytest.mark.parametrize("entry_point", ["direct", "canonical"])
@pytest.mark.parametrize("resource,wrong_unit", [("cpu", "vcpu"), ("memory", "gb")])
def test_matching_units_must_also_match_profile(
    canonical_evaluation_data, entry_point, resource, wrong_unit,
):
    data = canonical_evaluation_data.copy()
    data[f"actual_{resource}_unit"] = wrong_unit
    data[f"recommended_{resource}_unit"] = wrong_unit
    evaluator = RecommendationEvaluator(capabilities=GOOGLE_CAPABILITIES)
    with pytest.raises(CanonicalSchemaError, match="must match profile unit"):
        if entry_point == "canonical":
            evaluator.evaluate_canonical(data)
        else:
            evaluator.evaluate(
                data,
                actual_cpu_col="actual_cpu",
                recommended_cpu_col="recommended_cpu",
                actual_memory_col="actual_memory",
                recommended_memory_col="recommended_memory",
            )


@pytest.mark.parametrize("missing_column", ["dataset_id", "workload_id", "policy_name"])
def test_direct_profile_evaluation_validates_canonical_identifiers(
    canonical_evaluation_data, missing_column,
):
    evaluator = RecommendationEvaluator(capabilities=GOOGLE_CAPABILITIES)
    data = canonical_evaluation_data.drop(columns=[missing_column])
    with pytest.raises(ValueError, match=missing_column):
        evaluator.evaluate(
            data,
            actual_cpu_col="actual_cpu",
            recommended_cpu_col="recommended_cpu",
            actual_memory_col="actual_memory",
            recommended_memory_col="recommended_memory",
        )


def test_direct_profile_evaluation_maps_selected_columns(canonical_evaluation_data):
    data = canonical_evaluation_data.rename(columns={
        "actual_cpu": "usage", "recommended_cpu": "allocation",
        "actual_cpu_unit": "usage_unit", "recommended_cpu_unit": "allocation_unit",
    })
    original = data.copy(deep=True)
    evaluator = RecommendationEvaluator(capabilities=GOOGLE_CAPABILITIES)
    evaluated = evaluator.evaluate(
        data, actual_cpu_col="usage", recommended_cpu_col="allocation",
    )
    assert evaluated["actual_cpu"].tolist() == [2.0]
    assert evaluated["recommended_cpu"].tolist() == [4.0]
    assert evaluated["actual_memory"].isna().all()
    assert evaluated["recommended_memory"].isna().all()
    assert "any_resource_violation" not in evaluated
    pd.testing.assert_frame_equal(data, original)


@pytest.mark.parametrize("resource", ["cpu", "memory"])
@pytest.mark.parametrize("kind", ["actual", "recommended"])
@pytest.mark.parametrize("selected_unit_valid", [True, False])
def test_selected_value_and_unit_override_canonical_pair(
    canonical_evaluation_data, resource, kind, selected_unit_valid,
):
    data = canonical_evaluation_data.copy(deep=True)
    canonical = f"{kind}_{resource}"
    profile_unit = getattr(GOOGLE_CAPABILITIES, f"{resource}_unit")
    data[canonical] = 99.0
    data[f"{canonical}_unit"] = "stale" if selected_unit_valid else profile_unit
    data["selected"] = 3.0
    data["selected_unit"] = profile_unit if selected_unit_valid else "invalid"
    original = data.copy(deep=True)
    columns = {
        f"actual_{resource}_col": f"actual_{resource}",
        f"recommended_{resource}_col": f"recommended_{resource}",
        f"{canonical}_col": "selected",
    }
    evaluator = RecommendationEvaluator(capabilities=GOOGLE_CAPABILITIES)

    if selected_unit_valid:
        evaluated = evaluator.evaluate(data, **columns)
        assert evaluated[canonical].tolist() == [3.0]
        assert evaluated[f"{canonical}_unit"].tolist() == [profile_unit]
    else:
        with pytest.raises(CanonicalSchemaError, match="units"):
            evaluator.evaluate(data, **columns)

    pd.testing.assert_frame_equal(data, original)


@pytest.mark.parametrize("entry_point", ["direct", "canonical"])
def test_profile_evaluation_accepts_absent_scope(canonical_evaluation_data, entry_point):
    data = canonical_evaluation_data.drop(
        columns=["resource_scope", "recommended_resource_scope"]
    )
    evaluator = RecommendationEvaluator(capabilities=GOOGLE_CAPABILITIES)
    if entry_point == "canonical":
        evaluated = evaluator.evaluate_canonical(data)
    else:
        evaluated = evaluator.evaluate(
            data, actual_cpu_col="actual_cpu", recommended_cpu_col="recommended_cpu",
            actual_memory_col="actual_memory", recommended_memory_col="recommended_memory",
        )
    assert evaluator.summarize(evaluated)["cpu_violation_pct"] == 0.0


def test_profile_evaluation_rejects_mixed_scopes(canonical_evaluation_data):
    data = pd.concat([canonical_evaluation_data] * 2, ignore_index=True)
    data.loc[1, "resource_scope"] = "instance"
    data.loc[1, "recommended_resource_scope"] = "instance"
    evaluator = RecommendationEvaluator(capabilities=GOOGLE_CAPABILITIES)
    with pytest.raises(ValueError, match="consistent scope"):
        evaluator.evaluate_canonical(data)


def test_profile_summary_metadata_is_separate(canonical_evaluation_data):
    evaluator = RecommendationEvaluator(capabilities=GOOGLE_CAPABILITIES)
    evaluated = evaluator.evaluate_canonical(canonical_evaluation_data)
    numeric = evaluator.summarize(evaluated)
    metadata = evaluator.summary_metadata(evaluated)
    assert all(isinstance(value, (int, float, np.number)) for value in numeric.values())
    assert metadata == {
        "dataset_id": GOOGLE_CAPABILITIES.dataset_id,
        "policy_name": "P95",
        "cpu_result_semantics": "peak_usage",
        "primary_resource": None,
        "evaluated_resources": ["cpu", "memory"],
        "unsupported_resources": [],
        "any_resource_metric_reported": True,
        "any_resource_suppression_reason": None,
    }
    for resource in ("cpu", "memory"):
        for metric in ("waste", "shortfall"):
            assert numeric[f"valid_{resource}_{metric}_count"] == 1


def test_alibaba_metadata_reports_memory_primary(canonical_evaluation_data):
    from src.canonical.schema import ALIBABA_GPU_2020_CAPABILITIES

    profile = ALIBABA_GPU_2020_CAPABILITIES
    data = canonical_evaluation_data.copy()
    data["dataset_id"] = profile.dataset_id
    for resource in ("cpu", "memory"):
        for kind in ("actual", "recommended"):
            data[f"{kind}_{resource}_unit"] = getattr(profile, f"{resource}_unit")
    evaluator = RecommendationEvaluator(capabilities=profile)
    evaluated = evaluator.evaluate_canonical(data)
    metadata = evaluator.summary_metadata(evaluated)
    assert metadata["primary_resource"] == "memory"
    assert metadata["cpu_result_semantics"] == "average_usage"
    assert metadata["any_resource_metric_reported"] is False
    assert metadata["any_resource_suppression_reason"] == "profile_disallows_any_resource"
    assert "cpu_usage_label" not in evaluator.summarize(evaluated)


@pytest.mark.parametrize("resource", ["cpu", "memory"])
def test_unsupported_resource_metadata_and_counts(canonical_evaluation_data, resource):
    profile = replace(GOOGLE_CAPABILITIES, **{f"supports_{resource}": False})
    evaluator = RecommendationEvaluator(capabilities=profile)
    evaluated = evaluator.evaluate_canonical(canonical_evaluation_data)
    numeric = evaluator.summarize(evaluated)
    metadata = evaluator.summary_metadata(evaluated)
    other = "memory" if resource == "cpu" else "cpu"
    assert metadata["unsupported_resources"] == [resource]
    assert metadata["evaluated_resources"] == [other]
    assert metadata["any_resource_metric_reported"] is False
    assert metadata["any_resource_suppression_reason"] == "single_resource_evaluation"
    assert numeric[f"valid_{resource}_waste_count"] == 0
    assert numeric[f"valid_{resource}_shortfall_count"] == 0


def test_profile_waste_counts_exclude_nonfinite_pairs(canonical_evaluation_data):
    data = pd.concat([canonical_evaluation_data] * 4, ignore_index=True)
    data["actual_cpu"] = [2.0, np.inf, -np.inf, np.nan]
    evaluator = RecommendationEvaluator(capabilities=GOOGLE_CAPABILITIES)
    summary = evaluator.summarize(evaluator.evaluate_canonical(data))
    assert summary["valid_cpu_waste_count"] == 1
    assert summary["valid_cpu_shortfall_count"] == 1
    assert summary["valid_memory_waste_count"] == 4
    assert summary["valid_memory_shortfall_count"] == 4


def test_average_cpu_label_uses_capability_flags(canonical_evaluation_data):
    # Target semantics alone must not determine whether CPU is peak-capable.
    profile = replace(
        GOOGLE_CAPABILITIES, has_cpu_average=True, has_cpu_peak=False,
    )
    evaluator = RecommendationEvaluator(capabilities=profile)
    evaluated = evaluator.evaluate_canonical(canonical_evaluation_data)
    assert evaluated["cpu_usage_label"].eq("average_usage").all()
    assert evaluator.summary_metadata(evaluated)["cpu_result_semantics"] == "average_usage"


def test_no_profile_summary_remains_numeric_only():
    evaluator = RecommendationEvaluator()
    data = pd.DataFrame({"actual": [2.0], "recommendation": [4.0]})
    evaluated = evaluator.evaluate(
        data, actual_cpu_col="actual", recommended_cpu_col="recommendation",
        actual_memory_col="actual", recommended_memory_col="recommendation",
    )
    summary = evaluator.summarize(evaluated)
    assert len(summary) == 15
    assert evaluator.summary_metadata(evaluated) == {}
    assert all(isinstance(value, (int, float, np.number)) for value in summary.values())
    assert not any(key.endswith(("waste_count", "shortfall_count")) for key in summary)
