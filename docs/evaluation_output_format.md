\# Evaluation Output Format (v0) — TraceAdvisor

This document defines the v0 output artifacts produced by the offline evaluator.  
All methods (Baseline 0/1/2/3 and TraceAdvisor) must use the same output schema to ensure fair comparisons.

\#\# Output Artifacts (minimum)

\#\#\# 1\) Per-execution results (recommended for debugging)  
\*\*File:\*\* \`reports/eval/per\_execution\_\<method\>\_\<split\>.csv\`

Purpose: record the recommendation, observed peak, and violation/slack outcomes for each execution. Useful for debugging anomalies and producing plots.

Required columns:  
\- \`execution\_id\` : unique ID for a job execution/run  
\- \`recurring\_job\_id\` : stable recurring job grouping key  
\- \`timestamp\` : submission time or execution start time used for chronological ordering  
\- \`confidence\_tier\` : {high, medium, low}

Observed (ground truth from traces):  
\- \`peak\_cpu\`  
\- \`peak\_mem\_gb\`  
\- \`peak\_gpu\` (optional; include if available)

Requests (status quo):  
\- \`req\_cpu\`  
\- \`req\_mem\_gb\`  
\- \`req\_gpu\` (optional)

Recommendations (method output):  
\- \`rec\_cpu\`  
\- \`rec\_mem\_gb\`  
\- \`rec\_gpu\` (optional)

Slack values:  
\- \`slack\_req\_cpu\` \= req\_cpu \- peak\_cpu  
\- \`slack\_req\_mem\_gb\` \= req\_mem\_gb \- peak\_mem\_gb  
\- \`slack\_req\_gpu\` (optional)

\- \`slack\_rec\_cpu\` \= rec\_cpu \- peak\_cpu  
\- \`slack\_rec\_mem\_gb\` \= rec\_mem\_gb \- peak\_mem\_gb  
\- \`slack\_rec\_gpu\` (optional)

Waste values (positive slack only):  
\- \`waste\_req\_cpu\` \= max(0, slack\_req\_cpu)  
\- \`waste\_req\_mem\_gb\` \= max(0, slack\_req\_mem\_gb)  
\- \`waste\_req\_gpu\` (optional)

\- \`waste\_rec\_cpu\` \= max(0, slack\_rec\_cpu)  
\- \`waste\_rec\_mem\_gb\` \= max(0, slack\_rec\_mem\_gb)  
\- \`waste\_rec\_gpu\` (optional)

Violation indicators (binary):  
\- \`viol\_cpu\` \= 1 if peak\_cpu \> rec\_cpu else 0  
\- \`viol\_mem\` \= 1 if peak\_mem\_gb \> rec\_mem\_gb else 0  
\- \`viol\_gpu\` (optional)  
\- \`viol\_any\` \= 1 if any resource violation else 0

Optional columns (helpful later, not required for v0):  
\- \`n\_history\` : number of prior runs used for recommendation  
\- \`coverage\_target\` : e.g., 0.95  
\- \`margin\_param\` : configured margin/headroom used for this method

Notes:  
\- For GPU: if GPU is not available in the dataset subset, omit GPU columns consistently across all outputs.  
\- Keep memory consistently in GB to reduce confusion.

\---

\#\#\# 2\) Method summary (overall \+ tier breakdown)  
\*\*File:\*\* \`reports/eval/summary\_\<split\>.csv\`

Purpose: one table per evaluation run summarizing decision-quality metrics for each method.

Each row corresponds to one (method, tier) combination.  
Required columns:  
\- \`split\` : {validation, test}  
\- \`method\` : e.g., baseline0\_as\_is, baseline1\_percentile\_margin, baseline2\_jobclass, baseline3\_ml\_point, traceadvisor  
\- \`tier\` : {all, high, medium, low}  
\- \`n\_exec\` : number of executions evaluated in that tier

Violation rates:  
\- \`vr\_any\`  
\- \`vr\_cpu\`  
\- \`vr\_mem\`  
\- \`vr\_gpu\` (optional)

Slack totals:  
\- \`total\_slack\_req\_cpu\`  
\- \`total\_slack\_req\_mem\_gb\`  
\- \`total\_slack\_req\_gpu\` (optional)

\- \`total\_slack\_rec\_cpu\`  
\- \`total\_slack\_rec\_mem\_gb\`  
\- \`total\_slack\_rec\_gpu\` (optional)

Slack reduction (%):  
\- \`slack\_reduction\_cpu\_pct\`  
\- \`slack\_reduction\_mem\_pct\`  
\- \`slack\_reduction\_gpu\_pct\` (optional)

Calculation notes:  
\- totals should use waste (positive slack only) when computing slack reduction:  
  TotalSlack\_req(r) \= sum max(0, req \- peak)  
  TotalSlack\_rec(r) \= sum max(0, rec \- peak)

\---

\#\#\# 3\) Tradeoff sweep summary (optional in v0, required later)  
\*\*File:\*\* \`reports/eval/tradeoff\_\<method\>\_\<split\>.csv\`

Purpose: support risk–efficiency tradeoff curves by sweeping percentile or margin values.

Required columns:  
\- \`method\`  
\- \`split\`  
\- \`tier\` : {all, high, medium, low}  
\- \`sweep\_param\_name\` : e.g., percentile, margin, headroom  
\- \`sweep\_param\_value\` : e.g., 0.90 / 0.95 / 0.99  
\- \`n\_exec\`  
\- \`vr\_any\`  
\- \`slack\_reduction\_cpu\_pct\`  
\- \`slack\_reduction\_mem\_pct\`  
\- \`slack\_reduction\_gpu\_pct\` (optional)

\---

\#\# Naming Conventions  
Recommended method IDs:  
\- \`baseline0\_as\_is\`  
\- \`baseline1\_percentile\_margin\`  
\- \`baseline2\_jobclass\_multiplier\`  
\- \`baseline3\_ml\_point\_margin\`  
\- \`traceadvisor\_quantile\_calibrated\` (or \`traceadvisor\_v1\`)

Recommended split IDs:  
\- \`validation\`  
\- \`test\`

Recommended directory:  
\- \`reports/eval/\`

\---

\#\# Minimal v0 success criteria  
A v0 evaluation run is considered successful if it produces:  
1\) \`reports/eval/summary\_test.csv\` with all required columns, and  
2\) at least one per-execution CSV for debugging (recommended).
