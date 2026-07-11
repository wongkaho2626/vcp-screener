"""Unit tests for momentum_validation pure functions (turnover, cost drag,
volatility scaling, equal-weight benchmark index)."""

import math
import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
)

from momentum_validation import (
    apply_costs,
    build_ew_index,
    replaced_fraction,
    series_stats,
    vol_scaled,
)


class TestReplacedFraction:
    def test_first_month_is_full_buy(self):
        assert replaced_fraction([], ["A", "B"]) == pytest.approx(1.0)

    def test_identical_holdings_zero(self):
        assert replaced_fraction(["A", "B"], ["B", "A"]) == pytest.approx(0.0)

    def test_half_replaced(self):
        assert replaced_fraction(["A", "B"], ["A", "C"]) == pytest.approx(0.5)


class TestApplyCosts:
    def test_drag_is_turnover_times_roundtrip(self):
        # 100bp round trip on 50% turnover → 0.5% drag per month.
        net = apply_costs([2.0, 1.0], [1.0, 0.5], roundtrip_bp=100.0)
        assert net == [pytest.approx(1.0), pytest.approx(0.5)]

    def test_zero_cost_is_identity(self):
        assert apply_costs([1.5, -0.5], [1.0, 0.3], roundtrip_bp=0.0) == [1.5, -0.5]


class TestVolScaled:
    def test_warmup_months_unscaled(self):
        vals = [1.0, -1.0, 2.0, 0.5]
        out = vol_scaled(vals, window=3)
        assert out[:3] == vals[:3]

    def test_derisks_after_high_vol_never_levers(self):
        # Calm first 3 months (±0.1), then a wild month; the next month's
        # trailing vol >> target → weight < 1. Weights never exceed 1.
        vals = [0.1, -0.1, 0.1, 20.0, 1.0, 1.0]
        out = vol_scaled(vals, window=3)
        assert abs(out[4]) < abs(vals[4])
        for got, raw in zip(out, vals):
            assert abs(got) <= abs(raw) + 1e-9

    def test_scaling_preserves_sign(self):
        vals = [0.1, -0.1, 0.1, 20.0, -3.0, 2.0]
        out = vol_scaled(vals, window=3)
        assert out[4] < 0 and out[5] > 0


class TestBuildEwIndex:
    def test_ew_index_averages_daily_returns(self):
        # Sym A: +10% then +10%; Sym B: flat. EW daily returns: +5%, +5%.
        a = [{"date": "d1", "close": 10}, {"date": "d2", "close": 11},
             {"date": "d3", "close": 12.1}]
        b = [{"date": "d1", "close": 20}, {"date": "d2", "close": 20},
             {"date": "d3", "close": 20}]
        chrono, idx = build_ew_index([a, b])
        assert [bar["date"] for bar in chrono] == ["d1", "d2", "d3"]
        assert idx["d2"] == 1
        r1 = chrono[1]["close"] / chrono[0]["close"] - 1
        r2 = chrono[2]["close"] / chrono[1]["close"] - 1
        assert r1 == pytest.approx(0.05)
        assert r2 == pytest.approx(0.05)

    def test_symbol_missing_a_date_is_skipped_that_day(self):
        # B lacks d2 → d2 return uses only A (+10%).
        a = [{"date": "d1", "close": 10}, {"date": "d2", "close": 11}]
        b = [{"date": "d1", "close": 20}]
        chrono, _ = build_ew_index([a, b])
        r1 = chrono[1]["close"] / chrono[0]["close"] - 1
        assert r1 == pytest.approx(0.10)

    def test_glitch_daily_return_is_excluded(self):
        # B jumps +1900% in a day (bad data) — excluded, so the index
        # return is A's +10% alone.
        a = [{"date": "d1", "close": 10}, {"date": "d2", "close": 11}]
        b = [{"date": "d1", "close": 1}, {"date": "d2", "close": 20}]
        chrono, _ = build_ew_index([a, b])
        r1 = chrono[1]["close"] / chrono[0]["close"] - 1
        assert r1 == pytest.approx(0.10)


class TestSeriesStats:
    def test_ruinous_series_reports_nan_ann_not_crash(self):
        # A month worse than -100% sends the compounded level negative;
        # annualised return must degrade to NaN instead of raising.
        s = series_stats([5.0, -120.0, 3.0, 1.0, 2.0, -1.0])
        assert math.isnan(s["ann"])
        assert s["mdd"] <= -100.0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
