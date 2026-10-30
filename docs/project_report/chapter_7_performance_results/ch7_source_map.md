# Chapter 7 evidence source map

Repository audit: 30 October 2026. This is an evidence inventory, not a chapter draft. No experiments were rerun. Existing notebooks, implementation and result artifacts were read only. Paths below are repository-relative; notebook cell numbers are zero-based JSON indices. Numerical tables below are transcribed programmatically from saved CSVs, rounded for display; the named CSV and row key are authoritative for full precision.

## Evidence status and metric definitions

- **Saved final test:** committed final-test summary, linked to a frozen manifest/run record. This verifies the saved reported result, not a new independent experiment or full reproduction.
- **Validation / selection:** used for selecting policies or models; cannot be presented as final-test performance. Google validation policy rows explicitly retain `result_status=preliminary` even though the separate test manifest is final.
- **Supporting / exploratory:** a saved analysis exists but does not establish the complete recurrence-based CPU/memory/ML/Hybrid pipeline.
- **Unavailable:** no current saved output found; do not estimate it.

For the Google and Alibaba primary tables, `src/evaluation/metrics.py` defines violation as actual target > recommendation, waste as max(recommendation − actual, 0), shortfall as max(actual − recommendation, 0), and bounded utilization as min(actual/recommendation, 1). Utilization excludes nonfinite inputs and recommendations ≤ 1e-12. `src/evaluation/evaluator.py` averages valid values, excluding NaNs. Violation columns ending `_pct` are percentages; utilization is a ratio, not a percentage. Waste and shortfall are resource quantities averaged over valid rows, including nonviolating rows' zero shortfall. These are offline target-exceedance metrics, not measured production SLA failures, runtime improvements, throughput or cost savings.

Google any-resource violation is true if either resource definitely violates; false only if both are known nonviolations, otherwise unknown. It is not the sum of CPU and memory rates. Valid counts differ between policies. No primary table supplies a separate empirical prediction-interval coverage metric. Valid counts describe scoring availability; do not call them telemetry coverage or confuse them with 1 − violation rate.

## 7.1 Preliminary Baseline Studies on Azure Traces

Primary sources: `notebooks/resource-central/resource_central.ipynb` JSON cell 23, saved `text/plain` DataFrame output; `reports/eval/resource-central/tables/resource_central_baseline_metadata.csv` sole row; `resource_central_vm_level_results.csv` and `resource_central_bucket_metrics.csv` in the same tables directory. Status: verified saved preliminary, in-sample CPU results; no chronological validation/test split for this baseline study.

Table 7.1 transcribes cell 23’s saved rounded output, without rerunning it:

| Baseline | Provisioned CPU (%) | Violation (%) | Utilization proxy (%) |
| --- | --- | --- | --- |
| Mean | 8.62 | 20.67 | 100.00 |
| P90 | 20.10 | 10.00 | 42.90 |
| P95 | 38.81 | 5.00 | 22.21 |
| P99 | 90.28 | 1.00 | 9.55 |

Definition: demand = sampled `avg_cpu` × scale_factor (saved factor 1); thresholds = sample mean/quantiles; violation = 100 × mean(demand > threshold); utilization proxy = 100 × mean(demand)/threshold, not mean capped utilization. Same readings determine and score thresholds. No held-out reliability, memory, recurrence prediction, or Hybrid performance follows from this output.

Metadata confirms 100,000 readings and 100,000 VMs; average/median `p95_minus_mean` = 6.97701706727 / 2.2952135 percentage points; `bucket_accuracy` = 0.8711 (87.11%). Notebook cells 7,9,10,12 show `mean_cpu` is computed from `avg_cpu`, `p95_cpu` from `max_cpu`, and bucket accuracy is mean/P95 bucket agreement. The VM-level CSV has one sample per VM; these are within-reading average/maximum differences, not long-history per-VM P95 estimates. Cell 26’s separate classifier prototype does not turn the 87.11% agreement into test model accuracy.

## 7.2 Google ClusterData 2019 Results

### Population and provenance

Primary pipeline: `pipelines/google_subset/01_dataIngestion.ipynb` through `06_finalPolicyComparison.ipynb`, rather than the older `notebooks/GoogleCluster2019/` or `notebooks/subset/` experiments. Sources: `reports/results/google_subset/n04_metadata.json`, `n05_ml_metadata.json`, `decision_manifest.json`, `final_test_run_metadata.json`, and `googlepipeline_finalrun.md` §§1–3.

The Kaggle sample has 253,585 execution rows; chronological train/validation/test execution counts are 178,858 / 36,703 / 38,024 and occurrence counts 3,473 / 675 / 731. Both-target scoring populations are 329 validation and 259 test occurrences. Google targets are next-occurrence CPU and memory peaks in normalized units, at full-workload occurrence scope. Final manifest/run record reports clean commit `e59349e04a8fb87f8097780462cb2464a9e5d337`, freeze at 2026-10-29 20:03:25 UTC, test at 20:03:35 UTC. Its recorded final status does not remove the leakage and local artifact limitations in §7.5.

### 7.2.1 Baseline Recommendation Results

Request, Mean, P90, P95, P99 are available on validation and final test. Validation compares min_runs ∈ {1,3,5,10}; P99@1 is selected by lowest any-resource violation. Final comparison uses min_runs=1 for historical policies, with request fallback when history is insufficient. Every baseline row below identifies its source by CSV and `policy` (and `min_runs` in the full candidate table).

#### Google baseline candidates — validation / selection

Source: `reports/results/google_subset/tables/baseline_validation_comparison.csv`. Output location: header names below and each row’s policy/resource/model keys. Status and split are specified in the heading. Definitions: primary metrics above; prediction metrics below.

| policy | min_runs | cpu_violation_pct | memory_violation_pct | any_resource_violation_pct | average_cpu_utilization | average_memory_utilization | average_cpu_waste | average_memory_waste | average_cpu_shortfall | average_memory_shortfall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Mean | 1 | 35.365854 | 34.146341 | 42.987805 | 0.490653 | 0.509092 | 1.740472 | 0.362849 | 1.886908 | 0.216659 |
| P90 | 1 | 22.256098 | 21.646341 | 28.658537 | 0.386572 | 0.406117 | 4.855667 | 0.980455 | 1.334680 | 0.142224 |
| P95 | 1 | 18.597561 | 19.817073 | 25.304878 | 0.341114 | 0.370631 | 8.449073 | 1.864572 | 1.063636 | 0.103044 |
| P99 | 1 | 16.768293 | 17.073171 | 21.951220 | 0.297908 | 0.337065 | 19.041133 | 3.345875 | 0.972168 | 0.086182 |
| Request | 1 | 52.147239 | 38.036810 | 55.521472 | 0.622737 | 0.529662 | 0.957049 | 0.449035 | 2.421430 | 0.302142 |
| Mean | 3 | 36.697248 | 32.822086 | 42.944785 | 0.492853 | 0.494731 | 1.691664 | 0.390923 | 1.926506 | 0.236008 |
| P90 | 3 | 23.547401 | 20.552147 | 28.834356 | 0.391207 | 0.393944 | 4.762353 | 1.006552 | 1.374827 | 0.162779 |
| P95 | 3 | 20.183486 | 18.711656 | 25.460123 | 0.345878 | 0.358518 | 8.359986 | 1.895372 | 1.103226 | 0.123567 |
| P99 | 3 | 18.348624 | 16.257669 | 22.392638 | 0.302713 | 0.324960 | 18.979028 | 3.385185 | 1.011696 | 0.106768 |
| Request | 3 | 52.147239 | 38.036810 | 55.521472 | 0.622737 | 0.529662 | 0.957049 | 0.449035 | 2.421430 | 0.302142 |
| Mean | 5 | 36.085627 | 30.674847 | 41.717791 | 0.486583 | 0.473584 | 1.660923 | 0.411162 | 1.916174 | 0.229343 |
| P90 | 5 | 25.076453 | 19.631902 | 28.834356 | 0.393084 | 0.379611 | 4.539946 | 0.999714 | 1.414330 | 0.161730 |
| P95 | 5 | 22.018349 | 18.404908 | 26.073620 | 0.349291 | 0.345417 | 8.075216 | 1.882839 | 1.146365 | 0.123539 |
| P99 | 5 | 20.183486 | 16.257669 | 23.312883 | 0.307236 | 0.312911 | 18.644325 | 3.368093 | 1.057701 | 0.107552 |
| Request | 5 | 52.147239 | 38.036810 | 55.521472 | 0.622737 | 0.529662 | 0.957049 | 0.449035 | 2.421430 | 0.302142 |
| Mean | 10 | 40.061162 | 30.368098 | 45.092025 | 0.512617 | 0.469247 | 1.638618 | 0.423959 | 1.999384 | 0.235869 |
| P90 | 10 | 32.110092 | 21.779141 | 35.276074 | 0.439612 | 0.395933 | 4.144517 | 0.961917 | 1.608620 | 0.190712 |
| P95 | 10 | 29.663609 | 20.858896 | 33.435583 | 0.400608 | 0.367025 | 7.492935 | 1.831291 | 1.353068 | 0.159077 |
| P99 | 10 | 28.440367 | 19.018405 | 30.981595 | 0.361811 | 0.337969 | 17.910638 | 3.301600 | 1.272412 | 0.144392 |
| Request | 10 | 52.147239 | 38.036810 | 55.521472 | 0.622737 | 0.529662 | 0.957049 | 0.449035 | 2.421430 | 0.302142 |

