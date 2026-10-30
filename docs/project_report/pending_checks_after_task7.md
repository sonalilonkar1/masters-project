# Project Report Updates After Alibaba Task 7

**Who this is for:** the team member who updates the project report once Alibaba GPU 2020 Task 7 (ML, Hybrid, decision manifest and final test) is finished.

**What it covers:** every sentence, table cell and supporting document in `docs/project_report/` that depends on Task 7. Nothing else. The Google thin adapter, the REST API and the web frontend are described in the report as implemented and are **not** part of this list.

**Task 7 status (29 Oct 2026):**
- **PR1, PR #99** (branch `task7-pr1-continue`, head `d446771`): candidates, selection, Hybrid validation, refit, locked decision manifest. Open, not merged. Never reads the test set.
- **PR2:** one-time final test. Not started.

**Report files referred to below:**

| Short name | File |
|---|---|
| Ch2 | `docs/project_report/chapter_2_project_architecture/ch2_project_architecture.md` |
| Ch3 | `docs/project_report/chapter_3_technology_descriptions/ch3_technology_descriptions.md` |
| Ch4 | `docs/project_report/chapter_4_project_design/ch4_project_design.md` |
| Ch5 | `docs/project_report/chapter_5_project_implementation/ch5_project_implementation.md` |
| Ch7, Ch9 | `docs/project_report/chapter_7_results_and_discussion/`, `docs/project_report/chapter_9_summary_and_conclusions/` (not yet written) |

---

## How to use this file

1. **Wait** until Task 7 (PR1 and PR2) is merged into `main`.
2. **Record what the final code does** (Step 1). Several sentence fixes depend on these answers.
3. **Produce the artifacts** (Step 2). All numbers come from these files, never from memory or from a PR description.
4. **Edit the sentences** (Step 3). For each row: open the file, search for the quoted text (copy a few distinctive words), replace it as instructed, then mark the row ✅ (no change needed) or ✏️ (changed) in the last column.
5. **Fill the numbers** (Step 4) from the files named in each row.
6. **Update the supporting documents** (Step 5).
7. **Run the final check** (Step 6). When it passes, Task 7 is fully reflected in the report.

---

## Step 1: Record what the final Task 7 code does

Task 7 is still being developed, and PR #99 may change before it merges. The report must describe the **final merged code**, so answer each question below by reading `main` after Task 7 (PR1 and PR2) is merged, and write the answer in the "Answer" column. Do not take the answer from the issue, the PR description or earlier versions of this file. The answers decide which wording to use in Step 3.

| # | Question | Where to look in the merged code | Answer (fill in) | Rows in Step 3 that depend on it |
|---|---|---|---|---|
| D1 | In what order are ML models ranked on validation? (Accuracy first, violation first, or other) | `MODEL_SELECTION_ORDER` in `src/models/alibaba_gpu_2020_select.py`; `model_selection_order` in `decision_manifest.json` | | C11, C41 |
| D2 | Which candidate models are used, and which constant predictor (mean, median, both)? | `build_candidate_models()` in `src/models/alibaba_gpu_2020_candidates.py`; `candidate_models.csv` | | C5, C6, C7, C10 |
| D3 | What is the Hybrid safeguard, and which policy and `min_runs` does it use? | `HYBRID_SAFEGUARD_COL` in `alibaba_gpu_2020_select.py`; `hybrid_rule`, `hybrid_safeguard` in the manifest; `baseline_selection.json` | | C31, C42 |
| D4 | Is there a hyperparameter grid or search, or one fixed setting per model? | `build_candidate_models()` and any grid or search code; `model_selection.json` → `hyperparameters` | | C8, C9, C10 |
| D5 | Can the constant predictor be selected, or is it only a reference? | `compare_and_select()` in `alibaba_gpu_2020_select.py` | | C12 |
| D6 | What is the exact feature list, and how are categorical and missing values handled? | `ALIBABA_GPU_2020_FEATURES` in `src/features/alibaba_gpu_2020_feature_config.py`; `build_feature_matrices()` in `src/features/alibaba_gpu_2020_ml_prep.py`; `feature_list` in the manifest | | C1, C2, C3, C4, C23, C25 |
| D7 | What does the final test check before reading test targets, and does it refuse a second run? | The PR2 final-test script | | C17, C19, C32, C15 |
| D8 | Are the rows where Hybrid falls back to ML (missing safeguard) counted in an output file? | `metadata.json` or `validation_policy_comparison.csv` in `alibaba_gpu_v2020_ml/` | | C42, Ch5 Table 5.4 |

