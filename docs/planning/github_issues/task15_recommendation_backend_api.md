# [P1] Task 15: Recommendation Backend — UI Export and Read-Only API

**Labels:** `area-implementation`, `priority-high`
**Owner:** Unassigned
**Priority:** P1 — Required for the demo and Task 16
**Related design:** `docs/design/recommendation_service_design_plan.md`
**Related summary:** `docs/design/discussion_summary_2026-11-16.md`
**Related planning document:** `docs/planning/295b_scope_and_done.md`
**Status:** Implemented in PR #131 (branch `feature/task15-backend`, 2026-11-16). The verified bundle is committed in `reports/results/ui/` (checksum `97e9418d…`), built from the Nov 15 Alibaba run shared through #130. All acceptance criteria are met.

## Objective

Build the backend that allows a developer to:

1. Select Google ClusterData 2019 or Alibaba GPU 2020.
2. Search and select a workload.
3. Select a risk level.
4. View the CPU and memory recommendation for the workload's next run.
5. View the evidence behind the recommendation:
   - Original request values.
   - Recommendation basis per resource: history, request fallback, or model (ML alone).
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

- Per-run recommendation outputs are stored locally under `data/processed/`, which is git-ignored. Only their checksums are committed.
- The recommendation service is built in PR #131: export in `scripts/export_ui_artifacts.py` and `src/service/export.py`, API in `src/service/api.py`. Before that PR, no recommendation API existed.
- **Agreed Alibaba run:** PR #121 (Task 8, merged 2026-11-16) re-ran Tasks 4–7 and the final test on 2026-11-15. The agreed results are the ones committed on `main`:

  | What `main` records | Where | Value |
  |---|---|---|
  | Run ID | `reports/results/alibaba_gpu_2020/final_test/run_record.json` | `4fdc7e96-789b-43a9-990f-20f189e9598b` |
  | Decision manifest | same file | `d36964c0…` |
  | Input checksums | `reports/results/alibaba_gpu_2020/verification/artifact_manifest.json` | `final_test_predictions.parquet` `f01df084…`, `targets/test.parquet` `daaea11a…`, `baselines/recommendations_test.parquet` `1e3361f6…` |

  Local copies made before 2026-11-15 hold the Oct 30 run and do **not** match these checksums. The matching files were shared through #130 on the team Drive (`CMPE 295A_B/alibaba_gpu_v2020_run_4fdc7e96/`) and verified 31 of 31 on a second machine.

- **Agreed Google run:** the frozen manifest committed at `reports/results/google_subset/decision_manifest.json` (status `final`) pins every Google input by SHA-256, including `test_occurrences.parquet` and `test_ml_predictions.parquet`.

### Dataset Summary

| Item | Google ClusterData 2019 | Alibaba GPU 2020 |
|---|---:|---:|
| Test occurrences (rows) | 731 | 69,285 |
| Scored occurrences with next-run targets | 259 | 44,053 |
| Latest test run without next occurrence | 472 | 25,232 |
| Workloads | 472 | 25,232 |
| Policies | 7 | 7 |
| Hybrid rule | `max(ML, P95)` | `max(ML, P99)` |
| Locked baseline | P99, `min_runs = 1` | P99, `min_runs = 10` |
| ML model | Random forest with log-transformed target | HistGradientBoosting |
| Workload key | `recurrence_key` | `recurrence_key` |
| Unique row key | `occurrence_id` | `role_key` |
| CPU semantics | Peak CPU in normalized `ncu` | Average usage in `percent_of_vcpu` |
| Memory semantics | Peak normalized memory | Peak memory in `gb` |
| Latest run falls back to request: CPU | 231 of 472 | 19,342 of 25,232 (Oct 30 files; re-check on Nov 15) |
| Latest run falls back to request: memory | 233 of 472 | 19,341 of 25,232 (Oct 30 files; re-check on Nov 15) |

### Why the recommendation basis matters

Below the configured `min_runs` threshold, history-based policies fall back to the request. Hybrid then becomes `max(ML, request)`.

The backend must return the basis of every recommendation, copied from the stored flags, so the UI can explain whether each resource recommendation came from:

