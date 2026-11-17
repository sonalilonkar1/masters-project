import json
from pathlib import Path

import pandas as pd

from src.service.bundle import bundle_files, verify_bundle
from src.service.export import write_bundle
from ui_sources import fixture_contents

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "ui_bundle"


def recommendations(dataset_id):
    return pd.read_parquet(FIXTURE_DIR / dataset_id / "recommendations.parquet")


def pick(frame, occurrence_id, policy):
    match = frame[(frame["occurrence_id"] == occurrence_id) & (frame["policy"] == policy)]
    assert len(match) == 1
    return match.iloc[0]


def test_committed_fixture_passes_its_checksums():
    verify_bundle(FIXTURE_DIR)


def test_committed_fixture_matches_generator(tmp_path):
    """Content, not bytes: Parquet files record the pyarrow version that wrote them."""
    regenerated = tmp_path / "ui_bundle"
    write_bundle(fixture_contents(REPO_ROOT), regenerated)

    assert bundle_files(regenerated) == bundle_files(FIXTURE_DIR)
    for name in bundle_files(FIXTURE_DIR):
        if name.endswith(".parquet"):
            pd.testing.assert_frame_equal(pd.read_parquet(FIXTURE_DIR / name), pd.read_parquet(regenerated / name), check_exact=True)
        else:
            assert json.loads((FIXTURE_DIR / name).read_text()) == json.loads((regenerated / name).read_text()), (
                f"{name} is stale; run python3 tests/fixtures/make_ui_bundle.py"
            )


def test_fixture_is_marked_development_and_synthetic():
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text())

    assert manifest["bundle_status"] == "development"
    assert "Synthetic" in manifest["fixture"]


def test_fixture_covers_the_edge_cases():
    google = recommendations("google_clusterdata2019")
    alibaba = recommendations("alibaba_gpu_v2020")

    # History and request fallback
    assert pick(google, "a2", "P95")["cpu_basis"] == "history"
    assert pick(google, "a1", "P95")["cpu_basis"] == "request_fallback"
    # Missing request stays null; Hybrid without a safeguard is the ML value with basis "model"
    assert pd.isna(pick(google, "b1", "Request")["request_cpu"])
    assert pick(google, "b1", "Hybrid")["cpu_basis"] == "model"
    # Ineligible CPU target next to an available memory target
    tied = pick(alibaba, "G||J2", "Hybrid")
    assert tied["cpu_target_status"] == "next_occurrence_ineligible_resource"
    assert tied["memory_target_status"] == "available"
    # CPU falls back while memory uses history
    assert (tied["cpu_basis"], tied["memory_basis"]) == ("request_fallback", "history")


def test_fixture_has_workloads_with_and_without_scored_runs():
    for dataset_id in ("google_clusterdata2019", "alibaba_gpu_v2020"):
        workloads = pd.read_parquet(FIXTURE_DIR / dataset_id / "workloads.parquet")
        assert set(workloads["has_scored_history"]) == {True, False}
        assert set(workloads["latest_uses_history"]) == {True, False}
