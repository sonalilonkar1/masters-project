# Recommendation Service: Design Plan (Tasks 15 and 16)

**Status:** Task 15 (export and API) implemented; the verified bundle is in `reports/results/ui/`. Task 16 builds the web UI.
**Snapshot:** 2026-11-16, checked against `main` at `d46e282`, a full read of `src/` and `pipelines/google_subset/`, and the local `data/processed/` outputs.

---

## 1. Goal

A developer chooses a dataset (Google ClusterData 2019 or Alibaba GPU 2020), finds a workload, chooses how much risk they accept, and sees the CPU and memory recommendation for that workload's next run, together with the evidence behind it: how often that policy was exceeded on the test period, how much capacity it wasted, and how the recommendation compared with what the workload actually used on its earlier test runs.

The service **presents results that already exist**. It does not train, select, tune, rescore or evaluate anything, and it never changes a published number.

## 2. User Flow

```
Dataset ──► Workload ──► Risk level ──► Recommendation + evidence
(Google /    (search,      (Restrictive /    ├─ recommended CPU and memory, with the original request
 Alibaba)     browse)       Balanced /       ├─ how the number was built (rule, history, inputs)
                            Efficient)       ├─ policy's test violation rate and waste on this dataset
                                             └─ workload history: recommendation vs actual per test run
```

A second view compares all seven policies on the selected dataset (violation rate against waste), with the three risk levels marked. This is report Figure 8.2; the recommendation view is Figure 8.1.

## 3. Non-Goals

- Live or shadow recommendations for new submissions (Chapter 9 future work).
- Any new metric, model, selection or evaluation; corrected results (Tasks 10, 14) arrive only by re-running the export.
- Authentication, hosting or deployment beyond running locally.
- Cross-dataset aggregation or ranking (units and semantics differ; report Table 4.1).
- GPU recommendations; Azure, Splitwise or ModServe results.

## 4. Architecture

```
 data/processed/ (local, git-ignored)          reports/results/ (committed)
   final-test outputs, test occurrences          final_test_policy_comparison.csv
            │                                              │
            └──────────────┬───────────────────────────────┘
                           ▼
          [1] Export  scripts/export_ui_artifacts.py         ← Task 15, offline, run once per result version
                           │  reshape + label only, checksums
                           ▼
          [2] UI bundle  (immutable, versioned, SHA256SUMS)
                           │  loaded once, verified at start-up
                           ▼
          [3] API  read-only HTTP/JSON                       ← Task 15
                           │  the only interface to the bundle
                           ▼
          [4] Web UI  dataset → workload → risk → evidence   ← Task 16
```

Design choices and why:

| Choice | Reason |
|---|---|
| An offline export produces a fixed bundle; the API never reads pipeline outputs | Pipeline outputs are large, wide, dataset-specific and git-ignored. A small bundle in one common format keeps the API simple, makes every served number traceable to a checksum, and lets corrected results replace the bundle without code changes. |
| The API is read-only and stateless | Nothing to secure or migrate; the bundle is the single source of truth. |
| The UI talks only to the API | One place enforces units, labels and missing-value rules; the UI cannot drift from the data contract. |
| Risk levels map to existing policies in a config file | The mapping is a presentation choice made in advance, not tuned on test results; changing it needs no code change. |

## 5. Data Sources (verified 2026-11-16)

