"""
Shared evaluator for comparing actual and recommended resources.

This evaluator can be reused for:
- Request recommendations
- P95 recommendations
- ML recommendations
- Hybrid recommendations
- Google datasets
- Alibaba datasets
- Future datasets

The evaluator does not require execution_id or recurrence_key.
Those columns can be preserved through the optional id_cols argument.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from .metrics import (
    any_resource_violation,
    cpu_utilization,
    cpu_violation,
    memory_utilization,
    memory_violation,
    shortfall,
    waste,
)


class RecommendationEvaluator:
    """
    Apply the shared metrics to actual and recommended resources.

    The evaluator receives column names instead of assuming fixed dataset
    column names. This allows the same evaluator to work with Google,
    Alibaba, and other datasets.
    """

    def __init__(self, epsilon: float = 1e-12):
        """
        Create an evaluator.

        Args:
            epsilon: Smallest recommendation treated as valid for
                utilization calculations.
        """
        self.epsilon = epsilon

    def evaluate(
        self,
        data: pd.DataFrame,
        actual_cpu_col: str,
        actual_memory_col: str,
        recommended_cpu_col: str,
        recommended_memory_col: str,
        policy_name: str | None = None,
        id_cols: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """
        Calculate row-level evaluation metrics.

        Args:
            data: Input DataFrame containing actual and recommended values.
            actual_cpu_col: Column containing observed peak CPU.
            actual_memory_col: Column containing observed peak memory.
            recommended_cpu_col: Column containing recommended CPU.
            recommended_memory_col: Column containing recommended memory.
            policy_name: Optional name such as Request, P95, ML, or Hybrid.
            id_cols: Optional identifier columns to preserve, such as
                execution_id, recurrence_key, or evaluation_unit_id.

        Returns:
            A copy of the input DataFrame with standardized metric columns.
        """

        # Collect the columns required for evaluation.
        required_columns = [
            actual_cpu_col,
            actual_memory_col,
            recommended_cpu_col,
            recommended_memory_col,
        ]

        # Add optional identifier columns to the validation list.
        if id_cols is not None:
            required_columns.extend(id_cols)

        # Remove duplicate column names while preserving order.
        required_columns = list(dict.fromkeys(required_columns))

        # Stop early if any required column is missing.
        missing_columns = [
            column for column in required_columns if column not in data.columns
        ]

        if missing_columns:
            raise ValueError(
                "The following required columns are missing: "
                f"{missing_columns}"
            )

        # Copy the input so the original DataFrame is not modified.
        evaluated = data.copy()

        # Read the actual and recommended resource values.
        actual_cpu = evaluated[actual_cpu_col]
        actual_memory = evaluated[actual_memory_col]
        recommended_cpu = evaluated[recommended_cpu_col]
        recommended_memory = evaluated[recommended_memory_col]

        # Calculate CPU violation for every row.
        evaluated["cpu_violation"] = cpu_violation(
            actual_cpu,
            recommended_cpu,
        )

        # Calculate memory violation for every row.
        evaluated["memory_violation"] = memory_violation(
            actual_memory,
            recommended_memory,
        )

        # Calculate whether either CPU or memory was violated.
        evaluated["any_resource_violation"] = any_resource_violation(
            actual_cpu,
            recommended_cpu,
            actual_memory,
            recommended_memory,
        )

        # Calculate bounded CPU utilization.
        #
        # The result cannot exceed 1.0, which represents 100%.
        evaluated["cpu_utilization"] = cpu_utilization(
            actual_cpu,
            recommended_cpu,
            epsilon=self.epsilon,
        )

        # Calculate bounded memory utilization.
        evaluated["memory_utilization"] = memory_utilization(
            actual_memory,
            recommended_memory,
            epsilon=self.epsilon,
        )

        # Calculate unused recommended CPU capacity.
        evaluated["cpu_waste"] = waste(
            actual_cpu,
            recommended_cpu,
        )

        # Calculate unused recommended memory capacity.
        evaluated["memory_waste"] = waste(
            actual_memory,
            recommended_memory,
        )

        # Calculate CPU under-provisioning severity.
        evaluated["cpu_shortfall"] = shortfall(
            actual_cpu,
            recommended_cpu,
        )

        # Calculate memory under-provisioning severity.
        evaluated["memory_shortfall"] = shortfall(
            actual_memory,
            recommended_memory,
        )

        # Add the policy name when one is provided.
        #
        # Examples:
        # - Request
        # - P95
        # - ML
        # - Hybrid
        if policy_name is not None:
            evaluated["policy_name"] = policy_name

        # Return the original data together with standardized metrics.
        return evaluated

    def summarize(
        self,
        evaluated_data: pd.DataFrame,
    ) -> dict[str, float | int]:
        """
        Calculate summary metrics from row-level evaluation results.

        Violation percentages use only rows with valid actual and
        recommended values. Utilization averages exclude undefined
        zero-recommendation rows.
        """

        # Identify rows where CPU comparison is meaningful.
        valid_cpu_rows = (
            evaluated_data["cpu_violation"].notna()
            & evaluated_data["cpu_utilization"].notna()
        )

        # Identify rows where memory comparison is meaningful.
        valid_memory_rows = (
            evaluated_data["memory_violation"].notna()
            & evaluated_data["memory_utilization"].notna()
        )

        # Any-resource comparison requires both CPU and memory values.
        valid_any_resource_rows = valid_cpu_rows & valid_memory_rows

        # Calculate CPU violation percentage.
        cpu_violation_pct = (
            evaluated_data.loc[valid_cpu_rows, "cpu_violation"].mean() * 100
            if valid_cpu_rows.any()
            else np.nan
        )

        # Calculate memory violation percentage.
        memory_violation_pct = (
            evaluated_data.loc[
                valid_memory_rows,
                "memory_violation",
            ].mean()
            * 100
            if valid_memory_rows.any()
            else np.nan
        )

        # Calculate any-resource violation percentage.
        any_resource_violation_pct = (
            evaluated_data.loc[
                valid_any_resource_rows,
                "any_resource_violation",
            ].mean()
            * 100
            if valid_any_resource_rows.any()
            else np.nan
        )

        # Calculate average bounded CPU utilization.
        average_cpu_utilization = (
            evaluated_data.loc[
                valid_cpu_rows,
                "cpu_utilization",
            ].mean()
            if valid_cpu_rows.any()
            else np.nan
        )

        # Calculate average bounded memory utilization.
        average_memory_utilization = (
            evaluated_data.loc[
                valid_memory_rows,
                "memory_utilization",
            ].mean()
            if valid_memory_rows.any()
            else np.nan
        )

        # Return standardized summary names for every policy.
        return {
            "row_count": len(evaluated_data),
            "cpu_violation_pct": cpu_violation_pct,
            "memory_violation_pct": memory_violation_pct,
            "any_resource_violation_pct": any_resource_violation_pct,
            "average_cpu_utilization": average_cpu_utilization,
            "average_memory_utilization": average_memory_utilization,
            "average_cpu_waste": evaluated_data["cpu_waste"].mean(),
            "average_memory_waste": evaluated_data["memory_waste"].mean(),
            "average_cpu_shortfall": evaluated_data["cpu_shortfall"].mean(),
            "average_memory_shortfall": evaluated_data[
                "memory_shortfall"
            ].mean(),
        }