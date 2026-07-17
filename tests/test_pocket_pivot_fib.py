"""Tests for the frozen Fibonacci-retracement entry on Pocket Pivot signals.

The candidate rule keeps the Pocket Pivot v2 signal unchanged and replaces the
next-open fill with a wait for a 38.2% retracement of the signal leg (lowest
low of the 10 sessions ending at the signal bar, up to the signal bar's high).
The first bar whose low touches the level and whose close holds at or above it
becomes the entry signal; a close below the frozen pattern stop invalidates.
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from portfolio_backtest import Config, _candidate_signals, _plan_pocket_pivot_fib


def bullish_bars(count: int = 220) -> list[dict]:
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


def fib_level(bars: list[dict], signal_idx: int, retracement: float = 0.382) -> float:
    leg_low = min(b["low"] for b in bars[signal_idx - 9:signal_idx + 1])
    leg_high = bars[signal_idx]["high"]
    return leg_high - retracement * (leg_high - leg_low)


def detection(as_of: str) -> dict:
    return {
        "as_of_date": as_of,
        "sector": "Technology",
        "vcp_pattern": {
            "pivot_price": 120.0,
            "contractions": [{"low_price": 110.0}],
        },
    }


def test_fib_entry_fires_on_first_touch_and_hold_of_382_level():
    bars = bullish_bars()
    make_signal_bar(bars, 205)
    level = fib_level(bars, 205)
    assert bars[206]["low"] <= level <= bars[206]["close"]
    assert _plan_pocket_pivot_fib(bars, 205, stop=110.0, pivot=120.0) == 206


def test_fib_entry_skips_when_price_never_retraces_to_the_level():
    bars = bullish_bars()
    make_signal_bar(bars, 205)
    for bar in bars[206:]:
        bar["low"] = bar["close"]
    assert _plan_pocket_pivot_fib(bars, 205, stop=110.0, pivot=120.0) is None


def test_fib_entry_invalidates_on_close_below_pattern_stop_while_waiting():
    bars = bullish_bars()
    make_signal_bar(bars, 205)
    bars[206]["close"] = 109.0
    assert _plan_pocket_pivot_fib(bars, 205, stop=110.0, pivot=120.0) is None


def test_fib_level_uses_the_ten_session_leg_low():
    bars = bullish_bars()
    make_signal_bar(bars, 205)
    bars[200]["low"] = 100.0
    deep_level = fib_level(bars, 205)
    for bar in bars[206:]:
        bar["low"] = deep_level + 1.0
    assert _plan_pocket_pivot_fib(bars, 205, stop=110.0, pivot=120.0) is None


def test_fib_wait_window_is_ten_sessions_after_the_signal_bar():
    bars = bullish_bars()
    make_signal_bar(bars, 205)
    level = fib_level(bars, 205)
    for bar in bars[206:216]:
        bar["low"] = bar["close"]
    bars[216]["low"] = level - 0.5
    assert _plan_pocket_pivot_fib(bars, 205, stop=110.0, pivot=120.0) is None

    inside = bullish_bars()
    make_signal_bar(inside, 205)
    for bar in inside[206:215]:
        bar["low"] = bar["close"]
    inside[215]["low"] = fib_level(inside, 205) - 0.5
    assert _plan_pocket_pivot_fib(inside, 205, stop=110.0, pivot=120.0) == 215


def test_candidate_signals_fill_next_open_after_the_retrace_bar():
    bars = bullish_bars()
    make_signal_bar(bars, 205)
    det = detection("d205")
    with patch(
        "portfolio_backtest.compute_edge_rank",
        return_value={("AAA", "d205"): {"edge_rank": 82.5}},
    ):
        signals = _candidate_signals(
            {"AAA": [det]}, {"AAA": bars}, Config(), entry_rule="pocket_pivot_fib",
        )
    assert len(signals) == 1
    assert signals[0]["signal_date"] == "d206"
    assert signals[0]["fill_date"] == "d207"
    assert signals[0]["pattern_stop"] == 110.0