#### Google policy comparison — saved final test (includes ML/Hybrid for §7.2.2)

Source: `reports/results/google_subset/tables/final_test_policy_comparison.csv`. Output location: header names below and each row’s policy/resource/model keys. Status and split are specified in the heading. Definitions: primary metrics above; prediction metrics below.

| policy | cpu_violation_pct | memory_violation_pct | any_resource_violation_pct | average_cpu_utilization | average_memory_utilization | average_cpu_waste | average_memory_waste | average_cpu_shortfall | average_memory_shortfall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Request | 50.583658 | 34.241245 | 54.474708 | 0.616912 | 0.548320 | 0.498079 | 0.176035 | 1.078243 | 0.186514 |
| Mean | 28.571429 | 33.590734 | 38.223938 | 0.436060 | 0.491494 | 1.226161 | 0.235393 | 0.810724 | 0.125781 |
| P90 | 18.146718 | 16.602317 | 22.779923 | 0.329633 | 0.382799 | 3.846919 | 0.744414 | 0.508794 | 0.077361 |
| P95 | 13.127413 | 13.127413 | 17.374517 | 0.277586 | 0.342160 | 7.616189 | 1.541418 | 0.370589 | 0.043018 |
| P99 | 9.266409 | 11.969112 | 14.671815 | 0.232648 | 0.296832 | 17.482997 | 2.994451 | 0.219613 | 0.039349 |
| ML | 30.115830 | 18.918919 | 32.818533 | 0.430606 | 0.311797 | 0.424415 | 0.130077 | 1.065403 | 0.165208 |
| Hybrid | 10.810811 | 7.722008 | 12.355212 | 0.241931 | 0.190262 | 7.636559 | 1.545782 | 0.364557 | 0.041557 |

#### Google policy comparison — validation / preliminary

Source: `reports/results/google_subset/tables/validation_policy_comparison.csv`. Output location: header names below and each row’s policy/resource/model keys. Status and split are specified in the heading. Definitions: primary metrics above; prediction metrics below.

| policy | valid_cpu_violation_count | valid_memory_violation_count | valid_any_resource_violation_count | valid_cpu_utilization_count | valid_memory_utilization_count | cpu_violation_pct | memory_violation_pct | any_resource_violation_pct | average_cpu_utilization | average_memory_utilization | average_cpu_waste | average_memory_waste | average_cpu_shortfall | average_memory_shortfall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Request | 326 | 326 | 326 | 315 | 326 | 52.147239 | 38.036810 | 55.521472 | 0.622737 | 0.529662 | 0.957049 | 0.449035 | 2.421430 | 0.302142 |
| Mean | 328 | 328 | 328 | 324 | 328 | 35.365854 | 34.146341 | 42.987805 | 0.490653 | 0.509092 | 1.740472 | 0.362849 | 1.886908 | 0.216659 |
| P90 | 328 | 328 | 328 | 324 | 328 | 22.256098 | 21.646341 | 28.658537 | 0.386572 | 0.406117 | 4.855667 | 0.980455 | 1.334680 | 0.142224 |
| P95 | 328 | 328 | 328 | 324 | 328 | 18.597561 | 19.817073 | 25.304878 | 0.341114 | 0.370631 | 8.449073 | 1.864572 | 1.063636 | 0.103044 |
| P99 | 328 | 328 | 328 | 324 | 328 | 16.768293 | 17.073171 | 21.951220 | 0.297908 | 0.337065 | 19.041133 | 3.345875 | 0.972168 | 0.086182 |
| ML | 329 | 329 | 329 | 329 | 329 | 30.395137 | 25.227964 | 34.954407 | 0.458292 | 0.424641 | 0.462198 | 0.155441 | 2.361424 | 0.298359 |
| Hybrid | 329 | 329 | 329 | 329 | 329 | 13.373860 | 14.589666 | 17.933131 | 0.285701 | 0.296925 | 8.469589 | 1.867287 | 1.042738 | 0.120440 |
| Hybrid_P99 | 329 | 329 | 329 | 329 | 329 | 11.854103 | 12.765957 | 15.501520 | 0.246460 | 0.270445 | 19.025843 | 3.343329 | 0.952055 | 0.103786 |

Final-test valid CPU/memory/any-resource violation counts: Request 257; all other policies 259. CPU utilization counts: Request 254, Mean/P90/P95/P99 258, ML/Hybrid 259; memory utilization Request 257 and all others 259. Source: final-test CSV `valid_*_count` columns. Thus the common 259-row population does not imply identical valid denominators. Validation valid counts appear above. Zero recommendations can be valid for violation/waste but invalid for utilization.

### 7.2.2 ML and Hybrid Recommendation Results

Sources: `pipelines/google_subset/05_evaluateRecommendations.ipynb` cells 10 (training label cutoff), 28 (refit cutoff), 30 (test feature allow-list); `n05_ml_metadata.json`; `tables/ml_validation_model_comparison.csv`. CPU/memory training populations for selection are 1,672 / 1,649; validation is 329 for both. Models train on log1p(target), with expm1 and clipping at zero for predictions. Raw RMSE = sqrt(mean squared error), MAE = mean absolute error, R² = 1 − residual sum of squares / target total sum of squares; `log_*` apply to log1p target and prediction. Model selection uses lowest validation log RMSE, raw MAE as tie-breaker. These are validation regression comparisons, not test regression accuracy.

Random Forest is selected for both resources: CPU depth 10, memory depth 6, 300 trees, min_samples_leaf=10, max_features=sqrt, seed 42. Final locked refits use train+validation labels with target start ≤ validation end (2,108 CPU / 2,082 memory rows). Do not confuse these with selection training counts.

#### Google model comparisons — validation / selection, including untuned and median references

Source: `reports/results/google_subset/tables/ml_validation_model_comparison.csv`. Output location: header names below and each row’s policy/resource/model keys. Status and split are specified in the heading. Definitions: primary metrics above; prediction metrics below.

| resource | variant | model | selectable | training_rows | validation_rows | mae | rmse | r2 | log_mae | log_rmse | log_r2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cpu | tuned | decision_tree | True | 1672 | 329 | 2.852441 | 9.686474 | -0.032158 | 0.566765 | 0.890988 | 0.052761 |
| cpu | starting | decision_tree | False | 1672 | 329 | 3.017286 | 9.807704 | -0.058156 | 0.614229 | 0.981220 | -0.148810 |
| cpu | tuned | random_forest | True | 1672 | 329 | 2.823622 | 9.559451 | -0.005266 | 0.566233 | 0.850443 | 0.137010 |
| cpu | starting | random_forest | False | 1672 | 329 | 2.879180 | 9.575071 | -0.008553 | 0.576802 | 0.865700 | 0.105767 |
| cpu | tuned | xgboost | True | 1672 | 329 | 2.851296 | 9.600012 | -0.013814 | 0.565298 | 0.860442 | 0.116598 |
| cpu | starting | xgboost | False | 1672 | 329 | 2.963228 | 9.636878 | -0.021616 | 0.597328 | 0.905451 | 0.021760 |
| cpu | reference | reference_median | False | 1672 | 329 | 2.755626 | 9.914146 | -0.081248 | 0.546103 | 1.047708 | -0.309772 |
| memory | tuned | decision_tree | True | 1649 | 329 | 0.487761 | 1.312772 | 0.023877 | 0.239843 | 0.421387 | 0.033391 |
| memory | starting | decision_tree | False | 1649 | 329 | 0.656479 | 1.600345 | -0.450619 | 0.292498 | 0.539254 | -0.582980 |
| memory | tuned | random_forest | True | 1649 | 329 | 0.453800 | 1.255345 | 0.107410 | 0.222872 | 0.387027 | 0.184598 |
| memory | starting | random_forest | False | 1649 | 329 | 0.495645 | 1.278159 | 0.074672 | 0.243384 | 0.415328 | 0.060988 |
| memory | tuned | xgboost | True | 1649 | 329 | 0.527649 | 1.305813 | 0.034198 | 0.254511 | 0.439447 | -0.051237 |
| memory | starting | xgboost | False | 1649 | 329 | 0.625975 | 2.070684 | -1.428587 | 0.268030 | 0.484374 | -0.277176 |
| memory | reference | reference_median | False | 1649 | 329 | 0.425042 | 1.392760 | -0.098698 | 0.206121 | 0.472368 | -0.214643 |

