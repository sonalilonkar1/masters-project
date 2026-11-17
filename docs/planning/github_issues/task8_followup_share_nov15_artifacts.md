# [P1] Task 8 Follow-up: Share the Nov 15 Alibaba GPU 2020 Run Artifacts

**Labels:** `area-data`, `priority-high`
**Owner:** Task 8 owner (holds the authoritative run's files)
**Related:** PR #121 (merged 2026-11-16), Task 15 (`task15_recommendation_backend_api.md`)

---

## Objective

Share the per-run Parquet files of the authoritative Alibaba GPU 2020 run so other team members can rebuild, verify and use it. PR #121 committed the checksums, run records and summary CSVs, but `data/processed/*` is git-ignored, so the files themselves are only on the machine that ran Tasks 4–7. The PR #121 review already noted that "some physical artifacts remain unavailable for independent verification".

## Authoritative Run

| Item | Value |
|---|---|
| Final run ID | `4fdc7e96-789b-43a9-990f-20f189e9598b` |
| Decision manifest | `d36964c09c903af646f29929d363d0ccb6ccf60674f31054ed8dfac9dff527ac` |
| Task 7 execution commit | `ea6aa08` |
| Reference checksums | `reports/results/alibaba_gpu_2020/verification/artifact_manifest.json`, `final_test/run_record.json` |

## Folders to Share

| Folder under `data/processed/` | Stage | Needed by |
|---|---|---|
| `alibaba_gpu_v2020_targets/` | Task 4 | Task 15 export (start times, test rows) |
| `alibaba_gpu_v2020_baselines/` | Task 6 | Task 15 export (`uses_history_*` flags, history counts) |
| `alibaba_gpu_v2020_ml/` | Task 7 PR 1 | Independent verification |
| `alibaba_gpu_v2020_final_test/` | Task 7 PR 2 | Task 15 export (`final_test_predictions.parquet`) |

`alibaba_gpu_v2020/` (Task 3 canonical) is not needed: the shared Task 3 build already matches the manifest.

## Current Mismatch

Checked 2026-11-16 on a teammate's machine holding the Oct 30 run: of the 31 files in `artifact_manifest.json`, 8 match (all 5 Task 3 files, 2 Task 6 validation CSVs, `feature_order.json`), 23 differ and 0 are missing.

## Acceptance Criteria

- [ ] The four folders are uploaded to the team Drive (same place as the Task 3 handoff), with their `SHA256SUMS`.
- [ ] After download, every file listed in `artifact_manifest.json` matches its `sha256` (31 of 31).
- [ ] The Drive link and the date are recorded in this file or the GitHub issue.

## Unblocks

- Task 15 final (verified) UI bundle for Alibaba, and the re-check of the latest-recommendation fallback count (19,341 of 25,232 on the Oct 30 files).
- Task 16 final screenshots.
- Independent re-verification of PR #121.
