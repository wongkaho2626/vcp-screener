from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from atr_range_expansion_discovery import range_expansion_state, true_range_series


def bar(close: float, high: float | None = None,
        low: float | None = None) -> dict:
    return {"date": "d", "open": close,
            "high": close + 1 if high is None else high,
            "low": close - 1 if low is None else low,
            "close": close, "volume": 1000}


def test_true_range_includes_gap_from_prior_close() -> None:
    bars = [bar(10), bar(15, high=16, low=14)]
    assert true_range_series(bars) == [None, 6.0]


def test_range_expansion_uses_prior_atr_and_close_location() -> None:
    bars = [bar(10), bar(10), bar(10), bar(14, high=15, low=9)]
    ranges = true_range_series(bars)
    ema = [None, None, 10.0, 11.0]
    state = range_expansion_state(
        bars, ranges, ema, 3, pivot=12, atr_lookback=2,
        atr_multiple=1.5, close_location_min=.75)
    assert state == {"positive_cross": True, "negative_dominance": False}


def test_range_expansion_requires_pivot_and_positive_close() -> None:
    bars = [bar(10), bar(10), bar(10), bar(9, high=15, low=8)]
    ranges = true_range_series(bars)
    ema = [None, None, 10.0, 10.0]
    state = range_expansion_state(
        bars, ranges, ema, 3, pivot=12, atr_lookback=2,
        atr_multiple=1.5, close_location_min=0)
    assert not state["positive_cross"]
    assert state["negative_dominance"]


def test_future_append_cannot_change_existing_expansion_state() -> None:
    bars = [bar(10), bar(10), bar(10), bar(14, high=15, low=9)]
    ranges = true_range_series(bars)
    ema = [None, None, 10.0, 11.0]
    before = range_expansion_state(
        bars, ranges, ema, 3, pivot=12, atr_lookback=2,
        atr_multiple=1.5, close_location_min=.75)
    extended = [*bars, bar(100)]
    after = range_expansion_state(
        extended, true_range_series(extended), [*ema, 20.0], 3, pivot=12,
        atr_lookback=2, atr_multiple=1.5, close_location_min=.75)
    assert after == before
