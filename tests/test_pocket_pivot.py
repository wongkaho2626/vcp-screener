"""Focused tests for the frozen, causal Pocket Pivot entry rule."""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from portfolio_backtest import Config, _candidate_signals, _plan_pocket_pivot


def bullish_bars(count: int = 215) -> list[dict]:
    return [
        {
            "date": f"d{i:03d}",
            "open": 100 + i * 0.1,
            "high": 101 + i * 0.1,
            "low": 99 + i * 0.1,
            "close": 100 + i * 0.1,
            "volume": 500,
        }
        for i in range(count)
    ]


def make_signal_bar(bars: list[dict], index: int, volume: int = 1_001) -> None:
    bars[index - 1]["close"] = bars[index - 2]["close"] - 0.1
    bars[index - 1]["volume"] = 1_000
    bars[index]["volume"] = volume


def detection(as_of: str) -> dict:
    return {
        "as_of_date": as_of,
        "sector": "Technology",
        "vcp_pattern": {
            "pivot_price": 120.0,
            "contractions": [{"low_price": 110.0}],
        },
    }


def test_pocket_pivot_accepts_strict_volume_and_bullish_location_rules():
    bars = bullish_bars()
    make_signal_bar(bars, 205)
    assert _plan_pocket_pivot(bars, 205, stop=110.0, pivot=120.0) == 205


def test_pocket_pivot_requires_a_prior_down_day_and_strictly_greater_volume():
    no_down_day = bullish_bars()
    no_down_day[205]["volume"] = 10_000
    assert _plan_pocket_pivot(no_down_day, 205, stop=110.0, pivot=120.0, window=1) is None

    tied_volume = bullish_bars()
    make_signal_bar(tied_volume, 205, volume=1_000)
    assert _plan_pocket_pivot(tied_volume, 205, stop=110.0, pivot=120.0, window=1) is None


def test_pocket_pivot_invalidates_on_close_below_pattern_stop():
    bars = bullish_bars()
    bars[205]["volume"] = 1
    bars[206]["close"] = 109.0
    make_signal_bar(bars, 208)
    assert _plan_pocket_pivot(bars, 205, stop=110.0, pivot=120.0) is None


def test_pocket_pivot_window_is_ten_sessions_including_as_of_bar():
    bars = bullish_bars(220)
    bars[205]["volume"] = 1
    make_signal_bar(bars, 215)
    assert _plan_pocket_pivot(bars, 205, stop=100.0, pivot=125.0) is None


def test_candidate_signal_uses_as_of_pattern_fields_without_forward_outcome():
    bars = bullish_bars()
    make_signal_bar(bars, 205)
    det = detection("d205")
    with patch(
        "portfolio_backtest.compute_edge_rank",
        return_value={("AAA", "d205"): {"edge_rank": 82.5}},
    ):
        signals = _candidate_signals(
            {"AAA": [det]}, {"AAA": bars}, Config(), entry_rule="pocket_pivot",
        )
    assert len(signals) == 1
    assert signals[0]["signal_date"] == "d205"
    assert signals[0]["fill_date"] == "d206"
    assert signals[0]["pattern_stop"] == 110.0

