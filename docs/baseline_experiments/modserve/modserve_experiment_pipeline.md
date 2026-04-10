# ModServe Baseline Experiment Pipeline

## 1. Purpose

This document describes the baseline experiment pipeline used for the ModServe-based phase of TraceAdvisor. The purpose of this phase is to establish a clear, reproducible evaluation framework using a **recent multimodal LLM-serving workload** that better reflects contemporary AI inference behavior than older general-purpose cluster traces. The current phase focuses on:  
1. reproducing the workload characterization style of the ModServe study,  
2. constructing a replay-ready interval dataset,  
3. implementing simplified provisioning baselines, and  
4. evaluating those baselines with consistent replay-based metrics. :contentReference[oaicite:0]{index=0}

This baseline phase is intended to create the methodological foundation that a later TraceAdvisor prediction model can reuse.

---

## 2. Why ModServe was chosen

ModServe was chosen because it is based on a **recent Azure multimodal inference trace** and therefore better reflects the characteristics of modern production LLM-serving workloads than older cluster datasets. The ModServe study shows that multimodal inference traffic exhibits **bursty arrival patterns**, **heavy-tailed request characteristics**, and strong differences between **text-only** and **image-text** requests. It also highlights that image-driven bursts create distinctive resource-management challenges that are not captured well by traditional batch-cluster traces. These properties make the ModServe trace a strong empirical foundation for studying resource-allocation baselines in a setting closer to current AI-serving systems. :contentReference[oaicite:1]{index=1}

In addition, ModServe is relevant to TraceAdvisor because it motivates **stage-aware resource management**. Rather than treating all inference demand as a single homogeneous workload, the paper shows that image and text stages have different performance characteristics and should be managed separately. This makes the dataset well suited for building provisioning baselines that later support a pre-execution advisory system. :contentReference[oaicite:2]{index=2}

---

## 3. Dataset used

We use the public Azure multimodal inference trace associated with ModServe. At the request level, the dataset contains the following fields:

- `TIMESTAMP`
- `NumImages`
- `ContextTokens`
- `GeneratedTokens`

These request-level fields are sufficient to reproduce the key workload analyses in the paper and to construct a simplified replay-based baseline evaluation pipeline. The ModServe study analyzes a one-week production multimodal inference trace and uses it to show that modern multimodal serving workloads are variable, bursty, and sensitive to the mix of image and text inputs. :contentReference[oaicite:3]{index=3}

---

## 4. What this phase is trying to reproduce

This phase does **not** attempt to reproduce the entire ModServe serving system, GPU cluster, or model-stage profiling infrastructure. Those parts depend on large-scale serving deployments and hardware-specific experiments that are outside the scope of the current baseline phase.

Instead, this phase reproduces the **most TraceAdvisor-relevant parts** of the ModServe experimental structure:

### 4.1 Workload characterization
We reproduce the trace-analysis style used in the paper:
- requests per minute,
- context tokens per minute,
- generated tokens per minute,
- images per minute,
- CDF of prompt length,
- CDF of images per request. :contentReference[oaicite:4]{index=4}

### 4.2 Stage-aware provisioning logic
We reproduce the conceptual distinction between:
- monolithic allocation,
- fixed decoupled stage allocation,
- and reactive decoupled stage allocation. :contentReference[oaicite:5]{index=5}

### 4.3 Burst-focused analysis
We reproduce a simplified version of the paper’s burst-oriented evaluation by selecting the burstiest test day and comparing baseline behavior during that interval. This is particularly relevant because the paper identifies image-driven bursts as one of the defining challenges of modern multimodal serving. :contentReference[oaicite:6]{index=6}

---

## 5. High-level pipeline

The full baseline pipeline is:

**Raw Azure multimodal trace**  
→ **cleaning and parsing**  
→ **workload characterization**  
→ **5-minute control-interval construction**  
→ **chronological train / validation / test split**  
→ **baseline provisioning policies**  
→ **replay evaluation**  
→ **test summary + burst-day summary**

This pipeline is designed to provide a structured experimental methodology in which workload analysis, baseline definition, and evaluation all connect through a single replay framework. :contentReference[oaicite:7]{index=7}

---

## 6. Notebook structure

The implementation is organized into three notebooks.

### Notebook 1: `01_modserve_trace_eda.ipynb`
Purpose:
- load the raw trace,
- clean and standardize the columns,
- create request-type indicators,
- reproduce the paper-style workload characterization plots.

Main outputs:
- cleaned request-level dataset,
- daily summary table,
- workload characterization figures.

### Notebook 2: `02_modserve_5min_windows_and_baselines.ipynb`
Purpose:
- aggregate request-level traffic into 5-minute intervals,
- create interval-level workload features,
- split the trace chronologically,
- define baseline provisioning policies.

Main outputs:
- replay-ready 5-minute dataset,
- baseline provisioning columns,
- metadata describing capacities and burst-day selection.