**Last seen in PR #99 (29 Oct 2026, for reference only; may have changed):**
- D1: accuracy first (`rmse, mae, violation_pct, average_shortfall, model`).
- D2: `DummyRegressor` (mean), decision tree, random forest (100 trees), `HistGradientBoostingRegressor`, XGBoost (300 trees, depth 6, learning rate 0.05, subsampling 0.8).
- D3: `max(ml_prediction, selected_task6_baseline)` with `rec_*_selected`, P99 at `min_runs = 10`.
- D4: no grid; one fixed setting per model.
- D5: `dummy_mean` is ranked with the other models, so it could be selected.
- D6: requests (CPU, memory, GPU), `inst_num`, `gpu_type`, `gpu_type_spec`, `workload` (one-hot, with a NaN column), history counts, history statistics, missing indicators, zero fill.
- D7: not built (PR2).
- D8: the flag is computed but not saved.

**Open points noticed in PR #99** (for the Task 7 team; check whether they are still present in the merged code):

| # | Point |
|---|---|
| P1 | The report currently says "small grid" for Alibaba in three places (C8–C10); the code had no grid (D4) |
| P2 | `dummy_mean` was ranked with the other models, so it could be selected although documented as a reference floor (D5) |
| P3 | XGBoost was skipped silently when it could not be imported (`HAS_XGBOOST`) |
| P4 | The Hybrid fallback flag was not saved, so Ch5 Table 5.4's Hybrid row cannot be filled from the outputs (D8) |
| P5 | The Task 7 issue file `docs/planning/github_issues/task7_machine_learning_hybrid_and_final_test.md` says violation first (line 185 and decision D-2, line 356) and lists hyperparameters as a tie-break; it should match the final code |

---

## Step 2: Produce the artifacts

Run from a clean, committed checkout of `main` in the locked environment (`requirements-lock.txt`); the scripts refuse a tree with uncommitted changes.

```bash
python3 scripts/build_alibaba_gpu_2020_canonical.py --verify data/processed/alibaba_gpu_v2020   # shared Task 3 copy
python3 scripts/build_alibaba_gpu_2020_targets.py                                               # Task 4
python3 scripts/run_alibaba_gpu_2020_baselines.py                                               # Task 6
python3 scripts/run_alibaba_gpu_2020_ml.py                                                      # Task 7 PR1
# Task 7 PR2: the one-time final test (script name from PR2)
```

| Folder | Files used by this checklist |
|---|---|
| `data/processed/alibaba_gpu_v2020_targets/` | `metadata.json` (`per_split`), `{train,validation,test}.parquet` |
| `data/processed/alibaba_gpu_v2020_baselines/` | `baseline_selection.json`, `validation_comparison.csv`, `recommendations_{train,validation,test}.parquet`, `metadata.json` |
| `data/processed/alibaba_gpu_v2020_ml/` | `decision_manifest.json`, `model_selection.json`, `candidate_models.csv`, `validation_policy_comparison.csv`, `feature_order.json`, `metadata.json`, plus the final-test outputs from PR2 |

---

## Step 3: Sentences to edit, by chapter

**Chapters 6–9 are not written yet.** Their source maps (`chapter_6_…/ch6_source_map.md` to `chapter_9_…/ch9_source_map.md`) mark every Task 7-dependent item with **[Task 7]**. When a chapter is written, add its Task 7 sentences to this step as a new table, in the same format as below. If Task 7 finishes first, fill the **[Task 7]** items in those source maps from the Step 1 answers and the Step 2 artifacts before the chapter is written.

**"Condition"** says which Step 1 answer decides the edit. Where a row gives two versions ("If no grid … If a grid was added …"), use the one that matches your Step 1 answer; if the answer is something else, write the sentence to describe what the code does. **Confirm** rows were written from PR #99 on 29 Oct; check them against your Step 1 answers and rewrite them if the merged code differs.

