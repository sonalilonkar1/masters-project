# Alibaba GPU 2020 Verification Report

- Dataset: `alibaba_gpu_v2020`
- Schema: `0.2.0`
- Result: **PASS**
- Checks: 41 passed, 0 failed
- Generated: `2026-11-13T06:25:31Z`
- Decision manifest SHA-256: `f7cbc314fda18d8a8f0c347f433810983372c6db283b030c50b08c467e917950`
- Final run ID: `7dd3942e-c2c0-4816-9466-efd32e486cc2`
- Final run code commit: `b463d5d3239cd2a223045ee034f1ecb9ca89317a`

## Verification checks

| Check | Result | Detail |
|---|---|---|
| `task3_canonical.sha256` | PASS | 5 checksums match |
| `task4_targets.sha256` | PASS | 4 checksums match |
| `task6_baselines.sha256` | PASS | 8 checksums match |
| `task7_pr1_ml.sha256` | PASS | 9 checksums match |
| `task7_pr2_final_test.sha256` | PASS | 5 checksums match |
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
| `task7_pr2.seven_policies` | PASS | policies=('Request', 'Mean', 'P90', 'P95', 'P99', 'ML', 'Hybrid') |
| `task7_pr2.separate_denominators` | PASS | required=['valid_cpu_violation_count', 'valid_memory_violation_count'], columns=['policy', 'row_count', 'valid_cpu_violation_count', 'valid_memory_violation_count', 'valid_cpu_utilization_count', 'valid_memory_utilization_count', 'cpu_violation_pct', 'memory_violation_pct', 'average_cpu_utilization', 'average_memory_utilization', 'average_cpu_waste', 'average_memory_waste', 'average_cpu_shortfall', 'average_memory_shortfall', 'cpu_result_semantics', 'primary_resource', 'any_resource_metric_reported'] |
| `task7_pr2.cpu_semantics` | PASS | all rows must carry cpu_result_semantics=average_usage |
| `task7_pr2.memory_primary` | PASS | all rows must carry primary_resource=memory |
| `task7_pr2.no_gpu_or_any_resource_metrics` | PASS | forbidden columns=[] |
| `task7.lock_before_final_test` | PASS | lock='2026-11-10T22:50:19Z', final_run='2026-11-10T23:14:38Z' |
| `task7.final_run_traces_manifest` | PASS | expected manifest sha='f7cbc314fda18d8a8f0c347f433810983372c6db283b030c50b08c467e917950', run_record='f7cbc314fda18d8a8f0c347f433810983372c6db283b030c50b08c467e917950' |
| `task7.test_evaluator_call_count` | PASS | expected explicit test_evaluator_call_count=1, found 1 |
| `task7.test_target_read_count` | PASS | expected explicit test_target_read_count=1, found 1 |
| `task7.final_run_id` | PASS | expected non-empty run_id, found '7dd3942e-c2c0-4816-9466-efd32e486cc2' |
| `task7.run_log_contains_final_run` | PASS | matching entries for run_id='7dd3942e-c2c0-4816-9466-efd32e486cc2': 1 |
| `task7.run_log_matches_run_record` | PASS | mismatches={} |
| `task7.run_log_output_directory` | PASS | logged_out_dir='data/processed/alibaba_gpu_v2020_final_test', expected_out_dir='data/processed/alibaba_gpu_v2020_final_test' |
| `task7.run_log_precedes_run_record` | PASS | run_log='2026-11-10T23:14:33Z', run_record='2026-11-10T23:14:38Z' |
| `task7.final_run_chronology` | PASS | lock='2026-11-10T22:50:19Z', run_log='2026-11-10T23:14:33Z', run_record='2026-11-10T23:14:38Z' |
| `task7.run_history_documented` | PASS | matching_runs=1, unique_run_ids=True, documented_reruns=True |
| `task7.final_run_code_commit_matches_lock` | PASS | decision_commit='b463d5d3239cd2a223045ee034f1ecb9ca89317a', run_commit='b463d5d3239cd2a223045ee034f1ecb9ca89317a' |
| `task7.prediction_columns` | PASS | missing=[] |
| `task7.prediction_units_scope` | PASS | expected CPU=percent_of_vcpu, memory=gb, scope=task_role_per_instance |

## Explicit verification limitations

- **UNVERIFIED:** Task 4 split isolation / history timing / target-value consistency on test rows — Task 8 deliberately does not reopen test target values. Test-side value-level checks are therefore inherited from the frozen Task 4 artifact checksums and metadata, not independently recomputed here.
- **UNVERIFIED:** Task 7 model-prediction reproduction on the real test feature rows — The verifier checks the locked model checksums, feature-order lock, saved prediction artifact checksum and run provenance, but does not rerun model inference in Task 8.

## Interpretation

This report is verification-only. A failed check must be returned to the task that owns the artifact; Task 8 does not repair earlier pipeline behavior.

The verifier does not rerun or retune the final test.

