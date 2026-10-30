# Chapter 8 Source Map: Operations, Reproducibility, and Future Deployment

**Purpose:** for each Chapter 8 section, the sources describing how TraceAdvisor is run, reproduced and used. Chapter 8 is about **operating the system**: running the pipelines, reproducing results, the repository layout, and the developer-facing API and frontend. Design reasons for the artifact layer are in Chapter 4 §4.4 and implementation in Chapter 5 §5.6; refer to them.

**Scope rules**
- The REST API and web frontend, and the Google thin adapter, are written as implemented, kept general (no framework names until chosen).
- Alibaba Task 7 is merged and run (30 Oct 2026); the ML and final-test steps are described from the merged scripts.
- Style: formal prose; commands may be shown in short code blocks; citations only for the two datasets.

---

## 8.1 Offline Artifact Workflow

**What the section says:** the end-to-end run order for each dataset, what each stage reads and writes, and how a run is published.

| Kind | Source |
|---|---|
| Google run order | `pipelines/google_subset/01`–`06`; `reports/results/google_subset/googlepipeline_finalrun.md` §8 (run 01–05 with the `traceadvisor-lock` kernel; Notebook 06 freeze with `FREEZE_STATUS = "final"`, then `RUN_FINAL_TEST = True` at the same commit) |
| Alibaba run order | `scripts/build_alibaba_gpu_2020_canonical.py` (or `--verify` on the shared copy), `scripts/build_alibaba_gpu_2020_targets.py`, `scripts/run_alibaba_gpu_2020_baselines.py`, `scripts/run_alibaba_gpu_2020_ml.py`, then (after the team freezes the PR1 outputs, at the same commit) `scripts/run_alibaba_gpu_2020_final_test.py`; all from a clean checkout (`reports/results/alibaba_gpu_2020/alibaba_gpu_2020_results_and_analysis.md` §0) |
| Options and refusals | `--force`, `--allow-dirty`, `--out-dir`, `--keep-failed-output`, `--verify`, `--defect-rerun-reason`; refusal on a dirty tree or an existing output; final test refuses a lock built at another commit and a second run (run log); ML script refuses to replace a tested lock (Chapter 5 §5.6) |
| Shared data handoff | Task 3 build `c2ae87f` shared on Drive and checked with `--verify` (system guide §2.3) |
| Run times | 30 Oct 2026 run: targets 56 s, baselines 110 s, ML 2 min 53 s, final test 7 s (`alibaba_gpu_2020_results_and_analysis.md` §0); peak memory for targets and baselines about 5 GB and 1.9 GB (`alibaba_gpu_2020_results_tasks1_6.md` §7) |
| Design reference | Chapter 4 §4.4, Figure 4.3 |

## 8.2 Reproducibility and Repository Layout

**What the section says:** how a reader reproduces the reported numbers, and where everything lives.

| Kind | Source |
|---|---|
| Locked environment | `requirements-lock.txt` header (Python 3.12; `python3.12 -m venv ~/venvs/traceadvisor-lock`; `pip install -r requirements-lock.txt`; register the `traceadvisor-lock` kernel); `requirements.txt` keeps minimum versions; Table 3.1 |
| Data setup | System guide §2.2 (Google Kaggle sample at `subset/borg_traces_data.csv`), §2.3 (Alibaba official tables, checksums in `config/alibaba_gpu_2020_sources.json`) |
| Repository layout | System guide §3; README "Project Structure": `src/` (canonical, adapters, sources, features, baselines, models, policies, evaluation), `pipelines/google_subset/`, `scripts/`, `config/`, `tests/`, `data/` (local only), `reports/results/` (final results), `reports/eval/` (earlier baseline experiments), `docs/` |
| What is versioned | Code, docs, config and final results in Git; raw and processed data local (Chapter 4 §4.4) |
| Provenance records | Google `decision_manifest.json` and `final_test_run_metadata.json`; Alibaba `metadata.json`, `count_report.md`, `SHA256SUMS`, Alibaba `ml/decision_manifest.json`, `ml/final_test_runs.jsonl`, `final_test/run_record.json` (copies in `reports/results/alibaba_gpu_2020/`) |
| Reproduction limits | Each final test can be run once per manifest. Google: freeze from a clean checkout of `e59349e` (`googlepipeline_finalrun.md` §8). Alibaba: run PR1 and the final test at one clean commit (the published run used `fe38ea0`); a new PR1 lock gives a new manifest |
| Tests | `pytest` in the locked environment (Chapter 6) |
| Earlier experiments | Azure Resource Central, Splitwise, ModServe notebooks and `reports/eval/` (system guide §11): kept for context, not part of the evaluated system |

## 8.3 Developer-Facing API and Web Frontend (retitle from "Interactive Developer Dashboard (Planned)")

**What the section says:** how developers use TraceAdvisor's results: the read-only REST API over the published artifacts and the web frontend built on it. Written as implemented and kept general.

| Kind | Source |
|---|---|
| Design | Chapter 4 §4.4 (read-only, decoupled from the pipeline, units and dataset labels travel with every value), Figure 4.3; Chapter 2 §2.2.6 |
| Content served | Recommendations per policy and split, evaluation summaries, units, CPU semantics label, dataset labels; organized by dataset, workload and policy |
| Data source | Published artifacts under `data/processed/` and `reports/results/` |
| Deployment | General description: the API reads published files and needs no access to the pipeline or raw data |
| Not to claim | Framework names, hosting, authentication or endpoints until the implementation exists |

---

## Check against the code

| # | Item | Finding | Effect on Chapter 8 |
|---|---|---|---|
| 1 | 8.3 title | Table of contents says "Interactive Developer Dashboard (Planned)" | Retitle; written as implemented |
| 2 | Lock file | `requirements-lock.txt` committed in `02184f2`; header gives the install commands | Quote the commands |
| 3 | Alibaba scripts | All five scripts on `main` (ML in PR #98, final test in PR #102) | Describe the full run order |
| 4 | `reports/` layout | `reports/results/` (final) and `reports/eval/` (earlier experiments); kept as is | Describe both |
