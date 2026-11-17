import importlib.util
import json
import shutil
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from src.service import api
from src.service.bundle import BundleIntegrityError, verify_bundle

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "ui_bundle"
GOOGLE = "google_clusterdata2019"
ALIBABA = "alibaba_gpu_v2020"


@pytest.fixture(scope="module")
def client():
    return TestClient(api.create_app(FIXTURE_DIR))


def url(dataset, workload=None, endpoint=None):
    path = f"/api/v1/datasets/{dataset}"
    if workload is not None:
        path += f"/workloads/{quote(workload, safe='')}/{endpoint}"
    return path


def resource(item, name):
    return next(r for r in item["resources"] if r["resource"] == name)


def assert_error(response, status, code):
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"} and body["error"]["code"] == code and body["error"]["message"]


# --- health, datasets, risk levels ---------------------------------------------------


def test_health_reports_bundle(client):
    body = client.get("/api/v1/health").json()

    assert body["status"] == "ok"
    assert body["bundle_status"] == "development"
    assert body["bundle_checksum"] == verify_bundle(FIXTURE_DIR)
    assert [d["dataset_id"] for d in body["datasets"]] == [GOOGLE, ALIBABA]
    assert all(d["source_mismatch_count"] == 0 for d in body["datasets"])


def test_datasets_units_semantics_and_order(client):
    datasets = {d["dataset_id"]: d for d in client.get("/api/v1/datasets").json()["datasets"]}

    alibaba = datasets[ALIBABA]
    assert [r["resource"] for r in alibaba["resources"]] == ["memory", "cpu"]
    cpu = resource(alibaba, "cpu")
    assert (cpu["unit"], cpu["semantics"], cpu["label"]) == ("percent_of_vcpu", "average_usage", "Average usage, not peak")
    assert alibaba["min_runs"] == 10 and datasets[GOOGLE]["min_runs"] == 1
    assert [r["resource"] for r in datasets[GOOGLE]["resources"]] == ["cpu", "memory"]
    assert datasets[GOOGLE]["population"]["workloads"] == 2


def test_risk_levels(client):
    body = client.get("/api/v1/risk-levels").json()

    assert body["default_risk_level"] == "restrictive"
    levels = {level["risk_level"]: level for level in body["risk_levels"]}
    assert levels["restrictive"]["is_default"] and not levels["efficient"]["is_default"]
    assert levels["restrictive"]["policies"][ALIBABA] == {"policy": "Hybrid", "policy_id": "hybrid"}
    assert levels["efficient"]["policies"][GOOGLE]["policy_id"] == "p90"


# --- workloads -----------------------------------------------------------------------


def test_workloads_default_sort_by_test_runs(client):
    body = client.get(url(ALIBABA) + "/workloads").json()

    assert body["total"] == 2
    assert [w["workload_id"] for w in body["items"]] == ["G||A", "G||B"]
    assert body["items"][0]["test_run_count"] == 3


def test_workloads_filters_search_and_paging(client):
    with_history = client.get(url(ALIBABA) + "/workloads", params={"has_history": "true"}).json()
    assert [w["workload_id"] for w in with_history["items"]] == ["G||A"]

    searched = client.get(url(ALIBABA) + "/workloads", params={"search": "g / b"}).json()
    assert [w["workload_id"] for w in searched["items"]] == ["G||B"]

    page = client.get(url(GOOGLE) + "/workloads", params={"sort": "id", "limit": 1, "offset": 1}).json()
    assert (page["total"], page["limit"], page["offset"]) == (2, 1, 1)
    assert [w["workload_id"] for w in page["items"]] == ["u||A"]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": api.MAX_LIMIT + 1}, {"offset": -1}, {"sort": "size"}, {"has_history": "maybe"}])
def test_workloads_invalid_parameters(client, params):
    assert_error(client.get(url(GOOGLE) + "/workloads", params=params), 400, "invalid_parameter")


