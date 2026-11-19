"""Producer-specific aggregate validation; no inference or row-level evaluation."""

import pandas as pd

from scripts import verify_alibaba_gpu_2020_artifacts as task8

ALIBABA = "alibaba_gpu_v2020"
GOOGLE = "google_clusterdata2019"


def validate_summary(frame, dataset, sensitivity=False, comparison=None, final_population=None):
    if frame.empty:
        raise ValueError(f"{dataset}: empty result table")
    keys = ["sensitivity", "policy"] if sensitivity else ["policy"]
    if not set(keys).issubset(frame.columns):
        raise ValueError(f"{dataset}: missing columns {keys}")
    if frame[keys].isna().any().any() or frame.duplicated(keys).any():
        raise ValueError(f"{dataset}: null or duplicate policy/cut")
    if set(frame.policy) != set(task8.FINAL_POLICIES):
        raise ValueError(f"{dataset}: must contain exactly seven policies")
    if dataset == ALIBABA:
        expected = task8.SENSITIVITY_COLUMNS if sensitivity else task8.COMPARISON_COLUMNS
        if set(frame.columns) != set(expected):
            raise ValueError(f"{dataset}: missing columns {sorted(set(expected)-set(frame))}; "
                             f"unsupported metrics {sorted(set(frame)-set(expected))}")
        if sensitivity:
            checks = task8._validate_sensitivity(frame, comparison)
        else:
            ordered = frame.set_index("policy").loc[list(task8.FINAL_POLICIES)].reset_index()
            checks = task8._validate_policy_comparison(ordered, final_population)
            if pd.to_numeric(frame.row_count, errors="raise").nunique() != 1:
                raise ValueError("comparison populations differ across policies")
    elif dataset == GOOGLE and not sensitivity:
        expected = set(task8.COMPARISON_COLUMNS) - {
            "cpu_result_semantics", "primary_resource", "any_resource_metric_reported"}
        expected |= {"n_common_occurrences", "any_resource_violation_pct", "valid_any_resource_violation_count"}
        if set(frame.columns) != expected:
            raise ValueError(f"{dataset}: missing columns {sorted(expected-set(frame))}; "
                             f"unsupported metrics {sorted(set(frame)-expected)}")
        checks = task8._validate_occurrence_numeric_rows(frame, "google.comparison", final_population)
        populations, errors = task8._parse_numeric_series(frame.row_count)
        common, common_errors = task8._parse_numeric_series(frame.n_common_occurrences)
        if errors or common_errors or populations.nunique() != 1 or not common.eq(populations).all():
            raise ValueError("Google comparison/common populations disagree")
        denominator, errors = task8._parse_numeric_series(frame.valid_any_resource_violation_count)
        values, value_errors = task8._parse_numeric_series(frame.any_resource_violation_pct)
        if errors or value_errors:
            raise ValueError("invalid Google any-resource numerical values")
        for index in frame.index:
            count, value = denominator.loc[index], values.loc[index]
            maximum = min(float(frame.loc[index, "valid_cpu_violation_count"]),
                          float(frame.loc[index, "valid_memory_violation_count"]))
            if pd.isna(count) or not count.is_integer() or not 0 <= count <= maximum:
                raise ValueError("Google any-resource denominator invalid")
            if (count == 0 and not pd.isna(value)) or (count > 0 and (pd.isna(value) or not 0 <= value <= 100)):
                raise ValueError("Google any-resource percentage/nullability invalid")
    else:
        raise ValueError(f"{dataset}: scope evidence only; no supported result producer")
    failures = [f"{c.name}: {c.detail}" for c in checks if not c.ok]
    if failures:
        raise ValueError("; ".join(failures))
