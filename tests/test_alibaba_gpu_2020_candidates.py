import numpy as np
import pandas as pd

from src.features.alibaba_gpu_2020_ml_prep import (
    clip_negative_predictions,
)
from src.models.alibaba_gpu_2020_candidates import (
    build_candidate_models,
)


def make_fixture():
    X = pd.DataFrame(
        {
            "requested_cpu": [10, 20, 30, 40, 50, 60],
            "requested_memory": [1, 2, 3, 4, 5, 6],
            "inst_num": [1, 1, 2, 2, 3, 3],
        }
    )

    y = pd.Series(
        [12, 18, 33, 39, 55, 61],
        dtype=float,
    )

    return X, y


def test_all_candidate_models_fit_and_predict():
    X, y = make_fixture()

    models = build_candidate_models()

    assert set(models) == {
        "dummy_mean",
        "decision_tree",
        "random_forest",
        "hist_gradient_boosting",
    }

    for model in models.values():
        model.fit(X, y)

        predictions = model.predict(X)

        assert len(predictions) == len(X)
        assert np.isfinite(predictions).all()


def test_candidate_model_predictions_can_be_clipped():
    predictions = np.array(
        [-1.0, 0.0, 10.0]
    )

    clipped, count = clip_negative_predictions(
        predictions
    )

    assert count == 1
    assert clipped.tolist() == [
        0.0,
        0.0,
        10.0,
    ]


def test_candidate_registry_is_reproducible():
    first = build_candidate_models()
    second = build_candidate_models()

    assert (
        first["decision_tree"].random_state
        == second["decision_tree"].random_state
    )

    assert (
        first["random_forest"].random_state
        == second["random_forest"].random_state
    )

    assert (
        first["hist_gradient_boosting"].random_state
        == second["hist_gradient_boosting"].random_state
    )