# Review of PR #129: Task 12 PR 2, Final Cross-Dataset Reporting

**PR:** #129 (`task12-final-reporting-pr2-integrated`, commit `0df93b8`), author sofiesilva0223
**Issue:** #117 (Task 12, `task12_final_cross_dataset_reporting.md`)
**Reviewed:** 2026-11-18, in the locked environment (`requirements-lock.txt`, Python 3.12) with the Google and Nov 15 Alibaba processed data available locally

## How It Was Checked

- Ran the full test suite on the PR with the processed data present: 978 passed, 1 skipped. The 5 failures reported in the PR description come from the Google occurrence Parquet files missing on the author's machine, not from the code.
- Regenerated the bundle with the runbook command (`--config config/cross_dataset_report_final.json --strict`) and compared it file by file with `reports/results/cross_dataset_final/`.
- Ran `--validate-bundle` on the committed bundle.
- Traced every reported value (518 rows) back to its source cell by reading the source CSVs as text.
- Checked the bundle against the Task 12 acceptance criteria and §5 (Limitations).

All CSV and Markdown tables regenerate byte-identical, and every value points at the right source row and column. The issues below are what remains.

## Required Changes

### 1. The committed bundle fails its own validation in the locked environment

The committed SVG figures were rendered with Matplotlib 3.10.0 (`<dc:title>Matplotlib v3.10.0`), but `requirements-lock.txt` pins `matplotlib==3.11.2`. In the locked environment the regenerated figures differ (axis layout coordinates), and:

```text
python scripts/build_final_cross_dataset_report.py --validate-bundle reports/results/cross_dataset_final
REPORT FAILED: canonical reporting document or rendered table disagrees with validated state: google_clusterdata2019/01_cpu.svg
```

The five figures, `artifact_manifest.json` and `report_provenance.json` differ as a result. This breaks acceptance criterion 5 ("Reproduction succeeds") for anyone using the repository's environment.

**Fix:** regenerate the bundle in the locked environment and commit that output. Optionally record the Matplotlib version in the provenance so a mismatch is reported clearly instead of as a content disagreement.

### 2. Limitations required by the issue are missing

Task 12 §5 requires these limitations:

- **Alibaba GPU 2020:** selection bias from eligibility rules, low sensor coverage on multi-instance roles, the roughly 50-day telemetry window, same-second targets, CPU average semantics.
- **Google:** subset scale, small validation population (and F7/F8, which are present).

None of the first group appears in `cross_dataset_final/`. "Same-second" appears only as a link label to the sensitivity table in `report.md`, and "subset scale" and "small validation population" appear nowhere. `limitations.md` lists only provenance items for Alibaba. `config/cross_dataset_report_pr1.json` contained the Alibaba limitations in its `reason` text, but `config/cross_dataset_report_final.json` dropped them.

**Fix:** add these limitations to the final configuration so they render in `limitations.md` (and in each dataset's section of `report.md`).

### 3. "Closes #117" would close the issue with open acceptance criteria

The bundle itself reports `DECISION_PENDING` and `project_completion: false`. The Google, Azure and Alibaba 2018 decisions are pending, and the Task 10 before/after comparison is "pending approved artifacts". #117 has been reopened and is open.

**Fix:** change "Closes #117" to "Part of #117" in the PR description.

## Recommended Changes

### 4. 80 reported values are not exact copies of their source cells

The values agree with their sources only up to the 16th–17th significant digit. Example (Alibaba, Hybrid, memory `average_shortfall`):

| Source CSV cell | Reported value |
|---|---|
| `0.19704480677699449` | `0.1970448067769944` |

80 of the 518 traced values differ in this way. The difference has no scientific effect, but the report presents values as copied from source cells, and the check meant to prove it cannot catch the difference: both `scripts/build_final_cross_dataset_report.py` (`read_csv`) and `trace_metric_cells` in `src/reporting/artifact_provenance.py` read the source with `pd.read_csv` using pandas' default float parser, which is not round-trip exact.

**Fix:** read the source CSVs with `pd.read_csv(..., float_precision="round_trip")` in both places (or with the `csv` module), and keep the check independent of the generator's reader.

### 5. Out-of-date statements in the documentation

- `current_status.md` and `task12_final_cross_dataset_reporting.md` say PR 2 is "implemented locally, not pushed/reviewed" on `task12-final-reporting-pr2`. It is now PR #129 on `task12-final-reporting-pr2-integrated`.
- `task12_issue117_reopening_comment.md` is a draft comment for reopening #117. #117 is now open, so it is obsolete, and its closing line ("No GitHub issue was reopened or edited by the agent") does not belong in the repository. Remove the file and the references to it.
- `reports/results/README.md` still says every file there is "Markdown, CSV, JSON, PNG"; the new bundle adds SVG.

### 6. Validation claims in the PR description that cannot be traced to the repository

"80 independent adversarial and compatibility checks passed" and "Verified all 165 protected historical/scientific files remain unchanged" do not correspond to any test or script in the PR. Either add the checks to the repository or remove the claims.

## Coordination with PR #131 (Task 15)

- Both PRs edit the same rows of `docs/planning/github_issues/current_status.md`, and they conflict there. The PR merged second resolves it; the conflict is documentation only.
- Task 12 labels Alibaba CPU "average-usage sizing, not peak safety", while the Task 15 API and UI use "Average usage, not peak". Both are correct; the team should pick one wording for the final report.
