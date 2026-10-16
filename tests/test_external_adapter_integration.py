import pandas as pd

from src.adapters.alibaba import Alibaba2018Adapter
from src.adapters.azure_vm import AzureVMAdapter


def test_alibaba_canonical_artifact_reload(tmp_path):
    task = pd.DataFrame([{
        "task_name":"M1","instance_num":1,"job_name":"j1",
        "task_type":1,"status":"Terminated","start_time":1,
        "end_time":2,"plan_cpu":100.0,"plan_mem":0.5,
    }])

    instance = pd.DataFrame([{
        "instance_name":"i1","task_name":"M1","job_name":"j1",
        "task_type":1,"status":"Terminated","start_time":1,
        "end_time":2,"machine_id":"m1","seq_no":1,
        "total_seq_no":1,"cpu_avg":50.0,"cpu_max":90.0,
        "mem_avg":0.2,"mem_max":0.4,
    }])

    out = Alibaba2018Adapter().adapt_tables(
        task,
        instance,
    ).canonical

    path = tmp_path / "alibaba.parquet"
    out.to_parquet(path, index=False)
    reloaded = pd.read_parquet(path)

    assert len(reloaded) == len(out)
    assert list(reloaded["instance_id"]) == list(out["instance_id"])
    assert list(reloaded["peak_cpu"]) == list(out["peak_cpu"])


def test_azure_canonical_artifact_reload(tmp_path):
    vm = pd.DataFrame([{
        "vm_id":"vm1","subscription_id":"s1","deployment_id":"d1",
        "vm_created":0,"vm_deleted":600,"max_cpu":80.0,
        "avg_cpu":35.0,"p95_max_cpu":70.0,
        "vm_category":"Interactive","vm_core_count_bucket":4.0,
        "vm_memory_bucket":14.0,
    }])

    cpu = pd.DataFrame([{
        "timestamp":0,"vm_id":"vm1","min_cpu":10.0,
        "max_cpu":60.0,"avg_cpu":30.0,
    }])

    out = AzureVMAdapter().adapt_cpu_readings(
        vm,
        cpu,
    ).canonical

    path = tmp_path / "azure.parquet"
    out.to_parquet(path, index=False)
    reloaded = pd.read_parquet(path)

    assert len(reloaded) == len(out)
    assert list(reloaded["instance_id"]) == list(out["instance_id"])
    assert list(reloaded["observed_cpu"]) == list(out["observed_cpu"])
    assert reloaded["observed_memory"].isna().all()
