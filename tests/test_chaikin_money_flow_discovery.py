from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from chaikin_money_flow_discovery import cmf_series, lifecycle_signals, money_flow_state


def bar(index: int, close: float, high: float = 10, low: float = 0,
        volume: float = 100) -> dict:
    return {"date": f"d{index:03d}", "open": close, "high": high,
            "low": low, "close": close, "volume": volume}


def row(index: int) -> dict:
    return {"setup_id": "AAA|d000|0", "symbol": "AAA", "sector": "Tech",
            "as_of_date": "d000", "signal_date": f"d{index:03d}",
            "fill_date": f"d{index + 1:03d}", "fill_idx": index + 1,
            "edge_rank": 70, "pattern_stop": 80, "pivot": 5,
            "close": 9, "features": [0.0] * 15}


def test_cmf_weights_close_location_by_volume() -> None:
    history = [bar(0, 0, volume=100), bar(1, 10, volume=300)]
    assert cmf_series(history, period=2) == [None, 0.5]


def test_future_append_cannot_change_existing_cmf() -> None:
    history = [bar(0, 2), bar(1, 8), bar(2, 9)]
    before = cmf_series(history, period=2)
    after = cmf_series([*history, bar(3, 0, volume=1_000_000)], period=2)
    assert after[:len(before)] == before


def test_money_flow_entry_requires_zero_cross_and_pivot() -> None:
    history = [bar(0, 2), bar(1, 9)]
    cmf = cmf_series(history, period=1)
    assert money_flow_state(history, cmf, 1, pivot=5) == {
        "accumulation_cross": True, "negative_cmf": False,
    }
    assert not money_flow_state(history, cmf, 1, pivot=12)["accumulation_cross"]


def test_lifecycle_waits_for_two_negative_states_and_caps_attempts() -> None:
    states = []
    values = [(True, False), (False, True), (False, True),
              (True, False), (False, True), (False, True),
              (True, False), (False, True), (False, True), (True, False)]
    for index, (cross, negative) in enumerate(values, start=100):
        states.append({**row(index), "accumulation_cross": cross,
                       "negative_cmf": negative})
    signals = lifecycle_signals(states)
    assert [signal["fill_idx"] for signal in signals] == [101, 104, 107]
    assert [signal["model_exit_idx"] for signal in signals] == [103, 106, 109]
