# Chapter 9. Summary, Conclusions, and Recommendations

This chapter summarizes the project, states the conclusions supported by the results of Chapter 7, and discusses the limitations of the evaluation and directions for further work. It introduces no new results.

## 9.1 Summary

Users of shared clusters must state the CPU and memory a job needs before it runs, and because under-provisioning can cause out-of-memory failures and evictions while over-provisioning only wastes capacity, they tend to request too much. This project developed TraceAdvisor, an offline, trace-driven system that recommends CPU and memory for recurring workloads before submission, using only the history of earlier runs and without changes to the scheduler.

TraceAdvisor converts each trace into a shared canonical model through a dataset-specific adapter, while a capability profile records what each dataset can and cannot measure (Section 4.1). From the canonical data, it reconstructs recurring workloads and builds point-in-time profiles that use only runs completed before each submission. The recommendations compared are the original request; the mean and the 90th, 95th and 99th percentiles of earlier usage, falling back to the request when a workload has fewer than `min_runs` earlier runs; an ML prediction; and a Hybrid policy that takes the larger of the ML prediction and a historical percentile (Section 4.2). Recommendations are evaluated by chronological replay, with violation rate, shortfall, waste and utilization reported separately for CPU and memory. Every selection is made on a validation period and locked in a decision manifest before the test period is scored once (Sections 4.3 and 6.2).

The system was evaluated on a 31-day sample of Google ClusterData 2019 [Wilkes 2019] and on the full Alibaba GPU 2020 trace [Alibaba 2020]. On the Google test period, Hybrid had the lowest rate of CPU or memory violations, 12.36%, compared with 14.67% for the 99th percentile, 17.37% for its 95th-percentile safeguard, and 54.47% for the original requests (Section 7.2). On Alibaba, Hybrid lowered the violation rates of its 99th-percentile safeguard from 6.45% to 3.77% for average CPU usage and from 3.44% to 3.15% for memory, at 8.71 GB of average memory waste compared with 8.67 GB, while the original requests reached a similar memory violation rate of 3.16% at 22.31 GB (Section 7.3).

## 9.2 Conclusions

**Historical percentiles are a strong baseline, and their value depends on the requests they replace.** On Google, where requests were exceeded by more than half of test occurrences, percentile recommendations reduced violations substantially. On Alibaba, where memory requests were generous, they reduced memory waste by more than half at a similar violation rate. This agrees with earlier findings that recurring workloads behave consistently enough for their history to guide allocation [Cortez 2017].

**An ML prediction alone is not a safe allocation.** On both datasets, the ML policy had the lowest waste but under-provisioned about one occurrence in three on Google and almost one in two on Alibaba, even though the Alibaba models explained most of the variance in validation (R² of 0.76 for CPU and 0.53 for memory). A model trained to minimize average error aims at typical usage, while a safe allocation must cover high usage.

**The Hybrid rule combines the strengths of both.** Because Hybrid never recommends less than its safeguard when a historical recommendation exists, it cannot have more violations than the safeguard on those workloads, and on both test periods it had fewer at almost the same waste. The ML prediction raises the recommendation only for the workloads it expects to grow, which is where the historical percentile alone falls short.

**A canonical model with explicit capability profiles allows one evaluation across structurally different traces.** The same policies, metrics and selection rules were applied to two traces that differ in structure, units and resource semantics, without treating them as measuring the same quantities. In particular, Alibaba CPU is reported as average-usage sizing because the trace records only lifetime averages (Table 4.1).

**Time controls can be enforced by the workflow rather than left to convention.** Point-in-time features, chronological splits, locked decisions and a one-time test are checked automatically before any result is produced (Section 6.2).

**The direction of the `min_runs` effect depends on the requests.** A larger history threshold sends more workloads to the request fallback, which increased violations on Google and decreased them on Alibaba (Section 7.4). The safeguard and threshold should therefore be selected per platform rather than fixed in advance.

## 9.3 Limitations and Recommendations for Further Research

The results are subject to several limitations.

- **Google units are normalized,** so its waste cannot be expressed in cores or gigabytes, and no numeric comparison across datasets is possible.
- **Alibaba CPU is a lifetime average,** so its CPU results describe average-usage sizing and not protection against CPU peaks.
- **The Alibaba population is selective.** Only 36.8% of task-role occurrences were eligible, mainly because many instances have no sensor data, and about 98% of the evaluated occurrences are from single-instance roles.
- **ML tuning was limited.** On Google, the log-scale target biases predictions low; on Alibaba, each model family used one fixed configuration, and the ML and Hybrid validation results are optimistic because the same split selected the models.
- **GPU usage was not evaluated** as a target.
- **The evaluation is offline,** so the results do not establish effects on job failures, scheduling or cost in a running cluster.

These limitations suggest the following directions for further work.

- **Direct quantile modelling with calibration.** Predicting a high quantile of next-run usage directly, with calibrated coverage, could replace the combination of a point forecast and a separate safeguard (Section 4.2.2).
- **Further datasets and resources.** Through the adapter framework, further traces can be added, such as the Azure VM traces as a CPU-only portability check, and GPU sizing can be evaluated on Alibaba, where GPU usage is recorded.
- **Uncertainty.** Repeated runs and bootstrap confidence intervals would show which differences are statistically reliable.
- **Shadow-mode evaluation.** Through the planned API (Section 8.3), recommendations could be returned for new submissions and compared with their observed usage without changing the allocated resources, which would measure the system's effect in a live cluster without risk to running jobs.
