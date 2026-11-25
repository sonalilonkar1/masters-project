"""Synthetic tests for the Task 10 (#115) split-isolated Google targets.

These tests need no local data. They run the target-construction code of
Notebook 04 (the cells defining ``add_split_isolated_targets`` and
``SPLIT_OCCURRENCE_FRAMES``) on a small made-up occurrence table, and they run
the leakage audit of ``make_task10_comparison.py`` on the same table.
"""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_04 = REPO_ROOT / "pipelines" / "google_subset" / "04_splitAndBaselines.ipynb"
COMPARISON_SCRIPT = (
    REPO_ROOT
    / "reports"
    / "results"
    / "google_subset"
    / "task10_correction"
    / "make_task10_comparison.py"
)

TARGET_TIME = "target_next_occurrence_start_time_us"
TARGET_CPU = "target_cpu_next_occurrence_peak_ncu"
TARGET_MEMORY = "target_memory_next_occurrence_peak_normalized"
TARGET_SIZE = "target_next_occurrence_execution_count"
REASON = "target_null_reason"
NO_NEXT = "no_next_occurrence"
OTHER_SPLIT = "next_occurrence_in_other_split"

# Frozen boundaries of the synthetic split: train <= 100, validation
# 200..300, test >= 400.
BOUNDARIES = {
    "TRAIN_END_TIME": 100,
    "VAL_START_TIME": 200,
    "VAL_END_TIME": 300,
    "TEST_START_TIME": 400,
}

# (recurrence_key, start, cpu peak, memory peak, execution count)
OCCURRENCES = [
    ("a", 10, 1.0, 0.10, 1),
    ("a", 50, 2.0, 0.20, 2),
    ("a", 210, 3.0, 0.30, 1),
    ("a", 420, 4.0, 0.40, 3),
    ("a", 450, 5.0, 0.50, 1),
    ("b", 20, 6.0, 0.60, 1),
    ("c", 60, 7.0, 0.70, 1),
    ("c", 70, 8.0, np.nan, 4),
    ("c", 250, 9.0, 0.90, 1),
    ("c", 260, 10.0, 1.00, 1),
    ("d", 410, 11.0, 1.10, 1),
    ("d", 430, np.nan, 1.20, 1),
    ("e", 220, 13.0, 1.30, 1),
    ("e", 440, 14.0, 1.40, 1),
]

# Expected result per (recurrence_key, start):
# (target start, target cpu, target memory, null reason)
EXPECTED = {
    ("a", 10): (50, 2.0, 0.20, None),
    ("a", 50): (None, None, None, OTHER_SPLIT),  # next is in validation
    ("a", 210): (None, None, None, OTHER_SPLIT),  # next is in test
    ("a", 420): (450, 5.0, 0.50, None),
    ("a", 450): (None, None, None, NO_NEXT),
    ("b", 20): (None, None, None, NO_NEXT),
    ("c", 60): (70, 8.0, None, None),  # next memory is missing: stays NaN
    ("c", 70): (None, None, None, OTHER_SPLIT),  # next is in validation
    ("c", 250): (260, 10.0, 1.00, None),
    ("c", 260): (None, None, None, NO_NEXT),
    ("d", 410): (430, None, 1.20, None),  # next CPU is missing: stays NaN
    ("d", 430): (None, None, None, NO_NEXT),
    ("e", 220): (None, None, None, OTHER_SPLIT),  # next is in test
    ("e", 440): (None, None, None, NO_NEXT),
}
EXPECTED_REMOVED = {"train": 2, "validation": 2, "test": 0}


def _notebook_cell(marker):
    notebook = json.loads(NOTEBOOK_04.read_text(encoding="utf-8"))
    cells = [
        "".join(cell["source"])
        for cell in notebook["cells"]
        if cell["cell_type"] == "code" and marker in "".join(cell["source"])
    ]
    assert len(cells) == 1, f"expected one Notebook 04 cell containing {marker!r}"
    return cells[0]


