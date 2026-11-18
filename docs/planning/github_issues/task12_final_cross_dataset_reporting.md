# [P1] Task 12: Final Cross-Dataset Reporting and Comparison

**Labels:** `area-documentation`, `priority-high`

**Owner:** Unassigned

**Priority:** Final · Required for project completion · Runs after the completed and verified work. Reports only; does not change pipeline results.

---

## Objective

Produce the final project-level report from frozen, verified artifacts: per-dataset results, a contract-comparison table that separates comparable from non-comparable metrics, limitations, adapter-integration evidence and reproducibility instructions.

## What This Task Builds

- A reporting script that regenerates every final table and figure from frozen artifacts.
- Per-dataset final result tables and figures.
- A contract-comparison table (no score ranking).
- Limitations, conclusions and reproducibility sections.
- The final artifact manifest extended to every reported artifact, and final README and runbook updates.

## What This Task Does Not Build

- Any new or rerun pipeline result, model, policy or metric.
- Any change to verified artifacts.
- A combined or cross-dataset accuracy ranking.

## Current Project State

- PR 1 (#123) and Task 8 (#121) are merged. `cross_dataset_pr1/` is historical;
  its original comparison digest `de560f…` is not the current Alibaba input.
- PR #129 is open on `task12-final-reporting-pr2-integrated`. The review is
  recorded in [the PR #129 review](pr129_task12_review.md). The separate
  `cross_dataset_final/` bundle uses
  decision `d36964c09c903af646f29929d363d0ccb6ccf60674f31054ed8dfac9dff527ac`,
  run `4fdc7e96-789b-43a9-990f-20f189e9598b`, execution
  `ea6aa08458aace364cd33529ce77de894bcd76ad`.
- Reporting validates dataset/stage/logical-artifact/path/hash/run linkage,
  scientific aggregate contracts, accessible published bytes and metadata.
- Reporting does not reproduce model inference, reopen test target values or
  independently observe historical execution. Task 8's UNVERIFIED disclosures,
  earlier-run history and environment follow-ups remain explicit.
- Google retention/correction, Azure go/stop and Alibaba 2018 scope outcomes are
  `decision_pending`; no undocumented team decision is treated as approved.
- Final-format generation succeeds with `project_completion: false`;
  `--require-complete` refuses completion while those decisions are pending.
- Issue #117 remains open while dataset decisions and the Task 10 before/after
  comparison await evidence.
- See `docs/data/cross_dataset_reporting_runbook.md` for reporting-only commands,
  evidence access, reproducibility and remaining limitations.

## Relationship to PR #70 and Tasks 1–5

| Item | Relationship |
|---|---|
| PR #70 follow-up | Profiles supply the per-dataset contract table (units, scope, semantics, isolation) |
| Tasks 1–3 | Adapter-integration evidence and count reports are cited |
| Task 4 | Split and target metadata are cited |
| Task 5 | Labels and suppression in evaluator output are reproduced as reported |

## Scope

- Datasets actually completed, stated explicitly.
- Reporting only.

## Dependencies

- **Task 8** complete (verified Alibaba GPU 2020 result).
- **Task 10** complete, or a documented decision to keep the earlier Google results.
- **Task 9** and **Task 11** outcome statements, or a statement that they were not attempted.

## Parallel Work

- The reporting script can be developed early against validation artifacts, alongside Tasks 9–11.
- Final tables wait for the dependencies.

## Blocks

- None. It closes the project.

## Detailed Implementation Tasks

### 1. Completed Datasets

- [ ] State which datasets were completed (full pipeline, demonstration, feasibility only, or not attempted).

### 2. Dataset-Specific Research Questions and Contracts

- [ ] For each dataset: research question, modeling unit, resource scope, aggregation, units, CPU and memory semantics, recurrence source, target availability, target isolation and evaluated resources, taken from the profiles and metadata.

### 3. Results

- [ ] **Google:** full-workload occurrence CPU and memory peaks (`ncu`, `normalized`), all policies, any-resource metrics where valid, with the Task 10 before/after comparison.
- [ ] **Alibaba GPU 2020:** role-level memory first (`gb`, peak) and CPU (`percent_of_vcpu`, lifetime average, labeled "average-usage sizing, not peak safety"); all seven policies; separate denominators; no any-resource or GPU metric; same-second, multi-instance and group-weighted sensitivity.
- [ ] **Alibaba 2018:** adapter findings and scope statement; no recommendation result.
- [ ] **Azure:** feasibility decision, and results only if Stage 2 ran.

### 4. Comparable and Non-Comparable Metrics

- [ ] A table separating what can be compared (capabilities, contracts, adapter behavior, within-dataset policy ordering) from what cannot (raw violation, utilization or accuracy numbers across datasets).
- [ ] State that raw percentages are not comparable across datasets when workload definitions, units or target semantics differ.
- [ ] No numeric CPU comparison between Google and Alibaba GPU 2020.

### 5. Limitations

- [ ] Alibaba GPU 2020: selection bias from eligibility rules, low sensor coverage on multi-instance roles, the roughly 50-day telemetry window, same-second targets, CPU average semantics.
- [ ] Google: subset scale, small validation population, F7 and F8 if not fixed.
- [ ] Alibaba 2018 and Azure scope.

### 6. Adapter Integration Evidence

- [ ] Show the same canonical contract, framework and evaluator applied to each dataset, with each dataset's profile.

### 7. Reproducibility

- [ ] Extend the Task 8 manifest to every reported artifact.
- [ ] Reporting script regenerates every table and figure.
- [ ] Fresh-environment run from `requirements.txt` and the documented data setup.

### 8. Conclusions and Documentation

- [ ] Final conclusions per dataset and overall, consistent with the limitations.
- [ ] README and runbook updates.

## Required Tests

- [ ] Every reported number traces to a frozen artifact listed in the manifest.
- [ ] The reporting script regenerates all tables identically.
- [ ] A check that no Alibaba GPU 2020 CPU figure lacks the average-usage label.
- [ ] A check that no table ranks policies across datasets.
- [ ] The full `pytest` suite passes.

## Acceptance Criteria

1. Every dataset's completion status is stated.
2. No combined or cross-dataset accuracy ranking, and no numeric CPU comparison between datasets.
3. Every Alibaba GPU 2020 CPU figure carries the average-usage label, and memory is reported first.
4. Every number traces to a verified artifact; no pipeline result was changed.
5. Reproduction succeeds and the manifest is published.

## Expected Outputs

- Reporting script (extend `scripts/report_summary.py` or add a new script; to confirm).
- Final per-dataset tables and figures (location to confirm, for example new dataset folders under `reports/eval/`).
- Contract-comparison table, limitations, conclusions.
- Final manifest, README and runbook.

## Data Leakage Controls

- Reads frozen final artifacts only; never reruns or retunes anything.

## Schema and Adapter Boundaries

- Reads profiles and metadata only; no schema, adapter or pipeline change.

## Unresolved Decisions

| ID | Decision | Recommendation |
|---|---|---|
| D-1 | Extend `scripts/report_summary.py` or write a new script | New script, leaving the legacy one unchanged, because the legacy script reads v0 summary columns |
| D-2 | Final table layout | One table per dataset plus one contract-comparison table |
| D-3 | Google results if Task 10 is not done | Report the earlier results with the F3 and F4 contamination disclosed |

## Risks

- Readers may still compare numbers across datasets; labeling must be explicit.
- Late completion of Tasks 9–11 can delay final tables; their outcomes can be reported as not attempted.

## Pull-Request Boundary

Two PRs: (1) reporting script and generated tables; (2) final manifest, limitations, conclusions and documentation.

## Handoff

- Final report chapters, presentation and release.

## Not in This Issue

- Any pipeline, model, baseline, evaluator, target or adapter change.
- Rerunning any final test.
- Cross-dataset accuracy rankings.

## References

- `scripts/report_summary.py`, `README.md`, `requirements.txt`
- `docs/planning/github_issues/task8_alibaba_gpu_2020_final_verification.md`
- `docs/planning/github_issues/task9_alibaba_2018_adapter_demonstration.md`
- `docs/planning/github_issues/task10_google_subset_corrections_and_rerun.md`
- `docs/planning/github_issues/task11_azure_vm_dataset_integration.md`
- `docs/design/canonical_workload_schema.md` §10, §12, §13
- `docs/data/alibaba_gpu_2020_evidence_and_limitations.md` §5–§6
- `docs/data/google_subset_pipeline_analysis.md`
- `docs/planning/data_integration_tasks.md` Task 11, final-report part (earlier numbering), and §8
