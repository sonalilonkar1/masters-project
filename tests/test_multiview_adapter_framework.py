import pandas as pd
import pytest

from src.adapters.base import (
    AdapterResult,
    BaseDatasetAdapter,
)

from src.adapters.validation import (
    AdapterValidationError,
    validate_rejected_output,
    validate_role_instance_linkage,
)

from src.canonical.schema import (
    SCHEMA_VERSION,
    DatasetCapabilities,
)


TEST_CAPABILITIES = DatasetCapabilities(
    dataset_id="synthetic_multiview",
    supports_cpu=True,
    supports_memory=True,
    supports_request=False,
    supports_recurrence=True,
    supports_targets=False,
    supports_ml=False,
    supports_observed_cpu=True,
    supports_observed_memory=True,
    supports_allocated_cpu=True,
    supports_allocated_memory=True,
    supported_record_levels=(
        "role_occurrence",
        "instance",
    ),
    recurrence_key_origin="official_with_role",
    notes="Synthetic Task 1 framework test profile.",
)


class SyntheticMultiViewAdapter(
    BaseDatasetAdapter
):
    adapter_name = "synthetic_multiview"
    adapter_version = "0.2.0"

    @property
    def capabilities(
        self,
    ) -> DatasetCapabilities:
        return TEST_CAPABILITIES

    def to_canonical(
        self,
        source: pd.DataFrame,
    ) -> pd.DataFrame:
        raise NotImplementedError(
            "Synthetic adapter uses multi-view path"
        )

    def map_prepared_sources(
        self,
        prepared,
    ):
        roles = prepared[
            "roles"
        ].copy()

        instances = prepared[
            "instances"
        ].copy()

        rejected = prepared.get(
            "rejected",
            pd.DataFrame(),
        ).copy()

        return (
            {
                "role_occurrence": roles,
                "instance": instances,
            },
            rejected,
        )


def make_role_view():
    return pd.DataFrame(
        [
            {
                "schema_version": SCHEMA_VERSION,
                "dataset_id": "synthetic_multiview",
                "record_level": "role_occurrence",
                "workload_id": "w1",
                "recurrence_key": "r1",
                "occurrence_id": "o1",
                "role_key": "role-1",
                "time_basis": "trace_relative",
                "start_time_us": 100,
                "validity_status": "valid",
            }
        ]
    )


def make_instance_view():
    return pd.DataFrame(
        [
            {
                "schema_version": SCHEMA_VERSION,
                "dataset_id": "synthetic_multiview",
                "record_level": "instance",
                "workload_id": "w1",
                "recurrence_key": "r1",
                "occurrence_id": "o1",
                "role_key": "role-1",
                "instance_id": "instance-1",
                "time_basis": "trace_relative",
                "start_time_us": 110,
                "validity_status": "valid",
            }
        ]
    )


def test_adapter_result_preserves_single_view_access():
    canonical = make_role_view()

    result = AdapterResult(
        canonical=canonical,
        metadata={},
    )

    assert result.canonical is canonical


def test_multiview_adapter_returns_named_views():
    adapter = SyntheticMultiViewAdapter()

    result = adapter.adapt_sources(
        {
            "roles": make_role_view(),
            "instances": make_instance_view(),
        },
        primary_view="role_occurrence",
    )

    assert set(
        result.views
    ) == {
        "role_occurrence",
        "instance",
    }

    assert (
        result.canonical
        is result.views[
            "role_occurrence"
        ]
    )


def test_role_and_instance_views_validate_independently():
    adapter = SyntheticMultiViewAdapter()

    bad_instance = (
        make_instance_view()
    )

    bad_instance.loc[
        0,
        "dataset_id",
    ] = "wrong-dataset"

    with pytest.raises(
        AdapterValidationError,
        match="dataset_id",
    ):
        adapter.adapt_sources(
            {
                "roles": make_role_view(),
                "instances": bad_instance,
            },
            primary_view="role_occurrence",
        )


def test_rejected_output_is_separate_from_views():
    adapter = SyntheticMultiViewAdapter()

    rejected = pd.DataFrame(
        [
            {
                "rejection_reason": "synthetic_rejection",
                "role_key": None,
                "source_value": None,
            }
        ]
    )

    result = adapter.adapt_sources(
        {
            "roles": make_role_view(),
            "instances": make_instance_view(),
            "rejected": rejected,
        },
        primary_view="role_occurrence",
    )

    assert len(
        result.rejected
    ) == 1

    assert (
        result.rejected.loc[
            0,
            "source_value",
        ]
        is None
    )

    assert (
        "rejection_reason"
        not in result.views[
            "role_occurrence"
        ].columns
    )