def test_unknown_dataset(client):
    assert_error(client.get(url("azure_vm") + "/workloads"), 404, "not_found")
    assert_error(client.get(url("azure_vm") + "/policies"), 404, "not_found")


# --- recommendation ------------------------------------------------------------------


def test_recommendation_defaults_to_restrictive(client):
    body = client.get(url(ALIBABA, "G||A", "recommendation")).json()

    assert (body["risk_level"], body["policy"], body["policy_id"]) == ("restrictive", "Hybrid", "hybrid")
    assert body["latest_run"] == {"occurrence_id": "G||J3", "role_key": "G||J3||A", "start_time_us": 200}
    assert [r["resource"] for r in body["resources"]] == ["memory", "cpu"]
    memory = resource(body, "memory")
    assert memory["unit"] == "gb" and memory["basis"] == {"type": "history", "history_run_count": 11}
    assert resource(body, "cpu")["label"] == "Average usage, not peak"
    assert body["same_for_all_risk_levels"] is False
    assert body["bundle"]["bundle_checksum"] == verify_bundle(FIXTURE_DIR)


def test_recommendation_evidence_is_the_policy_row(client):
    body = client.get(url(ALIBABA, "G||A", "recommendation"), params={"risk": "balanced"}).json()
    metrics = json.loads((FIXTURE_DIR / ALIBABA / "policy_metrics.json").read_text())
    p95 = next(row for row in metrics["policies"] if row["policy"] == "P95")

    evidence = body["policy_evidence"]
    assert evidence["policy"] == "P95" and evidence["risk_levels"] == ["balanced"]
    assert resource(evidence, "memory")["violation_pct"] == p95["memory_violation_pct"]
    assert resource(evidence, "cpu")["valid_violation_count"] == p95["valid_cpu_violation_count"]
    assert evidence["any_resource"] is None
    assert body["rule"]["min_runs"] == 10 and "95th percentile" in body["rule"]["description"]


def test_recommendation_fallback_is_same_for_all_risk_levels(client):
    body = client.get(url(ALIBABA, "G||B", "recommendation")).json()

    assert all(r["basis"]["type"] == "request_fallback" for r in body["resources"])
    assert all(r["recommended"] == r["request"] for r in body["resources"])
    assert body["same_for_all_risk_levels"] is True


def test_recommendation_workload_id_with_slash(client):
    body = client.get(url(GOOGLE, "u/2||B", "recommendation")).json()
    unencoded = client.get(f"/api/v1/datasets/{GOOGLE}/workloads/u/2||B/recommendation").json()

    assert body["workload_id"] == unencoded["workload_id"] == "u/2||B"
    # No request and no history: Hybrid is the ML value alone, with basis "model".
    assert resource(body, "cpu")["basis"]["type"] == "model"
    assert resource(body, "cpu")["recommended"] is not None


def test_recommendation_missing_values_are_null(client):
    body = client.get(url(GOOGLE, "u/2||B", "recommendation"), params={"policy": "request"}).json()

    assert body["risk_level"] is None and body["policy"] == "Request"
    for item in body["resources"]:
        assert item["request"] is None and item["recommended"] is None
        assert item["basis"] == {"type": "request", "history_run_count": None}
    assert body["rule"]["min_runs"] is None


@pytest.mark.parametrize(
    ("params", "code", "status"),
    [
        ({"risk": "reckless"}, "invalid_parameter", 400),
        ({"policy": "p80"}, "invalid_parameter", 400),
        ({"risk": "balanced", "policy": "p99"}, "invalid_parameter", 400),
    ],
)
def test_recommendation_invalid_choice(client, params, code, status):
    assert_error(client.get(url(ALIBABA, "G||A", "recommendation"), params=params), status, code)


def test_recommendation_unknown_workload(client):
    assert_error(client.get(url(ALIBABA, "G||Z", "recommendation")), 404, "not_found")
    assert_error(client.get(url(GOOGLE, "G||A", "recommendation")), 404, "not_found")  # no cross-dataset lookups