def _synthetic_occurrences():
    frame = pd.DataFrame(
        OCCURRENCES,
        columns=[
            "recurrence_key",
            "execution_start_time_us",
            "occurrence_peak_cpu_ncu",
            "occurrence_peak_memory_normalized",
            "occurrence_execution_count",
        ],
    )
    frame["occurrence_key"] = (
        frame["recurrence_key"] + "||" + frame["execution_start_time_us"].astype(str)
    )
    frame["occurrence_end_time_us"] = frame["execution_start_time_us"] + 5
    # Non-target columns that the correction must leave unchanged.
    frame["rec_cpu_p99"] = frame["occurrence_peak_cpu_ncu"] * 1.5
    frame["prior_completed_occurrence_count"] = frame.groupby("recurrence_key").cumcount()
    # Same order as Notebook 04's occurrence table.
    return frame.sort_values(
        ["recurrence_key", "execution_start_time_us"], kind="mergesort"
    ).reset_index(drop=True)


def _split(frame):
    times = frame["execution_start_time_us"]
    masks = {
        "train": times <= BOUNDARIES["TRAIN_END_TIME"],
        "validation": (times >= BOUNDARIES["VAL_START_TIME"])
        & (times <= BOUNDARIES["VAL_END_TIME"]),
        "test": times >= BOUNDARIES["TEST_START_TIME"],
    }
    return {name: frame.loc[mask].reset_index(drop=True) for name, mask in masks.items()}


def _run_notebook_target_cells(splits, all_occurrences):
    namespace = {
        "pd": pd,
        "np": np,
        "display": lambda *args, **kwargs: None,
        "all_occurrences": all_occurrences,
        "train_occurrences": splits["train"],
        "val_occurrences": splits["validation"],
        "test_occurrences": splits["test"],
        **BOUNDARIES,
    }
    exec(_notebook_cell("def add_split_isolated_targets("), namespace)
    exec(_notebook_cell("SPLIT_OCCURRENCE_FRAMES = {"), namespace)
    return namespace


@pytest.fixture()
def corrected():
    all_occurrences = _synthetic_occurrences()
    splits = _split(all_occurrences)
    namespace = _run_notebook_target_cells(splits, all_occurrences)
    return splits, namespace


def _value(value):
    return None if pd.isna(value) else value


def test_notebook_targets_are_split_isolated(corrected):
    _, namespace = corrected
    outputs = {
        "train": namespace["train_occurrences"],
        "validation": namespace["val_occurrences"],
        "test": namespace["test_occurrences"],
    }

    seen = set()
    for frame in outputs.values():
        for row in frame.itertuples(index=False):
            key = (row.recurrence_key, row.execution_start_time_us)
            seen.add(key)
            target_start, target_cpu, target_memory, reason = EXPECTED[key]
            row_values = row._asdict()
            assert _value(row_values[TARGET_TIME]) == target_start, key
            assert _value(row_values[TARGET_CPU]) == target_cpu, key
            assert _value(row_values[TARGET_MEMORY]) == target_memory, key
            assert _value(row_values[REASON]) == reason, key
            if target_start is None:
                assert pd.isna(row_values[TARGET_SIZE]), key
    assert seen == set(EXPECTED)

    assert namespace["cross_split_targets_removed"] == EXPECTED_REMOVED


def test_notebook_targets_leave_non_target_columns_unchanged(corrected):
    splits, namespace = corrected
    added = [TARGET_TIME, TARGET_CPU, TARGET_MEMORY, TARGET_SIZE, REASON]
    for name, key in [
        ("train", "train_occurrences"),
        ("validation", "val_occurrences"),
        ("test", "test_occurrences"),
    ]:
        output = namespace[key]
        assert list(output.columns) == list(splits[name].columns) + added
        pd.testing.assert_frame_equal(output[list(splits[name].columns)], splits[name])


