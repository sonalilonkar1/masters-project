"""
Shared evaluator for comparing actual and recommended resources.

This evaluator supports different datasets and recommendation policies
without depending on dataset-specific identifier columns.
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
    Apply shared resource metrics to actual and recommended resources.
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

        The input DataFrame is not modified.
        """
        required_columns = [
            actual_cpu_col,
            actual_memory_col,
            recommended_cpu_col,
            recommended_memory_col,
        ]

        if id_cols is not None:
            required_columns.extend(id_cols)

        required_columns = list(dict.fromkeys(required_columns))

        missing_columns = [
            column
            for column in required_columns
            if column not in data.columns
        ]

        if missing_columns:
            raise ValueError(
                "The following required columns are missing: "
                f"{missing_columns}"
            )

        evaluated = data.copy()

        actual_cpu = evaluated[actual_cpu_col]
        actual_memory = evaluated[actual_memory_col]
        recommended_cpu = evaluated[recommended_cpu_col]
        recommended_memory = evaluated[recommended_memory_col]

        evaluated["cpu_violation"] = cpu_violation(
            actual_cpu,
            recommended_cpu,
        )

        evaluated["memory_violation"] = memory_violation(
            actual_memory,
            recommended_memory,
        )

        evaluated["any_resource_violation"] = (
            any_resource_violation(
                actual_cpu,
                recommended_cpu,
                actual_memory,
                recommended_memory,
            )
        )

        evaluated["cpu_utilization"] = cpu_utilization(
            actual_cpu,
            recommended_cpu,
            epsilon=self.epsilon,
        )

        evaluated["memory_utilization"] = memory_utilization(
            actual_memory,
            recommended_memory,
            epsilon=self.epsilon,
        )

        evaluated["cpu_waste"] = waste(
            actual_cpu,
            recommended_cpu,
        )

        evaluated["memory_waste"] = waste(
            actual_memory,
            recommended_memory,
        )

        evaluated["cpu_shortfall"] = shortfall(
            actual_cpu,
            recommended_cpu,
        )

        evaluated["memory_shortfall"] = shortfall(
            actual_memory,
            recommended_memory,
        )

        if policy_name is not None:
            evaluated["policy_name"] = policy_name

        return evaluated

    def summarize(
        self,
        evaluated_data: pd.DataFrame,
    ) -> dict[str, float | int]:
        """
        Calculate summary metrics from row-level evaluation results.

        Invalid violation results are excluded from violation denominators.
        Undefined utilization results are excluded from utilization
        denominators.
        """
        valid_cpu_violation_rows = (
            evaluated_data["cpu_violation"].notna()
        )

        valid_memory_violation_rows = (
            evaluated_data["memory_violation"].notna()
        )

        valid_any_resource_violation_rows = (
            evaluated_data["any_resource_violation"].notna()
        )

        valid_cpu_utilization_rows = (
            evaluated_data["cpu_utilization"].notna()
        )

        valid_memory_utilization_rows = (
            evaluated_data["memory_utilization"].notna()
        )

        valid_cpu_violation_count = int(
            valid_cpu_violation_rows.sum()
        )

        valid_memory_violation_count = int(
            valid_memory_violation_rows.sum()
        )

        valid_any_resource_violation_count = int(
            valid_any_resource_violation_rows.sum()
        )

        valid_cpu_utilization_count = int(
            valid_cpu_utilization_rows.sum()
        )

        valid_memory_utilization_count = int(
            valid_memory_utilization_rows.sum()
        )

        cpu_violation_pct = (
            evaluated_data.loc[
                valid_cpu_violation_rows,
                "cpu_violation",
            ].mean()
            * 100
            if valid_cpu_violation_count > 0
            else np.nan
        )

        memory_violation_pct = (
            evaluated_data.loc[
                valid_memory_violation_rows,
                "memory_violation",
            ].mean()
            * 100
            if valid_memory_violation_count > 0
            else np.nan
        )

        any_resource_violation_pct = (
            evaluated_data.loc[
                valid_any_resource_violation_rows,
                "any_resource_violation",
            ].mean()
            * 100
            if valid_any_resource_violation_count > 0
            else np.nan
        )

        average_cpu_utilization = (
            evaluated_data.loc[
                valid_cpu_utilization_rows,
                "cpu_utilization",
            ].mean()
            if valid_cpu_utilization_count > 0
            else np.nan
        )

        average_memory_utilization = (
            evaluated_data.loc[
                valid_memory_utilization_rows,
                "memory_utilization",
            ].mean()
            if valid_memory_utilization_count > 0
            else np.nan
        )

        return {
            "row_count": len(evaluated_data),

            "valid_cpu_violation_count": (
                valid_cpu_violation_count
            ),
            "valid_memory_violation_count": (
                valid_memory_violation_count
            ),
            "valid_any_resource_violation_count": (
                valid_any_resource_violation_count
            ),
            "valid_cpu_utilization_count": (
                valid_cpu_utilization_count
            ),
            "valid_memory_utilization_count": (
                valid_memory_utilization_count
            ),

            "cpu_violation_pct": cpu_violation_pct,
            "memory_violation_pct": memory_violation_pct,
            "any_resource_violation_pct": (
                any_resource_violation_pct
            ),
            "average_cpu_utilization": (
                average_cpu_utilization
            ),
            "average_memory_utilization": (
                average_memory_utilization
            ),
            "average_cpu_waste": (
                evaluated_data["cpu_waste"].mean()
            ),
            "average_memory_waste": (
                evaluated_data["memory_waste"].mean()
            ),
            "average_cpu_shortfall": (
                evaluated_data["cpu_shortfall"].mean()
            ),
            "average_memory_shortfall": (
                evaluated_data["memory_shortfall"].mean()
            ),
        }