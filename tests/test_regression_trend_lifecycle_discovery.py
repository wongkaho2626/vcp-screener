from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from regression_trend_lifecycle_discovery import regression_state, regression_trend


def bars(closes: list[float]) -> list[dict]:
    return [{"date": f"d{i:03d}", "open": close, "high": close + 1,
             "low": close - 1, "close": close, "volume": 1000}
            for i, close in enumerate(closes)]


def test_perfect_exponential_path_has_positive_slope_and_unit_r_squared() -> None:
    history = bars([math.exp(.1 * index) for index in range(5)])
    slope, r_squared = regression_trend(history, 4, period=5) or (None, None)
    assert slope is not None and abs(slope - .1) < 1e-12
    assert r_squared is not None and abs(r_squared - 1) < 1e-12


def test_regression_state_requires_slope_fit_and_pivot() -> None:
    history = bars([math.exp(.1 * index) for index in range(5)])
    assert regression_state(history, 4, pivot=1, period=5,
                            entry_r2=.5, exit_r2=.2)["positive_cross"]
    assert not regression_state(history, 4, pivot=100, period=5,
                                entry_r2=.5, exit_r2=.2)["positive_cross"]


def test_flat_path_is_failure_not_entry() -> None:
    history = bars([10.0] * 5)
    state = regression_state(history, 4, pivot=1, period=5,
                             entry_r2=.5, exit_r2=.2)
    assert not state["positive_cross"]
    assert state["negative_dominance"]


def test_future_append_cannot_change_existing_regression_state() -> None:
    history = bars([math.exp(.1 * index) for index in range(5)])
    before = regression_state(history, 4, pivot=1, period=5,
                              entry_r2=.5, exit_r2=.2)
    extended = [*history, *bars([1.0, 1000.0])]
    assert regression_state(extended, 4, pivot=1, period=5,
                            entry_r2=.5, exit_r2=.2) == before
