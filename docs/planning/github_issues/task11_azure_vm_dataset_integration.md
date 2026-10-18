# [P4] Task 11: Azure Virtual-Machine Dataset Integration

**Labels:** `area-data`, `priority-low`

**Owner:** Unassigned

**Priority:** Priority 4 (lowest) · Future integration · Lower than the complete Alibaba GPU 2020 pipeline, the optional Alibaba 2018 demonstration and the Google corrections. Not on the critical path.

---

## Objective

Determine whether the Azure public VM trace can support a valid TraceAdvisor experiment, and only if it can, plan and implement the adapter views and evaluation it supports. The task begins with an inspection and feasibility stage and stops if the data cannot support a valid experiment.

**No assumption is made that Azure supports the recurrence or next-occurrence experiment used for Alibaba GPU 2020.**

## What This Task Builds

- **Stage 1 (always):** a feasibility report on dataset identity, fields, semantics, recurrence and evaluation options, ending in a go or stop decision.
- **Stage 2 (only after a go decision):** the required adapter views, capability profile, exclusions, tests and artifacts.

## What This Task Does Not Build

- An invented recurrence key or next-occurrence targets.
- Observed memory values (not provided by the trace).
- Any change to Alibaba GPU 2020, Alibaba 2018 or Google behavior.

## Current Project State

- `src/adapters/azure_vm.py` (`AzureVMAdapter`, 0.1.0) exists:
  - VM lifecycle and capacity view (`adapt_vm_table`, `instance` rows) and a five-minute CPU interval view (`adapt_cpu_readings`, `interval` rows);
  - open-ended capacity buckets (for example `>24`) keep a null value, an open-ended flag and a lower bound;
  - observed memory is never populated.
- Registered profile `azure_public_vm_v2`: `supports_request = false`, `supports_recurrence = false`, `supports_targets = false`, `supports_observed_memory = false`, allocated CPU and memory supported.
- **Dataset identity is unresolved:** the adapter docstring says "Azure 2019 Public Dataset V2", while adapter framework §9.4 says the available data is V1 (2017).
- Locally, `data/raw/azure/` contains `2023Dataset/AzureLLMInferenceTrace_*.csv` and processed LLM-inference windows, and an empty `2021Dataset/`. No VM trace file was found there.
- Earlier study (`docs/data/old_dataset_semantics_alibaba2018_azure.md` §3.6): no explicit recurring identity; subscription and deployment-shape signals are pattern evidence, not identity; CPU history or replay is feasible; next-occurrence semantics stay unsupported.
- Tests: `tests/test_azure_vm_adapter.py`.

## Relationship to PR #70 and Tasks 1–5

| Item | Relationship |
|---|---|
| PR #70 follow-up | Azure profile uses defaults and is not edited; any change is a Stage 2 decision |
| Task 1 | Stage 2 adapter work would use the framework |
| Tasks 2–4 | Not used (Alibaba GPU 2020 only) |
| Task 5 | Stage 2 evaluation would use the profile-aware evaluator |

## Scope

- Dataset: Azure public VM trace (version to verify).
- Stage 2 scope is defined only by the Stage 1 decision.

## Dependencies

- Tasks 1–8 complete (Alibaba GPU 2020 verified).
- Recommended after Task 10 by priority.
- Access to the correct Azure VM trace files.

## Parallel Work

- Stage 1 can run in parallel with Task 9, Task 10 and Task 12 script development.
- Never blocks another task.

## Blocks

- None. Task 12 records the outcome.

## Detailed Implementation Tasks

### Stage 1: Inspection and Feasibility

