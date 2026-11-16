# [P1] Task 15: Recommendation Backend (UI Export and Read-Only API)

**Labels:** `area-implementation`, `priority-high`

**Owner:** Unassigned

**Priority:** Priority 1 · Required for the demo and for Task 16 (web UI) · Covers the planned New Issues 5 (output interface) and 7 (output and API) from `docs/planning/295b_scope_and_done.md`. The UI part of the former Task 15 is now Task 16.

**Design:** `docs/design/recommendation_service_design_plan.md` (sections 4–8, 10–14).

---

## Objective

Build the backend that lets a developer choose a dataset (Google ClusterData 2019 or Alibaba GPU 2020), find a workload, choose a risk level and receive the CPU and memory recommendation for the workload's next run with its evidence. The backend has two parts: an offline export that turns the final-test outputs into a small, checksummed UI bundle, and a read-only HTTP API that serves that bundle. It presents existing results only.

## Current Project State

- Final-test results exist for both datasets (one-time test run each). Nothing in this task may change them.
- **Committed summaries:** `reports/results/google_subset/tables/final_test_policy_comparison.csv` and `reports/results/alibaba_gpu_2020/final_test/final_test_policy_comparison.csv`.
- **Per-run recommendations exist only locally** (`data/processed/` is git-ignored). Checked 2026-11-16:

| | Google | Alibaba GPU 2020 |
|---|---|---|
| Test runs | 731 (`google_subset_v1/test_occurrences.parquet`) | 69,285 (`alibaba_gpu_v2020_final_test/final_test_predictions.parquet`) |
| Scored (with next-run target) | 259 (`final_test_row_level.parquet`, long, 7 policies) | 44,053 |
| Last run per workload (`no_next_occurrence`) | 472 | 25,232 |
| Workloads | 472 (83 with a scored run) | 25,232 |
| Hybrid rule | `max(ML, P95)`; stored for scored rows only | `max(ML, P99)`; stored for all rows |
| Locked baseline | P99, `min_runs = 1` | P99, `min_runs = 10` |
| Unique row key | `occurrence_id` | `role_key` (`occurrence_id` is shared by all roles of a job) |
| Latest run falls back to the request (memory) | 233 of 472 workloads | 19,341 of 25,232 workloads |
| Run start time | `execution_start_time_us` | `start_time_us` in `alibaba_gpu_v2020_targets/test.parquet` (join on `role_key`) |

- PR #121 (Task 8, merged 2026-11-16) re-ran the chain and the final test on 2026-11-15 (run `4fdc7e96…`) with changed ML and Hybrid numbers; this run is now the published result on `main`. The local outputs and the report are still the 2026-10-30 run, which lacks the `run_id` and counters added by PR #124.
- No API code exists.

## What This Task Builds

### Part A: Risk-level configuration

- [ ] `config/ui_risk_levels.json`: Restrictive → Hybrid (default), Balanced → P95, Efficient → P90, per dataset, with a one-line description of each level. Mean and ML are not levels.

### Part B: UI export

- [ ] `scripts/export_ui_artifacts.py` (CLI) and `src/service/export.py` (logic) write the bundle described in design §6 to `reports/results/ui/`: `risk_levels.json`, and per dataset `dataset.json`, `policy_metrics.json`, `workloads.parquet`, `recommendations.parquet`, `metadata.json`; plus `SHA256SUMS`.
- [ ] `recommendations.parquet` uses the common long format (design §6): one row per run and policy, with request, actual (nullable), exceeded flags (nullable), target status, start time and `is_latest`.
- [ ] Google: baselines from `test_occurrences.parquet`, ML from `test_ml_predictions.parquet`; Hybrid for all 731 runs by applying `src/policies/hybrid.py::hybrid_recommendation(ML, P95)`, and verified equal to the stored Hybrid on the 259 scored rows.
- [ ] Alibaba: melt the wide predictions to long; join run start times from the Task 4 test table and the `uses_history_*` flags from the Task 6 test recommendations, both on `role_key` with one-to-one checks.
- [ ] Both datasets: copy the per-resource basis (`history` or `request_fallback`) from the stored `uses_history_*` flags and the earlier-run counts; never recompute them.
- [ ] Copy each dataset's locked rules (`min_runs`, baseline, ML model, Hybrid rule and safeguard) from its frozen records into `rules.json`.
- [ ] Policy metrics copied field by field from the summary CSVs.
- [ ] `metadata.json`: source paths and SHA-256, source run ID, decision-manifest checksum, code commit, export time, row counts, and a note on the Google Hybrid re-application.
- [ ] Rules: no recalculation beyond the verified Google Hybrid case; nulls stay null; refuse an Alibaba source whose `run_record.json` lacks `run_id`, `test_target_read_count = 1` or `test_evaluator_call_count = 1`; refuse a dirty tree or an existing output unless `--allow-dirty` or `--force`; `--out-dir`.
- [ ] Measure the bundle size. Under 20 MB: commit it. Otherwise: share on Drive, commit only `SHA256SUMS` and `metadata.json`, and document where it lives.

