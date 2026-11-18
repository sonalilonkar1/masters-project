from pathlib import Path

import pandas as pd
import pytest

from scripts import build_final_cross_dataset_report as report

ROOT = Path(__file__).resolve().parents[1]


def comparison(dataset=report.ALIBABA):
    path = ("reports/results/alibaba_gpu_2020/final_test/final_test_policy_comparison.csv"
            if dataset == report.ALIBABA else "reports/results/google_subset/tables/final_test_policy_comparison.csv")
    return pd.read_csv(ROOT / path)


@pytest.mark.parametrize("dataset", [report.GOOGLE, report.ALIBABA])
@pytest.mark.parametrize("defect", ["utilization", "denominator", "missing", "null", "population"])
def test_five_previous_invalid_cases_are_rejected(dataset, defect):
    frame = comparison(dataset)
    if defect == "utilization":
        frame.loc[0, "average_cpu_utilization"] = 50
    elif defect == "denominator":
        frame.loc[0, "valid_cpu_violation_count"] = 1
    elif defect == "missing":
        frame = frame.drop(columns=["average_cpu_waste", "average_memory_shortfall"])
    elif defect == "null":
        frame.loc[0, "cpu_violation_pct"] = float("nan")
    else:
        frame.loc[0, "row_count"] += 1
    with pytest.raises(report.ReportError):
        report.validate_summary(frame, dataset)


@pytest.mark.parametrize("dataset", [report.GOOGLE, report.ALIBABA])
def test_real_producer_summaries_are_valid(dataset):
    report.validate_summary(comparison(dataset), dataset)


def test_real_sensitivity_preserves_structure_and_rejects_partition_change():
    frame = pd.read_csv(ROOT / "reports/results/alibaba_gpu_2020/final_test/final_test_sensitivity.csv")
    report.validate_summary(frame, report.ALIBABA, True, comparison())
    frame.loc[(frame.sensitivity == "same_second_excluded") & (frame.policy == "Request"),
              "valid_cpu_violation_count"] += 1
    with pytest.raises(report.ReportError, match="denominator_partition"):
        report.validate_summary(frame, report.ALIBABA, True, comparison())