### Chapter 2

| # | Section | Find (quoted) | Do | Condition | Done |
|---|---|---|---|---|---|
| C17 | 2.1 Goal | "Seven policies are produced and compared: the user's current request; …" | Confirm the final test scores all seven policies on Alibaba | PR2 | |
| C18 | 2.2.4 Recommendation Engine | "It fits the baselines and models on the training set, selects among them on the validation set only, …" | Replace with: "It computes the baselines from each row's point-in-time history and fits the models on the training set, selects among them on the validation set only, and writes the chosen configuration to a decision manifest that is locked before the test set is read." (Baselines are not fitted; this is a known error, fix it even before Task 7.) | None | ✏️ Applied 29 Oct |
| C19 | 2.2.5 Shared Metrics and Evaluation Framework | "After the decisions are locked, it scores the test set once." | Confirm PR2 scores the test set once and refuses a second run; otherwise describe what it does | PR2 | |
| C20 | Figure 2.1 | Flow: model fitting → validation-only selection → locked decision manifest → one-time test replay | Confirm | PR2 | |

### Chapter 3

| # | Section | Find (quoted) | Do | Condition | Done |
|---|---|---|---|---|---|
| C21 | 3.1 | "The Alibaba pipeline is a set of command-line scripts, one per stage, that verify their inputs, build their outputs and publish them only when all checks pass; …" | Confirm for `run_alibaba_gpu_2020_ml.py` and the PR2 script | PR2 | |
| C22 | Table 3.1 | Library versions | Confirm `requirements-lock.txt` is unchanged; if PR2 adds or upgrades a package, update the row | PR2 | |
| C23 | 3.2 | "Tree-based models were chosen because the features are tabular, mix requests, counts and history statistics on very different scales, …" | Replace "mix requests, counts and history statistics on very different scales" with "mix requests, counts, history statistics and, on Alibaba GPU 2020, categorical job descriptors, on very different scales" | D6 | |
| C5 | 3.2 | "(the median on Google; the mean on Alibaba GPU 2020)" | Confirm (already updated) | D2 | |
| C8 | 3.2 | "Each model family is tuned over a small grid of hyperparameters, and the tuning method respects time order on both datasets." and "On Alibaba GPU 2020, which has far more rows, every configuration is fitted on the training set and scored directly on the validation set, without a cross-validation search." | **If no grid:** replace the first with "On Google, each model family is tuned over a small grid of hyperparameters, and the tuning respects time order." and the second with "On Alibaba GPU 2020, which has far more rows, each model family is used with one fixed configuration, fitted on the training set and scored on the validation set." **If a grid was added:** confirm | D4 | |
| C24 | 3.2 | "Fitted models are saved with joblib so that the locked models can be reloaded for the final test without refitting." | Confirm PR2 reloads `cpu_model.joblib` and `memory_model.joblib` | PR2 | |

### Chapter 4

