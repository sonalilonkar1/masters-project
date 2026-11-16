# Results

Final results of the TraceAdvisor evaluation, one folder per dataset. Every file here is small (Markdown, CSV, JSON, PNG); the full Parquet tables and model files stay in `data/processed/` (not tracked by Git) and are identified by the `SHA256SUMS` and manifest copies kept here.

**Current cross-dataset entry point:** [Task 12 PR 2](cross_dataset_final/report.md),
with [evidence](cross_dataset_final/evidence_status.md),
[limitations](cross_dataset_final/limitations.md),
[conclusions](cross_dataset_final/conclusions.md), and
[artifact manifest](cross_dataset_final/artifact_manifest.json).
Reporting validation passes while final dataset decisions remain pending.
Published-byte validation is distinct from unavailable physical-artifact checks.
Use the [runbook](../../docs/data/cross_dataset_reporting_runbook.md) to reproduce.

`cross_dataset_pr1/` is the unchanged historical PR 1 snapshot. Some older
per-stage narratives and manuscript numbers also describe earlier Alibaba runs;
the PR 2 bundle uses the authoritative November 15 published tables. Updating
those manuscript numbers is a separate follow-up.

**Start with** each dataset's `*_results_and_analysis.md`: headline results, tables, figures and interpretation. The other report in each folder is the detailed run record.

| Folder | Read first | Run record | Layout |
|---|---|---|---|
| `google_subset/` (Google ClusterData 2019, Kaggle subset) | `google_subset_results_and_analysis.md` | `googlepipeline_finalrun.md` (run, frozen decisions, reproduction) | `tables/` (CSV exports of Notebooks 04–06), manifests and notebook metadata at the top level |
| `alibaba_gpu_2020/` (Alibaba GPU Cluster Trace 2020) | `alibaba_gpu_2020_results_and_analysis.md` | `alibaba_gpu_2020_results_tasks1_6.md` (data, splits, targets, baselines) | One folder per pipeline stage: `canonical/`, `targets/`, `baselines/`, `ml/` (PR1 lock), `final_test/` |

The layouts differ because the Google pipeline is a sequence of notebooks writing one table set, while the Alibaba pipeline is a sequence of scripts, each writing its own checksummed output folder.

Figures in each `figures/` folder are generated from the CSVs here by `make_results_figures.py`:

```bash
~/venvs/traceadvisor-lock/bin/python reports/results/make_results_figures.py
```

Numbers are never compared across the two datasets: units, CPU semantics (Google peak, Alibaba lifetime average) and evaluation populations differ.

Earlier baseline experiments that are not part of the final evaluation are in `reports/eval/`.
