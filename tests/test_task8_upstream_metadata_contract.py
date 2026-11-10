from pathlib import Path

def test_task7_metadata_contract_strings_present():
    repo = Path(__file__).resolve().parents[1]

    task6 = (repo / "scripts/run_alibaba_gpu_2020_baselines.py").read_text()
    pr1 = (repo / "scripts/run_alibaba_gpu_2020_ml.py").read_text()
    pr2 = (repo / "scripts/run_alibaba_gpu_2020_final_test.py").read_text()

    assert 'SCHEMA_VERSION = "0.2.0"' in task6
    assert '"schema_version": SCHEMA_VERSION' in task6

    assert '"dataset_id": PROFILE.dataset_id' in pr1
    assert 'SCHEMA_VERSION = "0.2.0"' in pr1
    assert '"schema_version": SCHEMA_VERSION' in pr1

    assert '"dataset_id": PROFILE.dataset_id' in pr2
    assert 'SCHEMA_VERSION = "0.2.0"' in pr2
    assert '"schema_version": SCHEMA_VERSION' in pr2
    assert '"test_target_read_count": test_target_read_count' in pr2
    assert '"test_evaluator_call_count": result.evaluator_call_count' in pr2
    assert '"run_id": run_id' in pr2
