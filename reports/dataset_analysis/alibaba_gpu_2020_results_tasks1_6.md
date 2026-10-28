# Alibaba GPU 2020 — Results So Far (Tasks 1–6)

**Question:** What do the Alibaba GPU 2020 pipeline results show so far, from the canonical data (Task 3) through the splits and targets (Task 4) to the baseline validation results (Task 6)?

**Short answer:** 461,900 of 1,254,108 role occurrences are eligible, and they split 70/15/15 into 323,329 / 69,286 / 69,285 rows. 42,069 validation rows have a next-occurrence target. On validation, **P99 history sizing at `min_runs = 10` is the best history baseline**: 5.58% memory violations with 8.94 GB average memory waste. **Request** (the current allocation) has the lowest memory violation rate, 4.74%, but wastes 2.5× as much memory (22.26 GB), has twice the memory shortfall and more than twice the CPU violation rate. With the PR #97 review's D1 fix applied, Task 6 selects among the history policies only (Request is reported as the status-quo reference but is not a selection candidate), which gives **P99 at `min_runs = 10`**.

**Status:** **validation results only.** Test outcomes have not been read or scored; Task 7 performs the only final-test evaluation. PR #97 (Task 6) is still open; the review's D1 fix (history-only selection) is applied (`docs/github_reviews/task6_pr97_review.md`, D1). All numbers here may change if Tasks 3–6 change.

**Scope:** Analysis only. No source files, notebooks, schemas or configurations were modified. This report is the only file created in the repository.

---

## 0. Evidence used

| Item | Source |
|---|---|
| Task 3 canonical data | Shared copy built from `c2ae87f` (`data/processed/alibaba_gpu_v2020/`), its `count_report.md` and `metadata.json`; `--verify` passed during the Task 4 review |
| Task 4 tables | Built locally during the PR #97 review with `scripts/build_alibaba_gpu_2020_targets.py` (Task 4 code as merged in PR #96, run at `af82838`), written to a scratch folder |
| Task 5 evaluator | `src/evaluation/evaluator.py` on `main` (used through Task 6; no results of its own) |
| Task 6 results | `scripts/run_alibaba_gpu_2020_baselines.py` from PR #97 (with the D1 fix applied), run on the Task 4 tables above; outputs written to a scratch folder. Sensitivity cuts at the selected `min_runs = 10` are produced by the same run (`build_sensitivity_tables`) |
| Software | Python 3.10.0, pandas 2.3.3, pyarrow 23.0.1 |

Units: memory in **GB** (per instance of a task role); CPU in **`percent_of_vcpu`** (lifetime average per run). Waste and shortfall are averages per scored row.

---

## 1. Pipeline status

