# [P3] Task 14: Google Evaluation Follow-ups (Cross-Split Targets, Sample Size, Feature Importance)

**Labels:** `area-evaluation`, `priority-low`

**Owner:** Unassigned

**Priority:** Priority 3 · Optional · After the final report. Not needed for the reported results, which stay as published.

---

## Objective

Track three open points about the evaluation that are not reported as limitations in Chapter 9 of the final report:

1. Google next-occurrence targets that cross the validation–test boundary.
2. The small size of the Google evaluation populations.
3. Feature importance for the selected ML models.

## Current Project State

**1. Cross-split Google targets.** Notebook 04 assigns next-occurrence targets before the chronological split, so 104 of the 329 scored validation occurrences have targets that start in the test period (`docs/data/google_subset_pipeline_analysis.md` F1–F4). With validation-period targets only (225 occurrences), P99 with `min_runs = 1` stays selected; its any-resource violation rate moves from 21.95% to 18.30% and Hybrid's from 17.93% to 17.78% (`reports/results/google_subset/tables/validation_policy_comparison_target_period_sensitivity.csv`). The effect on ML model selection is not established. The fix itself is specified in Task 10 (`task10_google_subset_corrections_and_rerun.md`); Alibaba already builds split-isolated targets.

**2. Small Google populations.** The Kaggle sample gives 329 validation and 259 test occurrences, so one occurrence moves a rate by about 0.3–0.4 percentage points. No confidence intervals or repeated runs exist for either dataset.

**3. Feature importance.** No notebook or script in the current pipeline computes it; the v0 feature-importance figures referenced in older documents came from the superseded pipeline and are no longer in the repository. Chapter 7 §7.2.3 was removed for this reason.

## What This Task Builds

- **Cross-split targets:** carry out Task 10 (targets built after split assignment, rerun of baseline and ML selection) and a before/after comparison. The published Google final test has already been run once against its decision manifest; a corrected run is a new experiment with a new manifest and must be reported as such, not as a replacement.
- **Sample size:** bootstrap confidence intervals over occurrences for the Google and Alibaba test tables (from the local row-level outputs under `data/processed/`, which are not committed; no new scoring decisions), and optionally a rerun of the Google pipeline on a larger sample of ClusterData 2019.
- **Feature importance:** permutation importance (and impurity importance for the Google random forests) computed from the locked models on **training-period rows only**, saved under `reports/results/<dataset>/tables/`. This uses no test data and changes no decision. The Alibaba model binaries are not in the report copies, so they must be taken from the local `data/processed/` lock.

## What This Task Does Not Build

- Any change to the published final-test results, decision manifests or run logs.
- Selection or tuning on test data.

## Acceptance Criteria

- [ ] Task 10 merged, or a decision recorded not to run it.
- [ ] Confidence-interval tables committed, with the method documented.
- [ ] Feature-importance tables committed for the selected Google (and optionally Alibaba) models, computed on training rows only.
- [ ] Any new results labelled as post-report follow-ups, separate from the published results.
