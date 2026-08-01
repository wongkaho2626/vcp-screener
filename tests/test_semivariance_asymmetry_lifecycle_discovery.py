from __future__ import annotations

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from semivariance_asymmetry_lifecycle_discovery import (
    semivariance_ratio,
    semivariance_state,
)


def bars(closes: list[float]) -> list[dict]:
    return [{"date": f"d{index:03d}", "open": close,
             "high": close * 1.01, "low": close * .99,
             "close": close, "volume": 1000}
            for index, close in enumerate(closes)]


def test_semivariance_separates_positive_and_negative_squared_returns() -> None:
    history = bars([100, 110, 100, 120])
    upside, downside, ratio = semivariance_ratio(history, 3, period=3) or (0, 0, 0)
    assert upside == pytest.approx(.1 ** 2 + .2 ** 2)
    assert downside == pytest.approx((100 / 110 - 1) ** 2)
    assert ratio == pytest.approx(upside / downside)


def test_all_up_window_has_infinite_ratio_and_can_enter_above_pivot() -> None:
    history = bars([100, 101, 102, 103])
    state = semivariance_state(history, 3, pivot=102, period=3,
                               entry_ratio=1.5, exit_ratio=.75)
    assert math.isinf(float(state["semivariance_ratio"]))
    assert state["positive_cross"]
    assert not state["negative_dominance"]


def test_downside_dominance_is_failure_and_pivot_blocks_entry() -> None:
    history = bars([100, 90, 80, 81])
    state = semivariance_state(history, 3, pivot=100, period=3,
                               entry_ratio=1.5, exit_ratio=.75)
    assert not state["positive_cross"]
    assert state["negative_dominance"]


def test_flat_window_is_undefined_and_future_append_is_invariant() -> None:
    history = bars([100, 100, 100, 100])
    before = semivariance_state(history, 3, pivot=90, period=3,
                                entry_ratio=1.5, exit_ratio=.75)
    assert before["semivariance_ratio"] is None
    extended = [*history, {"date": "d004", "open": 200, "high": 201,
                           "low": 199, "close": 200, "volume": 1000}]
    assert semivariance_state(extended, 3, pivot=90, period=3,
                              entry_ratio=1.5, exit_ratio=.75) == before


def test_semivariance_rejects_invalid_threshold_order() -> None:
    with pytest.raises(ValueError):
        semivariance_state(bars([1, 2]), 1, pivot=1, period=1,
                           entry_ratio=.5, exit_ratio=.75)
