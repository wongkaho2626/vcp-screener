"""Unit tests for fetch_r2k_membership pure functions (holdings-CSV parsing,
snapshot->interval construction, quarter-end candidate dates)."""

import os
import sys

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
)

from fetch_r2k_membership import (
    build_intervals,
    parse_holdings_csv,
    quarter_end_candidates,
)

SAMPLE = """iShares Russell 2000 ETF
Fund Holdings as of,"Jun 28, 2019"
Inception Date,"May 22, 2000"
Shares Outstanding,"271,350,000.00"
Stock,"-"

Ticker,Name,Sector,Asset Class,Market Value,Weight (%),Notional Value,Quantity,Price,Location,Exchange,Currency,FX Rate,Market Currency,Accrual Date
ABC,Alpha Beta Corp,Industrials,Equity,"1,000","0.10","1,000","10","100.00",United States,NASDAQ,USD,1.00,USD,--
XYZ.A,Xylophone Class A,Financials,Equity,"2,000","0.20","2,000","20","100.00",United States,NYSE,USD,1.00,USD,--
XTSLA,BLK CSH FND TREASURY SL AGENCY,Cash and/or Derivatives,Money Market,"9,999","0.99","9,999","99","1.00",United States,--,USD,1.00,USD,--
RTYU6,RUSSELL 2000 EMINI CME JUN 26,Cash and/or Derivatives,Futures,"5,000","0.50","5,000","5","1,000.00",United States,CME,USD,1.00,USD,--
"""


class TestParseHoldingsCsv:
    def test_extracts_equity_tickers_only(self):
        assert parse_holdings_csv(SAMPLE) == ["ABC", "XYZ-A"]

    def test_dot_class_symbols_normalized_to_dash(self):
        assert "XYZ-A" in parse_holdings_csv(SAMPLE)

    def test_html_response_returns_empty(self):
        assert parse_holdings_csv("<!DOCTYPE html><html>...</html>") == []


class TestBuildIntervals:
    def test_continuous_membership_is_open_ended(self):
        snaps = [("2020-03-31", ["A", "B"]), ("2020-06-30", ["A", "B"])]
        rows = build_intervals(snaps)
        assert ("A", "2020-03-31", "") in rows
        assert ("B", "2020-03-31", "") in rows

    def test_departure_closes_interval_at_last_seen(self):
        snaps = [("2020-03-31", ["A", "B"]), ("2020-06-30", ["A"])]
        rows = build_intervals(snaps)
        assert ("B", "2020-03-31", "2020-03-31") in rows
        assert ("A", "2020-03-31", "") in rows

    def test_reentry_creates_second_interval(self):
        snaps = [("2020-03-31", ["A"]), ("2020-06-30", []), ("2020-09-30", ["A"])]
        rows = build_intervals(snaps)
        assert rows.count(("A", "2020-03-31", "2020-03-31")) == 1
        assert rows.count(("A", "2020-09-30", "")) == 1


class TestQuarterEndCandidates:
    def test_walks_back_from_calendar_quarter_end(self):
        cands = quarter_end_candidates(2019, 2, max_back=3)
        assert cands == ["20190630", "20190629", "20190628"]

    def test_q4_uses_december_31(self):
        assert quarter_end_candidates(2020, 4, max_back=1) == ["20201231"]


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