### Notebook 3: `03_modserve_replay_evaluation.ipynb`
Purpose:
- evaluate the baselines on validation and test,
- compute consistent replay metrics,
- run the burst-day comparison,
- save final tables and figures.

Main outputs:
- validation summary table,
- test summary table,
- burst-day summary table,
- evaluation figures.

---

## 7. Data preparation pipeline

### 7.1 Request-level cleaning
The request-level dataset is cleaned as follows:
- parse timestamps using UTC-aware datetime conversion,
- convert image/token fields to numeric,
- drop rows with invalid timestamps or invalid numeric fields,
- clip negative values to zero if necessary,
- sort all requests chronologically.

We then create request-type flags:
- `is_image_text = NumImages > 0`
- `is_text_only = NumImages == 0`

This reflects the same distinction used in the ModServe trace analysis between text-only and image-text traffic. :contentReference[oaicite:8]{index=8}

### 7.2 Time bucketing
Each request timestamp is rounded down to the nearest 5-minute boundary:

`window_start = TIMESTAMP.floor("5min")`

This creates the interval key used for replay. The choice of 5 minutes is motivated by the ModServe design itself: the system periodically reconfigures resources every five minutes. :contentReference[oaicite:9]{index=9}

### 7.3 Window-level aggregation
For each 5-minute interval, the following features are computed:
- `n_requests`
- `n_text_only`
- `n_image_text`
- `sum_context_tokens`
- `sum_generated_tokens`
- `sum_images`
- `mean_context_tokens`
- `mean_generated_tokens`
- `mean_images_per_request`

From these, we derive:
- `requests_per_min`
- `context_tokens_per_min`
- `generated_tokens_per_min`
- `images_per_min`
- `frac_image_text`

Empty 5-minute intervals are explicitly included and filled with zeros so the replay timeline is continuous.

---

## 8. Train / validation / test split

The interval-level dataset is split chronologically:

- **Train:** first 4 days
- **Validation:** day 5
- **Test:** days 6–7

This split creates a leakage-free evaluation setup while preserving enough early history for baseline calibration and enough unseen windows for final comparison. Even though this phase does not yet train the final TraceAdvisor model, the split is still useful because the **train** portion calibrates fixed provisioning levels, the **validation** portion checks that those settings behave reasonably, and the **test** portion is reserved for final baseline comparison.

---

## 9. Abstract service-unit formulation

Because the current phase does not reproduce the full ModServe serving system or GPU cluster, the pipeline uses **abstract service units** instead of real GPU counts.

Two capacities are defined from the training split:

- **image unit capacity**
- **text unit capacity**

These are estimated using the **median non-zero train load** for:
- `images_per_min`
- `context_tokens_per_min`

This provides a simple but consistent abstraction for replay experiments.

### Required units per window
For each 5-minute interval, required capacity is computed as:

- `req_image_units = ceil(images_per_min / image_unit_capacity)`
- `req_text_units = ceil(context_tokens_per_min / text_unit_capacity)`
- `req_total_units = req_image_units + req_text_units`

This follows the same high-level logic used in ModServe, where the number of instances is determined from stage-specific load divided by per-instance capacity. :contentReference[oaicite:10]{index=10}

---

## 10. Baseline policies

Three baseline provisioning policies are implemented.

### 10.1 Fixed Monolith
This baseline provisions the same **total capacity** for every 5-minute interval and does not distinguish between image and text load.

Calibration:
- fixed monolith units = 95th percentile of `req_total_units` on the train split

Interpretation:
- simple shared-pool baseline
- analogous to a monolithic serving strategy

### 10.2 Fixed Decoupled
This baseline provisions:
- a fixed image capacity
- a fixed text capacity

for every interval.

Calibration:
- fixed image units = 95th percentile of `req_image_units` on train
- fixed text units = 95th percentile of `req_text_units` on train

Interpretation:
- stage-aware structure
- but no dynamic adaptation over time

### 10.3 Reactive Decoupled
This baseline provisions each interval using the **previous interval’s observed demand**:
- current image provisioning = previous `req_image_units`
- current text provisioning = previous `req_text_units`

Interpretation:
- simple periodic reactive controller
- closest baseline to ModServe’s stage-aware periodic load adaptation without reproducing the full system

These three baselines reflect the main comparison structure that is most relevant to TraceAdvisor:
- no stage-awareness,
- static stage-awareness,
- and simple reactive stage-awareness. :contentReference[oaicite:11]{index=11}

---

## 11. Replay evaluation procedure

The baselines are evaluated using a replay-style interval simulation.

For each 5-minute window:
1. compute the required units from the observed workload,
2. compute the provisioned units according to the baseline policy,
3. compare provisioned units to required units,
4. record reliability and efficiency metrics.

This is a **trace-driven replay approximation inspired by ModServe**. It is not a full serving-system execution, but it provides a clean and reproducible framework for comparing provisioning policies under multimodal demand variation.

---

## 12. Evaluation metrics

