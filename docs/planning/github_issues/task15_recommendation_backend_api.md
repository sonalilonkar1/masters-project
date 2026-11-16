# [P1] Task 15: Recommendation Backend — UI Export and Read-Only API

**Labels:** `area-implementation`, `priority-high`
**Owner:** Unassigned
**Priority:** P1 — Required for the demo and Task 16
**Related design:** `docs/design/recommendation_service_design_plan.md`
**Related summary:** `docs/design/discussion_summary_2026-11-16.md`
**Related planning document:** `docs/planning/295b_scope_and_done.md`

## Objective

Build the backend that allows a developer to:

1. Select Google ClusterData 2019 or Alibaba GPU 2020.
2. Search and select a workload.
3. Select a risk level.
4. View the CPU and memory recommendation for the workload's next run.
5. View the evidence behind the recommendation:
   - Original request values.
   - Recommendation basis (history or request fallback) per resource.
   - Policy test metrics.
   - Historical recommendation-versus-actual results.

This task includes:

- An offline export that converts final-test outputs into a small, versioned, checksummed UI bundle.
- A read-only HTTP API that serves the bundle.

The service presents existing results only. It must not train models, select policies, recompute evaluation metrics, or modify published results.

## Current Project State

- Final-test results exist for Google ClusterData 2019 and Alibaba GPU 2020.
- Final-test summaries are committed:

  - `reports/results/google_subset/tables/final_test_policy_comparison.csv`
  - `reports/results/alibaba_gpu_2020/final_test/final_test_policy_comparison.csv`

- Per-run recommendation outputs are stored locally under `data/processed/`, which is git-ignored.
- No recommendation service API currently exists.
- **Alibaba source run:** PR #121 (Task 8, merged 2026-11-16) re-ran Tasks 4–7 and the final test on 2026-11-15 (run `4fdc7e96…`). That run is now the published result on `main`. Local copies made before then hold the 2026-10-30 run, which lacks the `run_id` and counters added by PR #124. The final export must use the Nov 15 outputs.

### Dataset Summary

| Item | Google ClusterData 2019 | Alibaba GPU 2020 |
|---|---:|---:|
| Test occurrences (rows) | 731 | 69,285 |
| Scored occurrences with next-run targets | 259 | 44,053 |
| Latest test run without next occurrence | 472 | 25,232 |
| Workloads | 472 | 25,232 |
| Policies | 7 | 7 |
| Hybrid rule | `max(ML, P95)` | `max(ML, P99)` (the selected baseline) |
| Locked baseline | P99, `min_runs = 1` | P99, `min_runs = 10` |
| ML model | Random forest (log1p target) | HistGradientBoosting |
| Workload key | `recurrence_key` (`user‖logical name`) | `recurrence_key` (`group‖task`) |
| Unique row key | `occurrence_id` | `role_key` (`occurrence_id` is shared by all roles of a job: 68,677 unique among 69,285 rows) |
| CPU semantics | Peak CPU in normalized `ncu` | Average usage in `percent_of_vcpu` |
| Memory semantics | Peak normalized memory | Peak memory in `gb` |
| Latest run falls back to the request (memory) | 233 of 472 workloads (49.4%) | 19,341 of 25,232 workloads (76.7%) |

### Why the basis matters

Below `min_runs` earlier runs, every history policy equals the request, and Hybrid becomes `max(ML, request)`. For those workloads all three risk levels give the same answer. Most runs have history (Google 67%, Alibaba 56%), but most workloads' latest recommendation does not, because many workloads run only once or twice. The backend must therefore return the basis of every recommendation, copied from stored flags, so the UI can explain it.

## Scope

### Part A: Risk-Level Configuration

Create:

```text
config/ui_risk_levels.json
```

Define the following levels per dataset:

| Risk level | Policy | Meaning |
|---|---|---|
| Restrictive | Hybrid | Lower violation risk and more capacity reserved |
| Balanced | P95 | Middle point in the violation/waste trade-off |
| Efficient | P90 | Lower waste with a higher chance of exceeded runs |

Requirements:

- Restrictive is the default risk level.
- Mean and ML are not risk levels.
- The mapping is configuration-driven.
- Risk mappings are not tuned using test results.

### Part B: UI Export

Implement:

