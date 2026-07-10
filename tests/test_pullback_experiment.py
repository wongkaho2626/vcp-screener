"""Unit tests for pullback_experiment.plan_pullback_entry (pure function).
Synthetic bars only. Pivot retest and MA-touch variants."""

import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
)

from pullback_experiment import plan_pullback_entry


def make_bars(closes, lows=None):
    lows = lows or closes
    return [
        {"date": f"d{i:03d}", "close": c, "low": lo, "volume": 1000}
        for i, (c, lo) in enumerate(zip(closes, lows))
    ]


class TestPivotRetest:
    def test_touch_and_hold_enters_at_that_close(self):
        # Breakout at idx 2 (pivot 100); bar 4 dips to 101 (within 2%) and
        # closes at 103 → entry at 103.
        bars = make_bars(
            [98, 99, 105, 106, 103, 108],
            lows=[97, 98, 104, 105, 101, 107],
        )
        plan = plan_pullback_entry(bars, bo_idx=2, pivot=100.0, stop=92.0)
        assert plan == {"entry_idx": 4, "entry_price": 103}

    def test_no_pullback_within_window_returns_none(self):
        closes = [98, 99, 105] + [110] * 20
        bars = make_bars(closes)
        assert plan_pullback_entry(bars, bo_idx=2, pivot=100.0, stop=92.0, window=15) is None

    def test_invalidated_when_close_breaks_stop_first(self):
        # Bar 3 closes below the pattern stop before any retest → dead.
        bars = make_bars(
            [98, 99, 105, 91, 103, 108],
            lows=[97, 98, 104, 90, 101, 107],
        )
        assert plan_pullback_entry(bars, bo_idx=2, pivot=100.0, stop=92.0) is None

    def test_touch_without_hold_waits_for_later_hold(self):
        # Bar 3 touches but closes below pivot (no hold); bar 4 holds → entry bar 4.
        bars = make_bars(
            [98, 99, 105, 99, 102, 108],
            lows=[97, 98, 104, 98, 100.5, 107],
        )
        plan = plan_pullback_entry(bars, bo_idx=2, pivot=100.0, stop=92.0)
        assert plan == {"entry_idx": 4, "entry_price": 102}


class TestMaTouchVariant:
    def test_ma_touch_entry(self):
        # MA mode uses a strict touch (low <= MA, no tolerance) because the MA
        # lags price. MA3 at bar 5 = (106+104+105)/3 = 105; low 103.9 <= 105
        # and close 105 >= 105 → entry at bar 5. Bars 3-4 must not fill:
        # bar 3 low 105 > MA3 103.33; bar 4 close 104 < MA3 105 (no hold).
        bars = make_bars(
            [98, 99, 105, 106, 104, 105],
            lows=[97, 98, 104, 105, 103, 103.9],
        )
        plan = plan_pullback_entry(bars, bo_idx=2, pivot=100.0, stop=92.0, ma_period=3)
        assert plan == {"entry_idx": 5, "entry_price": 105}

    def test_ma_insufficient_history_never_fills(self):
        bars = make_bars([98, 99, 105, 104, 103, 102])
        assert plan_pullback_entry(bars, bo_idx=2, pivot=100.0, stop=92.0, ma_period=50) is None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