| | Google ClusterData 2019 subset | Alibaba GPU 2020 |
|---|---|---|
| Test occurrences | 731 in `test_occurrences.parquet` | 69,285 in `final_test_predictions.parquet` |
| … with a next-run target (scored) | 259 (`final_test_row_level.parquet`, long format, 7 policies) | 44,053 |
| … without a next run (`no_next_occurrence`) | 472, exactly one per workload (its last test run) | 25,232, exactly one per workload |
| Workloads (`recurrence_key`) | 472 (83 with at least one scored run; 16 with five or more); key = `user‖logical name` | 25,232 (5,650 with five or more test runs); key = `group‖task` |
| Unique row key | `occurrence_id` (= `recurrence_key‖start`) | **`role_key`** (`group‖job‖task`). `occurrence_id` (`group‖job`) is shared by every role of a job: 68,677 unique among 69,285 rows |
| Locked baseline | P99, `min_runs = 1` (N04 `metadata.json`) | P99, `min_runs = 10` (Task 6 `baseline_selection.json`) |
| ML model | Random forest per resource, log1p target (N05) | HistGradientBoosting per resource (Task 7) |
| History-or-fallback flags | `uses_history_{cpu,memory}_{mean,p90,p95,p99}` in `test_occurrences.parquet` | Same columns in Task 6 `recommendations_test.parquet` |
| Baseline recommendations | `test_occurrences.parquet`: `rec_{cpu,memory}_{request,mean,p90,p95,p99}` | `final_test_predictions.parquet`: same names |
| ML recommendations | `test_ml_predictions.parquet`: `ml_pred_cpu`, `ml_pred_memory` | `ml_recommended_{cpu,memory}` |
| Hybrid | `max(ML, P95)`; stored only for the 259 scored rows | `max(ML, P99)`; stored for all rows as `hybrid_recommended_*` |
| Actual (next run) | `target_cpu_next_occurrence_peak_ncu`, `target_memory_next_occurrence_peak_normalized` | `actual_cpu`, `actual_memory` with target statuses |
| Run start time | `execution_start_time_us` | `start_time_us` (join with `alibaba_gpu_v2020_targets/test.parquet` on `role_key`) |
| Policy metrics | `reports/results/google_subset/tables/final_test_policy_comparison.csv` | `reports/results/alibaba_gpu_2020/final_test/final_test_policy_comparison.csv` |
| Units | CPU `ncu`, memory `normalized`; both are next-run **peaks** | CPU `percent_of_vcpu`, **average usage**; memory `gb`, peak; scope `task_role_per_instance` |

Two facts follow from this table and shape the design:

1. **The "latest recommendation" is each workload's last test run**, the `no_next_occurrence` row. It is the one genuinely forward-looking recommendation: its actual has not happened in the data. Every workload has exactly one such row in both datasets.
2. **Google's stored Hybrid covers only the 259 scored rows.** To show a latest Hybrid recommendation for all 472 Google workloads, the export applies the existing rule `src/policies/hybrid.py::hybrid_recommendation(ML, P95)` to the locked ML and P95 values. This re-applies a frozen rule to frozen inputs; it is not a new result. The export must prove it: on the 259 scored rows, the recomputed values must equal the stored Hybrid values exactly (checked 2026-11-16: they do). No metric is ever recomputed.
3. **Most latest recommendations fall back to the request.** Below `min_runs` earlier runs, every history policy equals the request and Hybrid becomes `max(ML, request)`. This is true for the latest run of 233 of 472 Google workloads (49.4%) and 19,341 of 25,232 Alibaba workloads (76.7%), although most *runs* have history (Alibaba 56%, Google 67%). For these workloads all three risk levels give the same answer, so the service must show the basis of each number (history of n runs, or request fallback) and copy it from the stored `uses_history_*` flags, never recompute it.

## 6. UI Bundle (Export Output)

Location: `reports/results/ui/` (committed: about 12 MB with zstd-compressed Parquet, under the 20 MB limit). Four files at the top level and one folder per dataset:

| File | Content |
|---|---|
| `manifest.json` | Bundle schema version, `bundle_status` (`verified` or `development`), status and source run ID per dataset, export commit, time and library versions |
| `risk_levels.json` | Level → policy per dataset, with descriptions; copied from `config/ui_risk_levels.json` |
| `rules.json` | One rule per dataset and policy, copied from the frozen records: description, `min_runs`, Hybrid safeguard, ML model (Google N04 `metadata.json`, N05 `ml_metadata.json`, N06 `decision_manifest.json`; Alibaba Task 6 `baseline_selection.json`, Task 7 `decision_manifest.json`) |
| `<dataset>/dataset.json` | Display name, units, CPU and memory semantics, scope, primary resource, population sizes, notes (e.g. "historical replay, not a live cluster") |
| `<dataset>/policy_metrics.json` | Per policy: violation rates, average waste, shortfall and utilization, valid-row counts; copied field by field from the summary CSV |
| `<dataset>/workloads.parquet` | One row per workload: `workload_id`, `display_name`, `test_run_count`, `scored_run_count`, `first_start_time_us`, `last_start_time_us`, `latest_occurrence_id`, `latest_uses_history`, `has_scored_history` |
| `<dataset>/recommendations.parquet` | One row per (occurrence, policy), the common long format below |
| `<dataset>/metadata.json` | Source paths and SHA-256, source run ID, decision-manifest checksum, code commit, export time, row counts |
| `SHA256SUMS` | Checksums of every other file in the bundle; the API refuses to start if a file is missing, changed or unlisted |

Common long format for `recommendations.parquet`:

