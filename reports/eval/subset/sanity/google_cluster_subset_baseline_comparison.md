# Google Cluster Subset Baseline Comparison

This table reports validation baseline metrics. Validation results may be used for baseline and policy selection. The test split is reserved for final held-out evaluation after model and policy choices are locked.

| split      | baseline   |   cpu_violation_rate |   mem_violation_rate |   any_violation_rate |   avg_cpu_waste |   avg_mem_waste |   avg_cpu_utilization |   avg_mem_utilization |   cpu_util_valid_rows |   mem_util_valid_rows |
|:-----------|:-----------|---------------------:|---------------------:|---------------------:|----------------:|----------------:|----------------------:|----------------------:|----------------------:|----------------------:|
| validation | mean       |             0.37939  |            0.298086  |             0.449731 |      0.00627646 |      0.00186074 |               1.62865 |              0.932279 |                 10092 |                  7223 |
| validation | p90        |             0.2664   |            0.16614   |             0.333767 |      0.0126283  |      0.00244489 |               1.37699 |              0.780817 |                  9429 |                  7982 |
| validation | p95        |             0.253484 |            0.115964  |             0.29725  |      0.0156595  |      0.00264802 |               1.18753 |              0.719487 |                 10192 |                  8780 |
| validation | p99        |             0.229604 |            0.0966363 |             0.265007 |      0.0206675  |      0.00286312 |               1.05055 |              0.648025 |                 10197 |                  9545 |
| validation | req        |             0.444806 |            0.0950567 |             0.450195 |      0.00576431 |      0.00456828 |               1.87369 |              0.830864 |                 10427 |                 10194 |