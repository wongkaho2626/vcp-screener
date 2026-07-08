"""Unit tests for breadth_regime — as-of date lookup, change, and CSV load.
Synthetic data only."""

import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
)

from breadth_regime import breadth_change, breadth_on_date, load_breadth

SERIES = [
    ("2016-01-04", 30.0),
    ("2016-01-05", 32.0),
    ("2016-01-06", 28.0),
    ("2016-01-07", 45.0),
    ("2016-01-08", 50.0),
]


class TestBreadthOnDate:
    def test_exact_date(self):
        assert breadth_on_date(SERIES, "2016-01-06") == 28.0

    def test_weekend_resolves_to_prior_trading_day(self):
        # 2016-01-09 is a Saturday -> last reading is 01-08
        assert breadth_on_date(SERIES, "2016-01-09") == 50.0

    def test_gap_between_dates_uses_most_recent_prior(self):
        assert breadth_on_date([("2016-01-04", 30.0), ("2016-01-11", 40.0)], "2016-01-07") == 30.0

    def test_before_series_start_returns_none(self):
        assert breadth_on_date(SERIES, "2015-12-31") is None


class TestBreadthChange:
    def test_positive_change(self):
        # as-of 01-08 (idx 4) minus 2 rows back (01-06, 28.0) = +22
        assert breadth_change(SERIES, "2016-01-08", lookback=2) == pytest.approx(22.0)

    def test_negative_change(self):
        # as-of 01-06 (idx 2, 28.0) minus 2 rows back (01-04, 30.0) = -2
        assert breadth_change(SERIES, "2016-01-06", lookback=2) == pytest.approx(-2.0)

    def test_insufficient_history_returns_none(self):
        assert breadth_change(SERIES, "2016-01-05", lookback=20) is None


class TestLoadBreadth:
    def test_parses_mmddyyyy_and_sorts(self, tmp_path):
        p = tmp_path / "b.csv"
        p.write_text(
            "Date,breadth,source\n"
            "01/06/2016,28.0,S5TH\n"
            "01/04/2016,30.0,MMTH-mapped\n"
            "01/05/2016,32.0,S5TH\n"
        )
        series = load_breadth(str(p))
        assert series[0] == ("2016-01-04", 30.0)
        assert series[-1] == ("2016-01-06", 28.0)

    def test_skips_blank_and_bad_rows(self, tmp_path):
        p = tmp_path / "b.csv"
        p.write_text(
            "Date,breadth,source\n"
            "01/04/2016,30.0,x\n"
            "01/05/2016,,x\n"          # blank value
            "01/06/2016,notanumber,x\n"  # unparseable
        )
        series = load_breadth(str(p))
        assert series == [("2016-01-04", 30.0)]

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_breadth("/nonexistent/breadth.csv")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
