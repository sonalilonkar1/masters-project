# Alibaba GPU 2020 Source Setup and Loading

This document explains how to download, verify, and load the official Alibaba GPU 2020 trace (`cluster-trace-gpu-v2020`) for TraceAdvisor (Task 2).

- **Official source:** https://github.com/alibaba/clusterdata/blob/master/cluster-trace-gpu-v2020/README.md
- **Checksum manifest (committed):** `config/alibaba_gpu_2020_sources.json`
- **Loader:** `src/sources/alibaba_gpu_2020.py`
- **Verification:** `python scripts/verify_data_setup.py --dataset alibaba_gpu_2020`

The loader only verifies and reads the source tables. It does not join tables, build canonical identities, or map fields to the canonical schema; that belongs to the Alibaba GPU 2020 adapter (Task 3).

---

## 1. Tables

Six of the seven official tables are used. `pai_machine_metric` is not part of the TraceAdvisor scope and is not downloaded.

| Table | Rows | Decompressed CSV | Archive |
|---|---:|---:|---:|
| `pai_job_table` | 1,055,501 | 133,288,147 bytes | 62,065,432 bytes |
| `pai_task_table` | 1,261,050 | 113,398,956 bytes | 35,514,117 bytes |
| `pai_instance_table` | 7,522,002 | 1,975,177,534 bytes | 694,839,139 bytes |
| `pai_sensor_table` | 3,033,232 | 1,056,899,391 bytes | 406,119,947 bytes |
| `pai_group_tag_table` | 1,055,032 | 115,521,549 bytes | 55,064,781 bytes |
| `pai_machine_spec` | 1,897 | 73,311 bytes | 30,449 bytes |

The CSV files have **no header line**. Column names come from the official `.header` files, which are downloaded separately. Row counts match the counts in `docs/data/alibaba_dataset_selection_feasibility.md`; the job and task counts also match `docs/data/alibaba_gpu_2020_evidence_and_limitations.md`.

---

## 2. Download and decompression

Raw data stays outside Git in `data/raw/alibaba_gpu_2020/` (`data/raw/*` is in `.gitignore`).

```bash
mkdir -p data/raw/alibaba_gpu_2020/archives
cd data/raw/alibaba_gpu_2020

for t in pai_job_table pai_task_table pai_instance_table pai_sensor_table pai_group_tag_table pai_machine_spec; do
  curl --fail -o archives/$t.tar.gz https://aliopentrace.oss-cn-beijing.aliyuncs.com/v2020GPUTraces/$t.tar.gz
  curl --fail -o $t.header https://raw.githubusercontent.com/alibaba/clusterdata/master/cluster-trace-gpu-v2020/data/$t.header
  tar -xzf archives/$t.tar.gz
done
cd -
```

Expected layout:

```text
data/raw/alibaba_gpu_2020/
├── archives/<table>.tar.gz
├── <table>.csv
└── <table>.header
```

Alternative download links are listed in the official README.

---

## 3. Verification

```bash
python scripts/verify_data_setup.py --dataset alibaba_gpu_2020 --check-archives --load
```

For every table this checks that the CSV and header files exist and that their size, SHA-256, and line count match the manifest; that the header columns match the loader schema; with `--check-archives`, that the archive checksum matches; and with `--load`, that the loaded row count matches. Any mismatch fails with a clear error and a non-zero exit code.

The archive, header, and CSV SHA-256 values in the manifest are the **official values published in the README**. Sizes and line counts were measured on the verified files.

---

## 4. Loading

```python
from src.sources.alibaba_gpu_2020 import load_table, iter_table_chunks

jobs = load_table("pai_job_table")
instances = load_table(
    "pai_instance_table",
    columns=["job_name", "task_name", "inst_name", "worker_name", "status", "start_time", "end_time", "machine"],
)

for chunk in iter_table_chunks("pai_sensor_table", columns=["worker_name", "max_mem"], chunksize=1_000_000):
    ...
```

