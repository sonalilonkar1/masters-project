# Reporting limitations

Verified published bytes and metadata do not establish historical execution or inference reproduction.

Final project completion remains pending documented dataset decisions.

## google_clusterdata2019

Existing frozen Google results are displayed with F3/F4 contamination and F7/F8 limitations. Reporting treatment is governed by the validated dataset decision record.

- external_physical_artifact_bytes: UNVERIFIED: not inspected by reporting
- historical_exactly_once_execution: not independently observed
- scientific_inference_reproduction: UNVERIFIED
- F3/F4: cross-split targets and contaminated validation; not leakage-safe final results.
- F7/F8: abnormal/incomplete records and multi-machine aggregation remain limitations.
- Task 10 correction or documented retention is governed by the validated dataset decision record.

## alibaba_gpu_v2020

Authoritative published November 15 Alibaba run. Published reporting bytes and metadata are validated; unavailable physical artifacts, inference reproduction and historical execution are not independently reproduced.

- **UNVERIFIED:** Task 4 split isolation / history timing / target-value consistency on test rows — Task 8 deliberately does not reopen test target values. Test-side value-level checks are therefore inherited from the frozen Task 4 artifact checksums and metadata, not independently recomputed here.
- **UNVERIFIED:** Task 7 model-prediction reproduction on the real test feature rows — The verifier checks the locked model checksums, feature-order lock, saved prediction artifact checksum and run provenance, but does not rerun model inference in Task 8.
- external_physical_artifact_bytes: UNVERIFIED: not inspected by reporting
- historical_exactly_once_execution: recorded integer-one counters; not independently observed
- scientific_inference_reproduction: UNVERIFIED
- november_10_byte_equivalence: UNVERIFIED: old and new physical bundles not compared
- Run history across earlier decisions remains an upstream follow-up.
- Scientific execution environment differs from the repository lock file.
- Task 8 reporting receipt records a dirty source tree; no clean reproduction is claimed.

## alibaba_clustertrace2018

Task 9 demonstration outcome and validated sample metadata are not supplied. No next-occurrence or recommendation results are reported.


## azure_public_vm_v2

Existing feasibility analysis supports deferring integration. Dataset V1/V2 identity needs reconciliation; observed memory and official recurrence are unavailable. No Task 11 Stage 2 results are reported.
