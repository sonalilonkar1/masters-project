#!/usr/bin/env python3
"""Build canonical sample artifacts for Alibaba 2018 and Azure VM V2.

This script is intentionally dataset-specific orchestration. It does not
calculate historical percentiles, ML predictions, Hybrid policies, or final
evaluation metrics.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.adapters.alibaba import (
    ALIBABA_INSTANCE_COLUMNS,
    ALIBABA_TASK_COLUMNS,
    Alibaba2018Adapter,
)
from src.adapters.azure_vm import (
    AZURE_CPU_COLUMNS,
    AZURE_VM_COLUMNS,
    AzureVMAdapter,
)


def read_headerless_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    return pd.read_csv(
        path,
        header=None,
        names=columns,
    )


def write_result(
    output_dir: Path,
    name: str,
    canonical: pd.DataFrame,
    metadata: dict,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    canonical_path = output_dir / f"{name}.parquet"
    metadata_path = output_dir / f"{name}.metadata.json"

    canonical.to_parquet(
        canonical_path,
        index=False,
    )
    metadata_path.write_text(
        json.dumps(metadata, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {canonical_path}")
    print(f"Wrote {metadata_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alibaba-task", type=Path)
    parser.add_argument("--alibaba-instance", type=Path)
    parser.add_argument("--azure-vm", type=Path)
    parser.add_argument("--azure-cpu", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "data/processed/external_canonical"
        ),
    )
    args = parser.parse_args()

    if args.alibaba_task and args.alibaba_instance:
        task = read_headerless_csv(
            args.alibaba_task,
            ALIBABA_TASK_COLUMNS,
        )
        instance = read_headerless_csv(
            args.alibaba_instance,
            ALIBABA_INSTANCE_COLUMNS,
        )

        result = Alibaba2018Adapter().adapt_tables(
            task,
            instance,
        )
        write_result(
            args.output_dir,
            "alibaba2018_instances_canonical",
            result.canonical,
            dict(result.metadata),
        )

    if args.azure_vm:
        vm = read_headerless_csv(
            args.azure_vm,
            AZURE_VM_COLUMNS,
        )
        azure = AzureVMAdapter()

        lifecycle = azure.adapt_vm_table(vm)
        write_result(
            args.output_dir,
            "azure_vm_lifecycle_canonical",
            lifecycle.canonical,
            dict(lifecycle.metadata),
        )

        if args.azure_cpu:
            cpu = read_headerless_csv(
                args.azure_cpu,
                AZURE_CPU_COLUMNS,
            )

            try:
                intervals = azure.adapt_cpu_readings(
                    vm,
                    cpu,
                )
            except ValueError as exc:
                print(
                    "Azure CPU interval artifact skipped: "
                    f"{exc}"
                )
            else:
                write_result(
                    args.output_dir,
                    "azure_vm_cpu_intervals_canonical",
                    intervals.canonical,
                    dict(intervals.metadata),
                )


if __name__ == "__main__":
    main()