Additional saved outputs: `tables/ml_tuning_results.csv` (resource/model/configuration CV scores) and `tables/ml_cv_summary.csv` (purged time-series versus grouped robustness CV). `n05_ml_metadata.json` records five timestamp-preserving purged time folds and GroupKFold as a nonselection check. Keep CV scores separate from held-out validation scores. The all-available-label sensitivity in Notebook 05 is supplementary, not the selected training rule.

Hybrid = max(ML, P95) per resource, using ML where P95 is unavailable. This fixed safeguard differs from the selected P99 baseline. Test and validation policy metrics are fully recorded in §7.2.1 above. `Hybrid_P99` is supplementary validation only; no final-test result exists for it. No saved final-test RMSE/MAE/R² comparison of every model is present in the authoritative test policy CSV; do not relabel validation model scores as test scores.

### 7.2.3 Feature Importance and Explainability

**Unavailable for the current final pipeline.** `ml_feature_manifest.json` lists 24 ordered features: current resource requests, execution count, request diversity, prior completed occurrence count, CPU/memory historical peak statistics and runtime statistics. This is a feature inventory, not measured importance. No current importance CSV, SHAP output, permutation analysis or importance figure was found. Notebook 05 and current scripts do not establish a ranked contribution claim. The older source map references superseded `reports/eval/subset/figures_ml/feature_importance_*.png`, but those files are not present in this checkout; they cannot substantiate this subsection.

Supported explainability is structural: history must complete before recommendation time, and Hybrid takes the maximum of a point prediction and the historical safeguard. This explains the rule, not learned feature influence. Retain the requested subsection with this evidence gap until the team chooses whether to authorize a separate explainability analysis. No new analysis or figure was generated here.

## 7.3 Alibaba GPU 2020 Results

### 7.3.1 Baseline Recommendation Results

Completed saved baseline, ML, Hybrid and final-test evaluation

Primary sources: `reports/results/alibaba_gpu_2020/alibaba_gpu_2020_results_and_analysis.md` §§0–8; `alibaba_gpu_2020_results_tasks1_6.md`; CSVs below; `ml/model_selection.json`, `ml/decision_manifest.json`, `final_test/run_record.json`.

461,900 eligible roles out of 1,254,108 accepted role occurrences. Chronological eligible train/validation/test counts 323,329 / 69,286 / 69,285; within-split next-eligible targets 220,832 / 42,069 / 44,053 for memory and 220,299 / 41,913 / 44,045 for CPU. These are current pipeline counts, superseding preliminary inspection estimates in older design documents. Results concern successful roles with complete sensor coverage for memory; missing CPU does not remove a memory-valid role.

Memory = maximum across role instances of each instance’s lifetime peak, GB per instance. CPU = maximum across role instances of each instance’s lifetime-average cpu_usage, percent_of_vcpu; **not a CPU peak**, not the average across replicas, and not total job CPU. `peak_cpu` is absent. Sources: `docs/data/alibaba_gpu_2020_adapter_results.md` §§5–7 and current result report units. No combined CPU-or-memory violation is reported.

Validation baseline selection is lexicographic memory violation, memory waste, CPU violation, CPU waste, with Request excluded from selection. P99@10 is selected; history fallback uses Request. All final comparison history policies use min_runs=10. Hybrid = max(ML, selected P99@10), unlike Google’s P95 floor. Train-only ML candidates are fixed settings, not Google-style tuned log-target models; HistGradientBoosting is selected for both by raw RMSE, then MAE, violation, shortfall, name. Dummy mean is a nonselectable reference. Validation ML/Hybrid scores reuse the model-selection split.

#### Alibaba baseline candidates — validation / selection

Source: `reports/results/alibaba_gpu_2020/baselines/validation_comparison.csv`. Output location: header names below and each row’s policy/resource/model keys. Status and split are specified in the heading. Definitions: primary metrics above; prediction metrics below.

| policy | min_runs | cpu_violation_pct | memory_violation_pct | average_cpu_utilization | average_memory_utilization | average_cpu_waste | average_memory_waste | average_cpu_shortfall | average_memory_shortfall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Request | 1 | 15.515473 | 4.737455 | 0.368045 | 0.256292 | 430.056943 | 22.255487 | 172.377359 | 0.826212 |
| Mean | 1 | 46.703887 | 46.516437 | 0.854634 | 0.844552 | 86.017571 | 3.194228 | 54.734876 | 0.810711 |
| P90 | 1 | 14.952401 | 16.104495 | 0.767092 | 0.779688 | 183.943422 | 4.312426 | 21.177237 | 0.418406 |
| P95 | 1 | 11.340157 | 11.901875 | 0.743280 | 0.755533 | 212.439621 | 4.800059 | 17.863005 | 0.375663 |
| P99 | 1 | 8.672727 | 8.742780 | 0.711939 | 0.720288 | 245.042915 | 5.506020 | 15.925387 | 0.344684 |
| Request | 3 | 15.515473 | 4.737455 | 0.368045 | 0.256292 | 430.056943 | 22.255487 | 172.377359 | 0.826212 |
| Mean | 3 | 44.224942 | 44.258242 | 0.825191 | 0.803842 | 108.026575 | 4.627518 | 54.709358 | 0.780935 |
| P90 | 3 | 12.852814 | 14.048349 | 0.738880 | 0.739880 | 205.382660 | 5.694429 | 21.394318 | 0.411172 |
| P95 | 3 | 9.281130 | 9.879008 | 0.715229 | 0.715838 | 233.795729 | 6.175189 | 18.098501 | 0.370784 |
| P99 | 3 | 6.651874 | 6.774585 | 0.684015 | 0.680689 | 266.331783 | 6.875533 | 16.174878 | 0.341572 |
| Request | 5 | 15.515473 | 4.737455 | 0.368045 | 0.256292 | 430.056943 | 22.255487 | 172.377359 | 0.826212 |
| Mean | 5 | 42.838737 | 42.653736 | 0.805153 | 0.779432 | 121.557154 | 5.525859 | 56.538948 | 0.762013 |
| P90 | 5 | 12.459142 | 13.211629 | 0.721754 | 0.717748 | 217.545768 | 6.522289 | 24.067099 | 0.429606 |
| P95 | 5 | 8.982893 | 9.108845 | 0.698509 | 0.693990 | 245.750982 | 6.994799 | 20.833509 | 0.390537 |
| P99 | 5 | 6.458617 | 6.099503 | 0.667618 | 0.659055 | 278.116038 | 7.688441 | 18.954953 | 0.362278 |
| Request | 10 | 15.515473 | 4.737455 | 0.368045 | 0.256292 | 430.056943 | 22.255487 | 172.377359 | 0.826212 |
| Mean | 10 | 40.844130 | 39.901115 | 0.776168 | 0.741901 | 142.564075 | 6.851180 | 59.664732 | 0.797101 |
| P90 | 10 | 12.251569 | 12.396301 | 0.697437 | 0.683364 | 235.442059 | 7.802820 | 28.713061 | 0.488651 |
| P95 | 10 | 8.999594 | 8.457534 | 0.675090 | 0.660382 | 263.084356 | 8.260064 | 25.721453 | 0.451071 |
| P99 | 10 | 6.618472 | 5.576553 | 0.644912 | 0.626029 | 294.955963 | 8.941158 | 23.993369 | 0.423667 |

### 7.3.2 ML and Hybrid Recommendation Results

#### Alibaba CPU and memory model candidates — validation / selection

Source: `reports/results/alibaba_gpu_2020/ml/candidate_models.csv`. Output location: header names below and each row’s policy/resource/model keys. Status and split are specified in the heading. Definitions: primary metrics above; prediction metrics below.

