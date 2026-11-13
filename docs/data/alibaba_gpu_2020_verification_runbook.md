# Alibaba GPU 2020 Final Verification Runbook

This runbook implements Task 8. It verifies frozen Task 3/4/6/7 outputs and does not rerun or retune the final test.

## Preconditions

Task 7 Phase 4 must already be complete. These local directories must exist:

```text
data/processed/alibaba_gpu_v2020/
data/processed/alibaba_gpu_v2020_targets/
data/processed/alibaba_gpu_v2020_baselines/
data/processed/alibaba_gpu_v2020_ml/
data/processed/alibaba_gpu_v2020_final_test/
```

The working tree should contain the exact code used to generate the frozen artifacts.

## Focused tests

```bash
python -m pytest tests/test_verify_alibaba_gpu_2020_artifacts.py -v
```

## Full regression suite

```bash
python -m pytest -q
```

No failures are allowed.

## Run verification

```bash
python scripts/verify_alibaba_gpu_2020_artifacts.py
```

If a previous verification output exists and should intentionally be regenerated:

```bash
python scripts/verify_alibaba_gpu_2020_artifacts.py --force
```

Outputs:

```text
reports/results/alibaba_gpu_2020/verification/artifact_manifest.json
reports/results/alibaba_gpu_2020/verification/verification_report.md
reports/results/alibaba_gpu_2020/verification/reproduction_metadata.json
```

## Expected interpretation

A failed verification is not repaired in Task 8. Return the failure to the owning task.

In particular, Task 8 requires explicit final-test evidence in the Task 7 run record:

```json
{
  "run_id": "...",
  "test_target_read_count": 1,
  "test_evaluator_call_count": 1
}
```

If the frozen Task 7 run record does not contain these fields, the verifier intentionally fails those checks. The evidence must be added by the Task 7 owner and the final-test provenance handled according to Task 7's documented rerun policy; Task 8 must not infer "exactly once" from missing metadata.

## Fresh-environment reproduction

Use a clean environment and the repository's normal dependencies plus its test dependencies.

Example:

```bash
python -m venv .venv-verify
source .venv-verify/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pytest
python -m pytest -q
python scripts/verify_alibaba_gpu_2020_artifacts.py --force
```

If the locked Alibaba models use XGBoost, install the exact version recorded in the Task 7 decision manifest before model-reload reproduction.

## Commit boundary

Commit only:

- verification script and tests;
- this runbook;
- generated verification manifest/report/reproduction metadata after a successful final verification.

Do not modify Task 3/4/6/7 pipeline behavior in this PR.

## PR #121 review clarifications

### Test-target access

Task 8 must not reopen Task 4 test target values. Parquet row counts are obtained
from Parquet file metadata only. Value-level checks on test targets (split isolation,
history timing and target consistency) are therefore not recomputed by Task 8; the
verification report labels them explicitly as unverified and relies on the frozen Task 4
checksum/metadata evidence for those items.

### Final-run provenance

The verifier cross-checks all of the following:

- the current `decision_manifest.json` SHA-256;
- `run_record.json` decision hash, run ID, timestamp and code commit;
- the matching entry in `data/processed/alibaba_gpu_v2020_ml/final_test_runs.jsonl`;
- uniqueness/documentation of any rerun IDs;
- the PR1 lock code commit against the final-run code commit;
- lock timestamp ordering.

Do not manually edit a verification report to reconcile provenance. Regenerate the
report against the authoritative frozen artifacts.

### Task 8 scope

Task 8 changes only verification/reporting files. Changes to Task 6/7 runners or
`src/models/alibaba_gpu_2020_final_test.py` belong in a Task 7 follow-up PR and should
be merged (or otherwise established as the frozen upstream implementation) before the
Task 8 report is regenerated.
