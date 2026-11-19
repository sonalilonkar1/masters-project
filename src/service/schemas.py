"""Response models of the read-only recommendation API (Task 15 Part C).

Every resource value travels with its unit and meaning, missing values are
null (never 0 or omitted), and resources are an ordered list with the primary
resource first (memory on Alibaba).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class ResourceInfo(BaseModel):
    resource: str = Field(description="cpu or memory")
    unit: str
    semantics: str = Field(description="peak or average_usage")
    label: str = Field(description="Short display label, e.g. 'Average usage, not peak'")
    target_semantics: str = Field(description="What the next run's value means, from the capability profile")
    description: str


class Population(BaseModel):
    test_runs: int
    workloads: int
    scored_runs_cpu: int
    scored_runs_memory: int
    workloads_with_history_latest: int


class DatasetSummary(BaseModel):
    dataset_id: str
    display_name: str
    bundle_status: str
    source_run_id: Optional[str]
    primary_resource: Optional[str]
    resources: list[ResourceInfo]
    evaluation_scope: str
    population: Population
    min_runs: int = Field(description="Earlier runs needed before a history policy is used")
    caveats: list[str]


class DatasetList(BaseModel):
    datasets: list[DatasetSummary]


class PolicyMapping(BaseModel):
    policy: str
    policy_id: str


class RiskLevelInfo(BaseModel):
    risk_level: str
    label: str
    description: str
    is_default: bool
    policies: dict[str, PolicyMapping] = Field(description="Policy for each dataset")


class RiskLevelList(BaseModel):
    default_risk_level: str
    risk_levels: list[RiskLevelInfo]


class WorkloadSummary(BaseModel):
    workload_id: str
    display_name: str
    test_run_count: int
    scored_run_count: int
    first_start_time_us: int
    last_start_time_us: int
    latest_uses_history: bool
    has_scored_history: bool


class WorkloadPage(BaseModel):
    dataset_id: str
    total: int = Field(description="Workloads matching the filters, before paging")
    limit: int
    offset: int
    items: list[WorkloadSummary]


class Basis(BaseModel):
    type: str = Field(description="history, request_fallback, request or model")
    history_run_count: Optional[int] = Field(description="Earlier runs available; null for Request and ML")


class RecommendedResource(BaseModel):
    resource: str
    unit: str
    semantics: str
    label: str
    recommended: Optional[float]
    request: Optional[float]
    basis: Basis


class LatestRun(BaseModel):
    occurrence_id: str
    role_key: Optional[str]
    start_time_us: int


class Rule(BaseModel):
    policy: str
    description: str
    min_runs: Optional[int] = Field(description="Earlier runs needed; null when the policy does not use history")
    safeguard_policy: Optional[str] = Field(description="Hybrid only")
    ml_model: Optional[dict[str, str]] = Field(description="ML and Hybrid only")
    source: str


class ResourceMetrics(BaseModel):
    resource: str
    unit: str
    semantics: str = Field(description="peak or average_usage")
    label: str = Field(description="Short display label, e.g. 'Average usage, not peak'")
    violation_pct: Optional[float]
    valid_violation_count: Optional[int]
    average_utilization: Optional[float] = Field(description="Ratio of actual to recommended usage")
    valid_utilization_count: Optional[int]
    average_waste: Optional[float] = Field(description="In the resource unit")
    average_shortfall: Optional[float] = Field(description="In the resource unit")


class AnyResourceMetrics(BaseModel):
    violation_pct: Optional[float]
    valid_violation_count: Optional[int]


class PolicyMetrics(BaseModel):
    policy: str
    policy_id: str
    risk_levels: list[str]
    available_datasets: list[str] = Field(description="Datasets in the bundle whose final-test results include this policy")
    row_count: int
    resources: list[ResourceMetrics]
    any_resource: Optional[AnyResourceMetrics] = Field(description="Google only")


class BundleRef(BaseModel):
    bundle_status: str
    dataset_status: str
    source_run_id: Optional[str]
    bundle_checksum: str


class Recommendation(BaseModel):
    dataset_id: str
    workload_id: str
    display_name: str
    risk_level: Optional[str] = Field(description="Null when a policy was requested directly")
    policy: str
    policy_id: str
    latest_run: LatestRun
    primary_resource: Optional[str] = Field(description="Resource to emphasize (memory on Alibaba); null when the dataset has none")
    resources: list[RecommendedResource]
    same_for_all_risk_levels: bool
    rule: Rule
    policy_evidence: PolicyMetrics = Field(description="Dataset-wide final-test results of this policy, not of this workload")
    bundle: BundleRef


class HistoryResource(BaseModel):
    resource: str
    unit: str
    semantics: str = Field(description="peak or average_usage")
    label: str
    recommended: Optional[float]
    actual: Optional[float] = Field(description="Usage of the next run; null when not observed")
    exceeded: Optional[bool]
    target_status: str


class HistoryItem(BaseModel):
    occurrence_id: str
    role_key: Optional[str]
    start_time_us: int = Field(description="Start of the run the recommendation was made for")
    target_occurrence_id: Optional[str] = Field(description="The next run the recommendation is compared with")
    target_start_time_us: Optional[int]
    resources: list[HistoryResource]


class History(BaseModel):
    dataset_id: str
    workload_id: str
    risk_level: Optional[str]
    policy: str
    policy_id: str
    comparison: str
    items: list[HistoryItem]


class PolicyList(BaseModel):
    dataset_id: str
    source: str
    policies: list[PolicyMetrics]


class DatasetHealth(BaseModel):
    dataset_id: str
    bundle_status: str
    source_run_id: Optional[str]
    source_mismatch_count: int


class Health(BaseModel):
    status: str
    bundle_status: str
    bundle_schema_version: str
    bundle_checksum: str
    export_commit: Optional[str]
    export_timestamp_utc: Optional[str]
    datasets: list[DatasetHealth]
