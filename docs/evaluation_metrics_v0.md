# Evaluation Metrics (v0) — TraceAdvisor

This document defines the v0 evaluation metrics for comparing TraceAdvisor to baseline recommenders using offline, time-aware trace replay.

## Notation
Each job execution `i` has:
- Requested resources: `req_cpu(i)`, `req_mem(i)`, `req_gpu(i)`
- Observed peak usage from traces: `peak_cpu(i)`, `peak_mem(i)`, `peak_gpu(i)`
- Recommended resources from a method: `rec_cpu(i)`, `rec_mem(i)`, `rec_gpu(i)`

Resources are evaluated per-dimension: CPU, memory, GPU (if applicable).

We evaluate over a set of executions `S` (e.g., validation/test window), with chronological ordering to avoid leakage.

## Slack (Over-provisioning)
Slack measures how much allocated resource exceeds observed peak usage.

Per execution and resource:
- Slack under original request:  
  `slack_req(i,r) = req(i,r) − peak(i,r)`
- Slack under recommendation:  
  `slack_rec(i,r) = rec(i,r) − peak(i,r)`

Interpretation:
- `slack > 0` indicates over-provisioning (waste)
- `slack < 0` indicates under-provisioning (would imply risk / violation)

For aggregate waste calculations, we count only positive slack:  
`waste_req(i,r) = max(0, slack_req(i,r))`  
`waste_rec(i,r) = max(0, slack_rec(i,r))`

## Violations (Risk Proxy)
A violation occurs when observed peak usage exceeds the recommended allocation.

Per execution and resource:
- `viol(i,r) = 1` if `peak(i,r) > rec(i,r)`, else `0`

Any-resource violation:
- `viol_any(i) = 1` if any `viol(i,r) = 1` across resources (CPU/mem/GPU), else `0`

Note: this is a conservative proxy for resource exhaustion events (e.g., OOM/eviction). We use it because "fit within recommended resources" is directly observable from traces.

## Violation Rate
Per resource:  
`VRate_r = (1/|S|) * sum_{i in S} viol(i,r)`

Any-resource:  
`VRate_any = (1/|S|) * sum_{i in S} viol_any(i)`

## Slack Reduction (%)
Slack reduction measures how much over-provisioned capacity is reduced compared to current practice (as-is requests).

Total waste under original requests:  
`TotalSlack_req(r) = sum_{i in S} max(0, req(i,r) − peak(i,r))`

Total waste under recommendations:  
`TotalSlack_rec(r) = sum_{i in S} max(0, rec(i,r) − peak(i,r))`

Slack reduction:  
`SlackReduction_r(%) = 100 * (TotalSlack_req(r) − TotalSlack_rec(r)) / (TotalSlack_req(r) + eps)`

Where `eps` is a small constant (e.g., `1e-9`) to avoid division by zero.

We report SlackReduction separately for CPU, memory, and GPU (if available).

## Tiered Reporting (Confidence Tiers)
Each execution belongs to a confidence tier: **high / medium / low**

Tier assignment is produced by the recurrence/history module (based on history volume and stability).

For each evaluation run, we report:
1. Overall (all tiers combined)
2. High tier only
3. Medium tier only
4. Low tier only

For each tier block we report:
- number of executions (`n`)
- violation rates: `VRate_any` and `VRate_r` (CPU/mem/GPU)
- slack reduction: `SlackReduction_r` (CPU/mem/GPU)

## v0 Output Tables (minimum)
For each method (Baseline 0/1/2/3 and TraceAdvisor), we will produce:
- A summary table with `SlackReduction_cpu`, `SlackReduction_mem`, `SlackReduction_gpu` (if available)
- `VRate_any`, `VRate_cpu`, `VRate_mem`, `VRate_gpu` (if available)
- The same table stratified by confidence tier (high/med/low)
