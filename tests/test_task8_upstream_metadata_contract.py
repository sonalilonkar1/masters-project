from pathlib import Path


def test_task7_metadata_contract_strings_present():
    repo = Path(__file__).resolve().parents[1]

    task6 = (repo / "scripts/run_alibaba_gpu_2020_baselines.py").read_text()
    pr1 = (repo / "scripts/run_alibaba_gpu_2020_ml.py").read_text()
    pr2 = (repo / "scripts/run_alibaba_gpu_2020_final_test.py").read_text()
    model = (repo / "src/models/alibaba_gpu_2020_final_test.py").read_text()

    assert 'SCHEMA_VERSION = "0.2.0"' in task6
    assert '"schema_version": SCHEMA_VERSION' in task6

    assert '"dataset_id": PROFILE.dataset_id' in pr1
    assert 'SCHEMA_VERSION = "0.2.0"' in pr1
    assert '"schema_version": SCHEMA_VERSION' in pr1

    assert '"dataset_id": PROFILE.dataset_id' in pr2
    assert 'SCHEMA_VERSION = "0.2.0"' in pr2
    assert '"schema_version": SCHEMA_VERSION' in pr2

    # Serialized provenance must come from the shared observed tracker.
    assert (
        '"test_target_read_count": execution_tracker.test_target_read_count'
        in pr2
    )
    assert (
        '"test_evaluator_call_count": execution_tracker.evaluator_call_count'
        in pr2
    )
    assert "execution_tracker.require_exactly_once()" in pr2

    # Exactly-once evidence is collected at the actual operation boundaries,
    # not only inside helper wrappers.
    assert "def _guard_final_test_operations(" in pr2
    assert "original_read_parquet = pd.read_parquet" in pr2
    assert (
        "original_evaluate_canonical = RecommendationEvaluator.evaluate_canonical"
        in pr2
    )
    assert "execution_tracker.record_test_target_read()" in pr2
    assert "execution_tracker.record_evaluator_call()" in pr2
    assert "pd.read_parquet = guarded_read_parquet" in pr2
    assert (
        "RecommendationEvaluator.evaluate_canonical = guarded_evaluate_canonical"
        in pr2
    )
    assert "pd.read_parquet = original_read_parquet" in pr2
    assert (
        "RecommendationEvaluator.evaluate_canonical = original_evaluate_canonical"
        in pr2
    )

    # Provenance identity is serialized alongside measured operation counts.
    assert '"run_id": run_id' in pr2
    assert '"decision_manifest_sha256": decision_sha' in pr2

    # The model still receives the shared tracker so the observed production
    # counts can be returned in FinalTestResult without hardcoded values.
    assert (
        "execution_tracker: FinalTestExecutionTracker | None = None"
        in model
    )
    assert "evaluator_call_count=tracker.evaluator_call_count" in model