| Column | Type | Note |
|---|---|---|
| `workload_id` | string | `recurrence_key` |
| `occurrence_id` | string | |
| `role_key` | string, nullable | Alibaba only; the unique row key used for every join |
| `start_time_us` | int64 | Run start, for ordering and the history chart |
| `target_occurrence_id`, `target_start_time_us` | nullable | The next run the recommendation is compared with; null when there is none |
| `policy` | string | One of the seven policies |
| `recommended_cpu`, `recommended_memory` | float, nullable | Null when the policy has no value (for example Request on a run without a request) |
| `request_cpu`, `request_memory` | float, nullable | The Request policy value of the same run; null when the run has no request |
| `actual_cpu`, `actual_memory` | float, nullable | Next-run value; null when there is no next run. Never 0 |
| `cpu_target_status`, `memory_target_status` | string | Canonical `TARGET_STATUSES` from `src/canonical/schema.py` (`available`, `no_next_occurrence`, `next_occurrence_ineligible_resource`, …), kept per resource because Alibaba stores them separately |
| `cpu_exceeded`, `memory_exceeded` | bool, nullable | `actual > recommended`; null when actual is null. Copied from the row-level violation flags where stored |
| `is_latest` | bool | The workload's last test run |
| `cpu_basis`, `memory_basis` | string | `history` or `request_fallback`, copied from the stored `uses_history_*` flag of the policy's safeguard (P95 for Google Hybrid, P99 for Alibaba Hybrid; the policy itself for P90/P95/P99; `request` for Request; `model` for ML, and for Hybrid when its safeguard has no value, which happens on 2 latest Google runs with neither a request nor history) |
| `cpu_history_run_count`, `memory_history_run_count` | int, nullable | Earlier completed runs, null for Request and ML; copied (`occ_hist_peak_*_count` for Google, `*_history_count` for Alibaba) |

Units and semantics are stored once in `dataset.json`, not repeated per row; the API attaches them to every value it returns. Exact column types and nullability are fixed in `src/service/contract.py`.

Export rules:

1. **Copy, reshape, rename, label.** No recalculation except the Google Hybrid case in §5, which is verified against stored values.
2. **Missing stays missing.** Null actuals stay null; a missing request stays null.
3. **Use only the agreed inputs.** Every input must match the checksum committed on `main`: Alibaba against `reports/results/alibaba_gpu_2020/verification/artifact_manifest.json` (and the same `run_id` and manifest checksum as `final_test/run_record.json`), Google against `reports/results/google_subset/decision_manifest.json`. References are read at export time, never hard-coded. `--allow-unverified-source` allows other files for development only; the bundle is then marked `development` and must not be published. See Task 15, Source of Truth.
4. **Self-checks before writing:** per-policy row counts, equality of every copied value with its source, one `is_latest` row per workload, policy metrics equal to the summary CSV, and every Alibaba join on `role_key` validated one-to-one.
5. Same command-line conventions as the Alibaba scripts: refuses a dirty tree and an existing output unless `--allow-dirty` or `--force`; `--out-dir`.

## 7. API Contract

Read-only JSON over HTTP, served from the bundle. Base path `/api/v1`.

| Endpoint | Purpose | UI step |
|---|---|---|
| `GET /datasets` | Datasets with display names, units, semantics, sizes | Dataset selector |
| `GET /risk-levels` | Levels, their policy per dataset, descriptions | Risk selector |
| `GET /datasets/{dataset}/workloads?search=&has_history=&sort=&limit=&offset=` | Paginated workload list; `search` matches the ID or display name; `has_history=true` (UI default) keeps workloads whose latest recommendation uses history; `sort` = `test_runs` (default, descending) or `id` | Workload lookup |
| `GET /datasets/{dataset}/workloads/{workload_id}/recommendation?risk=` or `?policy=` | Latest recommendation, request, the rule that produced it, and the policy's test metrics | Recommendation panel |
| `GET /datasets/{dataset}/workloads/{workload_id}/history?policy=` | All test runs in time order: recommendation, actual, exceeded | History chart |
| `GET /datasets/{dataset}/policies` | All seven policies' test metrics, with risk levels marked | Policy comparison |
| `GET /health` | Status, bundle version, commit, checksum, source run IDs | Footer, monitoring |

Default sort by test-run count matters for the demo: half the workloads in both datasets have a single test run, so the first page should show workloads with a real history.

The exact request and response schemas are in `docs/design/recommendation_api_openapi.json`, generated from the app; Task 16 codes against that file. A shortened response from the verified bundle:

`GET /api/v1/datasets/alibaba_gpu_v2020/workloads/{id}/recommendation?risk=restrictive`