# --- history -------------------------------------------------------------------------


def test_history_pairs_each_run_with_the_next(client):
    body = client.get(url(ALIBABA, "G||A", "history"), params={"policy": "p99"}).json()

    assert "next run" in body["comparison"]
    items = body["items"]
    assert [i["occurrence_id"] for i in items] == ["G||J1", "G||J2", "G||J3"]
    assert (items[0]["target_occurrence_id"], items[0]["target_start_time_us"]) == ("G||J2", 200)
    assert [r["resource"] for r in items[0]["resources"]] == ["memory", "cpu"]
    cpu = resource(items[1], "cpu")
    assert cpu["target_status"] == "next_occurrence_ineligible_resource"
    assert cpu["actual"] is None and cpu["exceeded"] is None
    last = items[2]
    assert last["target_occurrence_id"] is None and resource(last, "memory")["target_status"] == "no_next_occurrence"


def test_history_without_scored_runs(client):
    items = client.get(url(ALIBABA, "G||B", "history")).json()["items"]

    assert len(items) == 1 and all(r["actual"] is None for r in items[0]["resources"])


# --- policies ------------------------------------------------------------------------


def test_policies_all_seven_with_risk_levels(client):
    body = client.get(url(GOOGLE) + "/policies").json()

    assert [p["policy_id"] for p in body["policies"]] == ["request", "mean", "p90", "p95", "p99", "ml", "hybrid"]
    marked = {p["policy"]: p["risk_levels"] for p in body["policies"]}
    assert marked == {"Request": [], "Mean": [], "P90": ["efficient"], "P95": ["balanced"], "P99": [], "ML": [], "Hybrid": ["restrictive"]}
    assert body["policies"][0]["any_resource"]["violation_pct"] is not None  # Google reports any-resource
    alibaba = client.get(url(ALIBABA) + "/policies").json()
    assert all(p["any_resource"] is None for p in alibaba["policies"])


# --- routes, errors and startup ------------------------------------------------------


def test_only_get_routes(client):
    for route in client.app.routes:
        if route.path.startswith("/api/"):
            assert route.methods <= {"GET", "HEAD"}, route.path
    assert_error(client.post("/api/v1/health"), 405, "method_not_allowed")
    assert_error(client.get("/api/v1/unknown"), 404, "not_found")


def test_changed_bundle_refuses_to_start(tmp_path):
    bundle = tmp_path / "ui"
    shutil.copytree(FIXTURE_DIR, bundle)
    (bundle / "rules.json").write_text("{}\n")

    with pytest.raises(BundleIntegrityError, match="changed: rules.json"):
        api.create_app(bundle)


def test_missing_bundle_refuses_to_start(tmp_path):
    with pytest.raises(BundleIntegrityError, match="not found"):
        api.create_app(tmp_path / "absent")


def test_bundle_folder_from_environment(monkeypatch):
    monkeypatch.setenv(api.BUNDLE_ENV, str(FIXTURE_DIR))

    assert api.create_app().state.bundle.path == FIXTURE_DIR


# --- OpenAPI contract ----------------------------------------------------------------

OPENAPI_PATH = REPO_ROOT / "docs" / "design" / "recommendation_api_openapi.json"


def test_committed_openapi_matches_app():
    spec = importlib.util.spec_from_file_location("export_openapi", REPO_ROOT / "scripts" / "export_openapi.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)

    assert OPENAPI_PATH.read_text() == script.openapi_text(), "run python3 scripts/export_openapi.py"


def test_openapi_documents_the_common_error_body(client):
    schema = client.get("/openapi.json").json()

    for path in schema["paths"].values():
        responses = path["get"]["responses"]
        assert "422" not in responses
        assert responses["400"]["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorResponse")
    assert "HTTPValidationError" not in schema["components"]["schemas"]
