from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from three_bar_staircase_discovery import staircase_state


def bars(closes: list[float], lows: list[float]) -> list[dict]:
    return [{"date": f"d{i:03d}", "open": close, "high": close + 1,
             "low": low, "close": close, "volume": 1000}
            for i, (close, low) in enumerate(zip(closes, lows))]


def test_staircase_requires_three_rising_closes_and_lows_above_pivot() -> None:
    history = bars([10, 11, 12], [8, 9, 10])
    assert staircase_state(history, 2, pivot=11) == {
        "positive_cross": True, "negative_dominance": False,
    }
    assert not staircase_state(history, 2, pivot=13)["positive_cross"]


def test_staircase_rejects_flat_close_or_low() -> None:
    assert not staircase_state(
        bars([10, 10, 12], [8, 9, 10]), 2, pivot=1)["positive_cross"]
    assert not staircase_state(
        bars([10, 11, 12], [8, 8, 10]), 2, pivot=1)["positive_cross"]


def test_failure_exit_requires_close_below_both_prior_lows() -> None:
    history = bars([10, 11, 7], [8, 9, 6])
    assert staircase_state(history, 2, pivot=100) == {
        "positive_cross": False, "negative_dominance": True,
    }


def test_future_append_cannot_change_existing_staircase_state() -> None:
    history = bars([10, 11, 12], [8, 9, 10])
    before = staircase_state(history, 2, pivot=11)
    extended = bars([10, 11, 12, 1, 100], [8, 9, 10, 0, 99])
    assert staircase_state(extended, 2, pivot=11) == before
