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
    validate_adapter_output,
    validate_rejected_output,
)


@dataclass(frozen=True)
class AdapterResult:
    """
    Result returned by a dataset adapter.

    Backward compatibility:
    - ``canonical`` remains the primary canonical DataFrame.
    - Existing callers that only use ``canonical`` and ``metadata``
      continue to work unchanged.

    Multi-view adapters may additionally expose named canonical views
    and a separate rejected-record output.
    """

    canonical: pd.DataFrame
    metadata: Mapping[str, Any]

    views: Mapping[str, pd.DataFrame] = field(
        default_factory=dict
    )

    rejected: pd.DataFrame = field(
        default_factory=pd.DataFrame
    )

    def get_view(
        self,
        name: str,
    ) -> pd.DataFrame:
        """
        Return a named canonical view.

        ``canonical`` is also accepted as a compatibility alias for the
        primary view.
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

    @property
    @abstractmethod
    def capabilities(
        self,
    ) -> DatasetCapabilities:
        ...

    @abstractmethod
    def to_canonical(
        self,
        source: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Convert one source DataFrame to one canonical DataFrame.

        Existing single-view adapters continue to implement this method.
        Multi-view adapters may use ``adapt_sources`` and override
        ``prepare_sources`` / ``map_prepared_sources`` instead.
        """
        ...

    def build_metadata(
        self,
        *,
        source: pd.DataFrame,
        canonical: pd.DataFrame,
    ) -> Mapping[str, Any]:
        """
        Legacy single-view metadata builder.

        Existing adapters may override this method.
        """
        return {
            "schema_version": SCHEMA_VERSION,
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "dataset_id": self.capabilities.dataset_id,
            "source_row_count": int(len(source)),
            "canonical_row_count": int(len(canonical)),
            "capabilities": self.capabilities.to_dict(),
        }

    def adapt(
        self,
        source: pd.DataFrame,
    ) -> AdapterResult:
        """
        Backward-compatible single-source / single-view adapter path.
        """
        if not isinstance(
            source,
            pd.DataFrame,
        ):
            raise TypeError(
                "source must be a pandas DataFrame"
            )

        original = source.copy(
            deep=True
        )

        canonical = self.to_canonical(
            source.copy(deep=True)
        )

        if not isinstance(
            canonical,
            pd.DataFrame,
        ):
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
            views={
                "canonical": canonical,
            },
            rejected=pd.DataFrame(),
        )

    def prepare_sources(
        self,
        sources: Mapping[str, pd.DataFrame],
    ) -> Mapping[str, pd.DataFrame]:
        """
        Prepare multiple named source tables before canonical mapping.

        The default implementation returns deep copies unchanged.

        Dataset-specific adapters may override this hook for source-level
        normalization or preparation, but canonical identity construction
        remains the responsibility of the dataset adapter implementation.
        """
        return {
            name: frame.copy(deep=True)
            for name, frame in sources.items()
        }

    def map_prepared_sources(
        self,
        prepared: Mapping[str, pd.DataFrame],
    ) -> tuple[
        Mapping[str, pd.DataFrame],
        pd.DataFrame,
    ]:
        """
        Map prepared source tables into named canonical views plus rejected
        records.

        The default implementation supports the legacy single-source case.
        Multi-view adapters override this method.

        This shared framework does not perform dataset-specific joins,
        identity construction, aggregation, exclusions, or linkage
        construction.
        """
        if set(prepared) != {"source"}:
            raise NotImplementedError(
                "Adapters receiving multiple source tables must override "
                "map_prepared_sources()"
            )

        canonical = self.to_canonical(
            prepared["source"].copy(deep=True)
        )

        return (
            {
                "canonical": canonical,
            },
            pd.DataFrame(),
        )

    def build_multiview_metadata(
        self,
        *,
        sources: Mapping[str, pd.DataFrame],
        views: Mapping[str, pd.DataFrame],
        rejected: pd.DataFrame,
        primary_view: str,
        provenance: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        """
        Build shared metadata for a multi-view adapter result.

        Dataset adapters may pass provenance values such as source version,
        source files, checksums, telemetry window, and join-coverage counts.
        The framework records them without inventing unavailable values.
        """
        provenance = dict(
            provenance or {}
        )

        validity_counts: dict[
            str,
            dict[str, int],
        ] = {}

        exclusion_counts: dict[
            str,
            int,
        ] = {}

        for name, frame in views.items():
            if (
                "validity_status"
                in frame.columns
            ):
                validity_counts[name] = {
                    str(key): int(value)
                    for key, value in (
                        frame[
                            "validity_status"
                        ]
                        .value_counts(
                            dropna=False
                        )
                        .items()
                    )
                }
            else:
                validity_counts[name] = {}

            if (
                "exclusion_reason"
                in frame.columns
            ):
                exclusion_counts[name] = int(
                    frame[
                        "exclusion_reason"
                    ]
                    .notna()
                    .sum()
                )
            else:
                exclusion_counts[name] = 0

        return {
            "schema_version": SCHEMA_VERSION,
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "dataset_id": self.capabilities.dataset_id,
            "capabilities": self.capabilities.to_dict(),
            "primary_view": primary_view,
            "source_row_count": int(
                sum(
                    len(frame)
                    for frame in sources.values()
                )
            ),
            "canonical_row_count": int(
                len(
                    views[
                        primary_view
                    ]
                )
            ),
            "source_row_counts": {
                name: int(
                    len(frame)
                )
                for name, frame
                in sources.items()
            },
            "canonical_row_counts": {
                name: int(
                    len(frame)
                )
                for name, frame
                in views.items()
            },
            "validity_counts": validity_counts,
            "exclusion_counts": exclusion_counts,
            "rejection_count": int(
                len(rejected)
            ),
            "provenance": {
                "source_version": provenance.get(
                    "source_version"
                ),
                "source_files": provenance.get(
                    "source_files",
                    {},
                ),
                "source_checksums": provenance.get(
                    "source_checksums",
                    {},
                ),
                "telemetry_window": provenance.get(
                    "telemetry_window"
                ),
            },
            "join_coverage_counts": provenance.get(
                "join_coverage_counts",
                {},
            ),
        }

    def adapt_sources(
        self,
        sources: Mapping[str, pd.DataFrame],
        *,
        primary_view: str | None = None,
        provenance: Mapping[str, Any] | None = None,
    ) -> AdapterResult:
        """
        Execute the shared multi-source / multi-view adapter pipeline.

        Every canonical view is validated independently.

        Rejected rows remain separate and are never validated as canonical
        output.
        """
        if not isinstance(
            sources,
            Mapping,
        ):
            raise TypeError(
                "sources must be a mapping of name -> pandas DataFrame"
            )

        if not sources:
            raise ValueError(
                "sources must contain at least one source table"
            )

        originals: dict[
            str,
            pd.DataFrame,
        ] = {}

        copied_sources: dict[
            str,
            pd.DataFrame,
        ] = {}

        for name, frame in sources.items():
            if not isinstance(
                name,
                str,
            ):
                raise TypeError(
                    "source table names must be strings"
                )

            if not isinstance(
                frame,
                pd.DataFrame,
            ):
                raise TypeError(
                    f"source {name!r} must be a pandas DataFrame"
                )

            originals[name] = frame.copy(
                deep=True
            )

            copied_sources[name] = frame.copy(
                deep=True
            )

        prepared = self.prepare_sources(
            copied_sources
        )

        if not isinstance(
            prepared,
            Mapping,
        ):
            raise TypeError(
                "prepare_sources() must return a mapping"
            )

        for name, frame in prepared.items():
            if not isinstance(
                frame,
                pd.DataFrame,
            ):
                raise TypeError(
                    f"prepared source {name!r} must be a pandas DataFrame"
                )

        views, rejected = (
            self.map_prepared_sources(
                prepared
            )
        )

        if not isinstance(
            views,
            Mapping,
        ):
            raise TypeError(
                "map_prepared_sources() must return a mapping of views"
            )

        if not views:
            raise ValueError(
                "adapter must produce at least one canonical view"
            )

        if not isinstance(
            rejected,
            pd.DataFrame,
        ):
            raise TypeError(
                "rejected output must be a pandas DataFrame"
            )

        normalized_views: dict[
            str,
            pd.DataFrame,
        ] = {}

        for name, frame in views.items():
            if not isinstance(
                name,
                str,
            ):
                raise TypeError(
                    "canonical view names must be strings"
                )

            if not isinstance(
                frame,
                pd.DataFrame,
            ):
                raise TypeError(
                    f"canonical view {name!r} must be a pandas DataFrame"
                )

            if (
                name
                in {
                    "role_occurrence",
                    "instance",
                }
                and not frame.empty
            ):
                expected_level = name

                if (
                    "record_level"
                    not in frame.columns
                ):
                    raise ValueError(
                        f"{name!r} view requires record_level"
                    )

                bad_level = (
                    frame[
                        "record_level"
                    ]
                    != expected_level
                )

                if bad_level.any():
                    raise ValueError(
                        f"{name!r} view may contain only "
                        f"record_level={expected_level!r}"
                    )

            validate_adapter_output(
                frame,
                capabilities=self.capabilities,
            )

            normalized_views[
                name
            ] = frame

        validate_rejected_output(
            rejected
        )

        for name, original in originals.items():
            pd.testing.assert_frame_equal(
                sources[name],
                original,
                check_dtype=True,
                check_like=False,
            )

        if primary_view is None:
            if len(
                normalized_views
            ) == 1:
                primary_view = next(
                    iter(
                        normalized_views
                    )
                )
            else:
                raise ValueError(
                    "primary_view is required when an adapter produces "
                    "multiple canonical views"
                )

        if (
            primary_view
            not in normalized_views
        ):
            raise KeyError(
                f"primary_view {primary_view!r} not found. "
                f"Available views: {sorted(normalized_views)}"
            )

        metadata = (
            self.build_multiview_metadata(
                sources=sources,
                views=normalized_views,
                rejected=rejected,
                primary_view=primary_view,
                provenance=provenance,
            )
        )

        return AdapterResult(
            canonical=normalized_views[
                primary_view
            ],
            views=normalized_views,
            rejected=rejected.copy(
                deep=True
            ),
            metadata=metadata,
        )