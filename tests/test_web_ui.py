import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.service import api

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "ui_bundle"
WEB_DIR = REPO_ROOT / "web"
GOOGLE = "google_clusterdata2019"
ALIBABA = "alibaba_gpu_v2020"


@pytest.fixture(scope="module")
def client():
    return TestClient(api.create_app(FIXTURE_DIR))


def resource(item, name):
    return next(r for r in item["resources"] if r["resource"] == name)


def test_ui_routes_are_served_by_the_fixture_backed_app(client):
    root = client.get("/")
    alias = client.get("/ui")
    script = client.get("/ui/app.js")
    styles = client.get("/ui/styles.css")

    assert root.status_code == alias.status_code == 200
    assert root.text == alias.text
    assert root.headers["content-type"].startswith("text/html")
    assert script.status_code == styles.status_code == 200
    assert script.headers["content-type"].startswith("text/javascript")
    assert styles.headers["content-type"].startswith("text/css")


def test_ui_routes_do_not_change_task15_openapi_contract(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/" not in paths
    assert "/ui" not in paths
    assert not any(path.startswith("/ui/") for path in paths)
    assert all(path.startswith("/api/v1/") for path in paths)


def test_every_required_view_is_present_in_static_html():
    html = (WEB_DIR / "index.html").read_text()
    for view in (
        "dataset-workload-risk",
        "recommendation",
        "history",
        "policy-comparison",
        "about",
    ):
        assert f'data-view="{view}"' in html

    assert 'id="dataset-select"' in html
    assert 'id="workload-search"' in html
    assert 'id="show-all-workloads"' in html
    assert 'id="risk-controls"' in html
    assert 'id="workload-page-size"' in html and '<option value="200">200</option>' in html


def test_frontend_uses_api_contract_without_hard_coded_result_numbers():
    script = (WEB_DIR / "app.js").read_text()

    assert 'const API = "/api/v1"' in script
    assert "encodeURIComponent(workloadId)" in script
    assert 'params.set("has_history", "true")' in script
    assert 'sort: "test_runs"' in script
    assert "state.riskConfig.default_risk_level" in script
    assert "same_for_all_risk_levels" in script
    assert "policy_evidence" in script
    assert "bundle_checksum" in script
    assert "source_run_id" in script
    assert "svgLineChart" in script and "svgScatter" in script
    assert "http://" not in script and "https://" not in script


def test_required_display_and_error_messages_are_present():
    script = (WEB_DIR / "app.js").read_text()
    html = (WEB_DIR / "index.html").read_text()

    assert "not available" in script
    assert "Average usage, not peak" not in script  # comes from the API, never hard-coded
    assert "Risk levels give the same answer for this workload until it has enough history." in script
    assert "No request and no history: ML prediction only." in script
    assert "No scored runs yet: this workload has not run again in the test period." in script
    assert "The TraceAdvisor API is unreachable." in script
    assert "Development data bundle" in html
    assert "accessible chart data" in script.lower()


def test_ui_smoke_contract_for_both_datasets(client):
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/datasets").status_code == 200
    assert client.get("/api/v1/risk-levels").status_code == 200

    for dataset in (GOOGLE, ALIBABA):
        page = client.get(
            f"/api/v1/datasets/{dataset}/workloads",
            params={"has_history": "true", "sort": "test_runs", "limit": 20, "offset": 0},
        )
        assert page.status_code == 200
        body = page.json()
        assert body["items"]
        workload = body["items"][0]["workload_id"]

        recommendation = client.get(
            f"/api/v1/datasets/{dataset}/workloads/{workload}/recommendation",
            params={"risk": "restrictive"},
        )
        history = client.get(
            f"/api/v1/datasets/{dataset}/workloads/{workload}/history",
            params={"risk": "restrictive"},
        )
        policies = client.get(f"/api/v1/datasets/{dataset}/policies")

        assert recommendation.status_code == history.status_code == policies.status_code == 200
        assert len(policies.json()["policies"]) == 7


def test_fixture_covers_alibaba_display_rules_and_fallback_state(client):
    datasets = {d["dataset_id"]: d for d in client.get("/api/v1/datasets").json()["datasets"]}
    alibaba = datasets[ALIBABA]
    assert [r["resource"] for r in alibaba["resources"]] == ["memory", "cpu"]
    assert resource(alibaba, "cpu")["label"] == "Average usage, not peak"

    fallback = client.get(f"/api/v1/datasets/{ALIBABA}/workloads/G%7C%7CB/recommendation").json()
    assert fallback["same_for_all_risk_levels"] is True
    assert all(r["basis"]["type"] == "request_fallback" for r in fallback["resources"])


def test_fixture_covers_google_ml_only_and_empty_history_states(client):
    ml_only = client.get(
        f"/api/v1/datasets/{GOOGLE}/workloads/u%2F2%7C%7CB/recommendation"
    ).json()
    assert resource(ml_only, "cpu")["basis"]["type"] == "model"

    history = client.get(f"/api/v1/datasets/{ALIBABA}/workloads/G%7C%7CB/history").json()
    assert history["items"]
    assert all(r["actual"] is None for item in history["items"] for r in item["resources"])


def test_ui_unknown_asset_uses_structured_404(client):
    response = client.get("/ui/not-a-real-asset.js")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_javascript_syntax_when_node_is_available():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed; browser JavaScript syntax check skipped")
    result = subprocess.run(
        [node, "--check", str(WEB_DIR / "app.js")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