def test_rejected_output_requires_reason():
    rejected = pd.DataFrame(
        [
            {
                "role_key": "role-1",
            }
        ]
    )

    with pytest.raises(
        AdapterValidationError,
        match="rejection_reason",
    ):
        validate_rejected_output(
            rejected
        )


def test_metadata_contains_required_framework_fields():
    adapter = SyntheticMultiViewAdapter()

    result = adapter.adapt_sources(
        {
            "roles": make_role_view(),
            "instances": make_instance_view(),
        },
        primary_view="role_occurrence",
        provenance={
            "source_version": "synthetic-v1",
            "source_files": {
                "roles": "roles.csv",
                "instances": "instances.csv",
            },
            "source_checksums": {
                "roles": "abc",
                "instances": "def",
            },
            "telemetry_window": {
                "start": 0,
                "end": 1000,
            },
            "join_coverage_counts": {
                "matched": 1,
                "unmatched": 0,
            },
        },
    )

    metadata = result.metadata

    assert (
        metadata[
            "schema_version"
        ]
        == SCHEMA_VERSION
    )

    assert (
        metadata[
            "adapter_name"
        ]
        == "synthetic_multiview"
    )

    assert (
        metadata[
            "adapter_version"
        ]
        == "0.2.0"
    )

    assert (
        metadata[
            "dataset_id"
        ]
        == "synthetic_multiview"
    )

    assert (
        metadata[
            "source_row_counts"
        ]
        == {
            "roles": 1,
            "instances": 1,
        }
    )

    assert (
        metadata[
            "canonical_row_counts"
        ]
        == {
            "role_occurrence": 1,
            "instance": 1,
        }
    )

    assert (
        metadata[
            "rejection_count"
        ]
        == 0
    )

    assert (
        metadata[
            "join_coverage_counts"
        ][
            "matched"
        ]
        == 1
    )


def test_missing_parent_role_is_rejected():
    role_view = make_role_view()

    instance_view = (
        make_instance_view()
    )

    instance_view.loc[
        0,
        "role_key",
    ] = "missing-role"

    valid, rejected = (
        validate_role_instance_linkage(
            role_view,
            instance_view,
        )
    )

    assert valid.empty
    assert len(
        rejected
    ) == 1

    assert (
        rejected.iloc[
            0
        ][
            "rejection_reason"
        ]
        == "missing_parent_role"
    )


@pytest.mark.parametrize(
    "field,new_value",
    [
        (
            "workload_id",
            "different-workload",
        ),
        (
            "recurrence_key",
            "different-recurrence",
        ),
        (
            "occurrence_id",
            "different-occurrence",
        ),
    ],
)
def test_mismatched_parent_identity_is_rejected(
    field,
    new_value,
):
    role_view = make_role_view()

    instance_view = (
        make_instance_view()
    )

    instance_view.loc[
        0,
        field,
    ] = new_value

    valid, rejected = (
        validate_role_instance_linkage(
            role_view,
            instance_view,
        )
    )

    assert valid.empty

    assert (
        rejected.iloc[
            0
        ][
            "rejection_reason"
        ]
        == "parent_identity_mismatch"
    )


def test_null_parent_identity_values_compare_equal():
    role_view = make_role_view()

    instance_view = (
        make_instance_view()
    )

    role_view.loc[
        0,
        "recurrence_key",
    ] = None

    instance_view.loc[
        0,
        "recurrence_key",
    ] = None

    valid, rejected = (
        validate_role_instance_linkage(
            role_view,
            instance_view,
        )
    )

    assert len(
        valid
    ) == 1

    assert rejected.empty


def test_linkage_validation_does_not_modify_identity_fields():
    role_view = make_role_view()
    instance_view = make_instance_view()

    original = (
        instance_view.copy(
            deep=True
        )
    )

    validate_role_instance_linkage(
        role_view,
        instance_view,
    )

    pd.testing.assert_frame_equal(
        instance_view,
        original,
    )


def test_multiview_requires_explicit_primary_view():
    adapter = SyntheticMultiViewAdapter()

    with pytest.raises(
        ValueError,
        match="primary_view is required",
    ):
        adapter.adapt_sources(
            {
                "roles": make_role_view(),
                "instances": make_instance_view(),
            }
        )