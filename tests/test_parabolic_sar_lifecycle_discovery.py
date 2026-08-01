from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from parabolic_sar_lifecycle_discovery import (
    lifecycle_signals,
    parabolic_sar_series,
    psar_state,
)


def bars(closes: list[float]) -> list[dict]:
    return [{"date": f"d{i:03d}", "open": close, "high": close + 1,
             "low": close - 1, "close": close, "volume": 1000}
            for i, close in enumerate(closes)]


def row(index: int) -> dict:
    return {"setup_id": "AAA|d000|0", "symbol": "AAA", "sector": "Tech",
            "as_of_date": "d000", "signal_date": f"d{index:03d}",
            "fill_date": f"d{index + 1:03d}", "fill_idx": index + 1,
            "edge_rank": 70, "pattern_stop": 5, "pivot": 10,
            "close": 20, "features": [0.0] * 15}


def test_rising_series_has_sar_below_last_close() -> None:
    history = bars([10, 11, 12, 13, 14, 15])
    sar = parabolic_sar_series(history)
    assert sar[-1] is not None and sar[-1] < history[-1]["close"]


def test_future_append_cannot_change_existing_psar() -> None:
    history = bars([10, 11, 12, 13, 14, 15])
    before = parabolic_sar_series(history)
    after = parabolic_sar_series([*history, *bars([1, 100])])
    assert after[:len(before)] == before


def test_psar_state_requires_close_cross_and_pivot() -> None:
    history = bars([9, 12])
    sar = [10, 10]
    assert psar_state(history, sar, 1, pivot=10) == {
        "positive_cross": True, "negative_dominance": False,
    }
    assert not psar_state(history, sar, 1, pivot=13)["positive_cross"]


def test_lifecycle_requires_two_below_sar_days_and_caps_attempts() -> None:
    states = []
    values = [(True, False), (False, True), (False, True),
              (True, False), (False, True), (False, True),
              (True, False), (False, True), (False, True), (True, False)]
    for index, (cross, negative) in enumerate(values, start=100):
        states.append({**row(index), "positive_cross": cross,
                       "negative_dominance": negative})
    signals = lifecycle_signals(states)
    assert [signal["fill_idx"] for signal in signals] == [101, 104, 107]
    assert [signal["model_exit_idx"] for signal in signals] == [103, 106, 109]
