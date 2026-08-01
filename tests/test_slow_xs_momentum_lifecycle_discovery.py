from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from slow_xs_momentum_lifecycle_discovery import (
    lifecycle_signals,
    momentum_12_1,
    momentum_rank_states,
)


def bars(closes: list[float]) -> list[dict]:
    return [{"date": f"d{i:03d}", "open": close, "high": close + 1,
             "low": close - 1, "close": close, "volume": 1000}
            for i, close in enumerate(closes)]


def row(symbol: str, index: int, setup: str | None = None) -> dict:
    return {"setup_id": setup or f"{symbol}|d000|0", "symbol": symbol,
            "sector": "Tech", "as_of_date": "d000",
            "signal_date": f"d{index:03d}", "fill_date": f"d{index + 1:03d}",
            "fill_idx": index + 1, "edge_rank": 70,
            "pattern_stop": 5, "pivot": 10, "close": 20,
            "features": [0.0] * 15}


def test_momentum_12_1_uses_skipped_endpoint_and_no_future() -> None:
    history = bars([float(index + 1) for index in range(10)])
    assert momentum_12_1(history, 9, long_lookback=9, skip_recent=2) == 7.0
    assert momentum_12_1(history, 8, long_lookback=9, skip_recent=2) is None


def test_rank_states_rank_same_date_active_symbols() -> None:
    long_prices = {}
    for symbol, endpoint in (("AAA", 2.0), ("BBB", 3.0)):
        closes = [1.0] * 254
        closes[253 - 21] = endpoint
        long_prices[symbol] = bars(closes)
    long_rows = [row("AAA", 253), row("BBB", 253)]
    states = momentum_rank_states(long_rows, long_prices)
    assert [state["momentum_rank"] for state in states] == [0.0, 1.0]


def test_lifecycle_uses_top_rank_then_median_exit_and_reentry() -> None:
    values = [.9, .7, .5, .85]
    states = [{**row("AAA", index, setup="AAA|d000|0"),
               "momentum_12_1": value, "momentum_rank": value,
               "above_pivot": True}
              for index, value in enumerate(values, start=300)]
    signals = lifecycle_signals(states)
    assert [signal["fill_idx"] for signal in signals] == [301, 304]
    assert signals[0]["model_exit_idx"] == 303


def test_future_append_cannot_change_existing_momentum_score() -> None:
    history = bars([float(index + 1) for index in range(260)])
    before = momentum_12_1(history, 259)
    extended = [*history, *bars([1.0, 1000.0])]
    assert momentum_12_1(extended, 259) == before
