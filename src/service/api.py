"""Read-only recommendation API (Task 15 Part C).

Serves one checksummed UI bundle under /api/v1. The bundle is verified and
loaded once at startup; no route runs pipeline code or writes files.

    TRACEADVISOR_UI_BUNDLE=data/processed/ui_dev uvicorn --factory src.service.api:create_app

Without TRACEADVISOR_UI_BUNDLE the verified bundle in reports/results/ui/ is served.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.service import schemas
from src.service.bundle import LoadedBundle, LoadedDataset, load_bundle
from src.service.contract import DATASET_IDS, POLICY_BY_ID, POLICY_IDS, POLICY_NAMES, error_body

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUNDLE_DIR = REPO_ROOT / "reports" / "results" / "ui"
UI_DIR = REPO_ROOT / "web"
BUNDLE_ENV = "TRACEADVISOR_UI_BUNDLE"
MAX_LIMIT = 200
DEFAULT_LIMIT = 50
RESOURCES = ("cpu", "memory")
HISTORY_COMPARISON = (
    "Each item is the recommendation made for one run (start_time_us), compared with what the next run "
    "of the same workload used (target_start_time_us). Runs without a next run have no actual value."
)
PERCENTILE_NAMES = {"P90": "90th", "P95": "95th", "P99": "99th"}


ERROR_RESPONSES = {
    400: {"model": schemas.ErrorResponse, "description": "Invalid or conflicting query parameters"},
    404: {"model": schemas.ErrorResponse, "description": "Unknown dataset, workload or route, or a policy the dataset does not have"},
    405: {"model": schemas.ErrorResponse, "description": "Only GET is supported"},
    500: {"model": schemas.ErrorResponse, "description": "Unexpected server error"},
}


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code, self.code, self.message = status_code, code, message


# --- Value helpers ---------------------------------------------------------------


def _value(value):
    """pandas/NumPy value -> JSON value; every kind of missing becomes None."""
    if value is None or value is pd.NA:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
        if isinstance(value, float) and math.isnan(value):
            return None
    return value


def _resource_order(dataset: LoadedDataset) -> list[str]:
    primary = dataset.info["primary_resource"]
    return [primary, *[r for r in RESOURCES if r != primary]] if primary else list(RESOURCES)


def _resource_label(dataset: LoadedDataset, resource: str) -> dict:
    """Resource name, unit, semantics and label: carried by every resource value the API returns."""
    info = _resource_info(dataset, resource)
    return {k: info[k] for k in ("resource", "unit", "semantics", "label")}


def _resource_info(dataset: LoadedDataset, resource: str) -> dict:
    spec = dataset.info["resources"][resource]
    average = "average" in spec["semantics"]
    return {
        "resource": resource,
        "unit": spec["unit"],
        "semantics": "average_usage" if average else "peak",
        "label": "Average usage, not peak" if average else "Peak usage",
        "target_semantics": spec["semantics"],
        "description": spec["description"],
    }


# --- The application ---------------------------------------------------------------


def create_app(bundle_dir: Optional[Path] = None) -> FastAPI:
    """Build the app around one bundle; fails at startup if the bundle does not verify."""
    bundle_dir = Path(bundle_dir or os.environ.get(BUNDLE_ENV) or DEFAULT_BUNDLE_DIR)
    bundle = load_bundle(bundle_dir)

    app = FastAPI(
        title="TraceAdvisor recommendation API",
        version=bundle.manifest["bundle_schema_version"],
        description="Read-only CPU and memory recommendations from the TraceAdvisor final-test bundle.",
    )
    app.state.bundle = bundle
    _add_error_handlers(app)
    _add_routes(app, bundle)
    _add_ui_routes(app)
    _document_errors_as_400(app)
    return app


def _document_errors_as_400(app: FastAPI) -> None:
    """Invalid parameters return 400 with the common error body, so drop FastAPI's default 422 schema."""
    default_openapi = app.openapi

    def openapi() -> dict:
        if app.openapi_schema is None:
            schema = default_openapi()
            for path in schema["paths"].values():
                for operation in path.values():
                    operation["responses"].pop("422", None)
            for name in ("HTTPValidationError", "ValidationError"):
                schema.get("components", {}).get("schemas", {}).pop(name, None)
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi


