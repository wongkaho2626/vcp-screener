from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from rs_line_leadership_discovery import (
    lifecycle_signals,
    relative_strength_series,
)


def bars(dates: list[str], closes: list[float]) -> list[dict]:
    return [{"date": date, "open": close, "high": close + 1,
             "low": close - 1, "close": close, "volume": 1000}
            for date, close in zip(dates, closes)]


def row(index: int, *, setup: str = "AAA|d00|0") -> dict:
    return {"setup_id": setup, "symbol": "AAA", "sector": "Tech",
            "signal_date": f"d{index:02d}", "fill_date": f"d{index + 1:02d}",
            "fill_idx": index + 1, "edge_rank": 70, "pattern_stop": 90,
            "pivot": 100, "close": 110, "features": [0.0] * 15}


def test_relative_strength_uses_latest_benchmark_not_after_stock_date() -> None:
    stock = bars(["2020-01-02", "2020-01-03"], [100, 110])
    spy = bars(["2020-01-01", "2020-01-04"], [50, 500])
    assert relative_strength_series(stock, spy) == [2.0, 2.2]


def test_appended_future_benchmark_cannot_change_existing_rs() -> None:
    stock = bars(["2020-01-02", "2020-01-03"], [100, 110])
    spy = bars(["2020-01-01"], [50])
    before = relative_strength_series(stock, spy)
    future = bars(["2020-01-04"], [500])
    assert relative_strength_series(stock, [*spy, *future]) == before


def test_lifecycle_waits_for_joint_rs_and_stock_trend_failure() -> None:
    states = []
    values = [
        (True, True, True, True),
        (False, True, False, True),
        (False, True, True, True),
        (True, True, True, True),
        (False, False, False, False),
    ]
    for i, (new_high, entry_ok, below_rs, below_stock) in enumerate(values, start=70):
        states.append({**row(i), "rs_new_high": new_high,
                       "entry_confirmed": entry_ok,
                       "below_rs_sma20": below_rs,
                       "below_stock_sma20": below_stock})
    signals = lifecycle_signals(states, max_attempts=3)
    assert len(signals) == 2
    assert signals[0]["fill_idx"] == 71
    # Row 71 has only stock failure; the joint failure arrives on row 72.
    assert signals[0]["model_exit_idx"] == 73


def test_entry_requires_rs_high_and_price_confirmation() -> None:
    states = [{**row(70), "rs_new_high": True, "entry_confirmed": False,
               "below_rs_sma20": False, "below_stock_sma20": False}]
    assert lifecycle_signals(states) == []
