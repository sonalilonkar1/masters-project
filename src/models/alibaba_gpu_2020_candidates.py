from __future__ import annotations
from typing import Dict
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import (
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.tree import DecisionTreeRegressor

try:  # XGBoost is in requirements; include it when importable and reproducible.
    from xgboost import XGBRegressor
    HAS_XGBOOST = True
except Exception:  # pragma: no cover - environment without xgboost
    HAS_XGBOOST = False

RANDOM_SEED = 42


def build_candidate_models() -> Dict[str, object]:
    """Candidate regressors shared by CPU and memory.

    DummyRegressor(mean) is a recorded floor, not a selectable learner. The
    tree/boosting models fit heavy-tailed tabular data with mixed categorical
    and numeric features. XGBoost is included when the library is importable
    (issue #89: optional, installation/reproducibility confirmed here).
    """
    models: Dict[str, object] = {
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
    if HAS_XGBOOST:
        models["xgboost"] = XGBRegressor(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            objective="reg:squarederror",
            random_state=RANDOM_SEED,
            n_jobs=-1,
        )
    return models
