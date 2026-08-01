from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from avwap_strength_exit_discovery import (
    is_fresh_close_high,
    strength_lifecycle_signals,
)


def bars(closes: list[float]) -> list[dict]:
    return [{"date": f"d{index:03d}", "open": close,
             "high": close + 1, "low": close - 1,
             "close": close, "volume": 1000}
            for index, close in enumerate(closes)]


def row(index: int, reclaim: bool = False,
        fresh: bool = False) -> dict:
    return {"setup_id": "AAA|d000|0", "symbol": "AAA", "sector": "Tech",
            "as_of_date": "d000", "signal_date": f"d{index:03d}",
            "fill_date": f"d{index + 1:03d}", "fill_idx": index + 1,
            "edge_rank": 70, "pattern_stop": 5, "pivot": 10,
            "reclaim": reclaim, "fresh_close_high": fresh}


def test_fresh_close_high_is_strict_and_future_invariant() -> None:
    history = bars([10, 11, 10, 12, 13])
    assert is_fresh_close_high(history, 4, window=5)
    tied = bars([10, 13, 10, 12, 13])
    assert not is_fresh_close_high(tied, 4, window=5)
    extended = [*history, {"date": "d005", "open": 1, "high": 2,
                           "low": .5, "close": 1, "volume": 1000}]
    assert is_fresh_close_high(extended, 4, window=5)


def test_strength_exit_waits_minimum_hold_and_fills_next_open() -> None:
    states = [row(index, reclaim=(index == 0), fresh=(index in {5, 9, 10}))
              for index in range(13)]
    signals = strength_lifecycle_signals(states, max_attempts=3, min_hold=10)
    assert len(signals) == 1
    assert signals[0]["fill_idx"] == 1
    assert signals[0]["model_exit_idx"] == 11


def test_strength_lifecycle_requires_later_reclaim_and_caps_attempts() -> None:
    states = []
    for index in range(40):
        states.append(row(index, reclaim=index in {0, 12, 24, 36},
                          fresh=index in {10, 22, 34}))
    signals = strength_lifecycle_signals(states, max_attempts=3, min_hold=10)
    assert [signal["fill_idx"] for signal in signals] == [1, 13, 25]
    assert [signal["model_exit_idx"] for signal in signals] == [11, 23, 35]
