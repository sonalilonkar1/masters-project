"""Base adapter contract for TraceAdvisor datasets."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping

import pandas as pd

from src.canonical.schema import (
    SCHEMA_VERSION,
    DatasetCapabilities,
)

from .validation import (
    AdapterValidationError,
    validate_adapter_output,
    validate_rejected_output,
    validate_role_instance_linkage,
)


def _count_values(frame: pd.DataFrame, column: str) -> dict[str, int]:
    """Return JSON-friendly per-value counts, preserving null as ``<null>``."""
    if column not in frame.columns:
        return {}

    counts = frame[column].value_counts(dropna=False)
    result: dict[str, int] = {}

    for value, count in counts.items():
        key = "<null>" if pd.isna(value) else str(value)
        result[key] = int(count)

    return result


@dataclass(frozen=True)
class AdapterResult:
    """
    Result returned by a dataset adapter.

    ``canonical`` remains the backward-compatible primary DataFrame.

    ``views`` contains named canonical views. Legacy results created without
    an explicit views mapping are normalized to
    ``{"canonical": canonical}``.

    ``primary_view`` identifies which named view is exposed through
    ``canonical``.

    ``rejected`` is audit-only output and is never a validated canonical view.

    DataFrames remain mutable even though this dataclass is frozen. Downstream
    stages must copy a view before adding or modifying columns.
    """

    canonical: pd.DataFrame
    metadata: Mapping[str, Any]
    views: Mapping[str, pd.DataFrame] = field(default_factory=dict)
    rejected: pd.DataFrame = field(default_factory=pd.DataFrame)
    primary_view: str | None = None

    def __post_init__(self) -> None:
        views = dict(self.views)
        metadata = dict(self.metadata)
        primary_view = self.primary_view

        if not views:
            views = {"canonical": self.canonical}
            primary_view = primary_view or "canonical"
        elif primary_view is None:
            matching_views = [
                name
                for name, frame in views.items()
                if frame is self.canonical
            ]

            if len(matching_views) != 1:
                raise ValueError(
                    "Unable to infer a unique primary_view from canonical"
                )

            primary_view = matching_views[0]

        if primary_view not in views:
            raise ValueError(
                f"primary_view {primary_view!r} not found in views"
            )

        if views[primary_view] is not self.canonical:
            raise ValueError(
                "canonical must reference the same DataFrame as "
                "views[primary_view]"
            )

        object.__setattr__(self, "views", views)
        object.__setattr__(self, "metadata", metadata)
        object.__setattr__(self, "primary_view", primary_view)

    def get_view(self, name: str) -> pd.DataFrame:
        """Return a named canonical view.

        ``canonical`` remains a compatibility alias for the primary view.
        """
        if name == "canonical":
            return self.canonical

        if name not in self.views:
            raise KeyError(
                f"Unknown canonical view {name!r}. "
                f"Available views: {sorted(self.views)}"
            )

        return self.views[name]


class BaseDatasetAdapter(ABC):
    adapter_name: str = "base"
    adapter_version: str = "0.1.0"

    # Dataset adapters may override this with per-rejection-level requirements.
    rejected_required_columns: Mapping[str, tuple[str, ...]] = {}

    @property
    @abstractmethod
    def capabilities(self) -> DatasetCapabilities:
        ...

    @abstractmethod
    def to_canonical(self, source: pd.DataFrame) -> pd.DataFrame:
        """Convert one source DataFrame to one canonical DataFrame."""
        ...

    def build_metadata(
        self,
        *,
        source: pd.DataFrame,
        canonical: pd.DataFrame,
    ) -> Mapping[str, Any]:
        """Legacy single-view metadata builder."""
        return {
            "schema_version": SCHEMA_VERSION,
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "dataset_id": self.capabilities.dataset_id,
            "source_row_count": int(len(source)),
            "canonical_row_count": int(len(canonical)),
            "capabilities": self.capabilities.to_dict(),
        }

    def adapt(self, source: pd.DataFrame) -> AdapterResult:
        """Backward-compatible single-source / single-view adapter path."""
        if not isinstance(source, pd.DataFrame):
            raise TypeError("source must be a pandas DataFrame")

        original = source.copy(deep=True)
        canonical = self.to_canonical(source.copy(deep=True))

        if not isinstance(canonical, pd.DataFrame):
            raise TypeError(
                "to_canonical() must return a pandas DataFrame"
            )

        pd.testing.assert_frame_equal(
            source,
            original,
            check_dtype=True,
            check_like=False,
        )

        validate_adapter_output(
            canonical,
            capabilities=self.capabilities,
        )

        metadata = self.build_metadata(
            source=source,
            canonical=canonical,
        )

        return AdapterResult(
            canonical=canonical,
            metadata=metadata,
            views={"canonical": canonical},
            rejected=pd.DataFrame(),
            primary_view="canonical",
        )

    def prepare_sources(
        self,
        sources: Mapping[str, pd.DataFrame],
    ) -> Mapping[str, pd.DataFrame]:
        """Prepare multiple named source tables before canonical mapping."""
        return {
            name: frame.copy(deep=True)
            for name, frame in sources.items()
        }

    def map_prepared_sources(
        self,
        prepared: Mapping[str, pd.DataFrame],
    ) -> tuple[Mapping[str, pd.DataFrame], pd.DataFrame]:
        """Map prepared source tables into named canonical views and rejects."""
        if set(prepared) != {"source"}:
            raise NotImplementedError(
                "Adapters receiving multiple source tables must override "
                "map_prepared_sources()"
            )

        canonical = self.to_canonical(
            prepared["source"].copy(deep=True)
        )

        return {"canonical": canonical}, pd.DataFrame()

    @staticmethod
    def _validate_provenance(
        provenance: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        """Validate required provenance for the multi-view adapter path."""
        if provenance is None:
            raise AdapterValidationError(
                "Multi-view adaptation requires provenance metadata"
            )

        values = dict(provenance)

        required = (
            "source_version",
            "source_files",
            "source_checksums",
            "telemetry_window",
        )

        missing = [
            key
            for key in required
            if key not in values
            or values[key] is None
            or values[key] == ""
            or values[key] == {}
        ]

        if missing:
            raise AdapterValidationError(
                "Missing required provenance metadata: "
                f"{sorted(missing)}"
            )

        if not isinstance(values["source_files"], Mapping):
            raise AdapterValidationError(
                "provenance source_files must be a mapping"
            )

        if not isinstance(values["source_checksums"], Mapping):
            raise AdapterValidationError(
                "provenance source_checksums must be a mapping"
            )

        if not isinstance(values["telemetry_window"], Mapping):
            raise AdapterValidationError(
                "provenance telemetry_window must be a mapping"
            )

        return values

    @staticmethod
    def _validate_rejected_view_separation(
        *,
        views: Mapping[str, pd.DataFrame],
        rejected: pd.DataFrame,
    ) -> None:
        """Reject overlap between validated views and rejected output."""
        if rejected.empty:
            return

        checks = (
            ("role_occurrence", "role_key"),
            ("instance", "instance_id"),
        )

        for view_name, key in checks:
            if (
                view_name not in views
                or key not in views[view_name].columns
                or key not in rejected.columns
            ):
                continue

            validated_keys = set(
                views[view_name][key]
                .dropna()
                .astype(str)
                .tolist()
            )

            rejected_keys = set(
                rejected[key]
                .dropna()
                .astype(str)
                .tolist()
            )

            overlap = sorted(validated_keys & rejected_keys)

            if overlap:
                raise AdapterValidationError(
                    "Rejected output overlaps validated "
                    f"{view_name!r} view on {key}: {overlap[:5]}"
                )

    def build_multiview_metadata(
        self,
        *,
        sources: Mapping[str, pd.DataFrame],
        views: Mapping[str, pd.DataFrame],
        rejected: pd.DataFrame,
        primary_view: str,
        provenance: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Build validated metadata for a multi-view adapter result."""
        provenance_values = self._validate_provenance(provenance)

        validity_counts = {
            name: _count_values(frame, "validity_status")
            for name, frame in views.items()
        }

        cpu_validity_counts = {
            name: _count_values(frame, "cpu_validity_status")
            for name, frame in views.items()
        }

        memory_validity_counts = {
            name: _count_values(frame, "memory_validity_status")
            for name, frame in views.items()
        }

        # Exclusion/eligibility belongs to the evaluation-level primary view,
        # not audit-level instance rows.
        exclusion_reason_counts = _count_values(
            views[primary_view],
            "exclusion_reason",
        )

        rejection_counts: dict[str, dict[str, int]] = {}
        if not rejected.empty:
            grouped = (
                rejected.groupby(
                    ["rejection_level", "rejection_reason"],
                    dropna=False,
                )
                .size()
            )

            for (level, reason), count in grouped.items():
                rejection_counts.setdefault(
                    str(level),
                    {},
                )[str(reason)] = int(count)

        return {
            "schema_version": SCHEMA_VERSION,
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "dataset_id": self.capabilities.dataset_id,
            "capabilities": self.capabilities.to_dict(),
            "primary_view": primary_view,
            "source_row_count": int(
                sum(len(frame) for frame in sources.values())
            ),
            "canonical_row_count": int(
                len(views[primary_view])
            ),
            "source_row_counts": {
                name: int(len(frame))
                for name, frame in sources.items()
            },
            "canonical_row_counts": {
                name: int(len(frame))
                for name, frame in views.items()
            },
            "validity_counts": validity_counts,
            "cpu_validity_counts": cpu_validity_counts,
            "memory_validity_counts": memory_validity_counts,
            "exclusion_reason_counts": exclusion_reason_counts,
            "rejection_count": int(len(rejected)),
            "rejection_counts": rejection_counts,
            "provenance": {
                "source_version": provenance_values[
                    "source_version"
                ],
                "source_files": dict(
                    provenance_values["source_files"]
                ),
                "source_checksums": dict(
                    provenance_values["source_checksums"]
                ),
                "telemetry_window": dict(
                    provenance_values["telemetry_window"]
                ),
            },
            "join_coverage_counts": dict(
                provenance_values.get(
                    "join_coverage_counts",
                    {},
                )
            ),
        }

    def adapt_sources(
        self,
        sources: Mapping[str, pd.DataFrame],
        *,
        primary_view: str | None = None,
        provenance: Mapping[str, Any] | None = None,
    ) -> AdapterResult:
        """Execute the shared multi-source / multi-view adapter pipeline."""
        if not isinstance(sources, Mapping):
            raise TypeError(
                "sources must be a mapping of name -> pandas DataFrame"
            )

        if not sources:
            raise ValueError(
                "sources must contain at least one source table"
            )

        originals: dict[str, pd.DataFrame] = {}
        copied_sources: dict[str, pd.DataFrame] = {}

        for name, frame in sources.items():
            if not isinstance(name, str):
                raise TypeError(
                    "source table names must be strings"
                )

            if not isinstance(frame, pd.DataFrame):
                raise TypeError(
                    f"source {name!r} must be a pandas DataFrame"
                )

            originals[name] = frame.copy(deep=True)
            copied_sources[name] = frame.copy(deep=True)

        prepared = self.prepare_sources(copied_sources)

        if not isinstance(prepared, Mapping):
            raise TypeError(
                "prepare_sources() must return a mapping"
            )

        for name, frame in prepared.items():
            if not isinstance(frame, pd.DataFrame):
                raise TypeError(
                    f"prepared source {name!r} must be a pandas DataFrame"
                )

        views, rejected = self.map_prepared_sources(prepared)

        if not isinstance(views, Mapping):
            raise TypeError(
                "map_prepared_sources() must return a mapping of views"
            )

        if not views:
            raise ValueError(
                "adapter must produce at least one canonical view"
            )

        if not isinstance(rejected, pd.DataFrame):
            raise TypeError(
                "rejected output must be a pandas DataFrame"
            )

        normalized_views: dict[str, pd.DataFrame] = {}

        for name, frame in views.items():
            if not isinstance(name, str):
                raise TypeError(
                    "canonical view names must be strings"
                )

            if not isinstance(frame, pd.DataFrame):
                raise TypeError(
                    f"canonical view {name!r} must be a pandas DataFrame"
                )

            if (
                name in {"role_occurrence", "instance"}
                and not frame.empty
            ):
                if "record_level" not in frame.columns:
                    raise ValueError(
                        f"{name!r} view requires record_level"
                    )

                bad_level = (
                    frame["record_level"] != name
                )

                if bad_level.any():
                    raise ValueError(
                        f"{name!r} view may contain only "
                        f"record_level={name!r}"
                    )

            validate_adapter_output(
                frame,
                capabilities=self.capabilities,
            )

            normalized_views[name] = frame

        if (
            "role_occurrence" in normalized_views
            and "instance" in normalized_views
        ):
            validate_role_instance_linkage(
                normalized_views["role_occurrence"],
                normalized_views["instance"],
                capabilities=self.capabilities,
            )

        validate_rejected_output(
            rejected,
            required_columns=self.rejected_required_columns,
        )

        self._validate_rejected_view_separation(
            views=normalized_views,
            rejected=rejected,
        )

        for name, original in originals.items():
            pd.testing.assert_frame_equal(
                sources[name],
                original,
                check_dtype=True,
                check_like=False,
            )

        if primary_view is None:
            if len(normalized_views) == 1:
                primary_view = next(iter(normalized_views))
            else:
                raise ValueError(
                    "primary_view is required when an adapter produces "
                    "multiple canonical views"
                )

        if primary_view not in normalized_views:
            raise KeyError(
                f"primary_view {primary_view!r} not found. "
                f"Available views: {sorted(normalized_views)}"
            )

        metadata = self.build_multiview_metadata(
            sources=sources,
            views=normalized_views,
            rejected=rejected,
            primary_view=primary_view,
            provenance=provenance,
        )

        return AdapterResult(
            canonical=normalized_views[primary_view],
            views=normalized_views,
            rejected=rejected.copy(deep=True),
            metadata=metadata,
            primary_view=primary_view,
        )