| Task | What it delivers | Status |
|---|---|---|
| 1. Shared adapter framework and rejected-output support | Adapter base, rejected output | Merged |
| 2. Data setup and source loading | Checksum-verified loading of the official `cluster-trace-gpu-v2020` tables | Merged |
| 3. Adapter and canonical artifacts | `role_occurrence`, `instance`, `rejected` views | Merged (PRs #94, #95; build from `c2ae87f`) |
| 4. Splits, history and next-occurrence targets | Train, validation and test tables; `iter_resource_history` | Merged (PR #96) |
| 5. Dataset-aware evaluator | Separate CPU and memory denominators; any-resource suppressed; CPU average-usage label | Merged |
| 6. Baselines and `min_runs` selection | Request, Mean, P90, P95, P99; validation comparison; locked selection | **PR #97 open, under review** |
| 7. ML, Hybrid and final test | — | Not started |

---

## 2. Dataset semantics that shape every result

- **Memory is the real peak** (`max_mem`), so memory results measure peak safety. Memory is the primary resource.
- **CPU is the lifetime average of each run**; the CPU peak is not in the trace. A CPU "violation" means the next run's average exceeded the recommendation. **CPU results are average-usage sizing, never peak-safe provisioning.**
- **No any-resource metric** is reported: combining an average CPU result with a peak memory result has no meaning.
- **Unit of evaluation:** one task role of one job occurrence (`role_occurrence`), with requests and usage per instance (`task_role_per_instance`).
- **Telemetry window:** about day 19 to day 68.9 of the trace.

---

## 3. Canonical data (Task 3)

| Level | Source rows | Accepted | Rejected (`missing_submission_time`) |
|---|---|---|---|
| Job | 1,055,501 | 1,051,838 | 3,663 |
| Role occurrence | 1,261,050 | 1,254,108 | 6,942 |
| Instance | 7,522,002 | 7,410,783 | 111,219 |

Every level reconciles (source = accepted + rejected).

Why role occurrences are excluded (rule order, first matching rule):

| `exclusion_reason` | Roles | Share of accepted |
|---|---|---|
| `missing_sensor` | 287,780 | 22.9% |
| `job_failed` | 282,027 | 22.5% |
| `partial_sensor_coverage` | 97,018 | 7.7% |
| `job_incomplete` | 87,980 | 7.0% |
| `instance_failed` | 33,022 | 2.6% |
| `multi_attempt_worker` | 2,048 | 0.2% |
| `no_recurrence_key` | 1,788 | 0.1% |
| `invalid_memory_exceeds_capacity` | 512 | <0.1% |
| `instance_interrupted` | 31 | <0.1% |
| `missing_or_invalid_request` | 2 | <0.1% |
| **Eligible** | **461,900** | **36.8%** |

1,224 eligible roles have no usable CPU value; they still count for memory.

Most of the loss is missing telemetry (`missing_sensor`, `partial_sensor_coverage`: 30.6%) and unsuccessful jobs (`job_failed`, `job_incomplete`: 29.5%). Results therefore describe **completed, fully observed workloads**, which is a selection bias to report with every result.

---

## 4. Splits and targets (Task 4)

Chronological 70/15/15 split of the eligible rows by submission time; whole jobs stay in one split. A row's target is the **immediately next eligible run of the same recurrence**, only if it is in the same split.

| Split | Rows | Occurrences | Rows with a next-occurrence target | CPU target `available` | Memory target `available` | Same-second successor |
|---|---|---|---|---|---|---|
| Train | 323,329 | 319,186 | 220,832 | 220,299 | 220,832 | 2,006 |
| Validation | 69,286 | 68,549 | 42,069 | 41,913 | 42,069 | 245 |
| Test | 69,285 | 68,677 | 44,053 | 44,045 | 44,053 | 251 |

- Rows without a target: last run of their recurrence (`no_next_occurrence`: 93,655 / 19,481 / 25,232) or next run in a later split (8,842 / 7,736 / 0).
- These figures are identical to the Task 4 (PR #96) review, §5.2.
- **Requests are generous:** in train, the median request is about **7×** the run's actual peak memory, and only **8%** of runs exceed their memory request.

---

## 5. Baseline results on validation (Task 6)

### 5.1 Population and history depth

- **Common validation population:** 42,069 rows (every row with a CPU or memory target), from 9,712 recurrences. Memory is scored on all 42,069; CPU on 41,913.
- **History depth** (earlier completed runs of the same recurrence, memory): median 31; 25% of rows have 9 or fewer; 90th percentile 894; maximum 15,005. A few very large recurrences dominate the history.
- **Request fallback:** a history policy falls back to the request when the row has fewer than `min_runs` earlier runs.

| `min_runs` | Rows falling back to Request |
|---|---|
| 1 | 7.6% |
| 3 | 16.4% |
| 5 | 20.3% |
| 10 | 25.7% |

The same rates apply to CPU and memory.

### 5.2 Validation comparison (all 20 candidates)

Sorted by the agreed memory-first order (memory violation, memory waste, CPU violation, CPU waste, `min_runs`, policy).

| Policy | `min_runs` | Memory violation % | Avg memory waste (GB) | Avg memory shortfall (GB) | Avg memory utilization | CPU violation % | Avg CPU waste | Avg CPU utilization |
|---|---|---|---|---|---|---|---|---|
| Request | any (identical) | **4.74** | 22.26 | 0.83 | 0.26 | 15.52 | 430.1 | 0.37 |
| P99 | 10 | 5.58 | 8.94 | 0.42 | 0.63 | 6.62 | 295.0 | 0.65 |
| P99 | 5 | 6.10 | 7.69 | 0.36 | 0.66 | 6.46 | 278.1 | 0.67 |
| P99 | 3 | 6.77 | 6.88 | 0.34 | 0.68 | 6.65 | 266.3 | 0.68 |
| P95 | 10 | 8.46 | 8.26 | 0.45 | 0.66 | 9.00 | 263.1 | 0.68 |
| P99 | 1 | 8.74 | 5.51 | 0.34 | 0.72 | 8.67 | 245.0 | 0.71 |
| P95 | 5 | 9.11 | 6.99 | 0.39 | 0.69 | 8.98 | 245.8 | 0.70 |
| P95 | 3 | 9.88 | 6.18 | 0.37 | 0.72 | 9.28 | 233.8 | 0.72 |
| P95 | 1 | 11.90 | 4.80 | 0.38 | 0.76 | 11.34 | 212.4 | 0.74 |
| P90 | 10 | 12.40 | 7.80 | 0.49 | 0.68 | 12.25 | 235.4 | 0.70 |
| P90 | 5 | 13.21 | 6.52 | 0.43 | 0.72 | 12.46 | 217.5 | 0.72 |
| P90 | 3 | 14.05 | 5.69 | 0.41 | 0.74 | 12.85 | 205.4 | 0.74 |
| P90 | 1 | 16.10 | 4.31 | 0.42 | 0.78 | 14.95 | 183.9 | 0.77 |
| Mean | 10 | 39.90 | 6.85 | 0.80 | 0.74 | 40.84 | 142.6 | 0.78 |
| Mean | 5 | 42.65 | 5.53 | 0.76 | 0.78 | 42.84 | 121.6 | 0.81 |
| Mean | 3 | 44.26 | 4.63 | 0.78 | 0.80 | 44.22 | 108.0 | 0.83 |
| Mean | 1 | 46.52 | 3.19 | 0.81 | 0.85 | 46.70 | 86.0 | 0.86 |

### 5.3 What the comparison shows

1. **More history helps every history policy.** For P99, P95, P90 and Mean, memory violation falls steadily from `min_runs = 1` to `10` (P99: 8.74% → 5.58%). Part of this is the request fallback: at `min_runs = 10`, 25.7% of rows use the generous request instead of a short history.
2. **Percentile level is the main trade-off.** Moving from Mean to P90, P95 and P99 lowers memory violation (39.9% → 12.4% → 8.5% → 5.6% at `min_runs = 10`) and raises memory waste (6.9 → 7.8 → 8.3 → 8.9 GB).
3. **Mean is not a safe sizing policy:** it is exceeded about 40–47% of the time.
4. **Request vs P99@10:** Request is exceeded slightly less often (4.74% vs 5.58%), but it reserves about 4× the memory a run actually peaks at (utilization 0.26), wastes 2.5× more memory (22.26 vs 8.94 GB), and when it is exceeded it is exceeded by more (shortfall 0.83 vs 0.42 GB). Its CPU violation rate is more than twice P99@10's (15.52% vs 6.62%).
5. **CPU requests are not generous in the same way as memory requests.** Request has a 15.5% CPU violation rate and the largest CPU shortfall (172 vs 24 for P99@10), so the current CPU requests are often below the next run's average usage.

### 5.4 Selection

| | Selected | Basis |
|---|---|---|
| Before the D1 fix (Request selectable) | Request, `min_runs = 1` | Request has the lowest memory violation; its four identical rows tie, and `min_runs` ascending picks 1 |
| After the D1 fix (applied in this PR) | **P99, `min_runs = 10`** | Same sort order applied to the history policies only; Request reported as the reference |

Why Request is excluded: Task 7's Hybrid is `max(ML prediction, selected baseline)`, so with Request as the baseline Hybrid could never allocate less than the current request; and with Request@1 the four history baselines would be reported on test at their weakest setting. The D1 fix makes only the history policies (Mean, P90, P95, P99) selectable, so the locked baseline is **P99 at `min_runs = 10`**.

### 5.5 Sensitivity on validation (at `min_runs = 10`)

Reported separately; none of these changes the selection.

| Cut | Rows | Request: mem viol % / mem waste | P99: mem viol % / mem waste | P95: mem viol % / mem waste | P99: CPU viol % |
|---|---|---|---|---|---|
| All rows (occurrence-weighted) | 42,069 | 4.74 / 22.26 | 5.58 / 8.94 | 8.46 / 8.26 | 6.62 |
| Same-second successors excluded | 41,824 | 4.75 / 22.28 | 5.60 / 8.98 | 8.48 / 8.30 | 6.65 |
| Same-second successors only | 245 | 2.86 / 17.49 | 1.22 / 2.13 | 4.08 / 1.55 | 1.63 |
| Multi-instance roles (`inst_num > 1`) | 889 | 13.39 / 25.96 | 10.91 / 13.66 | 12.26 / 13.17 | 12.16 |
| Each recurrence weighted equally (9,712 groups) | 42,069 | 7.12 / 22.99 | 7.69 / 14.09 | 9.86 / 13.52 | 7.35 |

- **Same-second successors** (245 rows) do not change the picture; excluding them moves results by less than 0.05 points.
- **Multi-instance roles** (889 rows, 2% of the population) are harder to size: every policy is exceeded more often. Here **P99@10 beats Request on memory violation** (10.91% vs 13.39%) as well as waste.
- **Weighting each recurrence equally** raises violation rates for every policy (the many small recurrences have short histories), but the order is the same: Request 7.12%, P99 7.69%, P95 9.86%. P99's memory waste rises to 14.09 GB, still well below Request's 22.99 GB.

With the D1 fix the selected `min_runs` is 10, so the PR #97 output files hold these cuts at `min_runs = 10`.

---

## 6. Limitations and open points

- **Validation only.** Test results come from Task 7, once, after the selection, models and Hybrid rule are locked.
- **Selection rule.** The D1 fix is applied: only the history policies are selectable, giving **P99 at `min_runs = 10`**. PR #97 is still open for review.
- **CPU is average usage.** CPU violation rates do not measure peak safety; short CPU spikes above any recommendation are invisible in this trace.
- **Selection bias.** Only 36.8% of role occurrences are eligible: completed, fully observed workloads.
- **Mostly single-instance roles.** Only 889 of 42,069 validation rows (2%) are multi-instance, and they behave differently (§5.5).
- **Very uneven recurrences.** Median history is 31 runs, but a few recurrences have thousands; occurrence-weighted results lean towards them.

---

## 7. How to reproduce

1. Download the shared Task 3 copy (`alibaba_gpu_v2020_c2ae87f`) into `data/processed/alibaba_gpu_v2020/` and check it with `python3 scripts/build_alibaba_gpu_2020_canonical.py --verify data/processed/alibaba_gpu_v2020`.
2. Build the Task 4 tables: `python3 scripts/build_alibaba_gpu_2020_targets.py` (about 1 minute, 5 GB peak memory).
3. On the PR #97 branch: `python3 scripts/run_alibaba_gpu_2020_baselines.py` (about 2 minutes, 1.9 GB peak memory). Outputs: `validation_comparison.csv`, `sensitivity_validation.csv`, `baseline_selection.json`, `history_statistics.parquet`, `recommendations_{train,validation,test}.parquet`, `metadata.json` in `data/processed/alibaba_gpu_v2020_baselines/`.
4. With the D1 fix applied the run selects P99 at `min_runs = 10`, so `sensitivity_validation.csv` (§5.5) is produced directly at that setting.
