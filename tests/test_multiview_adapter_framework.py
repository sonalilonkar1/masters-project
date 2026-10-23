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
    instance_event_time_semantics="parent_job_submission",
    allowed_exclusion_reasons=(
        "no_recurrence_key",
    ),
    notes="Synthetic Task 1 framework test profile.",
)


def make_provenance():
    return {
        "source_version": "synthetic-v1",
        "source_files": {
            "roles": "roles.csv",
            "instances": "instances.csv",
        },
        "source_checksums": {
            "roles": "sha256:abc",
            "instances": "sha256:def",
        },
        "telemetry_window": {
            "start": 0,
            "end": 1000,
        },
        "join_coverage_counts": {
            "matched": 1,
            "unmatched": 0,
        },
    }


class SyntheticMultiViewAdapter(
    BaseDatasetAdapter
):
    adapter_name = "synthetic_multiview"
    adapter_version = "0.2.0"

    rejected_required_columns = {
        "instance": (
            "source_row_number",
        ),
    }

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


class MutatingPreparationAdapter(
    SyntheticMultiViewAdapter
):
    def prepare_sources(
        self,
        sources,
    ):
        prepared = dict(sources)
        prepared["roles"]["temporary_column"] = "temporary"
        return prepared


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
                "cpu_validity_status": "valid",
                "memory_validity_status": "partial",
                "exclusion_reason": None,
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
                "event_time_us": 100,
                "start_time_us": 110,
                "validity_status": "valid",
                "cpu_validity_status": "valid",
                "memory_validity_status": "valid",
            }
        ]
    )


