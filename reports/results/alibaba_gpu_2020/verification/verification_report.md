# Alibaba GPU 2020 Verification Report

- Dataset: `alibaba_gpu_v2020`
- Schema: `0.2.0`
- Result: **PASS**
- Checks: 55 passed, 0 failed
- Generated: `2026-11-15T21:34:42Z`
- Decision manifest SHA-256: `d36964c09c903af646f29929d363d0ccb6ccf60674f31054ed8dfac9dff527ac`
- Final run ID: `4fdc7e96-789b-43a9-990f-20f189e9598b`
- Final run code commit: `ea6aa08458aace364cd33529ce77de894bcd76ad`

## Verification checks

| Check | Result | Detail |
|---|---|---|
| `task3_canonical.sha256` | PASS | 5 checksums match |
| `task4_targets.sha256` | PASS | 4 checksums match |
| `task6_baselines.sha256` | PASS | 8 checksums match |
| `task7_pr1_ml.sha256` | PASS | 9 checksums match |
| `task7_pr2_final_test.sha256` | PASS | 5 checksums match |
| `task7_pr1.published_evidence` | PASS | 8 published files match |
| `task7_pr2.published_evidence` | PASS | 5 published files match |
| `task3.dataset_id` | PASS | expected 'alibaba_gpu_v2020', found 'alibaba_gpu_v2020' |
| `task3.schema_version` | PASS | expected '0.2.0', found '0.2.0' |
| `task4.dataset_id` | PASS | expected 'alibaba_gpu_v2020', found 'alibaba_gpu_v2020' |
| `task4.schema_version` | PASS | expected '0.2.0', found '0.2.0' |
| `task6.dataset_id` | PASS | expected 'alibaba_gpu_v2020', found 'alibaba_gpu_v2020' |
| `task6.schema_version` | PASS | expected '0.2.0', found '0.2.0' |
| `task7_pr1.dataset_id` | PASS | expected 'alibaba_gpu_v2020', found 'alibaba_gpu_v2020' |
| `task7_pr1.schema_version` | PASS | expected '0.2.0', found '0.2.0' |
| `task7_pr2.dataset_id` | PASS | expected 'alibaba_gpu_v2020', found 'alibaba_gpu_v2020' |
| `task7_pr2.schema_version` | PASS | expected '0.2.0', found '0.2.0' |
| `task6.selected_policy` | PASS | selected_policy='P99' |
| `task6.selected_min_runs` | PASS | selected_min_runs=10 |
| `task7_pr1.phase` | PASS | phase='pr1_validation_lock' |
| `task7_pr1.cpu_semantics` | PASS | cpu_result_semantics='average_usage' |
| `task7_pr1.primary_resource` | PASS | primary_resource='memory' |
| `task7_pr1.no_any_resource` | PASS | any_resource_metric_reported=False |
| `task7_pr1.models_locked` | PASS | selected_models={'cpu': 'hist_gradient_boosting', 'memory': 'hist_gradient_boosting'} |
| `task7_pr1.feature_order_matches_lock` | PASS | locked=['requested_cpu', 'requested_memory', 'requested_gpu', 'inst_num', 'cpu_history_count', 'memory_history_count', 'hist_cpu_mean', 'hist_cpu_p90', 'hist_cpu_p95', 'hist_cpu_p99', 'hist_memory_mean', 'hist_memory_p90', 'hist_memory_p95', 'hist_memory_p99', 'hist_cpu_mean_missing', 'hist_cpu_p90_missing', 'hist_cpu_p95_missing', 'hist_cpu_p99_missing', 'hist_memory_mean_missing', 'hist_memory_p90_missing', 'hist_memory_p95_missing', 'hist_memory_p99_missing', 'gpu_type_MISC', 'gpu_type_P100', 'gpu_type_T4', 'gpu_type_V100', 'gpu_type_V100M32', 'gpu_type__NA_', 'gpu_type_spec_P100', 'gpu_type_spec_T4', 'gpu_type_spec_V100', 'gpu_type_spec_V100M32', 'gpu_type_spec__NA_', 'workload_bert', 'workload_ctr', 'workload_graphlearn', 'workload_inception', 'workload_nmt', 'workload_resnet', 'workload_rl', 'workload_vgg', 'workload_xlnet', 'workload__NA_'], artifact=['requested_cpu', 'requested_memory', 'requested_gpu', 'inst_num', 'cpu_history_count', 'memory_history_count', 'hist_cpu_mean', 'hist_cpu_p90', 'hist_cpu_p95', 'hist_cpu_p99', 'hist_memory_mean', 'hist_memory_p90', 'hist_memory_p95', 'hist_memory_p99', 'hist_cpu_mean_missing', 'hist_cpu_p90_missing', 'hist_cpu_p95_missing', 'hist_cpu_p99_missing', 'hist_memory_mean_missing', 'hist_memory_p90_missing', 'hist_memory_p95_missing', 'hist_memory_p99_missing', 'gpu_type_MISC', 'gpu_type_P100', 'gpu_type_T4', 'gpu_type_V100', 'gpu_type_V100M32', 'gpu_type__NA_', 'gpu_type_spec_P100', 'gpu_type_spec_T4', 'gpu_type_spec_V100', 'gpu_type_spec_V100M32', 'gpu_type_spec__NA_', 'workload_bert', 'workload_ctr', 'workload_graphlearn', 'workload_inception', 'workload_nmt', 'workload_resnet', 'workload_rl', 'workload_vgg', 'workload_xlnet', 'workload__NA_'] |
| `task7_pr2.seven_policies` | PASS | policies=('Request', 'Mean', 'P90', 'P95', 'P99', 'ML', 'Hybrid') |
| `task7_pr2.separate_denominators` | PASS | required=['valid_cpu_violation_count', 'valid_memory_violation_count'], columns=['policy', 'row_count', 'valid_cpu_violation_count', 'valid_memory_violation_count', 'valid_cpu_utilization_count', 'valid_memory_utilization_count', 'cpu_violation_pct', 'memory_violation_pct', 'average_cpu_utilization', 'average_memory_utilization', 'average_cpu_waste', 'average_memory_waste', 'average_cpu_shortfall', 'average_memory_shortfall', 'cpu_result_semantics', 'primary_resource', 'any_resource_metric_reported'] |
| `task7_pr2.cpu_semantics` | PASS | all rows must carry cpu_result_semantics=average_usage |
| `task7_pr2.memory_primary` | PASS | all rows must carry primary_resource=memory |
| `task7_pr2.no_gpu_or_any_resource_metrics` | PASS | forbidden columns=[] |
| `task7_pr2.comparison.numeric_finite` | PASS | numeric cells must be finite and non-null |
| `task7_pr2.comparison.numeric_bounds` | PASS | numeric bounds valid |
| `task7_pr2.sensitivity_row_count` | PASS | expected 35 rows (5 sensitivities x 7 policies), found 35 |
| `task7_pr2.sensitivity_policy_coverage` | PASS | policy_counts={'Request': 5, 'Mean': 5, 'P90': 5, 'P95': 5, 'P99': 5, 'ML': 5, 'Hybrid': 5} |
| `task7_pr2.sensitivity_exact_groups` | PASS | candidate_columns=['sensitivity', 'n_groups'], chosen_columns=['sensitivity'], groups=5 |
| `task7_pr2.sensitivity.numeric_finite` | PASS | always_finite=True, group_counts_null=True, group_n_groups_valid=True, non_group_counts_valid=True, non_group_n_groups_null=True |
| `task7_pr2.sensitivity.numeric_bounds` | PASS | numeric bounds valid |
| `task7.lock_before_final_test` | PASS | earlier='2026-11-15T09:16:50Z', later='2026-11-15T09:26:29Z' |
| `task7.final_run_traces_manifest` | PASS | expected manifest sha='d36964c09c903af646f29929d363d0ccb6ccf60674f31054ed8dfac9dff527ac', run_record='d36964c09c903af646f29929d363d0ccb6ccf60674f31054ed8dfac9dff527ac' |
| `task7.test_evaluator_call_count` | PASS | expected explicit test_evaluator_call_count=1, found 1 |
| `task7.test_target_read_count` | PASS | expected explicit test_target_read_count=1, found 1 |
| `task7.final_run_id` | PASS | expected non-empty run_id, found '4fdc7e96-789b-43a9-990f-20f189e9598b' |
| `task7.pr1_checksum_binding` | PASS | 9 bound checksums match |
| `task7.task6_checksum_binding` | PASS | 8 bound checksums match |
| `task7.task4_test_checksum_binding` | PASS | expected='daaea11a67420e91b9c5cb6d2c54b96eedf0944b3bafe99b5cbb137ca8ec6b1f', actual='daaea11a67420e91b9c5cb6d2c54b96eedf0944b3bafe99b5cbb137ca8ec6b1f' |
| `task7.final_metadata_matches_run_record` | PASS | compared=8, mismatches={} |
| `task7.run_log_contains_final_run` | PASS | matching entries for run_id='4fdc7e96-789b-43a9-990f-20f189e9598b': 1 |
| `task7.run_log_matches_run_record` | PASS | mismatches={} |
| `task7.run_log_output_directory` | PASS | logged_out_dir='data/processed/alibaba_gpu_v2020_final_test', expected_out_dir='data/processed/alibaba_gpu_v2020_final_test' |
| `task7.run_log_precedes_run_record` | PASS | run_log='2026-11-15T09:26:24Z', run_record='2026-11-15T09:26:29Z' |
| `task7.final_run_chronology` | PASS | lock='2026-11-15T09:16:50Z', run_log='2026-11-15T09:26:24Z', run_record='2026-11-15T09:26:29Z' |
| `task7.run_history_documented` | PASS | matching_runs=1, unique_run_ids=True, documented_reruns=True |
| `task7.final_run_code_commit_matches_lock` | PASS | decision_commit='ea6aa08458aace364cd33529ce77de894bcd76ad', run_commit='ea6aa08458aace364cd33529ce77de894bcd76ad' |
| `task7.prediction_columns` | PASS | missing=[] |
| `task7.prediction_units_scope` | PASS | expected CPU=percent_of_vcpu, memory=gb, scope=task_role_per_instance |

## Explicit verification limitations

- **UNVERIFIED:** Task 4 split isolation / history timing / target-value consistency on test rows — Task 8 deliberately does not reopen test target values. Test-side value-level checks are therefore inherited from the frozen Task 4 artifact checksums and metadata, not independently recomputed here.
- **UNVERIFIED:** Task 7 model-prediction reproduction on the real test feature rows — The verifier checks the locked model checksums, feature-order lock, saved prediction artifact checksum and run provenance, but does not rerun model inference in Task 8.

## Interpretation

This report is verification-only. A failed check must be returned to the task that owns the artifact; Task 8 does not repair earlier pipeline behavior.

The verifier does not rerun or retune the final test.