def test_notebook_target_cells_refuse_existing_target_columns():
    all_occurrences = _synthetic_occurrences()
    splits = _split(all_occurrences)
    splits["validation"][TARGET_CPU] = 1.0

    with pytest.raises(RuntimeError, match="target columns already exist"):
        _run_notebook_target_cells(splits, all_occurrences)


def _load_comparison_script():
    spec = importlib.util.spec_from_file_location("make_task10_comparison", COMPARISON_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _audit_inputs(namespace):
    occurrences = {
        "train": namespace["train_occurrences"].copy(),
        "validation": namespace["val_occurrences"].copy(),
        "test": namespace["test_occurrences"].copy(),
    }
    boundaries = {
        "train_end": BOUNDARIES["TRAIN_END_TIME"],
        "val_start": BOUNDARIES["VAL_START_TIME"],
        "val_end": BOUNDARIES["VAL_END_TIME"],
        "test_start": BOUNDARIES["TEST_START_TIME"],
    }
    validation = occurrences["validation"]
    population = int(validation[[TARGET_CPU, TARGET_MEMORY]].notna().all(axis=1).sum())
    before = {"common_validation_population": {"occurrences": population + 2}}
    after = {
        "cross_split_targets_removed": dict(EXPECTED_REMOVED),
        "common_validation_population": {"occurrences": population},
    }
    return occurrences, boundaries, before, after


def test_leakage_audit_counts_on_synthetic_targets(corrected):
    module = _load_comparison_script()
    _, namespace = corrected
    audit = module.leakage_audit(*_audit_inputs(namespace)).set_index("split")

    assert audit["targets_nulled_cross_split"].to_dict() == EXPECTED_REMOVED
    assert audit.loc["train", "nulled_target_was_in_validation_period"] == 2
    assert audit.loc["validation", "nulled_target_was_in_test_period"] == 2
    assert audit["null_no_next_occurrence"].to_dict() == {
        "train": 1,
        "validation": 1,
        "test": 3,
    }


def _first(frame, reason):
    return frame.index[frame[REASON].eq(reason).fillna(False)][0]


def _swap_reasons(occurrences):
    train = occurrences["train"]
    cross, final = _first(train, OTHER_SPLIT), _first(train, NO_NEXT)
    train.loc[cross, REASON], train.loc[final, REASON] = NO_NEXT, OTHER_SPLIT


def _restore_cross_split_target(occurrences):
    validation = occurrences["validation"]
    row = _first(validation, OTHER_SPLIT)
    validation.loc[row, [TARGET_TIME, TARGET_CPU, TARGET_MEMORY]] = [420.0, 4.0, 0.40]
    validation.loc[row, REASON] = pd.NA


def _drop_same_split_target(occurrences):
    train = occurrences["train"]
    row = train.index[train[TARGET_TIME].notna()][0]
    train.loc[row, [TARGET_TIME, TARGET_CPU, TARGET_MEMORY]] = np.nan
    train.loc[row, REASON] = OTHER_SPLIT


def _change_target_value(occurrences):
    test = occurrences["test"]
    row = test.index[test[TARGET_MEMORY].notna()][0]
    test.loc[row, TARGET_MEMORY] += 1.0


def _unknown_reason(occurrences):
    test = occurrences["test"]
    test.loc[_first(test, NO_NEXT), REASON] = "something_else"


@pytest.mark.parametrize(
    "corrupt",
    [
        _swap_reasons,
        _restore_cross_split_target,
        _drop_same_split_target,
        _change_target_value,
        _unknown_reason,
    ],
    ids=[
        "swapped_null_reasons",
        "restored_cross_split_target",
        "dropped_same_split_target",
        "changed_target_value",
        "unknown_null_reason",
    ],
)
def test_leakage_audit_rejects_inconsistent_targets(corrected, corrupt):
    module = _load_comparison_script()
    _, namespace = corrected
    occurrences, boundaries, before, after = _audit_inputs(namespace)
    corrupt(occurrences)

    with pytest.raises(RuntimeError, match="Split-isolated targets failed validation"):
        module.leakage_audit(occurrences, boundaries, before, after)