def make_rejected_instance(
    *,
    instance_id="rejected-instance",
):
    return pd.DataFrame(
        [
            {
                "rejection_level": "instance",
                "rejection_reason": "missing_submission_time",
                "instance_id": instance_id,
                "role_key": None,
                "source_row_number": 999,
                "source_value": None,
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
    assert result.primary_view == "canonical"
    assert set(result.views) == {"canonical"}
    assert result.views["canonical"] is canonical
    assert result.get_view("canonical") is canonical
    assert result.rejected.empty


def test_adapter_result_infers_named_primary_view():
    canonical = make_role_view()

    result = AdapterResult(
        canonical=canonical,
        metadata={},
        views={
            "role_occurrence": canonical,
        },
    )

    assert result.primary_view == "role_occurrence"
    assert (
        result.get_view("role_occurrence")
        is canonical
    )


def test_adapter_result_rejects_inconsistent_primary_view():
    canonical = make_role_view()
    different = make_role_view().copy(
        deep=True
    )

    with pytest.raises(
        ValueError,
        match="canonical must reference",
    ):
        AdapterResult(
            canonical=canonical,
            metadata={},
            views={
                "role_occurrence": different,
            },
            primary_view="role_occurrence",
        )


def test_adapter_result_unknown_view_raises():
    result = AdapterResult(
        canonical=make_role_view(),
        metadata={},
    )

    with pytest.raises(
        KeyError,
        match="Unknown canonical view",
    ):
        result.get_view("missing")


def test_adapter_result_copies_views_mapping():
    canonical = make_role_view()
    views = {
        "role_occurrence": canonical,
    }

    result = AdapterResult(
        canonical=canonical,
        metadata={},
        views=views,
    )

    views["other"] = canonical

    assert "other" not in result.views


def test_multiview_adapter_returns_named_views():
    adapter = SyntheticMultiViewAdapter()

    result = adapter.adapt_sources(
        {
            "roles": make_role_view(),
            "instances": make_instance_view(),
        },
        primary_view="role_occurrence",
        provenance=make_provenance(),
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

    assert (
        result.primary_view
        == "role_occurrence"
    )


def test_role_and_instance_views_validate_independently():
    adapter = SyntheticMultiViewAdapter()
    bad_instance = make_instance_view()

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
            provenance=make_provenance(),
        )


def test_rejected_output_is_separate_from_views():
    adapter = SyntheticMultiViewAdapter()
    rejected = make_rejected_instance()

    result = adapter.adapt_sources(
        {
            "roles": make_role_view(),
            "instances": make_instance_view(),
            "rejected": rejected,
        },
        primary_view="role_occurrence",
        provenance=make_provenance(),
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


def test_rejected_output_requires_level_and_reason():
    with pytest.raises(
        AdapterValidationError,
        match="rejection_level",
    ):
        validate_rejected_output(
            pd.DataFrame(
                [
                    {
                        "rejection_reason": "x",
                    }
                ]
            )
        )

    with pytest.raises(
        AdapterValidationError,
        match="rejection_reason",
    ):
        validate_rejected_output(
            pd.DataFrame(
                [
                    {
                        "rejection_level": "instance",
                    }
                ]
            )
        )


def test_rejected_output_required_columns_hook():
    rejected = pd.DataFrame(
        [
            {
                "rejection_level": "instance",
                "rejection_reason": "missing_submission_time",
            }
        ]
    )

    with pytest.raises(
        AdapterValidationError,
        match="source_row_number",
    ):
        validate_rejected_output(
            rejected,
            required_columns={
                "instance": (
                    "source_row_number",
                ),
            },
        )


def test_rejected_output_must_not_overlap_instance_view():
    adapter = SyntheticMultiViewAdapter()

    rejected = make_rejected_instance(
        instance_id="instance-1",
    )

    with pytest.raises(
        AdapterValidationError,
        match="overlaps validated",
    ):
        adapter.adapt_sources(
            {
                "roles": make_role_view(),
                "instances": make_instance_view(),
                "rejected": rejected,
            },
            primary_view="role_occurrence",
            provenance=make_provenance(),
        )


def test_metadata_contains_required_framework_fields():
    adapter = SyntheticMultiViewAdapter()

    result = adapter.adapt_sources(
        {
            "roles": make_role_view(),
            "instances": make_instance_view(),
        },
        primary_view="role_occurrence",
        provenance=make_provenance(),
    )

    metadata = result.metadata

    assert metadata[
        "schema_version"
    ] == SCHEMA_VERSION

    assert metadata[
        "adapter_name"
    ] == "synthetic_multiview"

    assert metadata[
        "adapter_version"
    ] == "0.2.0"

    assert metadata[
        "dataset_id"
    ] == "synthetic_multiview"

    assert metadata[
        "source_row_counts"
    ] == {
        "roles": 1,
        "instances": 1,
    }

    assert metadata[
        "canonical_row_counts"
    ] == {
        "role_occurrence": 1,
        "instance": 1,
    }

    assert metadata[
        "validity_counts"
    ][
        "role_occurrence"
    ][
        "valid"
    ] == 1

    assert metadata[
        "cpu_validity_counts"
    ][
        "role_occurrence"
    ][
        "valid"
    ] == 1

    assert metadata[
        "memory_validity_counts"
    ][
        "role_occurrence"
    ][
        "partial"
    ] == 1

    assert metadata[
        "exclusion_reason_counts"
    ][
        "<null>"
    ] == 1

    assert metadata[
        "rejection_count"
    ] == 0

    assert metadata[
        "rejection_counts"
    ] == {}

    assert metadata[
        "provenance"
    ][
        "source_version"
    ] == "synthetic-v1"

    assert metadata[
        "provenance"
    ][
        "source_files"
    ][
        "roles"
    ] == "roles.csv"

    assert metadata[
        "provenance"
    ][
        "source_checksums"
    ][
        "instances"
    ] == "sha256:def"

    assert metadata[
        "provenance"
    ][
        "telemetry_window"
    ] == {
        "start": 0,
        "end": 1000,
    }

    assert metadata[
        "join_coverage_counts"
    ][
        "matched"
    ] == 1


def test_metadata_reports_rejections_by_level_and_reason():
    adapter = SyntheticMultiViewAdapter()

    result = adapter.adapt_sources(
        {
            "roles": make_role_view(),
            "instances": make_instance_view(),
            "rejected": make_rejected_instance(),
        },
        primary_view="role_occurrence",
        provenance=make_provenance(),
    )

    assert result.metadata[
        "rejection_count"
    ] == 1

    assert result.metadata[
        "rejection_counts"
    ] == {
        "instance": {
            "missing_submission_time": 1,
        }
    }


@pytest.mark.parametrize(
    "missing_key",
    [
        "source_version",
        "source_files",
        "source_checksums",
        "telemetry_window",
    ],
)
def test_missing_provenance_fails(
    missing_key,
):
    adapter = SyntheticMultiViewAdapter()
    provenance = make_provenance()
    provenance.pop(
        missing_key
    )

    with pytest.raises(
        AdapterValidationError,
        match="provenance",
    ):
        adapter.adapt_sources(
            {
                "roles": make_role_view(),
                "instances": make_instance_view(),
            },
            primary_view="role_occurrence",
            provenance=provenance,
        )


def test_missing_parent_role_fails_linkage():
    instance_view = make_instance_view()

    instance_view.loc[
        0,
        "role_key",
    ] = "missing-role"

    with pytest.raises(
        AdapterValidationError,
        match="orphan_count=1",
    ):
        validate_role_instance_linkage(
            make_role_view(),
            instance_view,
            capabilities=TEST_CAPABILITIES,
        )


def test_missing_parent_role_fails_adapt_sources():
    adapter = SyntheticMultiViewAdapter()
    instance_view = make_instance_view()

    instance_view.loc[
        0,
        "role_key",
    ] = "missing-role"

    with pytest.raises(
        AdapterValidationError,
        match="orphan_count=1",
    ):
        adapter.adapt_sources(
            {
                "roles": make_role_view(),
                "instances": instance_view,
            },
            primary_view="role_occurrence",
            provenance=make_provenance(),
        )


def test_null_instance_role_key_fails():
    instance_view = make_instance_view()

    instance_view.loc[
        0,
        "role_key",
    ] = None

    with pytest.raises(
        AdapterValidationError,
    ):
        validate_role_instance_linkage(
            make_role_view(),
            instance_view,
            capabilities=TEST_CAPABILITIES,
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
def test_mismatched_parent_identity_fails(
    field,
    new_value,
):
    instance_view = make_instance_view()

    instance_view.loc[
        0,
        field,
    ] = new_value

    with pytest.raises(
        AdapterValidationError,
        match="identity_mismatch_count=1",
    ):
        validate_role_instance_linkage(
            make_role_view(),
            instance_view,
            capabilities=TEST_CAPABILITIES,
        )


def test_null_parent_identity_values_compare_equal_through_adapter():
    role_view = make_role_view()
    instance_view = make_instance_view()

    role_view.loc[
        0,
        "recurrence_key",
    ] = None

    role_view.loc[
        0,
        "exclusion_reason",
    ] = "no_recurrence_key"

    instance_view.loc[
        0,
        "recurrence_key",
    ] = None

    result = SyntheticMultiViewAdapter().adapt_sources(
        {
            "roles": role_view,
            "instances": instance_view,
        },
        primary_view="role_occurrence",
        provenance=make_provenance(),
    )

    assert len(
        result.views["instance"]
    ) == 1


def test_instance_event_time_must_match_parent_submission():
    instance_view = make_instance_view()

    instance_view.loc[
        0,
        "event_time_us",
    ] = 101

    with pytest.raises(
        AdapterValidationError,
        match="event_time_mismatch_count=1",
    ):
        validate_role_instance_linkage(
            make_role_view(),
            instance_view,
            capabilities=TEST_CAPABILITIES,
        )


def test_instance_event_time_must_be_present():
    instance_view = make_instance_view()

    instance_view.loc[
        0,
        "event_time_us",
    ] = None

    with pytest.raises(
        AdapterValidationError,
        match="event_time_mismatch_count=1",
    ):
        validate_role_instance_linkage(
            make_role_view(),
            instance_view,
            capabilities=TEST_CAPABILITIES,
        )


def test_linkage_validation_does_not_modify_identity_fields():
    role_view = make_role_view()
    instance_view = make_instance_view()

    role_original = role_view.copy(
        deep=True
    )

    instance_original = (
        instance_view.copy(
            deep=True
        )
    )

    validate_role_instance_linkage(
        role_view,
        instance_view,
        capabilities=TEST_CAPABILITIES,
    )

    pd.testing.assert_frame_equal(
        role_view,
        role_original,
    )

    pd.testing.assert_frame_equal(
        instance_view,
        instance_original,
    )


def test_multiview_path_does_not_modify_caller_sources():
    roles = make_role_view()
    instances = make_instance_view()

    roles_original = roles.copy(
        deep=True
    )

    instances_original = (
        instances.copy(
            deep=True
        )
    )

    MutatingPreparationAdapter().adapt_sources(
        {
            "roles": roles,
            "instances": instances,
        },
        primary_view="role_occurrence",
        provenance=make_provenance(),
    )

    pd.testing.assert_frame_equal(
        roles,
        roles_original,
    )

    pd.testing.assert_frame_equal(
        instances,
        instances_original,
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
            },
            provenance=make_provenance(),
        )