- Every call verifies the file against the manifest first (`verify=False` skips this).
- Rows are returned in **source-file order**.
- `source_row_number` is the **1-based data-line number in the checksum-verified decompressed CSV**. It is assigned while reading, before any filtering, sorting, or joining, and is identical across full, column-selected, repeated, and chunked loads.
- Only empty fields are treated as missing. Text such as `NA` or `None` stays text.
- Quoting is disabled (the official files contain no quotes), so every row is exactly one line of the file.
- Numbers are parsed exactly (`float_precision="round_trip"`). The default fast parser was observed to differ from the source text in the last binary digit for 250,411 `cpu_usage` and 229,898 `avg_mem` values.

### Column types

Column order follows the official `.header` files.

| Table | Text columns | Numeric columns |
|---|---|---|
| `pai_job_table` | `job_name`, `inst_id`, `user`, `status` | `start_time`, `end_time` (float64) |
| `pai_task_table` | `job_name`, `task_name`, `status`, `gpu_type` | `inst_num`, `start_time`, `end_time`, `plan_cpu`, `plan_mem`, `plan_gpu` (float64) |
| `pai_instance_table` | `job_name`, `task_name`, `inst_name`, `worker_name`, `inst_id`, `status`, `machine` | `start_time`, `end_time` (float64) |
| `pai_sensor_table` | `job_name`, `task_name`, `worker_name`, `inst_id`, `machine`, `gpu_name` | `cpu_usage`, `gpu_wrk_util`, `avg_mem`, `max_mem`, `avg_gpu_wrk_mem`, `max_gpu_wrk_mem`, `read`, `write`, `read_count`, `write_count` (float64) |
| `pai_group_tag_table` | `inst_id`, `user`, `gpu_type_spec`, `group`, `workload` | — |
| `pai_machine_spec` | `machine`, `gpu_type` | `cap_cpu`, `cap_mem`, `cap_gpu` (int64) |

Text columns use the pandas `string` type. Numeric columns that contain empty fields are float64; the machine capacities have no empty fields.

### Missing values in the source

Empty fields per table (measured on the full files): job `start_time` 3,663 and `end_time` 296,420; task `start_time` 3,714, `end_time` 349,561, `inst_num` 130, `plan_cpu` and `plan_mem` 18,454 each, `plan_gpu` 223,965, `gpu_type` 217,738; instance `start_time` 1,773,468, `end_time` 2,267,582, `worker_name` and `machine` 331,057 each; sensor `cpu_usage` 5,829, `avg_mem` 1,217, and `read`, `write`, `read_count`, `write_count` 3 each; group tag `gpu_type_spec` 1,034,399, `workload` 952,234, `user` 1; machine spec none.

---

## 5. Disk and memory requirements

Measured on macOS with Python 3.12 and pandas 2.3:

- **Disk:** about 4.65 GB (1.25 GB of archives plus 3.39 GB of decompressed CSVs). The archives can be deleted after verification if `--check-archives` is not needed.
- **Memory (peak process RSS when loading one table with all columns, in GiB):** job 0.5, task 0.64, group tag 0.43, machine spec under 0.1, sensor about 2.2, instance 3.5–3.8 (varies between runs).
- **Time:** verifying all six files takes a few seconds; loading the instance table about 11 seconds.
- Selecting columns lowers memory; chunked loading (`iter_table_chunks`) keeps memory bounded by the chunk size.

---

## 6. Optional local cache

This setup does not create a cache. A local Parquet cache may be written under `data/processed/` (not committed to Git). It must keep `source_row_number` from the loader and must not be used to recompute it.

---

## 7. Tests

- `tests/test_alibaba_gpu_2020_loader.py` runs on small fixture files: column names and types, source order, exact float parsing, missing-value handling, `source_row_number` stability across full, column-selected, repeated, and chunked loads, and failures for modified, truncated, or missing files and mismatched headers.
- A full-data test runs only with the official tables present and `TRACEADVISOR_FULL_DATA_TESTS=1`:

```bash
TRACEADVISOR_FULL_DATA_TESTS=1 python -m pytest tests/test_alibaba_gpu_2020_loader.py
```
