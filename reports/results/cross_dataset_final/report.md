# Cross-dataset reporting — Task 12 PR 2

Raw violation, utilization, accuracy and CPU percentages must not be compared or ranked across datasets: units, workload scope and targets differ.

Reporting validation is separate from experimental verification. Published bytes and metadata are checked; external physical artifacts and historical execution are not independently reproduced.

Final project completion remains pending documented dataset decisions.

[Dataset status](dataset_status.md) · [Contract comparison](contract_comparison.md) · [Comparability](comparability.md) · [Evidence](evidence_status.md) · [Limitations](limitations.md) · [Conclusions](conclusions.md) · [Artifact manifest](artifact_manifest.json)

## google_clusterdata2019

Existing frozen Google results are displayed with F3/F4 contamination and F7/F8 limitations. Reporting treatment is governed by the validated dataset decision record.

Task 10 before/after comparison: **pending approved artifacts**. Earlier results may contain cross-split targets and contaminated validation (F3/F4); they are not leakage-safe final results.

### cpu: peak outcomes

Status: **decision_pending**. [Table](google_clusterdata2019/01_cpu.md) · [Figure](google_clusterdata2019/01_cpu.svg)

### memory: peak outcomes

Status: **decision_pending**. [Table](google_clusterdata2019/02_memory.md) · [Figure](google_clusterdata2019/02_memory.svg)

### any_resource: peak outcomes

Status: **decision_pending**. [Table](google_clusterdata2019/03_any_resource.md) · [Figure](google_clusterdata2019/03_any_resource.svg)

## alibaba_gpu_v2020

Authoritative published November 15 Alibaba run. Published reporting bytes and metadata are validated; unavailable physical artifacts, inference reproduction and historical execution are not independently reproduced.

### memory: peak outcomes

Status: **published_evidence_validated**. [Table](alibaba_gpu_v2020/01_memory.md) · [Figure](alibaba_gpu_v2020/01_memory.svg)

### cpu: average-usage sizing, not peak safety

Status: **published_evidence_validated**. [Table](alibaba_gpu_v2020/02_cpu.md) · [Figure](alibaba_gpu_v2020/02_cpu.svg)

[Sensitivity results](alibaba_gpu_v2020/sensitivity.md): same-second, multi-instance and group-weighted source summaries.

## alibaba_clustertrace2018

Task 9 demonstration outcome and validated sample metadata are not supplied. No next-occurrence or recommendation results are reported.

No evaluation numbers reported.

## azure_public_vm_v2

Existing feasibility analysis supports deferring integration. Dataset V1/V2 identity needs reconciliation; observed memory and official recurrence are unavailable. No Task 11 Stage 2 results are reported.

No evaluation numbers reported.
