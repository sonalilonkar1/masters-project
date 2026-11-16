# [P1] Task 16: Recommendation Web UI

**Labels:** `area-implementation`, `priority-high`

**Owner:** Unassigned

**Priority:** Priority 1 · Required for the demo and for replacing the Figure 8.1 and 8.2 placeholders in the final report · Covers the planned New Issues 8 (UI and policy controls) and 9 (UI–API integration) from `docs/planning/295b_scope_and_done.md`. Split from the former Task 15.

**Design:** `docs/design/recommendation_service_design_plan.md` (sections 2, 8, 9, 12–14).

---

## Objective

Build the web interface a developer uses to choose a dataset (Google ClusterData 2019 or Alibaba GPU 2020), find a workload, choose a risk level and see the CPU and memory recommendation for that workload's next run, with the evidence behind it. The UI reads everything from the Task 15 API; it computes no results.

## Current Project State

- No frontend exists. Report Chapter 8 §8.3 describes it as planned, with placeholders for Figures 8.1 (recommendation view) and 8.2 (policy comparison).
- The API contract is defined in Task 15 and the design plan §7; Task 15 commits it as `docs/design/recommendation_api_openapi.json`.
- About half the workloads in both datasets have a single test run (no scored history), so the UI must handle an empty history.
- For most workloads the latest recommendation falls back to the request (49.4% of Google and 76.7% of Alibaba workloads), so every risk level gives the same answer. The UI must say so instead of implying a choice (design plan §5 fact 3, §9).

## User Flow

```
Dataset ──► Workload ──► Risk level ──► Recommendation + evidence
```

## What This Task Builds

### Part A: Framework decision

- [ ] Choose the frontend approach and record it in the design plan §10. Proposal: static HTML/JS with Chart.js, served by the Task 15 API, no build step; React is the alternative if the team wants richer interaction.

### Part B: Views

- [ ] **Dataset selector:** Google ClusterData 2019 or Alibaba GPU 2020, with a one-line description, units and CPU meaning (`GET /datasets`).
- [ ] **Workload lookup:** search and paginated list, default order by number of test runs, showing workloads with history by default and all workloads on a toggle (`GET /datasets/{dataset}/workloads?has_history=true`).
- [ ] **Recommendation panel** (Figure 8.1):
  - Risk selector Restrictive / Balanced / Efficient, Restrictive by default (`GET /risk-levels`).
  - Recommended CPU and memory next to the original request, with units.
  - How the number was built: the rule and its inputs (e.g. "larger of the ML prediction and the P99 of earlier runs").
  - The policy's test evidence on this dataset, for example "Memory recommendations at this level were exceeded by 3.15% of test runs, average waste 8.71 GB", read from the API.
  - Basis per resource, for example "Based on 23 earlier runs" or "Only 3 earlier runs (needs 10): we keep your request".
  - When the API reports `same_for_all_risk_levels`, the selector says the levels make no difference for this workload yet.
  - Source: run ID and bundle checksum (small print).
- [ ] **Workload history:** chart of the workload's test runs in time order. Each point is the recommendation made at run *i* against the usage of run *i + 1*; exceeded runs highlighted; a clear message when the workload has no scored run yet.
- [ ] **Policy comparison** (Figure 8.2): violation rate against average waste for all seven policies on the selected dataset, with the three risk levels marked (`GET /datasets/{dataset}/policies`).
- [ ] **About the data:** dataset descriptions, units, the one-time test, the fact that results are historical replay rather than a live cluster, and the Google Hybrid note from the bundle metadata.

### Part C: Display rules

- [ ] Every value shown with its unit; null shown as "not available", never 0.
- [ ] Alibaba CPU labelled "average usage, not peak" wherever it appears; Alibaba memory shown first.
- [ ] Google values shown in normalized units with a short explanation; never converted to cores or GiB.
- [ ] No view combines or ranks datasets.
- [ ] Every number comes from the API; none is written in the frontend code.
- [ ] Desktop browser; a phone layout is not required.

### Part D: Tests

- [ ] Smoke test that each view loads against the API running on the Task 15 fixture bundle.
- [ ] Checks that units, the Alibaba CPU label and "not available" render as required.
- [ ] Any new dependency added to `requirements.txt` and `requirements-lock.txt` (or a documented frontend toolchain if Part A chooses one); the full existing suite still passes.

### Part E: Report and demo

- [ ] Screenshots replace the Figure 8.1 and 8.2 placeholders in `docs/project_report/chapter_8_operations_and_reproducibility/`; §8.3 changes from "planned" to "implemented" and names the frameworks.
- [ ] Check that Chapter 2 §2.2.6 / Figure 2.1 and Chapter 4 §4.4 / Figure 4.4 still match what was built; update the Chapter 8 source map.
- [ ] README: how to open the UI locally (after the Task 15 commands).
- [ ] Demo script: one Google and one Alibaba workload with history at all three risk levels, one workload that falls back to the request, then the policy comparison.

## What This Task Does Not Build

- The export or the API (Task 15).
- Any calculation of recommendations or metrics in the browser.
- Live recommendations, authentication, hosting or deployment beyond running locally.
- GPU recommendations or other datasets.

## Dependencies

- Task 15 API contract agreed (OpenAPI file committed) to start; Task 15 fixture bundle for tests.
- Task 15 real bundle (from the Nov 15 Alibaba run) for the final screenshots.

## Blocks

- Final report Chapter 8 §8.3 and Figures 8.1 and 8.2; the demo.

## Suggested Split

| PR | Content |
|---|---|
| 1 | Part A, the views against the fixture-backed API, Part C rules, Part D tests |
| 2 | Real bundle, Part E screenshots, report updates, README and demo script |

## Acceptance Criteria

- [ ] A developer can go from dataset to workload to risk level to recommendation for both datasets; Restrictive is the default.
- [ ] Risk-level evidence in the UI equals `final_test_policy_comparison.csv` for each dataset (via the API).
- [ ] Workload history and policy comparison views work for both datasets, including workloads without a scored run.
- [ ] Missing values show as "not available"; Alibaba CPU is labelled average usage everywhere it appears.
- [ ] UI tests pass and the full existing suite still passes.
- [ ] Figures 8.1 and 8.2 are replaced with screenshots and §8.3 is updated.
- [ ] README explains how to open the UI locally.
