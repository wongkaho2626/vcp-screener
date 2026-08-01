from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from month_start_flow_lifecycle_discovery import (
    first_session_dates,
    month_start_signals,
)


def _bar(day: str, close: float = 101.0) -> dict:
    return {"date": day, "open": close, "high": close + 1,
            "low": close - 1, "close": close, "volume": 1_000}


def _rows(bars: list[dict], pivot: float = 100.0) -> list[dict]:
    return [{
        "setup_id": "AAA|2020-01-30|0", "symbol": "AAA", "sector": "Tech",
        "signal_date": bar["date"], "fill_date": bars[index + 1]["date"],
        "fill_idx": index + 1, "edge_rank": 70.0, "pattern_stop": 90.0,
        "pivot": pivot, "close": bar["close"],
    } for index, bar in enumerate(bars[:-1])]


def test_first_session_comes_from_benchmark_calendar() -> None:
    spy = [_bar("2020-01-31"), _bar("2020-02-03"), _bar("2020-02-04"),
           _bar("2020-03-02")]
    assert first_session_dates(spy) == {"2020-02-03", "2020-03-02"}


def test_month_start_signal_fills_next_open_and_exits_after_three_sessions() -> None:
    bars = [_bar("2020-01-31"), _bar("2020-02-03", 102),
            _bar("2020-02-04"), _bar("2020-02-05"),
            _bar("2020-02-06"), _bar("2020-02-07")]
    signals = month_start_signals(_rows(bars), {"AAA": bars}, bars)
    assert len(signals) == 1
    signal = signals[0]
    assert signal["signal_date"] == "2020-02-03"
    assert signal["fill_date"] == "2020-02-04"
    assert signal["fill_idx"] == 2
    assert signal["model_exit_idx"] == 5


def test_close_must_be_strictly_above_frozen_pivot() -> None:
    bars = [_bar("2020-01-31"), _bar("2020-02-03", 100),
            _bar("2020-02-04"), _bar("2020-02-05")]
    assert month_start_signals(_rows(bars), {"AAA": bars}, bars) == []


def test_stock_history_cannot_invent_a_month_start() -> None:
    spy = [_bar("2020-02-03"), _bar("2020-02-04"), _bar("2020-02-05"),
           _bar("2020-02-06")]
    stock = [_bar("2020-02-04"), _bar("2020-02-05"), _bar("2020-02-06")]
    assert month_start_signals(_rows(stock), {"AAA": stock}, spy) == []


def test_calendar_signal_is_truncation_invariant() -> None:
    bars = [_bar("2020-01-31"), _bar("2020-02-03", 102),
            _bar("2020-02-04"), _bar("2020-02-05"),
            _bar("2020-02-06"), _bar("2020-02-07")]
    initial = month_start_signals(_rows(bars), {"AAA": bars}, bars)
    extended = bars + [_bar("2020-02-10", 300)]
    later = month_start_signals(_rows(extended), {"AAA": extended}, extended)
    assert later[0] == initial[0]
