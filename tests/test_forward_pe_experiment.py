"""Unit tests for forward_pe_experiment pure functions (PIT lookup, trailing
percentile, trade annotation). Synthetic series only — no real data."""

import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
)

from forward_pe_experiment import (
    annotate_market_valuation,
    fpe_on_date,
    load_forward_pe,
    trailing_percentile,
)


def make_series(values, start_year=2015):
    """Monthly observations on the 15th, oldest first."""
    out = []
    for i, v in enumerate(values):
        year = start_year + i // 12
        month = i % 12 + 1
        out.append((f"{year:04d}-{month:02d}-15", float(v)))
    return out


class TestLoadForwardPe:
    def test_parses_and_sorts(self, tmp_path):
        p = tmp_path / "fpe.csv"
        p.write_text("date,forward_pe\n2020-02-01,17.5\n2020-01-01,16.0\n")
        assert load_forward_pe(str(p)) == [("2020-01-01", 16.0), ("2020-02-01", 17.5)]

    def test_rejects_bad_rows(self, tmp_path):
        p = tmp_path / "fpe.csv"
        p.write_text("date,forward_pe\n2020-01-01,not_a_number\n")
        with pytest.raises(ValueError):
            load_forward_pe(str(p))


class TestFpeOnDate:
    def test_uses_last_observation_on_or_before(self):
        series = make_series([10, 11, 12])
        assert fpe_on_date(series, "2015-02-20") == 11.0
        assert fpe_on_date(series, "2015-01-15") == 10.0

    def test_none_before_first_observation(self):
        series = make_series([10, 11])
        assert fpe_on_date(series, "2014-12-31") is None

    def test_none_when_stale(self):
        # Last observation far in the past must not be carried forward forever.
        series = make_series([10, 11])
        assert fpe_on_date(series, "2016-06-01") is None


class TestTrailingPercentile:
    def test_rising_series_is_high_percentile(self):
        series = make_series(range(1, 61))  # 5y of monthly, strictly rising
        pct = trailing_percentile(series, "2019-12-15", years=5)
        assert pct is not None and pct > 95

    def test_constant_series_is_midrank_50(self):
        series = make_series([20.0] * 60)
        assert trailing_percentile(series, "2019-12-15", years=5) == 50.0

    def test_none_with_too_little_history(self):
        series = make_series([20.0] * 6)
        assert trailing_percentile(series, "2015-06-20", years=5) is None


class TestAnnotateMarketValuation:
    def test_attaches_fields_without_mutating(self):
        series = make_series([20.0] * 60)
        trades = [{"symbol": "AAA", "as_of_date": "2019-12-20", "peg_pe": 30.0}]
        out = annotate_market_valuation(trades, series)
        assert out[0]["market_fpe"] == 20.0
        assert out[0]["market_fpe_pct5y"] == 50.0
        assert out[0]["rel_pe"] == 1.5  # 30 / 20
        assert "market_fpe" not in trades[0]

    def test_missing_inputs_yield_none(self):
        series = make_series([20.0] * 60)
        trades = [{"symbol": "AAA", "as_of_date": "2010-01-05", "peg_pe": None}]
        out = annotate_market_valuation(trades, series)
        assert out[0]["market_fpe"] is None
        assert out[0]["rel_pe"] is None
