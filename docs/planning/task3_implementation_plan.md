# Task 3: Alibaba GPU 2020 Adapter — Implementation Plan

**Issue:** #79 · **Schema version:** 0.2.0
**Status (2026-10-26):** Part A and Part B (B1–B7) are implemented and verified on the full source tables, including a final build from the clean committed tree (results doc §11.2).

This document tracks the work: steps, status, delivery and remaining items. **What the adapter does and why is in the design doc**, not here.

| Document | Role |
|---|---|
| `docs/design/alibaba_gpu_2020_adapter_design.md` (design) | How the adapter works: Part A and Part B steps, all design decisions, verification |
| `docs/design/alibaba_gpu_2020_output_contract.md` (output contract) | What Tasks 4, 6, 7 and 8 may rely on |
| `docs/data/alibaba_gpu_2020_source_data_checks.md` (checks report) | Verified properties of the source tables. **Cite for data validation** |
| `docs/data/alibaba_gpu_2020_adapter_results.md` (results) | Measured figures for Part A and Part B. **Cite for pipeline validation** |

---

## 1. Way of working

- One step at a time. Each step is proposed (what it changes and how), reviewed, recorded in the design doc, then implemented.
- Every step is tested on small fixtures and then run on the full tables, read-only, with each figure compared to an independent expectation. Measured figures go into the results doc.
- Code changes only the Task 3 adapter, its tests and the build script; the shared framework (`base.py`, `validation.py`, `schema.py`) is not changed.

## 2. Steps and status

| Step | Content | Design | State |
|---|---|---|---|
| A0 | Source data checks | Checks report | Done (2026-10-23) |
| S1 | Adapter class and profile | §3 | Done |
| A1–A7 | Joins, identity, inheritance, timestamps, rejection routing, linkage | §4 | Done (2026-10-24) |
| A8 | Part A tests | §7 | Done |
| B1 | Exclusion rules | §5.1 | Done (2026-10-25) |
| B3 | Resource mappings | §5.2 | Done (2026-10-25) |
| B4 | Role aggregation and scope | §5.3 | Done (2026-10-25) |
| B2 | Validity (built after B3 and B4) | §5.4 | Done (2026-10-25) |
| B5 | View assembly | §5.5 | Done (2026-10-25) |
| B6 | Metadata | §5.6 | Done (2026-10-25) |
| B7 | Build script, artifacts, count report, `SHA256SUMS` and `--verify` | §5.7 | Done (2026-10-26) |
| B8 | Part B tests | §7 | Done |

Build order for Part B: B1 → B3 → B4 → B2 → B5 → B6 → B7 (design §3).

## 3. Delivery

| Pull request | Content | State |
|---|---|---|
| Part A (`feature/task3-alibaba-gpu-2020-part-a`, "Part of #79") | Part A code, tests and docs | Open for review |
| Part B (`feature/task3-alibaba-gpu-2020-part-b`, "Closes #79") | B1–B7, design doc, results doc, contract updates | In progress; branched from Part A. Opened against `main` after the Part A PR merges (merge `main` into the Part B branch first) |

**After the Part B PR merges (data handoff):** pull `main`, run the build script once, put the five output files and `SHA256SUMS` on the team shared drive, and post the team message pointing to the output contract's "How to get the data" section. Teammates download and run `--verify` (little memory needed). Rebuilding takes about 12 minutes and needs 32 GB RAM to be reliable; 16 GB works only with heavy swap (output contract §3.1).

## 4. Remaining items

| Item | When |
|---|---|
| Memory follow-up (`docs/planning/github_issues/task3_followup_memory.md`) | After Task 3 merges; file the issue |
| Framework follow-up: restore `validation.py` docstrings | Optional, separate small change; not needed for Task 3 |
| Google data-preparation diagram | Later |
