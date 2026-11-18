# Task 12 reporting decisions

This file records evidence availability, not new team approval. Task 12 PR 2
does not authorize scientific reruns or make unresolved project decisions.

| Dataset | Documented evidence | Final reporting decision |
|---|---|---|
| Google subset | Existing frozen results; Task 10 still requires correction or an explicit decision to retain earlier results | `decision_pending`; display existing results provisionally with F3/F4 contamination and F7/F8 limitations |
| Azure VM | Feasibility study; no supplied Stage 2 results or formal go/stop outcome | `decision_pending`; feasibility evidence only; no evaluation scores |
| Alibaba 2018 | Adapter code exists; Task 9 has no supplied demonstration outcome | `decision_pending`; scope evidence only; no recommendation results |
| Alibaba GPU 2020 | Task 8 PR #121 merged with the published November 15 run | Use the authoritative published run for reporting, retaining upstream limitations and follow-ups |

Sources: `docs/planning/github_issues/task10_google_subset_corrections_and_rerun.md`,
`task11_azure_vm_dataset_integration.md`, `task9_alibaba_2018_adapter_demonstration.md`,
`docs/data/azure_vm_traceadvisor_feasibility.md`, and
`docs/design/discussion_summary_2026-11-16.md`.

Each dataset has a structured record in `config/reporting_decisions/`, selected
by `decision_record` in the final configuration. Records identify the dataset,
status, dataset-specific outcome, summary and SHA-256 of a structured evidence
file. Configuration, record and evidence must agree. The current evidence files
explicitly record absence of approval for the three pending datasets; they are
not approval documents.

To finalize a pending dataset, an owner must supply actual documented approval,
record its reference in the structured evidence, and update the record and
configuration together. The configured `decision_evidence` must name exactly the
structured record’s hashed evidence file; background planning prose cannot serve
as an alternate approval citation. Supported documented treatments are Google
`retain_provisional`, Azure `feasibility_only`, and Alibaba 2018 `deferred`.
A correction with new Google results requires a separate authoritative input
integration; changing a decision flag cannot manufacture those results.
Completed records use the canonical summary
`Documented reporting outcome for <dataset_id>: <outcome>.` in configuration,
record, evidence `basis`, and approval document. Pending or arbitrary prose is
not accepted as a completed summary.

`approval_reference` must be a readable repository-relative JSON document. Its
exact fields are `schema_version` (integer 1), `dataset_id`, `status`
(`documented_outcome`), `outcome`, `approval_reference` (its own relative path),
and `summary` (the canonical summary). The path must agree in configuration,
record and evidence. The document's SHA-256 must agree with `approval_sha256`
in both record and evidence. Reading it adds its bytes to the provenance source
inventory. A reference string alone, missing file, pending document or mismatched
identity cannot satisfy completion. These schema rules do not create approvals;
an owner must supply actual approval before changing any real pending record.

The validator checks consistency and hashes, not the identity or authority of
the person approving a decision. Human review of approval remains necessary.
Pending evidence cannot satisfy `--require-complete`, even when relabeled in
configuration. Completed-state tests use synthetic evidence only.

Until then a valid reporting bundle has `reporting_validation: PASS` but
`reporting_status: DECISION_PENDING` and `project_completion: false`.

The separate Task 8 follow-ups concerning earlier run history, the execution
environment versus the lock file, and manuscript updates remain open. This PR
neither repairs frozen evidence nor treats those follow-ups as completed.

Configuration annotations are not decision evidence or verification claims. They
are preserved for maintainers in configuration but excluded from authoritative
rendered reporting; validated state and reviewed scientific context determine
completion, evidence and limitation wording.

Final metadata is closed recursively: unknown approval/completion/verification
properties are invalid even if receipt hashes are repaired. Optional notes belong
in `unverified_annotations` (`scope: unverified`, `notes: [string, ...]`), never in
new authoritative fields. These notes do not change approval or completion state.
