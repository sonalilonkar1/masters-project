"""
Shared evaluator for comparing actual and recommended resources.

This evaluator supports different datasets and recommendation policies
without depending on dataset-specific identifier columns.
"""

from __future__ import annotations
from src.canonical.schema import (
    CanonicalSchemaError,
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
        actual_cpu_col: str | None = None,
        actual_memory_col: str | None = None,
        recommended_cpu_col: str | None = None,
        recommended_memory_col: str | None = None,
        policy_name: str | None = None,
        id_cols: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        
        """
        Calculate row-level evaluation metrics.

        The input DataFrame is not modified.
        """
        
        # A resource must supply both column names or neither.
        resource_pairs = {
            "cpu": (actual_cpu_col, recommended_cpu_col),
            "memory": (actual_memory_col, recommended_memory_col),
        }
        supplied_resources = []

        for resource, (actual_col, recommended_col) in resource_pairs.items():
            if (actual_col is None) != (recommended_col is None):
                raise ValueError(
                    f"{resource} requires both actual and recommendation columns"
                )

            if actual_col is not None:
                supplied_resources.append(resource)

        if not supplied_resources:
            raise ValueError(
                "At least one actual/recommendation pair is required"
            )

        # Create null columns for omitted resources on a private copy.
        data = data.copy()

        if actual_cpu_col is None:
            actual_cpu_col = "__unevaluated_actual_cpu"
            recommended_cpu_col = "__unevaluated_recommended_cpu"
            data[actual_cpu_col] = np.nan
            data[recommended_cpu_col] = np.nan

        if actual_memory_col is None:
            actual_memory_col = "__unevaluated_actual_memory"
            recommended_memory_col = "__unevaluated_recommended_memory"
            data[actual_memory_col] = np.nan
            data[recommended_memory_col] = np.nan
        
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
        if self.capabilities is not None:
            # Map caller-selected values and their units together before checks.
            for resource, actual_col, recommended_col in (
                ("cpu", actual_cpu_col, recommended_cpu_col),
                ("memory", actual_memory_col, recommended_memory_col),
            ):
                for kind, column in (
                    ("actual", actual_col), ("recommended", recommended_col)
                ):
                    canonical = f"{kind}_{resource}"
                    evaluated[canonical] = evaluated[column]
                    source_unit = f"{column}_unit"
                    if source_unit in evaluated:
                        evaluated[canonical + "_unit"] = evaluated[source_unit]
            if policy_name is not None:
                evaluated["policy_name"] = policy_name
            self._validate_profile_view(evaluated)

        # Unsupported resources do not count as evaluated resources.
        evaluated_resources = [
            resource
            for resource in supplied_resources
            if self.capabilities is None
            or (
                getattr(self.capabilities, f"supports_{resource}")
                and getattr(
                    self.capabilities,
                    f"supports_observed_{resource}",
                )
            )
        ]
        
        if self.capabilities is not None:
            # Canonical columns may exist even when a resource is unevaluated.
            evaluated_resources = [
                resource
                for resource in evaluated_resources
                if (
                    evaluated[resource_pairs[resource][0]].notna()
                    & evaluated[resource_pairs[resource][1]].notna()
                ).any()
            ]

        report_any_resource = (
            self.reports_any_resource
            and len(evaluated_resources) == 2
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

        if report_any_resource:
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
            and self.capabilities.has_cpu_average
            and not self.capabilities.has_cpu_peak
        ):
            evaluated["cpu_usage_label"] = "average_usage"
        
        # Keep internal placeholder columns out of the returned data.
        placeholder_columns = []
        if "cpu" not in supplied_resources:
            placeholder_columns.extend(
                [actual_cpu_col, recommended_cpu_col]
            )
        if "memory" not in supplied_resources:
            placeholder_columns.extend(
                [actual_memory_col, recommended_memory_col]
            )

        evaluated = evaluated.drop(columns=placeholder_columns)
        evaluated.attrs["evaluated_resources"] = evaluated_resources
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
        
        With a profile, four valid waste/shortfall counts are added. Profile
        metadata is returned separately by summary_metadata(); this result
        stays numeric-only. Use the same instance that evaluated the data.
        """
        report_any_resource = (
            self.reports_any_resource
            and len(
                evaluated_data.attrs.get(
                    "evaluated_resources",
                    ["cpu", "memory"],
                )
            ) == 2
        )
        
        valid_cpu_violation_rows = (
            evaluated_data["cpu_violation"].notna()
        )

        valid_memory_violation_rows = (
            evaluated_data["memory_violation"].notna()
        )

        valid_any_resource_violation_rows = (
            evaluated_data["any_resource_violation"].notna()
            if report_any_resource
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
            if report_any_resource
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
        if not report_any_resource:
            summary.pop("valid_any_resource_violation_count")
            summary.pop("any_resource_violation_pct")

        if self.capabilities is not None:
            for resource in ("cpu", "memory"):
                for metric in ("waste", "shortfall"):
                    summary[f"valid_{resource}_{metric}_count"] = int(
                        np.isfinite(evaluated_data[f"{resource}_{metric}"]).sum()
                    )
        
        return summary
    
    
    def summary_metadata(self, evaluated_data: pd.DataFrame) -> dict[str, object]:
        """Return profile metadata separately from the numeric summary.

        Returns an empty dictionary without a profile. Use the same evaluator
        instance for evaluation, summarize(), and summary_metadata(). Policy
        name is a string for one policy, a list for multiple policies, or null
        for empty input. No policy selection or ranking occurs here.
        """
        profile = self.capabilities
        if profile is None:
            return {}

        unsupported = [
            resource for resource in ("cpu", "memory")
            if not (
                getattr(profile, f"supports_{resource}")
                and getattr(profile, f"supports_observed_{resource}")
            )
        ]
        resources = list(evaluated_data.attrs.get("evaluated_resources", [
            resource for resource in ("cpu", "memory")
            if resource not in unsupported
            and evaluated_data[f"actual_{resource}"].notna().any()
            and evaluated_data[f"recommended_{resource}"].notna().any()
        ]))
        reported = (
            profile.any_resource_metric_valid and len(resources) == 2
            and "any_resource_violation" in evaluated_data
        )
        reason = None
        if not reported:
            if not profile.any_resource_metric_valid:
                reason = "profile_disallows_any_resource"
            elif not resources:
                reason = "no_evaluated_resources"
            elif len(resources) == 1:
                reason = "single_resource_evaluation"
            else:
                reason = "any_resource_metric_absent"

        cpu_semantics = None
        if "cpu" not in unsupported:
            if profile.has_cpu_average and not profile.has_cpu_peak:
                cpu_semantics = "average_usage"
            elif profile.has_cpu_peak:
                cpu_semantics = "peak_usage"

        policies = evaluated_data["policy_name"].dropna().unique().tolist()
        return {
            "dataset_id": profile.dataset_id,
            "policy_name": policies[0] if len(policies) == 1 else policies or None,
            "cpu_result_semantics": cpu_semantics,
            "primary_resource": (
                "memory"
                if profile.evaluation_mode == "next_occurrence_memory_peak_cpu_average"
                else None
            ),
            "evaluated_resources": resources,
            "unsupported_resources": unsupported,
            "any_resource_metric_reported": reported,
            "any_resource_suppression_reason": reason,
        }

    def _validate_profile_view(self, data: pd.DataFrame) -> None:
        """Validate and evaluate recommendations using a dataset profile.

        Requires a capability profile supplied to the constructor and these
        canonical columns:
            dataset_id, workload_id, policy_name,
            actual_cpu, actual_memory,
            recommended_cpu, recommended_memory.

        Each supported actual/recommendation pair requires matching,
        non-null actual_<resource>_unit and recommended_<resource>_unit
        values. Every row must contain at least one supported pair.

        Optional resource_scope describes the shared comparison scope.
        If recommended_resource_scope is supplied, resource_scope is required
        and both must agree. Supplied scopes must be supported, non-null,
        and consistent across the evaluation population.

        Unsupported resource values are masked before validation and scoring.
        Their metrics are NaN and their valid-row counts are zero.

        Any-resource metrics are omitted when the profile prohibits them.
        Average-only CPU profiles receive cpu_usage_label="average_usage".
        summary_metadata() reports semantics, primary resource, resource
        support, dataset/policy identity, and any-resource suppression reasons.
        summarize() returns numeric metrics separately from this metadata.

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

        # The shared schema validator is unchanged; require explicit units
        # here because nullable string comparisons can overlook missing units.
        for resource in ("cpu", "memory"):
            pair = (
                data[f"actual_{resource}"].notna()
                & data[f"recommended_{resource}"].notna()
            )
            if not pair.any():
                continue
            actual_unit = data[f"actual_{resource}_unit"]
            recommended_unit = data[f"recommended_{resource}_unit"]
            if (pair & (actual_unit.isna() | recommended_unit.isna())).any():
                raise CanonicalSchemaError(
                    f"{resource} actual/recommendation units must be populated"
                )

            profile_unit = getattr(self.capabilities, f"{resource}_unit")
            if profile_unit is not None:
                for units in (actual_unit, recommended_unit):
                    if (pair & ~units.eq(profile_unit).fillna(False)).any():
                        raise CanonicalSchemaError(
                            f"{resource} units must match profile unit {profile_unit!r}"
                        )

        # resource_scope is optional and describes the shared comparison scope.
        # A separate recommendation scope, when supplied, must agree with it.
        if "recommended_resource_scope" in data and "resource_scope" not in data:
            raise ValueError(
                "resource_scope required when recommended_resource_scope is supplied"
            )
        for column in ("resource_scope", "recommended_resource_scope"):
            if column not in data:
                continue
            if not data[column].isin(RESOURCE_SCOPES).all():
                raise ValueError(
                    f"{column} must contain a supported, non-null scope"
                )
            if data[column].nunique() > 1:
                raise ValueError(f"{column} must contain a consistent scope")

        if "recommended_resource_scope" in data:
            if not data["resource_scope"].eq(
                data["recommended_resource_scope"]
            ).all():
                raise ValueError("Actual/recommendation scopes must match")

    def evaluate_canonical(self, data: pd.DataFrame) -> pd.DataFrame:
        """Evaluate canonical resource columns using the constructor's profile."""
        if self.capabilities is None:
            raise ValueError(
                "Canonical evaluation requires a dataset capability profile"
            )
        columns = {}
        for resource in ("cpu", "memory"):
            for kind in ("actual", "recommended"):
                column = f"{kind}_{resource}"
                columns[f"{column}_col"] = column if column in data.columns else None
        return self.evaluate(data, **columns)
