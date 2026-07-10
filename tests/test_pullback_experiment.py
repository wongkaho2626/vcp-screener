"""Unit tests for pullback_experiment.plan_pullback_entry (pure function).
Synthetic bars only. Pivot retest and MA-touch variants."""

import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
)

from pullback_experiment import (
    annotate_pullback_entry,
    plan_pullback_entry,
    pullback_entry_status,
)


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


class TestPullbackEntryStatus:
    """Live-overlay state machine (ma_period=3 keeps fixtures small)."""

    def _status(self, closes, lows=None, pivot=100.0, window=5):
        bars = make_bars(closes, lows)
        return pullback_entry_status(bars, pivot, window=window, ma_period=3)

    def test_below_pivot_is_awaiting_breakout(self):
        s = self._status([95, 96, 97, 98, 97])
        assert s["status"] == "awaiting_breakout"

    def test_breakout_without_touch_is_awaiting_pullback(self):
        # Cross at idx 3; two bars since, price riding well above MA3? No —
        # keep price rising so no strict MA touch: statuses count days.
        s = self._status([95, 96, 97, 103, 106, 109])
        assert s["status"] == "awaiting_pullback"
        assert s["days_since_breakout"] == 2

    def test_touch_and_hold_today_is_buy_zone(self):
        # Cross idx 2; today (idx 4): MA3 = (104+106+105)/3 = 105, low 104.5
        # touches, close 105 holds → buy zone today.
        s = self._status(
            [95, 96, 104, 106, 105],
            lows=[94, 95, 103, 105, 104.5],
        )
        assert s["status"] == "buy_zone_today"

    def test_touch_earlier_is_pullback_done(self):
        # Same touch at idx 4, then one more bar → the signal was 1 day ago.
        s = self._status(
            [95, 96, 104, 106, 105, 108],
            lows=[94, 95, 103, 105, 104.5, 107],
        )
        assert s["status"] == "pullback_done"
        assert s["days_ago"] == 1

    def test_window_expired_without_touch(self):
        s = self._status([95, 96, 97, 103] + [110 + i for i in range(8)], window=5)
        assert s["status"] == "window_expired"

    def test_close_below_stop_invalidates(self):
        # Cross idx 3 then close 91 < pivot*0.92 = 92 while waiting.
        s = self._status([95, 96, 97, 103, 91, 95])
        assert s["status"] == "invalidated"

    def test_no_pivot_is_no_data(self):
        bars = make_bars([95, 96, 97])
        assert pullback_entry_status(bars, None)["status"] == "no_data"


class TestAnnotatePullbackEntry:
    def test_attaches_status_without_mutating_input(self):
        results = [{"symbol": "AAA", "pivot_proximity": {"pivot_price": 100.0}}]
        bars_recent_first = list(reversed(make_bars([95, 96, 97, 98, 97])))
        out = annotate_pullback_entry(
            results, lambda sym: bars_recent_first, ma_period=3
        )
        assert out[0]["pullback_entry_status"] == "awaiting_breakout"
        assert "pullback_entry_status" not in results[0]

    def test_missing_history_is_no_data(self):
        results = [{"symbol": "BBB", "pivot_proximity": {"pivot_price": 50.0}}]
        out = annotate_pullback_entry(results, lambda sym: [])
        assert out[0]["pullback_entry_status"] == "no_data"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