- Historical data.
- Request fallback.
- The original request policy.
- The ML model.

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
src/service/contract.py
src/service/export.py
```

`contract.py` fixes the bundle format in one place before any export code: column names, types and nullability, target-status and basis values, policy names, dataset IDs, units and semantics, and the API error format. The export validates against it and the API reads from it.

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

#### Source of Truth and Input Verification

The export reads only inputs that match the checksums committed on `main`. It never decides which run is authoritative; `main` does.

| Dataset | Reference committed on `main` | Inputs that must match |
|---|---|---|
| Alibaba | `reports/results/alibaba_gpu_2020/verification/artifact_manifest.json` and `final_test/run_record.json` | `alibaba_gpu_v2020_final_test/final_test_predictions.parquet`, `final_test/run_record.json`, `alibaba_gpu_v2020_targets/test.parquet`, `alibaba_gpu_v2020_baselines/recommendations_test.parquet` |
| Google | `reports/results/google_subset/decision_manifest.json` (`input_sha256`) | `google_subset_v1/test_occurrences.parquet`, `google_subset_v1/test_ml_predictions.parquet` |

Rules:

- Every input file's SHA-256 must equal the value recorded in the reference.
- The local Alibaba `run_record.json` must have the same `run_id` and `decision_manifest_sha256` as the committed one, and `test_target_read_count = 1` and `test_evaluator_call_count = 1`.
- Reference values are read from the committed files at export time, never hard-coded, so a future agreed run needs no code change.
- Files used only for checks and not pinned by a reference (for example Google `final_test_row_level.parquet`, used to verify Hybrid) are listed in `metadata.json` with their checksums.
- `metadata.json` records the reference file, its commit, and the matched checksums.

#### `dataset.json`

Include:

- Dataset identifier and display name.
- CPU and memory units.
- CPU and memory semantics.
- Primary resource.
- Evaluation scope.
- Population sizes.
- Dataset caveats.
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

Definitions:

- `latest_uses_history`: whether the latest recommendation is based on history for at least one resource.
- `has_scored_history`: whether the workload has at least one scored recommendation-to-next-run comparison.

#### `recommendations.parquet`

Use one row per occurrence and policy:

```text
workload_id
occurrence_id
role_key
start_time_us
target_start_time_us
target_occurrence_id
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

- `role_key` is populated for Alibaba and nullable for Google.
- Actual values are nullable.
- Missing values remain null and never become zero.
- CPU and memory target status are represented independently.
- Exceeded flags are nullable when the corresponding target is unavailable.
- `target_start_time_us` and `target_occurrence_id` identify the next run used as the target where available.
- `is_latest` is true only for the workload's final test occurrence.
- There is exactly one latest occurrence per workload.
- Recommendation time and target time must not be confused in the history view.

Target status values: the canonical vocabulary `TARGET_STATUSES` in `src/canonical/schema.py`, imported rather than copied:

```text
available
no_next_occurrence
next_occurrence_in_other_split
next_occurrence_ineligible_resource
unsupported_resource
```

Alibaba test data uses `available`, `no_next_occurrence` and, for 8 CPU targets, `next_occurrence_ineligible_resource`.

For Alibaba, copy resource-specific target statuses from the verified source.

For Google, derive target status as follows and document the derivation in `metadata.json`:

- `available` when the target value is present.
- `no_next_occurrence` when no next occurrence exists.
- `next_occurrence_ineligible_resource` when a next occurrence exists but its target value is missing (no current Google test row; 259 are `available` and 472 `no_next_occurrence`).

#### Target occurrence alignment

For Google:

- Copy `target_start_time_us` from `target_next_occurrence_start_time_us`.
- Construct or copy `target_occurrence_id` using the verified next-occurrence identity.

For Alibaba:

- The source may not contain an explicit target occurrence ID.
- Either derive the next run using the verified Task 4 ordering and validate that its observed value equals the stored `actual_*` value, or leave target occurrence fields null.
- The history view must still correctly explain that the recommendation is evaluated against the subsequent run.

#### Basis per resource

`cpu_basis` and `memory_basis` must use one of:

```text
history
request_fallback
request
model
```

Copy the basis from stored flags. Do not recompute it.

| Policy | Basis source |
|---|---|
| Request | Always `request` |
| Mean, P90, P95, P99 | Corresponding stored history flag |
| ML | Always `model` |
| Hybrid | Safeguard history flag: P95 for Google, P99 for Alibaba; `model` when the safeguard has no value (Google runs with neither a request nor history, where Hybrid is the ML value alone) |

Earlier-run counts must also be copied from the stored source fields.

#### `rules.json`

Key the rules by dataset and copy the locked rules from the frozen result records.

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

- `test_occurrences.parquet` for baseline recommendations, flags, and counts.
- `test_ml_predictions.parquet` for ML recommendations.
- `src/policies/hybrid.py::hybrid_recommendation(ML, P95)` for Google Hybrid.