| # | Section | Find (quoted) | Do | Condition | Done |
|---|---|---|---|---|---|
| C1 | 4.2.2, second paragraph (features) | "On Alibaba, the features are the CPU, memory and GPU requests, the number of instances, the GPU type and the workload label recorded with the job, …" | Confirm against `ALIBABA_GPU_2020_FEATURES` (already updated) | D6 | |
| C2 | 4.2.2, second paragraph (features) | "…while the requests, counts and job descriptors add information the baselines ignore." | Confirm (already updated) | D6 | |
| C25 | 4.2.2, third paragraph (model families) | "The data are tabular, the features mix requests, counts and statistics on very different scales, …" | Replace "the features mix requests, counts and statistics on very different scales" with "the features mix requests, counts, statistics and categorical job descriptors on very different scales" | D6 | |
| C12 | 4.2.2, third paragraph (model families) | "A constant predictor always predicts one value from the training data. It has no predictive skill and is the floor that a selected model must beat; …" | **If D5 = reference only:** confirm. **If it can be selected:** add after the quoted sentence: "On Alibaba GPU 2020 it is ranked with the other candidates and could be selected." | D5 | |
| C26 | 4.2.2, fourth paragraph (target transformation) | "Negative predictions are clipped to zero on both datasets." | Confirm | — | |
| C27 | 4.2.2, fifth paragraph (missing features) | "On Alibaba, a missing-value indicator is added for each history statistic before the statistic is filled with zero, …" | Confirm | — | |
| C28 | 4.2.2, sixth paragraph (training rows) | "On Alibaba, the CPU model is trained only on rows with an available CPU target and the memory model only on rows with an available memory target, …" | Confirm | — | |
| C9 | 4.2.2, seventh paragraph (tuning) | "On Alibaba, which has far more rows, every configuration in a small grid is fitted on the training set and scored on the validation set directly, which preserves time order at much lower cost. Small, explicit grids were preferred to adaptive search methods for reproducibility: every evaluated configuration is recorded." | **If no grid:** replace with "On Alibaba, which has far more rows, each model family is used with one fixed configuration, fitted on the training set and scored on the validation set, which preserves time order. On Google, small, explicit grids were preferred to adaptive search methods for reproducibility: every evaluated configuration is recorded." Add the absence of Alibaba tuning to the Chapter 9 limitations. **If a grid was added:** confirm | D4 | |
| C11 | 4.2.2, eighth paragraph (model selection) | "On Alibaba, the selection order is recorded with the selected models in the pipeline's selection record." | **If D1 is accuracy first:** replace with "On Alibaba, the selected model is the candidate with the lowest validation root mean squared error, followed by mean absolute error, with violation rate and average shortfall used only to break remaining ties." **If violation first:** describe that order and remove the following sentence about rejecting violation-first selection | D1 | |
| C29 | 4.2.2, last paragraph (final refit) | "After selection, the chosen model for each resource is refitted on the training and validation sets together." and "Hybrid is validated using predictions from the models fitted on training data only, …" | Confirm | — | |
| C30 | 4.2.3, first paragraph (combination rule) | "If the baseline is unavailable for a row, Hybrid uses the ML prediction and the row is flagged." | Confirm | — | |
| C31 | 4.2.3, third paragraph (safeguard baseline) | "Alibaba uses the baseline selected on validation in Section 4.2.1, at its selected `min_runs`, …" | Confirm | D3 | |
| C32 | 4.3, paragraph before Figure 4.2 (lock and final test) | "The final test reads the test targets for the first time, scores all seven policies once and writes a run record; a second run is refused. A rerun is permitted only to correct a documented code defect, …" | Confirm against PR2; if PR2 does not refuse a second run or write a run record, rewrite the sentence to describe what it does | PR2 | |
| C33 | 4.4 Figure 4.3 | Published artifacts: "Baseline and ML outputs", "Decision manifest", "Evaluation results" | Confirm | PR2 | |
| C16 | 4.4, paragraph after Figure 4.3 (integrity) | "On Alibaba GPU 2020, every published output folder contains a checksum file …" | Confirm the PR2 output folder has a `SHA256SUMS` file | PR2 | |

### Chapter 5

