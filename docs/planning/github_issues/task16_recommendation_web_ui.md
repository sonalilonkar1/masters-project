# [P1] Task 16: Recommendation Web UI

**Labels:** `area-implementation`, `priority-high`
**Owner:** Unassigned
**Priority:** P1 — Required for the demo and for replacing the Figure 8.1 and 8.2 placeholders in the final report
**Related design:** `docs/design/recommendation_service_design_plan.md` (§2, §6–9, §12–14)
**Related summary:** `docs/design/discussion_summary_2026-11-16.md`
**Backend task:** Task 15 (#120, PR #131; `task15_recommendation_backend_api.md`)
**Related planning document:** `docs/planning/295b_scope_and_done.md` (planned New Issues 8 and 9)

## Objective

Build the web interface that allows a developer to:

1. Select Google ClusterData 2019 or Alibaba GPU 2020.
2. Search and select a workload.
3. Select a risk level.
4. See the CPU and memory recommendation for the workload's next run next to the original request.
5. Understand the evidence behind it:
   - Whether each number is based on the workload's history, falls back to the request, or comes from the ML model alone.
   - The rule that produced it.
   - How often that policy was exceeded and how much it wasted on the test period.
   - The workload's earlier recommendations compared with what the next run actually used.

The UI reads everything from the Task 15 API. It computes no recommendations or metrics and contains no hard-coded result numbers.

## Current Project State

- No frontend exists. Report Chapter 8 §8.3 describes it as planned, with placeholders for Figure 8.1 (recommendation view) and Figure 8.2 (policy comparison).
- **The Task 15 backend is built** (PR #131, on `feature/task15-backend` until it merges):
  - Read-only API under `/api/v1`: `src/service/api.py`.
  - API contract: `docs/design/recommendation_api_openapi.json`, generated from the app. The response schemas in this file are the source of truth for field names.
  - Fixture bundle: `tests/fixtures/ui_bundle/`, which lets the API run without pipeline data. It covers history, request fallback, no scored run, null requests and actuals, differing CPU and memory bases and target statuses, and a workload ID containing `/`.
  - Verified bundle: `reports/results/ui/` (checksum `ccef27ea…`, `bundle_status: verified`), built from the Nov 15 Alibaba run (`4fdc7e96…`) on `main`. Use it for the final screenshots.
- Run the API locally:

  ```bash
  # Fixture bundle (development and UI tests)
  TRACEADVISOR_UI_BUNDLE=tests/fixtures/ui_bundle uvicorn --factory src.service.api:create_app

  # Verified bundle (demo and screenshots)
  uvicorn --factory src.service.api:create_app
  ```

  Interactive API docs are at `http://127.0.0.1:8000/docs`.

### Facts the UI must handle

These are counted from the verified bundle:

| Fact | Google | Alibaba | UI consequence |
|---|---|---|---|
| Workloads | 472 | 25,232 | Paginated search, never a full list |
| Latest recommendation falls back to the request (P95/P99) | CPU 231, memory 233 of 472 | CPU 19,342, memory 19,341 of 25,232 | Explain the fallback per resource; default to workloads with history |
| Latest Hybrid recommendation with no request and no history | 2 workloads (basis `model`) | 0 | Show the ML-only explanation |
| Test runs that use history | 67% | 56% | Most activity comes from recurring workloads |
| Workloads with no scored run (one test run, or no next run observed) | 389 of 472 (82%) | 15,512 of 25,232 (61%) | History chart is empty for most workloads; the empty state is the common case |
| `min_runs` (history needed) | 1 | 10 | Shown in the fallback message |
| CPU meaning | Peak, normalized `ncu` | Average usage, `percent_of_vcpu` | Alibaba CPU label everywhere |
| Memory meaning | Peak, normalized | Peak, `gb` | Alibaba memory shown first |

For a workload that falls back, all three risk levels give the same answer. The API reports this as `same_for_all_risk_levels`, and the UI must say so rather than implying a choice.

## User Flow

```text
Dataset ──► Workload ──► Risk level ──► Recommendation + evidence
                                         ├─ recommended CPU and memory vs request
                                         ├─ basis per resource (history, request fallback or model)
                                         ├─ rule and inputs
                                         ├─ policy test evidence for this dataset
                                         └─ workload history chart
```

A separate view compares all seven policies on the selected dataset.

## Scope

### Part A: Framework Decision

Choose and record the approach in the design plan §10 before building views.

| Option | Pros | Cons |
|---|---|---|
| **Static HTML/JS + Chart.js, served by the Task 15 FastAPI app (proposal)** | No build step; one process; no CORS; Python-only repository | Less structure for complex state |
| React (Vite) as a separate app | Component structure, richer interaction | Node toolchain, `package.json`, separate test setup; CORS must be enabled in `src/service/api.py` (Task 15 deliberately leaves it off) |

Requirements:

- [ ] Decision recorded in the design plan §10 with the reason.
- [ ] The UI is served locally with one documented command (or two, if a separate frontend server is chosen).
- [ ] Chart library vendored or pinned; no runtime dependency on an external service.
- [ ] Any change to the Task 15 API (for example CORS or a static-file mount) keeps every route read-only, and the OpenAPI file is regenerated with `python scripts/export_openapi.py`.

### Part B: Views

Each view lists the API it uses. Field names below are from the OpenAPI contract.

#### 1. Dataset selector

`GET /api/v1/datasets`

- [ ] Google ClusterData 2019 and Alibaba GPU 2020, each with its `display_name`, units, CPU meaning (`resources[].label`) and population sizes (`population`).
- [ ] Changing the dataset resets the workload and risk selection.

#### 2. Workload lookup

`GET /api/v1/datasets/{dataset}/workloads?search=&has_history=&sort=&limit=&offset=`

- [ ] Search box (workload ID or display name) and paginated results (`total`, `limit` up to 200, `offset`).
- [ ] Default: workloads whose latest recommendation uses history (`has_history=true`), sorted by number of test runs, descending (`sort=test_runs`).
- [ ] Toggle "Show all workloads" (`has_history` omitted), with a one-line explanation that many workloads have too little history.
- [ ] Each row shows `display_name`, `test_run_count`, `scored_run_count` and a badge from `latest_uses_history`: "history" or "uses your request".
- [ ] Workload IDs URL-encoded when calling the API (IDs can contain `/` and `||`).

#### 3. Recommendation panel (Figure 8.1)

`GET /api/v1/risk-levels`, `GET /api/v1/datasets/{dataset}/workloads/{workload_id}/recommendation?risk=`

- [ ] Risk selector Restrictive / Balanced / Efficient; Restrictive by default (`default_risk_level`); each option shows its one-line `description` from the API.
- [ ] Recommended value next to the original request for each entry in `resources` (`recommended`, `request`, `unit`), in the order the API returns them (memory first on Alibaba); the resource named by `primary_resource` is emphasized (memory on Alibaba, none on Google).
- [ ] Basis per resource from `resources[].basis.type`, with N from `basis.history_run_count` and `min_runs` from `rule.min_runs`:
  - `history`: "Based on N earlier runs".
  - `request_fallback`: "Only N earlier runs (needs `min_runs`): we keep your request".
  - `model`: "No request and no history: ML prediction only".
  - CPU and memory can differ and are shown separately.
- [ ] When `same_for_all_risk_levels` is true, the selector shows "Risk levels give the same answer for this workload until it has enough history".
- [ ] Rule from `rule.description`, with `rule.safeguard_policy` and `rule.ml_model` where present.
- [ ] Policy test evidence from `policy_evidence.resources[]` (`violation_pct`, `average_waste`, valid counts), for example "At this level, memory recommendations were exceeded in X% of test runs; average waste Y GB". Labelled as dataset-wide, not specific to this workload.
- [ ] Next to that evidence, the same numbers for keeping the original request, from the `Request` row of `GET /api/v1/datasets/{dataset}/policies`, for example "Keeping your request: memory exceeded in 3.16% of test runs; average waste 22.3 GB". Shown for every risk level and resource, so the user sees the trade-off rather than assuming a level is always safer than the request: on Alibaba memory, Hybrid (3.18%, 8.70 GB) has about the same violation rate as the request (3.16%) with 61% less waste, while on Alibaba CPU and on Google it has far fewer violations. No wording in the UI may claim a risk level is safer than the request; only the numbers are compared.
- [ ] Source line in small print: `bundle.source_run_id`, `bundle.bundle_checksum` and `bundle.bundle_status`.

#### 4. Workload history

`GET /api/v1/datasets/{dataset}/workloads/{workload_id}/history?risk=`

- [ ] One chart per resource (memory first on Alibaba).
- [ ] Each point is the recommendation made at run *i* compared with the usage of run *i + 1*; the x-axis is `start_time_us` of run *i*, and the tooltip shows both start times when `target_start_time_us` is available.
- [ ] Recommendation line for the selected risk level; actual usage (`actual`) as points; exceeded runs (`exceeded: true`) highlighted.
- [ ] A point whose `actual` is null is never plotted as zero. That covers both `target_status` values `no_next_occurrence` and `next_occurrence_ineligible_resource`; such points are omitted or marked "next run not observed".
- [ ] Empty state: "No scored runs yet: this workload has not run again in the test period".

#### 5. Policy comparison (Figure 8.2)

`GET /api/v1/datasets/{dataset}/policies`

- [ ] Violation rate against average waste for all seven policies on the selected dataset, one chart per resource; any-resource view for Google only (`any_resource` is null on Alibaba).
- [ ] The three risk levels marked on their policies (`risk_levels`); `available_datasets` checked before showing a policy.
- [ ] Table under the chart with the same values and their valid-row counts.
- [ ] No chart or table combines the two datasets.

#### 6. About the data

`GET /api/v1/datasets`, `GET /api/v1/health`

- [ ] Dataset descriptions, units and semantics, and dataset `caveats`.
- [ ] The one-time final test, and that results are historical replay, not a live cluster.
- [ ] The request fallback and why most workloads use it.
- [ ] The Hybrid rule for each dataset from the recommendation response's `rule` (Google: larger of ML and P95; ML alone when there is no request and no history).
- [ ] Bundle status, schema version, export commit and checksum from `/health`.

### Part C: Display Rules

- [ ] Every value shown with its unit.
- [ ] `null` shown as "not available", never 0 and never blank.
- [ ] Alibaba CPU labelled "Average usage, not peak" wherever it appears, using the `semantics` and `label` the API returns on every resource (recommendation, history and policy metrics); Alibaba memory shown before CPU.
- [ ] Google values shown in normalized units with a short explanation; never converted to cores or GiB.
- [ ] Percentages and quantities rounded for display only; the API value is used in tooltips.
- [ ] No view combines or ranks datasets.
- [ ] Every number comes from the API; none is written in the frontend code.
- [ ] Basic accessibility: readable contrast, labelled controls, keyboard-usable selectors, chart data also available as a table.
- [ ] Desktop browser; a phone layout is not required.

### Part D: States and Errors

- [ ] Loading state for every API call.
- [ ] `400` and `404` errors shown with the API's `error.message`, not a blank view.
- [ ] API unreachable or `/health` not OK: a clear banner, with no stale numbers shown.
- [ ] A `development` bundle (`bundle_status` from `/health`) shows a visible "development data" banner.
- [ ] Changing dataset, workload or risk level cancels or ignores outdated responses.

### Part E: Tests

- [ ] Smoke test that each view loads against the API running on the Task 15 fixture bundle.
- [ ] Rendering checks: units present, Alibaba CPU label, memory first on Alibaba, "not available" for nulls.
- [ ] Basis checks on the fixture: the fallback message appears; `same_for_all_risk_levels` shows the "same answer" note; the Google workload `u/2||B` shows the ML-only (`model`) message.
- [ ] Request comparison check: the recommendation panel shows the `Request` policy's violation rate and waste from the fixture's `/policies` response next to the selected level's evidence.
- [ ] History checks: points with a null `actual` are not plotted as zero; the empty state appears for a workload without scored runs.
- [ ] Error checks: a `404` workload and an unreachable API show their messages.
- [ ] Dependencies added to `requirements.txt` and `requirements-lock.txt`, or a documented frontend toolchain if Part A chooses one; the full existing suite still passes.

### Part F: Report and Demo

- [ ] Screenshots from the verified bundle in `reports/results/ui/` (`bundle_status: verified`, Nov 15 Alibaba run; never a `development` bundle) replace the Figure 8.1 and 8.2 placeholders in `docs/project_report/chapter_8_operations_and_reproducibility/`.
- [ ] §8.3 changes from "planned" to "implemented" and names the frameworks.
- [ ] Check that Chapter 2 §2.2.6 / Figure 2.1 and Chapter 4 §4.4 / Figure 4.4 still match what was built; update the Chapter 8 source map.
- [ ] Rebuild the report (`assemble_report.py`, `build_latex.py`).
- [ ] README: how to open the UI locally (after the Task 15 commands).
- [ ] Demo script:
  1. One Google and one Alibaba workload with history, at all three risk levels.
  2. One workload that falls back to the request, showing the explanation.
  3. The workload history chart.
  4. The policy comparison.

## Non-Goals

This task does not include:

- The export or the API (Task 15), apart from the small serving changes allowed in Part A.
- Any calculation of recommendations or metrics in the browser.
- New metrics, including the history-versus-fallback outcome breakdown (Task 14).
- Live or shadow recommendations.
- Authentication, user accounts, hosting or deployment beyond running locally.
- GPU recommendations or other datasets.
- A phone layout.

## Dependencies

- Task 15 OpenAPI contract and fixture bundle: **available** in PR #131. Work can start from `feature/task15-backend` and rebase onto `main` after the PR merges.
- Task 15 verified bundle (Nov 15 Alibaba run, `bundle_status: verified`): **available** in `reports/results/ui/` (PR #131), for the final screenshots.

## Blocks

- Final report Chapter 8 §8.3 and Figures 8.1 and 8.2.
- The demo.

## Suggested Pull Requests

| PR | Scope |
|---|---|
| PR 1 | Part A decision, views against the fixture-backed API, display rules, states and errors, tests |
| PR 2 | Final bundle screenshots, report updates, README and demo script |

## Acceptance Criteria

- [ ] The framework decision is recorded in the design plan.
- [ ] A developer can go from dataset to workload to risk level to recommendation for both datasets; Restrictive is the default.
- [ ] The workload list defaults to workloads with history and can show all workloads.
- [ ] Every recommendation shows its basis per resource (history, request fallback or model); fallback workloads show the explanation and the "same answer" note.
- [ ] Risk-level evidence in the UI equals `final_test_policy_comparison.csv` for each dataset (via the API).
- [ ] The recommendation panel shows the evidence for keeping the request next to the selected level's evidence, and no text claims a risk level is safer than the request.
- [ ] The history chart pairs each recommendation with the next run's usage and never plots a missing value as zero.
- [ ] The policy comparison shows all seven policies with the risk levels marked, per dataset.
- [ ] Missing values show as "not available"; Alibaba CPU is labelled average usage everywhere it appears.
- [ ] No number is hard-coded in the frontend.
- [ ] Errors, an unreachable API and a development bundle are shown clearly.
- [ ] UI tests pass against the fixture bundle, and the full existing suite still passes.
- [ ] Figures 8.1 and 8.2 are replaced with screenshots from the verified bundle, and §8.3 is updated.
- [ ] README explains how to open the UI locally.

## Completion Definition

Task 16 is complete when the UI runs locally against the verified bundle, shows every view for both datasets with correct units, bases and evidence, and the report's Figures 8.1 and 8.2 and §8.3 reflect what was built.
