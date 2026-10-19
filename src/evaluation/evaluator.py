"""
Shared evaluator for comparing actual and recommended resources.

This evaluator supports different datasets and recommendation policies
without depending on dataset-specific identifier columns.
"""

from __future__ import annotations
from src.canonical.schema import (
    DatasetCapabilities,
    RESOURCE_SCOPES,
    validate_evaluator_view,
)
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

    def __init__(self, epsilon: float = 1e-12, capabilities: DatasetCapabilities | None = None,):
        """
        Create an evaluator.

        Args:
            epsilon: Smallest recommendation treated as valid for
                utilization calculations.
        
        Capabilities: Optional dataset profile controlling resource
                support, any-resource reporting, and CPU labeling.
                Required by evaluate_canonical().
        """
        self.epsilon = epsilon
        self.capabilities = capabilities
    
    @property
    def reports_any_resource(self) -> bool:
        return (
            self.capabilities is None
            or self.capabilities.any_resource_metric_valid
        )
    
    
    def _mask_unsupported_resources(
        self,
        data: pd.DataFrame,
        resource_columns: dict[str, tuple[str, str]],
    ) -> pd.DataFrame:
        """Exclude unsupported resource pairs without modifying the input."""
        masked = data.copy()

        if self.capabilities is None:
            return masked

        for resource, columns in resource_columns.items():
            supported = (
                getattr(self.capabilities, f"supports_{resource}")
                and getattr(
                    self.capabilities,
                    f"supports_observed_{resource}",
                )
            )
            if not supported:
                for column in columns:
                    if column in masked.columns:
                        masked[column] = np.nan
        return masked
    
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

        evaluated = self._mask_unsupported_resources(
            data,
            {
                "cpu": (actual_cpu_col, recommended_cpu_col),
                "memory": (actual_memory_col, recommended_memory_col),
            },
        )

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

        if self.reports_any_resource:
            evaluated["any_resource_violation"] = any_resource_violation(
                actual_cpu,
                recommended_cpu,
                actual_memory,
                recommended_memory,
            )
        else:
            evaluated = evaluated.drop(
                columns=["any_resource_violation"],
                errors="ignore",
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

        # Lifetime-average CPU results must not be presented as peak safety.
        if (
            self.capabilities is not None
            and self.capabilities.cpu_target_semantics
            == "next_occurrence_lifetime_average"
        ):
            evaluated["cpu_usage_label"] = "average_usage"
        return evaluated

    def summarize(
        self,
        evaluated_data: pd.DataFrame,
    ) -> dict[str, float | int | str]:
        """
        Calculate summary metrics from row-level evaluation results.

        Invalid violation results are excluded from violation denominators.
        Undefined utilization results are excluded from utilization
        denominators.
        
        Profile-dependent suppression and labels use this evaluator's
        capability profile, so use the same instance that evaluated the data.
        """
        valid_cpu_violation_rows = (
            evaluated_data["cpu_violation"].notna()
        )

        valid_memory_violation_rows = (
            evaluated_data["memory_violation"].notna()
        )

        valid_any_resource_violation_rows = (
            evaluated_data["any_resource_violation"].notna()
            if self.reports_any_resource
            else pd.Series(False, index=evaluated_data.index)
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
            if self.reports_any_resource
            and valid_any_resource_violation_count > 0
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

        summary = {
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
        if not self.reports_any_resource:
            summary.pop("valid_any_resource_violation_count")
            summary.pop("any_resource_violation_pct")

        if (
            self.capabilities is not None
            and self.capabilities.cpu_target_semantics
            == "next_occurrence_lifetime_average"
        ):
            summary["cpu_usage_label"] = "average_usage"
        
        return summary
    
    
    def evaluate_canonical(self,data: pd.DataFrame,) -> pd.DataFrame:
        """Validate and evaluate recommendations using a dataset profile.

        Requires a capability profile supplied to the constructor and these
        canonical columns:
            dataset_id, workload_id, policy_name,
            actual_cpu, actual_memory,
            recommended_cpu, recommended_memory,
            resource_scope, recommended_resource_scope.

        Each supported actual/recommendation pair requires matching,
        non-null actual_<resource>_unit and recommended_<resource>_unit
        values. Every row must contain at least one supported pair.

        resource_scope describes the actual values.
        recommended_resource_scope describes the recommendations.
        Both scopes must be supported, non-null, and equal.

        Unsupported resource values are masked before validation and scoring.
        Their metrics are NaN and their valid-row counts are zero.

        Any-resource metrics are omitted when the profile prohibits them.
        Lifetime-average CPU targets receive cpu_usage_label="average_usage".

        The input is not modified. Use the same evaluator instance to
        summarize the returned results.
        """
        if self.capabilities is None:
            raise ValueError(
                "Canonical evaluation requires a dataset capability profile"
            )

        # Prevent applying one dataset's rules to another dataset's rows.
        if "dataset_id" not in data.columns:
            raise ValueError("Canonical evaluation requires dataset_id")

        if (
            data["dataset_id"].isna().any()
            or not data["dataset_id"].eq(
                self.capabilities.dataset_id
            ).all()
        ):
            raise ValueError(
                "dataset_id must match the capability profile"
            )

        # Validate only supported pairs. Rows still need at least one pair.
        data = self._mask_unsupported_resources(
            data,
            {
                "cpu": ("actual_cpu", "recommended_cpu"),
                "memory": ("actual_memory", "recommended_memory"),
            },
        )
        
        # Check canonical columns, resource pairs, and matching units.
        validate_evaluator_view(data)

        # Actual values and recommendations must describe the same scope.
        scope_columns = [
            "resource_scope",
            "recommended_resource_scope",
        ]

        for column in scope_columns:
            if column not in data.columns:
                raise ValueError(
                    f"Canonical evaluation requires {column}"
                )

            if not data[column].isin(RESOURCE_SCOPES).all():
                raise ValueError(
                    f"{column} must contain a supported, non-null scope"
                )

        if not data["resource_scope"].eq(
            data["recommended_resource_scope"]
        ).all():
            raise ValueError(
                "Actual/recommendation scopes must match"
            )
        
        # Reuse existing formulas and capability-aware suppression.
        return self.evaluate(
            data=data,
            actual_cpu_col="actual_cpu",
            actual_memory_col="actual_memory",
            recommended_cpu_col="recommended_cpu",
            recommended_memory_col="recommended_memory",
        )