Google Hybrid may be applied to latest unscored rows because stored Hybrid values exist only for scored rows.

The export must verify that recomputed Hybrid values equal the stored Hybrid values for all 259 scored rows.

No other recommendations or metrics may be recalculated.

#### Alibaba Export

Use:

- `final_test_predictions.parquet` for recommendations and targets.
- `alibaba_gpu_v2020_targets/test.parquet` for run start times.
- Task 6 test recommendations for `uses_history_*` flags.
- `role_key` for one-to-one joins.

Requirements:

- Melt wide predictions into the common long format.
- Validate all joins as one-to-one.
- Copy the per-policy history flags and earlier-run counts.
- Do not recompute history eligibility or fallback decisions.

#### Provenance and Metadata

Each `metadata.json` must include:

- Source paths.
- Source SHA-256 checksums and the committed reference each was matched against.
- Source run ID.
- Decision-manifest checksum.
- Source code commit.
- Export commit.
- Export timestamp.
- Bundle version.
- Schema version.
- Bundle status: `verified` or `development`.
- `source_mismatches`: every input whose checksum or run fields differ from the reference (empty for a `verified` bundle).
- Row counts.
- Latest-run fallback counts, separately for CPU and memory, each compared with the count from the source `uses_history_*` flags.
- Note explaining the Google Hybrid re-application.
- Note explaining derived fields.

#### Export Safety Rules

The CLI must support:

```text
--out-dir
--allow-dirty
--force
--allow-unverified-source
```

Default behavior:

