from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from path_efficiency_lifecycle_discovery import (
    lifecycle_signals,
    signed_efficiency,
    sma,
)


def bars(closes: list[float]) -> list[dict]:
    return [{"date": f"d{i:02d}", "open": value, "high": value + 1,
             "low": value - 1, "close": value, "volume": 1000}
            for i, value in enumerate(closes)]


def row(signal_idx: int, *, setup: str = "AAA|d10|0", close: float = 110,
        pivot: float = 100) -> dict:
    return {"setup_id": setup, "symbol": "AAA", "sector": "Tech",
            "as_of_date": "d10", "signal_date": f"d{signal_idx:02d}",
            "fill_date": f"d{signal_idx + 1:02d}", "fill_idx": signal_idx + 1,
            "edge_rank": 70, "pattern_stop": 90, "pivot": pivot,
            "close": close, "features": [0.0] * 15}


def test_signed_efficiency_distinguishes_smooth_from_choppy_path() -> None:
    smooth = bars([100 + i for i in range(11)])
    choppy = bars([100, 102, 100, 102, 100, 102, 100, 102, 100, 102, 101])
    assert signed_efficiency(smooth, 10, 10) == 1.0
    assert 0 < signed_efficiency(choppy, 10, 10) < .10


def test_signed_efficiency_and_sma_are_causal_under_future_append() -> None:
    history = bars([100 + i for i in range(25)])
    before = (signed_efficiency(history, 20, 10), sma(history, 20, 20))
    after = history + bars([500, 600])
    assert (signed_efficiency(after, 20, 10), sma(after, 20, 20)) == before


def test_lifecycle_fresh_cross_exit_and_three_attempt_limit() -> None:
    states = []
    values = [
        (.20, True, True), (.40, True, True), (.50, True, True),
        (-.10, True, True), (.40, True, True), (.10, False, True),
        (.40, True, True), (-.05, True, True), (.40, True, True),
        (-.05, True, True), (.40, True, True),
    ]
    for i, (efficiency, above_sma, above_pivot) in enumerate(values, start=20):
        states.append({**row(i, close=110 if above_pivot else 90),
                       "efficiency": efficiency,
                       "above_sma20": above_sma,
                       "above_pivot": above_pivot})
    signals = lifecycle_signals(states, entry_threshold=.30, max_attempts=3)
    assert [signal["attempt"] for signal in signals] == [1, 2, 3]
    assert [signal["fill_idx"] for signal in signals] == [22, 25, 27]
    assert [signal["model_exit_idx"] for signal in signals] == [24, 26, 28]


def test_entry_requires_pivot_and_sma_confirmation() -> None:
    states = [
        {**row(20), "efficiency": .20, "above_sma20": True, "above_pivot": True},
        {**row(21), "efficiency": .40, "above_sma20": False, "above_pivot": True},
    ]
    assert lifecycle_signals(states) == []
