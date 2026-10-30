# Chapter 3. Technology Descriptions

## 3.1 Data Processing and Analysis Stack

TraceAdvisor is implemented in Python 3.12. Python was chosen because its data and machine learning libraries cover every stage of the pipeline, from loading raw traces to fitting and evaluating models, without moving data between tools.

Tabular processing uses pandas and NumPy. pandas holds each table in memory and provides the joins, group-wise aggregations and time-ordered operations that the pipeline relies on, such as summing parallel executions within a time window or collecting a workload's earlier occurrences. NumPy provides the vectorized arithmetic underneath, including the metric calculations. The largest Alibaba source table has about 7.5 million rows, so the source loader can also read a table in fixed-size chunks and load only the columns a step needs.

Intermediate and final tables are stored in the Apache Parquet format through PyArrow. Parquet is a compressed columnar format that preserves column types, including nullable integers and strings, so a table read back by a later stage has exactly the types it was written with. This matters for TraceAdvisor, where a missing value must remain missing rather than becoming zero or an empty string.

The two pipelines are run in different ways. The Google pipeline, the first to be developed, is a sequence of Jupyter notebooks, which keep each step's code, its checks and their outputs together for review. The Alibaba pipeline is a set of command-line scripts, one per stage, that verify their inputs, build their outputs and publish them only when all checks pass; scripts suit this dataset better because each stage runs for a long time on large inputs and must be repeatable without manual steps. Figures are produced with Matplotlib and Seaborn.

The shared code is tested with pytest. The test suite covers the canonical schema, the adapter framework and both adapters, the source loader, the split and target builder, the metrics and evaluator, the baselines, the Hybrid rule and the build scripts. Table 3.1 lists the main libraries and the versions used for all final runs.

**Table 3.1** Main libraries and versions

| Purpose | Library | Version |
|---|---|---|
| Language | Python | 3.12 |
| Tabular processing | pandas | 2.3.3 |
| Numerical computing | NumPy | 2.5.4 |
| Columnar storage | PyArrow | 23.0.1 |
| Machine learning | scikit-learn | 1.9.1 |
| Gradient boosting | XGBoost | 3.4.1 |
| Model persistence | joblib | 1.6.0 |
| Figures | Matplotlib, Seaborn | 3.11.2, 0.13.2 |
| Notebooks | JupyterLab | 4.6.5 |
| Testing | pytest | 9.2.0 |

## 3.2 Machine Learning Libraries and Models

The ML policy is built with scikit-learn and XGBoost. scikit-learn provides the regression models, hyperparameter search and cross-validation utilities, and a common interface that lets different model families be tuned and compared in the same way. XGBoost provides a gradient-boosted tree implementation that is widely used for tabular regression.

Tree-based models were chosen because the features are tabular, mix requests, counts, history statistics and, on Alibaba GPU 2020, categorical job descriptors, on very different scales, and relate to usage non-linearly. Tree models need no feature scaling, handle such mixtures well and can report which features they rely on. Four model categories are used, with gradient boosting implemented in two ways:

- **Decision tree:** a single regression tree. It is easy to interpret and serves as the simplest non-trivial model.
- **Random forest:** an average of many trees, each trained on a random sample of rows and features. Averaging reduces the variance of a single tree.
- **Gradient-boosted trees:** trees added one at a time, each correcting the errors of the previous ones. XGBoost is used on both datasets, and scikit-learn's histogram-based gradient boosting is also compared on Alibaba GPU 2020.
- **Constant predictor:** scikit-learn's `DummyRegressor`, which always predicts one value from the training data (the median on Google; the mean on Alibaba GPU 2020). It has no predictive skill and is included as the floor that any selected model must beat; it is never selected.