- Refuse to run when any input checksum or the Alibaba `run_id` does not match the committed reference (see Source of Truth).
- `--allow-unverified-source` (development only) allows non-matching inputs, such as older local copies. The bundle is then marked `development` in `manifest.json` and every `metadata.json`, and lists every mismatch.
- A `development` bundle must never be committed or published; the API reports its status through `/health`.
- With `--allow-unverified-source`, the default output is `data/processed/ui_dev/` (git-ignored), and any `--out-dir` inside `reports/` is refused.
- Write to a hidden staging folder next to the output (same parent, so the final rename is atomic), validate, write checksums, then rename into place. On any failure the staging folder is deleted and no partial output remains. With `--force`, the old output is removed only after the new one is in place.
- Refuse to run with a dirty Git tree unless `--allow-dirty` is supplied.
- Refuse to overwrite an existing output directory unless `--force` is supplied.
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
(dataset, workload_id, policy)
```

The dataset is part of the key even though workload IDs do not currently repeat across datasets.

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
| `GET /api/v1/health` | Return service, bundle status (`verified` or `development`), checksum, commit, and source-run status |

#### Workload Endpoint

Supported query parameters:

```text
search=
has_history=
sort=test_runs|id
limit=
offset=
```

Requirements:

- Default sort is `test_runs` descending.
- `has_history` filters on `latest_uses_history`.
- Apply a maximum limit.
- Invalid pagination returns `400`.
- Search matches workload ID or display name.
- Workload IDs are safely URL-encoded.
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
- CPU and memory basis.
- Earlier-run counts.
- `same_for_all_risk_levels`.
- Rule description and inputs from `rules.json`.
- Dataset-wide policy metrics.
- Primary resource.
- Bundle and source metadata.

Example basis structure:

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

`same_for_all_risk_levels` must be true only when Restrictive, Balanced, and Efficient produce identical CPU and memory values for that workload.

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

- Display name.
- CPU metrics.
- Memory metrics.
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
- `404` for unknown datasets or workloads, or a `?policy=` the dataset does not have.
- `500` only for unexpected server errors.

#### Checksum Verification

At startup:

- Read `SHA256SUMS`, which lists every bundle file except itself (`manifest.json`, `risk_levels.json`, `rules.json`, and every dataset's JSON and Parquet files).
- Verify every listed bundle file.
- Fail startup if any file is missing or modified, or if the bundle folder contains a file that is not listed.
- Report bundle version, status and checksum through `/health`.

#### OpenAPI Contract

FastAPI must generate the OpenAPI specification from the implemented schemas and routes.

Commit it at:

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
- Target occurrence and timestamp are correct where available.
- CPU and memory target statuses are independent.
- Basis per resource and policy matches the stored flags.
- Latest-run fallback counts match the source data, separately for CPU and memory.
- Alibaba one-to-one joins on `role_key` are enforced.
- An input whose checksum differs from the committed reference is rejected.
- An Alibaba `run_record.json` whose `run_id` or manifest checksum differs from `main`'s is rejected.
- `--allow-unverified-source` produces a bundle marked `development` that lists every mismatch in `source_mismatches`.
- `--allow-unverified-source` with an output folder inside `reports/` is refused.
- A failed validation leaves no output folder and no staging folder.
- Reference checksums are read from the committed files, not hard-coded.
- Dirty-tree export is rejected unless `--allow-dirty` is provided.
- Existing output is rejected unless `--force` is provided.
- Missing source files are rejected.
- Checksums and metadata are generated.

Verification tests use small synthetic inputs and reference files, so they run without the real pipeline outputs.

#### Fixture Bundle

The fixture bundle must contain:

- Both datasets.
- Multiple workloads.
- A workload whose latest recommendation uses history.
- A workload whose latest recommendation falls back to the request.
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
- Recommendation lookup.
- Basis fields and `same_for_all_risk_levels`.
- History target alignment.
- Policy metrics equal the bundle.
- Units on every resource value.
- Alibaba CPU semantics and label.
- Null values in responses.
- `400` and `404` cases.
- Checksum mismatch startup failure.
- `/health` reports the bundle status.
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
- How to obtain the agreed source files and check them against `main`.
- Final export instructions, and development export with `--allow-unverified-source`.
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

- Web UI implementation.
- Screenshots or report Figures 8.1 and 8.2.
- Model training or tuning.
- Model selection or reselection.
- New metrics.
- Re-running the evaluation pipeline.
- Changing published evaluation numbers.
- Choosing which run is authoritative (that is what is committed on `main`).
- Live or shadow recommendations.
- Authentication.
- Hosting or deployment.
- Cross-dataset ranking or aggregation.
- GPU recommendations.
- Azure, Splitwise, or ModServe results.

## Dependencies

- The agreed Alibaba files (Nov 15 run, matching the checksums on `main`) must be available locally before producing the final bundle. They were shared through #130 (Drive `CMPE 295A_B/alibaba_gpu_v2020_run_4fdc7e96/`); `--allow-unverified-source` remains for development with other local copies.
- The local Google inputs already match the committed Google manifest.
- Corrected Google outputs must be exported again when Tasks 10 or 14 change published results; the new reference is then whatever is committed on `main`.
- Task 16 depends on the committed OpenAPI contract and fixture bundle.

## Pull Request

One PR covers Parts A–E (team decision, 2026-11-16): PR #131 from branch `feature/task15-backend`.

## Acceptance Criteria

- [x] The export produces a bundle for both datasets from inputs that match the checksums committed on `main`.
- [x] The final bundle is marked `verified`; a `development` bundle is never committed or published.
- [x] Reference checksums and the Alibaba `run_id` are read from committed files, not hard-coded.
- [x] The bundle includes version metadata, provenance, checksums, risk levels, policy rules, dataset metadata, workloads, recommendations, and policy metrics.
- [x] Every copied recommendation and metric equals its source.
- [x] Google Hybrid for unscored rows is generated only through the existing Hybrid rule.
- [x] Google Hybrid equals stored Hybrid values on all 259 scored rows.
- [x] CPU and memory target statuses are represented independently.
- [x] History identifies both the recommendation occurrence and the next target occurrence where available.
- [x] Recommendation basis is preserved per resource and policy from stored flags and counts.
- [x] Latest-run fallback counts match the source data, separately for CPU and memory.
- [x] The API loads only the bundle and does not read pipeline outputs.
- [x] The API verifies bundle checksums before starting and reports the bundle status.
- [x] All endpoints are read-only `GET` endpoints.
- [x] Every resource value includes a unit.
- [x] Alibaba CPU values are labelled as average usage, not peak.
- [x] Missing values are returned as `null`.
- [x] Invalid requests return structured `400` errors.
- [x] Unknown resources return structured `404` errors.
- [x] Policy metrics returned by the API equal the committed summary CSVs.
- [x] The OpenAPI contract is committed for Task 16.
- [x] Export tests pass.
- [x] API tests pass using the fixture bundle.
- [x] The full existing test suite passes.
- [x] README instructions allow another developer to obtain the agreed files, export the bundle and run the API locally.
- [x] The design document is updated if implementation decisions change.

## Completion Definition

Task 15 is complete when a `verified` bundle, built from inputs matching the checksums committed on `main`, can be generated, checksum-validated, and served through the read-only API, and Task 16 can develop entirely against the fixture bundle and committed OpenAPI contract.
