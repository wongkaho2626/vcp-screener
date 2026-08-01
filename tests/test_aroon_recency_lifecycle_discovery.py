from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from aroon_recency_lifecycle_discovery import aroon_state, aroon_values


def bars(highs: list[float], lows: list[float],
         closes: list[float] | None = None) -> list[dict]:
    if closes is None:
        closes = [(high + low) / 2 for high, low in zip(highs, lows)]
    return [{"date": f"d{index:03d}", "open": close, "high": high,
             "low": low, "close": close, "volume": 1000}
            for index, (high, low, close) in enumerate(zip(highs, lows, closes))]


def test_current_high_and_oldest_low_produce_fresh_high_state() -> None:
    history = bars([10, 11, 12, 13, 20], [1, 5, 6, 7, 8])
    up, down = aroon_values(history, 4, period=5) or (None, None)
    assert up == 100
    assert down == 20


def test_tied_extreme_uses_most_recent_occurrence() -> None:
    history = bars([20, 11, 12, 20, 15], [5, 1, 3, 1, 4])
    up, down = aroon_values(history, 4, period=5) or (None, None)
    assert up == 80
    assert down == 80


def test_aroon_state_requires_recency_thresholds_and_pivot() -> None:
    history = bars([10, 11, 12, 13, 20], [1, 5, 6, 7, 8],
                   [6, 8, 9, 10, 15])
    state = aroon_state(history, 4, pivot=14, period=5,
                        entry_up=70, entry_down=50)
    assert state["positive_cross"]
    assert not state["negative_dominance"]
    assert not aroon_state(history, 4, pivot=16, period=5,
                           entry_up=70, entry_down=50)["positive_cross"]


def test_reverse_recency_is_failure_and_future_append_is_invariant() -> None:
    history = bars([20, 15, 14, 13, 12], [5, 4, 3, 2, 1])
    before = aroon_state(history, 4, pivot=1, period=5,
                         entry_up=70, entry_down=50)
    assert not before["positive_cross"]
    assert before["negative_dominance"]
    extended = [*history, {"date": "d005", "open": 100, "high": 101,
                           "low": 99, "close": 100, "volume": 1000}]
    assert aroon_state(extended, 4, pivot=1, period=5,
                       entry_up=70, entry_down=50) == before


def test_aroon_rejects_invalid_period() -> None:
    with pytest.raises(ValueError):
        aroon_values(bars([2], [1]), 0, period=1)