| resource | model | n_train | n_val | n_clipped_validation | mae | rmse | r2 | violation_pct | average_shortfall | selected |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cpu | dummy_mean | 220299 | 41913 | 0 | 566.228260 | 858.953806 | -0.048516 | 11.970033 | 190.730941 | False |
| cpu | decision_tree | 220299 | 41913 | 0 | 167.491769 | 519.172279 | 0.616948 | 55.591344 | 79.094343 | False |
| cpu | random_forest | 220299 | 41913 | 0 | 134.670213 | 425.971240 | 0.742133 | 53.978479 | 54.386433 | False |
| cpu | hist_gradient_boosting | 220299 | 41913 | 151 | 135.723501 | 412.940869 | 0.757668 | 41.908238 | 49.226306 | True |
| cpu | xgboost | 220299 | 41913 | 1 | 134.482223 | 415.038047 | 0.755200 | 45.348698 | 49.818194 | False |
| memory | dummy_mean | 220832 | 42069 | 0 | 9.228217 | 13.276163 | -0.029706 | 24.787849 | 3.486624 | False |
| memory | decision_tree | 220832 | 42069 | 0 | 3.619940 | 10.334961 | 0.375998 | 47.747748 | 1.414858 | False |
| memory | random_forest | 220832 | 42069 | 0 | 3.204646 | 9.161680 | 0.509636 | 46.376191 | 1.235032 | False |
| memory | hist_gradient_boosting | 220832 | 42069 | 376 | 3.142379 | 8.982769 | 0.528601 | 47.759633 | 1.239059 | True |
| memory | xgboost | 220832 | 42069 | 353 | 3.224062 | 9.087733 | 0.517520 | 50.010697 | 1.230351 | False |

#### Alibaba policies — validation / selection

Source: `reports/results/alibaba_gpu_2020/ml/validation_policy_comparison.csv`. Output location: header names below and each row’s policy/resource/model keys. Status and split are specified in the heading. Definitions: primary metrics above; prediction metrics below.

| policy | row_count | valid_cpu_violation_count | valid_memory_violation_count | cpu_violation_pct | memory_violation_pct | average_cpu_utilization | average_memory_utilization | average_cpu_waste | average_memory_waste | average_cpu_shortfall | average_memory_shortfall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Request | 42069 | 41913 | 42069 | 15.515473 | 4.737455 | 0.368045 | 0.256292 | 430.056943 | 22.255487 | 172.377359 | 0.826212 |
| Mean | 42069 | 41913 | 42069 | 40.844130 | 39.901115 | 0.776168 | 0.741901 | 142.564075 | 6.851180 | 59.664732 | 0.797101 |
| P90 | 42069 | 41913 | 42069 | 12.251569 | 12.396301 | 0.697437 | 0.683364 | 235.442059 | 7.802820 | 28.713061 | 0.488651 |
| P95 | 42069 | 41913 | 42069 | 8.999594 | 8.457534 | 0.675090 | 0.660382 | 263.084356 | 8.260064 | 25.721453 | 0.451071 |
| P99 | 42069 | 41913 | 42069 | 6.618472 | 5.576553 | 0.644912 | 0.626029 | 294.955963 | 8.941158 | 23.993369 | 0.423667 |
| ML | 42069 | 41913 | 42069 | 41.908238 | 47.759633 | 0.821489 | 0.853581 | 86.497195 | 1.903320 | 49.226306 | 1.239059 |
| Hybrid | 42069 | 41913 | 42069 | 4.602391 | 5.148684 | 0.626924 | 0.623725 | 305.621776 | 9.140566 | 12.995332 | 0.307365 |

#### Alibaba policies — saved final test

Source: `reports/results/alibaba_gpu_2020/final_test/final_test_policy_comparison.csv`. Output location: header names below and each row’s policy/resource/model keys. Status and split are specified in the heading. Definitions: primary metrics above; prediction metrics below.

| policy | row_count | valid_cpu_violation_count | valid_memory_violation_count | valid_cpu_utilization_count | valid_memory_utilization_count | cpu_violation_pct | memory_violation_pct | average_cpu_utilization | average_memory_utilization | average_cpu_waste | average_memory_waste | average_cpu_shortfall | average_memory_shortfall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Request | 44053 | 44045 | 44053 | 44045 | 44053 | 16.710183 | 3.164370 | 0.379797 | 0.253515 | 419.970913 | 22.313198 | 191.463032 | 0.661486 |
| Mean | 44053 | 44045 | 44053 | 44045 | 44053 | 41.829947 | 37.021315 | 0.788145 | 0.745055 | 138.752781 | 6.450900 | 81.051775 | 0.614283 |
| P90 | 44053 | 44045 | 44053 | 44045 | 44053 | 12.407765 | 9.888089 | 0.704164 | 0.682353 | 237.569508 | 7.440147 | 48.063104 | 0.301017 |
| P95 | 44053 | 44045 | 44053 | 44045 | 44053 | 9.097514 | 6.044991 | 0.681723 | 0.658849 | 266.947073 | 7.894859 | 45.267546 | 0.264165 |
| P99 | 44053 | 44045 | 44053 | 44045 | 44053 | 6.452492 | 3.443579 | 0.648675 | 0.620059 | 306.435275 | 8.667781 | 43.529385 | 0.232954 |
| ML | 44053 | 44045 | 44053 | 44042 | 44049 | 47.372006 | 44.768801 | 0.857457 | 0.841783 | 72.007092 | 1.327719 | 78.384134 | 1.045793 |
| Hybrid | 44053 | 44045 | 44053 | 44045 | 44053 | 3.766602 | 3.146210 | 0.629465 | 0.617031 | 326.823419 | 8.706855 | 20.539894 | 0.196647 |

Final record: clean commit `fe38ea0c07969a4cdceb3d1d08bbe08813232d5f` for ML lock and test; locked models refitted on train+validation; `prior_runs=0`, no defect rerun, test manifest hash matches ML manifest. `final_test/run_record.json` reports negative test predictions clipped: CPU 44, memory 18; Hybrid missing safeguards: zero for either resource. CPU utilization ML denominator 44,042, memory 44,049; violations use 44,045 / 44,053. The committed run record supports a recorded first test; it is not independent proof that no other experiment ever accessed test data.

Sensitivity artifacts: `baselines/sensitivity_validation.csv` and `final_test/final_test_sensitivity.csv` contain same-second successor exclusion/only, multi-instance subgroup and recurrence/group-weighted metrics. These are supplementary subgroup/weighting analyses, not additional independent test datasets. Exact rows and all metrics are available below.

#### Sensitivity — Alibaba validation

Source: `reports/results/alibaba_gpu_2020/baselines/sensitivity_validation.csv`. Output location: header names below and each row’s policy/resource/model keys. Status and split are specified in the heading. Definitions: primary metrics above; prediction metrics below.

