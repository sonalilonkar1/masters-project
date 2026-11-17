# Task 15 Implementation Plan: Risk Levels, UI Export and Read-Only API

**Status:** Steps 1–14 done (2026-11-16); the bundle uses zstd Parquet (about 13 MB, under the 20 MB commit limit). Remaining: step 15, the verified bundle, waiting on #130; the single PR opens after it. Delete this file when Task 15 is complete.
**Branch:** `feature/task15-backend` (one PR for all of Task 15)
**Issue:** Task 15 (`task15_recommendation_backend_api.md`), Parts A–E. Column lists and endpoint details are in the issue and are not repeated here.

## Files

| Part | File | Purpose |
|---|---|---|
| A | `src/service/contract.py` | The bundle format fixed in one place: columns, types, nullability, target-status and basis values, policy names, dataset IDs, units, semantics, API error format |
| A | `config/ui_risk_levels.json` | Risk levels mapped per dataset: Restrictive → Hybrid (default), Balanced → P95, Efficient → P90 |
| A | `src/service/risk_levels.py` | Load and validate the risk-level config |
| B | `src/service/export.py` | Export logic as small pure functions, testable on synthetic data |
| B | `scripts/export_ui_artifacts.py` | Thin CLI: `--out-dir`, `--allow-dirty`, `--force`, `--allow-unverified-source` |
| C | `src/service/bundle.py` | Verify `SHA256SUMS`, load once, index by `(dataset, workload_id, policy)` |
| C | `src/service/schemas.py`, `src/service/api.py` | Response models and the FastAPI app under `/api/v1`, `GET` only |
| C | `docs/design/recommendation_api_openapi.json`, `scripts/export_openapi.py` | OpenAPI contract generated from the app on the fixture bundle, for Task 16 |
| D | `tests/test_ui_contract.py`, `tests/test_ui_risk_levels.py`, `tests/test_ui_export.py`, `tests/test_ui_fixture_bundle.py`, `tests/test_api.py`, `tests/ui_sources.py` | Tests on synthetic inputs and the fixture bundle; no pipeline data needed |
| D | `tests/fixtures/ui_bundle/`, `tests/fixtures/make_ui_bundle.py` | Small synthetic bundle covering both datasets and every edge case in the issue |
| D | `requirements.txt`, `requirements-lock.txt` | Add `fastapi`, `uvicorn`, `httpx2` (Starlette's test client; `httpx` stays for Jupyter) |
| E | `README.md` | Obtain inputs, export (verified and development), start the API, run tests, regenerate OpenAPI |

## Build Order

| Step | Work | Check before moving on |
|---|---|---|
| 1 | `contract.py`: dataset IDs, policy names and IDs, units, semantics, bundle columns, nulls, allowed values, error format | Contract tests |
| 2 | `ui_risk_levels.json` and its loader | Loads; rejects unmapped levels, unknown policies, Mean and ML |
| 3 | Strict source verification | Matching, mismatching and missing inputs; wrong Alibaba `run_id` or manifest hash; development mode records `source_mismatches` |
| 4 | Google export | Hybrid equals stored on all 259 scored rows; latest rows one per workload |
| 5 | Alibaba export | One-to-one joins on `role_key`; latest rows one per workload |
| 6 | Validation | Row counts, nulls kept, copied values equal the source, basis per resource and policy, fallback counts per resource |
| 7 | Write through a staging folder | Failure leaves nothing behind; `--force` replaces only after success |
| 8 | Checksums | `SHA256SUMS` covers every file except itself; changed, missing or extra files detected |
| 9 | Fixture bundle | History, fallback, no scored run, nulls, differing CPU/memory bases and statuses |
| 10 | Bundle loader | Refuses a bad bundle; index includes the dataset |
| 11 | API and response schemas | API tests on the fixture bundle |
| 12 | OpenAPI contract | Generated file committed and matches the app |
| 13 | Dependencies and README; full test suite | All tests pass |
| 14 | Development bundle from local data | Google `verified`; Alibaba `development` until the Nov 15 files arrive |
| 15 | Verified bundle | After `task8_followup_share_nov15_artifacts.md` is done; all inputs match |

## Source Verification

Two kinds of input, checked differently:

| Dataset | Git-ignored inputs: SHA-256 must match the committed reference | Committed inputs: pinned by the Git commit, recorded in `metadata.json` |
|---|---|---|
| Google | `google_subset_v1/test_occurrences.parquet`, `google_subset_v1/test_ml_predictions.parquet` (reference: `decision_manifest.json` `input_sha256`) | `reports/results/google_subset/decision_manifest.json`, `tables/final_test_policy_comparison.csv`, `final_test_run_metadata.json` |
| Alibaba | `alibaba_gpu_v2020_final_test/final_test_predictions.parquet`, `final_test/run_record.json`, `alibaba_gpu_v2020_targets/test.parquet`, `alibaba_gpu_v2020_baselines/recommendations_test.parquet` (reference: `verification/artifact_manifest.json`, `final_test/run_record.json`) | `verification/artifact_manifest.json`, `final_test/run_record.json`, `final_test/final_test_policy_comparison.csv`, `ml/decision_manifest.json`, `baselines/baseline_selection.json` |

- **Same run:** Alibaba inputs are tied together by the local `run_record.json` matching the committed `run_id` and `decision_manifest_sha256`, with both test counters equal to 1. Both Google inputs are pinned by the one `input_sha256` block of the decision manifest.
- Reference values are read from the committed files at export time, never hard-coded.
- Files used only for checks (for example Google `final_test_row_level.parquet`) are listed in `metadata.json` with their checksums.

## Verified and Development Bundles

| | Default (verified) | `--allow-unverified-source` (development) |
|---|---|---|
| Inputs | Must all match | Mismatches allowed and listed |
| Default output | `reports/results/ui/` | `data/processed/ui_dev/` (git-ignored) |
| Output inside `reports/` | Allowed | Refused |
| Metadata | `bundle_status: verified`, empty `source_mismatches` | `bundle_status: development`, every mismatch listed |
| Use | Commit, screenshots, report | Local development only; never screenshots or figures (README warning) |

`/health` reports `bundle_status` and the number of source mismatches.

## Other Rules

- **Fallback counts:** counted separately for CPU and memory on the latest rows, and compared with the counts from the source `uses_history_*` flags. Known values (Google CPU 231 and memory 233 of 472; Alibaba CPU 19,342 and memory 19,341 of 25,232 on the Oct 30 files) are used only in real-data checks, not in code.
- **Checksums:** `SHA256SUMS` lists every bundle file except itself. The API refuses to start if a listed file is missing or changed, or if an unlisted file is present.
- **Staging:** a hidden folder next to the output, so the rename stays on the same disk. Order: write all files, validate, write checksums, rename. Any failure deletes the staging folder. With `--force`, the old output is moved aside and deleted only after the new one is in place.
- **API index:** `(dataset, workload_id, policy)`.

## Choices

| Choice | Decision |
|---|---|
| Dataset IDs | `google_clusterdata2019` and `alibaba_gpu_v2020`, as in the capability profiles and Task 12 |
| Policy names | Summary-CSV names (`Request` … `Hybrid`) in the bundle; lowercase `policy_id` in the API |
| Risk-level config | One mapping per dataset, even though both are the same today |
| API framework | FastAPI with Uvicorn; OpenAPI generated by FastAPI |
| CORS | Not enabled; added only if Task 16 chooses a separate frontend server |

## Review Corrections Applied (2026-11-16)

| # | Point | Outcome |
|---|---|---|
| 1 | CLI flags | One flag, `--allow-unverified-source`; development output refused inside `reports/`. `--final` was already removed from Task 15; removed from Task 16 |
| 2 | API index | `(dataset, workload_id, policy)` |
| 3 | Fix the format first | `contract.py` as step 1 |
| 4 | Fallback per resource | CPU and memory counted and checked separately (they differ: 231/233, 19,342/19,341) |
| 5 | Source files | Table above, split into git-ignored and committed inputs |
| 6 | Development status | `bundle_status` plus `source_mismatches`; no second boolean |
| 7 | Checksum scope | Every file except `SHA256SUMS`; extra files refused |
| 8 | Staging | Same parent folder; nothing left on failure |
| 9 | `workloads.parquet` columns | Already in the issue; fixed in `contract.py` |
| 10 | Risk config per dataset | Kept per dataset |
