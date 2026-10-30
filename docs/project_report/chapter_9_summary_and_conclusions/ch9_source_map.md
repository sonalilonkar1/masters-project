# Chapter 9 Source Map: Summary, Conclusions, and Recommendations

**Purpose:** for each Chapter 9 section, what to summarize and where it comes from. Chapter 9 introduces **no new results**: it summarizes Chapters 4–7, states the conclusions they support, and lists limitations and future work. Every claim must point to a section of an earlier chapter.

**Scope rules**
- Write after Chapter 7. Alibaba conclusions depend on **[Task 7]**: write the structure, leave Alibaba numbers and conclusions as *pending*, and add every such sentence to `pending_checks_after_task7.md`.
- Style: formal prose, no tables unless necessary; citations only for the two datasets.

---

## 9.1 Summary

| Topic | Source |
|---|---|
| Problem and approach | Chapter 4 introduction (pre-execution validity, asymmetric risk, dataset heterogeneity; acting at submission from historical traces) |
| System | Chapter 2 (subsystems); Chapter 4 §4.1 (canonical model, profiles, adapters) |
| Policies | Chapter 4 §4.2 (Request, Mean, P90/P95/P99 with `min_runs`, ML, Hybrid = max(ML, safeguard)) |
| Evaluation | Chapter 4 §4.3 (replay, separate CPU and memory metrics, fixed populations, lock and one-time test) |
| Google results | Chapter 7 §7.1 (test: Hybrid 12.36% any-resource violation, P99 14.67%, Request 54.47%; Hybrid waste ≈ P95) |
| Alibaba results | Chapter 7 §7.2: Task 6 validation (P99@10: 5.58% memory violation, 8.94 GB waste vs Request 4.74%, 22.26 GB); **[Task 7]** ML, Hybrid and final test *pending* |

## 9.2 Conclusions

| Conclusion to evaluate | Evidence |
|---|---|
| History-based percentiles reduce violations relative to requests where requests are too low (Google), and reduce waste where requests are generous (Alibaba memory) | Chapter 7 §7.1.1, §7.2 |
| An accurate ML model alone is efficient but under-provisions often | Google test: ML 32.82% any-resource violation at the lowest waste; **[Task 7]** Alibaba |
| The Hybrid safeguard combines the two: never more violations than its safeguard, at close to the safeguard's waste | Google test: 12.36 vs P95 17.37, waste 7.637 vs 7.616 CPU; **[Task 7]** Alibaba |
| Canonical model and capability profiles allow one evaluation across structurally different traces without pretending they measure the same thing | Chapter 4 §4.1–4.3, Table 4.1 |
| Strict temporal controls are necessary and observable | Chapter 6 §6.2 (checks; Google cross-split finding and its sensitivity) |
| **[Task 7]** Whether the Google findings hold on Alibaba | Chapter 7 §7.2 |

## 9.3 Limitations and Recommendations for Further Research

| Limitation | Source |
|---|---|
| Google targets cross the validation/test boundary (104 of 330 validation targets); validation somewhat optimistic; selected baseline unchanged on validation-period targets | Chapter 4 §4.1.7; Chapter 6 §6.2; Chapter 7 §7.1.2 sensitivity; system guide §13 |
| Small Google populations (329 / 259); Kaggle 31-day sample, not the full trace | `googlepipeline_finalrun.md` §7 |
| Normalized Google units; waste not in cores or GB; no numeric cross-dataset comparison | Chapter 4 §4.1.1 |
| Alibaba CPU is a lifetime average, not peak safety | Chapter 4 §4.1.1, §4.3 |
| Alibaba selection bias: 36.8% of roles eligible; 98% of evaluated roles single-instance; telemetry about day 19 to 68.9 | Chapter 4 §4.1.6; `alibaba_gpu_2020_results_tasks1_6.md` §2, §6 |
| Back-transformation bias of the log target (Google) | Chapter 4 §4.2.2 |
| **[Task 7]** Alibaba ML tuning: one fixed configuration per model if no grid is added (checklist D4) | Chapter 4 §4.2.2 |
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
| 2 | **[Task 7]** | Alibaba summary, conclusions and the tuning limitation | *pending*; add to the checklist |
| 3 | Chapter 1 | Related-work comparisons depend on the rewritten literature review | Refer to Chapter 1 without citing until it is final |
