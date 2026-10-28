from __future__ import annotations

from typing import Dict

from sklearn.dummy import DummyRegressor
from sklearn.ensemble import (
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.tree import DecisionTreeRegressor


RANDOM_SEED = 42


def build_candidate_models() -> Dict[str, object]:
    return {
        "dummy_mean": DummyRegressor(
            strategy="mean",
        ),
        "decision_tree": DecisionTreeRegressor(
            random_state=RANDOM_SEED,
        ),
        "random_forest": RandomForestRegressor(
            n_estimators=100,
            random_state=RANDOM_SEED,
            n_jobs=-1,
        ),
        "hist_gradient_boosting": HistGradientBoostingRegressor(
            random_state=RANDOM_SEED,
        ),
    }