```json
{
  "dataset_id": "alibaba_gpu_v2020",
  "workload_id": "7755b21b…||xComputeWorker",
  "display_name": "7755b21b… / xComputeWorker",
  "risk_level": "restrictive",
  "policy": "Hybrid",
  "policy_id": "hybrid",
  "latest_run": {"occurrence_id": "…", "role_key": "…", "start_time_us": 6450729000000},
  "primary_resource": "memory",
  "resources": [
    {"resource": "memory", "unit": "gb", "semantics": "peak", "label": "Peak usage",
     "recommended": 6.36, "request": 19.55, "basis": {"type": "history", "history_run_count": 17289}},
    {"resource": "cpu", "unit": "percent_of_vcpu", "semantics": "average_usage", "label": "Average usage, not peak",
     "recommended": 102.76, "request": 1000.0, "basis": {"type": "history", "history_run_count": 17289}}
  ],
  "same_for_all_risk_levels": false,
  "rule": {"policy": "Hybrid", "description": "Larger of the ML prediction and the P99 of the workload's earlier runs …",
           "min_runs": 10, "safeguard_policy": "P99", "ml_model": {"cpu": "hist_gradient_boosting", "memory": "hist_gradient_boosting"}, "source": "…"},
  "policy_evidence": {
    "policy": "Hybrid", "risk_levels": ["restrictive"], "available_datasets": ["google_clusterdata2019", "alibaba_gpu_v2020"], "row_count": 44053,
    "resources": [
      {"resource": "memory", "unit": "gb", "semantics": "peak", "label": "Peak usage", "violation_pct": 3.18, "valid_violation_count": 44053, "average_waste": 8.70, "…": "…"},
      {"resource": "cpu", "unit": "percent_of_vcpu", "semantics": "average_usage", "label": "Average usage, not peak", "violation_pct": 3.62, "valid_violation_count": 44045, "average_waste": 327.47, "…": "…"}
    ],
    "any_resource": null
  },
  "bundle": {"bundle_status": "verified", "dataset_status": "verified", "source_run_id": "4fdc7e96-…", "bundle_checksum": "ccef27ea…"}
}
```

`policy_evidence` is the policy's dataset-wide final-test result, not a score for this workload. The history endpoint returns one item per test run with `occurrence_id`, `start_time_us`, `target_occurrence_id`, `target_start_time_us` and, per resource, `unit`, `semantics`, `label`, `recommended`, `actual`, `exceeded` and `target_status`. Every policy in `/policies` and in `policy_evidence` lists its `available_datasets`, computed from the bundle. `primary_resource` is `memory` on Alibaba and null on Google.

API rules:

