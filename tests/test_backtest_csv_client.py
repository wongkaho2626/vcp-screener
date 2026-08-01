import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from backtest_vcp import CSVHistoricalClient
from csv_client import CSVClient


def test_detector_and_portfolio_csv_clients_use_identical_adjusted_ohlc(tmp_path):
    path = tmp_path / "prices.csv"
    path.write_text(
        "Ticker,Date,Open,High,Low,Close,Adj Close,Volume\n"
        "AAA,2020-01-02,100,110,90,100,50,1234\n"
        "AAA,2020-01-03,102,112,92,102,51,2345\n"
    )

    detector = CSVHistoricalClient(str(path)).get_historical_prices("AAA", days=10)
    portfolio = CSVClient(str(path)).get_historical_prices("AAA", days=10)

    assert detector["historical"] == portfolio["historical"]
    latest = detector["historical"][0]
    assert latest == {
        "date": "2020-01-03", "open": 51.0, "high": 56.0,
        "low": 46.0, "close": 51.0, "adjClose": 51.0, "volume": 2345,
    }


def test_detector_falls_back_to_raw_scale_when_adjusted_close_is_missing(tmp_path):
    path = tmp_path / "prices.csv"
    path.write_text(
        "Ticker,Date,Open,High,Low,Close,Adj Close,Volume\n"
        "AAA,2020-01-02,100,110,90,100,,1234\n"
    )

    bar = CSVHistoricalClient(str(path)).get_historical_prices("AAA")["historical"][0]
    assert (bar["open"], bar["high"], bar["low"], bar["close"]) == (100, 110, 90, 100)
