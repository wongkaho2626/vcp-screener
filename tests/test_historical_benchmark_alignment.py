import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
)

import screen_vcp


def test_historical_analysis_aligns_benchmark_by_date(monkeypatch):
    """A shorter stock history must not shift SPY into a future session."""
    stock = [
        {"date": "2024-01-05", "close": 105},
        {"date": "2024-01-04", "close": 104},
        {"date": "2024-01-03", "close": 103},
        {"date": "2024-01-02", "close": 102},
    ]
    spy = [
        {"date": "2024-01-08", "close": 508},
        {"date": "2024-01-05", "close": 505},
        {"date": "2024-01-04", "close": 504},
        {"date": "2024-01-03", "close": 503},
        {"date": "2024-01-02", "close": 502},
    ]

    class AlignmentObserved(Exception):
        pass

    def capture_relative_strength(stock_prices, benchmark_prices):
        assert stock_prices[0]["date"] == "2024-01-03"
        assert benchmark_prices[0]["date"] == "2024-01-03"
        assert all(row["date"] <= "2024-01-03" for row in benchmark_prices)
        raise AlignmentObserved

    monkeypatch.setattr(
        screen_vcp, "calculate_relative_strength", capture_relative_strength,
    )
    with pytest.raises(AlignmentObserved):
        screen_vcp.analyze_stock(
            "TEST", stock,
            {"price": 103, "yearHigh": 105, "yearLow": 102,
             "avgVolume": 1, "marketCap": 0},
            spy, as_of_offset=2,
        )


def test_benchmark_binary_search_uses_prior_session_when_date_is_absent():
    spy = [
        {"date": "2024-01-08"},
        {"date": "2024-01-05"},
        {"date": "2024-01-04"},
        {"date": "2024-01-03"},
    ]
    assert [row["date"] for row in screen_vcp._benchmark_on_or_before(
        spy, "2024-01-06",
    )] == ["2024-01-05", "2024-01-04", "2024-01-03"]
