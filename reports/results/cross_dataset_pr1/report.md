# Cross-dataset reporting — PR 1

Raw violation, utilization, accuracy and CPU percentages must not be compared or ranked across datasets: units, workload scope and targets differ.

These are source renderings. Source hash checks do not certify final experimental reproducibility. Final release verification and conclusions remain pending.

PR 1 keeps all pipeline results provisional, including when an upstream manifest passes the supplied consistency checks. Authoritative upstream verification and any promotion of reporting status are deferred to PR 2.

Receipts separate input artifacts resolved under `--root` from the actual executing generator, imported Python capability definitions and effective profile values. The mirrored capability JSON is not loaded.

[Dataset status](dataset_status.md) · [Contract comparison](contract_comparison.md) · [Comparability](comparability.md) · [Source inventory](report_sources.csv) · [Reporting receipts](report_provenance.json)

Regenerate from the same source files in a new empty output directory using the configuration embedded in the receipt (input paths resolve under `--root`):

```text
python scripts/build_final_cross_dataset_report.py --config <report>/report_provenance.json --root <artifact-root> --out-dir <new-directory>
```

## google_clusterdata2019

Earlier Google test summary is available. Task 10 correction, before/after results and approval to retain earlier results are not supplied; provisional only. F3/F4 cross-split contamination is disclosed in the cited analysis. F7/F8 remain limitations.

Task 10 before/after comparison: **pending approved artifacts**. Earlier results may contain cross-split targets and contaminated validation (F3/F4); they are not leakage-safe final results.

### cpu: peak outcomes

Status: **provisional**. [Table](google_clusterdata2019/01_cpu.md) · [Figure](google_clusterdata2019/01_cpu.svg)

### memory: peak outcomes

Status: **provisional**. [Table](google_clusterdata2019/02_memory.md) · [Figure](google_clusterdata2019/02_memory.svg)

### any_resource: peak outcomes

Status: **provisional**. [Table](google_clusterdata2019/03_any_resource.md) · [Figure](google_clusterdata2019/03_any_resource.svg)

## alibaba_gpu_v2020

These committed Alibaba results are an earlier provisional rendering, not final verified findings. The PR 1 comparison source SHA-256 is de560f38741a60d5e427a4c21c7444debcc8e4a558dc4382fded3a10590b4d27; the newer Task 8 report references c5e6ed9a3237a0e7dd5e6d932366b1131172ce5e1c363d3c6d9a224a6af4e5d8, decision manifest f7cbc314fda18d8a8f0c347f433810983372c6db283b030c50b08c467e917950, and final run 7dd3942e-c2c0-4816-9466-efd32e486cc2. These newer references are review-reported and are not accepted as authoritative inputs. The authoritative Task 7 artifact chain has not yet been reconciled with Task 8; this is a provenance discrepancy, not merely pending verification. Alibaba reporting outputs will be regenerated in Task 12 PR 2 after Task 7 and Task 8 provenance is reconciled. Results apply to successfully completed, resource-valid roles with complete telemetry: eligibility selection bias, low multi-instance sensor coverage, the shortened telemetry window and same-second targets limit generalization.

### memory: peak outcomes

Status: **provisional**. [Table](alibaba_gpu_v2020/01_memory.md) · [Figure](alibaba_gpu_v2020/01_memory.svg)

### cpu: average-usage sizing, not peak safety

Status: **provisional**. [Table](alibaba_gpu_v2020/02_cpu.md) · [Figure](alibaba_gpu_v2020/02_cpu.svg)

[Sensitivity results](alibaba_gpu_v2020/sensitivity.md): same-second, multi-instance and group-weighted source summaries.

## alibaba_clustertrace2018

Task 9 demonstration outcome and validated sample metadata are not supplied. No next-occurrence or recommendation results are reported.

No evaluation numbers reported.

## azure_public_vm_v2

Existing feasibility analysis supports deferring integration. Dataset V1/V2 identity needs reconciliation; observed memory and official recurrence are unavailable. No Task 11 Stage 2 result or formal completed outcome is supplied.

No evaluation numbers reported.
