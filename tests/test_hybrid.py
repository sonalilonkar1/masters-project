import numpy as np
import pandas as pd
import pytest

from policies.hybrid import hybrid_recommendation


def test_hybrid_takes_the_larger_value():
    hybrid, missing = hybrid_recommendation([1.0, 5.0, 2.0], [3.0, 4.0, 2.0])

    np.testing.assert_array_equal(hybrid, [3.0, 5.0, 2.0])
    assert not missing.any()


def test_missing_safeguard_falls_back_to_ml():
    hybrid, missing = hybrid_recommendation([1.0, 2.0], [np.nan, 0.5])

    np.testing.assert_array_equal(hybrid, [1.0, 2.0])
    np.testing.assert_array_equal(missing, [True, False])


def test_hybrid_is_never_below_either_input():
    rng = np.random.default_rng(0)
    ml = rng.random(100)
    guard = rng.random(100)
    guard[::7] = np.nan

    hybrid, missing = hybrid_recommendation(ml, guard)

    assert (hybrid >= ml).all()
    assert (hybrid[~missing] >= guard[~missing]).all()
    np.testing.assert_array_equal(missing, np.isnan(guard))


@pytest.mark.parametrize(
    "ml, guard, message",
    [
        ([1.0, np.nan], [1.0, 1.0], "finite"),
        ([-1.0], [1.0], "non-negative"),
        ([1.0], [-1.0], "non-negative"),
        ([1.0], [np.inf], "infinite"),
        ([1.0, 2.0], [1.0], "same shape"),
    ],
)
def test_invalid_inputs_are_rejected(ml, guard, message):
    with pytest.raises(ValueError, match=message):
        hybrid_recommendation(ml, guard)


def test_series_with_different_index_are_rejected():
    ml = pd.Series([1.0, 5.0], index=[10, 20])
    guard = pd.Series([3.0, 4.0], index=[20, 10])

    with pytest.raises(ValueError, match="same index"):
        hybrid_recommendation(ml, guard)


def test_series_with_same_index_are_accepted():
    ml = pd.Series([1.0, 5.0], index=[10, 20])
    guard = pd.Series([3.0, np.nan], index=[10, 20])

    hybrid, missing = hybrid_recommendation(ml, guard)

    np.testing.assert_array_equal(hybrid, [3.0, 5.0])
    np.testing.assert_array_equal(missing, [False, True])