On Google, each model family is tuned over a small grid of hyperparameters, and the tuning respects time order: scikit-learn's grid search is run on the training set with time-series cross-validation, in which each fold is validated only on rows later than those it was trained on, and rows whose next-run targets fall in a fold's validation period are removed from its training data. On Alibaba GPU 2020, which has far more rows, each model family is used with one fixed configuration, fitted on the training set and scored on the validation set. On Google, models are trained on the `log1p` transform of usage, which reduces the influence of a few very large workloads, and predictions are transformed back before evaluation. A separate model is fitted for each dataset and each resource. Fitted models are saved with joblib so that the locked models can be reloaded for the final test without refitting.

## 3.3 Dataset and Trace Sources

### 3.3.1 Primary Dataset: Google ClusterData 2019

Google ClusterData 2019 is a public trace of Google's Borg cluster management system. TraceAdvisor uses a publicly available sample of it published on Kaggle, a single CSV file with 405,894 rows and 34 columns spanning about 31 days. All Google results in this report are based on this sample.

Each row describes one task instance over one usage window of up to five minutes. It identifies the collection the task belongs to, the instance's index within it, the machine it ran on, its user and the collection's logical name, and it records the task's CPU and memory request together with its average and maximum CPU and memory usage in that window, the window's start and end times, and the scheduling event. Resource values are normalized in the trace, with CPU in normalized compute units and memory in normalized units, so they are relative quantities rather than cores or bytes.

The sample has no explicit run or recurrence identifiers. TraceAdvisor reconstructs runs from the usage windows and identifies a recurring workload by the combination of its user and collection logical name. The main limitation is size: the 31-day sample yields 3,473 training, 675 validation and 731 test occurrences, so results on Google are based on hundreds rather than thousands of evaluated occurrences.

### 3.3.2 Second Dataset: Alibaba GPU Cluster Trace 2020

The Alibaba GPU Cluster Trace 2020 (`cluster-trace-gpu-v2020`) is a public trace of a production cluster running machine learning jobs on Alibaba's Platform for AI (PAI). It records jobs, the task roles within each job, the individual instances that ran each role, per-instance resource measurements and the specifications of the machines. TraceAdvisor uses six of its seven official tables (Table 3.2); the seventh, a machine-level metric table, is outside the project's scope. The tables are distributed as compressed archives of headerless CSV files, and their column names come from separate header files.

**Table 3.2** Alibaba GPU 2020 source tables used

| Table | Rows | Contents |
|---|---|---|
| `pai_job_table` | 1,055,501 | One row per job: user, status, start and end times |
| `pai_task_table` | 1,261,050 | One row per task role in a job: requested CPU, memory and GPU, instance count |
| `pai_instance_table` | 7,522,002 | One row per running instance of a role |
| `pai_sensor_table` | 3,033,232 | Per-instance measurements: average CPU, average and peak memory, GPU usage |
| `pai_group_tag_table` | 1,055,032 | The `group` recurrence tag, one row per job identifier (`inst_id`); 1,053,971 rows match a job and 1,061 match none |
| `pai_machine_spec` | 1,897 | Machine CPU, memory and GPU specifications |

The trace was selected after twelve Alibaba traces were examined. It is the only one that provides both an official recurrence tag, the `group` field, present on 99.86% of jobs (1,530 of the 1,055,501 jobs have no tag; the difference in row counts between the job and tag tables is not the untagged count, because 1,061 tag rows match no job), and a memory peak recorded in the same unit as the memory request, which together make next-run memory recommendation possible. It also has limitations. CPU usage is available only as an average over an instance's lifetime, not as a peak. Only 36.8% of role occurrences are eligible for evaluation, because the remainder did not complete or were not fully observed. Most evaluated roles have a single instance, and the measurements cover only about day 19 to day 69 of the trace.

### 3.3.3 Earlier Baseline Traces: Azure Resource Central, Splitwise and ModServe

Before the TraceAdvisor design was fixed, three public Microsoft Azure traces were used for baseline sizing experiments. They motivated the design, but they were not processed through the TraceAdvisor adapter and evaluation pipeline; their results are summarized in Section 7.1.

**Resource Central** is a trace of virtual machines on Azure (the 2017 release). It was used to compare each virtual machine's mean CPU utilization with its 95th percentile.

