# [P1] Task 15: Developer API and Risk-Based Web Frontend

**Labels:** `area-implementation`, `priority-high`

**Owner:** Unassigned (suggested three-contributor split below)

**Priority:** Priority 1 · Required for the demo and for replacing the Figure 8.1 and 8.2 placeholders in the final report · Combines the planned New Issues 7 (output and API), 8 (UI and policy controls) and 9 (UI–API integration) from `docs/planning/295b_scope_and_done.md`.

---

## Objective

Build the presentation layer described in Chapter 4 §4.4 and Chapter 8 §8.3 of the final report: a **read-only REST API** over the published TraceAdvisor results and a **web frontend** on top of it. The frontend lets a developer pick a dataset, look up a recurring workload, choose a **risk level** (Restrictive, Balanced or Efficient), and see the recommended CPU and memory for that workload together with how often that policy was exceeded and how much it wasted in the test period.

The presentation layer only **reads** published results. It never runs the pipeline, retrains a model, recomputes a selection or changes an artifact.

## Why

The evaluation shows that the policies form a scale from safe and wasteful to efficient and risky (Chapter 7). The right point on that scale depends on the job: a job that must not fail justifies extra capacity, while a job that can be rerun can trade some risk for less waste. The frontend turns this into an explicit choice, and every option is shown with its measured risk, so the developer never sees a number without its evidence.

## Current Project State

- All results are final for both datasets (one-time test run each). Nothing in this task may change them.
- **Committed summaries** (in Git): `reports/results/google_subset/tables/final_test_policy_comparison.csv` and `reports/results/alibaba_gpu_2020/final_test/final_test_policy_comparison.csv` (violation rate, waste, shortfall and utilization per policy), plus the figures in `reports/results/*/figures/`.
- **Per-workload recommendations exist only locally** (`data/processed/` is git-ignored):

| Dataset | File | Rows | Workloads | Content |
|---|---|---|---|---|
| Google | `data/processed/google_subset_v1/final_test_row_level.parquet` (0.1 MB) | 1,813 = 259 occurrences × 7 policies | 83 `recurrence_key` | `recommended_cpu`, `recommended_memory`, next-occurrence targets, violation, waste, shortfall per row; long format (`policy_name`) |
| Alibaba | `data/processed/alibaba_gpu_v2020_final_test/final_test_predictions.parquet` (13.6 MB) | 69,285 test occurrences (44,053 with a target, 25,232 `no_next_occurrence`) | 25,232 `recurrence_key` | `rec_{cpu,memory}_{request,mean,p90,p95,p99}`, `ml_recommended_*`, `hybrid_recommended_*`, `actual_*`, target status, units, `recommended_resource_scope`; wide format |

- No API or frontend code exists. No framework has been chosen.

## Risk Levels

The risk levels map to evaluated policies. The mapping is fixed here, not tuned on test results.

| Risk level | Policy | Google test (any-resource violation) | Alibaba test (memory violation / average memory waste) |
|---|---|---|---|
| **Restrictive** (default) | Hybrid | 12.36% | 3.15% / 8.71 GB |
| **Balanced** | P95 | 17.37% | 6.04% / 7.89 GB |
| **Efficient** | P90 | 22.78% | 9.89% / 7.44 GB |

- The numbers above are for orientation only. The API must read them from the summary CSVs, never hard-code them, so corrected results (Tasks 10 and 14) appear automatically after re-export.
- Mean and ML alone are **not** offered as risk levels (exceeded by about a third or more of test occurrences on both datasets). They appear only in the policy comparison view.
- The original **Request** is always shown next to the recommendation as the reference.

## What This Task Builds

### Part A: Published UI artifacts (export step)

A script `scripts/export_ui_artifacts.py` that reads the local final-test outputs and the committed summaries and writes a small, versioned set of files for the API, for example under `reports/results/ui/`:

- `risk_levels.json`: the mapping above (level → policy name per dataset), with a short description of each level.
- `<dataset>/policy_summary.json`: per policy, the test violation rates, waste, shortfall and utilization, with the number of valid rows, copied from the summary CSV.
- `<dataset>/workloads.parquet` (or CSV): one row per workload occurrence in the test period, in a **common long format**: `dataset`, `workload_id` (`recurrence_key`), `occurrence_id`, `occurrence_start` (where available), `policy`, `recommended_cpu`, `recommended_memory`, `request_cpu`, `request_memory`, `actual_cpu`, `actual_memory`, `cpu_violation`, `memory_violation`, units and labels.
- `<dataset>/metadata.json`: source file paths, their SHA-256 checksums, the commit, the decision-manifest checksum of the final test, and the export time.
- `SHA256SUMS` for the exported files.

Rules:

- **No recalculation of results.** Recommendations and metrics are copied from the final-test outputs. The export may only reshape (Google is already long; Alibaba is wide and must be melted), rename and label.
- **Missing values stay missing.** A `no_next_occurrence` row has a recommendation but no actual; keep `actual_*` as null, never 0.
- Every row carries `cpu_unit`, `memory_unit` and `cpu_semantics`: Google `normalized` / `peak`; Alibaba `percent_of_vcpu` / `average_usage`, memory `gb`, scope `task_role_per_instance`.
- Refuse to run on a dirty tree or over an existing export (same convention as the Alibaba scripts: `--force`, `--allow-dirty`, `--out-dir`).
- **Size decision:** the Alibaba export (about 69,000 occurrences × 7 policies) must be compact enough to commit (target under 20 MB, for example Parquet with only the needed columns). If it is not, document where it is shared (Drive) and verify it by checksum, as for the Task 3 data.

### Part B: Read-only REST API