| sensitivity | min_runs | policy | row_count | valid_cpu_violation_count | valid_memory_violation_count | valid_cpu_utilization_count | valid_memory_utilization_count | cpu_violation_pct | memory_violation_pct | average_cpu_utilization | average_memory_utilization | average_cpu_waste | average_memory_waste | average_cpu_shortfall | average_memory_shortfall | cpu_result_semantics | primary_resource | any_resource_metric_reported | cpu_usage_label | n_groups |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| occurrence_weighted | 10 | Request | 42069 | 41913 | 42069 | 41913 | 42069 | 15.515473 | 4.737455 | 0.368045 | 0.256292 | 430.056943 | 22.255487 | 172.377359 | 0.826212 | average_usage | memory | False | average_usage |  |
| occurrence_weighted | 10 | Mean | 42069 | 41913 | 42069 | 41913 | 42069 | 40.844130 | 39.901115 | 0.776168 | 0.741901 | 142.564075 | 6.851180 | 59.664732 | 0.797101 | average_usage | memory | False | average_usage |  |
| occurrence_weighted | 10 | P90 | 42069 | 41913 | 42069 | 41913 | 42069 | 12.251569 | 12.396301 | 0.697437 | 0.683364 | 235.442059 | 7.802820 | 28.713061 | 0.488651 | average_usage | memory | False | average_usage |  |
| occurrence_weighted | 10 | P95 | 42069 | 41913 | 42069 | 41913 | 42069 | 8.999594 | 8.457534 | 0.675090 | 0.660382 | 263.084356 | 8.260064 | 25.721453 | 0.451071 | average_usage | memory | False | average_usage |  |
| occurrence_weighted | 10 | P99 | 42069 | 41913 | 42069 | 41913 | 42069 | 6.618472 | 5.576553 | 0.644912 | 0.626029 | 294.955963 | 8.941158 | 23.993369 | 0.423667 | average_usage | memory | False | average_usage |  |
| same_second_excluded | 10 | Request | 41824 | 41668 | 41824 | 41668 | 41824 | 15.601901 | 4.748470 | 0.368243 | 0.256151 | 429.146139 | 22.283414 | 173.280338 | 0.828124 | average_usage | memory | False | average_usage |  |
| same_second_excluded | 10 | Mean | 41824 | 41668 | 41824 | 41668 | 41824 | 40.745896 | 39.824024 | 0.775075 | 0.740741 | 143.328873 | 6.887690 | 59.945025 | 0.797938 | average_usage | memory | False | average_usage |  |
| same_second_excluded | 10 | P90 | 41824 | 41668 | 41824 | 41668 | 41824 | 12.278007 | 12.430662 | 0.696142 | 0.682197 | 236.686693 | 7.841456 | 28.865243 | 0.488646 | average_usage | memory | False | average_usage |  |
| same_second_excluded | 10 | P95 | 41824 | 41668 | 41824 | 41668 | 41824 | 9.033311 | 8.483168 | 0.673744 | 0.659194 | 264.452872 | 8.299392 | 25.862917 | 0.451221 | average_usage | memory | False | average_usage |  |
| same_second_excluded | 10 | P99 | 41824 | 41668 | 41824 | 41668 | 41824 | 6.647787 | 5.602047 | 0.643501 | 0.624963 | 296.472825 | 8.981051 | 24.125595 | 0.423726 | average_usage | memory | False | average_usage |  |
| same_second_only | 10 | Request | 245 | 245 | 245 | 245 | 245 | 0.816327 | 2.857143 | 0.334384 | 0.280508 | 584.960527 | 17.488054 | 18.804524 | 0.499745 | average_usage | memory | False | average_usage |  |
| same_second_only | 10 | Mean | 245 | 245 | 245 | 245 | 245 | 57.551020 | 53.061224 | 0.961972 | 0.939960 | 12.492316 | 0.618598 | 11.994416 | 0.654249 | average_usage | memory | False | average_usage |  |
| same_second_only | 10 | P90 | 245 | 245 | 245 | 245 | 245 | 7.755102 | 6.530612 | 0.917752 | 0.882593 | 23.762812 | 1.207228 | 2.830866 | 0.489490 | average_usage | memory | False | average_usage |  |
| same_second_only | 10 | P95 | 245 | 245 | 245 | 245 | 245 | 3.265306 | 4.081633 | 0.903990 | 0.863231 | 30.336070 | 1.546424 | 1.662274 | 0.425528 | average_usage | memory | False | average_usage |  |
| same_second_only | 10 | P99 | 245 | 245 | 245 | 245 | 245 | 1.632653 | 1.224490 | 0.885014 | 0.808024 | 36.977941 | 2.131025 | 1.505275 | 0.413580 | average_usage | memory | False | average_usage |  |
| multi_instance | 10 | Request | 889 | 888 | 889 | 888 | 889 | 14.301802 | 13.385827 | 0.344093 | 0.339446 | 656.108264 | 25.961723 | 214.613116 | 1.275343 | average_usage | memory | False | average_usage |  |
| multi_instance | 10 | Mean | 889 | 888 | 889 | 888 | 889 | 30.855856 | 28.346457 | 0.653183 | 0.629102 | 307.353740 | 12.174996 | 126.374730 | 1.012625 | average_usage | memory | False | average_usage |  |
| multi_instance | 10 | P90 | 889 | 888 | 889 | 888 | 889 | 14.639640 | 14.735658 | 0.607672 | 0.591567 | 369.475159 | 12.798979 | 102.892039 | 0.842480 | average_usage | memory | False | average_usage |  |
| multi_instance | 10 | P95 | 889 | 888 | 889 | 888 | 889 | 13.400901 | 12.260967 | 0.594707 | 0.574451 | 377.829950 | 13.171213 | 100.672695 | 0.810413 | average_usage | memory | False | average_usage |  |
| multi_instance | 10 | P99 | 889 | 888 | 889 | 888 | 889 | 12.162162 | 10.911136 | 0.578482 | 0.551523 | 387.061940 | 13.663847 | 99.341214 | 0.773181 | average_usage | memory | False | average_usage |  |
| group_weighted | 10 | Request | 42069 |  |  |  |  | 15.653217 | 7.123247 | 0.424931 | 0.266271 | 372.214180 | 22.985029 | 179.206598 | 1.198284 | average_usage | memory | False | average_usage | 9712 |
| group_weighted | 10 | Mean | 42069 |  |  |  |  | 30.980276 | 30.460970 | 0.669324 | 0.583004 | 216.887029 | 12.273276 | 74.921777 | 1.092558 | average_usage | memory | False | average_usage | 9712 |
| group_weighted | 10 | P90 | 42069 |  |  |  |  | 11.273722 | 12.771695 | 0.614757 | 0.542237 | 299.289502 | 13.123381 | 47.008275 | 0.816296 | average_usage | memory | False | average_usage | 9712 |
| group_weighted | 10 | P95 | 42069 |  |  |  |  | 9.012287 | 9.864430 | 0.599867 | 0.526062 | 322.451227 | 13.519825 | 44.293716 | 0.783091 | average_usage | memory | False | average_usage | 9712 |
| group_weighted | 10 | P99 | 42069 |  |  |  |  | 7.345073 | 7.691674 | 0.581918 | 0.503454 | 349.305110 | 14.092557 | 42.733272 | 0.758854 | average_usage | memory | False | average_usage | 9712 |

#### Sensitivity — Alibaba final test

Source: `reports/results/alibaba_gpu_2020/final_test/final_test_sensitivity.csv`. Output location: header names below and each row’s policy/resource/model keys. Status and split are specified in the heading. Definitions: primary metrics above; prediction metrics below.