def _add_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(request: Request, error: ApiError):
        return JSONResponse(error_body(error.code, error.message), status_code=error.status_code)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError):
        details = "; ".join(f"{'.'.join(str(p) for p in item['loc'][1:])}: {item['msg']}" for item in error.errors())
        return JSONResponse(error_body("invalid_parameter", details), status_code=400)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, error: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(error.status_code, "invalid_parameter")
        return JSONResponse(error_body(code, str(error.detail)), status_code=error.status_code)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, error: Exception):
        return JSONResponse(error_body("internal_error", "Unexpected server error"), status_code=500)


def _add_ui_routes(app: FastAPI) -> None:
    """Serve the Task 16 static frontend from the same read-only FastAPI process.

    These GET-only routes are intentionally excluded from the API/OpenAPI contract so
    Task 15's /api/v1 schema stays frozen. The frontend only calls /api/v1 and does
    not read bundle files directly.
    """

    index = UI_DIR / "index.html"
    assets = {
        "app.js": UI_DIR / "app.js",
        "styles.css": UI_DIR / "styles.css",
    }

    @app.get("/", include_in_schema=False)
    @app.get("/ui", include_in_schema=False)
    def ui_index():
        return FileResponse(index, media_type="text/html")

    @app.get("/ui/{asset_name}", include_in_schema=False)
    def ui_asset(asset_name: str):
        path = assets.get(asset_name)
        if path is None:
            raise ApiError(404, "not_found", f"Unknown UI asset {asset_name!r}")
        media_type = "text/javascript" if asset_name.endswith(".js") else "text/css"
        return FileResponse(path, media_type=media_type)


