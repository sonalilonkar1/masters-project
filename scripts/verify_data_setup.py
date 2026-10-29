"""Verify local dataset setup.

Usage:
    python scripts/verify_data_setup.py                       # Google Kaggle subset smoke test (default)
    python scripts/verify_data_setup.py --dataset alibaba_gpu_2020
    python scripts/verify_data_setup.py --dataset alibaba_gpu_2020 --check-archives --load
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
FILE_PATH = "data/raw/clusterdata2019_kaggle_subset.csv"


def verify_google_kaggle_subset():
    print(" Running smoke test...")

    try:
        df = pd.read_csv(FILE_PATH)
    except FileNotFoundError:
        print(f" File not found at {FILE_PATH}")
        return

    print(" File loaded successfully!\n")

    print(" Shape of dataset:")
    print(df.shape)

    print("\n Columns:")
    print(df.columns.tolist())

    print("\n Sample rows:")
    print(df.head(5))


def verify_alibaba_gpu_2020(raw_dir, check_archives, load):
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    from src.sources.alibaba_gpu_2020 import (
        DEFAULT_RAW_DIR,
        TABLES,
        SourceVerificationError,
        load_manifest,
        load_table,
        verify_table,
    )

    raw_dir = Path(raw_dir) if raw_dir else DEFAULT_RAW_DIR
    manifest = load_manifest()
    print(f" Verifying Alibaba GPU 2020 sources in {raw_dir}")

    failures = 0
    for table in TABLES:
        try:
            report = verify_table(table, raw_dir=raw_dir, manifest=manifest, check_archive=check_archives)
            message = f"{report['data_lines']:,} rows, sha256 {report['sha256'][:12]}..."
            if load:
                rows = len(load_table(table, raw_dir=raw_dir, manifest=manifest, verify=False))
                if rows != report["data_lines"]:
                    raise SourceVerificationError(f"loaded {rows} rows, expected {report['data_lines']}")
                message += f" (loaded {rows:,} rows)"
            print(f"  OK    {table}: {message}")
        except (SourceVerificationError, FileNotFoundError, KeyError) as exc:
            failures += 1
            print(f"  FAIL  {table}: {exc}")

    if failures:
        print(f"\n {failures} table(s) failed verification. See docs/data/alibaba_gpu_2020_source_setup.md.")
        return 1

    print("\n All Alibaba GPU 2020 source tables verified.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", choices=["google_kaggle_subset", "alibaba_gpu_2020"], default="google_kaggle_subset")
    parser.add_argument("--raw-dir", help="Alibaba GPU 2020 raw directory (default: data/raw/alibaba_gpu_2020)")
    parser.add_argument("--check-archives", action="store_true", help="Also verify the downloaded .tar.gz archives")
    parser.add_argument("--load", action="store_true", help="Also load every table and check its row count")
    args = parser.parse_args()

    if args.dataset == "alibaba_gpu_2020":
        return verify_alibaba_gpu_2020(args.raw_dir, args.check_archives, args.load)

    verify_google_kaggle_subset()
    return 0


if __name__ == "__main__":
    sys.exit(main())
