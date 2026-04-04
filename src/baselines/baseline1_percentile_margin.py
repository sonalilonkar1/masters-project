# src/baselines/baseline1_percentile_margin.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class Baseline1PercentileMargin:
    """
    Baseline 1: per-recurring-job percentile sizing (P95/P99) computed on TRAIN history only.
    - Fit: compute quantiles for peak_cpu and peak_mem grouped by recurring_job_id.
    - Predict: join quantiles onto rows; fallback to original request if no history.
    Optional additive margins can be used to be more conservative.
    """

    quantiles_: Optional[pd.DataFrame] = None

    def fit(
        self,
        train_df: pd.DataFrame,
        q: float,
        min_history: int = 3,
    ) -> "Baseline1PercentileMargin":
        if not (0.0 < q < 1.0):
            raise ValueError(f"q must be in (0,1), got {q}")

        required = {"recurring_job_id", "peak_cpu", "peak_mem"}
        missing = required - set(train_df.columns)
        if missing:
            raise ValueError(f"train_df missing columns: {sorted(missing)}")

        # Compute quantiles and history counts on TRAIN only.
        grp = train_df.groupby("recurring_job_id", as_index=False)
        quant = grp.agg(
            rec_cpu=("peak_cpu", lambda x: float(np.quantile(x.to_numpy(), q))),
            rec_mem=("peak_mem", lambda x: float(np.quantile(x.to_numpy(), q))),
            n_hist=("peak_cpu", "size"),
        )

        # Enforce minimum history: jobs with insufficient history will not have quantiles.
        quant.loc[quant["n_hist"] < min_history, ["rec_cpu", "rec_mem"]] = np.nan

        self.quantiles_ = quant
        return self

    def predict(
        self,
        df: pd.DataFrame,
        margin_cpu: float = 0.0,
        margin_mem: float = 0.0,
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Returns (rec_cpu, rec_mem, n_hist) aligned to df.index
        """
        if self.quantiles_ is None:
            raise RuntimeError("Call fit() before predict().")

        required = {"recurring_job_id", "req_cpu", "req_mem"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"df missing columns: {sorted(missing)}")

        merged = df.merge(self.quantiles_, on="recurring_job_id", how="left")

        rec_cpu = merged["rec_cpu"].copy()
        rec_mem = merged["rec_mem"].copy()

        # Fallback to original requests if we have no quantile (cold start or insufficient history).
        rec_cpu = rec_cpu.fillna(merged["req_cpu"])
        rec_mem = rec_mem.fillna(merged["req_mem"])

        # Add optional safety margin
        rec_cpu = rec_cpu.astype(float) + float(margin_cpu)
        rec_mem = rec_mem.astype(float) + float(margin_mem)

        n_hist = merged["n_hist"].fillna(0).astype(int)

        # Return series aligned to original df index
        rec_cpu.index = df.index
        rec_mem.index = df.index
        n_hist.index = df.index
        return rec_cpu, rec_mem, n_hist