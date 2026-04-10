# Assumptions (v0)

This document outlines the assumptions and design decisions used for defining recurring jobs, confidence tiers, and history-based metrics for Baseline 1\.

---

## 1. Recurrence Rule (v0)
A recurring job is defined using the following key:

recurring_job_id = user\_clean + "||" + collection_logical_name

### Notes:  
- `user_clean` represents the normalized user identifier.  
- `collection_logical_name` represents the logical job name.  
- This grouping assumes that jobs with the same user and logical name represent repeated executions of the same workload.

### Fallback Handling:  
- If user is missing → `"unknown_user"`  
- If logical name is missing → `"unknown_job"`

This rule ensures a stable grouping of executions into recurring workloads.

---

## 2. Confidence Tier Definition (v0)
Confidence tiers are assigned based on:

- `run_count`: total number of executions of a recurring job  
- `stability`: variability in resource usage

### Stability Definition:

stability = max(cv_cpu, cv_mem)

Where:  
- cv_cpu = std_peak_cpu / mean_peak_cpu    
- cv_mem = std_peak_mem / mean_peak_mem  

---

### Tier Assignment Rules:

- **cold_start**: run_count < 3    
- **high**: run_count ≥ 10 AND stability ≤ 0.20    
- **medium**: run_count ≥ 5 AND stability ≤ 0.50    
- **low**: otherwise (including unstable jobs)

### Interpretation:  
- High confidence → stable and frequently observed jobs    
- Medium confidence → moderately stable jobs    
- Low confidence → unstable or insufficiently observed jobs    
- Cold start → insufficient history to make reliable predictions  

---

## 3. n_history (Execution-Level History)
n_history is defined as the number of prior executions of a job before the current execution.

### Computation:
n_history = groupby(recurrence\_key).cumcount()

### Behavior:  
- First execution → n\_history \= 0    
- Second execution → n\_history \= 1    
- etc.

### Purpose:  
- Enables time-aware modeling of job behavior    
- Prevents using future information when evaluating predictions    
- Supports realistic pre-execution decision making  

---

## 4. Dataset Structure
Two datasets are produced:

### 1. job_metrics_v0.parquet (Execution-Level)  
Contains:  
- recurring_job_id    
- confidence_tier    
- n_history    
- resource usage and slack metrics  
This dataset is used for evaluation and baseline comparison.

---

### 2. job_profiles_confidence_v0.parquet (Job-Level)  
Contains:  
- aggregated statistics per recurring job    
- stability metrics    
- resource and duration profiles    
- percentile-based usage estimates (P90, P95, P99)  
This dataset is used for analysis and summary reporting.

---

## 5. Limitations (v0)
- Recurrence is defined heuristically using user and logical name    
- Confidence tiers use fixed thresholds (not learned)    
- Stability is based only on peak usage variability    
- Does not yet incorporate temporal drift or workload evolution  

---

## 6. Future Improvements
- Learn recurrence patterns using clustering or embeddings    
- Dynamically adjust confidence thresholds    
- Incorporate time-aware or sequence-based modeling    
- Use n\_history to adapt percentile selection per execution  
