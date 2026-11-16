# Task 12 PR 2 reporting runbook

## Scope and status

This workflow reads small, published scientific summaries and provenance files.
It never trains, loads models, reproduces inference, reads target Parquet values,
or runs a frozen evaluator. The current final-format bundle is reporting-valid,
but **project completion remains pending** Google, Azure and Alibaba 2018 decisions.
See [reporting decisions](cross_dataset_reporting_decisions.md).

Current entry point: `reports/results/cross_dataset_final/report.md`.
`reports/results/cross_dataset_pr1/` is an unchanged historical rendering. Its
original inputs belong to commit `853744027dcd42ea0d6b1b72b7eba42ceafa48d1`;
running its old receipt against current paths does not recreate those old bytes.

## Inputs and identity

`config/cross_dataset_report_final.json` explicitly maps dataset, stage, logical
artifact, authoritative manifest path, published path and SHA-256. Task 8 paths
under `data/processed/` identify artifacts; the reporting copies live under
`reports/results/`. Matching is never performed by basename alone.

Alibaba's expected decision digest is
`d36964c09c903af646f29929d363d0ccb6ccf60674f31054ed8dfac9dff527ac`,
run ID `4fdc7e96-789b-43a9-990f-20f189e9598b`, execution commit
`ea6aa08458aace364cd33529ce77de894bcd76ad`. The Task 8 manifest itself is pinned,
its companion hashes/generation checked, and its dataset/identity reconciled
with the published decision, pre-read log, run record and final metadata.

Google uses canonical ID `google_clusterdata2019` and explicitly documented
producer alias `google_subset_v1`. Its decision/run identity and published source
digests are checked without claiming correction of F3/F4 contamination.

## Generate and validate

From the repository root, use an existing suitable Python environment:

```bash
env -u PYTHONPATH python scripts/build_final_cross_dataset_report.py \
  --config config/cross_dataset_report_final.json \
  --out-dir /tmp/traceadvisor-task12-report-a --strict

python scripts/build_final_cross_dataset_report.py \
  --validate-bundle /tmp/traceadvisor-task12-report-a

env -u PYTHONPATH python scripts/build_final_cross_dataset_report.py \
  --config /tmp/traceadvisor-task12-report-a/report_provenance.json \
  --out-dir /tmp/traceadvisor-task12-report-b --strict

diff -r /tmp/traceadvisor-task12-report-a /tmp/traceadvisor-task12-report-b
```

Choose unused output paths. Generation refuses nonempty output directories.
Final output is staged on the destination filesystem and published as a complete
directory. Malformed inputs or failed publication do not expose a successful
final manifest. Existing bundles are never overwritten by the CLI.

`--strict` requires both pipeline summaries; it does not approve dataset decisions.
Add `--require-complete` to refuse a bundle while decisions are pending. With the
current configuration that command must fail before publishing any output.

Bundle validation checks every generated file, receipt/manifest agreement,
configuration, executable code, reference documents and accessible source hashes.
It re-derives dataset decisions and upstream claims from the pinned inputs,
checks the complete verification scope, and reconciles generated limitations
and evidence tables. Rehashing a forged receipt cannot authorize physical-byte,
historical-execution or inference verification claims. Completed decisions additionally require a readable, hash-bound structured
approval document whose dataset, status, outcome, reference and canonical
summary agree with configuration, record and evidence. See the decision schema
in [reporting decisions](cross_dataset_reporting_decisions.md).

Validation re-renders every table, Markdown document and SVG from the pinned
inputs, then compares their complete contents and the complete output inventory.
A separate cell checker derives policy/resource/metric mappings directly from
the authoritative CSVs and checks all 399 unique source metric cells, their 518
rendered metric rows (including resource-table copies), and 8 conclusion values.
Values must match the exact pandas-decoded source value, including structural
nulls; there is no numerical tolerance, imputation or new scientific computation.
Denominators, population/group counts, units, source rows/columns and hashes are
reconciled independently. Canonical comparisons also cover source inventories,
Markdown tables and figures. Repairing receipts cannot authorize changed values.

Executable provenance is derived from the actual generator, imported capability
module, reporting validators and approved Task 8 CSV-contract module. Complete
roles, paths, hashes, effective profiles and reference-document inventory must
match. Reporting-code validation does not attest the historical model execution
commit or its physical artifacts; those retain their existing evidence limits.

