# Task 16 Recommendation Web UI Demo Script

## Pre-demo checks

1. From the repository root, start the verified bundle:
   ```bash
   uvicorn --factory src.service.api:create_app
   ```
2. Open `http://127.0.0.1:8000/`.
3. Confirm the header says **Bundle: verified** and there is no development-data warning.
4. Keep the API local and read-only; do not run any training or evaluation pipeline during the demo.

## 1. Google workload with history

1. Select **Google ClusterData 2019**.
2. Keep the default filter that shows workloads whose latest recommendation uses history.
3. Select a workload with the **history** badge.
4. Start on **Restrictive (Hybrid)** and point out:
   - recommended CPU and memory beside the original request;
   - per-resource basis and earlier-run count;
   - the rule description and safeguard;
   - dataset-wide policy evidence and bundle provenance.
5. Switch to **Balanced (P95)** and **Efficient (P90)**, then return to Restrictive. Explain that the risk mapping is configuration-driven and the UI does not calculate recommendations.
6. Scroll to **Workload history**. Explain that each point compares the recommendation made at run *i* with the usage of run *i + 1*, and that missing next-run actuals are never plotted as zero.

## 2. Alibaba workload with history

1. Switch to **Alibaba GPU 2020**.
2. Select a workload with the **history** badge.
3. Point out that **memory is displayed before CPU** and CPU is labelled **Average usage, not peak**.
4. Show all three risk levels and the per-resource basis/history counts.
5. Show the history charts and policy comparison.

## 3. Request-fallback case

Use the fixture bundle for this edge-case demonstration if a convenient verified-bundle workload is not known in advance:

```bash
TRACEADVISOR_UI_BUNDLE=tests/fixtures/ui_bundle \
uvicorn --factory src.service.api:create_app
```

1. Select Alibaba and enable **Show all workloads**.
2. Select `G||B`.
3. Show the request-fallback explanation and the message that all risk levels give the same answer until the workload has enough history.
4. Show the empty-history message: **No scored runs yet: this workload has not run again in the test period.**
5. Call out the yellow development-bundle warning; this fixture is for demoing edge states only and is not used for report figures.

## 4. Policy comparison

1. Return to the verified bundle before the final comparison view.
2. Select Google.
3. Show CPU and memory policy-comparison charts and tables for all seven policies.
4. Point out the Restrictive, Balanced and Efficient mappings and the Google-only any-resource violation view.
5. Emphasize that datasets are never combined or ranked against one another.

## 5. Close

Summarize that TraceAdvisor is an offline, historical replay system: the UI serves frozen, checksummed final-test results through a read-only API. It is not a live scheduler or live recommendation service.
