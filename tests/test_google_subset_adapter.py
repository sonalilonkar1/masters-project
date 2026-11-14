"""Adapter contract and independent equivalence checks for Google Task 13."""

import pandas as pd
import pytest

from src.adapters import GoogleSubsetAdapter, attach_google_precomputed_targets
from src.adapters.base import BaseDatasetAdapter
from src.adapters.validation import AdapterValidationError, validate_adapter_output
from src.canonical.schema import GOOGLE_CAPABILITIES, SCHEMA_VERSION
from test_google_canonical_contract import (
    SPLIT_PATHS,
    build_google_canonical_contract_view,
)


def _load_occurrences(paths):
    """Preserve source-file membership; the saved files contain no split field."""
    for path in paths.values():
        if not path.exists():
            pytest.skip(f"Existing Google occurrence artifact not available: {path}")
    frames = []
    for split, path in paths.items():
        frame = pd.read_parquet(path)
        # Future artifacts may already carry split labels; never overwrite them.
        if "split" not in frame:
            frame = frame.assign(split=split)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


@pytest.fixture(params=["synthetic", "artifacts"])
def occurrences(request):
    if request.param == "artifacts":
        return _load_occurrences(SPLIT_PATHS)
    # Different null patterns and cross-split targets are intentional.
    return pd.DataFrame({
        "recurrence_key": ["a", "b", "a", "b"],
        "occurrence_key": ["a||1", "b||1", "a||2", "b||2"],
        "execution_start_time_us": [0, 10, 20, 30],
        "occurrence_end_time_us": [5, 15, 25, 35],
        "occurrence_runtime_us": [5, 5, 5, 5],
        "occurrence_requested_cpu_ncu": [1.0, 2.0, 3.0, 4.0],
        "occurrence_requested_memory_normalized": [0.1, 0.2, 0.3, 0.4],
        "occurrence_peak_cpu_ncu": [0.5, 1.0, 1.5, 2.0],
        "occurrence_peak_memory_normalized": [0.05, 0.1, 0.15, 0.2],
        "target_cpu_next_occurrence_peak_ncu": [1.5, 2.0, None, None],
        "target_memory_next_occurrence_peak_normalized": [0.15, None, None, None],
        "split": ["train", "validation", "test", "test"],
    }, index=pd.Index([9, 4, 7, 2], name="source_row"))


def test_adapter_validates_current_fields_and_preserves_rows(occurrences):
    source = occurrences.drop(columns="split")
    before = source.copy(deep=True)
    adapter = GoogleSubsetAdapter()
    assert GoogleSubsetAdapter.adapt is BaseDatasetAdapter.adapt
    assert adapter.capabilities is GOOGLE_CAPABILITIES
    result = adapter.adapt(source)
    view = result.canonical
    validate_adapter_output(view, capabilities=GOOGLE_CAPABILITIES)
    assert len(view) == len(source)
    assert view.occurrence_id.is_unique
    pd.testing.assert_series_equal(
        view.occurrence_id, source.occurrence_key, check_names=False
    )
    assert "split" not in view
    assert not any(c.startswith("actual_") or c.endswith("target_status") for c in view)
    assert view.validity_status.eq("valid").all()
    assert view.exclusion_reason.isna().all()
    assert result.views == {"canonical": view}
    assert result.metadata["schema_version"] == SCHEMA_VERSION
    assert result.metadata["dataset_id"] == GOOGLE_CAPABILITIES.dataset_id
    assert result.metadata["source_row_count"] == len(source)
    assert result.metadata["canonical_row_count"] == len(source)
    pd.testing.assert_frame_equal(source, before)


def test_attached_view_equals_independent_contract_and_preserves_inputs(occurrences):
    original = occurrences.copy(deep=True)
    view = GoogleSubsetAdapter().adapt(occurrences.drop(columns="split")).canonical
    before = view.copy(deep=True)
    # Reverse the source order: attachment must join by identity, not position.
    attached = attach_google_precomputed_targets(view, occurrences.iloc[::-1])
    reference = build_google_canonical_contract_view(occurrences)
    shared = list(reference.columns)
    pd.testing.assert_frame_equal(attached[shared], reference)
    pd.testing.assert_series_equal(
        attached[shared].isna().sum(), reference.isna().sum()
    )
    pd.testing.assert_series_equal(attached.split, occurrences.split)
    pd.testing.assert_frame_equal(view, before)
    pd.testing.assert_frame_equal(occurrences, original)
    # The returned frame must not alias the adapter's view.
    attached.loc[:, "requested_cpu"] = 999.0
    pd.testing.assert_frame_equal(view, before)


def test_adapter_does_not_require_targets_or_split(occurrences):
    current = occurrences.drop(columns=[
        "split", "target_cpu_next_occurrence_peak_ncu",
        "target_memory_next_occurrence_peak_normalized",
    ])
    view = GoogleSubsetAdapter().adapt(current).canonical
    assert len(view) == len(current)


def test_adapter_rejects_duplicate_occurrences(occurrences):
    source = occurrences.drop(columns="split")
    duplicated = pd.concat([source, source.iloc[[0]]], ignore_index=True)
    with pytest.raises(AdapterValidationError, match="Duplicate canonical occurrence"):
        GoogleSubsetAdapter().adapt(duplicated)


def test_attachment_rejects_duplicate_or_missing_matches(occurrences):
    view = GoogleSubsetAdapter().adapt(occurrences.drop(columns="split")).canonical
    duplicated = pd.concat([occurrences, occurrences.iloc[[0]]], ignore_index=True)
    with pytest.raises(pd.errors.MergeError):
        attach_google_precomputed_targets(view, duplicated)
    with pytest.raises(ValueError, match="must match"):
        attach_google_precomputed_targets(view, occurrences.iloc[1:])


def test_missing_artifacts_skip_without_loading_partial_data(tmp_path, monkeypatch):
    def unexpected_read(*args, **kwargs):
        pytest.fail("Missing artifacts should be detected before loading")

    monkeypatch.setattr(pd, "read_parquet", unexpected_read)
    with pytest.raises(
        pytest.skip.Exception, match="Existing Google occurrence artifact not available"
    ):
        _load_occurrences({"train": tmp_path / "missing.parquet"})


@pytest.mark.parametrize("invalid_split", [None, pd.NA, float("nan")])
def test_attachment_rejects_null_split_labels(occurrences, invalid_split):
    view = GoogleSubsetAdapter().adapt(occurrences.drop(columns="split")).canonical
    source = occurrences.copy(deep=True)
    source.loc[source.index[0], "split"] = invalid_split
    with pytest.raises(ValueError, match="Source split labels must not be null"):
        attach_google_precomputed_targets(view, source)


@pytest.mark.parametrize("invalid_split", ["val", "", "TRAIN"])
def test_attachment_rejects_unsupported_split_labels(occurrences, invalid_split):
    view = GoogleSubsetAdapter().adapt(occurrences.drop(columns="split")).canonical
    source = occurrences.copy(deep=True)
    source.loc[source.index[0], "split"] = invalid_split
    with pytest.raises(
        ValueError, match="Source split labels must be one of: train, validation, test"
    ):
        attach_google_precomputed_targets(view, source)
