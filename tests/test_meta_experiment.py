"""Unit tests for meta_experiment pure feature functions (M.E.T. edges).
Synthetic bars only; small MA periods keep fixtures readable."""

import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
)

from meta_experiment import (
    low_volume_pullback,
    ma200_uptrend,
    ma_support_edge,
    sma_at,
)


def make_bars(closes, lows=None, volumes=None):
    """Oldest-first bars; lows/volumes default to close/1000."""
    lows = lows or closes
    volumes = volumes or [1000] * len(closes)
    return [
        {"date": f"d{i:03d}", "close": c, "low": lo, "volume": v}
        for i, (c, lo, v) in enumerate(zip(closes, lows, volumes))
    ]


class TestSmaAt:
    def test_mean_of_trailing_window_including_current(self):
        bars = make_bars([1, 2, 3, 4, 5])
        assert sma_at(bars, 4, 3) == pytest.approx(4.0)  # (3+4+5)/3

    def test_none_when_insufficient_history(self):
        bars = make_bars([1, 2])
        assert sma_at(bars, 1, 3) is None


class TestMa200Uptrend:
    def test_rising_series_passes(self):
        bars = make_bars(list(range(1, 21)))
        assert ma200_uptrend(bars, 19, period=5, slope_bars=2)

    def test_falling_series_fails(self):
        bars = make_bars(list(range(20, 0, -1)))
        assert not ma200_uptrend(bars, 19, period=5, slope_bars=2)

    def test_insufficient_history_fails(self):
        bars = make_bars([1, 2, 3])
        assert not ma200_uptrend(bars, 2, period=5, slope_bars=2)


class TestMaSupportEdge:
    def test_pullback_low_touching_ma_and_holding(self):
        # Flat tape: SMA3 = 10; final bar dips to 9.9 and closes at 10.
        bars = make_bars([10, 10, 10, 10, 10], lows=[10, 10, 10, 10, 9.9])
        assert ma_support_edge(bars, 4, periods=(3,), lookback=2)

    def test_price_extended_far_above_ma_is_not_support(self):
        bars = make_bars([10, 11, 12, 13, 14], lows=[10, 11, 12, 13, 13.5])
        assert not ma_support_edge(bars, 4, periods=(3,), lookback=2)

    def test_close_breaking_below_ma_is_not_support(self):
        # Low touches SMA3 but the close finishes well below it: broken, not held.
        bars = make_bars([10, 10, 10, 10, 9.0], lows=[10, 10, 10, 10, 8.8])
        assert not ma_support_edge(bars, 4, periods=(3,), lookback=2)


class TestLowVolumePullback:
    def test_quiet_pullback_after_high_volume_advance(self):
        closes = list(range(10, 40)) + [39, 38, 37, 36, 35]
        volumes = [100] * 30 + [30] * 5
        bars = make_bars(closes, volumes=volumes)
        assert low_volume_pullback(bars, len(bars) - 1)

    def test_heavy_pullback_fails(self):
        closes = list(range(10, 40)) + [39, 38, 37, 36, 35]
        volumes = [100] * 30 + [100] * 5
        bars = make_bars(closes, volumes=volumes)
        assert not low_volume_pullback(bars, len(bars) - 1)

    def test_no_down_bars_fails_closed(self):
        bars = make_bars(list(range(1, 40)))
        assert not low_volume_pullback(bars, 38)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