JSON over HTTP, reading only the Part A files. Suggested endpoints (final names are part of this task):

| Endpoint | Returns |
|---|---|
| `GET /datasets` | Available datasets with their labels, units and CPU semantics |
| `GET /risk-levels` | The three levels, their policy per dataset and descriptions |
| `GET /datasets/{dataset}/workloads?search=&limit=&offset=` | Workload list for lookup, paginated (Alibaba has 25,232 test workloads) |
| `GET /datasets/{dataset}/workloads/{workload_id}?risk=restrictive` | The workload's latest recommendation at the chosen risk level, its request, and the policy's test violation rate and waste |
| `GET /datasets/{dataset}/workloads/{workload_id}/history?policy=` | The workload's test occurrences in time order: recommendation, actual and whether it was exceeded |
| `GET /datasets/{dataset}/policies` | Policy comparison: all seven policies' test metrics |
| `GET /health` | Status, and the export's commit and checksum |

Rules:

- **Read-only:** only `GET`; no endpoint writes files or runs pipeline code.
- **Every number travels with its unit and label.** A response without `unit` and `cpu_semantics` is a bug.
- Unknown dataset, workload or risk level → `404` / `400` with a clear message, never an empty success.
- No cross-dataset aggregation (units differ; Chapter 4 Table 4.1).
- Loads the files once at start-up and checks them against `SHA256SUMS`; refuses to start on a mismatch.

### Part C: Web frontend

Views:

1. **Dataset and workload lookup:** choose Google ClusterData 2019 or Alibaba GPU 2020; search or browse workloads.
2. **Risk-based recommendation** (report Figure 8.1): a Restrictive / Balanced / Efficient selector (Restrictive by default). It shows:
   - recommended CPU and memory and the original request, with units;
   - the policy's test violation rate and average waste for this dataset, for example "Memory recommendations at this level were exceeded by 3.15% of test runs, average waste 8.71 GB";
   - the CPU label on Alibaba: "average usage, not peak".
3. **Workload history:** a chart of the workload's test occurrences, actual usage against the recommendation at the selected level, with exceeded runs highlighted.
4. **Policy comparison** (report Figure 8.2): violation rate against waste for all seven policies per dataset (the same view as the Chapter 7 trade-off figures), with the three risk levels marked.
5. **About the data:** dataset descriptions, units, the one-time test, and the fact that the results are from historical replay, not a live cluster.

Rules:

- The frontend talks only to the API; it does not read files directly.
- Never show a value without its unit; never show a missing value as 0 (show "not available").
- Google values are normalized units; say so in the UI instead of converting them.
- Must work in a desktop browser; a phone layout is not required.

### Part D: Tests

- Export: reshaped values equal the source files exactly for every policy (row count and value checks); nulls preserved; units and labels present on every row; refusal on a dirty tree or existing output.
- API: each endpoint's response shape; units on every value; risk mapping per dataset; policy metrics equal the summary CSVs; 404/400 cases; no non-GET routes; start-up refuses a checksum mismatch.
- Frontend: at least a smoke test that the main views load against a test API with small fixture files.
- All tests run in the locked environment (`requirements-lock.txt`); new dependencies are added to `requirements.txt` and the lock file.

### Part E: Report and demo updates

- Replace the placeholders for Figures 8.1 and 8.2 in `docs/project_report/chapter_8_operations_and_reproducibility/` with screenshots, and change §8.3 from "planned" to "implemented"; name the frameworks there once chosen.
- Check that Chapter 2 §2.2.6 / Figure 2.1 and Chapter 4 §4.4 / Figure 4.4 still match what was built.
- README: how to run the export, the API and the frontend locally (three commands).
- Demo script: one Google and one Alibaba workload shown at all three risk levels, then the policy comparison.

## What This Task Does Not Build

- Live or shadow-mode recommendations for new submissions (Chapter 9 future work).
- Authentication, user accounts, hosting or deployment beyond running locally.
- Any rerun, retraining, reselection or new metric. If Task 10 or Task 14 produces corrected results, rerun only the Part A export.
- Azure, Splitwise or ModServe results.
- GPU recommendations.

## Decisions Needed Before Starting

1. **Frameworks** for the API and the frontend (team choice; keep them lightweight and testable).
2. **Where the Alibaba export lives:** in Git if compact, otherwise on Drive with checksums.
3. **"Latest recommendation" definition:** proposed as the recommendation for the workload's last test occurrence, which is the one closest to a real next-run recommendation.

## Suggested Split

| Contributor | Parts |
|---|---|
| 1 | Part A (export) and its tests |
| 2 | Part B (API) and its tests, against the Part A files |
| 3 | Part C (frontend) against mock API responses first, then the real API; Part E screenshots |

Parts B and C can start in parallel once the Part A file format is agreed.

## Acceptance Criteria

- [ ] `scripts/export_ui_artifacts.py` produces the Part A files for both datasets from the final-test outputs, with checksums and metadata; values equal the sources exactly.
- [ ] The API serves all endpoints read-only, with units and labels on every value, and refuses to start on a checksum mismatch.
- [ ] The frontend shows the risk-based recommendation, workload history and policy comparison for both datasets; Restrictive is the default.
- [ ] Risk-level metrics in the UI equal `final_test_policy_comparison.csv` for each dataset.
- [ ] Missing values are shown as "not available", and Alibaba CPU is labelled average usage everywhere it appears.
- [ ] Tests for export, API and frontend pass in the locked environment, and the full existing suite still passes.
- [ ] Figures 8.1 and 8.2 in the report are replaced with screenshots, and §8.3 is updated.
- [ ] README explains how to run it locally.