### Part C: Read-only API

- [ ] `src/service/bundle.py` loads the bundle once, verifies it against `SHA256SUMS` and refuses to start on a mismatch; indexes by `(workload_id, policy)`.
- [ ] `src/service/api.py` and `src/service/schemas.py` implement, under `/api/v1`:

| Endpoint | Returns |
|---|---|
| `GET /datasets` | Datasets with display names, units, semantics, sizes |
| `GET /risk-levels` | Levels, their policy per dataset, descriptions |
| `GET /datasets/{dataset}/workloads?search=&has_history=&sort=&limit=&offset=` | Paginated workloads; `has_history` filter; default sort by test-run count, descending |
| `GET /datasets/{dataset}/workloads/{workload_id}/recommendation?risk=` or `?policy=` | Latest recommendation, request, rule and inputs, basis per resource (history with n runs, or request fallback), `same_for_all_risk_levels`, policy test metrics, source |
| `GET /datasets/{dataset}/workloads/{workload_id}/history?policy=` | Test runs in time order: recommendation, actual, exceeded |
| `GET /datasets/{dataset}/policies` | All seven policies' test metrics, risk levels marked |
| `GET /health` | Status, bundle version, commit, checksum, source run IDs |

- [ ] Every number carries its `unit`; Alibaba CPU carries `semantics: average_usage` and the label "Average usage, not peak"; Alibaba lists memory first.
- [ ] Missing values are `null`, never 0 or omitted.
- [ ] Unknown dataset, workload or policy → `404`; invalid or conflicting query → `400`; error body `{"error": {"code", "message"}}`.
- [ ] Only `GET` routes; no cross-dataset response.
- [ ] OpenAPI contract published by the app and committed as `docs/design/recommendation_api_openapi.json` for Task 16.

### Part D: Tests

- [ ] `tests/test_ui_export.py`: copied values equal sources per policy; row counts; nulls preserved; one latest row per workload; Google Hybrid equality on scored rows; metrics equal the CSVs; provenance, dirty-tree and existing-output refusals.
- [ ] `tests/fixtures/ui_bundle/`: a tiny hand-built bundle (a few workloads per dataset) so API tests need no local data.
- [ ] `tests/test_api.py`: response shape per endpoint; units on every value; risk mapping; metrics equal the bundle; 400 and 404 cases; no non-GET routes; start-up refuses a checksum mismatch.
- [ ] `fastapi`, `uvicorn` and `httpx` (for `TestClient`) added to `requirements.txt` and `requirements-lock.txt`; the full existing suite still passes.

### Part E: Documentation

- [ ] README: run the export and start the API locally.
- [ ] Update the design plan if any decision changes during implementation.

## What This Task Does Not Build

- The web UI, screenshots and report Figures 8.1 and 8.2 (Task 16).
- Any rerun, retraining, reselection or new metric. Corrected Google results (Tasks 10, 14) arrive by re-running the export only.
- Authentication, hosting or deployment beyond running locally.
- Live recommendations for new submissions.

## Dependencies

- The Nov 15 Alibaba final-test outputs (on `main` since PR #121) available locally, for the final export. Everything else can start now on the local Oct 30 outputs and the fixture bundle.

## Blocks

- Task 16 (web UI) needs the agreed API contract (Part C) and, for screenshots, the real bundle.

## Suggested Split

| PR | Content |
|---|---|
| 1 | Part A, Part B and the export tests |
| 2 | Part C, the fixture bundle and the API tests; OpenAPI contract committed |

## Acceptance Criteria

- [ ] The export produces the bundle for both datasets from the verified final-test outputs, with checksums and metadata; every copied value equals its source.
- [ ] Google Hybrid for unscored runs is produced only by the existing rule and equals the stored Hybrid on all 259 scored runs.
- [ ] Every recommendation carries its basis per resource, copied from the stored flags; fallback counts match the design plan §5 (233 Google, 19,341 Alibaba latest runs for memory).
- [ ] The API serves every endpoint read-only, with units and labels on every value, and refuses to start on a checksum mismatch.
- [ ] Policy metrics returned by the API equal `final_test_policy_comparison.csv` for each dataset.
- [ ] The OpenAPI contract is committed for Task 16.
- [ ] Export and API tests pass in the locked environment, and the full existing suite still passes.
- [ ] README explains how to run the export and the API.