- [ ] **Dataset version and source:** identify V1 (2017) or V2 (2019), source URL and checksums; reconcile the adapter docstring with framework §9.4.
- [ ] **Tables and fields:** list tables, columns, types, row counts.
- [ ] **Timestamp semantics:** units, origin, created and deleted times, reading interval.
- [ ] **Identity:** subscription, deployment, VM, and whether any task or instance concept exists.
- [ ] **Resource fields:** requests (none expected), capacity buckets, CPU readings (min, max, average), memory capacity.
- [ ] **CPU and memory semantics:** what each CPU reading means; confirm no observed memory.
- [ ] **Missingness and lifecycle status:** VMs without readings, open-ended lifetimes, truncated windows.
- [ ] **Recurrence:** whether an official recurrence identity exists.
- [ ] **Next-occurrence targets:** whether they can be built without inventing recurrence.
- [ ] **Evaluation options:** whether only capacity-versus-observed CPU or history/replay evaluation is feasible.
- [ ] **Decision:** go (with the supported experiment named) or stop.

### Stop Conditions

Stop and report Azure as future work if any of these hold:

- [ ] The dataset version cannot be verified.
- [ ] No resource field can be compared with an observed value in the same unit and scope.
- [ ] The only route to targets is an invented recurrence key.
- [ ] Required trace files are unavailable.

### Stage 2: Integration (only after a go decision)

- [ ] **Adapter views:** confirm or extend the `instance` and `interval` views through the Task 1 framework.
- [ ] **Capability profile:** record supported record levels, units, semantics and evaluation mode; keep recurrence and targets unsupported unless Stage 1 proved otherwise.
- [ ] **Exclusions:** define and document exclusion rules for incomplete lifecycles and missing readings.
- [ ] **Evaluation:** only the experiment named in the go decision, scored with the Task 5 evaluator.
- [ ] **Artifacts:** validated canonical output and metadata.

## Required Tests

- [ ] Existing `tests/test_azure_vm_adapter.py` passes unchanged in every stage.
- [ ] Stage 2: validation rejects populated observed memory and any recurrence or target fields that the profile does not support.
- [ ] Stage 2: open-ended capacity buckets are never converted to exact values.

## Acceptance Criteria

1. The feasibility report answers every Stage 1 item and ends in a go or stop decision.
2. On stop: Azure is recorded as future work with its open questions; no code changes.
3. On go: adapter views, profile, exclusions and tests are delivered for the named experiment only.
4. No recurrence is invented and no next-occurrence claim is made without official identity.
5. No Alibaba GPU 2020, Alibaba 2018 or Google change.

## Expected Outputs

- Feasibility report (location to confirm under `docs/data/`).
- Stage 2 only: adapter changes, profile, tests, validated artifacts and metadata.

## Data Leakage Controls

- No targets unless official identity exists; any Stage 2 history/replay evaluation uses only past readings.

## Schema and Adapter Boundaries

- Stage 1 changes no code.
- Stage 2 profile or schema changes require their own approved issue.

## Unresolved Decisions

| ID | Decision | Recommendation |
|---|---|---|
| D-1 | Which Azure version to use | Verify the available files first; use V2 only if V2 files are obtained, and record the result |
| D-2 | Whether Stage 2 is scheduled | Only after Stage 1 returns go and Tasks 9 and 10 are complete or deferred |

## Risks

- Azure may not support next-occurrence evaluation at all.
- The required VM trace files may not be available locally.
- Without observed memory, any Azure result is CPU-only.

## Pull-Request Boundary

- Stage 1: one documentation PR with the feasibility report.
- Stage 2: one PR per approved view or evaluation, opened only after a go decision.

## Handoff

- **Task 12:** the feasibility decision and, if Stage 2 ran, its validated outputs.

## Not in This Issue

- Invented recurrence or fabricated next-occurrence targets.
- Observed memory.
- Alibaba GPU 2020 (Tasks 1–8), Alibaba 2018 (Task 9) or Google (Task 10) work.

## References

- `src/adapters/azure_vm.py`, `tests/test_azure_vm_adapter.py`
- `docs/design/adapter_framework.md` §9.4
- `docs/data/old_dataset_semantics_alibaba2018_azure.md` §3
- `docs/data/old_adapter_analysis_alibaba2018_azure.md`
- `docs/design/canonical_workload_schema.md` §10
- `reports/dataset_analysis/azure_vm_traceadvisor_feasibility.md` (local, uncommitted)
- `docs/planning/data_integration_tasks.md` Task 10 (earlier numbering)