**Splitwise** is a trace of large language model inference requests on Azure, for code and conversation services. Fixed capacities set at the mean, median and upper percentiles of token demand in a training period were tested on later windows.

**ModServe** is a trace of multimodal inference on Azure over one week in October 2024. Fixed and reactive provisioning policies for image and text serving were compared.

All three experiments showed the trade-off that TraceAdvisor addresses. None of the traces, however, describes recurring jobs with a per-job resource request and per-job CPU and memory usage. Resource Central has no memory usage and no per-job request, and Splitwise and ModServe describe service-level demand per time window rather than individual jobs, so there is no job to make a pre-execution recommendation for. TraceAdvisor's evaluation is therefore based on Google ClusterData 2019 and Alibaba GPU 2020.

## 3.4 Dataset Adapters and Unit Normalization

Each dataset records resources in its own units, so values must be labelled consistently before any shared stage uses them. The canonical schema defines a fixed vocabulary of resource units, and every resource field in a canonical view carries a unit from that vocabulary. A request and the usage it is compared with must use the same unit, and values are kept in their source unit rather than converted, because no reliable conversion exists for normalized data.

For Google, CPU is kept in the trace's normalized compute units and memory in its normalized units. The original values are kept alongside the parsed ones, and timestamps, which the trace records in microseconds, are kept at that resolution. Because the units are normalized, Google results describe relative sizing, and waste is not expressed in cores or gigabytes.

For Alibaba GPU 2020, requested and measured CPU are expressed as a percentage of one virtual CPU, where 100 means one full vCPU, and memory is expressed in gigabytes. Timestamps are converted from seconds to microseconds to match the canonical time resolution. The adapter maps the requested CPU, memory and GPU from the task table, and each instance's average CPU, average memory and peak memory from the sensor table. Because the trace has no CPU peak, the canonical CPU peak field is left empty and the dataset's capability profile records that only an average is available. GPU request and usage fields are carried through with their own units but are not evaluated.

The capability profile is what allows the shared stages to treat the datasets correctly without dataset-specific code. It records each dataset's CPU and memory units, whether CPU is a peak or an average, and the level at which values are measured, and the adapter's output is rejected if any of its units or fields disagree with the profile. Because the two datasets measure CPU differently and use different units, their results are reported side by side but never compared numerically.

## 3.5 Artifact Storage, Reproducibility, and Presentation Technologies

TraceAdvisor stores its outputs as ordinary files in standard formats: Parquet for tables, JSON for metadata and decision manifests, and CSV for the result tables included in reports. Each output folder of the Alibaba pipeline contains a checksum file listing the SHA-256 hash of every file in it, and each stage recomputes the hashes of its inputs before running and stops if any differs, so a result can only be produced from the exact inputs it records. The Google notebooks record the SHA-256 hashes of every input to the final test in the decision manifest instead, and the final test stops if any of them has changed. The pipeline scripts first write outputs to a temporary staging folder and move them into place only after all checks pass, so an interrupted or failed run never leaves a partial output.

Each Alibaba run also records its provenance in a metadata file: the checksums of its inputs, the Git commit of the code that produced it and the versions of the libraries used. On Google, the same information is recorded in the decision manifest. All final runs use one locked environment, defined by a file that pins the exact version of every installed package. Together these records make it possible to trace any reported number back to the data, code and environment that produced it.

Git is used for version control of the code, documentation, configuration and final results (reports and result tables). The raw traces and intermediate tables, which together amount to several gigabytes, are kept outside Git; the committed checksums of the official Alibaba source files let anyone who downloads the traces confirm that they have the same data.

The presentation layer is built from two components. A REST API serves the recommendations and evaluation results held in the artifact repository over HTTP, returning them in JSON so that any client can use them. A web frontend built on this API presents the results to developers in a browser, allowing them to look up a workload, see its recommended CPU and memory, and compare the policies. The presentation layer only reads published results; it does not run the pipeline or modify any artifact.