| sensitivity | policy | row_count | valid_cpu_violation_count | valid_memory_violation_count | valid_cpu_utilization_count | valid_memory_utilization_count | cpu_violation_pct | memory_violation_pct | average_cpu_utilization | average_memory_utilization | average_cpu_waste | average_memory_waste | average_cpu_shortfall | average_memory_shortfall | cpu_result_semantics | primary_resource | any_resource_metric_reported | n_groups |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| occurrence_weighted | Request | 44053 | 44045 | 44053 | 44045 | 44053 | 16.710183 | 3.164370 | 0.379797 | 0.253515 | 419.970913 | 22.313198 | 191.463032 | 0.661486 | average_usage | memory | False |  |
| occurrence_weighted | Mean | 44053 | 44045 | 44053 | 44045 | 44053 | 41.829947 | 37.021315 | 0.788145 | 0.745055 | 138.752781 | 6.450900 | 81.051775 | 0.614283 | average_usage | memory | False |  |
| occurrence_weighted | P90 | 44053 | 44045 | 44053 | 44045 | 44053 | 12.407765 | 9.888089 | 0.704164 | 0.682353 | 237.569508 | 7.440147 | 48.063104 | 0.301017 | average_usage | memory | False |  |
| occurrence_weighted | P95 | 44053 | 44045 | 44053 | 44045 | 44053 | 9.097514 | 6.044991 | 0.681723 | 0.658849 | 266.947073 | 7.894859 | 45.267546 | 0.264165 | average_usage | memory | False |  |
| occurrence_weighted | P99 | 44053 | 44045 | 44053 | 44045 | 44053 | 6.452492 | 3.443579 | 0.648675 | 0.620059 | 306.435275 | 8.667781 | 43.529385 | 0.232954 | average_usage | memory | False |  |
| occurrence_weighted | ML | 44053 | 44045 | 44053 | 44042 | 44049 | 47.372006 | 44.768801 | 0.857457 | 0.841783 | 72.007092 | 1.327719 | 78.384134 | 1.045793 | average_usage | memory | False |  |
| occurrence_weighted | Hybrid | 44053 | 44045 | 44053 | 44045 | 44053 | 3.766602 | 3.146210 | 0.629465 | 0.617031 | 326.823419 | 8.706855 | 20.539894 | 0.196647 | average_usage | memory | False |  |
| same_second_excluded | Request | 43802 | 43794 | 43802 | 43794 | 43802 | 16.805955 | 3.171088 | 0.380210 | 0.253126 | 418.878506 | 22.349306 | 192.560379 | 0.664803 | average_usage | memory | False |  |
| same_second_excluded | Mean | 43802 | 43794 | 43802 | 43794 | 43802 | 41.797963 | 36.977764 | 0.787432 | 0.744365 | 139.317041 | 6.473666 | 81.484554 | 0.616536 | average_usage | memory | False |  |
| same_second_excluded | P90 | 43802 | 43794 | 43802 | 43794 | 43802 | 12.421793 | 9.919638 | 0.703221 | 0.681650 | 238.641435 | 7.463499 | 48.332815 | 0.302347 | average_usage | memory | False |  |
| same_second_excluded | P95 | 43802 | 43794 | 43802 | 43794 | 43802 | 9.124538 | 6.065933 | 0.680719 | 0.658126 | 268.161182 | 7.917708 | 45.525542 | 0.265544 | average_usage | memory | False |  |
| same_second_excluded | P99 | 43802 | 43794 | 43802 | 43794 | 43802 | 6.482623 | 3.456463 | 0.647587 | 0.619349 | 307.852369 | 8.692160 | 43.778386 | 0.234260 | average_usage | memory | False |  |
| same_second_excluded | ML | 43802 | 43794 | 43802 | 43791 | 43798 | 47.232498 | 44.726268 | 0.856835 | 0.841347 | 72.371812 | 1.331003 | 78.724052 | 1.050113 | average_usage | memory | False |  |
| same_second_excluded | Hybrid | 43802 | 43794 | 43802 | 43794 | 43802 | 3.781340 | 3.157390 | 0.628267 | 0.616303 | 328.357365 | 8.731458 | 20.657133 | 0.197744 | average_usage | memory | False |  |
| same_second_only | Request | 251 | 251 | 251 | 251 | 251 | 0 | 1.992032 | 0.307728 | 0.321312 | 610.571928 | 16.011878 | 0 | 0.082556 | average_usage | memory | False |  |
| same_second_only | Mean | 251 | 251 | 251 | 251 | 251 | 47.410359 | 44.621514 | 0.912557 | 0.865438 | 40.301843 | 2.477965 | 5.541268 | 0.221023 | average_usage | memory | False |  |
| same_second_only | P90 | 251 | 251 | 251 | 251 | 251 | 9.960159 | 4.382470 | 0.868766 | 0.805041 | 50.541734 | 3.365008 | 1.004443 | 0.068924 | average_usage | memory | False |  |
| same_second_only | P95 | 251 | 251 | 251 | 251 | 251 | 4.382470 | 2.390438 | 0.856813 | 0.785011 | 55.111501 | 3.907450 | 0.252901 | 0.023455 | average_usage | memory | False |  |
| same_second_only | P99 | 251 | 251 | 251 | 251 | 251 | 1.195219 | 1.195219 | 0.838511 | 0.743947 | 59.183476 | 4.413408 | 0.084160 | 0.005171 | average_usage | memory | False |  |
| same_second_only | ML | 251 | 251 | 251 | 251 | 251 | 71.713147 | 52.191235 | 0.965914 | 0.917818 | 8.371501 | 0.754619 | 19.075859 | 0.291970 | average_usage | memory | False |  |
| same_second_only | Hybrid | 251 | 251 | 251 | 251 | 251 | 1.195219 | 1.195219 | 0.838511 | 0.743947 | 59.183476 | 4.413408 | 0.084160 | 0.005171 | average_usage | memory | False |  |
| multi_instance | Request | 595 | 595 | 595 | 595 | 595 | 14.789916 | 13.445378 | 0.343835 | 0.331009 | 630.342064 | 26.741680 | 186.226479 | 1.620913 | average_usage | memory | False |  |
| multi_instance | Mean | 595 | 595 | 595 | 595 | 595 | 32.941176 | 28.403361 | 0.715792 | 0.673795 | 240.492781 | 10.657478 | 89.870551 | 1.223865 | average_usage | memory | False |  |
| multi_instance | P90 | 595 | 595 | 595 | 595 | 595 | 15.798319 | 10.924370 | 0.659468 | 0.622378 | 331.815226 | 11.387300 | 76.502110 | 1.085672 | average_usage | memory | False |  |
| multi_instance | P95 | 595 | 595 | 595 | 595 | 595 | 13.445378 | 8.739496 | 0.639131 | 0.598990 | 348.623342 | 11.884423 | 75.114819 | 1.070232 | average_usage | memory | False |  |
| multi_instance | P99 | 595 | 595 | 595 | 595 | 595 | 12.100840 | 8.067227 | 0.615734 | 0.569701 | 369.630278 | 12.417323 | 73.680764 | 1.063248 | average_usage | memory | False |  |
| multi_instance | ML | 595 | 595 | 595 | 594 | 595 | 31.596639 | 40.840336 | 0.832642 | 0.879062 | 76.810052 | 1.139446 | 61.612667 | 0.806965 | average_usage | memory | False |  |
| multi_instance | Hybrid | 595 | 595 | 595 | 595 | 595 | 5.546218 | 5.714286 | 0.595016 | 0.564230 | 377.934985 | 12.561526 | 35.393008 | 0.264302 | average_usage | memory | False |  |
| group_weighted | Request | 44053 |  |  |  |  | 21.216760 | 4.111972 | 0.460739 | 0.281964 | 362.674679 | 22.233622 | 195.034605 | 1.017021 | average_usage | memory | False | 9720 |
| group_weighted | Mean | 44053 |  |  |  |  | 36.881892 | 27.598035 | 0.721266 | 0.622870 | 195.310341 | 10.701615 | 89.291503 | 0.860636 | average_usage | memory | False | 9720 |
| group_weighted | P90 | 44053 |  |  |  |  | 15.730275 | 9.234626 | 0.658788 | 0.577736 | 283.950627 | 11.534822 | 59.587573 | 0.597694 | average_usage | memory | False | 9720 |
| group_weighted | P95 | 44053 |  |  |  |  | 13.274324 | 6.236901 | 0.642943 | 0.560695 | 308.664444 | 11.940020 | 57.049134 | 0.563863 | average_usage | memory | False | 9720 |
| group_weighted | P99 | 44053 |  |  |  |  | 11.384634 | 4.168754 | 0.621302 | 0.534196 | 339.778670 | 12.607378 | 55.462326 | 0.534916 | average_usage | memory | False | 9720 |
| group_weighted | ML | 44053 |  |  |  |  | 42.733106 | 41.226514 | 0.812587 | 0.805971 | 96.411405 | 1.556925 | 80.578300 | 1.601634 | average_usage | memory | False | 9720 |
| group_weighted | Hybrid | 44053 |  |  |  |  | 4.084581 | 3.709276 | 0.566033 | 0.531438 | 378.498123 | 12.668642 | 22.816291 | 0.443584 | average_usage | memory | False | 9720 |

#### Sensitivity — Google validation

Source: `reports/results/google_subset/tables/validation_policy_comparison_target_period_sensitivity.csv`. Output location: header names below and each row’s policy/resource/model keys. Status and split are specified in the heading. Definitions: primary metrics above; prediction metrics below.

| policy | population | n_common_occurrences | result_status | row_count | valid_cpu_violation_count | valid_memory_violation_count | valid_any_resource_violation_count | valid_cpu_utilization_count | valid_memory_utilization_count | cpu_violation_pct | memory_violation_pct | any_resource_violation_pct | average_cpu_utilization | average_memory_utilization | average_cpu_waste | average_memory_waste | average_cpu_shortfall | average_memory_shortfall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Request | targets_within_validation_period | 225 | preliminary | 225 | 222 | 222 | 222 | 218 | 222 | 52.702703 | 40.540541 | 57.657658 | 0.630986 | 0.550247 | 0.914486 | 0.458779 | 2.250134 | 0.320531 |
| Mean | targets_within_validation_period | 225 | preliminary | 225 | 224 | 224 | 224 | 224 | 224 | 31.250000 | 35.267857 | 40.178571 | 0.462710 | 0.504067 | 2.085764 | 0.444397 | 1.595128 | 0.213317 |
| P90 | targets_within_validation_period | 225 | preliminary | 225 | 224 | 224 | 224 | 224 | 224 | 20.089286 | 20.982143 | 26.785714 | 0.357742 | 0.391995 | 5.971058 | 1.249096 | 0.905727 | 0.130024 |
| P95 | targets_within_validation_period | 225 | preliminary | 225 | 224 | 224 | 224 | 224 | 224 | 15.625000 | 19.196429 | 23.214286 | 0.308962 | 0.355092 | 10.743086 | 2.461662 | 0.512022 | 0.081327 |
| P99 | targets_within_validation_period | 225 | preliminary | 225 | 224 | 224 | 224 | 224 | 224 | 12.946429 | 15.625000 | 18.303571 | 0.257725 | 0.316483 | 25.039882 | 4.493954 | 0.380569 | 0.057829 |
| ML | targets_within_validation_period | 225 | preliminary | 225 | 225 | 225 | 225 | 225 | 225 | 32.444444 | 26.222222 | 36.888889 | 0.466405 | 0.437478 | 0.504970 | 0.173827 | 2.136009 | 0.311654 |
| Hybrid | targets_within_validation_period | 225 | preliminary | 225 | 225 | 225 | 225 | 225 | 225 | 12.888889 | 14.222222 | 17.777778 | 0.272111 | 0.289015 | 10.734024 | 2.457773 | 0.498104 | 0.108319 |
| Hybrid_P99 | targets_within_validation_period | 225 | preliminary | 225 | 225 | 225 | 225 | 225 | 225 | 10.666667 | 12 | 14.222222 | 0.224157 | 0.258640 | 24.965773 | 4.480163 | 0.367821 | 0.085151 |

