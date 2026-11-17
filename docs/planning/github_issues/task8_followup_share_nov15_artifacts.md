# [P1] Task 8 Follow-up: Share the Nov 15 Alibaba GPU 2020 Run Artifacts

**Labels:** `area-data`, `priority-high`
**Owner:** Unassigned (whoever holds the files of run `4fdc7e96`; most likely the person who ran Tasks 7 and 8 on Nov 15)
**Related:** PR #121 (merged 2026-11-16), Task 15 (`task15_recommendation_backend_api.md`)

---

## Objective

Upload the per-run files of the authoritative Alibaba GPU 2020 run to the team Google Drive so other team members can verify and use them.

PR #121 committed the checksums, run records and summary CSVs to `reports/results/alibaba_gpu_2020/`, but `data/processed/*` is git-ignored, so the Parquet files themselves are only on the machine that ran Tasks 4–7. The PR #121 review already noted that "some physical artifacts remain unavailable for independent verification". Copies on other machines are from the older Oct 30 run and do not match `main`.

## Authoritative Run

| Item | Value |
|---|---|
| Final run ID | `4fdc7e96-789b-43a9-990f-20f189e9598b` |
| Decision manifest | `d36964c09c903af646f29929d363d0ccb6ccf60674f31054ed8dfac9dff527ac` |
| Task 7 execution commit | `ea6aa08` |
| Reference checksums on `main` | `reports/results/alibaba_gpu_2020/verification/artifact_manifest.json`, `reports/results/alibaba_gpu_2020/final_test/run_record.json` |

## What to Upload

Upload these four folders from `data/processed/` **whole, with every file inside, unchanged**:

| Folder | Stage | Files that must be inside | Needed by |
|---|---|---|---|
| `alibaba_gpu_v2020_targets/` | Task 4 | `train.parquet`, `validation.parquet`, `test.parquet`, `metadata.json`, `SHA256SUMS` | Task 15 export: test rows and start times |
| `alibaba_gpu_v2020_baselines/` | Task 6 | `recommendations_{train,validation,test}.parquet`, `history_statistics.parquet`, `baseline_selection.json`, `metadata.json`, `validation_comparison.csv`, `sensitivity_validation.csv`, `SHA256SUMS` | Task 15 export: `uses_history_*` flags and history counts |
| `alibaba_gpu_v2020_ml/` | Task 7 PR 1 | `cpu_model.joblib`, `memory_model.joblib`, `decision_manifest.json`, `model_selection.json`, `feature_order.json`, `candidate_models.csv`, `validation_ml_hybrid_predictions.parquet`, `validation_policy_comparison.csv`, `metadata.json`, `final_test_runs.jsonl`, `SHA256SUMS` | Independent verification |
| `alibaba_gpu_v2020_final_test/` | Task 7 PR 2 | `final_test_predictions.parquet`, `final_test_policy_comparison.csv`, `final_test_sensitivity.csv`, `run_record.json`, `metadata.json`, `SHA256SUMS` | Task 15 export: ML and Hybrid predictions |

**Not needed:** `alibaba_gpu_v2020/` (Task 3 canonical). The Drive already has it in `CMPE 295A_B/alibaba_gpu_v2020_c2ae87f/`, and it matches `main`.

## Steps

1. **Check you have the right run.** From the repository root on the latest `main`:

   ```bash
   python3 -c "import json; r=json.load(open('data/processed/alibaba_gpu_v2020_final_test/run_record.json')); print(r.get('run_id'))"
   ```

   It must print `4fdc7e96-789b-43a9-990f-20f189e9598b`. If it prints anything else, or `None`, stop: these are not the agreed files.

2. **Check every checksum before uploading:**

   ```bash
   python3 - <<'EOF'
   import hashlib, json, pathlib
   m = json.load(open("reports/results/alibaba_gpu_2020/verification/artifact_manifest.json"))
   bad = 0
   for a in m["artifacts"]:
       p = pathlib.Path(a["path"])
       ok = p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() == a["sha256"]
       bad += not ok
       print("OK      " if ok else "MISMATCH", p)
   print(f"{len(m['artifacts']) - bad} of {len(m['artifacts'])} match")
   EOF
   ```

   It must end with `31 of 31 match`.

3. **Upload** to the shared Drive folder `CMPE 295A_B`, next to the Task 3 handoff, in one new folder named after the run:

   ```text
   CMPE 295A_B/
     alibaba_gpu_v2020_c2ae87f/            (existing, Task 3)
     alibaba_gpu_v2020_run_4fdc7e96/       (new)
       alibaba_gpu_v2020_targets/
       alibaba_gpu_v2020_baselines/
       alibaba_gpu_v2020_ml/
       alibaba_gpu_v2020_final_test/
   ```

   Upload the folders as they are. Do not rename, zip, convert or open-and-resave any file; Google Drive must not convert JSON or CSV files to Google Docs or Sheets.

4. **Post** the Drive link and the upload date as a comment on this issue.

5. **A second team member** downloads the four folders into their own `data/processed/` (after moving their old copies aside) and runs step 2. It must again print `31 of 31 match`. Record the result as a comment.

## If the Files No Longer Exist

Do **not** rerun the final test to recreate them. The final test is run once per locked decision set, and run `4fdc7e96` is the published result; a new run would be a third execution and would need its own disclosure. Raise it with the team instead, so the team can decide how Task 15 obtains its Alibaba rows.

## Current State on Other Machines

Checked 2026-11-16 on a teammate's machine holding the Oct 30 run: of the 31 files in `artifact_manifest.json`, 8 match (all 5 Task 3 files, the 2 Task 6 validation CSVs and `feature_order.json`), 23 differ and 0 are missing. The local `run_record.json` has no `run_id`.

## Acceptance Criteria

- [ ] Step 1 prints `4fdc7e96-789b-43a9-990f-20f189e9598b` on the uploader's machine.
- [ ] Step 2 prints `31 of 31 match` before upload.
- [ ] The four folders are in `CMPE 295A_B/alibaba_gpu_v2020_run_4fdc7e96/` with all files listed above.
- [ ] The Drive link and date are posted on this issue.
- [ ] A second team member downloads them and step 2 prints `31 of 31 match` on their machine.

## Unblocks

- Task 15 verified UI bundle for Alibaba, and the re-check of the latest-recommendation fallback counts (CPU 19,342 and memory 19,341 of 25,232 on the Oct 30 files).
- Task 16 final screenshots.
- Independent re-verification of PR #121.
