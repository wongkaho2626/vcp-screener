"""Tests for the S&P 500 history CSV downloader."""

import csv
import json
import os
import sys

import pandas as pd

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
)

from download_sp500_history import (
    COLUMNS,
    download_to_csv,
    extract_symbol_frame,
    iter_csv_rows,
    load_symbols,
)


def _ticker_first_frame():
    index = pd.to_datetime(["2024-01-03", "2024-01-02"])
    columns = pd.MultiIndex.from_product(
        [["AAPL", "MSFT"], ["Open", "High", "Low", "Close", "Adj Close", "Volume"]]
    )
    values = [
        [10, 12, 9, 11, 10.5, 100, 20, 22, 19, 21, 20.5, 200],
        [9, 11, 8, 10, 9.5, 90, 19, 21, 18, 20, 19.5, 190],
    ]
    return pd.DataFrame(values, index=index, columns=columns)


def test_load_symbols_normalizes_deduplicates_and_sorts(tmp_path):
    path = tmp_path / "constituents.json"
    path.write_text(json.dumps([{"symbol": "MSFT"}, {"symbol": "BRK.B"}, {"symbol": "MSFT"}]))

    assert load_symbols(path) == ["BRK-B", "MSFT"]


def test_extracts_ticker_from_ticker_first_multiindex():
    result = extract_symbol_frame(_ticker_first_frame(), "MSFT", 2)

    assert list(result.columns) == ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    assert result.iloc[0]["Close"] == 21


def test_iter_csv_rows_sorts_dates_and_falls_back_to_close_for_adjusted():
    frame = pd.DataFrame(
        {
            "Open": [10, 9],
            "High": [12, 11],
            "Low": [9, 8],
            "Close": [11, 10],
            "Volume": [100.0, float("nan")],
        },
        index=pd.to_datetime(["2024-01-03", "2024-01-02"]),
    )

    rows = list(iter_csv_rows("AAPL", frame))

    assert [row[1] for row in rows] == ["2024-01-02", "2024-01-03"]
    assert rows[0][6:] == [10.0, 0]


def test_download_to_csv_writes_combined_file(tmp_path):
    frame = _ticker_first_frame()
    calls = []

    def fake_download(symbols, **kwargs):
        calls.append((symbols, kwargs))
        return frame

    output = tmp_path / "prices.csv"
    count, failed = download_to_csv(
        ["AAPL", "MSFT"],
        output,
        batch_size=2,
        retries=1,
        retry_delay=0,
        sleep_secs=0,
        downloader=fake_download,
    )

    assert count == 4
    assert failed == []
    assert calls[0][1]["period"] == "max"
    with output.open(newline="") as file:
        rows = list(csv.reader(file))
    assert rows[0] == COLUMNS
    assert [row[0] for row in rows[1:]] == ["AAPL", "AAPL", "MSFT", "MSFT"]


def test_date_range_uses_start_and_end_instead_of_period(tmp_path):
    frame = _ticker_first_frame().loc[:, "AAPL"]
    captured = {}

    def fake_download(symbols, **kwargs):
        captured.update(kwargs)
        return frame

    download_to_csv(
        ["AAPL"],
        tmp_path / "prices.csv",
        start="2024-01-01",
        end="2024-02-01",
        retries=1,
        retry_delay=0,
        sleep_secs=0,
        downloader=fake_download,
    )

    assert captured["start"] == "2024-01-01"
    assert captured["end"] == "2024-02-01"
    assert "period" not in captured
