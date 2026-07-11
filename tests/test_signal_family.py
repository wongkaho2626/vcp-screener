"""Unit tests for signal_family_experiment pure functions (RSI, mean-reversion
walker, 52-week-high walker, momentum score/rank, month-end calendar).
Synthetic bars; small periods for hand-checkable numbers."""

import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
)

from signal_family_experiment import (
    mean_reversion_trades,
    momentum_score,
    month_end_indices,
    near_high_trades,
    rank_momentum,
    wilder_rsi,
)


def make_bars(closes):
    return [{"date": f"d{i:03d}", "close": c} for i, c in enumerate(closes)]


class TestWilderRSI:
    def test_warmup_is_none(self):
        vals = wilder_rsi([10, 11, 10, 9], period=2)
        assert vals[0] is None and vals[1] is None

    def test_hand_computed_values(self):
        # deltas +1, -1, -1 → idx2: avgG=.5 avgL=.5 → RSI 50;
        # idx3: avgG=.25 avgL=.75 → RS 1/3 → RSI 25.
        vals = wilder_rsi([10, 11, 10, 9], period=2)
        assert vals[2] == pytest.approx(50.0)
        assert vals[3] == pytest.approx(25.0)

    def test_all_gains_is_100(self):
        vals = wilder_rsi([10, 11, 12, 13], period=2)
        assert vals[3] == pytest.approx(100.0)


class TestMeanReversionTrades:
    # Uptrend 5..15 (+2/bar), then -1, -1: RSI2 at idx7 = 40 (<45 test
    # threshold) and close 13 > SMA6 12.5 → enter idx7.
    BASE = [5, 7, 9, 11, 13, 15, 14, 13]

    def test_enters_on_oversold_in_uptrend_and_exits_on_rsi(self):
        bars = make_bars(self.BASE + [15])  # idx8: RSI2 ≈ 76.9 > 70 → exit
        trades = mean_reversion_trades(
            bars, ma_period=6, rsi_period=2, entry_th=45.0, exit_th=70.0,
            max_hold=10, stop_pct=8.0,
        )
        assert len(trades) == 1
        t = trades[0]
        assert (t["entry_idx"], t["exit_idx"], t["reason"]) == (7, 8, "rsi")

    def test_stop_exits_full(self):
        # Entry 13 at idx7; idx8 close 11.9 < 13*0.92 = 11.96 → stop.
        bars = make_bars(self.BASE + [11.9])
        trades = mean_reversion_trades(
            bars, ma_period=6, rsi_period=2, entry_th=45.0, exit_th=70.0,
            max_hold=10, stop_pct=8.0,
        )
        assert len(trades) == 1
        assert trades[0]["reason"] == "stop"
        assert trades[0]["exit_idx"] == 8

    def test_timeout_after_max_hold(self):
        # Small gains keep RSI2 below 70 → timeout at entry+2.
        bars = make_bars(self.BASE + [13.1, 13.2])
        trades = mean_reversion_trades(
            bars, ma_period=6, rsi_period=2, entry_th=45.0, exit_th=70.0,
            max_hold=2, stop_pct=8.0,
        )
        assert len(trades) == 1
        assert (trades[0]["exit_idx"], trades[0]["reason"]) == (9, "timeout")

    def test_no_entry_when_below_ma(self):
        # Downtrend: close never above SMA → no trades even with RSI oversold.
        bars = make_bars([15, 14, 13, 12, 11, 10, 9, 8, 7, 6])
        trades = mean_reversion_trades(
            bars, ma_period=6, rsi_period=2, entry_th=45.0, exit_th=70.0,
            max_hold=10, stop_pct=8.0,
        )
        assert trades == []


class TestNearHighTrades:
    def test_enters_at_new_high_above_ma(self):
        # idx5 close 10.5 = 5-bar rolling max, > SMA3 10.17 → enter.
        bars = make_bars([10, 10, 10, 10, 10, 10.5, 10.6, 10.7])
        trades = near_high_trades(
            bars, lookback=5, within_pct=2.0, ma_period=3, stop_pct=8.0,
            max_hold=60, cooldown=3,
        )
        assert trades
        assert trades[0]["entry_idx"] == 5
        assert trades[0]["stop_price"] == pytest.approx(10.5 * 0.92)

    def test_flat_series_never_enters(self):
        # close == SMA (not strictly above) → filter blocks entry.
        bars = make_bars([10] * 12)
        trades = near_high_trades(
            bars, lookback=5, within_pct=2.0, ma_period=3, stop_pct=8.0,
            max_hold=60, cooldown=3,
        )
        assert trades == []

    def test_cooldown_blocks_reentry(self):
        # Rising series is always near its high; max_hold=2 forces exit at
        # idx7; cooldown=3 → next entry must be past idx 7+3.
        closes = [10] * 5 + [10.5 + 0.1 * i for i in range(10)]
        bars = make_bars(closes)
        trades = near_high_trades(
            bars, lookback=5, within_pct=2.0, ma_period=3, stop_pct=8.0,
            max_hold=2, cooldown=3,
        )
        assert len(trades) >= 2
        assert trades[0]["entry_idx"] == 5
        assert trades[0]["exit_idx"] == 7
        assert trades[1]["entry_idx"] == 11


class TestMomentum:
    def test_score_skips_recent_window(self):
        closes = [10, 10, 12, 15, 20, 30]
        # closes[5-1]/closes[5-4] - 1 = 20/10 - 1
        assert momentum_score(closes, 5, lb_long=4, lb_skip=1) == pytest.approx(1.0)

    def test_score_none_without_history(self):
        assert momentum_score([10, 11, 12], 2, lb_long=4, lb_skip=1) is None

    def test_rank_takes_top_fraction_ceil(self):
        scores = {"A": 0.5, "B": 0.2, "C": 0.9}
        assert rank_momentum(scores, top_frac=0.5) == ["C", "A"]

    def test_month_end_indices_excludes_final_bar(self):
        dates = ["2020-01-30", "2020-01-31", "2020-02-03", "2020-02-28",
                 "2020-03-02"]
        assert month_end_indices(dates) == [1, 3]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