## 7.4 Analysis Across Datasets

### Other saved supporting experiments — scope boundaries

| Dataset / evidence | Verified saved finding and exact location | Split / metric | Status and caveat |
| --- | --- | --- | --- |
| Google earlier full-trace experiments | `reports/eval/GoogleCluster2019/summary_1d.csv`, `summary_1w.csv`, `tier=all`: Request/P95/P99 any-resource rates 0.9271647075 / 0.3089967881 / 0.2573670129 (1d); 0.9458868117 / 0.2287205909 / 0.1605130878 (1w) | Earlier notebook execution evaluation; ratios, not percent. See `notebooks/GoogleCluster2019/Experiments_1DayData.ipynb` cell 7 and `Experiments_1WeekData.ipynb` cells 3,7 | Supporting historical baseline results. `split=1d/1w` names dataset windows, not validation/test. Notebook code determines temporal holdout; waste is a sum, unlike primary average waste. Do not pool with final occurrence results or claim ML/Hybrid completion. |
| Azure Resource Central | `reports/eval/resource-central/tables/resource_central_baseline_metadata.csv`, sole row: 100,000 CPU readings / 100,000 VMs; bucket_accuracy=0.8711; mean P95-minus-mean CPU=6.9770170673 | Descriptive same-sample CPU bucket agreement; no temporal holdout in that metadata | Supporting CPU-only prototype. `notebooks/resource-central/resource_central.ipynb` cell 6 limits first CPU file to 100,000 readings; cells 7/23 derive percentiles/global thresholds on same sample. Cell 26 has a separate random-split RF classifier prototype; metadata bucket_accuracy is not that model’s held-out score. No verified recurrence-based memory/Hybrid final evaluation. One reading per VM makes per-VM percentile claims especially limited. |
| Azure LLM / Splitwise | `reports/eval/splitwise/azure_llm_10s_test_summary.csv`, code mean/P95/P99 violation_rate=0.3333333333 / 0.0416666667 / 0; conversation mean/P95/P99=0.0140845070 / 0 / 0 | Saved test; 24 code and 71 conversation 10-second token-demand windows; `notebooks/splitwise/azure_llm_inference.ipynb` cells 5,8 | Completed fixed-capacity baseline experiment, not CPU/memory validation. Violation compares TotalTokens to fixed train-derived capacity; utilization actual/capacity is unbounded. No current saved ML/Hybrid evaluation. Some notebook output paths differ from committed CSV location and plotting uses an author-specific absolute path. |
| ModServe | `reports/eval/modserve/tables/modserve_test_baseline_summary.csv`: Fixed Monolith / Fixed Decoupled / Reactive Decoupled underprovision_rate=0.0472222222 / 0.0527777778 / 0.2847222222; avg provisioned units=19 / 19 / 5.3763888889 | Saved test, 720 five-minute windows; `modserve_val_baseline_summary.csv` separately holds validation; notebook `notebooks/modserve/02_modserve_5min_windows_and_baselines.ipynb` cell 13 defines training P95 fixed levels | Completed capacity replay support. Required/provisioned image/text units depend on calibrated capacities, not measured per-role CPU/memory peaks or real serving latency. Fixed/reactive baselines are not TraceAdvisor ML/Hybrid. |
| Alibaba 2018 and Azure canonical adapter concepts | `docs/data/old_dataset_semantics_alibaba2018_azure.md`, `old_adapter_analysis_alibaba2018_azure.md`, `traceadvisor_external_dataset_capability_matrix.csv` | Integration/feasibility evidence, not authoritative final test | No saved completed baseline+ML+Hybrid recurring-role final evaluation found. Do not equate an adapter or feasibility analysis with full validation. |

Cross-platform comparability: compare the qualitative history/ML/Hybrid trade-off and implementation capability. Do not compare raw CPU/memory waste, RMSE or R² as rankings across Google and Alibaba: different units, populations, target scopes, recurrence keys, filtering, selection criteria and Hybrid safeguards. Even percentage violation rates describe different events and cannot be pooled into a common accuracy score. Within each dataset’s fixed split, the policies are substantially comparable with explicit denominator caveats. Alibaba targets are split-isolated; Google validation targets are not.

## 7.5 Discussion of Findings

### Findings supported by the primary saved tables

- Google final test: Hybrid any-resource violation 12.355212% versus P95 17.374517% and selected P99 14.671815%; CPU waste 7.636559 versus P95 7.616189 and P99 17.482997. P99 has lower CPU violation (9.266409%) than Hybrid (10.810811%). Use resource-specific qualifications, not “Hybrid wins every metric.” Source: Google final policy table above; status: saved test with provenance limitations below.
- Alibaba final test: Hybrid memory violation 3.146210% versus P99 3.443579%; memory waste 8.706855 versus 8.667781 GB. Request is 3.164370%, numerically close but not an exact tie. Hybrid CPU violation 3.766602% versus P99 6.452492%. Source: Alibaba final table; CPU is average-usage sizing only.
- ML-only has lowest average waste in each saved final table, but high violation rates; lower average waste alone does not establish a good recommendation. Model accuracy and provisioning reliability measure different goals.
- min_runs affects fallback: Google P99 validation any-resource violation rises from 21.951220%@1 to 30.981595%@10; Alibaba P99 memory violation falls from 8.742780%@1 to 5.576553%@10 (check exact source CSV for full precision). Requests differ between datasets, explaining why more fallback has different effects. These are validation candidate observations, not causal experiments or test tuning.

### Leakage, artifact integrity and incomplete evidence

Google target-period issue is verified in `docs/data/google_subset_pipeline_analysis.md` F1–F4 and N04 target-before-split code. Of 330 validation rows with a target, 329 have both resource targets and are scored; 104 scored rows target test-period outcomes. The 225 in-period rows give P99 any-resource violation 18.30% versus 21.95% overall; Hybrid 17.78% versus 17.93%. The saved sensitivity table above is authoritative. This is contamination of validation-based selection, so the final evaluation is not a completely untouched test-period outcome study even though the separate test policy scoring was frozen and recorded once. The baseline selection remains P99@1 in the saved sensitivity; that does not prove all ML tuning choices would remain unchanged after leakage correction. Do not repeat the source prose’s blanket “optimistic” characterization: removing cross-period rows lowers P99’s violation rate, while ML moves differently. The direction depends on the metric/population.

N05 explicitly restricts primary training labels to train-period target starts and final refit labels to validation end; do not apply the older analysis’s “all training labels leak” finding to the selected current model. Boundary eligibility is by target start, not proof that every target’s lifetime peak was observable by that timestamp.

Read-only SHA-256 audit of the Google final manifest’s 13 input paths in this workspace:

| Input path | Current bytes versus saved final manifest |
| --- | --- |
| `data/processed/google_subset_v1/val_occurrences.parquet` | Mismatch |
| `data/processed/google_subset_v1/test_occurrences.parquet` | Mismatch |
| `data/processed/google_subset_v1/metadata.json` | Match |
| `data/processed/google_subset_v1/baseline_validation_comparison.csv` | Match |
| `data/processed/google_subset_v1/ml_metadata.json` | Mismatch |
| `data/processed/google_subset_v1/ml_feature_manifest.json` | Match |
| `data/processed/google_subset_v1/val_ml_predictions.parquet` | Mismatch |
| `data/processed/google_subset_v1/test_ml_predictions.parquet` | Mismatch |
| `data/processed/google_subset_v1/n05_locked_models/cpu_random_forest.joblib` | Mismatch |
| `data/processed/google_subset_v1/n05_locked_models/memory_random_forest.joblib` | Mismatch |
| `src/evaluation/evaluator.py` | Match |
| `src/evaluation/metrics.py` | Match |
| `src/policies/hybrid.py` | Match |

Eight local Google inputs differ from the frozen final manifest, including the local models and prediction/occurrence Parquets. Five match. This does not invalidate the committed summary by itself, but **the current workspace inputs cannot reproduce or authenticate that frozen run as-is**. The committed manifest’s own hash matches `final_test_run_metadata.json`. Do not compute explanations from the current local models and attribute them to the saved final run without resolving model provenance. `n05_ml_metadata.json` is a report copy, not the same path as local `ml_metadata.json`.

