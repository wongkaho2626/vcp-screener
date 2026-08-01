from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from anchored_vwap_reclaim_discovery import (
    anchored_vwap_series,
    lifecycle_signals,
    reclaim_state,
)


def bars(values: list[tuple[float, float]]) -> list[dict]:
    return [
        {"date": f"d{i:03d}", "open": close, "high": close + 1,
         "low": close - 1, "close": close, "volume": volume}
        for i, (close, volume) in enumerate(values)
    ]


def row(index: int) -> dict:
    return {"setup_id": "AAA|d000|0", "symbol": "AAA", "sector": "Tech",
            "as_of_date": "d000", "signal_date": f"d{index:03d}",
            "fill_date": f"d{index + 1:03d}", "fill_idx": index + 1,
            "edge_rank": 70, "pattern_stop": 80, "pivot": 100,
            "close": 110, "features": [0.0] * 15}


def test_anchored_vwap_uses_typical_price_and_volume() -> None:
    history = [
        {"date": "d000", "open": 8, "high": 12, "low": 6,
         "close": 9, "volume": 100},
        {"date": "d001", "open": 18, "high": 24, "low": 12,
         "close": 18, "volume": 300},
    ]
    values = anchored_vwap_series(history, anchor_idx=0)
    assert values[0] == 9
    assert values[1] == 15.75


def test_future_append_cannot_change_existing_anchored_vwap() -> None:
    history = bars([(90, 100), (110, 200), (105, 300)])
    before = anchored_vwap_series(history, anchor_idx=0)
    extended = [*history, *bars([(500, 1_000_000)])]
    after = anchored_vwap_series(extended, anchor_idx=0)
    assert after[:len(before)] == before


def test_reclaim_requires_cross_from_below_and_frozen_pivot() -> None:
    history = bars([(90, 100), (110, 100)])
    avwap = anchored_vwap_series(history, anchor_idx=0)
    assert reclaim_state(history, avwap, 1, pivot=100) == {
        "reclaim": True, "below_avwap": False,
    }
    assert not reclaim_state(history, avwap, 1, pivot=115)["reclaim"]


def test_lifecycle_uses_two_close_exit_next_open_and_limits_attempts() -> None:
    states = []
    values = [
        (True, False), (False, True), (False, False), (False, True),
        (False, True), (True, False), (False, True), (False, True),
        (True, False), (False, True), (False, True), (True, False),
    ]
    for index, (reclaim, below) in enumerate(values, start=150):
        states.append({**row(index), "reclaim": reclaim, "below_avwap": below})
    signals = lifecycle_signals(states, max_attempts=3, exit_confirm_closes=2)
    assert [signal["attempt"] for signal in signals] == [1, 2, 3]
    assert [signal["fill_idx"] for signal in signals] == [151, 156, 159]
    assert [signal["model_exit_idx"] for signal in signals] == [155, 158, 161]
