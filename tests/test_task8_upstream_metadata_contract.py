from pathlib import Path


def test_task7_metadata_contract_strings_present():
    repo = Path(__file__).resolve().parents[1]

    task6 = (
        repo / "scripts/run_alibaba_gpu_2020_baselines.py"
    ).read_text()

    pr1 = (
        repo / "scripts/run_alibaba_gpu_2020_ml.py"
    ).read_text()

    pr2 = (
        repo / "scripts/run_alibaba_gpu_2020_final_test.py"
    ).read_text()

    model = (
        repo / "src/models/alibaba_gpu_2020_final_test.py"
    ).read_text()

    # Task 6 metadata contract.
    assert 'SCHEMA_VERSION = "0.2.0"' in task6
    assert '"schema_version": SCHEMA_VERSION' in task6

    # Task 7 PR1 metadata contract.
    assert '"dataset_id": PROFILE.dataset_id' in pr1
    assert 'SCHEMA_VERSION = "0.2.0"' in pr1
    assert '"schema_version": SCHEMA_VERSION' in pr1

    # Task 7 PR2 metadata/provenance contract.
    assert '"dataset_id": PROFILE.dataset_id' in pr2
    assert 'SCHEMA_VERSION = "0.2.0"' in pr2
    assert '"schema_version": SCHEMA_VERSION' in pr2

    # Execution counters must come from measured operations,
    # not hardcoded values.
    assert (
        '"test_target_read_count": '
        'execution_tracker.test_target_read_count'
    ) in pr2

    assert (
        '"test_evaluator_call_count": '
        'execution_tracker.evaluator_call_count'
    ) in pr2

    # Exactly-once execution is enforced by the runner.
    assert (
        "execution_tracker.require_exactly_once()"
        in pr2
    )

    # Target reads are counted at the real read boundary.
    assert (
        "execution_tracker.record_test_target_read()"
        in pr2
    )

    # Provenance identity is serialized.
    assert '"run_id": run_id' in pr2

    assert (
        '"decision_manifest_sha256": decision_sha'
        in pr2
    )

    # The model receives the shared execution tracker.
    assert (
        "execution_tracker: "
        "FinalTestExecutionTracker | None = None"
        in model
    )

    assert (
        "execution_tracker=tracker"
        in model
    )

    assert (
        "tracker.record_evaluator_call()"
        in model
    )