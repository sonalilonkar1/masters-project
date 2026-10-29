# src/policies/hybrid.py
#
# TraceAdvisor Hybrid recommendation rule.
#
# Hybrid combines the ML prediction with a conservative historical
# safeguard (the P95 baseline in the 295B backlog):
#
#     hybrid = max(ML prediction, safeguard)
#
# When the safeguard is unavailable (for example, no request and no usable
# history), the Hybrid recommendation falls back to the ML prediction instead
# of becoming unknown. Rows using that fallback are flagged.

from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd


def hybrid_recommendation(
    ml_prediction,
    safeguard,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Return (hybrid values, safeguard_missing flags).

    - ml_prediction must be finite and non-negative for every row.
    - safeguard may be NaN (unavailable); otherwise it must be finite and
      non-negative.
    - hybrid = max(ml_prediction, safeguard), or ml_prediction where the
      safeguard is NaN.
    - Inputs are paired by position. Two pandas Series must share the same
      index, so rows are never paired across different occurrences.
    """
    if isinstance(ml_prediction, pd.Series) and isinstance(safeguard, pd.Series):
        if not ml_prediction.index.equals(safeguard.index):
            raise ValueError("ml_prediction and safeguard Series must have the same index.")

    ml = np.asarray(ml_prediction, dtype=float)
    guard = np.asarray(safeguard, dtype=float)

    if ml.shape != guard.shape:
        raise ValueError(
            f"ml_prediction and safeguard must have the same shape; "
            f"got {ml.shape} and {guard.shape}."
        )

    if not np.isfinite(ml).all():
        raise ValueError("ml_prediction must be finite for every row.")

    if (ml < 0).any():
        raise ValueError("ml_prediction must be non-negative.")

    guard_missing = np.isnan(guard)

    if np.isinf(guard).any():
        raise ValueError("safeguard must not contain infinite values.")

    if (guard[~guard_missing] < 0).any():
        raise ValueError("safeguard must be non-negative where available.")

    # fmax ignores NaN, so a missing safeguard leaves the ML prediction.
    return np.fmax(ml, guard), guard_missing