```text
scripts/export_ui_artifacts.py
src/service/export.py
```

The export must produce:

```text
reports/results/ui/
  manifest.json
  risk_levels.json
  rules.json
  SHA256SUMS
  <dataset>/
    dataset.json
    policy_metrics.json
    workloads.parquet
    recommendations.parquet
    metadata.json
```

#### `dataset.json`

Include:

- Dataset identifier and display name.
- CPU and memory units.
- CPU and memory semantics.
- Primary resource (memory for Alibaba).
- Evaluation scope (`full_workload` for Google, `task_role_per_instance` for Alibaba).
- Population sizes.
- Dataset caveats (Alibaba: CPU is average usage, 251 same-second next runs; Google: cross-split validation targets, Task 10).
- Notes explaining that the data represents historical test replay, not live execution.

#### `policy_metrics.json`

Copy the committed summary CSVs field by field, including:

- Violation rates.
- Average waste.
- Shortfall.
- Utilization.
- Valid-row denominators.
- Per-resource units.
- Metric definitions where needed.

Metrics must not be recomputed.

#### `workloads.parquet`

One row per workload:

```text
workload_id
display_name
test_run_count
scored_run_count
first_start_time_us
last_start_time_us
latest_occurrence_id
latest_uses_history
has_scored_history
```

- `latest_uses_history`: the latest recommendation is based on history for at least one resource (not a request fallback). This drives the UI's default filter.
- `has_scored_history`: the workload has at least one scored recommendation-to-next-run comparison. This decides whether the history chart has points.

#### `recommendations.parquet`

Use one row per occurrence and policy:

```text
workload_id
occurrence_id
role_key                     (Alibaba only)
start_time_us
target_start_time_us         (nullable; see below)
target_occurrence_id         (nullable; see below)
policy
recommended_cpu
recommended_memory
request_cpu
request_memory
actual_cpu
actual_memory
cpu_target_status
memory_target_status
cpu_exceeded
memory_exceeded
cpu_basis
memory_basis
cpu_history_run_count
memory_history_run_count
is_latest
```

Requirements:

- Actual values are nullable.
- Missing values remain null and never become zero.
- CPU and memory target status are represented independently:
  - Alibaba: copied from `cpu_target_status` and `memory_target_status`.
  - Google: no stored status; derived as `available` when the target value is present, `no_next_occurrence` when there is no next occurrence, and `next_occurrence_missing_value` when a next occurrence exists but its value is missing. The derivation is documented in `metadata.json`.
- Exceeded flags are nullable when the corresponding target is unavailable.
- `target_start_time_us` and `target_occurrence_id` identify the next run used as the target:
  - Google: `target_start_time_us` is copied from `target_next_occurrence_start_time_us`; `target_occurrence_id` is `recurrence_key‖target_start_time_us`.
  - Alibaba: not stored. Either derive them from the Task 4 order (`recurrence_key`, `start_time_us`, `occurrence_id`, `role_key`) and verify that the derived next run's observed value equals the stored `actual_*` on every available row, or leave them null. The history view does not depend on them.
- `is_latest` is true only for the workload's final test occurrence. There is exactly one latest occurrence per workload.
- Recommendation time and target time are not confused in the history view.

#### Basis per resource

`cpu_basis` and `memory_basis` take one of `history`, `request_fallback`, `request` or `model`. They are copied from stored flags, never recomputed:

| Policy | Basis source |
|---|---|
| Request | Always `request` |
| Mean, P90, P95, P99 | That policy's flag `uses_history_{resource}_{mean,p90,p95,p99}` |
| ML | Always `model` |
| Hybrid | Its safeguard's flag: `uses_history_{resource}_p95` (Google), `uses_history_{resource}_p99` (Alibaba) |

Flag sources: Google `test_occurrences.parquet`; Alibaba Task 6 `recommendations_test.parquet`. Earlier-run counts are copied from `occ_hist_peak_{cpu,memory}_count` (Google) and `{cpu,memory}_history_count` (Alibaba).

#### `rules.json`

Keyed by dataset. Copy the locked rules from the frozen result records:

- Google: N04 `metadata.json`, N05 `ml_metadata.json`, N06 `decision_manifest.json`.
- Alibaba: Task 6 `baseline_selection.json`, Task 7 `decision_manifest.json`.