| # | Section | Find (quoted) | Do | Condition | Done |
|---|---|---|---|---|---|
| C40 | Introduction | "Values from the Alibaba ML and Hybrid stages, which were produced last, are marked *pending* in the tables of this chapter and are added from the final artifacts." | Delete the sentence once every pending cell is filled (Step 4) | Step 4 | |
| C4 | 5.1.1 Alibaba adapter | "GPU fields are not evaluated as targets; the GPU request and GPU type are used as features by the ML models (Section 5.3.1)." | Confirm | D6 | |
| C3 | 5.3.1, second paragraph | Paragraph starting "The Alibaba features are defined in a separate configuration." | Confirm every listed feature, the exclusion list, one-hot encoding, `feature_order.json` and "no log transformation" against the merged code | D6 | |
| C10 | 5.3.2, paragraph after Table 5.5 | "Its candidates are a constant predictor (`DummyRegressor` with the mean strategy), a decision tree, a random forest with 100 trees, histogram-based gradient boosting, and XGBoost with 300 trees of depth 6, …" | Confirm the candidates and settings. **If a grid was added:** replace the settings with the grid and say each configuration is fitted on train and scored on validation | D2, D4 | |
| C41 | 5.3.2, paragraph after Table 5.5 | "The CPU and memory models are selected independently, using the selection order recorded with the result." | **If D1 is accuracy first:** replace with "The CPU and memory models are selected independently, by validation RMSE, then MAE, with violation rate and average shortfall used only to break remaining ties." | D1 | |
| C6, C7 | 5.3.2, 5.3.3 | "`DummyRegressor` with the mean strategy"; "including the constant predictor" | Confirm | D2 | |
| C42 | 5.4, second paragraph | "The Alibaba ML script applies the same function to each resource, with the locked recommendation of the selected baseline, P99 at `min_runs = 10`, as the safeguard." | Confirm against D3; if D8 = yes, add the file that holds the fallback count | D3, P4 | |
| C13 | 5.5, third paragraph | "…the baseline script also produces the sensitivity results of Section 4.3: …" | Confirm (the ML script produces none); if PR2 adds sensitivity results on test, say so | PR2 | |
| C14 | 5.6 Table 5.7, row "Final test" | "Final-test outputs pending" | Replace with a short description of the PR2 outputs, in the same style as the Google column | PR2 | |
| C15 | 5.6, fourth paragraph | "The one-time Alibaba final test reads this manifest before it opens the test table." | Replace with a description of the PR2 checks, in the order PR2 runs them (compare with the Google paragraph just above it), and say whether a second run is refused | PR2 | |

---

## Step 4: Numbers to fill

Replace each `pending` cell. Do not round differently from the surrounding table.

| Where | Cell | Source |
|---|---|---|
| Ch5 Table 5.2 | Alibaba rows (row counts, targets, same-second 2,006 / 245 / 251) | Confirm against `alibaba_gpu_v2020_targets/metadata.json` → `per_split.<split>.rows`, `in_split_successor_rows`, `cpu_status_counts.available`, `memory_status_counts.available`, `same_second_successor_rows` |
| Ch5 §5.2.2 | "P99 at `min_runs = 10`" | `baseline_selection.json` → `selected_policy`, `selected_min_runs` |
| Ch5 §5.2.3 | Fallback rates 7.6% / 16.4% / 20.3% / 25.7% and median history 31 | Recompute from `recommendations_validation.parquet` and the validation target table; these values currently come from `reports/results/alibaba_gpu_2020/alibaba_gpu_2020_results_tasks1_6.md` |
| Ch5 Table 5.4 | All `pending` cells | Snippet below; Hybrid row from the D8 output file, or `rec_*_selected` missing on the population |
| Ch5 Table 5.6 | One row per candidate per resource: model, settings, validation RMSE and MAE, selected | `candidate_models.csv` → `resource`, `model`, `rmse`, `mae`, `selected`; settings from `model_selection.json` → `<resource>.hyperparameters` for the selected model (for the others, from the candidate code). State the units: CPU in `percent_of_vcpu`, memory in GB. Add rows as needed |
| Ch7 §7.2 | Alibaba validation and final-test results, all seven policies | `alibaba_gpu_v2020_ml/validation_policy_comparison.csv` and the PR2 final-test comparison |
| Ch7 §7.3 | Discussion of Alibaba ML and Hybrid | Same files |
| Ch9 §9.1–9.2 | Alibaba final numbers in the summary and conclusions | PR2 final-test comparison |

**Table 5.4 snippet.** Run it only **after the final test**, because it reads test target statuses.

```python
import pandas as pd
T = "data/processed/alibaba_gpu_v2020_targets"
B = "data/processed/alibaba_gpu_v2020_baselines"
for split in ["train", "validation", "test"]:
    t = pd.read_parquet(f"{T}/{split}.parquet",
                        columns=["role_key", "exclusion_reason", "cpu_target_status", "memory_target_status"])
    r = pd.read_parquet(f"{B}/recommendations_{split}.parquet")
    d = t[t.exclusion_reason.isna()].merge(r, on="role_key", validate="one_to_one")
    pop = d[d.cpu_target_status.eq("available") | d.memory_target_status.eq("available")]
    print(split, len(pop),
          "history cpu/mem:", int(pop.uses_history_cpu_p99.sum()), int(pop.uses_history_memory_p99.sum()),
          "request cpu/mem:", int((~pop.uses_history_cpu_p99).sum()), int((~pop.uses_history_memory_p99).sum()),
          "no safeguard cpu/mem:", int(pop.rec_cpu_selected.isna().sum()), int(pop.rec_memory_selected.isna().sum()))
```

