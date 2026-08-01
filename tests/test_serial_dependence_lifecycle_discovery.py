from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from dmi_crossover_lifecycle_discovery import lifecycle_signals
from serial_dependence_lifecycle_discovery import (
    lag1_autocorrelation,
    serial_dependence_state,
)


def _bars_from_returns(returns: list[float]) -> list[dict]:
    close = 100.0
    bars = [{"date": "2020-01-01", "open": close, "high": close,
             "low": close, "close": close, "volume": 1_000}]
    for index, value in enumerate(returns, start=2):
        close *= 1 + value
        bars.append({"date": f"2020-01-{index:02d}", "open": close,
                     "high": close, "low": close, "close": close,
                     "volume": 1_000})
    return bars


def test_lag1_autocorrelation_matches_known_cross() -> None:
    returns = [-.02, -.02, -.01, -.02, -.01, .01]
    bars = _bars_from_returns(returns)
    prior = lag1_autocorrelation(bars, 5, period=5)
    current = lag1_autocorrelation(bars, 6, period=5)
    assert prior is not None and abs(prior - (-0.5773502692)) < 1e-8
    assert current is not None and abs(current - 0.2294157339) < 1e-8


def test_serial_dependence_cross_is_close_confirmed_and_above_pivot() -> None:
    bars = _bars_from_returns([-.02, -.02, -.01, -.02, -.01, .01])
    state = serial_dependence_state(
        bars, 6, pivot=float(bars[6]["close"]) - .01, period=5)
    assert state["positive_cross"]
    assert not state["negative_dominance"]
    blocked = serial_dependence_state(
        bars, 6, pivot=float(bars[6]["close"]), period=5)
    assert not blocked["positive_cross"]


def test_zero_variance_window_is_undefined() -> None:
    bars = _bars_from_returns([.01] * 6)
    assert lag1_autocorrelation(bars, 6, period=5) is None
    assert serial_dependence_state(bars, 6, 1.0, period=5) == {
        "positive_cross": False, "negative_dominance": False,
        "lag1_autocorrelation": None,
        "prior_lag1_autocorrelation": None,
    }


def test_future_bars_do_not_change_completed_state() -> None:
    bars = _bars_from_returns([-.02, -.02, -.01, -.02, -.01, .01])
    initial = serial_dependence_state(bars, 6, 1.0, period=5)
    extended = bars + _bars_from_returns([.50])[1:]
    assert serial_dependence_state(extended, 6, 1.0, period=5) == initial


def test_lifecycle_entry_and_exit_are_next_open_indices() -> None:
    base = {
        "setup_id": "AAA|2020-01-01|0", "symbol": "AAA", "sector": "Tech",
        "edge_rank": 70.0, "pattern_stop": 90.0, "pivot": 100.0,
    }
    states = []
    for index, (positive, negative) in enumerate([
        (False, False), (True, False), (False, True), (False, True),
    ]):
        states.append({**base, "signal_date": f"2020-01-{index + 1:02d}",
                       "fill_date": f"2020-01-{index + 2:02d}",
                       "fill_idx": index + 1, "positive_cross": positive,
                       "negative_dominance": negative})
    signals = lifecycle_signals(states)
    assert signals[0]["signal_date"] == "2020-01-02"
    assert signals[0]["fill_date"] == "2020-01-03"
    assert signals[0]["model_exit_idx"] == 4
