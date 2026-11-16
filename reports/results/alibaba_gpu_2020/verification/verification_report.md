# Alibaba GPU 2020 Verification Report

- Dataset: `alibaba_gpu_v2020`
- Schema: `0.2.0`
- Result: **PASS**
- Checks: 81 passed, 0 failed
- Generated: `2026-11-16T05:10:42Z`
- Generation ID: `1cc473e40341494d9d946c25a7dc9a25`
- Decision manifest SHA-256: `d36964c09c903af646f29929d363d0ccb6ccf60674f31054ed8dfac9dff527ac`
- Final run ID: `4fdc7e96-789b-43a9-990f-20f189e9598b`
- Final run code commit: `ea6aa08458aace364cd33529ce77de894bcd76ad`

## Verification checks

| Check | Result | Detail |
|---|---|---|
| `verification.output_directory_isolated` | PASS | overlaps=[] |
| `task3_canonical.sha256` | PASS | 5 checksums match |
| `task4_targets.sha256` | PASS | 4 checksums match |
| `task6_baselines.sha256` | PASS | 8 checksums match |
| `task7_pr1_ml.sha256` | PASS | 9 checksums match |
| `task7_pr2_final_test.sha256` | PASS | 5 checksums match |
| `task3.published_evidence` | PASS | 2 published files match |
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
| `task7_pr1.phase` | PASS | phase='pr1_validation_lock' |
| `task7_pr1.cpu_semantics` | PASS | cpu_result_semantics='average_usage' |
| `task7_pr1.primary_resource` | PASS | primary_resource='memory' |
| `task7_pr1.no_any_resource` | PASS | any_resource_metric_reported=False |
| `task7_pr1.task4_inputs_present` | PASS | task4_inputs={'targets_dir': 'data/processed/alibaba_gpu_v2020_targets', 'targets_manifest': {'metadata.json': '1a24461ecebeddcca725383720ebc7c2cc84628c2e242f6b823a57bc9fe3c455', 'test.parquet': 'daaea11a67420e91b9c5cb6d2c54b96eedf0944b3bafe99b5cbb137ca8ec6b1f', 'train.parquet': 'f2378317f8fd26bda7663df84052ff7ec446af4c282c19e838fa4df76fef81e4', 'validation.parquet': 'a30adc80aa036d34e71f9033330cb9b17bf7d18acd4678707df74ce70f985421'}, 'task3_source_commit': 'c2ae87f4aa357384a3cc8bdc72f776f1012c3ab7', 'task4_code_commit': 'd29d24469c217005adc3ba08249bcc6d7a815ea3'} |
| `task7_pr1.task4_targets_manifest_present` | PASS | targets_manifest={'metadata.json': '1a24461ecebeddcca725383720ebc7c2cc84628c2e242f6b823a57bc9fe3c455', 'test.parquet': 'daaea11a67420e91b9c5cb6d2c54b96eedf0944b3bafe99b5cbb137ca8ec6b1f', 'train.parquet': 'f2378317f8fd26bda7663df84052ff7ec446af4c282c19e838fa4df76fef81e4', 'validation.parquet': 'a30adc80aa036d34e71f9033330cb9b17bf7d18acd4678707df74ce70f985421'} |
| `task7_pr1.task4_checksum_binding` | PASS | 4 bound checksums match |
| `task7.task4_test_checksum_binding` | PASS | decision='daaea11a67420e91b9c5cb6d2c54b96eedf0944b3bafe99b5cbb137ca8ec6b1f', run_record='daaea11a67420e91b9c5cb6d2c54b96eedf0944b3bafe99b5cbb137ca8ec6b1f' |
| `task7_pr1.task6_selection_present` | PASS | task6_selection={'baseline_selection_sha256': 'ec3c4e07f51b991c16ad27825b90752191958339aa9b78f25f06a51b61c6ad5e', 'baselines_manifest': {'baseline_selection.json': 'ec3c4e07f51b991c16ad27825b90752191958339aa9b78f25f06a51b61c6ad5e', 'history_statistics.parquet': '39e12b6ed581cc1a03735cdc04c88c17e2c021ab9da0c67beff1d9552edd54d3', 'metadata.json': '7a44dd9606f6164b518a5aece3c260758ec9ab5a15c77dcd2ac88af3d965d048', 'recommendations_test.parquet': '1e3361f68224d6565c00ab92820cf38bcbdeda703843647c5ef96fd820046e1b', 'recommendations_train.parquet': '93d618830576724defa523755ac8bf26ad281cc96a61725dc56094ee683de05b', 'recommendations_validation.parquet': '1d3df7a8aa0b81776340f4469171c8efbbc7d68ce15b0ab94a3ca865e4ddbc65', 'sensitivity_validation.csv': 'fd01cf2ca082cd60902180a450d9136c90936f21d08dd2884974d243aff7f1c0', 'validation_comparison.csv': '3b19cb6b5aff26fec79585064a44bb88d5658387433db255070490368460fb78'}, 'selected_min_runs': 10, 'selected_policy': 'P99'} |
| `task7_pr1.task6_baselines_manifest_present` | PASS | baselines_manifest={'baseline_selection.json': 'ec3c4e07f51b991c16ad27825b90752191958339aa9b78f25f06a51b61c6ad5e', 'history_statistics.parquet': '39e12b6ed581cc1a03735cdc04c88c17e2c021ab9da0c67beff1d9552edd54d3', 'metadata.json': '7a44dd9606f6164b518a5aece3c260758ec9ab5a15c77dcd2ac88af3d965d048', 'recommendations_test.parquet': '1e3361f68224d6565c00ab92820cf38bcbdeda703843647c5ef96fd820046e1b', 'recommendations_train.parquet': '93d618830576724defa523755ac8bf26ad281cc96a61725dc56094ee683de05b', 'recommendations_validation.parquet': '1d3df7a8aa0b81776340f4469171c8efbbc7d68ce15b0ab94a3ca865e4ddbc65', 'sensitivity_validation.csv': 'fd01cf2ca082cd60902180a450d9136c90936f21d08dd2884974d243aff7f1c0', 'validation_comparison.csv': '3b19cb6b5aff26fec79585064a44bb88d5658387433db255070490368460fb78'} |
| `task7_pr1.task6_checksum_binding` | PASS | 8 bound checksums match |
| `task7.task6_run_record_binding` | PASS | decision={'baseline_selection.json': 'ec3c4e07f51b991c16ad27825b90752191958339aa9b78f25f06a51b61c6ad5e', 'history_statistics.parquet': '39e12b6ed581cc1a03735cdc04c88c17e2c021ab9da0c67beff1d9552edd54d3', 'metadata.json': '7a44dd9606f6164b518a5aece3c260758ec9ab5a15c77dcd2ac88af3d965d048', 'recommendations_test.parquet': '1e3361f68224d6565c00ab92820cf38bcbdeda703843647c5ef96fd820046e1b', 'recommendations_train.parquet': '93d618830576724defa523755ac8bf26ad281cc96a61725dc56094ee683de05b', 'recommendations_validation.parquet': '1d3df7a8aa0b81776340f4469171c8efbbc7d68ce15b0ab94a3ca865e4ddbc65', 'sensitivity_validation.csv': 'fd01cf2ca082cd60902180a450d9136c90936f21d08dd2884974d243aff7f1c0', 'validation_comparison.csv': '3b19cb6b5aff26fec79585064a44bb88d5658387433db255070490368460fb78'}, run_record={'baseline_selection.json': 'ec3c4e07f51b991c16ad27825b90752191958339aa9b78f25f06a51b61c6ad5e', 'history_statistics.parquet': '39e12b6ed581cc1a03735cdc04c88c17e2c021ab9da0c67beff1d9552edd54d3', 'metadata.json': '7a44dd9606f6164b518a5aece3c260758ec9ab5a15c77dcd2ac88af3d965d048', 'recommendations_test.parquet': '1e3361f68224d6565c00ab92820cf38bcbdeda703843647c5ef96fd820046e1b', 'recommendations_train.parquet': '93d618830576724defa523755ac8bf26ad281cc96a61725dc56094ee683de05b', 'recommendations_validation.parquet': '1d3df7a8aa0b81776340f4469171c8efbbc7d68ce15b0ab94a3ca865e4ddbc65', 'sensitivity_validation.csv': 'fd01cf2ca082cd60902180a450d9136c90936f21d08dd2884974d243aff7f1c0', 'validation_comparison.csv': '3b19cb6b5aff26fec79585064a44bb88d5658387433db255070490368460fb78'} |
| `task7_pr1.baseline_selection_hash_binding` | PASS | decision='ec3c4e07f51b991c16ad27825b90752191958339aa9b78f25f06a51b61c6ad5e', manifest='ec3c4e07f51b991c16ad27825b90752191958339aa9b78f25f06a51b61c6ad5e' |
| `task7_pr1.baseline_selection_semantics` | PASS | physical=('P99',10), decision=('P99',10), run=('P99',10) |
| `task7_pr1.model_artifacts_present` | PASS | model_artifacts={'cpu': {'file': 'cpu_model.joblib', 'sha256': 'ff4a1521eb02343d1fb0ef089af0c24acdfbff72a28a73c823890c3740258384'}, 'memory': {'file': 'memory_model.joblib', 'sha256': 'c79c29ded8eb466a235ac93dad26d23d7166efbf4e8a69dcc461cdf8cbc5286a'}} |
| `task7_pr1.selected_models_present` | PASS | selected_models={'cpu': 'hist_gradient_boosting', 'memory': 'hist_gradient_boosting'} |
| `task7_pr1.cpu_model_artifact_present` | PASS | artifact={'file': 'cpu_model.joblib', 'sha256': 'ff4a1521eb02343d1fb0ef089af0c24acdfbff72a28a73c823890c3740258384'} |
| `task7_pr1.cpu_model_hash_binding` | PASS | decision/stage/run/physical model hash binding valid |
| `task7_pr1.cpu_selected_model` | PASS | selected_model='hist_gradient_boosting' |
| `task7_pr1.memory_model_artifact_present` | PASS | artifact={'file': 'memory_model.joblib', 'sha256': 'c79c29ded8eb466a235ac93dad26d23d7166efbf4e8a69dcc461cdf8cbc5286a'} |
| `task7_pr1.memory_model_hash_binding` | PASS | decision/stage/run/physical model hash binding valid |
| `task7_pr1.memory_selected_model` | PASS | selected_model='hist_gradient_boosting' |
| `task7_pr1.model_selection_cpu_matches_lock` | PASS | decision='hist_gradient_boosting', model_selection='hist_gradient_boosting', run='hist_gradient_boosting' |
| `task7_pr1.model_selection_memory_matches_lock` | PASS | decision='hist_gradient_boosting', model_selection='hist_gradient_boosting', run='hist_gradient_boosting' |
| `task7_pr1.feature_order_present` | PASS | feature_order=['requested_cpu', 'requested_memory', 'requested_gpu', 'inst_num', 'cpu_history_count', 'memory_history_count', 'hist_cpu_mean', 'hist_cpu_p90', 'hist_cpu_p95', 'hist_cpu_p99', 'hist_memory_mean', 'hist_memory_p90', 'hist_memory_p95', 'hist_memory_p99', 'hist_cpu_mean_missing', 'hist_cpu_p90_missing', 'hist_cpu_p95_missing', 'hist_cpu_p99_missing', 'hist_memory_mean_missing', 'hist_memory_p90_missing', 'hist_memory_p95_missing', 'hist_memory_p99_missing', 'gpu_type_MISC', 'gpu_type_P100', 'gpu_type_T4', 'gpu_type_V100', 'gpu_type_V100M32', 'gpu_type__NA_', 'gpu_type_spec_P100', 'gpu_type_spec_T4', 'gpu_type_spec_V100', 'gpu_type_spec_V100M32', 'gpu_type_spec__NA_', 'workload_bert', 'workload_ctr', 'workload_graphlearn', 'workload_inception', 'workload_nmt', 'workload_resnet', 'workload_rl', 'workload_vgg', 'workload_xlnet', 'workload__NA_'] |
| `task7_pr1.feature_order_matches_lock` | PASS | decision=['requested_cpu', 'requested_memory', 'requested_gpu', 'inst_num', 'cpu_history_count', 'memory_history_count', 'hist_cpu_mean', 'hist_cpu_p90', 'hist_cpu_p95', 'hist_cpu_p99', 'hist_memory_mean', 'hist_memory_p90', 'hist_memory_p95', 'hist_memory_p99', 'hist_cpu_mean_missing', 'hist_cpu_p90_missing', 'hist_cpu_p95_missing', 'hist_cpu_p99_missing', 'hist_memory_mean_missing', 'hist_memory_p90_missing', 'hist_memory_p95_missing', 'hist_memory_p99_missing', 'gpu_type_MISC', 'gpu_type_P100', 'gpu_type_T4', 'gpu_type_V100', 'gpu_type_V100M32', 'gpu_type__NA_', 'gpu_type_spec_P100', 'gpu_type_spec_T4', 'gpu_type_spec_V100', 'gpu_type_spec_V100M32', 'gpu_type_spec__NA_', 'workload_bert', 'workload_ctr', 'workload_graphlearn', 'workload_inception', 'workload_nmt', 'workload_resnet', 'workload_rl', 'workload_vgg', 'workload_xlnet', 'workload__NA_'], artifact=['requested_cpu', 'requested_memory', 'requested_gpu', 'inst_num', 'cpu_history_count', 'memory_history_count', 'hist_cpu_mean', 'hist_cpu_p90', 'hist_cpu_p95', 'hist_cpu_p99', 'hist_memory_mean', 'hist_memory_p90', 'hist_memory_p95', 'hist_memory_p99', 'hist_cpu_mean_missing', 'hist_cpu_p90_missing', 'hist_cpu_p95_missing', 'hist_cpu_p99_missing', 'hist_memory_mean_missing', 'hist_memory_p90_missing', 'hist_memory_p95_missing', 'hist_memory_p99_missing', 'gpu_type_MISC', 'gpu_type_P100', 'gpu_type_T4', 'gpu_type_V100', 'gpu_type_V100M32', 'gpu_type__NA_', 'gpu_type_spec_P100', 'gpu_type_spec_T4', 'gpu_type_spec_V100', 'gpu_type_spec_V100M32', 'gpu_type_spec__NA_', 'workload_bert', 'workload_ctr', 'workload_graphlearn', 'workload_inception', 'workload_nmt', 'workload_resnet', 'workload_rl', 'workload_vgg', 'workload_xlnet', 'workload__NA_'] |
| `task7_pr1.feature_order_hash_binding` | PASS | physical='b9b74433fafbb4401284f76966d2fb134685f9a44e3bdde5c56adb526a34f925', stage='b9b74433fafbb4401284f76966d2fb134685f9a44e3bdde5c56adb526a34f925', run='b9b74433fafbb4401284f76966d2fb134685f9a44e3bdde5c56adb526a34f925' |
| `task7.pr1_run_record_binding` | PASS | stage={'candidate_models.csv': 'ef474ef5ac200f4163772a19e0af75c2bea7903577bb4bf934f963b28137262c', 'cpu_model.joblib': 'ff4a1521eb02343d1fb0ef089af0c24acdfbff72a28a73c823890c3740258384', 'decision_manifest.json': 'd36964c09c903af646f29929d363d0ccb6ccf60674f31054ed8dfac9dff527ac', 'feature_order.json': 'b9b74433fafbb4401284f76966d2fb134685f9a44e3bdde5c56adb526a34f925', 'memory_model.joblib': 'c79c29ded8eb466a235ac93dad26d23d7166efbf4e8a69dcc461cdf8cbc5286a', 'metadata.json': '7136748103537e4531df8c34563b594e9ee9d1fe75c005e75412a2d5870dcf80', 'model_selection.json': 'b9357ea5b0c139d79cbb23c56f8e781f24c2a0b2276b2ce64b813f2cbb177e08', 'validation_ml_hybrid_predictions.parquet': '5d71419ec52383f6cedc4db0d3776c8ffba9795e9670b925081e6bf8cf4c245d', 'validation_policy_comparison.csv': '382bb89be7024e3474e34ed3f4f19563513858c06df71d9a201a2d3c2898a463'}, run_record={'candidate_models.csv': 'ef474ef5ac200f4163772a19e0af75c2bea7903577bb4bf934f963b28137262c', 'cpu_model.joblib': 'ff4a1521eb02343d1fb0ef089af0c24acdfbff72a28a73c823890c3740258384', 'decision_manifest.json': 'd36964c09c903af646f29929d363d0ccb6ccf60674f31054ed8dfac9dff527ac', 'feature_order.json': 'b9b74433fafbb4401284f76966d2fb134685f9a44e3bdde5c56adb526a34f925', 'memory_model.joblib': 'c79c29ded8eb466a235ac93dad26d23d7166efbf4e8a69dcc461cdf8cbc5286a', 'metadata.json': '7136748103537e4531df8c34563b594e9ee9d1fe75c005e75412a2d5870dcf80', 'model_selection.json': 'b9357ea5b0c139d79cbb23c56f8e781f24c2a0b2276b2ce64b813f2cbb177e08', 'validation_ml_hybrid_predictions.parquet': '5d71419ec52383f6cedc4db0d3776c8ffba9795e9670b925081e6bf8cf4c245d', 'validation_policy_comparison.csv': '382bb89be7024e3474e34ed3f4f19563513858c06df71d9a201a2d3c2898a463'} |
| `task7.final_population_size` | PASS | final_population_size=44053 |
| `task7_pr2.comparison.schema` | PASS | missing=[], unexpected=[], columns=('policy', 'row_count', 'valid_cpu_violation_count', 'valid_memory_violation_count', 'valid_cpu_utilization_count', 'valid_memory_utilization_count', 'cpu_violation_pct', 'memory_violation_pct', 'average_cpu_utilization', 'average_memory_utilization', 'average_cpu_waste', 'average_memory_waste', 'average_cpu_shortfall', 'average_memory_shortfall', 'cpu_result_semantics', 'primary_resource', 'any_resource_metric_reported') |
| `task7_pr2.seven_policies` | PASS | policies=('Request', 'Mean', 'P90', 'P95', 'P99', 'ML', 'Hybrid') |
| `task7_pr2.comparison.semantics` | PASS | semantics valid |
| `task7_pr2.comparison.numeric_parse` | PASS | numeric columns parse |
| `task7_pr2.comparison.denominator_relationships` | PASS | count relationships valid |
| `task7_pr2.comparison.metric_contract` | PASS | metric ranges/nullability valid |
| `task7_pr2.sensitivity.schema` | PASS | missing=[], unexpected=[], columns=('sensitivity', 'policy', 'row_count', 'valid_cpu_violation_count', 'valid_memory_violation_count', 'valid_cpu_utilization_count', 'valid_memory_utilization_count', 'cpu_violation_pct', 'memory_violation_pct', 'average_cpu_utilization', 'average_memory_utilization', 'average_cpu_waste', 'average_memory_waste', 'average_cpu_shortfall', 'average_memory_shortfall', 'cpu_result_semantics', 'primary_resource', 'any_resource_metric_reported', 'n_groups') |
| `task7_pr2.sensitivity.cartesian_product` | PASS | rows=35, unique_pairs=35, missing=[], unexpected=[] |
| `task7_pr2.sensitivity.semantics` | PASS | semantics valid |
| `task7_pr2.sensitivity.numeric_contract` | PASS | producer-compatible sensitivity numeric/null contract valid |
| `task7_pr2.sensitivity.cross_table_relationships` | PASS | cross-table relationships valid |
| `task7.lock_before_final_test` | PASS | earlier='2026-11-15T09:16:50Z', later='2026-11-15T09:26:29Z' |
| `task7.final_run_traces_manifest` | PASS | computed='d36964c09c903af646f29929d363d0ccb6ccf60674f31054ed8dfac9dff527ac', run='d36964c09c903af646f29929d363d0ccb6ccf60674f31054ed8dfac9dff527ac', metadata='d36964c09c903af646f29929d363d0ccb6ccf60674f31054ed8dfac9dff527ac' |
| `task7.run_record.test_evaluator_call_count` | PASS | expected exact integer 1, found 1 (int) |
| `task7.run_record.test_target_read_count` | PASS | expected exact integer 1, found 1 (int) |
| `task7.final_metadata.test_evaluator_call_count` | PASS | expected exact integer 1, found 1 (int) |
| `task7.final_metadata.test_target_read_count` | PASS | expected exact integer 1, found 1 (int) |
| `task7.operation_counters_cross_record` | PASS | run-record and final-metadata counters must agree |
| `task7.final_run_id` | PASS | run_id='4fdc7e96-789b-43a9-990f-20f189e9598b' |
| `task7.decision_identity_binding` | PASS | computed='d36964c09c903af646f29929d363d0ccb6ccf60674f31054ed8dfac9dff527ac', stage='d36964c09c903af646f29929d363d0ccb6ccf60674f31054ed8dfac9dff527ac', run_pr1='d36964c09c903af646f29929d363d0ccb6ccf60674f31054ed8dfac9dff527ac', run='d36964c09c903af646f29929d363d0ccb6ccf60674f31054ed8dfac9dff527ac', metadata='d36964c09c903af646f29929d363d0ccb6ccf60674f31054ed8dfac9dff527ac', log='d36964c09c903af646f29929d363d0ccb6ccf60674f31054ed8dfac9dff527ac' |
| `task7.execution_commit_exists` | PASS | ea6aa08458aace364cd33529ce77de894bcd76ad |
| `task7.execution_commit_identity` | PASS | identities={'run_record': 'ea6aa08458aace364cd33529ce77de894bcd76ad', 'run_log': 'ea6aa08458aace364cd33529ce77de894bcd76ad', 'final_metadata.build': 'ea6aa08458aace364cd33529ce77de894bcd76ad', 'decision.build': 'ea6aa08458aace364cd33529ce77de894bcd76ad'} |
| `task7.execution_instrumentation_audited` | PASS | recorded commit matches audited source contract from ea6aa08458aace364cd33529ce77de894bcd76ad |
| `task7.run_log_contains_final_run` | PASS | matching entries for run_id='4fdc7e96-789b-43a9-990f-20f189e9598b': 1 |
| `task7.run_log_matches_run_record` | PASS | mismatches={} |
| `task7.run_log_output_directory` | PASS | logged_out_dir='data/processed/alibaba_gpu_v2020_final_test', expected_out_dir='data/processed/alibaba_gpu_v2020_final_test' |
| `task7.run_log_precedes_run_record` | PASS | run_log='2026-11-15T09:26:24Z', run_record='2026-11-15T09:26:29Z' |
| `task7.final_run_chronology` | PASS | lock='2026-11-15T09:16:50Z', run_log='2026-11-15T09:26:24Z', run_record='2026-11-15T09:26:29Z' |
| `task7.run_history_documented` | PASS | matching_runs=1, unique_run_ids=True, documented_reruns=True |
| `task7.final_run_code_commit_matches_lock` | PASS | decision_commit='ea6aa08458aace364cd33529ce77de894bcd76ad', run_commit='ea6aa08458aace364cd33529ce77de894bcd76ad' |
| `task7.final_metadata_matches_run_record` | PASS | required final metadata fields match |
| `task7.prediction_columns` | PASS | missing=[] |
| `task7.prediction_units_scope` | PASS | expected CPU=percent_of_vcpu, memory=gb, scope=task_role_per_instance |

## Explicit verification limitations

- **UNVERIFIED:** Task 4 split isolation / history timing / target-value consistency on test rows — Task 8 deliberately does not reopen test target values. Test-side value-level checks are therefore inherited from the frozen Task 4 artifact checksums and metadata, not independently recomputed here.
- **UNVERIFIED:** Task 7 model-prediction reproduction on the real test feature rows — The verifier checks the locked model checksums, feature-order lock, saved prediction artifact checksum and run provenance, but does not rerun model inference in Task 8.

## Interpretation

This report is verification-only. A failed check must be returned to the task that owns the artifact; Task 8 does not repair earlier pipeline behavior.

The verifier does not rerun or retune the final test.
