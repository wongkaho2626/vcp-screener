from __future__ import annotations

import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from audit_existing_2006_plus_data import audit_membership, audit_price_csv


def write_csv(path, rows) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Ticker", "Date", "Open", "High", "Low", "Close",
                         "Adj Close", "Volume"])
        writer.writerows(rows)


def test_price_audit_validates_adjusted_execution_scale(tmp_path) -> None:
    path = tmp_path / "prices.csv"
    write_csv(path, [
        ["AAA", "2020-01-02", 100, 110, 90, 100, 50, 1000],
        ["AAA", "2020-01-03", 50, 55, 45, 50, 50, 2000],
        ["SPY", "2020-01-02", 300, 305, 295, 300, 300, 1],
    ])
    result = audit_price_csv(path)
    assert result["rows"] == 3
    assert result["stock_symbols"] == 1
    assert result["benchmark_present"]
    assert result["adjustment_factor_min"] == .5
    assert result["invalid_adjusted_ohlc_rows"] == 0


def test_price_audit_detects_bad_adjusted_ohlc_and_duplicate(tmp_path) -> None:
    path = tmp_path / "prices.csv"
    write_csv(path, [
        ["AAA", "2020-01-02", 100, 90, 80, 100, 100, 1000],
        ["AAA", "2020-01-02", 100, 90, 80, 100, 100, 1000],
    ])
    result = audit_price_csv(path)
    assert result["duplicate_adjacent_ticker_dates"] == 1
    assert result["invalid_adjusted_ohlc_rows"] == 2


def test_membership_audit_counts_priced_ended_intervals(tmp_path) -> None:
    path = tmp_path / "membership.csv"
    path.write_text("ticker,start_date,end_date\nAAA,2010-01-01,2015-01-01\n"
                    "BBB,2012-01-01,\nCCC,2014-01-01,2018-01-01\n")
    result = audit_membership(path, {"AAA", "BBB"})
    assert result["symbols"] == 3
    assert result["symbols_with_ended_interval"] == 2
    assert result["priced_symbols_with_ended_interval"] == 1