The current prototype uses replay-based **resource and SLO proxy metrics**.

### 12.1 SLO-safe window rate
A window is considered **SLO-safe** if provisioned units are at least as large as required units.

For monolith:
- SLO-safe if `provided_total_units >= req_total_units`

For decoupled baselines:
- SLO-safe if both:
  - `provided_image_units >= req_image_units`
  - `provided_text_units >= req_text_units`

This is the main reliability metric.

### 12.2 Underprovision rate
Fraction of windows where the baseline provisions fewer units than required.

Interpretation:
- higher value means more risk
- lower value is better

### 12.3 Overprovision rate
Fraction of windows where the baseline provisions more units than required.

Interpretation:
- higher value means more waste
- lower value is better

### 12.4 Average underprovisioned units
Average shortfall across windows.

Interpretation:
- measures severity of failures

### 12.5 Average overprovisioned units
Average excess capacity across windows.

Interpretation:
- measures efficiency loss / waste

### 12.6 Average provisioned units
Average total units assigned by the policy.

Interpretation:
- proxy for resource cost

### 12.7 Peak provisioned units
Maximum units assigned in any window.

Interpretation:
- useful for comparing how baselines behave under bursts

These metrics were selected because they align well with TraceAdvisor’s safety-versus-efficiency framing while remaining compatible with a simplified replay approximation of stage-aware serving.

---

## 13. Burst-day experiment

In addition to validation and test summaries, the pipeline includes a focused **burst-day experiment**.

### Burst-day selection
The burstiest test day is selected by ranking test days using:
- peak `images_per_min`
- total images

The day with the highest image-driven burst is chosen.

### Burst-day analysis
For that day, the pipeline produces:
- workload plot:
  - `images_per_min`
  - `context_tokens_per_min`
- provisioning comparison plot:
  - required units
  - fixed monolith provisioned units
  - fixed decoupled provisioned units
  - reactive decoupled provisioned units
- burst-day summary table using the same replay metrics as above

This burst-day analysis is especially important because ModServe identifies image-driven bursts as a central systems challenge, and this is also the part of the paper that is most relevant to TraceAdvisor’s future pre-execution advisory role. :contentReference[oaicite:12]{index=12}

---

## 14. Main outputs

### Tables
- `modserve_val_baseline_summary.csv`
- `modserve_test_baseline_summary.csv`
- `modserve_burst_day_summary.csv`
- `modserve_baseline_metadata.csv`
- `daily_summary.csv`

### Figures
- `requests_per_minute_by_type.png`
- `context_tokens_per_minute_by_type.png`
- `generated_tokens_per_minute_by_type.png`
- `images_per_minute.png`
- `cdf_prompt_length.png`
- `cdf_images_per_request.png`
- `modserve_test_baseline_rates.png`
- `modserve_test_avg_provisioned_units.png`
- `modserve_burst_day_workload.png`
- `modserve_burst_day_required_vs_provisioned.png`

---

## 15. What this phase does and does not do

### This phase does
- use a recent Azure workload,
- reproduce the paper’s trace-characterization style,
- build a clean baseline experiment pipeline,
- define stage-aware replay baselines,
- evaluate reliability/efficiency tradeoffs,
- create a reproducible methodology for later comparison.

### This phase does not yet do
- train the final TraceAdvisor model,
- reproduce ModServe’s full GPU serving system,
- reproduce the open-source model profiling experiments,
- reproduce exact TTFT/P99 TTFT hardware results.

Those system-level experiments require additional serving infrastructure and are beyond the baseline phase.

---

## 16. Relevance to TraceAdvisor

This ModServe baseline phase supports TraceAdvisor in three ways:

1. **Recent workload foundation**  
   It shifts the project to a recent multimodal Azure trace that reflects current LLM-serving behavior more closely than older general-purpose cluster traces. :contentReference[oaicite:13]{index=13}

2. **Stage-aware allocation framing**  
   It establishes that modern multimodal serving workloads benefit from reasoning about image and text load separately, which is important for later advisory logic. :contentReference[oaicite:14]{index=14}

3. **Reusable replay framework**  
   It builds the exact evaluation pipeline that a later TraceAdvisor model can plug into. In the next phase, the model will replace the reactive or fixed baseline policies with a history-driven recommendation policy for the next control interval.

---

## 17. Next step after this baseline phase

The next project phase will introduce the actual TraceAdvisor method.

That future step will:
- use only **past windows** as input,
- predict the next interval’s image/text demand or required units,
- produce recommended stage capacities before the interval begins,
- and evaluate those recommendations using the same replay framework and metrics defined here.

This ensures continuity between the baseline phase and the final system contribution.

---

## 18. One-sentence summary

The ModServe experiment pipeline converts a recent Azure multimodal inference trace into a replay-ready 5-minute interval dataset, applies three baseline provisioning strategies, and evaluates them with consistent reliability/efficiency metrics, thereby creating the baseline methodology that TraceAdvisor will later build on.