Alibaba integrity: all report-folder files present and listed in `ml/SHA256SUMS` and `final_test/SHA256SUMS` match their saved hashes; ML manifest hash also matches the final run record. Model binaries and row-level prediction Parquets are absent from those report copies by design; checksums alone do not verify unavailable files. Full canonical raw-data reconciliation is documented in `docs/data/alibaba_gpu_2020_adapter_results.md`, not independently rerun here. No expensive rebuild or environment reproduction was attempted.

Other limitations: small Google scoring populations and Kaggle sampling; abnormal Google execution endings remain in its reference pipeline; Alibaba selection excludes failed/incomplete jobs and missing/partial sensor coverage, with most eligible roles single-instance. Missing Alibaba CPU must remain excluded resource-by-resource, never zero-filled or interpreted as CPU peak. Old inspection/design documents contain preliminary counts (including 42,104 validation / 44,087 test) and stale future-work status; current target metadata and final tables supersede those counts. No saved confidence intervals, repeated seeds, online deployment benefit, monetary saving, measured runtime/throughput benchmark or current learned feature-importance evidence supports such claims.

### Existing figures and recommended chapter visuals (no figures generated)

| Priority / subsection | Reuse or recommended table | Source / caveats |
| --- | --- | --- |
| 1 — 7.2.1 baseline comparison | Recommended final-test table of Request/Mean/P90/P95/P99: resource and any-resource violation, average waste, valid counts; keep a separate validation selection table | Google CSVs above. Existing `reports/results/google_subset/figures/fig_google_baseline_candidates.png` shows validation candidates, not final test. |
| 2 — 7.2.2 ML and Hybrid | Recommended two tables: validation CPU/memory DT/RF/XGBoost model accuracy; final-test Request/P95/P99/ML/Hybrid provisioning performance | Existing `reports/results/google_subset/figures/fig_google_test_tradeoff.png` and `fig_google_val_vs_test.png`. Separate split panels/captions; indicate leakage and differing denominators. |
| 3 — 7.2.3 importance | No current reusable feature-importance figure | Use a feature-group inventory and explain the Hybrid maximum rule if desired; do not fabricate a ranking or reuse superseded missing figures. New importance work requires resolving frozen-model provenance and separate authorization. |
| 4 — 7.4 cross-platform | Recommended semantic comparison table and separate dataset panels for policies | Existing `reports/results/alibaba_gpu_2020/figures/fig_alibaba_test_tradeoff.png`, `fig_alibaba_ml_candidates.png`, `fig_alibaba_baseline_candidates.png`, `fig_alibaba_val_vs_test.png`. Label CPU average usage and GB memory; no pooled resource-unit axis or shared CPU safety ranking. |
| Supporting only | Existing ModServe, Splitwise and Resource Central plots in `reports/eval/{modserve,splitwise,resource-central}/figures/` | Use only if prototype scope is explicitly useful; they do not extend the main full-validation claim. |

The seven primary Google/Alibaba figure files are present. `reports/results/make_results_figures.py` is the source-table-to-figure mapping; it was not run. Figures are existing artifacts and were not independently regenerated. The two Google figures integrated into Chapter 7 were subsequently visually inspected during the formatting pass; the remaining figures were not visually audited. Primary CSV tables take precedence over figure labels and prose. In `googlepipeline_finalrun.md`, P95 17.38% and Request 54.48% in some prose are inconsistent with direct two-decimal rounding of the CSV (17.37%, 54.47%); use CSV values. Existing `docs/project_report/chapter_7_results_and_discussion/ch7_source_map.md` is a prior source map retained unchanged; this audit uses the user-requested new path.

### Clarifications before drafting

1. Decide whether §7.2.3 should report the lack of measured importance and describe structural explainability, or whether to authorize a separate importance experiment after recovering the frozen model artifacts. The present evidence does not support ranked feature claims.
2. Decide how to present Google’s contamination: retain saved results with an explicit limitation, or authorize a separate corrected experiment later. A saved one-time test should not be silently replaced or described as entirely uncontaminated.
3. Recover matching Google frozen inputs/model files if full reproduction or explanations of the final model are required. Current summary tables can be cited as saved results, with this audit’s verification boundary.
4. Keep Alibaba GPU 2020 as the completed second recurring-workload evaluation; label Azure/ModServe/Splitwise as supporting prototypes if included. “Cross-platform validation” does not establish identical CPU/memory measurement tasks.

### Chapter 7 figure integration and publication layout

The chapter now references the existing Google baseline candidate figure as Figure 7.1 in §7.2.1 (validation) and the Google test trade-off figure as Figure 7.2 in §7.2.2 (final test), using relative Markdown image paths without copying or modifying images. Captions appear below figures; Table 7.1–7.5 captions remain above tables. The former final paragraph listing optional figures has been removed from §7.5; the complete seven-figure inventory remains in the existing visuals table above. The other Google and Alibaba figures remain optional, and no feature-importance figure is supported.

Verification: visually inspected both integrated PNGs and read `reports/results/make_results_figures.py` without executing it. `google_figures()` maps Figure 7.1 to `tables/baseline_validation_comparison.csv` (`average_cpu_waste`, `any_resource_violation_pct`, selection P99@1) and Figure 7.2 to `tables/final_test_policy_comparison.csv` (`average_cpu_waste` / `cpu_violation_pct` and `average_memory_waste` / `memory_violation_pct`). The visible axes, selected candidate, policy positions and resource-specific ordering agree with these saved tables. Figure 7.1 is validation evidence and must not be interpreted as a plot of Table 7.2’s final-test values. Figure 7.2 shows CPU and memory violations separately, not the any-resource rate used in the chapter’s headline comparison. This inspection establishes consistency, not independent regeneration of the image coordinates or experiments.

Table 7.3 retains its seven columns and all original values; paired CPU / memory entries are defined in its caption. It is readable in a wide GitHub Markdown view but likely too wide for a single IEEE column. Tables 7.3 and 7.5 are both candidates for full-width `table*` environments during IEEE LaTeX conversion. Preserve their current Markdown structure; use wrapped headers and explicit CPU/memory pair labels where applicable. Figure 7.2’s side-by-side panels also favor a full-width `figure*` so axis and policy labels remain legible. Italicized captions are acceptable in the Markdown draft; apply IEEE caption styling during LaTeX conversion, keeping table captions above tables and figure captions below figures. Actual IEEE two-column typesetting has not been performed in this pass. No numerical findings, original chapter headings or evaluation artifacts were changed.

### Revised Table of Contents and reporting traceability

Current chapter order: §7.1 preliminary Azure, §7.2 Google with §7.2.1–7.2.3, §7.3 Alibaba with §7.3.1–7.3.2, §7.4 cross-dataset analysis/supporting experiments, §7.5 discussion/limitations. Historical audit notes above should be interpreted using this current mapping. Google tables are now 7.2 (baselines) and 7.3 (ML/Hybrid); their data rows and both existing image paths are unchanged. Figures remain 7.1 (Google validation) and 7.2 (Google final test). Discussion references now point to §7.5. Table 7.5 is the unchanged semantic comparison, formerly Table 7.3.

New Table 7.4 transcribes all seven policies from `reports/results/alibaba_gpu_2020/ml/validation_policy_comparison.csv` and `final_test/final_test_policy_comparison.csv`: `cpu_violation_pct`, `memory_violation_pct`, and `average_memory_waste`, rounded to two/two/three decimals. Validation counts: memory 42,069, CPU 41,913; final test: memory 44,053, CPU 44,045. Baseline prose P99@10 5.58%/8.941 GB versus Request 4.74%/22.255 GB comes from those validation rows, consistent with `baselines/validation_comparison.csv`. The new validation Hybrid 4.60% CPU / 5.15% memory and ML 41.91% / 47.76% come from the validation policy CSV. Selected HistGradientBoosting validation RMSE CPU 412.94 / memory 8.98 and R² 0.758 / 0.529 are in `ml/model_selection.json` (`validation_metrics`) and `ml/candidate_models.csv`; they are not final-test regression scores. Existing Alibaba final-test prose is retained under its resource definitions, baseline and ML/Hybrid interpretation.

Main chapter provenance links are omitted; source files remain documented here. Relative image references remain in the report for rendering. Publication candidates: Tables 7.3 and 7.5 for full-width `table*`; review the longer Table 7.4 for page placement as well. IEEE caption styling belongs to later LaTeX conversion. No experiments or figures were regenerated. Remaining evidence gaps are unchanged: Google validation leakage and eight local frozen-input mismatches; missing verified feature importance; no equivalent complete CPU/memory/ML/Hybrid study for Azure, ModServe or Splitwise.