Include:

- Policy definitions and descriptions.
- Selected baseline policy.
- `min_runs`.
- ML model identifier.
- Hybrid rule and safeguard policy.
- Per-resource fallback behavior.

The API must use this metadata when returning the rule that produced a recommendation.

#### Google Export

Use:

- `test_occurrences.parquet` for baseline recommendations, flags and counts.
- `test_ml_predictions.parquet` for ML recommendations.
- `src/policies/hybrid.py::hybrid_recommendation(ML, P95)` for Google Hybrid.

Google Hybrid may be applied to latest unscored rows because stored Hybrid values exist only for scored rows. The export must verify that the recomputed Hybrid values equal the stored Hybrid values for all 259 scored rows. No other recommendations or metrics may be recalculated.

#### Alibaba Export

Use:

- `final_test_predictions.parquet` for recommendations and targets.
- The Task 4 test table (`alibaba_gpu_v2020_targets/test.parquet`) for run start times.
- The Task 6 test recommendations for `uses_history_*` flags.
- `role_key` for one-to-one joins.

Requirements:

- Melt wide predictions into the common long format.
- Validate all joins as one-to-one on `role_key`.
- Copy the per-policy `uses_history_*` flags and the earlier-run counts.
- Do not recompute history eligibility or fallback decisions.

#### Provenance and Metadata

Each `metadata.json` must include:

- Source paths.
- Source SHA-256 checksums.
- Source run ID.
- Decision-manifest checksum.
- Source code commit.
- Export commit.
- Export timestamp.
- Bundle version.
- Schema version.
- Row counts and latest-run fallback counts.
- Note explaining the Google Hybrid re-application.
- Note explaining derived fields (Google target statuses; Alibaba target occurrence, if derived).
- Alibaba source-run information.

#### Export Safety Rules

The CLI must support:

```text
--out-dir
--allow-dirty
--force
--final
```

Default behavior:

- Refuse to run with a dirty Git tree (unless `--allow-dirty`).
- Refuse to overwrite an existing output directory (unless `--force`).
- Alibaba provenance: without `--final`, warn and record missing `run_id`, `test_target_read_count = 1` or `test_evaluator_call_count = 1`; with `--final`, refuse. The published bundle is always built with `--final`.
- Refuse to run when required source files are missing.
- Refuse duplicate or unmatched one-to-one joins.
- Refuse output when copied values, row counts, or metrics fail validation.

Measure the bundle size:

- If under 20 MB, commit it.
- If over 20 MB, use the agreed shared-artifact mechanism and commit metadata, checksums, and retrieval instructions.

### Part C: Read-Only API

Implement:

```text
src/service/bundle.py
src/service/api.py
src/service/schemas.py
```

Serve the API under:

```text
/api/v1
```

The bundle must be loaded once at startup and indexed by:

```text
(workload_id, policy)
```

The API must never read pipeline outputs directly.

#### Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/datasets` | Return datasets, units, semantics, scope, and sizes |
| `GET /api/v1/risk-levels` | Return risk levels, policy mappings, and descriptions |
| `GET /api/v1/datasets/{dataset}/workloads` | Return a paginated workload list |
| `GET /api/v1/datasets/{dataset}/workloads/{workload_id}/recommendation` | Return the latest recommendation and evidence |
| `GET /api/v1/datasets/{dataset}/workloads/{workload_id}/history` | Return recommendation-versus-next-run history |
| `GET /api/v1/datasets/{dataset}/policies` | Return all seven policy metrics |
| `GET /api/v1/health` | Return service, bundle, checksum, commit, and source-run status |

#### Workload Endpoint

Supported query parameters:

```text
search=
has_history=          (filters on latest_uses_history)
sort=test_runs|id
limit=
offset=
```

Requirements:

- Default sort is `test_runs` descending.
- Apply a maximum limit.
- Invalid pagination returns `400`.
- Search matches workload ID or display name.
- Workload IDs are safely URL-encoded (they contain `‖` separators).
- No cross-dataset results are returned.

#### Recommendation Endpoint

Supported query parameters:

```text
risk=
policy=
```

Rules:

- Exactly one of `risk` or `policy` may be supplied.
- If neither is supplied, use the default risk level.
- Supplying both returns `400`.
- Unknown risk levels or policies return `400`.

