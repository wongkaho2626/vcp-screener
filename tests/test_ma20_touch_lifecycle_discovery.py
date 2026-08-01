from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from ma20_touch_lifecycle_discovery import ma20_states


def bars(closes: list[float], lows: list[float]) -> list[dict]:
    return [{"date": f"d{i:03d}", "open": close, "high": close + 1,
             "low": low, "close": close, "volume": 1000}
            for i, (close, low) in enumerate(zip(closes, lows))]


def row(index: int) -> dict:
    return {"setup_id": "AAA|d000|0", "symbol": "AAA", "sector": "Tech",
            "as_of_date": "d000", "signal_date": f"d{index:03d}",
            "fill_date": f"d{index + 1:03d}", "fill_idx": index + 1,
            "edge_rank": 70, "pattern_stop": 5, "pivot": 10,
            "close": 20, "features": [0.0] * 15}


def test_ma20_touch_requires_prior_pivot_crossover_and_fresh_transition() -> None:
    prices = {"AAA": bars([9, 11, 11, 11], [8, 10, 10, 10])}
    states = ma20_states([row(1), row(2), row(3)], prices, ma_period=2)
    assert [state["positive_cross"] for state in states] == [True, False, False]


def test_ma20_touch_rearms_after_a_non_touch_session() -> None:
    prices = {"AAA": bars([9, 11, 11, 11], [8, 10, 12, 10])}
    states = ma20_states([row(1), row(2), row(3)], prices, ma_period=2)
    assert [state["positive_cross"] for state in states] == [True, False, True]


def test_ma20_negative_state_is_close_below_causal_average() -> None:
    prices = {"AAA": bars([9, 11, 8], [8, 10, 7])}
    states = ma20_states([row(1), row(2)], prices, ma_period=2)
    assert states[-1]["negative_dominance"] is True


def test_future_append_cannot_change_existing_ma20_states() -> None:
    prices = {"AAA": bars([9, 11, 11, 11], [8, 10, 12, 10])}
    rows = [row(1), row(2), row(3)]
    before = ma20_states(rows, prices, ma_period=2)
    extended = {"AAA": bars([9, 11, 11, 11, 1, 100], [8, 10, 12, 10, 0, 99])}
    assert ma20_states(rows, extended, ma_period=2) == before
