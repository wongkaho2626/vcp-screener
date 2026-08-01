from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from ichimoku_equilibrium_lifecycle_discovery import (
    ichimoku_state,
    ichimoku_values,
    range_midpoint,
)


def bars(highs: list[float], lows: list[float],
         closes: list[float] | None = None) -> list[dict]:
    if closes is None:
        closes = [(high + low) / 2 for high, low in zip(highs, lows)]
    return [{"date": f"d{index:03d}", "open": close, "high": high,
             "low": low, "close": close, "volume": 1000}
            for index, (high, low, close) in enumerate(zip(highs, lows, closes))]


def test_range_midpoint_uses_only_completed_window() -> None:
    history = bars([10, 20, 15, 30], [4, 8, 6, 12])
    assert range_midpoint(history, 2, period=3) == 12
    assert range_midpoint(history, 3, period=2) == 18


def test_ichimoku_values_are_unshifted_current_midpoints() -> None:
    history = bars([10, 11, 12, 13, 14, 15], [1, 2, 3, 4, 5, 6])
    values = ichimoku_values(history, 5, 2, 4, 6)
    assert values == (10.0, 9.0, 9.5, 8.0)


def test_state_requires_fast_base_cloud_and_pivot_confirmation() -> None:
    history = bars([10, 11, 12, 13, 14, 15], [1, 2, 3, 4, 5, 6],
                   [5, 6, 7, 8, 9, 12])
    state = ichimoku_state(history, 5, pivot=11,
                           tenkan_period=2, kijun_period=4, span_b_period=6)
    assert state["positive_cross"]
    assert not state["negative_dominance"]
    assert not ichimoku_state(history, 5, pivot=13,
                              tenkan_period=2, kijun_period=4,
                              span_b_period=6)["positive_cross"]


def test_reverse_midpoint_order_is_failure_and_future_append_is_invariant() -> None:
    history = bars([20, 19, 18, 17, 16, 15], [10, 9, 8, 7, 6, 5])
    before = ichimoku_state(history, 5, pivot=1,
                            tenkan_period=2, kijun_period=4, span_b_period=6)
    assert not before["positive_cross"]
    assert before["negative_dominance"]
    extended = [*history, {"date": "d006", "open": 100, "high": 101,
                           "low": 99, "close": 100, "volume": 1000}]
    assert ichimoku_state(extended, 5, pivot=1, tenkan_period=2,
                          kijun_period=4, span_b_period=6) == before


def test_ichimoku_rejects_non_increasing_periods() -> None:
    with pytest.raises(ValueError):
        ichimoku_values(bars([2, 3], [1, 2]), 1, 2, 2, 3)