The response must include:

- Dataset and workload.
- Selected risk level and policy.
- Latest occurrence.
- CPU and memory recommendations.
- Original request values.
- CPU and memory basis and earlier-run counts.
- `same_for_all_risk_levels`: true when Restrictive, Balanced and Efficient give identical CPU and memory values for this workload.
- Rule description and inputs (from `rules.json`), including `min_runs`.
- Dataset-wide policy metrics.
- Primary resource.
- Bundle and source metadata.

Use resource-specific basis fields:

```json
{
  "cpu_basis": {
    "type": "history",
    "history_run_count": 10
  },
  "memory_basis": {
    "type": "request_fallback",
    "history_run_count": 3
  }
}
```

#### History Endpoint

Each history item must distinguish the recommendation occurrence from the target occurrence:

```text
occurrence_id
target_occurrence_id
start_time_us
target_start_time_us
recommended_cpu
recommended_memory
actual_cpu
actual_memory
cpu_exceeded
memory_exceeded
cpu_target_status
memory_target_status
```

The response must make clear that the recommendation from one occurrence is evaluated against the subsequent occurrence.

#### Policy Comparison Endpoint

Return all seven policies:

```text
request
mean
p90
p95
p99
ml
hybrid
```

For every policy, return:

- Display name (as in the summary CSVs, e.g. `P95`, `Hybrid`).
- CPU metrics.
- Memory metrics (any-resource metrics for Google only).
- Valid-row denominators.
- Units.
- Risk-level mapping, if applicable.
- Dataset availability.

#### Response Rules

- Every resource value includes its unit.
- Alibaba CPU values include:

  ```text
  semantics: average_usage
  label: Average usage, not peak
  ```

- Alibaba memory is listed before CPU.
- Missing values are `null`, never zero or omitted.
- Counts are explicitly identified as counts.
- No response combines datasets.
- Only `GET` routes are exposed.
- No endpoint runs pipeline code or writes files.

#### Errors