The validation population must print 42,069. If the selected policy or `min_runs` changed, replace `p99` in the column names accordingly.

---

## Step 5: Supporting documents

| File | Change | Done |
|---|---|---|
| `docs/design/traceadvisor_system_guide.md` §1, §7.2, §9, §12 | "Task 7 in progress" → complete; selected Alibaba models; Alibaba final test | |
| `docs/design/canonical_schema_design_decisions.md` D-19 | The uncommitted D-19 edit (ML-only 47.8% / 41.9%, Hybrid 5.1% / 4.6% validation violations): replace the numbers with the final ones and commit | |
| `reports/results/alibaba_gpu_2020/` | Add the final results report (the current report covers Tasks 1–6 only) | |
| `reports/results/alibaba_gpu_2020/` | Copy the small result files so every report number traces to a committed file (only `canonical/count_report.md` and `canonical/metadata.json` are there now): `targets/metadata.json`; `baselines/baseline_selection.json`, `validation_comparison.csv`, `sensitivity_validation.csv`, `metadata.json`; `ml/decision_manifest.json`, `model_selection.json`, `candidate_models.csv`, `validation_policy_comparison.csv`, `feature_order.json`, `metadata.json`; and the PR2 final-test comparison and run record. Do not copy Parquet tables or model files. Check that no file contains a local absolute path | |
| `docs/planning/github_issues/task7_machine_learning_hybrid_and_final_test.md` | Make decision D-2 and line 185 match D1 and D4 (P5), if not done in the PR | |
| Report source maps (`ch2_source_map.md`, `ch3_source_map.md`, `ch5_source_map.md`) | Remove "planned" / "(Task 7)" / "(pending)" next to `scripts/run_alibaba_gpu_2020_ml.py`, `data/processed/alibaba_gpu_v2020_ml/` and the Task 7 rows; add the PR2 script | |

---

## Step 6: Final check

From the repository root:

```bash
grep -rn -i "pending\|task 7\|planned" docs/project_report/chapter_*/ch[2-9]_*.md | grep -v source_map
```

The output must be empty, apart from words that are part of normal prose (for example "pending" in an unrelated sentence). Every row in Steps 1, 3, 4 and 5 must be marked ✅ or ✏️.

---

## Record of edits already made (29 Oct 2026, from PR #99)

These were applied before Task 7 finished, from PR #99 as it stood on 29 Oct. They appear above as **Confirm** rows and must be re-checked against the Step 1 answers, because PR #99 may change.

| Row | Chapter and section | Change |
|---|---|---|
| C1, C2 | Ch4 §4.2.2 | Alibaba features include the GPU request, instance count, GPU type, GPU type specification and workload label |
| C3 | Ch5 §5.3.1 | Alibaba features paragraph rewritten from the PR #99 feature configuration |
| C4 | Ch5 §5.1.1 | GPU fields used as features, not as targets |
| C5, C6, C7 | Ch3 §3.2, Ch5 §5.3.2–5.3.3 | Alibaba constant predictor is the mean only |
| C10, C41, C42 | Ch5 §5.3.2, §5.4 | Alibaba candidates, settings, selection procedure and Hybrid validation written from PR #99 |
| C11 (Google part) | Ch4 §4.2.2 | Google selection: log-scale RMSE, MAE as the only tie-breaker |
| C13 | Ch5 §5.5 | Only the baseline script produces sensitivity results |
| C14, C15 | Ch5 §5.6 | Table 5.7 (artifacts); Alibaba decision manifest paragraph |
| C16 | Ch2 §2.1, §2.2.6; Ch3 §3.5; Ch4 §4.4 | Integrity wording: per-stage checksums on Alibaba, input hashes in the decision manifest on Google |
| C18 | Ch2 §2.2.4 | Baselines are computed from point-in-time history, not fitted on the training set |