- Only `GET`. No endpoint writes files or runs pipeline code.
- Every numeric value travels with `unit`; every CPU value on Alibaba with `semantics: average_usage` and its label. A value without a unit is a bug.
- Missing values are `null`, never 0, never omitted.
- Errors share one body, `{"error": {"code": "...", "message": "..."}}`: unknown dataset, workload or route → `404 not_found`; invalid or conflicting query (`risk` and `policy` together, unknown risk level or policy, bad sort or pagination) → `400 invalid_parameter` (FastAPI's default 422 is replaced); any method other than `GET` → `405 method_not_allowed`; unexpected failure → `500 internal_error`.
- Memory is listed before CPU on Alibaba (primary resource), matching the report.
- No response combines datasets.
- At start-up the API verifies every bundle file against `SHA256SUMS` and refuses to start on a mismatch.
- The API publishes its contract as OpenAPI; Task 16 develops against it.

Performance: the largest table is about 485,000 rows (69,285 Alibaba runs × 7 policies). It is loaded once into memory and indexed by `(dataset, workload_id, policy)`; every endpoint is a dictionary lookup or a slice. No database is needed.

## 8. Risk Levels

Defined in `config/ui_risk_levels.json`, fixed before the UI is built and not tuned on test results:

| Level | Policy | Meaning |
|---|---|---|
| Restrictive (default) | Hybrid | Fewest exceeded runs; most capacity held back |
| Balanced | P95 | Middle of the trade-off |
| Efficient | P90 | Least waste; more runs exceed the recommendation |

Mean and ML alone are not offered as levels (exceeded by about a third or more of test runs on both datasets); they appear only in the policy comparison. The numbers shown for each level are always read from the bundle, never written in code.

## 9. Web UI (Task 16)

Views: (1) dataset and workload lookup; (2) recommendation with risk selector, request, rule and policy test metrics; (3) workload history chart, recommendation line against actual per run, exceeded runs highlighted; (4) policy comparison; (5) about the data (units, one-time test, historical replay).

Fallback handling: the workload list shows workloads with history by default, with a toggle for all. When a resource falls back, the panel says so plainly, for example "Only 3 earlier runs (needs 10): we keep your request". When `same_for_all_risk_levels` is true, the risk selector is shown but marked as having no effect for this workload.

History chart meaning: each point is the recommendation made at run *i* compared with the usage of run *i + 1*; the x-axis is the start of run *i*.

Display rules: every value with its unit; null shown as "not available"; Alibaba CPU labelled "average usage, not peak" wherever it appears; Google values shown in normalized units with an explanation, never converted to cores or GiB; Alibaba memory shown first. Desktop browser only.

## 10. Technology

| Layer | Proposal | Reason |
|---|---|---|
| Export | Python, pandas, pyarrow (already in the lock file) | Same stack and conventions as the pipeline scripts |
| API | FastAPI with Uvicorn | Typed response models, automatic OpenAPI contract for Task 16, `TestClient` for pytest; small dependency set |
| UI | Decided in Task 16 (proposal: static HTML/JS with Chart.js, served by the API; no build step) | Keeps the repository Python-only and runnable with one command; React is the alternative if the team wants richer interaction |

New dependencies go into `requirements.txt` and `requirements-lock.txt`.

## 11. Repository Layout

```
config/ui_risk_levels.json
scripts/export_ui_artifacts.py          # CLI wrapper
src/service/
    export.py                           # build the bundle (pure functions, tested)
    bundle.py                           # load and verify the bundle, indexes
    api.py                              # FastAPI app and routes
    schemas.py                          # response models
web/                                    # Task 16 frontend
reports/results/ui/                     # the bundle
tests/test_ui_export.py
tests/test_api.py
tests/fixtures/ui_bundle/               # tiny hand-built bundle for API and UI tests
```

## 12. Testing

| Layer | Tests |
|---|---|
| Export | Every copied value equals its source per policy; row counts; nulls preserved; one latest row per workload; Google recomputed Hybrid equals stored Hybrid on the 259 scored rows; policy metrics equal the CSVs; refuses a run without verified provenance, a dirty tree or an existing output |
| API | Response shape per endpoint against the schema; units on every value; risk mapping per dataset; metrics equal the bundle; 400, 404 and 405 cases; no non-GET routes; start-up refuses a checksum mismatch; runs on the fixture bundle, so tests need no local data |
| UI (Task 16) | Smoke test that each view loads against the fixture-backed API; unit labels and "not available" rendering |
| Whole repo | Existing `pytest` suite still passes in the locked environment |

## 13. Delivery Plan

| Step | Task | Pull request | Can start |
|---|---|---|---|
| 1 | 15 | Risk-level config, bundle format and the export with its tests | Now on local data; final export from the Nov 15 run |
| 2 | 15 | API, fixture bundle and API tests; contract frozen | After step 1's format is agreed |
| 3 | 16 | UI against the fixture-backed API | After step 2's contract is agreed |
| 4 | 16 | Real bundle, screenshots for Figures 8.1 and 8.2, §8.3, README, demo script | After steps 1–3 |

## 14. Risks and Open Decisions

| Item | Impact | Proposal |
|---|---|---|
| Alibaba source run: PR #121 (merged 2026-11-16) published the Nov 15 run (`4fdc7e96…`) on `main`; the report and the local outputs are still the Oct 30 run | Exported numbers must match `main` | Get the Nov 15 outputs locally; export enforces provenance (§6 rule 3); report numbers updated in a separate PR |
| Most latest recommendations fall back to the request (§5 fact 3) | Risk levels look meaningless for most workloads | Show the basis; default to workloads with history; demo with those; state the limit in the report (Ch7 §7.5, Ch9) |
| Alibaba bundle size | Over 20 MB cannot be committed | Measure after step 1; Drive with checksums otherwise |
| Google results may be corrected (Task 10) | Bundle becomes stale | Re-run the export only; no code change |
| Google Hybrid for unscored rows is re-applied, not stored | Could be read as a new result | Verified equality on scored rows; recorded in `metadata.json`; stated in the About view |
| Most workloads have no scored run (Google 389 of 472, Alibaba 15,512 of 25,232 on the Oct 30 files) | History chart is empty for most workloads | Default sort by test runs; the UI says when a workload has no scored run yet |
| UI framework | Affects Task 16 only | Team decision at the start of Task 16 |