Return:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable explanation"
  }
}
```

Use:

- `400` for invalid or conflicting query parameters.
- `404` for unknown datasets, workloads, or policies.
- `500` only for unexpected server errors.

#### Checksum Verification

At startup:

- Read `SHA256SUMS`.
- Verify every listed bundle file.
- Fail startup if any file is missing or modified.
- Report bundle version and checksum through `/health`.

#### OpenAPI Contract

FastAPI generates an OpenAPI (Swagger) specification from the code. Commit it at:

```text
docs/design/recommendation_api_openapi.json
```

Update it whenever the API schema changes. Task 16 develops against this file.

### Part D: Tests

Create:

```text
tests/test_ui_export.py
tests/test_api.py
tests/fixtures/ui_bundle/
```

#### Export Tests

Test:

- Every copied recommendation equals its source.
- Every copied metric equals the summary CSV.
- Google Hybrid equals stored Hybrid on all 259 scored rows.
- Row counts per dataset and policy.
- Null values remain null.
- Exactly one latest row exists per workload.
- Target occurrence and timestamp are correct where present.
- CPU and memory target statuses are independent.
- Basis per resource and policy matches the stored flags; latest-run fallback counts match (233 Google, 19,341 Alibaba for memory).
- Alibaba one-to-one joins on `role_key` are enforced.
- Missing Alibaba provenance warns without `--final` and is rejected with `--final`.
- Dirty-tree export is rejected unless `--allow-dirty` is provided.
- Existing output is rejected unless `--force` is provided.
- Missing source files are rejected.
- Checksums and metadata are generated.

#### Fixture Bundle

The fixture bundle must contain:

- Both datasets.
- Multiple workloads.
- A workload whose latest recommendation uses history.
- A workload whose latest recommendation falls back to the request (`same_for_all_risk_levels` true).
- A workload without a scored next run.
- Null actual values.
- Different CPU and memory target statuses and bases.
- All seven policies.
- Risk mappings.
- Policy rules and metadata.

API tests must use the fixture and must not require local pipeline outputs.

#### API Tests

Test:

- Response shape for every endpoint.
- OpenAPI availability.
- Dataset metadata.
- Risk-level mappings.
- Default risk behavior.
- Invalid risk and policy combinations.
- Workload pagination.
- Search and `has_history` filtering.
- Recommendation lookup, basis fields and `same_for_all_risk_levels`.
- History target alignment.
- Policy metrics equal the bundle.
- Units on every resource value.
- Alibaba CPU semantics and label.
- Null values in responses.
- `400` and `404` cases.
- Checksum mismatch startup failure.
- No non-GET routes.
- No cross-dataset responses.

#### Dependencies

Add the required dependencies to:

```text
requirements.txt
requirements-lock.txt
```

Expected dependencies:

```text
fastapi
uvicorn
httpx
```

The complete existing test suite must continue to pass.

### Part E: Documentation

Update the README with:

- Required dependencies.
- Export instructions (development and `--final`).
- Source-output requirements (Nov 15 Alibaba run).
- API startup instructions.
- API base URL.
- Bundle location.
- Fixture testing instructions.
- OpenAPI generation instructions.
- External bundle retrieval instructions, if applicable.
- Explanation that the service serves historical final-test results and is not a live recommendation system.

Update the design document if implementation decisions change.

## Non-Goals

This task does not include:

- Web UI implementation (Task 16).
- Screenshots or report Figures 8.1 and 8.2 (Task 16).
- Model training or tuning.
- Model selection or reselection.
- New metrics, including the history-versus-fallback outcome breakdown (Task 14).
- Re-running the evaluation pipeline.
- Changing published evaluation numbers.
- Live or shadow recommendations.
- Authentication.
- Hosting or deployment.
- Cross-dataset ranking or aggregation.
- GPU recommendations.
- Azure, Splitwise, or ModServe results.

## Dependencies

- The Nov 15 Alibaba final-test outputs (published on `main` by PR #121) must be available locally before producing the final bundle. Development can start now on older local outputs and the fixture bundle.
- Corrected Google outputs must be exported again when Tasks 10 or 14 change published results.
- Task 16 depends on the committed OpenAPI contract and the fixture bundle.

## Suggested Pull Requests

| PR | Scope |
|---|---|
| PR 1 | Risk configuration, bundle schema, export implementation, validation, and export tests |
| PR 2 | Bundle loader, FastAPI API, schemas, fixture bundle, API tests, and OpenAPI contract |
| PR 3, if needed | Final bundle from the Nov 15 run, README instructions, and integration verification |

## Acceptance Criteria

- [ ] The export produces a bundle for both datasets; the published bundle is built with `--final` from the Nov 15 Alibaba run.
- [ ] The bundle includes version metadata, provenance, checksums, risk levels, policy rules, dataset metadata, workloads, recommendations, and policy metrics.
- [ ] Every copied recommendation and metric equals its source.
- [ ] Google Hybrid for unscored rows is generated only through the existing Hybrid rule.
- [ ] Google Hybrid equals stored Hybrid values on all 259 scored rows.
- [ ] CPU and memory target statuses are represented independently; derived fields are documented.
- [ ] History identifies both the recommendation occurrence and the next target occurrence (where available).
- [ ] Recommendation basis is preserved per resource and policy from stored flags and counts.
- [ ] Latest-run fallback counts match the source data (233 Google, 19,341 Alibaba for memory).
- [ ] The API loads only the bundle and does not read pipeline outputs.
- [ ] The API verifies bundle checksums before starting.
- [ ] All endpoints are read-only `GET` endpoints.
- [ ] Every resource value includes a unit.
- [ ] Alibaba CPU values are labelled as average usage, not peak.
- [ ] Missing values are returned as `null`.
- [ ] Invalid requests return structured `400` errors.
- [ ] Unknown resources return structured `404` errors.
- [ ] Policy metrics returned by the API equal the committed summary CSVs.
- [ ] The OpenAPI contract is committed for Task 16.
- [ ] Export tests pass.
- [ ] API tests pass using the fixture bundle.
- [ ] The full existing test suite passes.
- [ ] README instructions allow another developer to export the bundle and run the API locally.
- [ ] The design document is updated if implementation decisions change.

## Completion Definition

Task 15 is complete when the final bundle can be generated, checksum-validated, and served through the read-only API, and Task 16 can develop entirely against the fixture bundle and the committed OpenAPI contract.