Final manifests and receipts use the same closed, typed schema during generation
and standalone validation. Undeclared properties are rejected recursively,
including environment, verification scope, decision rows, metric receipts,
executable/profile objects, source/output references and inherited Task 8 receipt
metadata. Existing optional configuration fields and nullable Task 8 git-state
fields remain supported. The schema module itself is hashed as reporting code.
Duplicate JSON properties and non-JSON numeric constants are rejected on reading.

The only extension container is optional `unverified_annotations`, with exactly
`{"scope": "unverified", "notes": ["operator note"]}`. It may be configured at
report or dataset scope. Report-level notes are copied consistently into both
receipt and manifest; they cannot introduce nested status/verification fields or
change authoritative statements. Notes are not rendered as scientific evidence.

Configuration `reason` and annotation fields are retained as unverified operator
notes in the embedded configuration. They are excluded from authoritative report,
status and limitations text. Reviewed dataset context and validated decision and
evidence state supply that text. Useful scientific explanations and the exact
Task 8 UNVERIFIED disclosures remain visible; free-form notes cannot override them.

Canonical validation renders reporting figures but does not publish files, train
models, read target Parquet values or invoke a frozen evaluator. Exact SVG
validation uses the executing plotting environment; cross-environment byte
reproduction remains unverified. This is reporting consistency validation, not
independent validation of historical scientific experiments.
The artifact manifest covers all other files; it deliberately does not hash itself.

## Reproducibility environment

Minimum dependencies are in `requirements.txt`; record the environment actually
used in `report_provenance.json` rather than claiming an untested clean install.
Python, pandas, NumPy, PyArrow and Matplotlib versions are recorded. Executed
generator, helper modules, Task 8 CSV contract and capability definitions are
hashed independently of the selected input-artifact root.

Two runs with identical sources, code and environment must be byte-identical.
Cross-environment SVG equality is not guaranteed: fonts and plotting libraries
can differ. A fresh environment must be tested separately before claiming that
specific environment reproduces these bytes. Package installation is not part
of the reporting command.

The November 15 scientific environment differs from `requirements-lock.txt`.
That discrepancy and the dirty Task 8 reporting tree are preserved as upstream
limitations; this PR does not rewrite a historical environment or lock file.

## Evidence boundaries

- Published metadata consistency and published CSV bytes are independently checked.
- External Task 4/6 Parquet, models and predictions are **UNVERIFIED by this reporting
  run**. Their expected hashes are retained through the pinned upstream manifest.
- Task 4 test-value isolation/consistency and Task 7 inference reproduction retain
  Task 8's exact UNVERIFIED disclosures.
- Integer-one operation counts are recorded evidence supported by the approved
  upstream implementation, not independent observation of historical execution.
- November 10 byte equivalence is UNVERIFIED without both physical bundles.
- Earlier run-history reconciliation remains a Task 8 follow-up.

Do not commit large datasets or model files. If physical evidence is later supplied,
record the actual immutable location/version, size, hash, access instructions and
which bytes were inspected. No accessible location or successful download is
invented here, and this workflow does not silently fetch external artifacts.

## Metric contracts and interpretation

Utilization is a fraction in `[0,1]`, violation a percentage in `[0,100]`, waste
and shortfall carry dataset-specific resource units. Valid-count denominators
are preserved and checked; absent source waste/shortfall counts remain explicitly
unreported. Coverage and legacy slack reduction are not inferred.

Google reports occurrence CPU/memory peaks in `ncu`/`normalized`. Alibaba reports
memory peaks in `gb`, then CPU lifetime-average sizing in `percent_of_vcpu`, labeled
"average-usage sizing, not peak safety". Alibaba's exact five sensitivities include
complementary same-second populations and policy-independent group counts.
Structural nulls are validated, not filled with invented values.

Azure and Alibaba 2018 receive scope statements, no invented scores. Policy
ordering and source values are shown within datasets only; no cross-dataset
accuracy or CPU ranking is valid.

## Tests

```bash
python -m pytest -q tests/test_final_cross_dataset_report.py \
  tests/test_cross_dataset_provenance.py \
  tests/test_cross_dataset_summary_validation.py \
  tests/test_cross_dataset_final_reporting.py \
  tests/test_verify_alibaba_gpu_2020_artifacts.py \
  tests/test_task8_upstream_metadata_contract.py
python -m pytest -q
git diff --check
git diff --check origin/main...HEAD
```

The full suite has tests requiring ignored Google occurrence artifacts. Missing
artifacts must be reported as environmental failures, not silently deselected.
No training or real final-evaluation command is required for reporting validation.