def _add_routes(app: FastAPI, bundle: LoadedBundle) -> None:
    # Policies each dataset has, in display order; load_bundle checks recommendations and metrics agree.
    dataset_policies = {
        d: [p for p in POLICY_NAMES if any(row["policy"] == p for row in dataset.policy_metrics["policies"])]
        for d, dataset in bundle.datasets.items()
    }
    available_datasets = {policy: [d for d in bundle.datasets if policy in dataset_policies[d]] for policy in POLICY_NAMES}

    def dataset_or_404(dataset_id: str) -> LoadedDataset:
        if dataset_id not in bundle.datasets:
            raise ApiError(404, "not_found", f"Unknown dataset {dataset_id!r}; expected one of {list(DATASET_IDS)}")
        return bundle.datasets[dataset_id]

    def workload_or_404(dataset: LoadedDataset, dataset_id: str, workload_id: str) -> pd.Series:
        if workload_id not in dataset.workloads.index:
            raise ApiError(404, "not_found", f"Unknown workload {workload_id!r} in {dataset_id}")
        return dataset.workloads.loc[workload_id]

    def choose_policy(dataset_id: str, risk: Optional[str], policy: Optional[str]) -> tuple[Optional[str], str]:
        """(risk level, policy name) from exactly one of ?risk= and ?policy=, defaulting to the default risk level."""
        if risk is not None and policy is not None:
            raise ApiError(400, "invalid_parameter", "Give either risk or policy, not both")
        mapping = bundle.risk_levels["datasets"][dataset_id]
        if policy is not None:
            if policy not in POLICY_BY_ID:
                raise ApiError(400, "invalid_parameter", f"Unknown policy {policy!r}; expected one of {sorted(POLICY_BY_ID)}")
            if POLICY_BY_ID[policy] not in dataset_policies[dataset_id]:
                raise ApiError(404, "not_found", f"Policy {POLICY_BY_ID[policy]} is not available for {dataset_id}")
            return None, POLICY_BY_ID[policy]
        if risk is None:
            risk = bundle.risk_levels["default_risk_level"]
        if risk not in mapping:
            raise ApiError(400, "invalid_parameter", f"Unknown risk level {risk!r}; expected one of {list(mapping)}")
        return risk, mapping[risk]["policy"]

    def risk_levels_of(dataset_id: str, policy: str) -> list[str]:
        mapping = bundle.risk_levels["datasets"][dataset_id]
        return [level["risk_level"] for level in bundle.risk_levels["risk_levels"] if mapping[level["risk_level"]]["policy"] == policy]

    def policy_metrics(dataset_id: str, dataset: LoadedDataset, row: dict) -> dict:
        resources = []
        for resource in _resource_order(dataset):
            resources.append(
                {
                    **_resource_label(dataset, resource),
                    "violation_pct": row.get(f"{resource}_violation_pct"),
                    "valid_violation_count": row.get(f"valid_{resource}_violation_count"),
                    "average_utilization": row.get(f"average_{resource}_utilization"),
                    "valid_utilization_count": row.get(f"valid_{resource}_utilization_count"),
                    "average_waste": row.get(f"average_{resource}_waste"),
                    "average_shortfall": row.get(f"average_{resource}_shortfall"),
                }
            )
        any_resource = None
        if "any_resource_violation_pct" in row:
            any_resource = {
                "violation_pct": row["any_resource_violation_pct"],
                "valid_violation_count": row.get("valid_any_resource_violation_count"),
            }
        return {
            "policy": row["policy"],
            "policy_id": POLICY_IDS[row["policy"]],
            "risk_levels": risk_levels_of(dataset_id, row["policy"]),
            "available_datasets": available_datasets[row["policy"]],
            "row_count": row["row_count"],
            "resources": resources,
            "any_resource": any_resource,
        }

    def metrics_for(dataset_id: str, dataset: LoadedDataset, policy: str) -> dict:
        row = next(r for r in dataset.policy_metrics["policies"] if r["policy"] == policy)
        return policy_metrics(dataset_id, dataset, row)

    def rule_for(dataset_id: str, policy: str) -> dict:
        rules = bundle.rules[dataset_id]
        min_runs, safeguard, model = rules["min_runs"], rules["hybrid_safeguard_policy"], None
        fallback = f"with fewer than {min_runs} earlier runs, the original request is kept"
        if policy == "Request":
            description, min_runs = "The original request, unchanged.", None
        elif policy == "Mean":
            description = f"Mean usage of the workload's earlier runs; {fallback}."
        elif policy in PERCENTILE_NAMES:
            description = f"{PERCENTILE_NAMES[policy]} percentile of the workload's earlier runs; {fallback}."
        elif policy == "ML":
            description, min_runs, model = "Prediction of the machine-learning model trained on earlier runs.", None, rules["ml_models"]
        else:
            description = (
                f"Larger of the ML prediction and the {safeguard} of the workload's earlier runs ({rules['hybrid_rule']}); "
                f"the {safeguard} itself keeps the original request with fewer than {min_runs} earlier runs, "
                f"and where it is unavailable the ML prediction is used alone."
            )
            model = rules["ml_models"]
        return {
            "policy": policy,
            "description": description,
            "min_runs": min_runs,
            "safeguard_policy": safeguard if policy == "Hybrid" else None,
            "ml_model": model,
            "source": rules["source"],
        }

    def latest_row(dataset_id: str, workload_id: str, policy: str) -> pd.Series:
        rows = bundle.rows(dataset_id, workload_id, policy)
        latest = rows[rows["is_latest"]]
        if len(latest) != 1:
            raise ApiError(500, "internal_error", "Bundle has no single latest run for this workload")
        return latest.iloc[0]

    def same_for_all_risk_levels(dataset_id: str, workload_id: str) -> bool:
        values = set()
        for mapping in bundle.risk_levels["datasets"][dataset_id].values():
            row = latest_row(dataset_id, workload_id, mapping["policy"])
            values.add(tuple(_value(row[f"recommended_{r}"]) for r in RESOURCES))
        return len(values) == 1

    # --- Routes ---

    @app.get("/api/v1/health", response_model=schemas.Health, responses=ERROR_RESPONSES)
    def health():
        manifest = bundle.manifest
        return {
            "status": "ok",
            "bundle_status": manifest["bundle_status"],
            "bundle_schema_version": manifest["bundle_schema_version"],
            "bundle_checksum": bundle.checksum,
            "export_commit": manifest["export"].get("code_commit"),
            "export_timestamp_utc": manifest["export"].get("timestamp_utc"),
            "datasets": [
                {
                    "dataset_id": dataset_id,
                    "bundle_status": dataset.metadata["bundle_status"],
                    "source_run_id": dataset.metadata["source_run_id"],
                    "source_mismatch_count": len(dataset.metadata["source_mismatches"]),
                }
                for dataset_id, dataset in bundle.datasets.items()
            ],
        }

    @app.get("/api/v1/datasets", response_model=schemas.DatasetList, responses=ERROR_RESPONSES)
    def datasets():
        items = []
        for dataset_id, dataset in bundle.datasets.items():
            info = dataset.info
            items.append(
                {
                    "dataset_id": dataset_id,
                    "display_name": info["display_name"],
                    "bundle_status": dataset.metadata["bundle_status"],
                    "source_run_id": dataset.metadata["source_run_id"],
                    "primary_resource": info["primary_resource"],
                    "resources": [_resource_info(dataset, r) for r in _resource_order(dataset)],
                    "evaluation_scope": info["evaluation_scope"],
                    "population": info["population"],
                    "min_runs": bundle.rules[dataset_id]["min_runs"],
                    "caveats": info["caveats"],
                }
            )
        return {"datasets": items}

    def policy_ref(name: str) -> dict:
        """A policy name with its ID, built from the name like every other response."""
        return {"policy": name, "policy_id": POLICY_IDS[name]}

    @app.get("/api/v1/risk-levels", response_model=schemas.RiskLevelList, responses=ERROR_RESPONSES)
    def risk_levels():
        config = bundle.risk_levels
        return {
            "default_risk_level": config["default_risk_level"],
            "risk_levels": [
                {
                    **level,
                    "is_default": level["risk_level"] == config["default_risk_level"],
                    "policies": {d: policy_ref(config["datasets"][d][level["risk_level"]]["policy"]) for d in bundle.datasets},
                }
                for level in config["risk_levels"]
            ],
        }

    @app.get("/api/v1/datasets/{dataset_id}/workloads", response_model=schemas.WorkloadPage, responses=ERROR_RESPONSES)
    def workloads(
        dataset_id: str,
        search: Optional[str] = Query(None, description="Case-insensitive match on workload ID or display name"),
        has_history: Optional[bool] = Query(None, description="Filter on whether the latest recommendation uses history"),
        sort: str = Query("test_runs", description="test_runs (most runs first) or id"),
        limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
        offset: int = Query(0, ge=0),
    ):
        dataset = dataset_or_404(dataset_id)
        if sort not in ("test_runs", "id"):
            raise ApiError(400, "invalid_parameter", f"Unknown sort {sort!r}; expected test_runs or id")
        frame = dataset.workloads
        if search:
            needle = search.lower()
            frame = frame[
                frame["workload_id"].str.lower().str.contains(needle, regex=False)
                | frame["display_name"].str.lower().str.contains(needle, regex=False)
            ]
        if has_history is not None:
            frame = frame[frame["latest_uses_history"] == has_history]
        if sort == "test_runs":
            frame = frame.sort_values(["test_run_count", "workload_id"], ascending=[False, True], kind="mergesort")
        else:
            frame = frame.sort_values("workload_id", kind="mergesort")
        page = frame.iloc[offset : offset + limit]
        columns = list(schemas.WorkloadSummary.model_fields)
        return {
            "dataset_id": dataset_id,
            "total": int(len(frame)),
            "limit": limit,
            "offset": offset,
            "items": [{c: _value(row[c]) for c in columns} for _, row in page.iterrows()],
        }

    @app.get("/api/v1/datasets/{dataset_id}/workloads/{workload_id:path}/recommendation", response_model=schemas.Recommendation, responses=ERROR_RESPONSES)
    def recommendation(
        dataset_id: str,
        workload_id: str,
        risk: Optional[str] = Query(None, description="restrictive, balanced or efficient (default: the default risk level)"),
        policy: Optional[str] = Query(None, description="Policy ID instead of a risk level, e.g. p99"),
    ):
        dataset = dataset_or_404(dataset_id)
        workload = workload_or_404(dataset, dataset_id, workload_id)
        risk_level, policy_name = choose_policy(dataset_id, risk, policy)
        row = latest_row(dataset_id, workload_id, policy_name)
        return {
            "dataset_id": dataset_id,
            "workload_id": workload_id,
            "display_name": workload["display_name"],
            "risk_level": risk_level,
            "policy": policy_name,
            "policy_id": POLICY_IDS[policy_name],
            "latest_run": {
                "occurrence_id": row["occurrence_id"],
                "role_key": _value(row["role_key"]),
                "start_time_us": _value(row["start_time_us"]),
            },
            "primary_resource": dataset.info["primary_resource"],
            "resources": [
                {
                    **_resource_label(dataset, r),
                    "recommended": _value(row[f"recommended_{r}"]),
                    "request": _value(row[f"request_{r}"]),
                    "basis": {"type": row[f"{r}_basis"], "history_run_count": _value(row[f"{r}_history_run_count"])},
                }
                for r in _resource_order(dataset)
            ],
            "same_for_all_risk_levels": same_for_all_risk_levels(dataset_id, workload_id),
            "rule": rule_for(dataset_id, policy_name),
            "policy_evidence": metrics_for(dataset_id, dataset, policy_name),
            "bundle": {
                "bundle_status": bundle.manifest["bundle_status"],
                "dataset_status": dataset.metadata["bundle_status"],
                "source_run_id": dataset.metadata["source_run_id"],
                "bundle_checksum": bundle.checksum,
            },
        }

    @app.get("/api/v1/datasets/{dataset_id}/workloads/{workload_id:path}/history", response_model=schemas.History, responses=ERROR_RESPONSES)
    def history(
        dataset_id: str,
        workload_id: str,
        risk: Optional[str] = Query(None),
        policy: Optional[str] = Query(None),
    ):
        dataset = dataset_or_404(dataset_id)
        workload_or_404(dataset, dataset_id, workload_id)
        risk_level, policy_name = choose_policy(dataset_id, risk, policy)
        rows = bundle.rows(dataset_id, workload_id, policy_name)
        order = _resource_order(dataset)
        items = [
            {
                "occurrence_id": row["occurrence_id"],
                "role_key": _value(row["role_key"]),
                "start_time_us": _value(row["start_time_us"]),
                "target_occurrence_id": _value(row["target_occurrence_id"]),
                "target_start_time_us": _value(row["target_start_time_us"]),
                "resources": [
                    {
                        **_resource_label(dataset, r),
                        "recommended": _value(row[f"recommended_{r}"]),
                        "actual": _value(row[f"actual_{r}"]),
                        "exceeded": _value(row[f"{r}_exceeded"]),
                        "target_status": row[f"{r}_target_status"],
                    }
                    for r in order
                ],
            }
            for _, row in rows.iterrows()
        ]
        return {
            "dataset_id": dataset_id,
            "workload_id": workload_id,
            "risk_level": risk_level,
            "policy": policy_name,
            "policy_id": POLICY_IDS[policy_name],
            "comparison": HISTORY_COMPARISON,
            "items": items,
        }

    @app.get("/api/v1/datasets/{dataset_id}/policies", response_model=schemas.PolicyList, responses=ERROR_RESPONSES)
    def policies(dataset_id: str):
        dataset = dataset_or_404(dataset_id)
        rows = {r["policy"]: r for r in dataset.policy_metrics["policies"]}
        return {
            "dataset_id": dataset_id,
            "source": dataset.policy_metrics["source"],
            "policies": [policy_metrics(dataset_id, dataset, rows[name]) for name in dataset_policies[dataset_id]],
        }
