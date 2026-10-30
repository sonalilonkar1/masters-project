# Chapter 9 Source Map: Summary, Conclusions, and Recommendations

**Purpose:** for each Chapter 9 section, what to summarize and where it comes from. Chapter 9 introduces **no new results**: it summarizes Chapters 4–7, states the conclusions they support, and lists limitations and future work. Every claim must point to a section of an earlier chapter.

**Scope rules**
- Write after Chapter 7. Both datasets are final; Alibaba numbers come from `reports/results/alibaba_gpu_2020/alibaba_gpu_2020_results_and_analysis.md`.
- Style: formal prose, no tables unless necessary; citations only for the two datasets.

---

## 9.1 Summary

| Topic | Source |
|---|---|
| Problem and approach | Chapter 4 introduction (pre-execution validity, asymmetric risk, dataset heterogeneity; acting at submission from historical traces) |
| System | Chapter 2 (subsystems); Chapter 4 §4.1 (canonical model, profiles, adapters) |
| Policies | Chapter 4 §4.2 (Request, Mean, P90/P95/P99 with `min_runs`, ML, Hybrid = max(ML, safeguard)) |
| Evaluation | Chapter 4 §4.3 (replay, separate CPU and memory metrics, fixed populations, lock and one-time test) |
| Google results | Chapter 7 §7.2 (test: Hybrid 12.36% any-resource violation, P99 14.67%, Request 54.47%; Hybrid waste ≈ P95) |
| Alibaba results | Chapter 7 §7.3: final test Hybrid 3.15% memory / 3.77% CPU violation vs P99@10 3.44% / 6.45% at 8.71 vs 8.67 GB memory waste; Request 3.16% memory at 22.31 GB; ML 44.77% memory at 1.33 GB |

## 9.2 Conclusions

| Conclusion to evaluate | Evidence |
|---|---|
| History-based percentiles reduce violations relative to requests where requests are too low (Google), and reduce waste where requests are generous (Alibaba memory) | Chapter 7 §7.2.1, §7.3 |
| An accurate ML model alone is efficient but under-provisions often | Google test: ML 32.82% any-resource violation at the lowest waste; Alibaba test: ML 44.77% memory / 47.37% CPU at the lowest waste, despite R² 0.53 / 0.76 on validation |
| The Hybrid safeguard combines the two: never more violations than its safeguard, at close to the safeguard's waste | Google test: 12.36 vs P95 17.37, waste 7.637 vs 7.616 CPU; Alibaba test: memory 3.15 vs P99 3.44 (8.71 vs 8.67 GB), CPU 3.77 vs 6.45 |
| Canonical model and capability profiles allow one evaluation across structurally different traces without pretending they measure the same thing | Chapter 4 §4.1–4.3, Table 4.1 |
| Strict temporal controls are necessary and observable | Chapter 6 §6.2 (checks; Google cross-split finding and its sensitivity) |
| The Google findings hold on Alibaba; what differs is the role of the request (low on Google, generous on Alibaba), which decides whether a larger `min_runs` adds or removes safety | Chapter 7 §7.4; `alibaba_gpu_2020_results_and_analysis.md` §8 |

## 9.3 Limitations and Recommendations for Further Research

| Limitation | Source |
|---|---|
| Google targets cross the validation/test boundary (104 of 329 scored validation occurrences); validation somewhat optimistic; selected baseline unchanged on validation-period targets | Chapter 4 §4.1.7; Chapter 6 §6.2; Chapter 7 §7.5 sensitivity; system guide §13 |
| Small Google populations (329 / 259); Kaggle 31-day sample, not the full trace | `googlepipeline_finalrun.md` §7 |
| Normalized Google units; waste not in cores or GB; no numeric cross-dataset comparison | Chapter 4 §4.1.1 |
| Alibaba CPU is a lifetime average, not peak safety | Chapter 4 §4.1.1, §4.3 |
| Alibaba selection bias: 36.8% of roles eligible; 98% of evaluated roles single-instance; telemetry about day 19 to 68.9 | Chapter 4 §4.1.6; `alibaba_gpu_2020_results_tasks1_6.md` §2, §6 |
| Back-transformation bias of the log target (Google) | Chapter 4 §4.2.2 |
| Alibaba ML tuning: one fixed configuration per model, no search; ML and Hybrid validation results optimistic because the same split selected the models | Chapter 4 §4.2.2; D-19 |
| GPU fields not evaluated | Chapter 5 §5.1.1 |

| Recommendation | Source |
|---|---|
| Direct quantile modelling with calibration | Chapter 4 §4.2.2 (quantile regression considered, not adopted) |
| Split-isolated Google targets | Chapter 4 §4.1.7 |
| Further datasets through the adapter framework (Alibaba 2018 deferred; Azure VM as a CPU-only portability check) | `docs/design/adapter_framework.md`; `docs/data/azure_vm_traceadvisor_feasibility.md`; system guide §11 |
| GPU sizing | Chapter 5 §5.1.1 |
| Online or shadow-mode evaluation through the API | Chapter 4 introduction (offline-only evaluation); Chapter 8 §8.3 |

---

## Check against the sources

| # | Item | Finding | Effect on Chapter 9 |
|---|---|---|---|
| 1 | No new results | Every number must already appear in Chapters 5–7 | Cross-check when writing |
| 2 | Task 7 | Alibaba summary, conclusions and the tuning limitation | Filled above (30 Oct 2026) |
| 3 | Chapter 1 | Related-work comparisons depend on the rewritten literature review | Refer to Chapter 1 without citing until it is final |
| 4 | Citations | [Cortez 2017] added in 9.2 for history-guided allocation | Maps to [2] in `references.md` |
| 5 | Feature importance | Removed from Chapter 7 | Listed as a limitation and future work |
