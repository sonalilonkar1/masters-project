# Key Takeaways: Status Review, Recommendation Service Design and Code Review

**Date:** 2026-11-16. Based on `main` at `d46e282`, PR #121 (merged later the same day), a full read of `src/` and `pipelines/google_subset/`, and the local `data/processed/` outputs.

---

## 1. Decisions

| Topic | Decision |
|---|---|
| Task 15 scope | Split in two: **Task 15** backend (UI export and read-only API), **Task 16** web UI |
| Design | `docs/design/recommendation_service_design_plan.md`: offline export → checksummed bundle → read-only API → UI. Presents existing results only |
| User flow | Dataset (Google or Alibaba) → workload → risk level → recommendation with its evidence |
| Risk levels | Restrictive = Hybrid (default), Balanced = P95, Efficient = P90 |
| Request fallback | Keep the method. Show the basis of every number in the UI, state the limit in the report, analyse outcomes in Task 14 |
| Google N06 notebook | No change: its code hash still matches the frozen Google manifest (`ee6633b8…`), so editing it would break the provenance link |

## 2. The Two Pipelines

| | Google subset | Alibaba GPU 2020 |
|---|---|---|
| Run | Full-workload occurrence | One role of a job, per instance |
| Workload key | `user‖logical name` | `group‖task` |
| Unique row key | `occurrence_id` | `role_key` (`occurrence_id` is shared by all roles of a job) |
| Targets | Built before the split (cross split boundaries; Task 10) | Built after the split |
| Locked baseline | P99, `min_runs = 1` | P99, `min_runs = 10` |
| ML model | Random forest | HistGradientBoosting |
| Hybrid | max(ML, **P95**) | max(ML, **P99@10**) |
| Below `min_runs` | Baselines = request | Baselines = request |

## 3. Task 8 (PR #121) Review

| # | Finding | Severity |
|---|---|---|
| 1 | The PR re-ran Tasks 4–7 and the final test (run `4fdc7e96…`, Nov 15). The run log was overwritten with `prior_runs: 0` and no rerun reason, so the Oct 30 run (in the report) and run `7dd3942e…` (in the PR description) are no longer recorded | High |
| 2 | The verifier's rerun check only sees log entries with the current manifest hash, so it passes after the history was removed | High |
| 3 | Environment differs from `requirements-lock.txt` (Python 3.11, pandas 3.0.2, scikit-learn 1.8.0, xgboost 3.2.0) | Medium |
| 4 | ML and Hybrid numbers changed; baselines and selections did not | Medium |
| 5 | PR description is stale (34 checks, run `7dd3942e…`); report generated from a dirty tree | Low |

| Hybrid (Alibaba test) | Memory exceeded | Memory waste | CPU exceeded |
|---|---|---|---|
| Oct 30 run (report) | 3.146% | 8.707 GB | 3.767% |
| Nov 15 run (PR #121) | 3.178% | 8.699 GB | 3.621% |

**Outcome:** PR #121 was merged on 2026-11-16, so `main` now publishes the Nov 15 run. Follow-ups: record the Oct 30 run and the reason for the rerun, fix the verifier's run-history check, align `requirements-lock.txt` with the environment used, and update the report's Alibaba ML and Hybrid numbers (separate PR).

## 4. History Coverage and the Request Fallback

| | Google | Alibaba |
|---|---|---|
| Evaluated test rows that fall back (memory) | 9 of 259 (3.5%) | 11,036 of 44,053 (25.1%) |
| All test runs that use history | 67% | 56% |
| Latest run per workload that falls back | 233 of 472 (49.4%) | 19,341 of 25,232 (76.7%) |
| Hybrid / request on history runs (memory) | 4.4× (requests too low) | 0.41× (requests too high) |
| Hybrid / request on fallback runs (memory) | about 1.0× | about 1.0× |

- **Most workloads fall back, most runs do not.** Many workloads run once or twice; recurring workloads produce most runs.
- **Where there is history,** the project changes the decision: on Alibaba, less memory (waste 22.3 → 8.7 GB per run at the same 3.2% violation rate); on Google, more safety (violations 54% → 12%).
- **Where there is none,** it keeps the request, so it is never worse than today.
- **Limit:** one-off and new workloads are not improved. Cold-start sizing from similar workloads is future work (Ch9).

### P95 versus P99, and `min_runs`

| Alibaba | Memory exceeded | Memory waste |
|---|---|---|
| P95 (test) | 6.04% | 7.89 GB |
| P99 (test, selected) | 3.44% | 8.67 GB |
| P99, `min_runs = 1` (validation) | 8.74% (7.6% fallback) | 5.51 GB |
| P99, `min_runs = 10` (validation, selected) | 5.58% (25.7% fallback) | 8.94 GB |

The percentile trades safety for waste. The fallback share is set by `min_runs`, not by the percentile.

## 5. Code Review Findings

| # | Finding | Action |
|---|---|---|
| 1 | N04 overview says targets stay inside each split; the code builds them before the split | Task 10 |
| 2 | Excluding Request from Alibaba selection lets Hybrid go below the request only with ≥ 10 earlier runs (25.1% of evaluated memory rows cannot) | Report updated (Ch4 §4.2.1) |
| 3 | N06 committed with preliminary parameters and a stale "Task 9" reference | None (hash link, see §1) |
| 4 | Google decision manifest omits scikit-learn and xgboost versions (in `ml_metadata.json`) | Note in Task 12 manifest |
| 5 | `validate_features` docstring says it checks the DataFrame; it checks the feature list | Low; optional fix |
| 6 | Two import roots (`src.canonical…` and `canonical…`) | Low; optional fix |
| 7 | N01 falls back to a hard-coded user path | Low; optional fix |

## 6. Changes Made

| Area | Files |
|---|---|
| Status | `docs/planning/github_issues/current_status.md` (Task 8 findings, Tasks 15 and 16) |
| Issues | `task15_recommendation_backend_api.md` (was `task15_developer_api_and_risk_based_ui.md`), new `task16_recommendation_web_ui.md`, `task14_google_evaluation_followups.md` (history-versus-fallback breakdown) |
| Design | `recommendation_service_design_plan.md` (row keys, basis flags, per-dataset rules, fallback handling) |
| Report | Ch4 §4.2.1, Ch7 §7.5, Ch9 §9.3 and their source maps; `final_report.md`, `.docx` and LaTeX rebuilt |

## 7. Open Items

| Item | Owner |
|---|---|
| Task 8 follow-ups (§3): record the rerun, verifier fix, lock file | Team |
| Report: Alibaba ML and Hybrid numbers to the Nov 15 run (separate PR) | Team |
| Update GitHub #120 to Task 15; create the Task 16 issue | Team |
| Close stale #75 and #67 | Team |
| Frontend framework (Task 16) | Team |
